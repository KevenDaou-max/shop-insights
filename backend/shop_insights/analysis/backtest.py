"""PROOF it works: hide the last month, recommend from earlier data only, then score.

Rule against leakage: every recommender below receives `orders_until(orders, cutoff)` and
nothing else. The hidden weeks after the cutoff are only used to SCORE. Each recommendation
is compared with a simple baseline a shop owner could do without any model.
"""
from typing import Any

import numpy as np
import pandas as pd

from shop_insights.analysis.basket import bought_together
from shop_insights.analysis.forecast import (
    Forecast, forecast_sales, last_year_baseline, moving_average_baseline,
)
from shop_insights.analysis.restock import RestockSettings, needed_stock
from shop_insights.analysis.trends import dying_products, product_trends, promote_products
from shop_insights.analysis.weekly import DAYS_PER_WEEK, last_day, orders_until, weekly_matrix
from shop_insights.config import HOLDOUT_DAYS, LEAD_TIME_WEEKS, MIN_UNITS_FOR_TREND, TREND_WINDOW_WEEKS

LIST_SIZE = 20


def holdout_cutoff(orders: pd.DataFrame, holdout_days: int = HOLDOUT_DAYS) -> pd.Timestamp:
    """Last day the models may see; the `holdout_days` after it are hidden."""
    return last_day(orders) - pd.Timedelta(days=holdout_days)


def _actual_units(orders: pd.DataFrame, cutoff: pd.Timestamp, weeks: int, products: pd.Index) -> pd.DataFrame:
    """Real weekly units in the hidden weeks, columns 1..weeks."""
    end = cutoff + pd.Timedelta(days=weeks * DAYS_PER_WEEK)
    actual = weekly_matrix(orders, end, weeks, products=products)
    actual.columns = range(1, weeks + 1)
    return actual


def _wape(actual: pd.DataFrame, predicted: pd.DataFrame) -> float:
    """Weighted absolute % error: total units we were off by / total units sold. Lower is better."""
    return float(np.abs(actual.to_numpy() - predicted.to_numpy()).sum() / actual.to_numpy().sum() * 100)


def _bias(actual: pd.DataFrame, predicted: pd.DataFrame) -> float:
    """+ means we predicted too much in total, - too little."""
    return float((predicted.to_numpy().sum() - actual.to_numpy().sum()) / actual.to_numpy().sum() * 100)


# --- Forecast -------------------------------------------------------------------------

def score_forecast(forecast: Forecast, actual: pd.DataFrame) -> dict[str, Any]:
    horizon = actual.shape[1]
    candidates = {
        "model": forecast.predictions[list(range(1, horizon + 1))],
        "baseline_last_4_weeks_avg": moving_average_baseline(forecast.history, horizon),
        "baseline_same_weeks_last_year": last_year_baseline(forecast.history, horizon),
    }
    abs_err = {name: (pred - actual).abs().sum(axis=1) for name, pred in candidates.items()}
    return {
        "products": len(actual),
        "weeks": horizon,
        "actual_units": int(actual.to_numpy().sum()),
        "wape_pct": {name: round(_wape(actual, pred), 1) for name, pred in candidates.items()},
        "bias_pct": {name: round(_bias(actual, pred), 1) for name, pred in candidates.items()},
        "model_beats_4_week_avg_on_pct_of_products": round(
            float((abs_err["model"] < abs_err["baseline_last_4_weeks_avg"]).mean() * 100), 1
        ),
    }


def backtest_forecast(orders: pd.DataFrame, cutoff: pd.Timestamp, weeks: int = 4) -> tuple[Forecast, dict[str, Any]]:
    forecast = forecast_sales(orders_until(orders, cutoff), end=cutoff, horizon=weeks)
    actual = _actual_units(orders, cutoff, weeks, forecast.history.products)
    return forecast, score_forecast(forecast, actual)


# --- Promote / dying ------------------------------------------------------------------

def _share_change(orders: pd.DataFrame, cutoff: pd.Timestamp, weeks: int) -> pd.DataFrame:
    """Each product's units and share of all units: `weeks` before the cutoff vs the hidden weeks.

    Using SHARE of the shop's sales removes the season: in Nov-Dec almost everything sells
    more, so "sales went up" would be true for any list. "Gained share" means the product did
    better than the shop as a whole.
    """
    table = weekly_matrix(orders, cutoff + pd.Timedelta(days=weeks * DAYS_PER_WEEK), 2 * weeks)
    before = table[table.columns[:weeks]].sum(axis=1)
    after = table[table.columns[weeks:]].sum(axis=1)
    return pd.DataFrame({
        "before": before,
        "after": after,
        "share_change": after / after.sum() - before / before.sum(),
        "growth_pct": (after - before) / before.replace(0, np.nan) * 100,
    })


def _median(values: pd.Series) -> float | None:
    values = values.dropna()
    return round(float(values.median()), 1) if len(values) else None


def _score_promote(codes: pd.Index, outcome: pd.DataFrame) -> dict[str, Any]:
    """hit = the product gained share of the shop's sales in the hidden month."""
    rows = outcome.reindex(codes).fillna({"before": 0, "after": 0, "share_change": 0})
    return {
        "products": len(rows),
        "hit_rate_pct": round(float((rows["share_change"] > 0).mean() * 100), 1) if len(rows) else None,
        "median_growth_pct": _median(rows["growth_pct"]),
        "hidden_month_units": int(rows["after"].sum()),
    }


def _score_dying(codes: pd.Index, outcome: pd.DataFrame, trends: pd.DataFrame, weeks: int) -> dict[str, Any]:
    """hit = in the hidden month the product sold less than half of its earlier normal month.

    "Earlier normal" = the trend's `previous_units` window (before the recent window), scaled
    to `weeks`. This works for products already at zero, unlike "lost share".
    """
    after = outcome["after"].reindex(codes, fill_value=0)
    normal_month = trends["previous_units"].reindex(codes) * weeks / TREND_WINDOW_WEEKS
    return {
        "products": len(codes),
        "hit_rate_pct": round(float((after < 0.5 * normal_month).mean() * 100), 1) if len(codes) else None,
        "hidden_month_units": int(after.sum()),
        "earlier_normal_month_units": int(normal_month.sum()),
    }


def backtest_trends(orders: pd.DataFrame, cutoff: pd.Timestamp, weeks: int = 4) -> dict[str, Any]:
    seen = orders_until(orders, cutoff)
    trends = product_trends(seen, end=cutoff)
    last_month = weekly_matrix(seen, cutoff, weeks).sum(axis=1)
    outcome = _share_change(orders, cutoff, weeks)

    # Baseline promote: last month's best sellers. Baseline dying: last month's worst sellers
    # among products that were selling before (same "was selling" filter as the model).
    was_selling = trends.index[trends["previous_units"] >= MIN_UNITS_FOR_TREND]
    return {
        "promote": {
            "model": _score_promote(promote_products(trends, LIST_SIZE).index, outcome),
            "baseline_last_month_best_sellers": _score_promote(last_month.nlargest(LIST_SIZE).index, outcome),
            "explanation": "hit = product gained share of the shop's sales in the hidden month",
        },
        "dying": {
            "model": _score_dying(dying_products(trends, LIST_SIZE).index, outcome, trends, weeks),
            "baseline_last_month_worst_sellers": _score_dying(
                last_month.reindex(was_selling, fill_value=0).nsmallest(LIST_SIZE).index, outcome, trends, weeks),
            "explanation": "hit = product sold less than half of its earlier normal month in the hidden month",
        },
        "shop_growth_pct": round(float(outcome["after"].sum() / outcome["before"].sum() * 100 - 100), 1),
    }


# --- Bought together ------------------------------------------------------------------

def _pair_outcome(pairs: pd.DataFrame, hidden: pd.DataFrame) -> dict[str, Any]:
    """How the pairs behaved in the hidden month: confidence and lift measured on new orders only."""
    baskets = hidden[["invoice", "stock_code"]].drop_duplicates().astype(str)
    n_orders = baskets["invoice"].nunique()
    orders_with = baskets.groupby("stock_code")["invoice"].agg(set)
    lifts, confidences = [], []
    for a, b in pairs[["product_a", "product_b"]].itertuples(index=False):  # only ~20 pairs
        set_a, set_b = orders_with.get(a, set()), orders_with.get(b, set())
        together = len(set_a & set_b)
        if set_a and set_b:
            lifts.append(together * n_orders / (len(set_a) * len(set_b)))
            confidences.append(together / min(len(set_a), len(set_b)))
    return {
        "pairs": len(pairs),
        "pairs_seen_in_hidden_month": len(lifts),
        "pct_still_bought_together": round(float(np.mean([l > 1 for l in lifts]) * 100), 1) if lifts else None,
        "median_lift": round(float(np.median(lifts)), 1) if lifts else None,
        "median_confidence_pct": round(float(np.median(confidences)) * 100, 1) if confidences else None,
    }


def backtest_bundles(orders: pd.DataFrame, cutoff: pd.Timestamp) -> dict[str, Any]:
    seen = orders_until(orders, cutoff)
    hidden = orders[orders["invoice_date"] >= cutoff + pd.Timedelta(days=1)]
    model_pairs = bought_together(seen, end=cutoff, top_n=LIST_SIZE)
    # Baseline: the most frequent pairs (raw count), which mostly pairs best sellers with each other.
    common = bought_together(seen, end=cutoff, top_n=100_000).nlargest(LIST_SIZE, "orders_together")
    return {
        "model_top_lift_pairs": _pair_outcome(model_pairs, hidden),
        "baseline_most_common_pairs": _pair_outcome(common, hidden),
        "explanation": "lift > 1 in the hidden month = the pair really was still bought together",
    }


# --- Restock --------------------------------------------------------------------------

OVERSTOCK_RATIO = 1.5   # holding more than 1.5x what actually sold counts as overstocked


def _score_stock_levels(stock: pd.Series, actual: pd.Series) -> dict[str, Any]:
    """If the shop had held `stock` units at the cutoff, how did that compare with real demand?"""
    short = (actual - stock).clip(lower=0)
    leftover = (stock - actual).clip(lower=0)
    return {
        "ran_out_products": int((actual > stock).sum()),
        "ran_out_pct": round(float((actual > stock).mean() * 100), 1),
        "overstocked_products": int((stock > OVERSTOCK_RATIO * actual).sum()),
        "units_short": int(short.sum()),
        "units_left_over": int(leftover.sum()),
        "fill_rate_pct": round(float((1 - short.sum() / actual.sum()) * 100), 1),
        "units_held": int(stock.sum()),
    }


def backtest_restock(orders: pd.DataFrame, cutoff: pd.Timestamp, forecast: Forecast, weeks: int) -> dict[str, Any]:
    """Would the stock levels recommended at the cutoff have covered the hidden weeks' demand?

    Simplification: the shop starts the hidden period holding exactly the recommended level
    (lead time + coverage = the hidden weeks), with no other deliveries in between.
    """
    settings = RestockSettings(lead_time_weeks=LEAD_TIME_WEEKS, coverage_weeks=weeks - LEAD_TIME_WEEKS)
    plan = needed_stock(forecast, settings)
    actual = _actual_units(orders, cutoff, weeks, forecast.history.products).sum(axis=1)
    last_month = pd.Series(forecast.history.units[:, -weeks:].sum(axis=1), index=forecast.history.products)
    return {
        "products": len(actual),
        "actual_units": int(actual.sum()),
        "settings": {"lead_time_weeks": settings.lead_time_weeks, "coverage_weeks": settings.coverage_weeks,
                     "service_z": settings.service_z},
        "model_with_safety_stock": _score_stock_levels(plan["needed_stock"], actual),
        "model_forecast_only": _score_stock_levels(np.ceil(plan["expected_demand"]), actual),
        "baseline_same_as_last_month": _score_stock_levels(last_month, actual),
        "explanation": "stock held = recommended level at the cutoff; compared with real sales in the hidden weeks",
    }


# --- Everything -----------------------------------------------------------------------

MIN_WEEKS_FOR_BACKTEST = 30   # forecasting needs history before the cutoff, plus the hidden month


def run_backtest(orders: pd.DataFrame, holdout_days: int = HOLDOUT_DAYS) -> dict[str, Any]:
    """Hidden-month backtest of every recommender, plus the forecast on the month before it.

    The extra "validation month" shows whether a forecast result is stable or just luck.
    """
    span_weeks = (last_day(orders) - orders["invoice_date"].min().normalize()).days // DAYS_PER_WEEK
    if span_weeks < MIN_WEEKS_FOR_BACKTEST:
        return {"available": False, "reason": f"Needs at least {MIN_WEEKS_FOR_BACKTEST} weeks of data."}

    cutoff = holdout_cutoff(orders, holdout_days)
    weeks = holdout_days // DAYS_PER_WEEK
    forecast, forecast_score = backtest_forecast(orders, cutoff, weeks)
    _, validation_score = backtest_forecast(orders, cutoff - pd.Timedelta(days=holdout_days), weeks)
    return {
        "available": True,
        "cutoff": cutoff.date().isoformat(),
        "hidden_until": last_day(orders).date().isoformat(),
        "forecast": forecast_score,
        "forecast_previous_month": validation_score,
        "trends": backtest_trends(orders, cutoff, weeks),
        "bundles": backtest_bundles(orders, cutoff),
        "restock": backtest_restock(orders, cutoff, forecast, weeks),
    }
