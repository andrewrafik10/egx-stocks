"""
Combines the 4 valuation methods into a per-stock composite "upside score" and
ranks the universe. Handles missing/inapplicable methods gracefully by
re-normalizing weights across whatever methods actually produced a value.
"""

from statistics import median
from typing import Optional

import config
from scraper import CompanyFundamentals
from valuation import run_all_methods


def sector_benchmarks(all_cf: dict) -> dict:
    """Rough single-bucket peer benchmarks for now: banks/financials vs everyone else.
    TODO: refine into proper GICS-like sector buckets once you're tracking sector
    tags per ticker (e.g. reuse the sector classification from your relative
    valuation screen in financial-modeling-portfolio)."""
    financial_pes, financial_ev_ebitda = [], []
    other_pes, other_ev_ebitda = [], []

    for t, cf in all_cf.items():
        is_fin = t in config.FINANCIAL_SECTOR_TICKERS
        if cf.eps and cf.price and cf.eps > 0:
            pe = cf.price / cf.eps
            (financial_pes if is_fin else other_pes).append(pe)
        if cf.ebitda and cf.ebitda > 0 and cf.market_cap:
            net_debt = (cf.total_debt or 0) - (cf.cash or 0)
            ev = cf.market_cap + net_debt
            (financial_ev_ebitda if is_fin else other_ev_ebitda).append(ev / cf.ebitda)

    return {
        "financial_pe": median(financial_pes) if financial_pes else None,
        "other_pe": median(other_pes) if other_pes else None,
        "financial_ev_ebitda": median(financial_ev_ebitda) if financial_ev_ebitda else None,
        "other_ev_ebitda": median(other_ev_ebitda) if other_ev_ebitda else None,
    }


def score_ticker(ticker: str, cf: CompanyFundamentals, benchmarks: dict) -> dict:
    is_fin = ticker in config.FINANCIAL_SECTOR_TICKERS
    sector_pe = benchmarks["financial_pe"] if is_fin else benchmarks["other_pe"]
    sector_ev_ebitda = benchmarks["financial_ev_ebitda"] if is_fin else benchmarks["other_ev_ebitda"]

    method_results = run_all_methods(cf, sector_pe, sector_ev_ebitda)

    upsides = {}
    for method, res in method_results.items():
        fv = res["fair_value"]
        if fv is not None and cf.price:
            upsides[method] = (fv - cf.price) / cf.price

    # Graham is structurally unreliable for financials - down-weight rather than drop,
    # so it still contributes a little signal without dominating.
    weights = dict(config.METHOD_WEIGHTS)
    if is_fin and "graham" in upsides:
        weights["graham"] *= 0.3

    available = {m: w for m, w in weights.items() if m in upsides}
    total_weight = sum(available.values())

    if total_weight == 0:
        composite = None
    else:
        composite = sum(upsides[m] * (w / total_weight) for m, w in available.items())

    return {
        "ticker": ticker,
        "price": cf.price,
        "is_financial": is_fin,
        "method_results": method_results,
        "upsides": upsides,
        "methods_used": len(upsides),
        "composite_upside": composite,
        "errors": cf.errors,
    }


def rank_universe(all_cf: dict) -> list:
    benchmarks = sector_benchmarks(all_cf)
    scored = [score_ticker(t, cf, benchmarks) for t, cf in all_cf.items()]
    # push stocks with no usable methods to the bottom rather than dropping them,
    # so the report can still flag "insufficient data" names
    scored.sort(key=lambda x: (x["composite_upside"] is None, -(x["composite_upside"] or -999)))
    return scored
