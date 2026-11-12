"""Weekly sales FORECAST for the products that matter.

Model: ONE gradient-boosted tree model shared by all selected products ("global model"),
trained in a single batch. Each product's numbers are divided by its own recent level
(average of the last 8 weeks), so the model learns shapes like "sales jump before
Christmas" or "a spike is usually followed by a dip" that transfer between products that
sell 10 or 10,000 units a week. Forecasts are multiplied back by the level afterwards.

It is a "direct" multi-horizon model: the horizon h (1..H weeks ahead) is a feature, so we
predict each future week straight from today's information instead of feeding predictions
back in (errors would pile up).

Leakage: features for a training row at week t only use weeks <= t, and the target is week
t+h, which must also be <= the last week of the data we were given.
"""
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from shop_insights.analysis.weekly import DAYS_PER_WEEK, last_day, orders_until, product_names, weekly_matrix

WEEKS_PER_YEAR = 52
LEVEL_WEEKS = 8           # "normal" weekly sales = average of the last 8 weeks
MIN_HISTORY_WEEKS = 12    # need this much history before a week can be a training example
SELECTION_WEEKS = 12      # products are picked by their sales in the last 12 weeks
MAX_SCALED = 20.0         # cap scaled values so one 19,000-unit bulk order doesn't dominate training
FEATURE_NAMES = [
    "lag_1", "lag_2", "lag_3", "lag_4", "mean_4", "mean_12", "std_8", "active_weeks_8",
    "last_year_target", "last_year_change", "log_level", "horizon", "target_week_of_year",
]


@dataclass
class SalesHistory:
    """Weekly units for selected products, covering only whole weeks since the data starts."""
    units: np.ndarray            # shape (products, weeks), oldest -> newest
    products: pd.Index
    week_ends: pd.DatetimeIndex  # last day of each week column

    @property
    def n_weeks(self) -> int:
        return self.units.shape[1]


@dataclass
class Forecast:
    history: SalesHistory
    predictions: pd.DataFrame    # products x horizon (1..H), forecast units per week
    level: pd.Series             # recent average weekly units
    weekly_std: pd.Series        # recent week-to-week variation (used for safety stock)


def select_products(orders: pd.DataFrame, end: pd.Timestamp, top_n: int, extra: Iterable[str] = ()) -> pd.Index:
    """Top sellers of the last 12 weeks, plus any extra codes (e.g. from a stock file) that sold recently."""
    recent = weekly_matrix(orders, end, SELECTION_WEEKS).sum(axis=1)
    recent = recent[recent > 0].sort_values(ascending=False)
    extra_selling = recent.index.intersection(pd.Index(list(extra), dtype=str))
    return recent.index[:top_n].union(extra_selling, sort=False)


def build_history(orders: pd.DataFrame, end: pd.Timestamp, products: pd.Index) -> SalesHistory:
    end = pd.Timestamp(end).normalize()
    first = orders["invoice_date"].min().normalize()
    n_weeks = (end - first).days // DAYS_PER_WEEK   # whole weeks only: the oldest partial week is dropped
    units = weekly_matrix(orders, end, n_weeks, products=products).to_numpy()
    week_ends = pd.DatetimeIndex([end - pd.Timedelta(days=DAYS_PER_WEEK * k) for k in range(n_weeks - 1, -1, -1)])
    return SalesHistory(units=units, products=products, week_ends=week_ends)


def _week_of_year(history: SalesHistory, week_index: int) -> int:
    day = history.week_ends[0] + pd.Timedelta(days=DAYS_PER_WEEK * week_index)
    return int(day.isocalendar().week)


def _features(history: SalesHistory, t: int, h: int) -> tuple[np.ndarray, np.ndarray]:
    """Features for all products at origin week t (index), predicting week t+h. Returns (X, level)."""
    u = history.units
    level = np.maximum(u[:, t - LEVEL_WEEKS + 1:t + 1].mean(axis=1), 1.0)
    scaled = lambda values: np.minimum(values / level, MAX_SCALED)  # noqa: E731

    last_year = t + h - WEEKS_PER_YEAR
    if t - WEEKS_PER_YEAR - LEVEL_WEEKS + 1 >= 0:   # whole last-year window must exist
        last_year_level = u[:, last_year - h - LEVEL_WEEKS + 1:last_year - h + 1].mean(axis=1)
        last_year_target = scaled(u[:, last_year])
        with np.errstate(divide="ignore", invalid="ignore"):
            # How much did this product's sales change between the same two weeks last year?
            last_year_change = np.where(last_year_level > 0, np.minimum(u[:, last_year] / last_year_level, MAX_SCALED), np.nan)
    else:
        last_year_target = last_year_change = np.full(len(level), np.nan)

    recent8 = u[:, t - 7:t + 1]
    X = np.column_stack([
        scaled(u[:, t]), scaled(u[:, t - 1]), scaled(u[:, t - 2]), scaled(u[:, t - 3]),
        scaled(u[:, t - 3:t + 1].mean(axis=1)),
        scaled(u[:, t - 11:t + 1].mean(axis=1)),
        scaled(recent8.std(axis=1)),
        (recent8 > 0).mean(axis=1),
        last_year_target,
        last_year_change,
        np.log1p(level),
        np.full(len(level), h),
        np.full(len(level), _week_of_year(history, t + h)),
    ])
    return X, level


def _training_set(history: SalesHistory, horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Every (product, origin week, horizon) where the target week is inside the history."""
    X_parts, y_parts, w_parts = [], [], []
    last = history.n_weeks - 1
    # Loop over weeks (~100) and horizons (~4); each step handles ALL products at once with numpy.
    for t in range(MIN_HISTORY_WEEKS - 1, last):
        for h in range(1, min(horizon, last - t) + 1):
            X, level = _features(history, t, h)
            X_parts.append(X)
            y_parts.append(np.minimum(history.units[:, t + h] / level, MAX_SCALED))
            w_parts.append(level)   # weight by size: big sellers' errors cost more units
    return np.vstack(X_parts), np.concatenate(y_parts), np.concatenate(w_parts)


def fit_model(history: SalesHistory, horizon: int) -> HistGradientBoostingRegressor:
    X, y, weight = _training_set(history, horizon)
    model = HistGradientBoostingRegressor(
        loss="poisson",            # sales are non-negative counts; poisson loss predicts the mean, never < 0
        learning_rate=0.05,
        max_iter=300,
        min_samples_leaf=50,
        categorical_features=None,
        random_state=0,
    )
    return model.fit(X, y, sample_weight=np.sqrt(weight))


def predict(model: HistGradientBoostingRegressor, history: SalesHistory, horizon: int) -> pd.DataFrame:
    """Forecast weeks 1..horizon after the last week of the history."""
    t = history.n_weeks - 1
    columns = {}
    for h in range(1, horizon + 1):
        X, level = _features(history, t, h)
        columns[h] = model.predict(X) * level
    return pd.DataFrame(columns, index=history.products).clip(lower=0)


def forecast_sales(
    orders: pd.DataFrame,
    end: pd.Timestamp | None = None,
    horizon: int = 4,
    top_n: int = 300,
    extra_products: Iterable[str] = (),
) -> Forecast:
    """Train on data up to `end` and forecast the next `horizon` weeks for the selected products."""
    end = last_day(orders) if end is None else pd.Timestamp(end).normalize()
    orders = orders_until(orders, end)
    products = select_products(orders, end, top_n, extra_products)
    history = build_history(orders, end, products)
    if history.n_weeks < MIN_HISTORY_WEEKS + 1:
        raise ValueError(f"Need at least {MIN_HISTORY_WEEKS + 1} weeks of sales history to forecast.")

    model = fit_model(history, horizon)
    recent = history.units[:, -LEVEL_WEEKS:]
    return Forecast(
        history=history,
        predictions=predict(model, history, horizon),
        level=pd.Series(recent.mean(axis=1), index=products),
        weekly_std=pd.Series(history.units[:, -SELECTION_WEEKS:].std(axis=1, ddof=1), index=products),
    )


# --- Simple baselines (what a shop owner might do without a model) -------------------

def moving_average_baseline(history: SalesHistory, horizon: int, weeks: int = 4) -> pd.DataFrame:
    """Every future week = average of the last `weeks` weeks."""
    avg = history.units[:, -weeks:].mean(axis=1)
    return pd.DataFrame({h: avg for h in range(1, horizon + 1)}, index=history.products)


def last_year_baseline(history: SalesHistory, horizon: int) -> pd.DataFrame:
    """Every future week = the same week last year (falls back to the 4-week average if unknown)."""
    t = history.n_weeks - 1
    fallback = moving_average_baseline(history, horizon)
    columns = {}
    for h in range(1, horizon + 1):
        idx = t + h - WEEKS_PER_YEAR
        columns[h] = history.units[:, idx] if idx >= 0 else fallback[h].to_numpy()
    return pd.DataFrame(columns, index=history.products)


def forecast_table(forecast: Forecast, orders: pd.DataFrame, top_n: int, history_weeks: int = 12) -> pd.DataFrame:
    """Top products by next-week forecast, with recent history for charts."""
    names = product_names(orders)
    preds = forecast.predictions
    top = preds[1].sort_values(ascending=False).index[:top_n]
    recent = pd.DataFrame(
        forecast.history.units[:, -history_weeks:], index=forecast.history.products,
        columns=[d.date().isoformat() for d in forecast.history.week_ends[-history_weeks:]],
    )
    return pd.DataFrame({
        "description": names.reindex(top),
        "next_week": preds.loc[top, 1].round(0),
        "last_4_weeks_avg": recent.loc[top].iloc[:, -4:].mean(axis=1).round(0),
        "forecast": preds.loc[top].round(0).to_numpy().tolist(),
        "history": recent.loc[top].to_numpy().tolist(),
    }, index=top).rename_axis("stock_code")
