"""Rule-based order-block detection from OHLCV data.

Bullish OB = last bearish candle before a strong bullish displacement that
breaks a recent swing high. Bearish OB is the mirror image.

This is a screening definition, not a claim that order blocks are objectively
observable market facts. Zones are reported with their price boundaries.
"""
import pandas as pd

def detect_order_blocks(df: pd.DataFrame, lookback: int = 120):
    d = df.tail(lookback).copy().reset_index(drop=True)
    if len(d) < 30:
        return {"bullish": None, "bearish": None}

    atr = (d["High"] - d["Low"]).rolling(14).mean()
    bullish = bearish = None

    for i in range(15, len(d) - 3):
        body = abs(d.loc[i, "Close"] - d.loc[i, "Open"])
        if pd.isna(atr.iloc[i]) or body < 1.5 * atr.iloc[i]:
            continue

        prior_high = d.loc[max(0, i-10):i-1, "High"].max()
        prior_low = d.loc[max(0, i-10):i-1, "Low"].min()

        # Strong bullish displacement.
        if d.loc[i, "Close"] > d.loc[i, "Open"] and d.loc[i, "Close"] > prior_high:
            candidates = d.loc[max(0, i-5):i-1]
            bears = candidates[candidates["Close"] < candidates["Open"]]
            if not bears.empty:
                j = bears.index[-1]
                bullish = {
                    "low": float(d.loc[j, "Low"]),
                    "high": float(d.loc[j, "Open"]),
                    "index": int(j),
                }

        # Strong bearish displacement.
        if d.loc[i, "Close"] < d.loc[i, "Open"] and d.loc[i, "Close"] < prior_low:
            candidates = d.loc[max(0, i-5):i-1]
            bulls = candidates[candidates["Close"] > candidates["Open"]]
            if not bulls.empty:
                j = bulls.index[-1]
                bearish = {
                    "low": float(d.loc[j, "Open"]),
                    "high": float(d.loc[j, "High"]),
                    "index": int(j),
                }

    price = float(d["Close"].iloc[-1])
    def status(zone):
        if not zone:
            return {"present": False, "status": "No"}
        lo, hi = zone["low"], zone["high"]
        if lo <= price <= hi:
            s = "Inside"
        elif price < lo:
            s = "Below"
        else:
            s = "Above"
        distance = min(abs(price-lo), abs(price-hi)) / price * 100
        return {**zone, "present": True, "status": s, "distance_pct": round(distance, 2)}

    return {"bullish": status(bullish), "bearish": status(bearish)}
