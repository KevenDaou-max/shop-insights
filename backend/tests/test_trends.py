import pandas as pd

from shop_insights.analysis.trends import dying_products, product_trends, promote_products
from shop_insights.analysis.weekly import weekly_matrix
from tests.conftest import make_clean_orders

FLAT = [30] * 16


def _orders():
    return make_clean_orders({
        "GROW": [20] * 8 + [40, 45, 50, 55, 60, 65, 70, 75],
        "DROP": [60] * 8 + [20, 15, 10, 10, 5, 5, 5, 5],
        "FLAT": FLAT,
        "TINY": [1] * 8 + [3] * 8,   # +200% but far too small to matter
    })


def test_weekly_matrix_counts_back_from_end():
    orders = make_clean_orders({"A": [1, 2, 3]})
    table = weekly_matrix(orders, pd.Timestamp("2011-06-30"), 4)
    assert list(table.columns) == [-3, -2, -1, 0]
    assert table.loc["A"].tolist() == [0, 1, 2, 3]


def test_weekly_matrix_never_reads_after_end():
    orders = make_clean_orders({"A": [5, 7]})  # 7 units fall on 2011-06-30
    table = weekly_matrix(orders, pd.Timestamp("2011-06-29"), 2)
    assert table.to_numpy().sum() == 5


def test_promote_and_dying_find_the_right_products():
    trends = product_trends(_orders(), window=8)
    assert promote_products(trends, min_units=50).index.tolist() == ["GROW"]
    assert dying_products(trends, min_units=50).index.tolist() == ["DROP"]


def test_growth_pct_is_recent_vs_previous():
    trends = product_trends(_orders(), window=8)
    assert trends.loc["FLAT", "growth_pct"] == 0
    assert trends.loc["GROW", "growth_pct"] == round((460 - 160) / 160 * 100, 1)


def test_one_huge_order_is_not_a_trend():
    orders = make_clean_orders({"BULK": [30] * 15 + [3000]}, lines_per_week=1)
    trends = product_trends(orders, window=8)
    assert promote_products(trends, min_units=50).empty
