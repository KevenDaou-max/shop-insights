"""Clean the raw dataset, save it as Parquet and print a short summary.

Usage (from backend/):  python -m scripts.prepare_data
"""
import json
import time

from shop_insights.config import CLEAN_PARQUET
from shop_insights.data.store import build_clean_parquet, load_clean_orders
from shop_insights.data.summary import summarize_orders

if __name__ == "__main__":
    start = time.perf_counter()
    report = build_clean_parquet()
    print(f"Read + clean + save: {time.perf_counter() - start:.1f} s")
    print(f"Rows in: {report.rows_in:,}")
    for step, removed in report.removed.items():
        print(f"  - removed {removed:>7,}  {step}")
    print(f"Rows out: {report.rows_out:,}  ->  {CLEAN_PARQUET}")

    start = time.perf_counter()
    orders = load_clean_orders()
    print(f"Load cleaned Parquet: {time.perf_counter() - start:.2f} s, "
          f"{orders.memory_usage(deep=True).sum() / 1e6:.0f} MB in memory")
    print(json.dumps(summarize_orders(orders), indent=2))
