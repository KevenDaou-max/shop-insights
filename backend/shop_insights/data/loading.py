"""Read a sales file (CSV or Excel) into a DataFrame with standard column names."""
import io
from pathlib import Path

import pandas as pd

# Canonical column -> accepted spellings (compared after lowercasing and removing spaces/underscores).
# Accepting aliases lets the app read both "Online Retail" v1 and v2 exports and similar shop exports.
COLUMN_ALIASES: dict[str, set[str]] = {
    "invoice": {"invoice", "invoiceno", "invoicenumber", "orderid", "order"},
    "stock_code": {"stockcode", "sku", "productid", "productcode"},
    "description": {"description", "productname", "product"},
    "quantity": {"quantity", "qty", "units"},
    "invoice_date": {"invoicedate", "orderdate", "date"},
    "price": {"price", "unitprice"},
    "customer_id": {"customerid", "customer"},
    "country": {"country"},
}
REQUIRED_COLUMNS = ["invoice", "stock_code", "quantity", "invoice_date", "price"]


class SalesFileError(ValueError):
    """Raised when an uploaded file can't be used. The message is safe to show to the user."""


def _normalize(name: str) -> str:
    return str(name).strip().lower().replace(" ", "").replace("_", "").replace("-", "")


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename known columns to snake_case names and drop everything else."""
    lookup = {alias: canonical for canonical, aliases in COLUMN_ALIASES.items() for alias in aliases}
    renames = {col: lookup[_normalize(col)] for col in df.columns if _normalize(col) in lookup}
    df = df.rename(columns=renames)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise SalesFileError(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Found: {', '.join(map(str, renames.keys())) or 'none recognised'}."
        )
    keep = [c for c in COLUMN_ALIASES if c in df.columns]
    return df[keep]


def read_sales_bytes(content: bytes, filename: str) -> pd.DataFrame:
    """Parse an uploaded CSV/Excel file. Excel files may have several sheets (one per year)."""
    suffix = Path(filename).suffix.lower()
    try:
        if suffix in {".xlsx", ".xls"}:
            # calamine is a Rust Excel reader, ~10x faster than openpyxl on a 1M-row workbook.
            sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, engine="calamine")
            raw = pd.concat(sheets.values(), ignore_index=True)
        elif suffix in {".csv", ".txt"}:
            raw = _read_csv(content)
        else:
            raise SalesFileError(f"Unsupported file type '{suffix}'. Upload a .csv or .xlsx file.")
    except SalesFileError:
        raise
    except Exception as exc:  # pandas raises many different parser errors; the user just needs to know it failed
        raise SalesFileError(f"Could not read '{filename}': {exc}") from exc
    if raw.empty:
        raise SalesFileError("The file has no rows.")
    return standardize_columns(raw)


def _read_csv(content: bytes) -> pd.DataFrame:
    # Shop exports from Excel are often Windows-1252/Latin-1 (e.g. the '£' sign), not UTF-8.
    for encoding in ("utf-8", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(content), encoding=encoding, low_memory=False)
        except UnicodeDecodeError:
            continue
    raise SalesFileError("Could not decode the CSV file (tried UTF-8 and Latin-1).")


def read_sales_path(path: Path) -> pd.DataFrame:
    return read_sales_bytes(path.read_bytes(), path.name)
