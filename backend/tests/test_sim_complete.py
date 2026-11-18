import json

from fastapi.testclient import TestClient

from api.app import create_app
from core.contracts import Telemetry
from sim import scenarios
from sim.dataset import COLUMNS, generate_run, write_dataset
from sim.engine import SimulationEngine
from sim.recovery import RecoveryVerifier


def run(e, n):
    last = None
    for _ in range(n):
        last = e.step()
    return last


def warmed(seed=1, n=40):
    e = SimulationEngine(seed)
    run(e, n)
    return e


def test_every_scenario_runs_and_has_metadata():
    for name, info in scenarios.SCENARIO_INFO.items():
        e = warmed()
        e.start_scenario(name)
        run(e, 30)
        assert info["kind"] in ("attack", "fault", "benign") and info["group"] in ("core", "extra")
        e.stop_scenario()
        run(e, 60)


def test_pump_speed_scales_flow_and_pressure():
    e = warmed()
    e.command("PLC-01", "PUMP1_SPEED", 0.8)
    t = run(e, 25).telemetry
    assert 80 < t.flow < 96 and t.pressure < 1.6


def test_operator_setpoint_change_is_authorised_and_benign():
    e = warmed()
    e.start_scenario("operator_setpoint_change")
    r = e.step()
    assert all(x.authorised for x in r.events)
    assert e.ground_truth()["is_anomaly"] is False
    assert e.command_log and e.command_log[-1].register == "PUMP1_SPEED"


def test_stuck_valve_has_no_network_evidence():
    e = warmed()
    e.start_scenario("stuck_valve")
    events = []
    for _ in range(25):
        events += e.step().events
    t = e.plant.observe()
    assert all(x.authorised for x in events)
    assert t.valve1 is True and t.flow < 75 and t.pressure > 3.0
    assert e.ground_truth()["is_attack"] is False


def test_filter_clog_degrades_slowly():
    e = warmed()
    e.start_scenario("filter_clog")
    early = run(e, 20).telemetry
    late = run(e, 160).telemetry
    assert late.flow < early.flow - 8 and late.pressure > early.pressure + 0.3


def test_replay_masks_readings_but_not_the_valve_and_duplicates_seq():
    e = warmed(n=60)
    seen_before = {x.seq for x in e.event_log}
    e.start_scenario("replay_attack")
    events = []
    for _ in range(20):
        r = e.step()
        events += r.events
    t = r.telemetry
    assert t.valve1 is False  # the manipulation is visible in actuator state
    assert t.pressure < 2.6 and t.flow > 90  # but replayed readings still look normal
    assert e.plant.true_state()["pressure"] > 4.0
    dupes = [x for x in events if x.seq in seen_before and not x.authorised]
    assert dupes and all(x.t < e.plant.t - 10 for x in dupes)  # stale + duplicated sequence numbers


def test_dos_floods_events_drops_heartbeats_and_makes_sensors_stale():
    e = warmed()
    e.start_scenario("dos_flood")
    events = []
    stale = 0
    prev = None
    for _ in range(40):
        r = e.step()
        events += r.events
        cur = (r.telemetry.pressure, r.telemetry.flow)
        stale += prev == cur
        prev = cur
    assert sum(1 for x in events if not x.authorised) >= 25 * 40
    assert not any(x.authorised and x.dst == "PLC-03" for x in events)
    assert stale >= 5


def test_subtle_variants_stay_under_the_baseline_threshold_but_ramp_grows():
    e = warmed()
    e.start_scenario("fdi_small")
    t = run(e, 30).telemetry
    assert 2.3 < t.pressure < 2.8  # small, deliberately subtle
    e2 = warmed()
    e2.start_scenario("fdi_slow_ramp")
    a = run(e2, 20).telemetry.pressure
    b = run(e2, 60).telemetry.pressure
    assert b > a + 1.0


def test_containment_is_staged_and_recovers_each_core_scenario():
    for name in ("unauthorised_valve_close", "false_data_injection", "sensor_drift", "stuck_valve", "filter_clog", "dos_flood"):
        e = warmed()
        e.start_scenario(name)
        run(e, 40)
        e.begin_containment()
        v = RecoveryVerifier()
        v.start(e.plant.t)
        state = "recovering"
        for _ in range(120):
            state = v.update(e.step().telemetry).state
            if state != "recovering":
                break
        assert state == "recovered", name
        assert e.containment_log, name


def test_recovery_verifier_requires_dwell_and_can_be_unresolved():
    ok = Telemetry(t=0, tick=0, tank1_level=62, tank2_level=48, pressure=2.1, flow=110, temperature=27,
                   pump1=True, pump2=True, valve1=True)
    v = RecoveryVerifier(dwell=10, timeout=30)
    v.start(0.0)
    for i in range(1, 9):
        assert v.update(ok.model_copy(update={"t": float(i)})).state == "recovering"  # dwell not yet met
    assert v.update(ok.model_copy(update={"t": 11.0})).state == "recovered"

    bad = ok.model_copy(update={"pressure": 4.8})
    v2 = RecoveryVerifier(dwell=10, timeout=30)
    v2.start(0.0)
    states = [v2.update(bad.model_copy(update={"t": float(i)})).state for i in range(1, 40)]
    assert states[0] == "recovering" and states[-1] == "unresolved"
    # a closed valve is never "recovered", even with perfect numbers
    v3 = RecoveryVerifier(dwell=2, timeout=30)
    v3.start(0.0)
    closed = ok.model_copy(update={"valve1": False})
    assert all(v3.update(closed.model_copy(update={"t": float(i)})).state == "recovering" for i in range(1, 10))


def test_same_seed_gives_identical_runs():
    a, ea = generate_run("replay_attack", 5, ticks=200, start=50, stop=150)
    b, eb = generate_run("replay_attack", 5, ticks=200, start=50, stop=150)
    assert a == b and ea == eb


def test_dataset_labels_and_files(tmp_path):
    rows, _ = generate_run("unauthorised_valve_close", 3, ticks=200, start=50, stop=150)
    assert set(rows[0]) == set(COLUMNS)
    assert [r["is_attack"] for r in rows[:50]] == [0] * 50
    assert all(r["is_attack"] == 1 for r in rows[50:150]) and all(r["is_attack"] == 0 for r in rows[150:])
    rows, _ = generate_run("operator_setpoint_change", 3, ticks=200, start=50, stop=150)
    assert all(r["is_anomaly"] == 0 and r["kind"] == "benign" for r in rows[50:150])
    rows, _ = generate_run("stuck_valve", 3, ticks=200, start=50, stop=150)
    assert all(r["is_anomaly"] == 1 and r["is_attack"] == 0 for r in rows[50:150])

    m = write_dataset(tmp_path, normal_seeds=(1,), scenario_seeds=(1,))
    assert len(m["runs"]) == 1 + len(scenarios.SCENARIO_INFO)
    assert (tmp_path / "manifest.json").exists() and (tmp_path / "normal_seed1.csv").exists()
    first = json.loads((tmp_path / "normal_seed1.events.jsonl").read_text().splitlines()[0])
    assert first["authorised"] is True


def test_recovery_endpoint_after_approved_containment():
    app = create_app(autostart=False)
    rt = app.state.runtime
    with TestClient(app) as c:
        for _ in range(10):
            rt.step()
        c.post("/scenario/start", json={"name": "stuck_valve"})
        for _ in range(25):
            rt.step()
        iid = c.get("/incidents").json()[0]["id"]
        c.post(f"/incident/{iid}/approve-response")
        for _ in range(60):
            rt.step()
        body = c.get("/recovery").json()
        assert body["report"]["state"] == "recovered" and body["actions"]
        assert len(c.get("/scenarios").json()) == len(scenarios.SCENARIO_INFO)


def test_replay_only_records_normal_operation():
    e = warmed(n=60)
    e.start_scenario("unauthorised_valve_close")
    run(e, 30)  # plant is now reporting attack values
    e.start_scenario("replay_attack")  # hard-resets first, then replays what was recorded while normal
    t = run(e, 15).telemetry
    assert t.pressure < 2.6 and t.flow > 90
