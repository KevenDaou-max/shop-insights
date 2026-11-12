"""Turn raw order lines into clean product sales.

Every step records how many rows it removed, so the cleaning is transparent
(the numbers are shown in the README and returned by the API).
"""
from dataclasses import dataclass, field

import pandas as pd

# Stock codes that are services/fees/adjustments, not products a shop could promote or restock.
# Found by listing every code that doesn't look like a normal product code in Online Retail II.
NON_PRODUCT_CODE_PATTERN = (
    r"^(?:POST|DOT|M|C2|D|S|B|CRUK|PADS|AMAZONFEE|BANK CHARGES|ADJUST\d*|TEST\d*|GIFT_.*|DCGSS.*)$"
)
CANCEL_PREFIX = "C"     # Online Retail: an invoice starting with C cancels an earlier order
ADJUST_PREFIX = "A"     # "Adjust bad debt" bookkeeping entries


@dataclass
class CleaningReport:
    rows_in: int = 0
    removed: dict[str, int] = field(default_factory=dict)
    rows_out: int = 0

    def log(self, step: str, before: int, after: int) -> None:
        self.removed[step] = before - after


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["invoice"] = out["invoice"].astype(str).str.strip()
    # Upper-casing merges codes that differ only in case (e.g. 'm' and 'M' both mean "Manual").
    out["stock_code"] = out["stock_code"].astype(str).str.strip().str.upper()
    out["quantity"] = pd.to_numeric(out["quantity"], errors="coerce")
    out["price"] = pd.to_numeric(out["price"], errors="coerce")
    out["invoice_date"] = pd.to_datetime(out["invoice_date"], errors="coerce")
    if "customer_id" in out:
        out["customer_id"] = pd.to_numeric(out["customer_id"], errors="coerce").astype("Int64")
    if "description" not in out:
        out["description"] = pd.NA
    return out.dropna(subset=["quantity", "price", "invoice_date"])


def _remove_cancelled(df: pd.DataFrame) -> pd.DataFrame:
    """Drop cancellation lines AND the original sale lines they cancel.

    Dropping only the negative 'C' lines would leave the original order in the data, as if it
    happened (e.g. the famous 80,995-unit order that was cancelled minutes later). We match a
    cancellation to the latest earlier sale with the same customer, product and quantity.
    """
    is_cancel = df["invoice"].str.startswith(CANCEL_PREFIX)
    keys = ["customer_id", "stock_code", "quantity"]

    cancels = df.loc[is_cancel & df["customer_id"].notna(), keys + ["invoice_date"]]
    cancels = cancels.assign(quantity=-cancels["quantity"], cancel_id=range(len(cancels)))
    sales = df.loc[~is_cancel & df["customer_id"].notna(), keys + ["invoice_date"]]
    sales = sales.rename_axis("sale_idx").reset_index()

    matches = sales.merge(cancels, on=keys, suffixes=("", "_cancel"))
    matches = matches[matches["invoice_date"] <= matches["invoice_date_cancel"]]
    matches = (
        matches.sort_values("invoice_date", ascending=False)
        .drop_duplicates("cancel_id")      # each cancellation removes one sale...
        .drop_duplicates("sale_idx")       # ...and each sale can only be cancelled once
    )
    drop_idx = df.index[is_cancel].union(pd.Index(matches["sale_idx"]))
    return df.drop(index=drop_idx)


def _fill_descriptions(df: pd.DataFrame) -> pd.DataFrame:
    """Give each product one name: its most common description (some rows have none or typos)."""
    canonical = (
        df.dropna(subset=["description"])
        .groupby(["stock_code", "description"], observed=True)
        .size()
        .reset_index(name="n")
        .sort_values("n", ascending=False)
        .drop_duplicates("stock_code")
        .set_index("stock_code")["description"]
    )
    names = df["stock_code"].map(canonical).fillna(df["stock_code"])
    return df.assign(description=names.astype(str).str.strip())


def _finalize_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Categories for repeated strings cut memory ~5x and make groupby faster."""
    out = df.assign(
        invoice=df["invoice"].astype("category"),
        stock_code=df["stock_code"].astype("category"),
        description=df["description"].astype("category"),
        quantity=df["quantity"].astype("int32"),
        price=df["price"].astype("float64"),
        revenue=(df["quantity"] * df["price"]).astype("float64"),
    )
    if "country" in out:
        out["country"] = out["country"].astype("category")
    return out.sort_values("invoice_date", kind="stable").reset_index(drop=True)


def clean_orders(raw: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
    """Run all cleaning steps on standardized columns (see loading.standardize_columns)."""
    report = CleaningReport(rows_in=len(raw))

    def step(name: str, frame: pd.DataFrame, func) -> pd.DataFrame:
        result = func(frame)
        report.log(name, len(frame), len(result))
        return result

    df = step("unreadable values (bad date/number)", raw, _coerce_types)
    df = step("exact duplicate lines", df, lambda d: d.drop_duplicates())
    df = step("cancellations + the orders they cancelled", df, _remove_cancelled)
    df = step("bookkeeping adjustments", df, lambda d: d[~d["invoice"].str.startswith(ADJUST_PREFIX)])
    df = step("zero/negative quantity or price", df, lambda d: d[(d["quantity"] > 0) & (d["price"] > 0)])
    df = step(
        "non-product codes (postage, fees, vouchers...)",
        df,
        lambda d: d[~d["stock_code"].str.fullmatch(NON_PRODUCT_CODE_PATTERN)],
    )
    df = _finalize_dtypes(_fill_descriptions(df))
    report.rows_out = len(df)
    return df, report
