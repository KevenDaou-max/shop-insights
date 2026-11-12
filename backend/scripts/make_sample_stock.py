"""Generate a SAMPLE current-stock CSV for testing the restock upload.

The numbers are MADE UP (the real dataset has no inventory): for the 60 best sellers of the
last 12 weeks, stock = average weekly sales x a random 0-6 weeks of cover (fixed seed).
Usage (from backend/):  python -m scripts.make_sample_stock
"""
import numpy as np

from shop_insights.analysis.weekly import last_day, weekly_matrix
from shop_insights.config import SAMPLE_STOCK_CSV
from shop_insights.data.store import load_clean_orders

N_PRODUCTS = 60
MAX_WEEKS_OF_COVER = 6

if __name__ == "__main__":
    orders = load_clean_orders()
    weekly = weekly_matrix(orders, last_day(orders), 12).mean(axis=1).nlargest(N_PRODUCTS)
    weeks_of_cover = np.random.default_rng(42).uniform(0, MAX_WEEKS_OF_COVER, N_PRODUCTS)
    stock = (weekly * weeks_of_cover).round().astype(int)
    SAMPLE_STOCK_CSV.parent.mkdir(parents=True, exist_ok=True)
    stock.rename_axis("StockCode").rename("CurrentStock").to_csv(SAMPLE_STOCK_CSV)
    print(f"Wrote SAMPLE stock for {N_PRODUCTS} products to {SAMPLE_STOCK_CSV}")
