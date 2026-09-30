"""EGX100 technical scanner.

Data source: Yahoo Finance chart endpoint, using EGX Reuters-style .CA symbols.
The scanner stores the exact last trading date so delayed/missing names are
visible rather than silently treated as fresh.

Outputs:
  output/egx100_technical_scan_YYYY-MM-DD.csv
  output/egx100_technical_scan_YYYY-MM-DD.xlsx
"""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import logging
import time
import requests
import pandas as pd

from technical_indicators import add_indicators
from pattern_detection import detect_pattern
from order_blocks import detect_order_blocks

log = logging.getLogger(__name__)
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

UNIVERSE = [
    "COMI","SWDY","ETEL","EGAL","MFPC","QNBE","ABUK","HDBK","EAST","ALCN",
    "ORAS","EFIH","EMFD","ADIB","FWRY","SCTS","ORHD","EFID","CANA","OCDI",
    "PHDC","JUFO","HRHO","GBCO","HELI","CIEB","BTFH","FAIT","RAYA","CCAP",
    "FERC","EXPA","ARCC","IRON","EGCH","SCEM","CLHO","VALU","MCQE","MBSC",
    "CIRA","EFIC","PHAR","TAQA","SKPC","MTIE","POUL","ORWE","EGTS","UBEE",
    "MASR","AMOC","EGSA","SAUD","NIPH","MOIL","ATQA","KORA","AMES","MHOT",
    "EGBE","ISPH","CICH","RMDA","CSAG","OIH","BINV","MOIN","ZMID","AMIA",
    "MPCI","MIPH","OLFI","MPRC","SUGR","ISMQ","PRDC","BONY","EGAS","AXPH",
    "PHTV","CPCI","DOMT","NAPR","ENGC","SPHT","ARAB","OCPH","SVCE","CNFN",
    "MICH","ALRA","ELKA","GDWA","GPIM","GOUR","ELEC","AIFI","ACTF","TMGH"
]
UNIVERSE = list(dict.fromkeys(UNIVERSE))

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 EGX100-research-scanner/1.0"})

def fetch_history(ticker: str, years: int = 3) -> pd.DataFrame:
    symbol = f"{ticker}.CA"
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365 * years)
    params = {
        "period1": int(start.timestamp()),
        "period2": int(end.timestamp()),
        "interval": "1d",
        "events": "history",
        "includeAdjustedClose": "true",
    }
    r = SESSION.get(YAHOO_CHART.format(symbol=symbol), params=params, timeout=30)
    r.raise_for_status()
    payload = r.json()
    result = (payload.get("chart") or {}).get("result")
    if not result:
        raise ValueError("No Yahoo Finance history")
    result = result[0]
    ts = result.get("timestamp", [])
    quote = (result.get("indicators") or {}).get("quote", [{}])[0]
    df = pd.DataFrame({
        "Open": quote.get("open", []),
        "High": quote.get("high", []),
        "Low": quote.get("low", []),
        "Close": quote.get("close", []),
        "Volume": quote.get("volume", []),
    }, index=pd.to_datetime(ts, unit="s", utc=True).tz_convert(None))
    df = df.dropna(subset=["Close"])
    if len(df) < 210:
        raise ValueError(f"Only {len(df)} daily rows; need >=210 for EMA200")
    return df

def scan_one(ticker: str) -> dict:
    df = add_indicators(fetch_history(ticker))
    last = df.iloc[-1]
    p = float(last["Close"])
    ema50, ema200 = float(last["ema_50"]), float(last["ema_200"])
    rsi14, cci14 = float(last["rsi_14"]), float(last["cci_14"])
    pattern = detect_pattern(df)
    obs = detect_order_blocks(df)
    bull, bear = obs["bullish"], obs["bearish"]

    return {
        "ticker": ticker, "symbol": f"{ticker}.CA",
        "data_date": pd.Timestamp(df.index[-1]).date().isoformat(),
        "close": round(p, 6), "rsi_14": round(rsi14, 2),
        "rsi_status": "Oversold" if rsi14 < 30 else "Overbought" if rsi14 > 70 else "Neutral",
        "cci_14": round(cci14, 2),
        "cci_status": "Bullish" if cci14 > 100 else "Bearish" if cci14 < -100 else "Neutral",
        "ema_50": round(ema50, 6), "ema_200": round(ema200, 6),
        "ema_50_vs_200": "Above" if ema50 > ema200 else "Below",
        "price_vs_ema50": "Above" if p > ema50 else "Below",
        "price_vs_ema200": "Above" if p > ema200 else "Below",
        "trend": "Bullish" if p > ema50 > ema200 else "Bearish" if p < ema50 < ema200 else "Mixed",
        "pattern": pattern.name, "pattern_direction": pattern.direction,
        "pattern_confidence": pattern.confidence,
        "bullish_order_block": "Yes" if bull and bull.get("status") in ("Inside","Above") else "No",
        "bullish_ob_status": bull.get("status") if bull else "No",
        "bullish_ob_low": bull.get("low") if bull else None,
        "bullish_ob_high": bull.get("high") if bull else None,
        "bullish_ob_distance_pct": bull.get("distance_pct") if bull else None,
        "bearish_order_block": "Yes" if bear and bear.get("status") in ("Inside","Below") else "No",
        "bearish_ob_status": bear.get("status") if bear else "No",
        "bearish_ob_low": bear.get("low") if bear else None,
        "bearish_ob_high": bear.get("high") if bear else None,
        "bearish_ob_distance_pct": bear.get("distance_pct") if bear else None,
        "error": "",
    }

def run_scan() -> pd.DataFrame:
    rows = []
    for i, ticker in enumerate(UNIVERSE, 1):
        log.info("[%s/%s] %s", i, len(UNIVERSE), ticker)
        try:
            rows.append(scan_one(ticker))
        except Exception as exc:
            log.warning("%s failed: %s", ticker, exc)
            rows.append({"ticker": ticker, "symbol": f"{ticker}.CA", "error": str(exc)})
        time.sleep(0.25)
    return pd.DataFrame(rows)

def save_outputs(df: pd.DataFrame):
    out = Path("output"); out.mkdir(exist_ok=True)
    stamp = date.today().isoformat()
    csv_path = out / f"egx100_technical_scan_{stamp}.csv"
    xlsx_path = out / f"egx100_technical_scan_{stamp}.xlsx"
    df.to_csv(csv_path, index=False)
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="EGX100 Technical", index=False)
        ws = writer.book["EGX100 Technical"]; ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
        for col in ws.columns:
            width = min(max(len(str(c.value or "")) for c in col) + 2, 32)
            ws.column_dimensions[col[0].column_letter].width = width
    return csv_path, xlsx_path

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    df = run_scan()
    csv_path, xlsx_path = save_outputs(df)
    print(f"Saved {csv_path}")
    print(f"Saved {xlsx_path}")
    print(f"Universe rows: {len(df)}; successful: {df['error'].eq('').sum() if 'error' in df else len(df)}")
