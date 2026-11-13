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


def test_model_comes_from_env_with_default(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert ai_summary.gemini_model() == "gemini-3-flash-preview"
    monkeypatch.setenv("GEMINI_MODEL", "")
    assert ai_summary.gemini_model() == "gemini-3-flash-preview"
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash")
    assert ai_summary.gemini_model() == "gemini-3.5-flash"


def test_api_errors_become_short_friendly_messages(monkeypatch):
    from google.genai import errors

    class FailingModels:
        def generate_content(self, **_):
            raise errors.ClientError(404, {"error": {"code": 404, "message": "models/x is not found", "status": "NOT_FOUND"}})

    class FakeClient:
        def __init__(self, api_key, http_options):
            assert http_options.api_version == "v1beta"
            self.models = FailingModels()

    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setenv("GEMINI_MODEL", "x")
    monkeypatch.setattr("google.genai.Client", FakeClient)
    try:
        ai_summary.generate_summary(RESULT)
    except RuntimeError as exc:
        message = str(exc)
    assert message == "The AI model 'x' isn't available. Check GEMINI_MODEL in backend/.env."
    assert "{" not in message and "NOT_FOUND" not in message
