"""Run every analysis on a cleaned orders table and return one JSON-ready dict.

This is the only function the API calls for analysis, so the web layer stays thin and the
whole pipeline can be run (and timed) without a server.
"""
import json
from typing import Any

import pandas as pd

from shop_insights.analysis.backtest import run_backtest
from shop_insights.analysis.basket import bought_together
from shop_insights.analysis.forecast import forecast_sales, forecast_table
from shop_insights.analysis.restock import RestockSettings, restock_plan
from shop_insights.analysis.trends import dying_products, product_trends, promote_products
from shop_insights.analysis.weekly import product_names
from shop_insights.config import FORECAST_TOP_N
from shop_insights.data.summary import summarize_orders
from shop_insights.timing import StepTimer

MIN_FORECAST_HORIZON = 4  # the dashboard always shows 4 weeks ahead


def to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame -> list of dicts with plain Python types (NaN -> null)."""
    return json.loads(df.reset_index().to_json(orient="records"))


def analyze(
    orders: pd.DataFrame,
    settings: RestockSettings = RestockSettings(),
    current_stock: pd.Series | None = None,
    include_backtest: bool = True,
) -> dict[str, Any]:
    timer = StepTimer()
    names = product_names(orders)

    with timer.step("trends"):
        trends = product_trends(orders)
        promote, dying = promote_products(trends), dying_products(trends)
    with timer.step("bought_together"):
        bundles = bought_together(orders)
    with timer.step("forecast"):
        stock_codes = current_stock.index if current_stock is not None else []
        forecast = forecast_sales(
            orders, horizon=max(MIN_FORECAST_HORIZON, settings.window_weeks), extra_products=stock_codes
        )
        top_forecast = forecast_table(forecast, orders, FORECAST_TOP_N)
    with timer.step("restock"):
        restock = restock_plan(forecast, names, settings, current_stock)
    backtest = {"available": False, "reason": "Skipped."}
    if include_backtest:
        with timer.step("backtest"):
            backtest = run_backtest(orders)

    week_ends = forecast.history.week_ends
    return {
        "data": summarize_orders(orders),
        "settings": {
            "lead_time_weeks": settings.lead_time_weeks,
            "coverage_weeks": settings.coverage_weeks,
            "service_z": settings.service_z,
            "max_safety_weeks": settings.max_safety_weeks,
            "stock_file": current_stock is not None,
        },
        "promote": to_records(promote),
        "dying": to_records(dying),
        "bundles": to_records(bundles),
        "forecast": {
            "history_weeks": [d.date().isoformat() for d in week_ends[-12:]],
            "forecast_weeks": [
                (week_ends[-1] + pd.Timedelta(weeks=h)).date().isoformat() for h in range(1, MIN_FORECAST_HORIZON + 1)
            ],
            "products": to_records(top_forecast.assign(forecast=top_forecast["forecast"].map(lambda f: f[:MIN_FORECAST_HORIZON]))),
        },
        "restock": to_records(restock.drop(columns=["needed_stock", "expected_demand"])),
        "backtest": backtest,
        "timings_seconds": timer.seconds,
    }
