from fastapi.testclient import TestClient

from api.app import create_app
from db.store import EventStore
from sim.engine import SimulationEngine


def run(engine, n):
    last = None
    for _ in range(n):
        last = engine.step()
    return last.telemetry


def test_normal_operation_is_stable():
    e = SimulationEngine(seed=1)
    for _ in range(300):
        t = e.step().telemetry
        assert 1.8 < t.pressure < 2.4
        assert 95 < t.flow < 125
    assert 55 < t.tank1_level < 70


def test_simulation_is_deterministic():
    a = [SimulationEngine(seed=7).step().telemetry.model_dump() for _ in range(1)]
    b = [SimulationEngine(seed=7).step().telemetry.model_dump() for _ in range(1)]
    assert a == b


def test_valve_close_raises_pressure_and_drops_flow():
    e = SimulationEngine(seed=1)
    run(e, 20)
    e.start_scenario("unauthorised_valve_close")
    t = run(e, 20)
    assert t.pressure > 4.0 and t.flow < 30 and t.valve1 is False
    assert e.plant.true_state()["valve1"] is False


def test_false_data_injection_changes_reading_not_process():
    e = SimulationEngine(seed=1)
    run(e, 20)
    e.start_scenario("false_data_injection")
    t = run(e, 20)
    assert t.pressure > 4.0
    assert e.plant.true_state()["pressure"] < 2.4  # real process unchanged


def test_unauthorised_event_is_flagged_and_heartbeats_are_authorised():
    e = SimulationEngine(seed=1)
    e.start_scenario("unauthorised_valve_close")
    events = e.step().events
    bad = [x for x in events if not x.authorised]
    assert len(bad) == 1 and bad[0].dst == "PLC-02"
    assert any(x.authorised for x in events)


def test_store_roundtrip():
    s = EventStore()
    s.append("telemetry", 1.0, {"a": 1})
    s.append("event", 2.0, {"b": 2})
    assert [r["kind"] for r in s.query()] == ["telemetry", "event"]
    assert s.query(kind="event")[0]["data"] == {"b": 2}


def test_full_flow_attack_incident_contain_recover():
    app = create_app(autostart=False)
    rt = app.state.runtime
    with TestClient(app) as c:
        assert c.get("/health").json()["status"] == "ok"
        for _ in range(10):
            rt.step()
        assert c.get("/incidents").json() == []  # healthy: no incident

        assert c.post("/scenario/start", json={"name": "unauthorised_valve_close"}).status_code == 200
        for _ in range(15):
            rt.step()
        incs = c.get("/incidents").json()
        assert len(incs) == 1 and incs[0]["status"] == "open"
        iid = incs[0]["id"]
        assert any(ev["tag"] == "observed" for ev in incs[0]["evidence"])

        replay = c.get(f"/incidents/{iid}/replay").json()
        assert {r["kind"] for r in replay} >= {"telemetry", "event", "incident"}

        assert c.post(f"/incident/{iid}/approve-response").json()["status"] == "recovering"
        for _ in range(40):
            rt.step()
        assert c.get("/incidents").json()[0]["status"] == "recovered"


def test_unknown_scenario_and_incident_404():
    app = create_app(autostart=False)
    with TestClient(app) as c:
        assert c.post("/scenario/start", json={"name": "nope"}).status_code == 404
        assert c.post("/incident/INC-999/approve-response").status_code == 404
