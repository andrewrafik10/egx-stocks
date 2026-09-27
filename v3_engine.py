"""EGX V3 sector-aware valuation and research engine.

V3 adds economically appropriate valuation frameworks:
- Banks/financials: Residual Income + P/B + P/E + DDM when inputs exist.
- Real estate: P/E + P/B + DCF + EV/EBITDA + Book NAV proxy.
- Holding companies: SOTP when manually configured; otherwise transparent fallback.
- Other corporates: P/E + DCF + EV/EBITDA.
No method is forced when its inputs are unavailable.
"""
from statistics import median
from pathlib import Path
import json
import config
from v2_engine import macro_sector, metrics, build_peer_stats, _cost_of_equity, _safe_div

def v3_sector(cf,ticker):
    s=macro_sector(cf,ticker)
    if ticker in getattr(config,"HOLDING_COMPANY_TICKERS",set()):
        return "Holding Companies"
    return s

def _peer_stats_v3(all_cf):
    base=build_peer_stats(all_cf)
    return base

def _residual_income(cf, sector):
    if not cf.book_value_per_share or cf.book_value_per_share<=0 or not cf.eps or cf.eps<=0:
        return None
    r,_=_cost_of_equity(cf)
    roe=_safe_div(cf.net_income,cf.total_equity)
    if roe is None or r<=0: return None
    g_terminal=min(config.V3_TERMINAL_GROWTH, max(0.0, roe*0.6))
    payout=getattr(cf,"dividend_payout_ratio",None)
    retention=1-(payout if payout is not None and 0<=payout<=1 else config.V3_DEFAULT_RETENTION)
    retention=max(0.0,min(0.9,retention))
    bv=cf.book_value_per_share
    value=bv
    for y in range(1,config.V3_EXPLICIT_YEARS+1):
        roe_y=roe+(r-roe)*(y/config.V3_EXPLICIT_YEARS)
        eps_y=bv*roe_y
        ri=eps_y-r*bv
        value += ri/((1+r)**y)
        bv *= 1 + roe_y*retention
    terminal_ri=bv*(r + (g_terminal-r)*0.5) - r*bv
    value += terminal_ri/(r-g_terminal)/((1+r)**config.V3_EXPLICIT_YEARS)
    return value if value>0 else None

def _ddm(cf):
    dps=getattr(cf,"dividend_per_share",None)
    if not dps or dps<=0: return None
    r,_=_cost_of_equity(cf)
    g=min(config.V3_DDM_GROWTH, r-0.02)
    if r<=g: return None
    return dps*(1+g)/(r-g)

def _book_nav_proxy(cf):
    if cf.book_value_per_share and cf.book_value_per_share>0:
        return cf.book_value_per_share
    if cf.total_equity and cf.shares_outstanding and cf.total_equity>0:
        return cf.total_equity/cf.shares_outstanding
    return None

def _sotp(cf,ticker):
    registry=getattr(config,"SOTP_COMPONENTS",{})
    comps=registry.get(ticker)
    if not comps: return None
    total=sum(float(x.get("value_per_share",0)) for x in comps if x.get("value_per_share") is not None)
    if total<=0: return None
    return total

def _dcf(cf,sector):
    if sector in ("Financials","Holding Companies","Unclassified") or not cf.free_cash_flow or cf.free_cash_flow<=0 or not cf.shares_outstanding:
        return None
    hist=[x for x in cf.fcf_history if x is not None]
    if hist and sum(x>0 for x in hist)<len(hist)/2: return None
    if len(hist)>=2 and hist[0]>0 and hist[-1]>0:
        g0=max(-0.05,min(0.25,(hist[-1]/hist[0])**(1/(len(hist)-1))-1))
    else: g0=0.08
    r,_=_cost_of_equity(cf); gt=config.V3_TERMINAL_GROWTH
    if r<=gt: return None
    fcf=cf.free_cash_flow; pv=0
    for y in range(1,config.V3_EXPLICIT_YEARS+1):
        g=g0+(gt-g0)*(y/config.V3_EXPLICIT_YEARS)
        fcf*=1+g; pv+=fcf/((1+r)**y)
    terminal=fcf*(1+gt)/(r-gt)
    return (pv+terminal/((1+r)**config.V3_EXPLICIT_YEARS))/cf.shares_outstanding

def _fv_pe(cf,peer):
    return cf.eps*peer if cf.eps and cf.eps>0 and peer and peer>0 else None

def _fv_pb(cf,peer):
    return cf.book_value_per_share*peer if cf.book_value_per_share and cf.book_value_per_share>0 and peer and peer>0 else None

def _fv_ev_ebitda(cf,peer):
    if not peer or not cf.ebitda or cf.ebitda<=0 or not cf.shares_outstanding: return None
    eq=cf.ebitda*peer-(cf.total_debt or 0)+(cf.cash or 0)
    return eq/cf.shares_outstanding if eq>0 else None

def valuation_v3(cf,ticker,sector,peers):
    vals={}
    if sector=="Financials":
        vals["pe"]=_fv_pe(cf,peers.get("pe"))
        vals["pb"]=_fv_pb(cf,peers.get("pb"))
        vals["residual_income"]=_residual_income(cf,sector)
        vals["ddm"]=_ddm(cf)
    elif sector=="Real Estate":
        vals["pe"]=_fv_pe(cf,peers.get("pe"))
        vals["pb"]=_fv_pb(cf,peers.get("pb"))
        vals["dcf"]=_dcf(cf,sector)
        vals["ev_ebitda"]=_fv_ev_ebitda(cf,peers.get("ev_ebitda"))
        vals["book_nav_proxy"]=_book_nav_proxy(cf)
    elif sector=="Holding Companies":
        vals["sotp"]=_sotp(cf,ticker)
        vals["pe"]=_fv_pe(cf,peers.get("pe"))
        vals["pb"]=_fv_pb(cf,peers.get("pb"))
    else:
        vals["pe"]=_fv_pe(cf,peers.get("pe"))
        vals["dcf"]=_dcf(cf,sector)
        vals["ev_ebitda"]=_fv_ev_ebitda(cf,peers.get("ev_ebitda"))
    return vals

def applicable_v3(cf,ticker,sector):
    if sector=="Financials":
        return ["pe","pb","residual_income","ddm"]
    if sector=="Real Estate":
        return ["pe","pb","dcf","ev_ebitda","book_nav_proxy"]
    if sector=="Holding Companies":
        return ["sotp","pe","pb"]
    return ["pe","dcf","ev_ebitda"]

def score_one_v3(ticker,cf,peer_stats):
    sector=v3_sector(cf,ticker); peers=peer_stats.get(macro_sector(cf,ticker),{})
    m=metrics(cf); vals=valuation_v3(cf,ticker,sector,peers)
    applicable=applicable_v3(cf,ticker,sector)
    valid=[vals[k] for k in applicable if vals.get(k) is not None and vals[k]>0]
    base=median(valid) if valid else None
    dispersion=(max(valid)-min(valid))/base if len(valid)>=2 and base else None
    uncertainty=max(0.08,min(0.28,0.08+(dispersion or 0)*0.22)) if base else None
    bear=base*(1-uncertainty) if base else None; bull=base*(1+uncertainty) if base else None
    upside=(base-cf.price)/cf.price if base and cf.price else None
    valuation_score=max(0,min(100,50+upside*50)) if upside is not None else None
    quality=__import__("v2_engine").quality_score(m,cf)
    core=[cf.price,cf.eps,cf.book_value_per_share,cf.revenue,cf.net_income,cf.ebitda,cf.total_equity,cf.total_debt,cf.cash,cf.free_cash_flow]
    completeness=round(sum(x is not None for x in core)/len(core)*100)
    coverage=len(valid)/len(applicable) if applicable else 0
    method_agreement=100-min(40,(dispersion or 0)*40)
    sector_conf=100 if sector!="Unclassified" else 30
    confidence=max(0,min(100,completeness*.35+coverage*100*.25+(quality or 50)*.15+method_agreement*.20+sector_conf*.05))
    label="High" if confidence>=75 and coverage>=.75 and (dispersion is None or dispersion<=.50) else ("Medium" if confidence>=55 and coverage>=.50 else "Low")
    w=config.OPPORTUNITY_WEIGHTS
    opportunity=round(valuation_score*w["valuation"]+(quality or 50)*w["quality"]+confidence*w["confidence"],1) if valuation_score is not None else None
    flags=[]
    if sector=="Unclassified": flags.append("Sector classification unresolved")
    if coverage<0.50: flags.append("Low valuation-method coverage")
    if len(valid)<2: flags.append("Only one usable valuation method")
    if dispersion is not None and dispersion>0.75: flags.append("Extreme valuation disagreement")
    elif dispersion is not None and dispersion>0.50: flags.append("High valuation disagreement")
    if sector=="Financials" and vals.get("residual_income") is None: flags.append("Residual Income unavailable")
    if sector=="Financials" and vals.get("ddm") is None: flags.append("DDM unavailable")
    if sector=="Holding Companies" and vals.get("sotp") is None: flags.append("SOTP unavailable — component data required")
    if sector=="Real Estate" and vals.get("book_nav_proxy") is not None: flags.append("Book NAV proxy used; not property-level NAV")
    if cf.eps is None: flags.append("Missing EPS")
    if cf.book_value_per_share is None: flags.append("Missing BVPS")
    if cf.free_cash_flow is not None and cf.free_cash_flow<0: flags.append("Negative free cash flow")
    return {
      "version":"V3","ticker":ticker,"company_name":cf.company_name,"price":cf.price,"sector":sector,
      "metrics":m,"peer":peers,"valuations":vals,"applicable_methods":applicable,"methods_used":len(valid),
      "fair_value_bear":bear,"fair_value_base":base,"fair_value_bull":bull,"dispersion":dispersion,
      "valuation_score":valuation_score,"quality_score":quality,"confidence_score":round(confidence,1),
      "confidence":label,"opportunity_score":opportunity,"data_completeness":completeness,
      "valuation_coverage":coverage,"red_flags":flags,
      "research_status":"Review Required" if flags else "Quantitative Pass",
      "discount_rate":_cost_of_equity(cf)[0],"discount_rate_source":_cost_of_equity(cf)[1]
    }

def rank_v3(all_cf):
    peers=_peer_stats_v3(all_cf)
    rows=[score_one_v3(t,cf,peers) for t,cf in all_cf.items()]
    rows.sort(key=lambda r:(r["opportunity_score"] is None,-(r["opportunity_score"] or -999)))
    for i,r in enumerate(rows,1): r["rank"]=i
    return rows
