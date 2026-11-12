import pandas as pd
import pytest

from shop_insights.analysis.basket import bought_together, pair_counts


def _baskets() -> pd.DataFrame:
    # 10 orders. A and B appear together in 4 of them; C is everywhere (so it pairs by chance).
    rows = []
    for order in range(10):
        items = ["C"]
        if order < 4:
            items += ["A", "B"]
        elif order < 6:
            items += ["A"]
        elif order < 7:
            items += ["B"]
        rows += [(str(order), item) for item in items]
    return pd.DataFrame(rows, columns=["invoice", "stock_code"])


def _orders(baskets: pd.DataFrame) -> pd.DataFrame:
    return baskets.assign(
        description="P " + baskets["stock_code"],
        quantity=1,
        invoice_date=pd.Timestamp("2011-06-01"),
    )


def test_pair_counts_counts_each_pair_once():
    pairs = pair_counts(_baskets(), min_product_orders=1, min_pair_orders=1)
    counts = {frozenset((a, b)): n for a, b, n in pairs.itertuples(index=False)}
    assert counts == {frozenset("AB"): 4, frozenset("AC"): 6, frozenset("BC"): 5}


def test_support_confidence_lift():
    result = bought_together(_orders(_baskets()), min_product_orders=1, min_pair_orders=1)
    ab = result[result[["product_a", "product_b"]].apply(frozenset, axis=1) == frozenset("AB")].iloc[0]
    assert ab["support"] == pytest.approx(0.4)                  # 4 of 10 orders
    conf_from_a = ab["confidence_a_to_b"] if ab["product_a"] == "A" else ab["confidence_b_to_a"]
    assert conf_from_a == pytest.approx(4 / 6, abs=1e-3)       # A is in 6 orders
    assert ab["lift"] == pytest.approx((4 / 10) / ((6 / 10) * (5 / 10)), abs=0.01)
    assert result.iloc[0][["product_a", "product_b"]].tolist() in (["A", "B"], ["B", "A"])  # highest lift


def test_rare_products_are_ignored():
    pairs = pair_counts(_baskets(), min_product_orders=6, min_pair_orders=1)
    assert set(pairs["product_a"]) | set(pairs["product_b"]) == {"A", "C"}
