import math

import numpy as np
import pandas as pd
import pytest

from shop_insights.analysis.backtest import _score_stock_levels
from shop_insights.analysis.forecast import Forecast, SalesHistory
from shop_insights.analysis.restock import RestockSettings, read_stock_bytes, restock_plan
from shop_insights.data.loading import SalesFileError

PRODUCTS = pd.Index(["STEADY", "LOW", "PLENTY"])
NAMES = pd.Series({"STEADY": "Steady seller", "LOW": "Low stock", "PLENTY": "Plenty in stock"})


def _forecast(weekly: float = 10.0, std: float = 2.0) -> Forecast:
    history = SalesHistory(np.zeros((3, 1)), PRODUCTS, pd.DatetimeIndex(["2011-06-30"]))
    predictions = pd.DataFrame({h: [weekly] * 3 for h in range(1, 5)}, index=PRODUCTS)
    return Forecast(history, predictions, pd.Series(weekly, index=PRODUCTS), pd.Series(std, index=PRODUCTS))


def test_needed_stock_is_demand_plus_safety_stock():
    plan = restock_plan(_forecast(), NAMES, RestockSettings(2, 2, 1.65))
    expected = math.ceil(4 * 10 + 1.65 * 2 * math.sqrt(4))   # 40 demand + 6.6 safety
    assert (plan["recommended_quantity"] == expected).all()
    assert plan["weeks_of_stock_left"].isna().all()


def test_with_stock_file_orders_only_what_is_missing_most_urgent_first():
    stock = pd.Series({"STEADY": 30, "LOW": 5, "PLENTY": 500})
    plan = restock_plan(_forecast(), NAMES, RestockSettings(2, 2, 1.65), stock)
    assert plan.index.tolist() == ["LOW", "STEADY"]           # PLENTY needs nothing
    assert plan.loc["LOW", "recommended_quantity"] == 47 - 5
    assert plan.loc["LOW", "weeks_of_stock_left"] == 0.5
    assert plan.loc["LOW", "reason"].startswith("URGENT")
    assert not plan.loc["STEADY", "reason"].startswith("URGENT")  # 3 weeks left > 2-week lead time


def test_longer_window_needs_more_stock():
    short = restock_plan(_forecast(), NAMES, RestockSettings(1, 1))
    long = restock_plan(_forecast(), NAMES, RestockSettings(2, 2))
    assert (long["recommended_quantity"] > short["recommended_quantity"]).all()


def test_read_stock_file_and_errors():
    stock = read_stock_bytes(b"StockCode,CurrentStock\n85123a,10\n22423,0\n", "s.csv")
    assert stock.to_dict() == {"22423": 0, "85123A": 10}
    with pytest.raises(SalesFileError, match="StockCode and CurrentStock"):
        read_stock_bytes(b"Code,Amount\nA,1\n", "s.csv")
    with pytest.raises(SalesFileError, match="not a number"):
        read_stock_bytes(b"StockCode,CurrentStock\nA,-3\n", "s.csv")


def test_score_stock_levels():
    score = _score_stock_levels(pd.Series([10.0, 50.0]), pd.Series([20.0, 20.0]))
    assert score["ran_out_products"] == 1 and score["units_short"] == 10
    assert score["overstocked_products"] == 1 and score["units_left_over"] == 30
    assert score["fill_rate_pct"] == 75.0


def test_safety_stock_is_capped_at_weeks_of_demand():
    # ~10/week but very jumpy history: uncapped safety = 1.65 * 100 * 2 = 330 units.
    plan = restock_plan(_forecast(weekly=10, std=100), NAMES, RestockSettings(2, 2, 1.65, max_safety_weeks=2))
    assert (plan["safety_stock"] == 20).all()             # 2 weeks x 10/week
    assert (plan["recommended_quantity"] == 40 + 20).all()
    assert plan["safety_capped"].all()
    assert "capped at 2 weeks" in plan["reason"].iloc[0]


def test_cap_does_not_touch_normal_products():
    plan = restock_plan(_forecast(weekly=10, std=2), NAMES, RestockSettings(2, 2, 1.65, max_safety_weeks=2))
    assert not plan["safety_capped"].any()
