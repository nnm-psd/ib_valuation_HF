from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_RAW_DIR       = ROOT_DIR / "data" / "raw"
DATA_PROCESSED_DIR = ROOT_DIR / "data" / "processed"
DATA_CACHE_DIR     = ROOT_DIR / "data" / "cache"

DB_PATH = DATA_PROCESSED_DIR / "valuation_lab.db"
DB_URL  = f"sqlite:///{DB_PATH}"

DEFAULT_MARKET_RISK_PREMIUM  = 0.05
DEFAULT_TERMINAL_GROWTH_RATE = 0.02
DEFAULT_TAX_RATE_FR          = 0.25
