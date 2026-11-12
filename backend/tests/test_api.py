import io

import numpy as np
import pytest
from fastapi.testclient import TestClient

import api.main
from api.main import app
from tests.conftest import make_clean_orders

client = TestClient(app)


@pytest.fixture(scope="module")
def sales_csv() -> bytes:
    rng = np.random.default_rng(1)
    weeks = np.arange(70)
    series = {f"P{i}": (40 + 5 * i + 10 * np.sin(weeks / 4 + i) + rng.normal(0, 2, 70)).round().astype(int).tolist()
              for i in range(12)}
    orders = make_clean_orders(series, end="2011-06-30")
    orders = orders.rename(columns={"invoice": "Invoice", "stock_code": "StockCode", "description": "Description",
                                    "quantity": "Quantity", "invoice_date": "InvoiceDate", "price": "Price"})
    return orders.drop(columns="revenue").to_csv(index=False).encode()


def _upload(content: bytes, name: str = "sales.csv", **form):
    files = {"sales_file": (name, io.BytesIO(content), "text/csv")}
    if "stock" in form:
        files["stock_file"] = ("stock.csv", io.BytesIO(form.pop("stock")), "text/csv")
    return client.post("/api/analyses", files=files, data=form)


def test_upload_returns_all_sections_and_is_cached(sales_csv):
    first = _upload(sales_csv)
    assert first.status_code == 201, first.text
    body = first.json()
    for key in ("promote", "dying", "bundles", "forecast", "restock", "backtest", "data", "timings_seconds"):
        assert key in body
    assert body["cached"] is False and body["backtest"]["available"] is True

    second = _upload(sales_csv)
    assert second.json()["cached"] is True and second.json()["id"] == body["id"]

    section = client.get(f"/api/analyses/{body['id']}/restock")
    assert section.status_code == 200 and isinstance(section.json(), list)


def test_settings_change_gives_new_analysis(sales_csv):
    a = _upload(sales_csv, lead_time_weeks="2", coverage_weeks="2").json()
    b = _upload(sales_csv, lead_time_weeks="3", coverage_weeks="2").json()
    assert a["id"] != b["id"] and b["settings"]["lead_time_weeks"] == 3


def test_stock_file_limits_restock_to_listed_products(sales_csv):
    body = _upload(sales_csv, stock=b"StockCode,CurrentStock\nP11,0\nP0,100000\n").json()
    assert [row["stock_code"] for row in body["restock"]] == ["P11"]
    assert body["restock"][0]["weeks_of_stock_left"] == 0


def test_bad_files_get_clear_errors(sales_csv):
    assert "Missing required column" in _upload(b"a,b\n1,2\n").json()["detail"]
    assert "Unsupported file type" in _upload(b"x", name="sales.pdf").json()["detail"]
    assert _upload(b"", name="sales.csv").status_code == 400
    bad_stock = _upload(sales_csv, stock=b"foo,bar\n1,2\n")
    assert bad_stock.status_code == 400 and "StockCode" in bad_stock.json()["detail"]


def test_upload_size_limit(sales_csv, monkeypatch):
    monkeypatch.setattr(api.main, "MAX_SALES_MB", 0)
    response = _upload(sales_csv)
    assert response.status_code == 413 and "limit" in response.json()["detail"]


def test_invalid_settings_and_unknown_ids(sales_csv):
    assert _upload(sales_csv, coverage_weeks="0").status_code == 422
    assert client.get("/api/analyses/nope").status_code == 404
    assert client.get("/api/analyses/nope/unknown-section").status_code == 422
