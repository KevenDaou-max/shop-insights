"""Glue between HTTP and the analysis: parse, clean, analyse - each step cached by content hash."""
from typing import Any

import pandas as pd

from api.cache import LRUCache, content_hash
from shop_insights.analysis.restock import RestockSettings, read_stock_bytes
from shop_insights.data.cleaning import clean_orders
from shop_insights.data.loading import SalesFileError, read_sales_bytes
from shop_insights.data.store import load_clean_orders
from shop_insights.pipeline import analyze

DEMO_KEY = "demo-online-retail-ii"
MIN_CLEAN_ROWS = 100

# Cleaned tables are big (~50 MB for 1M rows), so keep only a few; result dicts are small.
_orders_cache: LRUCache[pd.DataFrame] = LRUCache(max_items=3)
_results_cache: LRUCache[dict[str, Any]] = LRUCache(max_items=32)


def _cached_orders(key: str, load) -> pd.DataFrame:
    orders = _orders_cache.get(key)
    if orders is None:
        orders = load()
        _orders_cache.put(key, orders)
    return orders


def _clean_upload(content: bytes, filename: str) -> pd.DataFrame:
    orders, _ = clean_orders(read_sales_bytes(content, filename))
    if len(orders) < MIN_CLEAN_ROWS:
        raise SalesFileError(f"Only {len(orders)} valid sales rows after cleaning; need at least {MIN_CLEAN_ROWS}.")
    return orders


def run(
    sales_key: str,
    load_orders,
    settings: RestockSettings,
    stock_bytes: bytes | None = None,
    stock_name: str = "stock.csv",
) -> tuple[str, dict[str, Any], bool]:
    """Return (analysis_id, result, served_from_cache)."""
    stock_key = content_hash(stock_bytes) if stock_bytes else "no-stock"
    analysis_id = content_hash(sales_key, stock_key, str(settings.lead_time_weeks), str(settings.coverage_weeks))
    cached = _results_cache.get(analysis_id)
    if cached is not None:
        return analysis_id, cached, True

    stock = read_stock_bytes(stock_bytes, stock_name) if stock_bytes else None  # validate before heavy work
    orders = _cached_orders(sales_key, load_orders)
    try:
        result = analyze(orders, settings, stock)
    except ValueError as exc:   # e.g. not enough weeks of history to forecast
        raise SalesFileError(str(exc)) from exc
    result["id"] = analysis_id
    _results_cache.put(analysis_id, result)
    return analysis_id, result, False


def run_upload(content: bytes, filename: str, settings: RestockSettings, stock_bytes: bytes | None, stock_name: str):
    return run(content_hash(content), lambda: _clean_upload(content, filename), settings, stock_bytes, stock_name)


def run_demo(settings: RestockSettings, stock_bytes: bytes | None):
    return run(DEMO_KEY, load_clean_orders, settings, stock_bytes)


def get_result(analysis_id: str) -> dict[str, Any] | None:
    return _results_cache.get(analysis_id)
