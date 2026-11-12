import pandas as pd
import pytest

from shop_insights.data.cleaning import clean_orders
from shop_insights.data.loading import SalesFileError, standardize_columns


def test_clean_orders_removes_messy_rows(raw_orders):
    clean, report = clean_orders(raw_orders)

    # Only the deduplicated heart holder line and the two genuine cakestand sales survive.
    assert sorted(clean["invoice"].astype(str)) == ["1001", "1002", "1003"]
    assert report.removed["exact duplicate lines"] == 1
    assert report.removed["cancellations + the orders they cancelled"] == 2
    assert report.rows_out == 3


def test_missing_description_filled_from_same_product(raw_orders):
    clean, _ = clean_orders(raw_orders)
    assert set(clean.loc[clean["stock_code"] == "22423", "description"]) == {"REGENCY CAKESTAND"}


def test_revenue_and_dtypes(raw_orders):
    clean, _ = clean_orders(raw_orders)
    assert clean["stock_code"].dtype == "category"
    assert clean["revenue"].sum() == pytest.approx(6 * 2.5 + 2 * 10 + 1 * 10)


def test_standardize_columns_accepts_aliases():
    df = pd.DataFrame(columns=["InvoiceNo", "StockCode", "Quantity", "InvoiceDate", "UnitPrice", "Customer ID"])
    assert list(standardize_columns(df).columns) == [
        "invoice", "stock_code", "quantity", "invoice_date", "price", "customer_id"
    ]


def test_standardize_columns_reports_missing():
    with pytest.raises(SalesFileError, match="price"):
        standardize_columns(pd.DataFrame(columns=["Invoice", "StockCode", "Quantity", "InvoiceDate"]))
