"""V3 out-of-sample forward validation and backtesting.

The engine never uses information from after a signal date to form that signal.
A signal is evaluated only when a later weekly snapshot for the same ticker exists
at or after the requested horizon. Missing future prices are skipped, not invented.

Outputs:
- 1/3/6/12-month realized return statistics
- opportunity-score bucket performance
- confidence performance
- research-signal performance
- sector performance
- observation-level records for audit
"""
from pathlib import Path
from datetime import datetime
import csv
from statistics import median

HORIZONS={"1m":30,"3m":90,"6m":180,"12m":365}
SCORE_BUCKETS=[("0-40",0,40),("40-60",40,60),("60-75",60,75),("75-100",75,101)]

def _float(v):
    try:
        return float(v) if v not in (None,"") else None
    except (TypeError,ValueError):
        return None

def _load(path):
    p=Path(path)
    if not p.exists(): return []
    rows=[]
    with p.open("r",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try: r["_date"]=datetime.strptime(r["as_of_date"],"%Y-%m-%d").date()
            except Exception: continue
            r["_price"]=_float(r.get("price"))
            r["_score"]=_float(r.get("opportunity_score"))
            r["_upside"]=_float(r.get("base_upside"))
            rows.append(r)
    return rows

def _summary(records, key_name="all"):
    if not records: return None
    returns=[x["realized_return"] for x in records]
    scored=[x for x in records if x.get("opportunity_score") is not None]
    return {
        "group":key_name,
        "observations":len(records),
        "scored_observations":len(scored),
        "avg_return":sum(returns)/len(returns),
        "median_return":median(returns),
        "positive_rate":sum(x>0 for x in returns)/len(returns),
        "avg_score":(sum(x["opportunity_score"] for x in scored)/len(scored) if scored else None),
    }

def evaluate(path="data/history_v3.csv"):
    rows=_load(path)
    by={}
    for r in rows:
        by.setdefault(r["ticker"],[]).append(r)
    for v in by.values(): v.sort(key=lambda x:x["_date"])
    obs=[]
    for ticker,series in by.items():
        for i,o in enumerate(series):
            if o["_price"] is None: continue
            for horizon,days in HORIZONS.items():
                target=o["_date"].toordinal()+days
                future=next((x for x in series[i+1:] if x["_date"].toordinal()>=target and x["_price"] is not None),None)
                if future is None: continue
                obs.append({
                    "as_of_date":o["as_of_date"],"ticker":ticker,"horizon":horizon,
                    "opportunity_score":o["_score"],"base_upside":o["_upside"],
                    "confidence":o.get("confidence") or "Unknown",
                    "research_signal":o.get("research_signal") or "Unknown",
                    "sector":o.get("sector") or "Unknown",
                    "research_status":o.get("research_status") or "Unknown",
                    "realized_return":future["_price"]/o["_price"]-1,
                    "future_date":future["as_of_date"],
                })

    summary=[]
    for horizon in HORIZONS:
        s=_summary([x for x in obs if x["horizon"]==horizon],horizon)
        if s: summary.append(s)

    bucket_summary=[]
    for horizon in HORIZONS:
        for label,lo,hi in SCORE_BUCKETS:
            rec=[x for x in obs if x["horizon"]==horizon and x["opportunity_score"] is not None and lo<=x["opportunity_score"]<hi]
            s=_summary(rec,label)
            if s:
                s["horizon"]=horizon
                bucket_summary.append(s)

    confidence_summary=[]
    for horizon in HORIZONS:
        for label in ("High","Medium","Low"):
            rec=[x for x in obs if x["horizon"]==horizon and x["confidence"]==label]
            s=_summary(rec,label)
            if s:
                s["horizon"]=horizon
                confidence_summary.append(s)

    signal_summary=[]
    signals=sorted({x["research_signal"] for x in obs})
    for horizon in HORIZONS:
        for label in signals:
            rec=[x for x in obs if x["horizon"]==horizon and x["research_signal"]==label]
            s=_summary(rec,label)
            if s:
                s["horizon"]=horizon
                signal_summary.append(s)

    sector_summary=[]
    sectors=sorted({x["sector"] for x in obs})
    for horizon in HORIZONS:
        for label in sectors:
            rec=[x for x in obs if x["horizon"]==horizon and x["sector"]==label]
            s=_summary(rec,label)
            if s:
                s["horizon"]=horizon
                sector_summary.append(s)
    return summary,obs,bucket_summary,confidence_summary,signal_summary,sector_summary
