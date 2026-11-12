"""Download the UCI Online Retail II dataset (not committed to git: ~45 MB, licensed CC BY 4.0)."""
import shutil
import urllib.request
import zipfile
from pathlib import Path

from shop_insights.config import DATASET_URL, RAW_DIR, RAW_XLSX, RAW_ZIP


def download_dataset(force: bool = False) -> Path:
    """Fetch the zip and extract the .xlsx. Skips work if the file already exists."""
    if RAW_XLSX.exists() and not force:
        print(f"Already downloaded: {RAW_XLSX}")
        return RAW_XLSX

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {DATASET_URL} ...")
    request = urllib.request.Request(DATASET_URL, headers={"User-Agent": "shop-insights-downloader"})
    with urllib.request.urlopen(request, timeout=120) as response, open(RAW_ZIP, "wb") as out:
        shutil.copyfileobj(response, out)

    with zipfile.ZipFile(RAW_ZIP) as archive:
        xlsx_name = next(n for n in archive.namelist() if n.lower().endswith(".xlsx"))
        # Extract by streaming to a fixed path, so a malicious archive path can't escape RAW_DIR.
        with archive.open(xlsx_name) as src, open(RAW_XLSX, "wb") as dst:
            shutil.copyfileobj(src, dst)
    RAW_ZIP.unlink()
    print(f"Saved {RAW_XLSX} ({RAW_XLSX.stat().st_size / 1e6:.1f} MB)")
    return RAW_XLSX
