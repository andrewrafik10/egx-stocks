"""Rule-based price-structure detection.

Patterns are deliberately conservative. A pattern is reported only when the
geometry passes objective tolerance checks; otherwise "No reliable pattern"
is returned. This avoids turning every chart into a subjective pattern call.
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass
class PatternResult:
    name: str
    direction: str
    confidence: str
    details: str = ""

def _pivots(s: pd.Series, window: int = 4):
    highs, lows = [], []
    v = s.to_numpy(dtype=float)
    for i in range(window, len(v) - window):
        left, right = v[i-window:i], v[i+1:i+window+1]
        if v[i] >= left.max() and v[i] >= right.max():
            highs.append(i)
        if v[i] <= left.min() and v[i] <= right.min():
            lows.append(i)
    return highs, lows

def _slope(values, indices):
    if len(indices) < 2:
        return np.nan
    return np.polyfit(np.asarray(indices, dtype=float), np.asarray(values, dtype=float), 1)[0]

def detect_pattern(df: pd.DataFrame, lookback: int = 100) -> PatternResult:
    d = df.tail(lookback).reset_index(drop=True)
    if len(d) < 60:
        return PatternResult("Insufficient history", "Neutral", "Low")

    close = d["Close"].astype(float)
    highs, lows = _pivots(close, 4)
    if len(highs) < 2 or len(lows) < 2:
        return PatternResult("No reliable pattern", "Neutral", "Low")

    hi = highs[-4:]
    lo = lows[-4:]
    hs = _slope(close.iloc[hi].values, hi)
    ls = _slope(close.iloc[lo].values, lo)

    # Normalize slopes by the latest price so the rules work across EGX price scales.
    p = float(close.iloc[-1])
    hsn, lsn = hs / p, ls / p

    # Wedges: both boundaries slope in the same direction and converge.
    if hsn > 0 and lsn > 0 and hsn < lsn * 0.85:
        return PatternResult("Rising wedge", "Bearish", "Medium")
    if hsn < 0 and lsn < 0 and abs(hsn) < abs(lsn) * 0.85:
        return PatternResult("Falling wedge", "Bullish", "Medium")

    # Channels: boundaries move in the same direction with similar slopes.
    if hsn > 0 and lsn > 0 and abs(hsn - lsn) / max(abs(hsn), abs(lsn), 1e-9) < 0.45:
        return PatternResult("Ascending channel", "Bullish", "Medium")
    if hsn < 0 and lsn < 0 and abs(hsn - lsn) / max(abs(hsn), abs(lsn), 1e-9) < 0.45:
        return PatternResult("Descending channel", "Bearish", "Medium")

    # Double/triple bottoms: repeated lows within 3% of each other, with a rebound.
    low_vals = close.iloc[lo].values
    if len(low_vals) >= 3:
        a, b, c = low_vals[-3:]
        if max(a,b,c) / min(a,b,c) - 1 <= 0.03:
            return PatternResult("Triple bottom", "Bullish", "Medium")
    if len(low_vals) >= 2:
        a, b = low_vals[-2:]
        if max(a,b) / min(a,b) - 1 <= 0.03:
            mid_start, mid_end = lo[-2], lo[-1]
            rebound = close.iloc[mid_start:mid_end+1].max() / min(a,b) - 1
            if rebound >= 0.06:
                return PatternResult("Double bottom", "Bullish", "Medium")

    # Tops, symmetrical to bottoms.
    high_vals = close.iloc[hi].values
    if len(high_vals) >= 3:
        a, b, c = high_vals[-3:]
        if max(a,b,c) / min(a,b,c) - 1 <= 0.03:
            return PatternResult("Triple top", "Bearish", "Medium")
    if len(high_vals) >= 2:
        a, b = high_vals[-2:]
        if max(a,b) / min(a,b) - 1 <= 0.03:
            dip = 1 - close.iloc[hi[-2]:hi[-1]+1].min() / max(a,b)
            if dip >= 0.06:
                return PatternResult("Double top", "Bearish", "Medium")

    return PatternResult("No reliable pattern", "Neutral", "Low")
