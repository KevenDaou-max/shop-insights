"""Plain-English summary of the results, written by Google Gemini (optional).

The LLM never sees raw data and never computes anything: we send it the numbers our code
already produced and ask it to explain them. That keeps every figure traceable to the code,
and the instructions forbid inventing numbers. Without GEMINI_API_KEY the app skips this.
"""
import json
import os
from typing import Any

DEFAULT_MODEL = "gemini-3-flash-preview"   # free-tier Flash model; override with GEMINI_MODEL
TOP = 5

INSTRUCTIONS = """You are a retail advisor writing for a small online shop owner with no data background.
Using ONLY the facts in the JSON below, write a short summary (max 180 words) in plain English:
1. Two or three products to promote and why.
2. Products that are dying and what to do about them.
3. One or two bundle ideas.
4. The most urgent restock actions.
5. One honest sentence on how reliable this advice was in the backtest, including where the
   simple baseline did better.
Rules: do not invent numbers or products; round numbers; no tables; use short paragraphs or bullets."""


def _pick(rows: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    return [{k: row.get(k) for k in keys} for row in rows[:TOP]]


def build_facts(result: dict[str, Any]) -> dict[str, Any]:
    """The compact, already-computed facts the LLM is allowed to talk about."""
    bt = result["backtest"]
    facts: dict[str, Any] = {
        "data_period": f"{result['data']['first_date']} to {result['data']['last_date']}",
        "promote": _pick(result["promote"], ["description", "recent_units", "previous_units", "reason"]),
        "dying": _pick(result["dying"], ["description", "recent_units", "previous_units", "reason"]),
        "bundles": _pick(result["bundles"], ["description_a", "description_b", "lift", "confidence_a_to_b"]),
        "restock": _pick(result["restock"], ["description", "recommended_quantity", "weeks_of_stock_left", "reason"]),
        "restock_mode": "units to order" if result["settings"]["stock_file"] else "recommended stock level",
    }
    if bt.get("available"):
        facts["backtest"] = {
            "forecast_error_wape_pct": bt["forecast"]["wape_pct"],
            "promote_hit_rate_pct": {
                "model": bt["trends"]["promote"]["model"]["hit_rate_pct"],
                "baseline": bt["trends"]["promote"]["baseline_last_month_best_sellers"]["hit_rate_pct"],
            },
            "dying_hit_rate_pct": {
                "model": bt["trends"]["dying"]["model"]["hit_rate_pct"],
                "baseline": bt["trends"]["dying"]["baseline_last_month_worst_sellers"]["hit_rate_pct"],
            },
            "restock_ran_out_pct": {
                "model": bt["restock"]["model_with_safety_stock"]["ran_out_pct"],
                "baseline": bt["restock"]["baseline_same_as_last_month"]["ran_out_pct"],
            },
        }
    return facts


def build_prompt(result: dict[str, Any]) -> str:
    return f"{INSTRUCTIONS}\n\nFACTS (JSON):\n{json.dumps(build_facts(result), indent=1)}"


def summary_available() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


def generate_summary(result: dict[str, Any]) -> str:
    """Call Gemini. Raises RuntimeError with a user-friendly message on failure."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("No GEMINI_API_KEY set; the AI summary is turned off.")
    from google import genai  # imported lazily so the app starts fine without the package/key

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", DEFAULT_MODEL), contents=build_prompt(result)
        )
    except Exception as exc:  # network, quota, invalid key... the dashboard still works without it
        raise RuntimeError(f"Gemini request failed: {exc}") from exc
    if not response.text:
        raise RuntimeError("Gemini returned an empty answer.")
    return response.text.strip()
