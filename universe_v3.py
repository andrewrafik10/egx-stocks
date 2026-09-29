"""V3 dated EGX100 universe layer.

The universe is versioned by as-of date. V3 deliberately preserves the prior
configured EGX30 + EGX70 lists as a fallback until an official constituent
extract is available, rather than silently inventing membership.
"""
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import csv
import config

@dataclass(frozen=True)
class UniverseMember:
    ticker: str
    index_name: str
    as_of_date: str
    source: str
    active: bool = True

OFFICIAL_SOURCE = "EGX official index constituents"
FALLBACK_SOURCE = "V2.6 configured EGX30 + EGX70 snapshot"

def configured_members(as_of=None):
    as_of = as_of or date.today().isoformat()
    rows = []
    for t in config.EGX30_TICKERS:
        rows.append(UniverseMember(t, "EGX30", as_of, FALLBACK_SOURCE))
    for t in config.EGX70_TICKERS:
        if t not in config.EGX30_TICKERS:
            rows.append(UniverseMember(t, "EGX70 EWI", as_of, FALLBACK_SOURCE))
    return rows

def load_history(path="data/universe_history.csv"):
    p=Path(path)
    if not p.exists(): return []
    with p.open("r",encoding="utf-8") as f: return list(csv.DictReader(f))

def persist_snapshot(members, path="data/universe_history.csv"):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    existing={}
    if p.exists():
        with p.open("r",encoding="utf-8") as f:
            for r in csv.DictReader(f):
                existing[(r["as_of_date"],r["ticker"],r["index_name"])]=r
    for m in members:
        existing[(m.as_of_date,m.ticker,m.index_name)] = {
            "as_of_date":m.as_of_date,"ticker":m.ticker,"index_name":m.index_name,
            "active":str(m.active).lower(),"source":m.source
        }
    fields=["as_of_date","ticker","index_name","active","source"]
    with p.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for k in sorted(existing): w.writerow(existing[k])
    return p

def get_universe():
    members=configured_members()
    persist_snapshot(members)
    return members
