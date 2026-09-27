"""V2.6 EGX quantitative research engine.

V2.6 upgrades:
- controlled EGX100 sector taxonomy
- valuation-method applicability by business type
- separate Quality / Valuation / Confidence scores
- valuation coverage and data completeness
- explicit research-range scenarios
- red flags and research-status diagnostics
- stock-level CAPM with auditable fallback
"""
from statistics import median
from pathlib import Path
import json
import config
from scraper import CompanyFundamentals

def _safe_div(a,b):
    return a/b if a is not None and b not in (None,0) else None

def _sector_overrides():
    p=Path(config.SECTOR_OVERRIDE_FILE)
    if not p.exists(): return {}
    try:
        d=json.loads(p.read_text(encoding="utf-8"))
        return {k:v for k,v in d.items() if not k.startswith("_")}
    except Exception:
        return {}

_SECTOR_OVERRIDES=_sector_overrides()

def macro_sector(cf,ticker):
    if ticker in _SECTOR_OVERRIDES:
        return _SECTOR_OVERRIDES[ticker]
    industry=(cf.sector or "").lower()
    for name,keywords in config.SECTOR_KEYWORDS:
        if any(k in industry for k in keywords):
            return name
    return "Unclassified"

def metrics(cf):
    revenue,ni,eq,ebitda,fcf=cf.revenue,cf.net_income,cf.total_equity,cf.ebitda,cf.free_cash_flow
    debt,cash=cf.total_debt,cf.cash
    pe=_safe_div(cf.price,cf.eps) if cf.eps and cf.eps>0 else None
    pb=_safe_div(cf.price,cf.book_value_per_share) if cf.book_value_per_share and cf.book_value_per_share>0 else None
    roe=_safe_div(ni,eq)
    net_margin=_safe_div(ni,revenue)
    ebitda_margin=_safe_div(ebitda,revenue)
    fcf_margin=_safe_div(fcf,revenue)
    debt_equity=_safe_div(debt,eq)
    net_debt=(debt or 0)-(cash or 0)
    net_debt_ebitda=_safe_div(net_debt,ebitda) if ebitda and ebitda>0 else None
    fcf_conversion=_safe_div(fcf,ni) if ni and ni>0 else None
    eps_growth=None
    h=cf.eps_history
    if len(h)>=2 and h[0] and h[-1] and h[0]>0 and h[-1]>0:
        eps_growth=(h[-1]/h[0])**(1/(len(h)-1))-1
    revenue_growth=None
    h=getattr(cf,"revenue_history",[])
    if len(h)>=2 and h[0] and h[-1] and h[0]>0 and h[-1]>0:
        revenue_growth=(h[-1]/h[0])**(1/(len(h)-1))-1
    return {
        "pe":pe,"pb":pb,"roe":roe,"roa":None,"net_margin":net_margin,
        "ebitda_margin":ebitda_margin,"fcf_margin":fcf_margin,"debt_equity":debt_equity,
        "net_debt_ebitda":net_debt_ebitda,"fcf_conversion":fcf_conversion,
        "eps_growth":eps_growth,"revenue_growth":revenue_growth,
        "beta":getattr(cf,"beta",None)
    }

def build_peer_stats(all_cf):
    groups={}
    for ticker,cf in all_cf.items():
        groups.setdefault(macro_sector(cf,ticker),[]).append((ticker,cf))
    stats={}
    for sector,items in groups.items():
        pe,pb,ev=[],[],[]
        for ticker,cf in items:
            m=metrics(cf)
            if m["pe"] is not None and 0<m["pe"]<60: pe.append(m["pe"])
            if m["pb"] is not None and 0<m["pb"]<10: pb.append(m["pb"])
            if cf.ebitda and cf.ebitda>0 and cf.market_cap:
                x=(cf.market_cap+(cf.total_debt or 0)-(cf.cash or 0))/cf.ebitda
                if 0<x<40: ev.append(x)
        stats[sector]={
            "n":len(items),
            "pe":median(pe) if len(pe)>=config.MIN_PEER_GROUP_SIZE else config.SECTOR_TARGET_PE.get(sector),
            "pb":median(pb) if len(pb)>=config.MIN_PEER_GROUP_SIZE else None,
            "ev_ebitda":median(ev) if len(ev)>=config.MIN_PEER_GROUP_SIZE else None,
            "pe_n":len(pe),"pb_n":len(pb),"ev_n":len(ev)
        }
    return stats

def _pe_fv(cf,peer):
    return cf.eps*peer if cf.eps and cf.eps>0 and peer and peer>0 else None

def _pb_fv(cf,peer):
    return cf.book_value_per_share*peer if cf.book_value_per_share and cf.book_value_per_share>0 and peer and peer>0 else None

def _cost_of_equity(cf):
    beta=getattr(cf,"beta",None)
    if config.CAPM_ENABLED and beta is not None and beta>0:
        raw=config.EGYPT_RISK_FREE_RATE+beta*config.EGYPT_EQUITY_RISK_PREMIUM
        return max(config.MIN_COST_OF_EQUITY,min(config.MAX_COST_OF_EQUITY,raw)),"CAPM"
    return config.DEFAULT_COST_OF_EQUITY,"Fallback"

def _dcf(cf,sector):
    if sector in ("Financials","Unclassified") or not cf.free_cash_flow or cf.free_cash_flow<=0 or not cf.shares_outstanding:
        return None
    hist=[x for x in cf.fcf_history if x is not None]
    if hist and sum(x>0 for x in hist)<len(hist)/2: return None
    if len(hist)>=2 and hist[0]>0 and hist[-1]>0:
        g0=max(-0.05,min(0.30,(hist[-1]/hist[0])**(1/(len(hist)-1))-1))
    else: g0=0.10
    r,_=_cost_of_equity(cf)
    gt=config.DEFAULT_TERMINAL_GROWTH
    if r<=gt: return None
    fcf=cf.free_cash_flow
    pv=0
    for y in range(1,6):
        g=g0+(gt-g0)*(y/5) if config.FCF_HIGH_GROWTH_FADE else g0
        fcf*=1+g
        pv+=fcf/((1+r)**y)
    terminal=fcf*(1+gt)/(r-gt)
    return (pv+terminal/((1+r)**5))/cf.shares_outstanding

def _comps_fv(cf,peer):
    if not peer or not cf.ebitda or cf.ebitda<=0 or not cf.shares_outstanding: return None
    eq=cf.ebitda*peer-(cf.total_debt or 0)+(cf.cash or 0)
    return eq/cf.shares_outstanding if eq>0 else None

def valuation(cf,sector,peers):
    vals={"pe":None,"pb":None,"dcf":None,"comps":None}
    if sector=="Financials":
        vals["pe"]=_pe_fv(cf,peers.get("pe"))
        vals["pb"]=_pb_fv(cf,peers.get("pb"))
    elif sector=="Real Estate":
        vals["pe"]=_pe_fv(cf,peers.get("pe"))
        vals["pb"]=_pb_fv(cf,peers.get("pb"))
        vals["dcf"]=_dcf(cf,sector)
        vals["comps"]=_comps_fv(cf,peers.get("ev_ebitda"))
    else:
        vals["pe"]=_pe_fv(cf,peers.get("pe"))
        vals["dcf"]=_dcf(cf,sector)
        vals["comps"]=_comps_fv(cf,peers.get("ev_ebitda"))
    return vals

def _applicable_methods(sector,cf):
    if sector=="Financials": return ["pe","pb"]
    if sector=="Real Estate": return ["pe","pb","dcf","comps"]
    methods=["pe","dcf","comps"]
    if not cf.eps or cf.eps<=0: methods.remove("pe")
    if not cf.free_cash_flow or cf.free_cash_flow<=0: 
        if "dcf" in methods: methods.remove("dcf")
    if not cf.ebitda or cf.ebitda<=0:
        if "comps" in methods: methods.remove("comps")
    return methods

def quality_score(m,cf):
    components=[]
    if m["roe"] is not None: components.append(max(0,min(100,50+m["roe"]*100)))
    if m["net_margin"] is not None: components.append(max(0,min(100,50+m["net_margin"]*200)))
    if m["fcf_conversion"] is not None: components.append(max(0,min(100,50+m["fcf_conversion"]*50)))
    if m["debt_equity"] is not None: components.append(max(0,min(100,100-m["debt_equity"]*50)))
    if m["eps_growth"] is not None: components.append(max(0,min(100,50+m["eps_growth"]*100)))
    return round(sum(components)/len(components),1) if components else None

def _red_flags(cf,m,sector,valid,dispersion,coverage):
    flags=[]
    if sector=="Unclassified": flags.append("Sector classification unresolved")
    if coverage<0.50: flags.append("Low valuation-method coverage")
    if len(valid)<2: flags.append("Only one usable valuation method")
    if dispersion is not None and dispersion>0.75: flags.append("Extreme valuation disagreement")
    elif dispersion is not None and dispersion>0.50: flags.append("High valuation disagreement")
    if cf.eps is None: flags.append("Missing EPS")
    if cf.book_value_per_share is None: flags.append("Missing BVPS")
    if cf.free_cash_flow is not None and cf.free_cash_flow<0: flags.append("Negative free cash flow")
    if m["debt_equity"] is not None and m["debt_equity"]>2: flags.append("High debt/equity")
    if m["eps_growth"] is not None and m["eps_growth"]<-0.10: flags.append("Negative EPS CAGR")
    if getattr(cf,"beta",None) is None and sector!="Financials": flags.append("CAPM beta unavailable")
    return flags

def score_one(ticker,cf,peer_stats):
    sector=macro_sector(cf,ticker)
    peers=peer_stats.get(sector,{})
    m=metrics(cf)
    vals=valuation(cf,sector,peers)
    applicable=_applicable_methods(sector,cf)
    valid=[vals[k] for k in applicable if vals.get(k) is not None and vals[k]>0]
    current=cf.price
    if valid:
        base=median(valid)
        dispersion=(max(valid)-min(valid))/base if len(valid)>=2 and base else None
        # Scenario range is an uncertainty range around the base valuation,
        # not a ranking of different valuation methods.
        uncertainty=max(0.10,min(0.30,0.10+(dispersion or 0)*0.25))
        bear=base*(1-uncertainty)
        bull=base*(1+uncertainty)
    else:
        base=bear=bull=dispersion=None
    valuation_upside=(base-current)/current if base and current else None
    valuation_score=None if valuation_upside is None else max(0,min(100,50+valuation_upside*50))
    quality=quality_score(m,cf)
    core_fields=[cf.price,cf.eps,cf.book_value_per_share,cf.revenue,cf.net_income,cf.ebitda,cf.total_equity,cf.total_debt,cf.cash,cf.free_cash_flow]
    data_completeness=round(sum(x is not None for x in core_fields)/len(core_fields)*100)
    coverage=len(valid)/len(applicable) if applicable else 0
    dispersion_penalty=0 if dispersion is None else min(35,dispersion*40)
    confidence=max(0,min(100,
        data_completeness*0.40+
        coverage*100*0.25+
        (quality or 50)*0.15+
        (100-dispersion_penalty)*0.15+
        (100 if sector!="Unclassified" else 30)*0.05
    ))
    if confidence>=75 and coverage>=0.75 and (dispersion is None or dispersion<=0.50): label="High"
    elif confidence>=55 and coverage>=0.50: label="Medium"
    else: label="Low"
    w=config.OPPORTUNITY_WEIGHTS
    opportunity=None
    if valuation_score is not None:
        opportunity=round(valuation_score*w["valuation"]+(quality or 50)*w["quality"]+confidence*w["confidence"],1)
    flags=_red_flags(cf,m,sector,valid,dispersion,coverage)
    discount_rate,discount_rate_source=_cost_of_equity(cf)
    return {
        "ticker":ticker,"price":current,"sector":sector,"company_name":getattr(cf,"company_name",None),
        "metrics":m,"peer":peers,"valuations":vals,"upsides":{},
        "applicable_methods":applicable,"fair_value_bear":bear,"fair_value_base":base,"fair_value_bull":bull,
        "dispersion":dispersion,"quality_score":quality,"valuation_score":valuation_score,
        "confidence_score":round(confidence,1),"confidence":label,"opportunity_score":opportunity,
        "data_completeness":data_completeness,"valuation_coverage":coverage,
        "methods_used":len(valid),"errors":cf.errors,"red_flags":flags,
        "research_status":"Review Required" if flags else "Quantitative Pass",
        "discount_rate":discount_rate,"discount_rate_source":discount_rate_source
    }

def rank_v2(all_cf):
    peers=build_peer_stats(all_cf)
    rows=[score_one(t,cf,peers) for t,cf in all_cf.items()]
    rows.sort(key=lambda x:(x["opportunity_score"] is None,-(x["opportunity_score"] or -999)))
    for i,r in enumerate(rows,1): r["rank"]=i
    return rows
