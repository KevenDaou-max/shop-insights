from fastapi.testclient import TestClient

from api import service
from api.main import app
from shop_insights import ai_summary

RESULT = {
    "data": {"first_date": "2011-01-01", "last_date": "2011-06-30"},
    "settings": {"stock_file": False},
    "promote": [{"description": f"P{i}", "recent_units": 10, "previous_units": 5, "reason": "up"} for i in range(9)],
    "dying": [], "bundles": [], "restock": [],
    "backtest": {"available": False},
}


def test_facts_are_limited_to_computed_numbers():
    facts = ai_summary.build_facts(RESULT)
    assert len(facts["promote"]) == ai_summary.TOP
    assert "backtest" not in facts
    assert "do not invent numbers" in ai_summary.build_prompt(RESULT)


def test_summary_endpoint_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    service._results_cache.put("abc", dict(RESULT))
    body = TestClient(app).get("/api/analyses/abc/summary").json()
    assert body["available"] is False and "GEMINI_API_KEY" in body["message"]


def test_summary_endpoint_caches_generated_text(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    calls = []
    monkeypatch.setattr(ai_summary, "generate_summary", lambda result: calls.append(1) or "Promote P0.")
    service._results_cache.put("xyz", dict(RESULT))
    client = TestClient(app)
    assert client.get("/api/analyses/xyz/summary").json()["text"] == "Promote P0."
    client.get("/api/analyses/xyz/summary")
    assert len(calls) == 1
