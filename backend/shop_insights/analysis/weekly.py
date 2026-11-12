"""Product x week tables: the shared building block for trends, forecasts and restock.

Weeks are 7-day blocks counted BACKWARDS from an `end` date, so week 0 is always the
7 days ending on `end`. Anchoring on the cutoff (instead of calendar weeks) means the
most recent week is never a half-finished week, and a backtest can reuse exactly the
same code with an earlier `end` - nothing after `end` is ever read.
"""
from typing import Literal

import pandas as pd

DAYS_PER_WEEK = 7


def last_day(orders: pd.DataFrame) -> pd.Timestamp:
    return orders["invoice_date"].max().normalize()


def orders_until(orders: pd.DataFrame, end: pd.Timestamp) -> pd.DataFrame:
    """All order lines on or before the `end` day: the only data a model at `end` may see."""
    return orders[orders["invoice_date"] < pd.Timestamp(end).normalize() + pd.Timedelta(days=1)]


def weekly_matrix(
    orders: pd.DataFrame,
    end: pd.Timestamp,
    n_weeks: int,
    measure: Literal["units", "lines"] = "units",
    products: pd.Index | None = None,
) -> pd.DataFrame:
    """Rows = stock codes, columns = week offsets -(n_weeks-1) .. 0 (oldest -> newest).

    measure="units" sums quantities; measure="lines" counts order lines (~ number of orders,
    which is robust to one customer placing a single huge order).
    """
    end = pd.Timestamp(end).normalize()
    days_back = (end - orders["invoice_date"].dt.normalize()).dt.days
    in_range = (days_back >= 0) & (days_back < n_weeks * DAYS_PER_WEEK)
    window = orders.loc[in_range]
    week = -(days_back[in_range] // DAYS_PER_WEEK)

    grouped = window.groupby([window["stock_code"], week.rename("week")], observed=True)["quantity"]
    values = grouped.sum() if measure == "units" else grouped.size()
    table = values.unstack("week", fill_value=0)
    table.index = table.index.astype(str)
    table = table.reindex(columns=range(-(n_weeks - 1), 1), fill_value=0)
    if products is not None:
        table = table.reindex(products, fill_value=0)
    return table.astype("float64")


def product_names(orders: pd.DataFrame) -> pd.Series:
    """stock_code -> description (descriptions are already one-per-code after cleaning)."""
    names = orders[["stock_code", "description"]].drop_duplicates("stock_code")
    return names.set_index(names["stock_code"].astype(str))["description"].astype(str)
