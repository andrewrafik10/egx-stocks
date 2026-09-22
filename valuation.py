"""
Four valuation methods applied per stock. Each returns (fair_value_per_share, note)
or (None, reason) when the method isn't applicable/reliable for that stock.

These are deliberately simple, transparent models - not a substitute for the
line-by-line models in your IB portfolio work. Treat outputs as a screening
signal, not a price target.
"""

import math
from typing import Optional, Tuple

import config
from scraper import CompanyFundamentals


def pe_valuation(cf: CompanyFundamentals, sector_median_pe: Optional[float]) -> Tuple[Optional[float], str]:
    """Fair value = EPS x sector median P/E. Prefers forward (consensus)
    EPS over trailing EPS when the site has a usable forward P/E - forward
    estimates are less distorted by one-off items and stale historical
    earnings, which matters a lot in Egypt's inflationary environment.
    Falls back to trailing EPS, then to a market-wide default multiple."""
    use_forward = cf.forward_eps is not None and cf.forward_eps > 0
    eps_to_use = cf.forward_eps if use_forward else cf.eps
    if eps_to_use is None or eps_to_use <= 0:
        return None, "no positive EPS (forward or trailing)"
    multiple = sector_median_pe
    if multiple is None or multiple <= 0:
        return None, "no sector P/E benchmark available"
    label = "forward" if use_forward else "trailing"
    return eps_to_use * multiple, f"{label} EPS {eps_to_use:.2f} x sector median P/E {multiple:.1f}x"


def graham_number(cf: CompanyFundamentals) -> Tuple[Optional[float], str]:
    """Graham formula: sqrt(GRAHAM_MULTIPLIER x EPS x BVPS), where
    GRAHAM_MULTIPLIER = GRAHAM_PE_CAP x GRAHAM_PB_CAP (see config.py).
    Unreliable for banks/financials (book value distorted by leverage - flagged
    separately in ranking.py) and meaningless with negative EPS or BVPS."""
    if cf.eps is None or cf.book_value_per_share is None:
        return None, "missing EPS or book value/share"
    if cf.eps <= 0 or cf.book_value_per_share <= 0:
        return None, "negative EPS or book value"
    value = math.sqrt(config.GRAHAM_MULTIPLIER * cf.eps * cf.book_value_per_share)
    return value, f"sqrt({config.GRAHAM_MULTIPLIER} x {cf.eps:.2f} x {cf.book_value_per_share:.2f})"


def _estimate_growth_rate(history: list, fallback: float = 0.10, cap: float = 0.35) -> float:
    """CAGR from oldest to newest value in history list, clipped to a sane range.
    Falls back when either endpoint is non-positive, since a negative-to-positive
    (or vice versa) swing makes a fractional-power CAGR produce a complex number."""
    vals = [v for v in history if v is not None]
    if len(vals) < 2 or vals[0] <= 0 or vals[-1] <= 0:
        return fallback
    years = len(vals) - 1
    try:
        cagr = (vals[-1] / vals[0]) ** (1 / years) - 1
    except (ValueError, ZeroDivisionError):
        return fallback
    return max(-0.10, min(cap, cagr))


def dcf_valuation(cf: CompanyFundamentals) -> Tuple[Optional[float], str]:
    """Simplified FCFE-style DCF per share:
      1. Estimate historical FCF growth rate (capped)
      2. Project FCF for DCF_PROJECTION_YEARS, fading growth toward terminal rate
      3. Discount at DEFAULT_COST_OF_EQUITY
      4. Add discounted terminal value (Gordon growth)
      5. Divide by shares outstanding

    Requires positive current FCF - flagged as unreliable otherwise (common for
    capex-heavy or early-stage names, per your modeling notes on this). Also
    requires a reasonably stable FCF history (majority-positive), since a
    single good year sandwiched between loss years produces a fair value that
    isn't really trustworthy even though the current year happens to be positive.
    """
    if cf.free_cash_flow is None or cf.free_cash_flow <= 0:
        return None, "no positive free cash flow"
    if not cf.shares_outstanding:
        return None, "missing shares outstanding"
    if cf.fcf_history:
        positive_years = sum(1 for v in cf.fcf_history if v is not None and v > 0)
        if positive_years < len(cf.fcf_history) / 2:
            return None, f"FCF history too volatile ({positive_years}/{len(cf.fcf_history)} positive years)"

    g0 = _estimate_growth_rate(cf.fcf_history, fallback=0.12)
    r = config.DEFAULT_COST_OF_EQUITY
    gt = config.DEFAULT_TERMINAL_GROWTH
    n = config.DCF_PROJECTION_YEARS

    if r <= gt:
        return None, "cost of equity must exceed terminal growth"

    fcf = cf.free_cash_flow
    pv_sum = 0.0
    growth = g0
    for year in range(1, n + 1):
        if config.FCF_HIGH_GROWTH_FADE:
            growth = g0 + (gt - g0) * (year / n)
        fcf = fcf * (1 + growth)
        pv_sum += fcf / ((1 + r) ** year)

    terminal_value = (fcf * (1 + gt)) / (r - gt)
    pv_terminal = terminal_value / ((1 + r) ** n)

    equity_value = pv_sum + pv_terminal
    value_per_share = equity_value / cf.shares_outstanding
    return value_per_share, f"FCF growth {g0:.1%} fading to {gt:.1%}, r={r:.1%}, {n}yr"


def comps_valuation(cf: CompanyFundamentals, sector_median_ev_ebitda: Optional[float]) -> Tuple[Optional[float], str]:
    """Implied equity value via EV/EBITDA peer multiple:
      implied EV = EBITDA x sector median EV/EBITDA
      implied equity value = EV - net debt
    """
    if cf.ebitda is None or cf.ebitda <= 0:
        return None, "no positive EBITDA"
    if sector_median_ev_ebitda is None or sector_median_ev_ebitda <= 0:
        return None, "no sector EV/EBITDA benchmark"
    if not cf.shares_outstanding:
        return None, "missing shares outstanding"

    net_debt = (cf.total_debt or 0) - (cf.cash or 0)
    implied_ev = cf.ebitda * sector_median_ev_ebitda
    implied_equity = implied_ev - net_debt
    if implied_equity <= 0:
        return None, "implied equity value negative"
    return implied_equity / cf.shares_outstanding, f"EBITDA {cf.ebitda:,.0f} x peer EV/EBITDA {sector_median_ev_ebitda:.1f}x, less net debt"


def run_all_methods(cf: CompanyFundamentals, sector_median_pe: Optional[float],
                     sector_median_ev_ebitda: Optional[float]) -> dict:
    """Returns {method: {"fair_value": float|None, "note": str}}"""
    results = {}
    for name, fn_result in [
        ("pe", pe_valuation(cf, sector_median_pe)),
        ("graham", graham_number(cf)),
        ("dcf", dcf_valuation(cf)),
        ("comps", comps_valuation(cf, sector_median_ev_ebitda)),
    ]:
        fair_value, note = fn_result
        results[name] = {"fair_value": fair_value, "note": note}
    return results

