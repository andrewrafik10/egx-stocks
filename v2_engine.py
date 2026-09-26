"""V2 research engine for the EGX100 weekly report.

V2 principles:
- sector-aware method eligibility
- quality metrics from available fundamentals
- valuation dispersion penalty
- fair-value bear/base/bull range
- data-completeness and confidence scoring
- transparent opportunity score

This is a screening/research model, not investment advice.
"""

from statistics import median
from math import sqrt
from typing import Optional
from pathlib import Path
import json
import config
from scraper import CompanyFundamentals


def _safe_div(a, b):
    return a / b if a is not None and b not in (None, 0) else None


def _sector_overrides():
    path = Path(config.SECTOR_OVERRIDE_FILE)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception:
        return {}


_SECTOR_OVERRIDES = _sector_overrides()


def macro_sector(cf: CompanyFundamentals, ticker: str) -> str:
    if ticker in _SECTOR_OVERRIDES:
        return _SECTOR_OVERRIDES[ticker]
    industry = (cf.sector or "").lower()
    for name, keywords in config.SECTOR_KEYWORDS:
        if any(k in industry for k in keywords):
            return name
    return "Financials" if ticker in config.FINANCIAL_SECTOR_TICKERS else "Unclassified"


def metrics(cf: CompanyFundamentals):
    revenue = cf.revenue
    ni = cf.net_income
    eq = cf.total_equity
    ebitda = cf.ebitda
    fcf = cf.free_cash_flow
    debt = cf.total_debt
    cash = cf.cash

    pe = _safe_div(cf.price, cf.eps) if cf.eps and cf.eps > 0 else None
    beta = getattr(cf, "beta", None)
    pb = _safe_div(cf.price, cf.book_value_per_share) if cf.book_value_per_share and cf.book_value_per_share > 0 else None
    roe = _safe_div(ni, eq)
    roa = None
    if cf.market_cap and cf.shares_outstanding and eq:
        # Approximate asset base unavailable in current scraper; leave ROA blank.
        roa = None
    net_margin = _safe_div(ni, revenue)
    ebitda_margin = _safe_div(ebitda, revenue)
    fcf_margin = _safe_div(fcf, revenue)
    debt_equity = _safe_div(debt, eq)
    net_debt = (debt or 0) - (cash or 0)
    net_debt_ebitda = _safe_div(net_debt, ebitda) if ebitda and ebitda > 0 else None
    fcf_conversion = _safe_div(fcf, ni) if ni and ni > 0 else None

    eps_growth = None
    if len(cf.eps_history) >= 2 and cf.eps_history[0] and cf.eps_history[-1] and cf.eps_history[0] > 0 and cf.eps_history[-1] > 0:
        years = len(cf.eps_history) - 1
        eps_growth = (cf.eps_history[-1] / cf.eps_history[0]) ** (1 / years) - 1

    revenue_growth = None
    if len(getattr(cf, "revenue_history", [])) >= 2:
        h = cf.revenue_history
        if h[0] and h[-1] and h[0] > 0 and h[-1] > 0:
            revenue_growth = (h[-1] / h[0]) ** (1 / (len(h)-1)) - 1

    return {
        "pe": pe, "pb": pb, "roe": roe, "roa": roa,
        "net_margin": net_margin, "ebitda_margin": ebitda_margin,
        "fcf_margin": fcf_margin, "debt_equity": debt_equity,
        "net_debt_ebitda": net_debt_ebitda, "fcf_conversion": fcf_conversion,
        "eps_growth": eps_growth, "revenue_growth": revenue_growth, "beta": beta,
    }


def build_peer_stats(all_cf):
    groups = {}
    for ticker, cf in all_cf.items():
        sector = macro_sector(cf, ticker)
        groups.setdefault(sector, []).append((ticker, cf))

    stats = {}
    for sector, items in groups.items():
        pe = []
        pb = []
        ev = []
        for ticker, cf in items:
            m = metrics(cf)
            if m["pe"] is not None and 0 < m["pe"] < 60:
                pe.append(m["pe"])
            if m["pb"] is not None and 0 < m["pb"] < 10:
                pb.append(m["pb"])
            if cf.ebitda and cf.ebitda > 0 and cf.market_cap:
                net_debt = (cf.total_debt or 0) - (cf.cash or 0)
                x = (cf.market_cap + net_debt) / cf.ebitda
                if 0 < x < 40:
                    ev.append(x)
        stats[sector] = {
            "n": len(items),
            "pe": median(pe) if len(pe) >= config.MIN_PEER_GROUP_SIZE else None,
            "pb": median(pb) if len(pb) >= config.MIN_PEER_GROUP_SIZE else None,
            "ev_ebitda": median(ev) if len(ev) >= config.MIN_PEER_GROUP_SIZE else None,
            "pe_n": len(pe), "pb_n": len(pb), "ev_n": len(ev),
        }
    return stats


def _pe_fv(cf, peer):
    if cf.eps and cf.eps > 0 and peer and peer > 0:
        return cf.eps * peer
    return None


def _pb_fv(cf, peer):
    if cf.book_value_per_share and cf.book_value_per_share > 0 and peer and peer > 0:
        return cf.book_value_per_share * peer
    return None


def _cost_of_equity(cf):
    beta = getattr(cf, "beta", None)
    if config.CAPM_ENABLED and beta is not None and beta > 0:
        raw = config.EGYPT_RISK_FREE_RATE + beta * config.EGYPT_EQUITY_RISK_PREMIUM
        return max(config.MIN_COST_OF_EQUITY, min(config.MAX_COST_OF_EQUITY, raw)), "CAPM"
    return config.DEFAULT_COST_OF_EQUITY, "Fallback"


def _dcf(cf, sector):
    if sector in ("Financials", "Unclassified"):
        return None
    if not cf.free_cash_flow or cf.free_cash_flow <= 0 or not cf.shares_outstanding:
        return None
    hist = [x for x in cf.fcf_history if x is not None]
    positive = sum(x > 0 for x in hist)
    if hist and positive < len(hist) / 2:
        return None
    if len(hist) >= 2 and hist[0] > 0 and hist[-1] > 0:
        g0 = max(-0.05, min(0.30, (hist[-1] / hist[0]) ** (1 / (len(hist)-1)) - 1))
    else:
        g0 = 0.10
    r, _ = _cost_of_equity(cf)
    gt = config.DEFAULT_TERMINAL_GROWTH
    if r <= gt:
        return None
    fcf = cf.free_cash_flow
    pv = 0
    for y in range(1, 6):
        g = g0 + (gt-g0)*(y/5) if config.FCF_HIGH_GROWTH_FADE else g0
        fcf *= 1+g
        pv += fcf / ((1+r)**y)
    terminal = fcf*(1+gt)/(r-gt)
    return (pv + terminal/((1+r)**5))/cf.shares_outstanding


def _comps_fv(cf, peer):
    if not peer or not cf.ebitda or cf.ebitda <= 0 or not cf.shares_outstanding:
        return None
    net_debt = (cf.total_debt or 0) - (cf.cash or 0)
    eq = cf.ebitda * peer - net_debt
    return eq/cf.shares_outstanding if eq > 0 else None


def valuation(cf, ticker, sector, peers):
    m = metrics(cf)
    results = {}
    results["pe"] = _pe_fv(cf, peers.get("pe"))
    if sector == "Financials":
        results["pb"] = _pb_fv(cf, peers.get("pb"))
        results["ddm"] = None
        results["dcf"] = None
        results["comps"] = None
    elif sector == "Real Estate":
        results["pb"] = _pb_fv(cf, peers.get("pb"))
        results["dcf"] = _dcf(cf, sector)
        results["comps"] = _comps_fv(cf, peers.get("ev_ebitda"))
    else:
        results["pb"] = None
        results["dcf"] = _dcf(cf, sector)
        results["comps"] = _comps_fv(cf, peers.get("ev_ebitda"))
    return results


def quality_score(m, cf):
    components = []
    if m["roe"] is not None:
        components.append(min(100, max(0, 50 + m["roe"]*100)))
    if m["net_margin"] is not None:
        components.append(min(100, max(0, 50 + m["net_margin"]*200)))
    if m["fcf_conversion"] is not None:
        components.append(min(100, max(0, 50 + m["fcf_conversion"]*50)))
    if m["debt_equity"] is not None:
        components.append(max(0, min(100, 100 - m["debt_equity"]*50)))
    if m["eps_growth"] is not None:
        components.append(max(0, min(100, 50 + m["eps_growth"]*100)))
    if not components:
        return None
    return round(sum(components)/len(components), 1)


def score_one(ticker, cf, peer_stats):
    sector = macro_sector(cf, ticker)
    peers = peer_stats.get(sector, {})
    m = metrics(cf)
    vals = valuation(cf, ticker, sector, peers)
    valid = [v for v in vals.values() if v is not None and v > 0]
    current = cf.price

    upsides = {}
    for k, v in vals.items():
        if v is not None and current:
            cap = 1.5 if k == "dcf" else 3.0
            upsides[k] = max(-cap, min(cap, (v-current)/current))

    if len(valid) >= 2:
        ordered = sorted(valid)
        base = median(ordered)
        bear = ordered[0]
        bull = ordered[-1]
        if len(ordered) >= 3:
            # robust range: lower quartile / median / upper quartile
            bear = ordered[max(0, int((len(ordered)-1)*0.25))]
            bull = ordered[min(len(ordered)-1, int((len(ordered)-1)*0.75))]
    elif len(valid) == 1:
        base = valid[0]
        bear = valid[0] * 0.85
        bull = valid[0] * 1.15
    else:
        base = bear = bull = None

    dispersion = None
    if len(valid) >= 2 and base:
        dispersion = (max(valid)-min(valid))/base

    quality = quality_score(m, cf)
    completeness_fields = [cf.price, cf.eps, cf.book_value_per_share, cf.revenue, cf.net_income, cf.ebitda, cf.total_equity, cf.total_debt, cf.cash, cf.free_cash_flow]
    completeness = round(sum(x is not None for x in completeness_fields)/len(completeness_fields)*100)

    dispersion_penalty = max(0, min(30, (dispersion or 0)*30))
    valuation_upside = (base-current)/current if base and current else None
    discount_rate, discount_rate_source = _cost_of_equity(cf)
    valuation_score = None if valuation_upside is None else max(0, min(100, 50 + valuation_upside*50))
    confidence = max(0, min(100, completeness*0.55 + (quality or 50)*0.20 + (100-dispersion_penalty)*0.25))

    opportunity = None
    if valuation_score is not None:
        w = config.OPPORTUNITY_WEIGHTS
        opportunity = round(valuation_score*w["valuation"] + (quality or 50)*w["quality"] + confidence*w["confidence"], 1)

    if confidence >= 75 and (dispersion is None or dispersion <= 0.60):
        conf_label = "High"
    elif confidence >= 55:
        conf_label = "Medium"
    else:
        conf_label = "Low"

    return {
        "ticker": ticker, "price": current, "sector": sector, "company_name": cf.company_name,
        "metrics": m, "peer": peers, "valuations": vals, "upsides": upsides,
        "fair_value_bear": bear, "fair_value_base": base, "fair_value_bull": bull,
        "dispersion": dispersion, "quality_score": quality,
        "data_completeness": completeness, "valuation_score": valuation_score,
        "confidence_score": round(confidence,1), "confidence": conf_label,
        "opportunity_score": opportunity, "methods_used": len(valid), "errors": cf.errors,
        "discount_rate": discount_rate, "discount_rate_source": discount_rate_source,
    }


def rank_v2(all_cf):
    peers = build_peer_stats(all_cf)
    rows = [score_one(t, cf, peers) for t, cf in all_cf.items()]
    rows.sort(key=lambda x: (x["opportunity_score"] is None, -(x["opportunity_score"] or -999)))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows
