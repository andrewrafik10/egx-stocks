"""Backtest-ready evaluation of weekly V2.5 signals.

The engine does not invent missing prices. It uses the first future snapshot
on/after each target horizon, so results are reproducible from stored weekly
runs.
"""
from pathlib import Path
from datetime import datetime
import csv
import math

HORIZONS = {"1w": 7, "4w": 28, "12w": 84}

def _read(path="data/history.csv"):
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["_date"] = datetime.strptime(r["as_of_date"], "%Y-%m-%d").date()
        r["_price"] = float(r["price"]) if r.get("price") else None
        r["_score"] = float(r["opportunity_score"]) if r.get("opportunity_score") else None
        r["_upside"] = float(r["base_upside"]) if r.get("base_upside") else None
    return rows

def evaluate(path="data/history.csv"):
    rows = _read(path)
    by_ticker = {}
    for r in rows:
        by_ticker.setdefault(r["ticker"], []).append(r)
    for v in by_ticker.values():
        v.sort(key=lambda x: x["_date"])

    observations = []
    for ticker, series in by_ticker.items():
        for i, origin in enumerate(series):
            if origin["_price"] is None:
                continue
            for label, days in HORIZONS.items():
                target = origin["_date"].fromordinal(origin["_date"].toordinal() + days)
                future = next((x for x in series[i+1:] if x["_date"] >= target and x["_price"] is not None), None)
                if not future:
                    continue
                ret = future["_price"] / origin["_price"] - 1
                observations.append({
                    "as_of_date": origin["as_of_date"], "ticker": ticker,
                    "horizon": label, "opportunity_score": origin["_score"],
                    "base_upside": origin["_upside"], "realized_return": ret,
                    "future_date": future["as_of_date"]
                })

    summary = []
    for horizon in HORIZONS:
        obs = [x for x in observations if x["horizon"] == horizon]
        if not obs:
            continue
        scored = [x for x in obs if x["opportunity_score"] is not None]
        positive = [x for x in scored if x["realized_return"] > 0]
        summary.append({
            "horizon": horizon,
            "observations": len(obs),
            "scored_observations": len(scored),
            "avg_return": sum(x["realized_return"] for x in obs) / len(obs),
            "median_return": sorted(x["realized_return"] for x in obs)[len(obs)//2],
            "positive_rate": len(positive) / len(scored) if scored else None,
            "avg_score": sum(x["opportunity_score"] for x in scored) / len(scored) if scored else None
        })
    return summary, observations

if __name__ == "__main__":
    summary, _ = evaluate()
    for row in summary:
        print(row)
