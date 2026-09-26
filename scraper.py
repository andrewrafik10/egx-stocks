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
import re
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
    revenue_history: list = field(default_factory=list) # oldest -> newest

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
    beta: Optional[float] = None

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
    # Pull out just the leading numeric token - handles cells where a growth
    # badge is concatenated onto the value with no separator, e.g. the overview
    # page's "Market Cap" cell rendering as "116.79B+75.0%" in one <td>.
    m = re.match(r'^\(?-?[\d,]*\.?\d+[BMK]?\)?', s)
    if not m:
        return None
    token = m.group(0)
    neg = token.startswith("(") and token.endswith(")")
    token = token.strip("()").replace(",", "")
    multiplier = 1
    if token.endswith("B"):
        multiplier, token = 1e9, token[:-1]
    elif token.endswith("M"):
        multiplier, token = 1e6, token[:-1]
    elif token.endswith("K"):
        multiplier, token = 1e3, token[:-1]
    try:
        val = float(token) * multiplier
        return -val if neg else val
    except ValueError:
        return None


def fetch_ticker(ticker: str) -> CompanyFundamentals:
    cf = CompanyFundamentals(ticker=ticker)
    base = f"{config.BASE_URL}/{ticker}"

    # --- Overview: price, market cap, name, industry ---
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
        # Industry classification, pulled from the page's embedded JS data
        # payload rather than a <table> - e.g. `{t:"Industry",v:"Agricultural
        # Chemicals",u:null}` - regex is far simpler and more robust here than
        # trying to parse the surrounding Svelte-hydrated markup.
        m = re.search(r'\{t:"Industry",v:"([^"]+)"', html)
        if m:
            cf.sector = m.group(1)
    time.sleep(config.REQUEST_DELAY_SECONDS)

    # --- Income statement (TTM + history for growth) ---
    html = _get(f"{base}/financials/income-statement/")
    if html:
        try:
            tables = pd.read_html(io.StringIO(html))
            for df in tables:
                if cf.revenue is None:
                    cf.revenue = _first_numeric_row(df, "^Revenue$")
                revenue_mask = df.iloc[:, 0].astype(str).str.contains("^Revenue$", case=False, na=False, regex=True)
                if revenue_mask.any():
                    row = df.loc[revenue_mask].iloc[0]
                    cf.revenue_history = [_clean_number(v) for v in row[1:] if _clean_number(v) is not None]
                if cf.net_income is None:
                    cf.net_income = _first_numeric_row(df, "Net Income$") or _first_numeric_row(df, "Net Income to Common")
                if cf.eps is None:
                    cf.eps = _first_numeric_row(df, "EPS \\(Basic\\)") or _first_numeric_row(df, "EPS \\(Diluted\\)")
                if cf.ebitda is None:
                    cf.ebitda = _first_numeric_row(df, "^EBITDA$")
                if cf.beta is None:
                    cf.beta = (_first_numeric_row(df, "Beta \(5Y Monthly\)")
                               or _first_numeric_row(df, "^Beta$"))
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
                    cf.book_value_per_share = _first_numeric_row(df, "Book Value Per Share")
        except ValueError:
            pass
    time.sleep(config.REQUEST_DELAY_SECONDS)

    # --- Cash flow statement ---
    html = _get(f"{base}/financials/cash-flow-statement/")
    if html:
        try:
            tables = pd.read_html(io.StringIO(html))
            for df in tables:
                if cf.operating_cash_flow is None:
                    cf.operating_cash_flow = _first_numeric_row(df, "Operating Cash Flow")
                if cf.capex is None:
                    cf.capex = _first_numeric_row(df, "Capital Expenditures")
                if cf.free_cash_flow is None:
                    cf.free_cash_flow = _first_numeric_row(df, "Free Cash Flow")
                fcf_mask = df.iloc[:, 0].astype(str).str.contains("^Free Cash Flow$", case=False, na=False, regex=True)
                if fcf_mask.any():
                    row = df.loc[fcf_mask].iloc[0]
                    cf.fcf_history = [_clean_number(v) for v in row[1:] if _clean_number(v) is not None]
        except ValueError:
            pass
    time.sleep(config.REQUEST_DELAY_SECONDS)

    # --- Ratios (EV/EBITDA, current price, sector-comparable multiples) ---
    html = _get(f"{base}/financials/ratios/")
    if html:
        try:
            tables = pd.read_html(io.StringIO(html))
            for df in tables:
                if cf.ebitda is None:
                    cf.ebitda = _first_numeric_row(df, "^EBITDA$")
        except ValueError:
            pass

    # derive price from market cap / shares if not separately captured
    if cf.price is None and cf.market_cap and cf.shares_outstanding:
        cf.price = cf.market_cap / cf.shares_outstanding

    # The financial-statement pages (income statement, balance sheet, cash flow)
    # express monetary line items in millions, unlike the overview page's summary
    # cards (which carry explicit B/M/K suffixes already handled by _clean_number).
    # Per-share figures (EPS, BVPS) and the overview page's price/market_cap are
    # NOT rescaled here - only aggregate financial-statement dollar figures are.
    MILLIONS = 1_000_000
    for attr in ("revenue", "net_income", "total_equity", "total_debt", "cash",
                 "operating_cash_flow", "capex", "free_cash_flow", "ebitda"):
        val = getattr(cf, attr)
        if val is not None:
            setattr(cf, attr, val * MILLIONS)
    cf.fcf_history = [v * MILLIONS if v is not None else None for v in cf.fcf_history]

    # sanity flags
    if cf.eps is None:
        cf.errors.append("missing EPS")
    if cf.book_value_per_share is None:
        cf.errors.append("missing book value/share")
    if cf.free_cash_flow is None and cf.operating_cash_flow and cf.capex:
        cf.free_cash_flow = cf.operating_cash_flow - abs(cf.capex)

    return cf


def fetch_universe(tickers: list) -> dict:
    """Fetch all tickers, returns {ticker: CompanyFundamentals}. Logs progress.
    Logs a full field dump for the first few tickers so mismatched row-label
    matching can be diagnosed from the Action log without live access to the site."""
    results = {}
    DEBUG_DUMP_COUNT = 5
    for i, t in enumerate(tickers, 1):
        log.info(f"[{i}/{len(tickers)}] Fetching {t} ...")
        cf = fetch_ticker(t)
        results[t] = cf
        if i <= DEBUG_DUMP_COUNT:
            log.info(
                f"DEBUG {t}: price={cf.price} market_cap={cf.market_cap} "
                f"shares_out={cf.shares_outstanding} revenue={cf.revenue} "
                f"net_income={cf.net_income} eps={cf.eps} eps_history={cf.eps_history} "
                f"total_equity={cf.total_equity} total_debt={cf.total_debt} cash={cf.cash} "
                f"bvps={cf.book_value_per_share} ocf={cf.operating_cash_flow} "
                f"capex={cf.capex} fcf={cf.free_cash_flow} fcf_history={cf.fcf_history} "
                f"ebitda={cf.ebitda} beta={cf.beta}"
            )
        if cf.errors:
            log.warning(f"{t}: {cf.errors}")
    return results

