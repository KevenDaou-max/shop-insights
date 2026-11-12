"""Short descriptive summary of a cleaned orders table."""
from typing import Any

import pandas as pd


def summarize_orders(orders: pd.DataFrame) -> dict[str, Any]:
    return {
        "rows": int(len(orders)),
        "first_date": orders["invoice_date"].min().date().isoformat(),
        "last_date": orders["invoice_date"].max().date().isoformat(),
        "orders": int(orders["invoice"].nunique()),
        "products": int(orders["stock_code"].nunique()),
        "customers": int(orders["customer_id"].nunique()) or None,
        "countries": int(orders["country"].nunique()) if "country" in orders else None,
        "units_sold": int(orders["quantity"].sum()),
        "revenue": round(float(orders["revenue"].sum()), 2),
    }
