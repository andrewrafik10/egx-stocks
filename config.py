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
REQUEST_DELAY_SECONDS = 2.0
REQUEST_TIMEOUT = 20
USER_AGENT = "Mozilla/5.0 (compatible; personal-research-bot/1.0)"

# --- EGX30 constituents (verify periodically) ---
EGX30_TICKERS = [
    "COMI", "SWDY", "ETEL", "TMGH", "EGAL", "MFPC", "QNBE", "ABUK", "HDBK",
    "EAST", "ALCN", "ORAS", "EFIH", "EMFD", "ADIB", "FWRY", "SCTS", "ORHD",
    "EFID", "CANA", "OCDI", "PHDC", "JUFO", "HRHO", "GBCO", "HELI", "CIEB",
    "BTFH", "FAIT", "RAYA",
]

# --- EGX70 constituents ---
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

# --- Graham Number assumptions ---
GRAHAM_PE_CAP = 5
GRAHAM_PB_CAP = 1.5
GRAHAM_MULTIPLIER = GRAHAM_PE_CAP * GRAHAM_PB_CAP  # = 7.5

# --- Valuation assumptions ---
DEFAULT_COST_OF_EQUITY = 0.25       # fallback only
DEFAULT_TERMINAL_GROWTH = 0.09
DCF_PROJECTION_YEARS = 5
FCF_HIGH_GROWTH_FADE = True

# Cost of Equity by macro sector (more realistic than one flat rate)
SECTOR_COST_OF_EQUITY = {
    "Financials": 0.27,
    "Real Estate": 0.26,
    "Materials & Chemicals": 0.25,
    "Healthcare": 0.24,
    "Consumer": 0.24,
    "Telecom & Technology": 0.23,
    "Energy & Utilities": 0.25,
    "Industrials": 0.25,
    "Travel & Leisure": 0.26,
    "Other": 0.25,
}

# Graham Number is unreliable for banks/financials
FINANCIAL_SECTOR_TICKERS = {
    "COMI", "QNBE", "HDBK", "ADIB", "CANA", "HRHO", "CIEB", "BTFH", "FAIT",
    "EXPA", "CICH", "UBEE", "SAUD", "EGBE", "SAIB",
}

# --- Sector classification ---
MIN_PEER_GROUP_SIZE = 3

SECTOR_KEYWORDS = [
    ("Financials", ["bank", "insurance", "financial", "asset management", "credit", "capital markets"]),
    ("Real Estate", ["real estate", "reit", "engineering & construction"]),
    ("Materials & Chemicals", ["chemical", "fertilizer", "steel", "metal", "mining", "paper", "packaging", "building materials", "cement", "construction materials"]),
    ("Energy & Utilities", ["oil", "gas", "energy", "utilit", "electric"]),
    ("Consumer", ["food", "beverage", "retail", "apparel", "household", "personal products", "tobacco", "restaurant", "grocery", "consumer"]),
    ("Healthcare", ["pharma", "health", "biotech", "medical", "drug"]),
    ("Telecom & Technology", ["telecom", "software", "technology", "internet", "semiconductor", "it services", "media"]),
    ("Industrials", ["industrial", "machinery", "manufactur", "transport", "logistics", "aerospace", "defense", "conglomerate", "electrical equipment", "shipping"]),
    ("Travel & Leisure", ["hotel", "resort", "tourism", "leisure", "entertainment", "broadcasting"]),
]

SECTOR_TARGET_PE = {
    "Financials": 7.5,
    "Real Estate": 10.0,
    "Materials & Chemicals": 8.5,
    "Healthcare": 11.5,
    "Consumer": 10.0,
    "Telecom & Technology": 9.5,
    "Energy & Utilities": 8.0,
    "Industrials": 9.5,
    "Travel & Leisure": 9.5,
    "Other": 9.5,
}

# --- Ranking weights ---
METHOD_WEIGHTS = {
    "pe": 0.25,
    "graham": 0.20,
    "dcf": 0.30,
    "comps": 0.25,
}

# --- Ranking quality controls ---
MIN_METHODS_FOR_RANK = 2

METHOD_UPSIDE_CAPS = {
    "pe": 3.0,
    "graham": 3.0,
    "dcf": 1.5,
    "comps": 3.0,
}
