"""
Combines the 4 valuation methods into a per-stock composite "upside score" and
ranks the universe. Handles missing/inapplicable methods gracefully by
re-normalizing weights across whatever methods actually produced a value.

Peer benchmarking (for P/E and EV/EBITDA comps) uses a 3-tier fallback:
  1. Exact scraped "Industry" string, if enough EGX peers share it
  2. Broader macro-sector bucket (keyword-mapped from that Industry string)
  3. Financial vs Other binary split - always has enough peers, guaranteed fallback
"""

from statistics import median
from typing import Optional

import config
from scraper import CompanyFundamentals
from valuation import run_all_methods


def macro_sector(industry: Optional[str], is_financial_fallback: bool) -> str:
    """Maps a scraped Industry string to one of the broader SECTOR_KEYWORDS
    buckets. Falls back to Financials/Other (via the hand-curated ticker list)
    when there's no scraped industry to work with at all."""
    if industry:
        low = industry.lower()
        for name, keywords in config.SECTOR_KEYWORDS:
            if any(k in low for k in keywords):
                return name
    return "Financials" if is_financial_fallback else "Other"


def sector_benchmarks(all_cf: dict) -> dict:
    """Builds median P/E and EV/EBITDA at all 3 tiers, plus peer counts so
    score_ticker can decide which tier is trustworthy enough to use."""
    industry_pe, industry_ev = {}, {}
    macro_pe, macro_ev = {}, {}
    financial_pes, financial_ev = [], []
    other_pes, other_ev = [], []

    for t, cf in all_cf.items():
        is_fin = t in config.FINANCIAL_SECTOR_TICKERS
        macro = macro_sector(cf.sector, is_fin)

        pe = None
        if cf.forward_pe and cf.forward_pe > 0:
            pe = cf.forward_pe
        elif cf.eps and cf.price and cf.eps > 0:
            pe = cf.price / cf.eps
        ev_ebitda = None
        if cf.ebitda and cf.ebitda > 0 and cf.market_cap:
            net_debt = (cf.total_debt or 0) - (cf.cash or 0)
            ev_ebitda = (cf.market_cap + net_debt) / cf.ebitda

        if pe is not None:
            if cf.sector:
                industry_pe.setdefault(cf.sector, []).append(pe)
            macro_pe.setdefault(macro, []).append(pe)
            (financial_pes if is_fin else other_pes).append(pe)
        if ev_ebitda is not None:
            if cf.sector:
                industry_ev.setdefault(cf.sector, []).append(ev_ebitda)
            macro_ev.setdefault(macro, []).append(ev_ebitda)
            (financial_ev if is_fin else other_ev).append(ev_ebitda)

    return {
        "industry_pe": {k: median(v) for k, v in industry_pe.items()},
        "industry_pe_n": {k: len(v) for k, v in industry_pe.items()},
        "industry_ev": {k: median(v) for k, v in industry_ev.items()},
        "industry_ev_n": {k: len(v) for k, v in industry_ev.items()},
        "macro_pe": {k: median(v) for k, v in macro_pe.items()},
        "macro_pe_n": {k: len(v) for k, v in macro_pe.items()},
        "macro_ev": {k: median(v) for k, v in macro_ev.items()},
        "macro_ev_n": {k: len(v) for k, v in macro_ev.items()},
        "financial_pe": median(financial_pes) if financial_pes else None,
        "other_pe": median(other_pes) if other_pes else None,
        "financial_ev_ebitda": median(financial_ev) if financial_ev else None,
        "other_ev_ebitda": median(other_ev) if other_ev else None,
    }


def _pick_peer_benchmark(ticker: str, cf: CompanyFundamentals, benchmarks: dict, metric: str):
    """Returns (value, label) for either metric='pe' or metric='ev', walking
    tiers from tightest to broadest until one has enough peers:
      1. Exact industry peer median
      2. Macro-sector peer median
      3. (P/E only) fixed sector target multiple (config.SECTOR_TARGET_PE)
      4. Financial vs Other binary median - guaranteed final fallback
    """
    is_fin = ticker in config.FINANCIAL_SECTOR_TICKERS
    macro = macro_sector(cf.sector, is_fin)

    if cf.sector:
        n = benchmarks[f"industry_{metric}_n"].get(cf.sector, 0)
        if n >= config.MIN_PEER_GROUP_SIZE:
            return benchmarks[f"industry_{metric}"][cf.sector], f"{cf.sector} (n={n})"

    n = benchmarks[f"macro_{metric}_n"].get(macro, 0)
    if n >= config.MIN_PEER_GROUP_SIZE:
        return benchmarks[f"macro_{metric}"][macro], f"{macro} (n={n})"

    if metric == "pe" and macro in config.SECTOR_TARGET_PE:
        return config.SECTOR_TARGET_PE[macro], f"{macro} target multiple (insufficient EGX peers)"

    key = "financial" if is_fin else "other"
    field = "pe" if metric == "pe" else "ev_ebitda"
    val = benchmarks.get(f"{key}_{field}")
    return val, f"{'Financial' if is_fin else 'Other'} fallback"


def score_ticker(ticker: str, cf: CompanyFundamentals, benchmarks: dict) -> dict:
    is_fin = ticker in config.FINANCIAL_SECTOR_TICKERS
    sector_pe, pe_peer_label = _pick_peer_benchmark(ticker, cf, benchmarks, "pe")
    sector_ev_ebitda, ev_peer_label = _pick_peer_benchmark(ticker, cf, benchmarks, "ev")

    method_results = run_all_methods(cf, sector_pe, sector_ev_ebitda)
    # Tag which peer group actually backed each relative-valuation method,
    # so the report can show it rather than a mystery "sector median".
    if method_results["pe"]["fair_value"] is not None:
        method_results["pe"]["note"] += f" [peers: {pe_peer_label}]"
    if method_results["comps"]["fair_value"] is not None:
        method_results["comps"]["note"] += f" [peers: {ev_peer_label}]"

    upsides = {}
    for method, res in method_results.items():
        fv = res["fair_value"]
        if fv is not None and cf.price:
            raw_upside = (fv - cf.price) / cf.price
            # Winsorize per-method (DCF capped tighter than the others - see
            # config.METHOD_UPSIDE_CAPS) so one outlier can't dominate.
            cap = config.METHOD_UPSIDE_CAPS.get(method, 3.0)
            upsides[method] = max(-cap, min(cap, raw_upside))

    methods_used = len(upsides)

    # Graham is structurally unreliable for financials - down-weight rather than drop,
    # so it still contributes a little signal without dominating.
    weights = dict(config.METHOD_WEIGHTS)
    if is_fin and "graham" in upsides:
        weights["graham"] *= 0.3
    # DCF is the most assumption-heavy method (one flat discount rate, a
    # single growth-fade path) - when it's not corroborated by at least 2
    # other methods, trust it less rather than let it swing the composite
    # on its own.
    if "dcf" in upsides and methods_used < 3:
        weights["dcf"] *= 0.5

    available = {m: w for m, w in weights.items() if m in upsides}
    total_weight = sum(available.values())

    if total_weight == 0:
        composite = None
    else:
        composite = sum(upsides[m] * (w / total_weight) for m, w in available.items())

    return {
        "ticker": ticker,
        "price": cf.price,
        "sector": cf.sector,
        "macro_sector": macro_sector(cf.sector, is_fin),
        "is_financial": is_fin,
        "method_results": method_results,
        "upsides": upsides,
        "methods_used": methods_used,
        "composite_upside": composite,
        "low_confidence": methods_used < config.MIN_METHODS_FOR_RANK,
        "errors": cf.errors,
    }


def rank_universe(all_cf: dict) -> list:
    benchmarks = sector_benchmarks(all_cf)
    scored = [score_ticker(t, cf, benchmarks) for t, cf in all_cf.items()]
    # Sort priority: (1) has a composite score at all, (2) meets the minimum
    # methods-used bar for confidence, (3) highest upside first. This keeps
    # a 1-method score from outranking a well-covered name, without hiding
    # it from the report entirely.
    scored.sort(key=lambda x: (
        x["composite_upside"] is None,
        x["low_confidence"],
        -(x["composite_upside"] if x["composite_upside"] is not None else -999),
    ))
    return scored

