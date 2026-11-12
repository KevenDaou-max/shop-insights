"""Central paths and tunable defaults, so magic numbers live in one place."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SAMPLE_DIR = DATA_DIR / "sample"

DATASET_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
RAW_ZIP = RAW_DIR / "online_retail_ii.zip"
RAW_XLSX = RAW_DIR / "online_retail_II.xlsx"
CLEAN_PARQUET = PROCESSED_DIR / "orders_clean.parquet"
SAMPLE_STOCK_CSV = SAMPLE_DIR / "SAMPLE_current_stock.csv"

# Trend analysis
TREND_WINDOW_WEEKS = 8          # compare the last 8 weeks with the 8 weeks before
MIN_UNITS_FOR_TREND = 50        # ignore products too small for a meaningful % change

# Basket analysis
BASKET_MIN_PRODUCT_ORDERS = 100  # products in fewer orders than this can't form reliable pairs
BASKET_MIN_PAIR_ORDERS = 30

# Forecasting / restock
FORECAST_TOP_N = 50
LEAD_TIME_WEEKS = 2
COVERAGE_WEEKS = 2
SERVICE_LEVEL_Z = 1.65           # ~95% chance of not running out (one-sided normal)

# Backtest
HOLDOUT_DAYS = 28
