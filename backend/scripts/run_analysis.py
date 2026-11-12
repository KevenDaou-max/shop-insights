"""Run every analysis step on the full cleaned dataset and print results + timings.

Usage (from backend/):  python -m scripts.run_analysis
"""
import pandas as pd

from shop_insights.analysis.trends import dying_products, product_trends, promote_products
from shop_insights.data.store import load_clean_orders
from shop_insights.timing import StepTimer

pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 45)


def main() -> None:
    timer = StepTimer(verbose=True)
    print("Timings (full dataset):")
    with timer.step("load cleaned parquet"):
        orders = load_clean_orders()
    with timer.step("trends (promote + dying)"):
        trends = product_trends(orders)
        promote, dying = promote_products(trends), dying_products(trends)

    print("\nPROMOTE:\n", promote[["description", "recent_units", "previous_units", "reason"]].head(10))
    print("\nDYING:\n", dying[["description", "recent_units", "previous_units", "reason"]].head(10))


if __name__ == "__main__":
    main()
