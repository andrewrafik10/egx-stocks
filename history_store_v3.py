"""V3 historical signal store. Keeps the internal CSV only."""
from pathlib import Path
from datetime import date
import csv

FIELDS=["as_of_date","version","ticker","company_name","sector","price","fair_value_bear","fair_value_base","fair_value_bull","base_upside","dispersion","valuation_score","quality_score","confidence_score","confidence","opportunity_score","data_completeness","valuation_coverage","methods_used","applicable_methods","research_status","red_flags","pe","pb","residual_income","ddm","dcf","ev_ebitda","book_nav_proxy","sotp","roe","eps_growth","revenue_growth","beta","dividend_per_share","dividend_payout_ratio","discount_rate","discount_rate_source"]

def append_snapshot(rows,path="data/history_v3.csv"):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); existing={}
    if p.exists():
        with p.open("r",newline="",encoding="utf-8") as f:
            for r in csv.DictReader(f): existing[(r.get("as_of_date"),r.get("ticker"))]=r
    d=date.today().isoformat()
    for r in rows:
        m=r["metrics"]; v=r["valuations"]; base=r.get("fair_value_base")
        existing[(d,r["ticker"])]={
          "as_of_date":d,"version":"V3","ticker":r["ticker"],"company_name":r.get("company_name") or "",
          "sector":r.get("sector") or "Unclassified","price":r.get("price"),"fair_value_bear":r.get("fair_value_bear"),
          "fair_value_base":base,"fair_value_bull":r.get("fair_value_bull"),
          "base_upside":((base-r["price"])/r["price"] if base and r.get("price") else None),
          "dispersion":r.get("dispersion"),"valuation_score":r.get("valuation_score"),"quality_score":r.get("quality_score"),
          "confidence_score":r.get("confidence_score"),"confidence":r.get("confidence"),"opportunity_score":r.get("opportunity_score"),
          "data_completeness":r.get("data_completeness"),"valuation_coverage":r.get("valuation_coverage"),
          "methods_used":r.get("methods_used"),"applicable_methods":",".join(r.get("applicable_methods",[])),
          "research_status":r.get("research_status"),"red_flags":"; ".join(r.get("red_flags",[])),
          "pe":m.get("pe"),"pb":m.get("pb"),"residual_income":v.get("residual_income"),"ddm":v.get("ddm"),
          "dcf":v.get("dcf"),"ev_ebitda":v.get("ev_ebitda"),"book_nav_proxy":v.get("book_nav_proxy"),"sotp":v.get("sotp"),
          "roe":m.get("roe"),"eps_growth":m.get("eps_growth"),"revenue_growth":m.get("revenue_growth"),
          "beta":m.get("beta"),"dividend_per_share":getattr(r.get("_cf"),"dividend_per_share",None),"dividend_payout_ratio":getattr(r.get("_cf"),"dividend_payout_ratio",None),"discount_rate":r.get("discount_rate"),"discount_rate_source":r.get("discount_rate_source")
        }
    with p.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader()
        for k in sorted(existing): w.writerow({x:("" if existing[k].get(x) is None else existing[k].get(x)) for x in FIELDS})
    return p
