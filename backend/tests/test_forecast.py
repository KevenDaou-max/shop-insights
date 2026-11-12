import numpy as np
import pandas as pd

from shop_insights.analysis.backtest import _wape
from shop_insights.analysis.forecast import (
    build_history, forecast_sales, moving_average_baseline, select_products,
)
from tests.conftest import make_clean_orders

END = pd.Timestamp("2011-06-30")


def _seasonal_orders(n_weeks: int = 70) -> pd.DataFrame:
    weeks = np.arange(n_weeks)
    rng = np.random.default_rng(0)
    series = {
        f"P{i}": (50 + 10 * i + 20 * np.sin(2 * np.pi * weeks / 13) + rng.normal(0, 3, n_weeks)).round().astype(int).tolist()
        for i in range(8)
    }
    return make_clean_orders(series, end=END.date().isoformat())


def test_forecast_shapes_and_non_negative():
    result = forecast_sales(_seasonal_orders(), end=END, horizon=3, top_n=8)
    assert result.predictions.shape == (8, 3)
    assert (result.predictions.to_numpy() >= 0).all()


def test_no_leakage_future_data_does_not_change_forecast():
    """Adding sales AFTER the cutoff must not change anything predicted AT the cutoff."""
    orders = _seasonal_orders()
    cutoff = END - pd.Timedelta(days=28)
    before = forecast_sales(orders, end=cutoff, horizon=2, top_n=8).predictions

    future = orders[orders["invoice_date"] > cutoff].assign(quantity=100_000)
    tampered = pd.concat([orders, future], ignore_index=True)
    after = forecast_sales(tampered, end=cutoff, horizon=2, top_n=8).predictions
    pd.testing.assert_frame_equal(before, after)


def test_select_products_adds_extra_codes_that_sold():
    orders = make_clean_orders({"BIG": [100] * 12, "SMALL": [5] * 12, "DEAD": [0] * 12}, end="2011-06-30")
    chosen = select_products(orders, END, top_n=1, extra=["SMALL", "DEAD", "UNKNOWN"])
    assert list(chosen) == ["BIG", "SMALL"]


def test_moving_average_baseline_and_wape():
    orders = make_clean_orders({"A": [10, 20, 30, 40]}, end="2011-06-30")
    history = build_history(orders, END, pd.Index(["A"]))
    baseline = moving_average_baseline(history, horizon=2, weeks=2)
    assert baseline.loc["A"].tolist() == [35.0, 35.0]
    actual = pd.DataFrame({1: [30.0], 2: [40.0]}, index=["A"])
    assert _wape(actual, baseline) == (5 + 5) / 70 * 100


def test_robust_std_ignores_one_spike_but_matches_std_on_normal_data():
    from shop_insights.analysis.forecast import robust_std
    spiky = np.array([[10, 12, 9, 11, 10, 5000, 11, 9, 10, 12, 10, 11]], dtype=float)
    assert robust_std(spiky)[0] < 3 < spiky.std()
    normal = np.random.default_rng(0).normal(100, 10, size=(1, 20000))
    assert abs(robust_std(normal)[0] - 10) < 0.5
