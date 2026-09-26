"""Persistent weekly signal history for EGX V2.5."""
from pathlib import Path
from datetime import date
import csv

HISTORY_PATH = Path("data/history.csv")

FIELDS = [
    "as_of_date","ticker","company_name","sector","price",
    "fair_value_bear","fair_value_base","fair_value_bull",
    "base_upside","dispersion","quality_score","opportunity_score",
    "confidence_score","confidence","data_completeness","methods_used",
    "pe","pb","dcf","comps","roe","net_margin","ebitda_margin",
    "fcf_margin","debt_equity","eps_growth","revenue_growth","beta","discount_rate","discount_rate_source"
]

def append_snapshot(rows, path=HISTORY_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if path.exists():
        with path.open("r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing[(row.get("as_of_date"), row.get("ticker"))] = row

    as_of = date.today().isoformat()
    for r in rows:
        m = r["metrics"]
        base_upside = None
        if r.get("fair_value_base") is not None and r.get("price"):
            base_upside = (r["fair_value_base"] - r["price"]) / r["price"]
        values = {
            "as_of_date": as_of,
            "ticker": r["ticker"],
            "company_name": r.get("company_name") or "",
            "sector": r.get("sector") or "Unclassified",
            "price": r.get("price"),
            "fair_value_bear": r.get("fair_value_bear"),
            "fair_value_base": r.get("fair_value_base"),
            "fair_value_bull": r.get("fair_value_bull"),
            "base_upside": base_upside,
            "dispersion": r.get("dispersion"),
            "quality_score": r.get("quality_score"),
            "opportunity_score": r.get("opportunity_score"),
            "confidence_score": r.get("confidence_score"),
            "confidence": r.get("confidence"),
            "data_completeness": r.get("data_completeness"),
            "methods_used": r.get("methods_used"),
            "pe": m.get("pe"), "pb": m.get("pb"),
            "dcf": r["valuations"].get("dcf"),
            "comps": r["valuations"].get("comps"),
            "roe": m.get("roe"), "net_margin": m.get("net_margin"),
            "ebitda_margin": m.get("ebitda_margin"), "fcf_margin": m.get("fcf_margin"),
            "debt_equity": m.get("debt_equity"), "eps_growth": m.get("eps_growth"),
            "revenue_growth": m.get("revenue_growth"),
            "beta": m.get("beta"),
            "discount_rate": r.get("discount_rate"),
            "discount_rate_source": r.get("discount_rate_source")
        }
        existing[(as_of, r["ticker"])] = {
            k: "" if v is None else v for k, v in values.items()
        }

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for key in sorted(existing):
            writer.writerow({k: existing[key].get(k, "") for k in FIELDS})
    return path
