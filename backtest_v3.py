"""V3 forward-validation engine: 1/3/6/12 month realized returns."""
from pathlib import Path
from datetime import datetime
import csv

HORIZONS={"1m":30,"3m":90,"6m":180,"12m":365}

def evaluate(path="data/history_v3.csv"):
    p=Path(path)
    if not p.exists(): return [],[]
    rows=list(csv.DictReader(p.open("r",encoding="utf-8")))
    for r in rows:
        r["_date"]=datetime.strptime(r["as_of_date"],"%Y-%m-%d").date()
        r["_price"]=float(r["price"]) if r.get("price") else None
        r["_score"]=float(r["opportunity_score"]) if r.get("opportunity_score") else None
        r["_upside"]=float(r["base_upside"]) if r.get("base_upside") else None
    by={}
    for r in rows: by.setdefault(r["ticker"],[]).append(r)
    for v in by.values(): v.sort(key=lambda x:x["_date"])
    obs=[]
    for ticker,series in by.items():
        for i,o in enumerate(series):
            if o["_price"] is None: continue
            for h,days in HORIZONS.items():
                target=o["_date"].toordinal()+days
                f=next((x for x in series[i+1:] if x["_date"].toordinal()>=target and x["_price"] is not None),None)
                if f:
                    obs.append({"as_of_date":o["as_of_date"],"ticker":ticker,"horizon":h,"opportunity_score":o["_score"],"base_upside":o["_upside"],"realized_return":f["_price"]/o["_price"]-1,"future_date":f["as_of_date"]})
    summary=[]
    for h in HORIZONS:
        a=[x for x in obs if x["horizon"]==h]; s=[x for x in a if x["opportunity_score"] is not None]
        if not a: continue
        rets=sorted(x["realized_return"] for x in a)
        summary.append({"horizon":h,"observations":len(a),"scored_observations":len(s),"avg_return":sum(rets)/len(rets),"median_return":rets[len(rets)//2],"positive_rate":sum(x["realized_return"]>0 for x in s)/len(s) if s else None,"avg_score":sum(x["opportunity_score"] for x in s)/len(s) if s else None})
    return summary,obs
