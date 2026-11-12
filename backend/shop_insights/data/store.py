"""Load the cleaned demo dataset (Parquet), building it from the raw Excel file on first use."""
import pandas as pd

from shop_insights.config import CLEAN_PARQUET, PROCESSED_DIR, RAW_XLSX
from shop_insights.data.cleaning import CleaningReport, clean_orders
from shop_insights.data.loading import read_sales_path


def build_clean_parquet() -> CleaningReport:
    if not RAW_XLSX.exists():
        raise FileNotFoundError(f"{RAW_XLSX} not found. Run: python -m scripts.download_data")
    orders, report = clean_orders(read_sales_path(RAW_XLSX))
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    orders.to_parquet(CLEAN_PARQUET, index=False)
    return report


def load_clean_orders() -> pd.DataFrame:
    if not CLEAN_PARQUET.exists():
        build_clean_parquet()
    return pd.read_parquet(CLEAN_PARQUET)
