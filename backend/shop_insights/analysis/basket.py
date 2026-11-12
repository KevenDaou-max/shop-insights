"""Products BOUGHT TOGETHER: market basket analysis on pairs of products.

For a pair (A, B):
  support    = share of all orders that contain both A and B         ("how common is the pair")
  confidence = share of orders containing A that also contain B      ("if they buy A, how often B")
  lift       = confidence(A->B) / share of orders containing B
             = how many times more often A and B appear together than if customers picked them
               independently. lift > 1 means they really go together; lift ~ 1 is coincidence.

Performance: instead of a dense orders x products table (40k x 4k = 160M cells), we keep only
products in at least `min_product_orders` orders and build a SPARSE 0/1 matrix X (orders x
products). One sparse matrix product X.T @ X then gives the co-occurrence count of every pair.
"""
import numpy as np
import pandas as pd
from scipy import sparse

from shop_insights.analysis.weekly import DAYS_PER_WEEK, last_day, orders_until, product_names
from shop_insights.config import BASKET_MIN_PAIR_ORDERS, BASKET_MIN_PRODUCT_ORDERS

DEFAULT_LOOKBACK_WEEKS = 52   # older baskets describe a different product range


def _recent_baskets(orders: pd.DataFrame, end: pd.Timestamp, lookback_weeks: int) -> pd.DataFrame:
    start = end - pd.Timedelta(days=lookback_weeks * DAYS_PER_WEEK)
    window = orders_until(orders, end)
    window = window[window["invoice_date"] > start]
    # A product listed twice on one invoice is still one basket membership.
    baskets = window[["invoice", "stock_code"]].drop_duplicates()
    return baskets.assign(invoice=baskets["invoice"].astype(str), stock_code=baskets["stock_code"].astype(str))


def pair_counts(baskets: pd.DataFrame, min_product_orders: int, min_pair_orders: int) -> pd.DataFrame:
    """Co-occurrence counts for every product pair seen together in >= min_pair_orders orders."""
    product_orders = baskets["stock_code"].value_counts()
    frequent = product_orders.index[product_orders >= min_product_orders]
    baskets = baskets[baskets["stock_code"].isin(frequent)]
    if baskets.empty:
        return pd.DataFrame(columns=["product_a", "product_b", "orders_together"])

    order_idx, _ = pd.factorize(baskets["invoice"])
    product_idx, products = pd.factorize(baskets["stock_code"])
    matrix = sparse.csr_matrix(
        (np.ones(len(baskets), dtype=np.int32), (order_idx, product_idx)),
        shape=(order_idx.max() + 1, len(products)),
    )
    co_occurrence = sparse.triu(matrix.T @ matrix, k=1).tocoo()   # k=1: each pair once, no A-A
    keep = co_occurrence.data >= min_pair_orders
    return pd.DataFrame({
        "product_a": products[co_occurrence.row[keep]],
        "product_b": products[co_occurrence.col[keep]],
        "orders_together": co_occurrence.data[keep],
    })


def bought_together(
    orders: pd.DataFrame,
    end: pd.Timestamp | None = None,
    lookback_weeks: int = DEFAULT_LOOKBACK_WEEKS,
    min_product_orders: int = BASKET_MIN_PRODUCT_ORDERS,
    min_pair_orders: int = BASKET_MIN_PAIR_ORDERS,
    top_n: int = 20,
) -> pd.DataFrame:
    """Top product pairs by lift, with support/confidence and a bundle suggestion."""
    end = last_day(orders) if end is None else pd.Timestamp(end)
    baskets = _recent_baskets(orders, end, lookback_weeks)
    n_orders = baskets["invoice"].nunique()
    pairs = pair_counts(baskets, min_product_orders, min_pair_orders)
    if pairs.empty:
        return pairs

    product_orders = baskets["stock_code"].value_counts()
    orders_a = pairs["product_a"].map(product_orders).to_numpy()
    orders_b = pairs["product_b"].map(product_orders).to_numpy()
    together = pairs["orders_together"].to_numpy()

    pairs = pairs.assign(
        support=together / n_orders,
        confidence_a_to_b=together / orders_a,
        confidence_b_to_a=together / orders_b,
        lift=together * n_orders / (orders_a * orders_b),
    )
    names = product_names(orders)
    pairs.insert(1, "description_a", pairs["product_a"].map(names))
    pairs.insert(3, "description_b", pairs["product_b"].map(names))
    top = pairs.sort_values(["lift", "orders_together"], ascending=False).head(top_n).reset_index(drop=True)
    best_conf = top[["confidence_a_to_b", "confidence_b_to_a"]].max(axis=1)
    top["reason"] = (
        (best_conf * 100).round(0).astype(int).astype(str) + "% of buyers of one also buy the other; "
        + top["lift"].round(1).astype(str) + "x more often than by chance"
    )
    return top.round({"support": 4, "confidence_a_to_b": 3, "confidence_b_to_a": 3, "lift": 2})
