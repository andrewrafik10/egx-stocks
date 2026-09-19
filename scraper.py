"""
Scrapes per-ticker fundamental data from stockanalysis.com for EGX-listed stocks.

Pulls: current price & market cap (overview page), income statement,
balance sheet, and cash flow statement (TTM + last few FY columns).

Uses pandas.read_html against the rendered tables rather than hand-written
CSS selectors, since stockanalysis.com serves server-rendered HTML tables
(confirmed by inspection) - this is more robust to minor markup changes.

NOTE: this is scraping, not an official API. Be respectful:
 - one run per week is plenty
 - REQUEST_DELAY_SECONDS between calls (see config.py)
 - re-check stockanalysis.com's Terms of Use periodically
"""

import time
import io
import logging
from dataclasses import dataclass, field
from typing import Optional

import requests
import pandas as pd

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": config.USER_AGENT})


@dataclass
class CompanyFundamentals:
    ticker: str
    company_name: Optional[str] = None
    price: Optional[float] = None
    market_cap: Optional[float] = None
    shares_outstanding: Optional[float] = None

    revenue: Optional[float] = None
    net_income: Optional[float] = None
    eps: Optional[float] = None
    eps_history: list = field(default_factory=list)   # oldest -> newest, for growth calc

    total_equity: Optional[float] = None
    total_debt: Optional[float] = None
    cash: Optional[float] = None
    book_value_per_share: Optional[float] = None

    operating_cash_flow: Optional[float] = None
    capex: Optional[float] = None
    free_cash_flow: Optional[float] = None
    fcf_history: list = field(default_factory=list)

    ebitda: Optional[float] = None
    sector: Optional[str] = None

    errors: list = field(default_factory=list)


def _get(url: str) -> Optional[str]:
    try:
        resp = SESSION.get(url, timeout=config.REQUEST_TIMEOUT)
        if resp.status_code != 200:
            log.warning(f"{url} -> HTTP {resp.status_code}")
            return None
        return resp.text
    except requests.RequestException as e:
        log.warning(f"{url} -> {e}")
        return None


def _first_numeric_row(df: pd.DataFrame, row_label_contains: str, col_index: int = 1):
    """Find a row whose first column contains `row_label_contains` (case-insensitive)
    and return the value in `col_index`, cleaned to a float. Returns None if not found
    or not parseable (handles '-', 'B'/'M'/'K' suffixes, commas, %)."""
    try:
        mask = df.iloc[:, 0].astype(str).str.contains(row_label_contains, case=False, na=False)
        if not mask.any():
            return None
        raw = df.loc[mask].iloc[0, col_index]
        return _clean_number(raw)
    except Exception:
        return None


def _clean_number(raw) -> Optional[float]:
    if raw is None:
        return None
    s = str(raw).strip()
    if s in ("-", "", "nan", "None"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace(",", "").replace("%", "")
    multiplier = 1
    if s.endswith("B"):
        multiplier, s = 1e9, s[:-1]
    elif s.endswith("M"):
        multiplier, s = 1e6, s[:-1]
    elif s.endswith("K"):
        multiplier, s = 1e3, s[:-1]
    try:
        val = float(s) * multiplier
        return -val if neg else val
    except ValueError:
        return None


def fetch_ticker(ticker: str) -> CompanyFundamentals:
    cf = CompanyFundamentals(ticker=ticker)
    base = f"{config.BASE_URL}/{ticker}"

    # --- Overview: price, market cap, name ---
    html = _get(f"{base}/")
    if html:
        try:
            tables = pd.read_html(io.StringIO(html))
            for df in tables:
                if cf.market_cap is None:
                    cf.market_cap = _first_numeric_row(df, "Market Cap")
                if cf.shares_outstanding is None:
                    cf.shares_outstanding = _first_numeric_row(df, "Shares Out")
        except ValueError:
            pass
    time.sleep(config.REQUEST_DELAY_SECONDS)

    # --- Income statement (TTM + history for growth) ---
    html = _get(f"{base}/financials/income-statement/")
    if html:
        try:
            tables = pd.read_html(io.StringIO(html))
            for df in tables:
                if cf.revenue is None:
                    cf.revenue = _first_numeric_row(df, "^Revenue$")
                if cf.net_income is None:
                    cf.net_income = _first_numeric_row(df, "Net Income$") or _first_numeric_row(df, "Net Income to Common")
                if cf.eps is None:
                    cf.eps = _first_numeric_row(df, "EPS \\(Basic\\)") or _first_numeric_row(df, "EPS \\(Diluted\\)")
                # collect EPS across all history columns present for growth-rate estimation
                eps_mask = df.iloc[:, 0].astype(str).str.contains("EPS \\(Diluted\\)", case=False, na=False)
                if eps_mask.any():
                    row = df.loc[eps_mask].iloc[0]
                    cf.eps_history = [_clean_number(v) for v in row[1:] if _clean_number(v) is not None]
        except ValueError:
            pass
    time.sleep(config.REQUEST_DELAY_SECONDS)

    # --- Balance sheet ---
    html = _get(f"{base}/financials/balance-sheet/")
    if html:
        try:
            tables = pd.read_html(io.StringIO(html))
            for df in tables:
                if cf.total_equity is None:
                    cf.total_equity = _first_numeric_row(df, "Total Equity") or _first_numeric_row(df, "Shareholders. Equity")
                if cf.total_debt is None:
                    cf.total_debt = _first_numeric_row(df, "Total Debt")
                if cf.cash is None:
                    cf.cash = _first_numeric_row(df, "Cash & Equivalents") or _first_numeric_row(df, "Cash & Cash Equiv")
                if cf.book_value_per_share is None:
                    cf.book_value_per_share =
