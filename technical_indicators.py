"""Pure-pandas technical indicators for EGX technical scanning.

Indicators:
- RSI(14), Wilder-style
- CCI(14)
- EMA(50), EMA(200)

No TA-Lib dependency is required, which keeps GitHub Actions portable.
"""
import pandas as pd

def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    out = 100 - (100 / (1 + rs))
    return out.fillna(100)

def cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    typical = (high + low + close) / 3
    sma = typical.rolling(period, min_periods=period).mean()
    mean_dev = typical.rolling(period, min_periods=period).apply(
        lambda x: float(abs(x - x.mean()).mean()), raw=True
    )
    return (typical - sma) / (0.015 * mean_dev.replace(0, pd.NA))

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["rsi_14"] = rsi(out["Close"], 14)
    out["cci_14"] = cci(out["High"], out["Low"], out["Close"], 14)
    out["ema_50"] = out["Close"].ewm(span=50, adjust=False, min_periods=50).mean()
    out["ema_200"] = out["Close"].ewm(span=200, adjust=False, min_periods=200).mean()
    return out
