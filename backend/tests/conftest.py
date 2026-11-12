"""Shared fixtures: small hand-made order tables, so tests are fast and results are known exactly."""
import pandas as pd
import pytest


def make_raw_orders(rows: list[tuple]) -> pd.DataFrame:
    """rows: (invoice, stock_code, description, quantity, date, price, customer_id)"""
    return pd.DataFrame(
        rows,
        columns=["invoice", "stock_code", "description", "quantity", "invoice_date", "price", "customer_id"],
    )


@pytest.fixture
def raw_orders() -> pd.DataFrame:
    return make_raw_orders([
        ("1001", "85123A", "HEART HOLDER", 6, "2011-01-03 10:00", 2.5, 1),
        ("1001", "85123A", "HEART HOLDER", 6, "2011-01-03 10:00", 2.5, 1),   # exact duplicate
        ("1002", "22423", None, 2, "2011-01-04 10:00", 10.0, 2),              # missing description
        ("1003", "22423", "REGENCY CAKESTAND", 1, "2011-01-05 10:00", 10.0, 3),
        ("1004", "22423", "REGENCY CAKESTAND", 500, "2011-01-06 10:00", 9.0, 4),
        ("C1005", "22423", "REGENCY CAKESTAND", -500, "2011-01-06 10:05", 9.0, 4),  # cancels 1004
        ("1006", "POST", "POSTAGE", 1, "2011-01-07 10:00", 18.0, 5),          # not a product
        ("1007", "21212", "CAKE CASES", 0, "2011-01-07 10:00", 0.5, 5),       # zero quantity
        ("1008", "21212", "CAKE CASES", 5, "2011-01-08 10:00", 0.0, 5),       # zero price
        ("A1009", "B", "Adjust bad debt", 1, "2011-01-08 10:00", 100.0, None),
    ])
