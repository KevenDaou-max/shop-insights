"""RESTOCK list: which products to reorder and how many units.

The sales data has no inventory, so we plan from forecast demand:

  protection window = lead time + coverage weeks
      (stock ordered today must last until the NEXT order arrives: wait for this delivery,
       then use it until the next one lands)
  expected demand   = forecast units summed over the protection window
  safety stock      = z * weekly_std * sqrt(window weeks)
      weekly_std: how much the product's weekly sales jump around (last 12 weeks), measured
                  robustly (1.4826 x median absolute deviation) so one giant wholesale order
                  doesn't create a giant safety stock.
      sqrt: random ups and downs in different weeks partly cancel out, so uncertainty over
            4 weeks is sqrt(4) = 2x one week's, not 4x.
      z = 1.65: if demand is roughly normal, ~95% chance of not running out.
  needed stock      = expected demand + safety stock
  units to order    = max(0, needed stock - current stock)    (only if a stock file is given)
"""
import io
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from shop_insights.analysis.forecast import Forecast
from shop_insights.config import COVERAGE_WEEKS, LEAD_TIME_WEEKS, SERVICE_LEVEL_Z
from shop_insights.data.loading import SalesFileError, normalize_column_name

STOCK_CODE_ALIASES = {"stockcode", "sku", "productid", "productcode"}
STOCK_LEVEL_ALIASES = {"currentstock", "stock", "onhand", "quantity", "qty"}


@dataclass(frozen=True)
class RestockSettings:
    lead_time_weeks: int = LEAD_TIME_WEEKS
    coverage_weeks: int = COVERAGE_WEEKS
    service_z: float = SERVICE_LEVEL_Z

    @property
    def window_weeks(self) -> int:
        return self.lead_time_weeks + self.coverage_weeks


def read_stock_bytes(content: bytes, filename: str) -> pd.Series:
    """Parse a current-stock CSV (StockCode, CurrentStock) into code -> units on hand."""
    try:
        raw = pd.read_csv(io.BytesIO(content), dtype=str, encoding="latin-1")
    except Exception as exc:
        raise SalesFileError(f"Could not read stock file '{filename}': {exc}") from exc
    columns = {normalize_column_name(c): c for c in raw.columns}
    code_col = next((columns[a] for a in STOCK_CODE_ALIASES if a in columns), None)
    stock_col = next((columns[a] for a in STOCK_LEVEL_ALIASES if a in columns), None)
    if code_col is None or stock_col is None:
        raise SalesFileError("Stock file needs two columns: StockCode and CurrentStock.")

    stock = pd.to_numeric(raw[stock_col], errors="coerce")
    bad = stock.isna() | (stock < 0)
    if bad.any():
        raise SalesFileError(f"Stock file has {int(bad.sum())} row(s) where CurrentStock is not a number >= 0.")
    codes = raw[code_col].astype(str).str.strip().str.upper()
    return stock.groupby(codes).sum().rename("current_stock")


def needed_stock(forecast: Forecast, settings: RestockSettings) -> pd.DataFrame:
    """Expected demand + safety stock over the protection window, per product."""
    weeks = settings.window_weeks
    missing = [h for h in range(1, weeks + 1) if h not in forecast.predictions.columns]
    if missing:
        raise ValueError(f"Forecast horizon too short for a {weeks}-week window.")
    demand = forecast.predictions[list(range(1, weeks + 1))].sum(axis=1)
    safety = settings.service_z * forecast.weekly_std.fillna(0) * math.sqrt(weeks)
    return pd.DataFrame({
        "expected_weekly_demand": demand / weeks,
        "expected_demand": demand,
        "safety_stock": safety,
        "needed_stock": np.ceil(demand + safety),
    })


def _weeks(value: pd.Series) -> pd.Series:
    return value.round(1).astype(str) + " weeks"


def restock_plan(
    forecast: Forecast,
    names: pd.Series,
    settings: RestockSettings = RestockSettings(),
    current_stock: pd.Series | None = None,
) -> pd.DataFrame:
    """Rows: product, recommended quantity, weekly demand, weeks of stock left, reason.

    Without a stock file: recommended_quantity = the stock level to hold.
    With a stock file: only products that need reordering, most urgent first.
    """
    plan = needed_stock(forecast, settings)
    plan.insert(0, "description", names.reindex(plan.index))
    plan = plan[plan["expected_demand"] > 0]
    window = f"{settings.lead_time_weeks}+{settings.coverage_weeks} weeks"

    if current_stock is None:
        plan["recommended_quantity"] = plan["needed_stock"]
        plan["weeks_of_stock_left"] = np.nan
        plan["reason"] = (
            "Hold this much: ~" + plan["expected_weekly_demand"].round(0).astype(int).astype(str)
            + "/week for " + window + " + " + plan["safety_stock"].round(0).astype(int).astype(str)
            + " safety units"
        )
        plan = plan.sort_values("expected_demand", ascending=False)
    else:
        # Products missing from the stock file are skipped: we can't know if they need ordering.
        plan = plan[plan.index.isin(current_stock.index)].copy()
        plan["current_stock"] = current_stock.reindex(plan.index)
        plan["recommended_quantity"] = (plan["needed_stock"] - plan["current_stock"]).clip(lower=0)
        plan["weeks_of_stock_left"] = plan["current_stock"] / plan["expected_weekly_demand"]
        plan = plan[plan["recommended_quantity"] > 0]
        arrives_too_late = plan["weeks_of_stock_left"] < settings.lead_time_weeks
        plan["reason"] = np.where(
            arrives_too_late,
            "URGENT: stock lasts ~" + _weeks(plan["weeks_of_stock_left"])
            + " but a new delivery takes " + str(settings.lead_time_weeks) + " weeks",
            "Stock lasts ~" + _weeks(plan["weeks_of_stock_left"]) + "; need " + window + " + safety stock",
        )
        plan = plan.sort_values("weeks_of_stock_left")
    plan.index.name = "stock_code"
    return plan.round({"expected_weekly_demand": 1, "expected_demand": 1, "safety_stock": 1, "weeks_of_stock_left": 1})
