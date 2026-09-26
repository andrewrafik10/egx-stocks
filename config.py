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

# --- Graham Number assumptions ---
# Classic formula: sqrt(22.5 x EPS x BVPS), where 22.5 = a P/E ceiling of 15
# times a P/B ceiling of 1.5. Adjusted per your request: P/E ceiling lowered
# to 5 (more conservative - demands a much cheaper earnings multiple before
# a stock counts as undervalued), P/B ceiling left at the classic 1.5.
GRAHAM_PE_CAP = 5
GRAHAM_PB_CAP = 1.5
GRAHAM_MULTIPLIER = GRAHAM_PE_CAP * GRAHAM_PB_CAP  # = 7.5

# --- Valuation assumptions ---
# EGP-denominated, reflecting Egypt's high-inflation environment.
#
# Cost of equity is now CAPM-based per stock: Rf + Beta x ERP, using each
# stock's own scraped Beta. Falls back to DEFAULT_COST_OF_EQUITY only when a
# stock has no Beta available. Inputs below should be refreshed periodically -
# they move with the macro environment (last set: Sep 2026).
#   - Risk-free rate: ~Egypt 10-year EGP government bond yield
#   - Equity risk premium: Damodaran's country-level total ERP for Egypt
#     (already includes both the mature-market base and Egypt's country risk
#     premium - do not add the mature-market rate again on top of this)
EGYPT_RISK_FREE_RATE = 0.215
EGYPT_EQUITY_RISK_PREMIUM = 0.1487
MIN_COST_OF_EQUITY = 0.15
MAX_COST_OF_EQUITY = 0.32
DEFAULT_COST_OF_EQUITY = 0.25       # fallback only, used when a stock has no Beta

# Sector-level cost-of-equity baseline used by the screening DCF.
# These are intentionally initialized to the market fallback rather than
# pretending to have precise sector estimates. Replace with a documented,
# periodically refreshed CAPM/beta-based dataset in the professional version.
SECTOR_COST_OF_EQUITY = {
    "Financials": DEFAULT_COST_OF_EQUITY,
    "Real Estate": DEFAULT_COST_OF_EQUITY,
    "Materials & Chemicals": DEFAULT_COST_OF_EQUITY,
    "Energy & Utilities": DEFAULT_COST_OF_EQUITY,
    "Consumer": DEFAULT_COST_OF_EQUITY,
    "Healthcare": DEFAULT_COST_OF_EQUITY,
    "Telecom & Technology": DEFAULT_COST_OF_EQUITY,
    "Industrials": DEFAULT_COST_OF_EQUITY,
    "Travel & Leisure": DEFAULT_COST_OF_EQUITY,
    "Other": DEFAULT_COST_OF_EQUITY,
}
DEFAULT_TERMINAL_GROWTH = 0.09      # long-run nominal growth assumption (EGP)
DCF_PROJECTION_YEARS = 5
FCF_HIGH_GROWTH_FADE = True         # fade explicit growth rate toward terminal over the projection

# Graham Number caveat: unreliable for banks/financials (BVPS distorted by
# leverage) and for negative-earnings names. Flagged automatically in ranking.py.
FINANCIAL_SECTOR_TICKERS = {
    "COMI", "QNBE", "HDBK", "ADIB", "CANA", "HRHO", "CIEB", "BTFH", "FAIT",
    "EXPA", "CICH", "UBEE", "SAUD", "EGBE", "SAIB",
}

# --- Sector classification for peer benchmarking ---
# Tier 1 (tightest): the exact "Industry" string scraped from each stock's
# overview page (e.g. "Agricultural Chemicals"). Used when enough EGX peers
# share that exact label.
# Tier 2 (fallback): broader macro-sector via keyword match against that same
# Industry string - order matters, first match wins.
# Tier 3 (guaranteed fallback): the existing Financial/Other split, which
# always has enough peers since it spans most of the universe.
MIN_PEER_GROUP_SIZE = 3  # minimum peers needed before trusting a tier's median

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

# Tier 3.5: fixed target P/E multiples by macro sector, used only when even the
# macro-sector peer group is too thin (< MIN_PEER_GROUP_SIZE) for a reliable
# EGX-data-driven median. These are analyst-judgment point estimates (midpoint
# of a reasonable range for the current market), not derived from live data -
# prefer real peer medians whenever there are enough peers to compute one.
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

# --- Ranking weights (must sum to 1.0 across methods actually available per stock) ---
METHOD_WEIGHTS = {
    "pe": 0.25,
    "graham": 0.20,
    "dcf": 0.30,
    "comps": 0.25,
}

# --- Ranking quality controls ---
# Below this many contributing methods, a stock's composite score is resting
# on too little evidence to rank normally - it's still shown, just sorted
# after higher-confidence names rather than dropped.
MIN_METHODS_FOR_RANK = 2
# Per-method winsorization caps on implied upside/downside, applied before
# blending into the composite. DCF is capped tighter than the others since
# it's the method most prone to extreme outliers on a thin FCF base.
METHOD_UPSIDE_CAPS = {
    "pe": 3.0,      # +/-300%
    "graham": 3.0,  # +/-300%
    "dcf": 1.5,     # +/-150%
    "comps": 3.0,   # +/-300%
}
