"""Optional InvestingPro Fair Value benchmark.

Only verified InvestingPro values should be entered here. Public Investing.com
pages expose the Fair Value feature, but many exact values are Pro-locked.
Blank values therefore mean unavailable/unverified, never zero or an estimate.
"""
from pathlib import Path
import csv

PATH = Path("data/investingpro_fair_value.csv")

def load():
    out={}
    if not PATH.exists():
        return out
    with PATH.open("r",encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            t=(r.get("ticker") or "").strip().upper()
            if not t: continue
            fv=r.get("fair_value")
            try: fv=float(fv) if fv not in (None,"") else None
            except ValueError: fv=None
            price_up=r.get("fair_value_upside")
            try: price_up=float(price_up) if price_up not in (None,"") else None
            except ValueError: price_up=None
            out[t]={
                "fair_value":fv,
                "fair_value_upside":price_up,
                "as_of_date":r.get("as_of_date"),
                "source":r.get("source") or "Investing.com InvestingPro",
                "verification_status":r.get("verification_status") or ("Verified" if fv is not None else "Not publicly verifiable"),
            }
    return out
