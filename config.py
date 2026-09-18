"""
Configuration for the EGX Fundamental Analysis Bot.

IMPORTANT: EGX30 and EGX70 constituents are reviewed and can change twice a year
(official EGX committee review). The lists below are a starting point based on
market cap ranking as of Sep 2026 - verify/update against the official EGX
index composition before relying on this for real decisions:
https://www.egx.com.eg (Indices section)
"""

import os

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# --- Data source ---
BASE_URL = "https://stockanalysis.com/quote/egx"
REQUEST_DELAY_SECONDS = 2.0   # be polite - ~100+ tickers x 4 pages = 400+ requests/run
REQUEST_TIMEOUT = 20
USER_AGENT = "Mozilla/5.0 (compatible; personal-research-bot/1.0)"

# --- EGX30 constituents (verify periodically - see note above) ---
EGX30_TICKERS = [
    "COMI", "SWDY", "ETEL", "TMGH", "EGAL", "MFPC", "QNBE", "ABUK", "HDBK",
    "EAST", "ALCN", "ORAS", "EFIH", "EMFD", "ADIB", "FWRY", "SCTS", "ORHD",
    "EFID", "CANA", "OCDI", "PHDC", "JUFO", "HRHO", "GBCO", "HELI", "CIEB",
    "BTFH", "FAIT", "RAYA",
]

# --- EGX70 constituents (next tier by market cap - verify periodically) ---
EGX70_TICKERS = [
    "FERC", "EXPA", "ARCC", "IRON", "EGCH", "SCEM", "CCAP", "BIOC", "CLHO",
    "VALU", "MCQE", "MBSC", "CIRA", "EFIC", "PHAR", "TAQA", "SKPC", "MTIE",
    "POUL", "ORWE", "EGTS", "UBEE", "MASR", "AMOC", "EGSA", "SAUD", "NIPH",
    "MOIL", "ATQA", "KORA", "AMES", "MHOT", "EGBE", "TALM", "ISPH", "CICH",
    "RMDA", "CSAG", "OIH", "BINV", "IFAP", "MOIN", "ZMID", "AMIA", "MPCI",
    "MIPH", "OLFI", "MPRC", "SUGR", "ISMQ", "PRDC", "BONY", "EGAS", "AXPH",
    "PHTV", "CPCI", "DOMT", "GOUR", "ELEC", "NINH", "SPIN", "ACAP", "NAPR",
    "ENGC", "SPHT", "ARAB", "OCPH", "SVCE", "CNFN", "MICH",
]

ALL_TICKERS = sorted(set(EGX30_TICKERS + EGX70_TICKERS))

# --- Valuation assumptions ---
# EGP-denominated, reflecting Egypt's high-inflation environment.
# TODO: tune these, or better - derive per-sector CAPM inputs like you did
# for COMI/ETEL in your modeling portfolio, rather than one flat rate.
DEFAULT_COST_OF_EQUITY = 0.25       # ~25% - broad EGX blended proxy
DEFAULT_TERMINAL_GROWTH = 0.09      # long-run nominal growth assumption (EGP)
DCF_PROJECTION_YEARS = 5
FCF_HIGH_GROWTH_FADE = True         # fade explicit growth rate toward terminal over the projection

# Graham Number caveat: unreliable for banks/financials (BVPS distorted by
# leverage) and for negative-earnings names. Flagged automatically in ranking.py.
FINANCIAL_SECTOR_TICKERS = {
    "COMI", "QNBE", "HDBK", "ADIB", "CANA", "HRHO", "CIEB", "BTFH", "FAIT",
    "EXPA", "CICH", "UBEE", "SAUD", "EGBE", "SAIB",
}

# --- Ranking weights (must sum to 1.0 across methods actually available per stock) ---
METHOD_WEIGHTS = {
    "pe": 0.25,
    "graham": 0.20,
    "dcf": 0.30,
    "comps": 0.25,
}
