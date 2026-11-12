"""Run every analysis step on the full cleaned dataset; print results + timings.

Also writes docs/results.json so the README numbers come straight from this run.
Usage (from backend/):  python -m scripts.run_analysis
"""
import json

import pandas as pd

from shop_insights.analysis.backtest import run_backtest
from shop_insights.analysis.basket import bought_together
from shop_insights.analysis.forecast import forecast_sales, forecast_table
from shop_insights.analysis.restock import RestockSettings, read_stock_bytes, restock_plan
from shop_insights.analysis.trends import dying_products, product_trends, promote_products
from shop_insights.analysis.weekly import product_names
from shop_insights.config import FORECAST_TOP_N, REPO_ROOT, SAMPLE_STOCK_CSV
from shop_insights.data.store import load_clean_orders
from shop_insights.timing import StepTimer

pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 45)
RESULTS_FILE = REPO_ROOT / "docs" / "results.json"


def main() -> None:
    timer = StepTimer(verbose=True)
    print("Timings (full dataset):")
    with timer.step("load cleaned parquet"):
        orders = load_clean_orders()
    with timer.step("trends (promote + dying)"):
        trends = product_trends(orders)
        promote, dying = promote_products(trends), dying_products(trends)
    with timer.step("bought together (basket)"):
        bundles = bought_together(orders)
    with timer.step("forecast (train + predict)"):
        forecast = forecast_sales(orders, horizon=4)
        top_forecast = forecast_table(forecast, orders, FORECAST_TOP_N)
    with timer.step("restock (with SAMPLE stock)"):
        stock = read_stock_bytes(SAMPLE_STOCK_CSV.read_bytes(), SAMPLE_STOCK_CSV.name)
        restock = restock_plan(forecast, product_names(orders), RestockSettings(), stock)
    with timer.step("backtest (all, 2 cutoffs)"):
        backtest = run_backtest(orders)

    print("\nPROMOTE:\n", promote[["description", "recent_units", "previous_units", "reason"]].head(10))
    print("\nDYING:\n", dying[["description", "recent_units", "previous_units", "reason"]].head(10))
    print("\nBOUGHT TOGETHER:\n", bundles[["description_a", "description_b", "orders_together", "lift"]].head(10))
    print("\nFORECAST (next week):\n", top_forecast[["description", "next_week", "last_4_weeks_avg"]].head(10))
    print("\nRESTOCK (SAMPLE stock):\n",
          restock[["description", "current_stock", "recommended_quantity", "weeks_of_stock_left"]].head(10))
    print("\nBACKTEST:\n", json.dumps(backtest, indent=1))

    RESULTS_FILE.parent.mkdir(exist_ok=True)
    RESULTS_FILE.write_text(json.dumps({"timings_seconds": timer.seconds, "backtest": backtest}, indent=2))
    print(f"\nSaved {RESULTS_FILE}")


if __name__ == "__main__":
    main()
