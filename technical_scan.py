"""EGX100 technical scanner.

Data source: Yahoo Finance via yfinance, using EGX Reuters-style .CA symbols.
Yahoo supports EGX quotes such as COMI.CA; the scanner stores the exact data
date so delayed/missing names are visible rather than silently treated as fresh.

Outputs:
  output/egx100_technical_scan_YYYY-MM-DD.csv
  output/egx100_technical_scan_YYYY-MM-DD.xlsx
"""
from __future__ import annotations
from datetime import date
from pathlib import Path
import logging
import pandas as pd
import yfinance as yf

from technical_indicators import add_indicators
from pattern_detection import detect_pattern
from order_blocks import detect_order_blocks

log = logging.getLogger(__name__)

UNIVERSE = [
    # Existing EGX100 research universe, plus September-2026 additions.
    "COMI","SWDY","ETEL","EGAL","MFPC","QNBE","ABUK","HDBK","EAST","ALCN",
    "ORAS","EFIH","EMFD","ADIB","FWRY","SCTS","ORHD","EFID","CANA","OCDI",
    "PHDC","JUFO","HRHO","GBCO","HELI","CIEB","BTFH","FAIT","RAYA","CCAP",
    "FERC","EXPA","ARCC","IRON","EGCH","SCEM","CCAP","BIOC","CLHO","VALU",
    "MCQE","MBSC","CIRA","EFIC","PHAR","TAQA","SKPC","MTIE","POUL","ORWE",
    "EGTS","UBEE","MASR","AMOC","EGSA","SAUD","NIPH","MOIL","ATQA","KORA",
    "AMES","MHOT","EGBE","TALM","ISPH","CICH","RMDA","CSAG","OIH","BINV",
    "IFAP","MOIN","ZMID","AMIA","MPCI","MIPH","OLFI","MPRC","SUGR","ISMQ",
    "PRDC","BONY","EGAS","AXPH","PHTV","CPCI","DOMT","GOUR","ELEC","GBCO",
    "GOUR","NAPR","ENGC","SPHT","ARAB","OCPH","SVCE","CNFN","MICH",
    # September 2026 EGX100 additions / current-code updates:
    "ALRA","ELKA","GDWA","GPIM",
]
# Remove duplicates while preserving order.
UNIVERSE = list(dict.fromkeys(UNIVERSE))

def fetch_history(ticker: str, period: str = "2y") -> pd.DataFrame:
    symbol = f"{ticker}.CA"
    df = yf.download(symbol, period=period, interval="1d", auto_adjust=False,
                     progress=False, threads=False)
    if df is None or df.empty:
        raise ValueError("No Yahoo Finance history")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    required = ["Open","High","Low","Close","Volume"]
    df = df[[c for c in required if c in df.columns]].dropna(subset=["Close"])
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
    bull = obs["bullish"]
    bear = obs["bearish"]

    return {
        "ticker": ticker,
        "symbol": f"{ticker}.CA",
        "data_date": pd.Timestamp(df.index[-1]).date().isoformat(),
        "close": round(p, 6),
        "rsi_14": round(rsi14, 2),
        "rsi_status": "Oversold" if rsi14 < 30 else "Overbought" if rsi14 > 70 else "Neutral",
        "cci_14": round(cci14, 2),
        "cci_status": "Bullish" if cci14 > 100 else "Bearish" if cci14 < -100 else "Neutral",
        "ema_50": round(ema50, 6),
        "ema_200": round(ema200, 6),
        "ema_50_vs_200": "Above" if ema50 > ema200 else "Below",
        "price_vs_ema50": "Above" if p > ema50 else "Below",
        "price_vs_ema200": "Above" if p > ema200 else "Below",
        "trend": "Bullish" if p > ema50 > ema200 else "Bearish" if p < ema50 < ema200 else "Mixed",
        "pattern": pattern.name,
        "pattern_direction": pattern.direction,
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
    df = pd.DataFrame(rows)
    if not df.empty and "close" in df:
        df = df.sort_values(["trend","rsi_14"], ascending=[True, True], na_position="last")
    return df

def save_outputs(df: pd.DataFrame):
    out = Path("output")
    out.mkdir(exist_ok=True)
    stamp = date.today().isoformat()
    csv_path = out / f"egx100_technical_scan_{stamp}.csv"
    xlsx_path = out / f"egx100_technical_scan_{stamp}.xlsx"
    df.to_csv(csv_path, index=False)
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="EGX100 Technical", index=False)
        ws = writer.book["EGX100 Technical"]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
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
