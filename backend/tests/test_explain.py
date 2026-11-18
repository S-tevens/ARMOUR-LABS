"""Plain-language explanations: the template, the Gemini guard rails and the endpoints. No test calls the network."""
import time

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from explain.service import ExplanationService, facts, grounded, template_text

INC = {
    "id": "INC-1", "t_start": 100.0, "severity": "high", "confidence": 0.9, "classification": "attack",
    "affected_devices": ["IED-2"], "status": "open", "district": None, "campaign_id": None,
    "scores": {"network": 0.9, "twin": 0.95, "ml": 0.1, "invariants": 0.0},
    "evidence": [
        {"type": "network", "text": "Breaker command to IED-2 from 10.9.9.9, not the SCADA host.", "tag": "observed"},
        {"type": "twin_residual", "text": "Hospital feeder reads 0 kW; the authorised commands predict 180 kW.", "tag": "correlated"},
    ],
}


def wait_for(svc, inc, source, tries=100):
    out = svc.explain(inc)
    for _ in range(tries):
        if out["source"] == source and not out["pending"]:
            return out
        time.sleep(0.02)
        out = svc.explain(inc)
    return out


def test_template_uses_only_the_incident_facts():
    text = template_text(INC)
    assert "cyberattack" in text and "IED-2" in text and "10.9.9.9" in text and "approve the simulated containment" in text
    assert "the network rules" in text and "the digital twin" in text and "machine-learning" not in text  # only detectors at 0.8 or more


def test_template_does_not_call_unknown_incidents_attacks():
    text = template_text({**INC, "classification": "unknown"})
    assert "cyberattack" not in text and "no confirmed cause" in text


def test_without_a_key_the_template_is_returned_at_once(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    out = ExplanationService().explain(INC)
    assert out["source"] == "template" and out["pending"] is False and out["gemini_configured"] is False


def test_grounding_rejects_invented_numbers():
    f = facts(INC)
    assert grounded("The hospital feeder reads 0 kW instead of 180 kW.", f)
    assert not grounded("About 250 kW of load was lost.", f)


def test_gemini_answer_is_used_when_it_is_grounded(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    calls = []

    def caller(f, key, models):
        calls.append(models)
        return "Someone sent a breaker command that SCADA did not authorise. Hospital feeder reads 0 kW.", "stub-model"

    svc = ExplanationService(caller)
    first = svc.explain(INC)
    assert first["source"] == "template" and first["pending"] is True  # the page is never made to wait
    out = wait_for(svc, INC, "gemini")
    assert out["source"] == "gemini" and out["model"] == "stub-model" and "SCADA" in out["text"]
    svc.explain(INC)
    assert len(calls) == 1  # cached: one call per incident state


def test_an_ungrounded_or_failed_gemini_answer_falls_back_to_the_template(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    svc = ExplanationService(lambda f, k, m: ("Roughly 4000 homes lost power.", "stub-model"))
    svc.explain(INC)
    time.sleep(0.3)
    out = svc.explain(INC)
    assert out["source"] == "template" and out["pending"] is False and "note" in out

    def boom(f, k, m):
        raise RuntimeError("HTTP 503")

    svc2 = ExplanationService(boom)
    svc2.explain(INC)
    time.sleep(0.3)
    assert svc2.explain(INC)["source"] == "template"


def test_a_new_incident_state_gets_a_new_explanation(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    svc = ExplanationService()
    a = svc.explain(INC)["text"]
    b = svc.explain({**INC, "status": "recovered"})["text"]
    assert a != b and "closed" in b


def test_the_api_key_is_never_part_of_the_text_sent_or_returned(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret-key-123")
    seen = []

    def caller(f, key, models):
        seen.append(str(f))
        return "Someone sent a breaker command that SCADA did not authorise.", "m"

    svc = ExplanationService(caller)
    svc.explain(INC)
    out = wait_for(svc, INC, "gemini")
    assert "secret-key-123" not in str(seen) and "secret-key-123" not in str(out)


def test_explanation_endpoint_for_a_real_incident(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = create_app(autostart=False)
    rt = app.state.runtime
    with TestClient(app) as c:
        assert c.get("/incidents/nope/explanation").status_code == 404
        assert c.get("/city/incidents/nope/explanation").status_code == 404
        for _ in range(20):
            rt.step()
        c.post("/scenario/start", json={"name": "unauthorised_breaker_trip"})
        for _ in range(15):
            rt.step()
        iid = c.get("/incidents").json()[0]["id"]
        out = c.get(f"/incidents/{iid}/explanation").json()
        assert out["source"] == "template" and "IED-03" in out["text"] and out["pending"] is False
