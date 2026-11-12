"""HTTP API. Run (from backend/):  uvicorn api.main:app --reload

Routes are plain `def` (not async): FastAPI then runs them in a thread pool, so a long
pandas analysis doesn't freeze the server for other requests.
"""
import os
from typing import Annotated, Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import service
from api.uploads import read_limited
from shop_insights.analysis.restock import RestockSettings
from shop_insights import ai_summary
from shop_insights.config import REPO_ROOT, SAMPLE_STOCK_CSV
from shop_insights.data.loading import SalesFileError

load_dotenv(REPO_ROOT / "backend" / ".env")  # GEMINI_API_KEY etc.; real env vars take priority

MAX_SALES_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))
MAX_STOCK_MB = 5
SECTIONS = ("data", "promote", "dying", "bundles", "forecast", "restock", "backtest", "timings_seconds")

app = FastAPI(title="Shop Insights API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

LeadTime = Annotated[int, Form(ge=0, le=8, description="Weeks until an order arrives")]
Coverage = Annotated[int, Form(ge=1, le=8, description="Weeks the order should last after arriving")]


@app.exception_handler(SalesFileError)
def bad_file(_, exc: SalesFileError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})


def _response(analysis_id: str, result: dict[str, Any], cached: bool) -> dict[str, Any]:
    return {**result, "id": analysis_id, "cached": cached}


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "ai_summary": ai_summary.summary_available()}


@app.post("/api/analyses", status_code=status.HTTP_201_CREATED)
def create_analysis(
    sales_file: Annotated[UploadFile, File(description="Orders as .csv or .xlsx")],
    stock_file: Annotated[UploadFile | None, File(description="Optional StockCode,CurrentStock CSV")] = None,
    lead_time_weeks: LeadTime = 2,
    coverage_weeks: Coverage = 2,
) -> dict[str, Any]:
    """Upload a sales file (and optional stock file) and get every result back in one response."""
    sales = read_limited(sales_file, MAX_SALES_MB)
    stock = read_limited(stock_file, MAX_STOCK_MB) if stock_file and stock_file.filename else None
    settings = RestockSettings(lead_time_weeks, coverage_weeks)
    return _response(*service.run_upload(sales, sales_file.filename or "upload.csv", settings, stock,
                                         stock_file.filename if stock else "stock.csv"))


@app.post("/api/analyses/demo", status_code=status.HTTP_201_CREATED)
def create_demo_analysis(
    use_sample_stock: Annotated[bool, Form()] = False,
    lead_time_weeks: LeadTime = 2,
    coverage_weeks: Coverage = 2,
) -> dict[str, Any]:
    """Analyse the bundled Online Retail II dataset (optionally with the SAMPLE stock file)."""
    stock = SAMPLE_STOCK_CSV.read_bytes() if use_sample_stock else None
    try:
        return _response(*service.run_demo(RestockSettings(lead_time_weeks, coverage_weeks), stock))
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


def _get_or_404(analysis_id: str) -> dict[str, Any]:
    result = service.get_result(analysis_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found (it may have expired). Upload the file again.")
    return result


@app.get("/api/analyses/{analysis_id}")
def get_analysis(analysis_id: str) -> dict[str, Any]:
    return _get_or_404(analysis_id)


# Declared before the generic /{section} route so "summary" isn't rejected as an unknown section.
@app.get("/api/analyses/{analysis_id}/summary")
def get_summary(analysis_id: str) -> dict[str, Any]:
    """AI summary, generated on first request and cached. Never fails the page: errors come back as text."""
    result = _get_or_404(analysis_id)
    if "ai_summary" not in result:
        if not ai_summary.summary_available():
            return {"available": False, "text": None, "message": "Add GEMINI_API_KEY to backend/.env to enable the AI summary."}
        try:
            result["ai_summary"] = ai_summary.generate_summary(result)
        except RuntimeError as exc:
            return {"available": False, "text": None, "message": str(exc)}   # not cached: may work next time
    return {"available": True, "text": result["ai_summary"], "message": None}


@app.get("/api/analyses/{analysis_id}/{section}")
def get_section(analysis_id: str, section: Literal[SECTIONS]) -> Any:  # type: ignore[valid-type]
    return _get_or_404(analysis_id)[section]
