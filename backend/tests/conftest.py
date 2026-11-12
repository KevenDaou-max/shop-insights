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


def make_clean_orders(weekly_units: dict[str, list[int]], end: str = "2011-06-30", lines_per_week: int | None = None) -> pd.DataFrame:
    """Build a cleaned-orders table from per-product weekly unit counts (oldest week first).

    Each week's units are split over separate invoices on the last day of that week (so week
    boundaries match analysis.weekly exactly): `lines_per_week` invoices, or by default one
    invoice per ~10 units, so busier weeks also have more orders, like real data.
    """
    end_ts = pd.Timestamp(end)
    rows = []
    invoice = 0
    for code, units in weekly_units.items():
        n = len(units)
        for i, qty in enumerate(units):
            if qty <= 0:
                continue
            day = end_ts - pd.Timedelta(days=7 * (n - 1 - i))
            n_lines = lines_per_week or -(-qty // 10)
            parts = [qty // n_lines + (1 if k < qty % n_lines else 0) for k in range(n_lines)]
            for part in filter(None, parts):
                invoice += 1
                rows.append((str(invoice), code, f"PRODUCT {code}", part, day, 1.0))
    df = pd.DataFrame(rows, columns=["invoice", "stock_code", "description", "quantity", "invoice_date", "price"])
    return df.assign(
        invoice=df["invoice"].astype("category"),
        stock_code=df["stock_code"].astype("category"),
        description=df["description"].astype("category"),
        revenue=df["quantity"] * df["price"],
    )
