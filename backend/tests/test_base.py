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
    for _ in range(600):
        t = e.step().telemetry
        assert 49.9 < t.frequency < 50.1
        assert 0.98 < t.bus_voltage < 1.02
        assert 250 < t.grid_import_kw < 400
        assert 55 < t.bess_soc < 66
        assert all((t.cb_main, t.cb_pv, t.cb_bess, t.cb_crit, t.cb_nc))
    assert 350 < t.load_critical_kw < 450


def test_simulation_is_deterministic():
    a = SimulationEngine(seed=7)
    b = SimulationEngine(seed=7)
    for _ in range(50):
        assert a.step().telemetry == b.step().telemetry


def test_unauthorised_trip_deenergises_the_hospital_feeder():
    e = SimulationEngine(seed=1)
    run(e, 20)
    e.start_scenario("unauthorised_breaker_trip")
    t = run(e, 10)
    assert t.cb_crit is False and abs(t.load_critical_kw) < 8
    assert t.ied_status.ied03 == "compromised"
    assert e.plant.true_state()["load_critical_kw"] == 0.0


def test_unauthorised_event_is_flagged_and_heartbeats_are_authorised():
    e = SimulationEngine(seed=1)
    e.start_scenario("unauthorised_breaker_trip")
    events = e.step().events
    bad = [x for x in events if not x.authorised]
    assert len(bad) == 1 and bad[0].dst == "IED-03" and bad[0].register == "CB_CRIT"
    assert any(x.authorised for x in events)


def test_false_frequency_report_fools_the_controller_not_the_grid():
    e = SimulationEngine(seed=1)
    run(e, 20)
    e.start_scenario("false_data_injection")
    t = run(e, 60)
    assert t.frequency < 49.7  # what meters report
    assert 49.95 < e.plant.true_state()["frequency"] < 50.05  # the real frequency is fine
    assert t.bess_kw > 150  # but the controller over-discharges the battery
    assert t.bess_soc < 58


def test_battery_obeys_limits_and_soc_follows_power():
    e = SimulationEngine(seed=1)
    run(e, 5)
    soc0 = e.plant.soc
    e.start_scenario("false_data_injection")
    for _ in range(100):
        e.step()
        assert -250.001 <= e.plant.bess_kw <= 250.001  # true power, not the noisy meter reading
    assert e.plant.soc < soc0


def test_islanding_moves_frequency_when_the_battery_cannot_cover_the_deficit():
    e = SimulationEngine(seed=1)
    run(e, 20)
    e.command("BESS_MODE", "HOLD")  # battery idle
    e.command("CB_MAIN", "OPEN")  # island: load 700 kW, PV ~375 kW
    t = run(e, 20)
    assert t.cb_main is False and abs(t.grid_import_kw) < 15  # no utility import while islanded
    assert t.frequency < 49.5  # large deficit pulls the frequency down


def test_store_roundtrip():
    s = EventStore()
    s.append("telemetry", 1.0, {"a": 1})
    s.append("event", 2.0, {"b": 2})
    assert [r["kind"] for r in s.query()] == ["telemetry", "event"]
    assert s.query(kind="event")[0]["data"] == {"b": 2}


def test_full_flow_attack_incident_contain_recover_without_second_incident():
    app = create_app(autostart=False)
    rt = app.state.runtime
    with TestClient(app) as c:
        assert c.get("/health").json()["status"] == "ok"
        for _ in range(20):
            rt.step()
        assert c.get("/incidents").json() == []  # healthy: no incident

        assert c.post("/scenario/start", json={"name": "unauthorised_breaker_trip"}).status_code == 200
        for _ in range(15):
            rt.step()
        incs = c.get("/incidents").json()
        assert len(incs) == 1 and incs[0]["status"] == "open"
        iid = incs[0]["id"]
        assert incs[0]["affected_devices"] == ["IED-03"]
        texts = " ".join(e["text"] for e in incs[0]["evidence"])
        assert "Hospital feeder load" in texts and "Unauthorised OPERATE CB_CRIT" in texts

        replay = c.get(f"/incidents/{iid}/replay").json()
        assert {r["kind"] for r in replay} >= {"telemetry", "event", "incident"}

        assert c.post(f"/incident/{iid}/approve-response").json()["status"] == "recovering"
        for _ in range(60):
            rt.step()
        for _ in range(200):
            rt.step()
        incs = c.get("/incidents").json()
        assert len(incs) == 1 and incs[0]["status"] == "recovered"
        assert rt.engine.plant.breakers["cb_crit"] is True


def test_planned_switching_raises_no_incident():
    app = create_app(autostart=False)
    rt = app.state.runtime
    with TestClient(app) as c:
        for _ in range(20):
            rt.step()
        c.post("/scenario/start", json={"name": "planned_switching"})
        for _ in range(120):
            rt.step()
        assert c.get("/incidents").json() == []


def test_unknown_scenario_and_incident_404():
    app = create_app(autostart=False)
    with TestClient(app) as c:
        assert c.post("/scenario/start", json={"name": "nope"}).status_code == 404
        assert c.post("/incident/INC-999/approve-response").status_code == 404
