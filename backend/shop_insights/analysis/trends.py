"""Which products to PROMOTE (growing) and which are DYING (falling or barely selling).

Idea: compare each product's last `window` weeks with the `window` weeks before that.
- Unit growth alone is fooled by one customer placing one huge order, so a product must
  also be ordered MORE OFTEN (more order lines) to count as growing.
- Small products jump +300% from 2 to 8 units; requiring `min_units` filters that noise.
- We also show what happened in the same weeks LAST year, so the owner can tell a real
  trend from normal seasonality (e.g. Christmas items always rise in autumn).
"""
import numpy as np
import pandas as pd

from shop_insights.analysis.weekly import last_day, product_names, weekly_matrix
from shop_insights.config import MIN_UNITS_FOR_TREND, TREND_WINDOW_WEEKS

WEEKS_PER_YEAR = 52
PROMOTE_MIN_GROWTH_PCT = 25.0
DYING_MAX_GROWTH_PCT = -50.0
BARELY_SELLING_MAX_LINES = 2   # ordered at most twice in the recent window
MIN_RECENT_LINES_TO_PROMOTE = 5


def _pct_change(new: pd.Series, old: pd.Series) -> pd.Series:
    return ((new - old) / old.replace(0, np.nan) * 100).round(1)


def _relative_slope(units: pd.DataFrame) -> pd.Series:
    """Least-squares slope of weekly units, as % of the product's average week.

    Done as one matrix operation for all products instead of fitting a model per product.
    """
    weeks = np.arange(units.shape[1], dtype=float)
    centered_weeks = weeks - weeks.mean()
    values = units.to_numpy()
    slope = (values - values.mean(axis=1, keepdims=True)) @ centered_weeks / (centered_weeks**2).sum()
    mean = values.mean(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return pd.Series(np.where(mean > 0, slope / mean * 100, 0.0), index=units.index).round(1)


def product_trends(
    orders: pd.DataFrame,
    end: pd.Timestamp | None = None,
    window: int = TREND_WINDOW_WEEKS,
) -> pd.DataFrame:
    """One row per product with recent vs previous sales and growth figures."""
    end = last_day(orders) if end is None else pd.Timestamp(end)
    n_weeks = WEEKS_PER_YEAR + 2 * window
    units = weekly_matrix(orders, end, n_weeks, "units")
    lines = weekly_matrix(orders, end, 2 * window, "lines", products=units.index)

    recent_cols, previous_cols = units.columns[-window:], units.columns[-2 * window:-window]
    last_year = units.columns[-WEEKS_PER_YEAR - window:-WEEKS_PER_YEAR]
    last_year_before = units.columns[-WEEKS_PER_YEAR - 2 * window:-WEEKS_PER_YEAR - window]

    trends = pd.DataFrame({
        "recent_units": units[recent_cols].sum(axis=1),
        "previous_units": units[previous_cols].sum(axis=1),
        "recent_lines": lines[lines.columns[-window:]].sum(axis=1),
        "previous_lines": lines[lines.columns[:window]].sum(axis=1),
        "weekly_trend_pct": _relative_slope(units[units.columns[-2 * window:]]),
    })
    trends["growth_pct"] = _pct_change(trends["recent_units"], trends["previous_units"])
    trends["order_growth_pct"] = _pct_change(trends["recent_lines"], trends["previous_lines"])
    trends["last_year_growth_pct"] = _pct_change(
        units[last_year].sum(axis=1), units[last_year_before].sum(axis=1)
    )
    trends.insert(0, "description", product_names(orders).reindex(trends.index))
    trends.index.name = "stock_code"
    return trends


def _seasonal_note(trends: pd.DataFrame, rising: bool) -> pd.Series:
    same_direction = trends["last_year_growth_pct"] > 0 if rising else trends["last_year_growth_pct"] < 0
    return np.where(same_direction, " (same pattern last year: likely seasonal)", "")


def promote_products(trends: pd.DataFrame, top_n: int = 20, min_units: int = MIN_UNITS_FOR_TREND) -> pd.DataFrame:
    """Growing products, ranked by extra units sold (a +40% on a big seller beats +300% on a tiny one)."""
    growing = trends[
        (trends["recent_units"] >= min_units)
        & (trends["recent_lines"] >= MIN_RECENT_LINES_TO_PROMOTE)
        & ((trends["growth_pct"] >= PROMOTE_MIN_GROWTH_PCT) | trends["previous_units"].eq(0))
        & (trends["recent_lines"] > trends["previous_lines"])
        & (trends["weekly_trend_pct"] > 0)
    ].copy()
    growing["unit_gain"] = growing["recent_units"] - growing["previous_units"]
    growing["reason"] = (
        np.where(
            growing["previous_units"].eq(0),
            "New product selling well",
            "Units +" + growing["growth_pct"].astype(str) + "%, orders +"
            + growing["order_growth_pct"].fillna(0).astype(str) + "% vs previous period",
        )
        + _seasonal_note(growing, rising=True)
    )
    return growing.sort_values("unit_gain", ascending=False).head(top_n)


def dying_products(trends: pd.DataFrame, top_n: int = 20, min_units: int = MIN_UNITS_FOR_TREND) -> pd.DataFrame:
    """Products that used to sell but dropped hard or almost stopped, ranked by units lost."""
    was_selling = trends["previous_units"] >= min_units
    dropped = trends["growth_pct"] <= DYING_MAX_GROWTH_PCT
    barely = trends["recent_lines"] <= BARELY_SELLING_MAX_LINES
    dying = trends[was_selling & (dropped | barely)].copy()
    dying["unit_loss"] = dying["previous_units"] - dying["recent_units"]
    dying["reason"] = (
        np.select(
            [dying["recent_lines"].eq(0), dying["recent_lines"] <= BARELY_SELLING_MAX_LINES],
            [
                "No orders in the recent period",
                "Barely selling: only " + dying["recent_lines"].astype(int).astype(str) + " order(s) recently",
            ],
            default="Units " + dying["growth_pct"].astype(str) + "% vs previous period",
        )
        + _seasonal_note(dying, rising=False)
    )
    return dying.sort_values("unit_loss", ascending=False).head(top_n)
