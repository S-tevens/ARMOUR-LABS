import json

from fastapi.testclient import TestClient

from api.app import create_app
from core.contracts import IedStatus, Telemetry
from detect.threshold import ThresholdDetector
from sim import scenarios
from sim.dataset import COLUMNS, generate_run, write_dataset
from sim.engine import SimulationEngine
from sim.recovery import RecoveryVerifier
from twin.twin import GridTwin


def run(e, n):
    last = None
    for _ in range(n):
        last = e.step()
    return last


def warmed(seed=1, n=40):
    e = SimulationEngine(seed)
    run(e, n)
    return e


def pipeline(seed, scenario, pre=60, post=150):
    """Simulator -> twin -> baseline detector. Returns (first alert delay or None, max twin residual, rows)."""
    e, tw, d = SimulationEngine(seed), GridTwin(), ThresholdDetector()
    first, worst, rows = None, 0.0, []
    for i in range(pre + post):
        if scenario and i == pre:
            e.start_scenario(scenario)
        r = e.step()
        tw.sync(e.command_log)
        st = tw.compute(r.telemetry)
        sc = d.score(r.telemetry, st, r.events)
        rows.append((r.telemetry, st, sc))
        if i >= pre:
            worst = max(worst, max(abs(v) for v in st.norm_residual.values()))
            if first is None and d.is_alert(sc):
                first = i - pre
    return first, worst, rows


def nominal_obs(**kw):
    base = dict(t=0, tick=0, frequency=50.0, bus_voltage=1.0, grid_import_kw=320, pv_kw=375, bess_kw=0, bess_soc=60,
                load_critical_kw=400, load_noncritical_kw=300, irradiance=750,
                cb_main=True, cb_pv=True, cb_bess=True, cb_crit=True, cb_nc=True, ied_status=IedStatus())
    base.update(kw)
    return Telemetry(**base)


# ---------------- scenarios ----------------
def test_every_scenario_runs_and_has_metadata():
    for name, info in scenarios.SCENARIO_INFO.items():
        e = warmed()
        e.start_scenario(name)
        run(e, 30)
        assert info["kind"] in ("attack", "fault", "benign") and info["group"] in ("core", "extra")
        e.stop_scenario()
        run(e, 60)


def test_planned_switching_is_authorised_benign_and_matches_a_real_trip_physically():
    e = warmed()
    e.start_scenario("planned_switching")
    r = e.step()
    assert all(x.authorised for x in r.events)
    assert e.ground_truth()["is_anomaly"] is False
    assert e.command_log and e.command_log[-1].register == "CB_NC"
    t = run(e, 10).telemetry
    assert t.cb_nc is False and abs(t.load_noncritical_kw) < 8


def test_stuck_breaker_stays_closed_and_has_no_network_evidence():
    e = warmed()
    e.start_scenario("stuck_breaker")
    events = []
    for _ in range(25):
        events += e.step().events
    t = e.plant.observe()
    assert t.cb_nc is True and t.load_noncritical_kw > 250  # commanded open, still carrying load
    assert all(x.authorised for x in events)  # the only command was legitimate
    assert e.ground_truth()["is_attack"] is False


def test_pv_inverter_trip_and_cloud_cover_effects():
    e = warmed()
    e.start_scenario("pv_inverter_trip")
    t = run(e, 10).telemetry
    assert t.pv_kw < 10 and t.irradiance > 500
    e2 = warmed()
    e2.start_scenario("cloud_cover")
    t2 = run(e2, 60).telemetry
    assert t2.pv_kw < 160 and t2.irradiance < 300  # PV fell, and the weather station explains it


def test_replay_masks_readings_but_not_the_breaker_and_duplicates_seq():
    e = warmed(n=60)
    seen_before = {x.seq for x in e.event_log}
    e.start_scenario("replay_attack")
    events = []
    for _ in range(20):
        r = e.step()
        events += r.events
    t = r.telemetry
    assert t.cb_crit is False  # the manipulation is visible in the breaker state
    assert t.load_critical_kw > 350  # but the replayed hospital load still looks normal
    assert e.plant.true_state()["load_critical_kw"] == 0.0
    dupes = [x for x in events if x.seq in seen_before and not x.authorised]
    assert dupes and all(x.t < e.plant.t - 10 for x in dupes)  # stale + duplicated sequence numbers


def test_replay_only_records_normal_operation():
    e = warmed(n=60)
    e.start_scenario("unauthorised_breaker_trip")
    run(e, 30)
    e.start_scenario("replay_attack")  # hard-resets first, then replays what was recorded while normal
    t = run(e, 15).telemetry
    assert t.load_critical_kw > 350 and 49.9 < t.frequency < 50.1


def test_dos_floods_events_drops_heartbeats_and_makes_measurements_stale():
    e = warmed()
    e.start_scenario("dos_flood")
    events, stale, prev = [], 0, None
    for _ in range(40):
        r = e.step()
        events += r.events
        cur = (r.telemetry.grid_import_kw, r.telemetry.frequency)
        stale += prev == cur
        prev = cur
    assert sum(1 for x in events if not x.authorised) >= 25 * 40
    assert not any(x.authorised and x.dst == "IED-03" for x in events)
    assert stale >= 5


# ---------------- digital twin ----------------
def test_twin_is_quiet_in_normal_operation_across_seeds():
    for seed in (1, 2, 3):
        first, worst, _ = pipeline(seed, None, pre=0, post=600)
        assert first is None and worst < 3.0, (seed, worst)


def test_twin_explains_benign_changes_but_flags_faults_and_attacks():
    for name in ("planned_switching", "cloud_cover"):
        first, worst, _ = pipeline(1, name)
        assert first is None and worst < 3.5, (name, worst)  # benign: explained, no alert
    for name in ("unauthorised_breaker_trip", "false_data_injection", "stuck_breaker", "pv_inverter_trip", "replay_attack"):
        first, worst, _ = pipeline(1, name)
        assert first is not None and first <= 2 and worst > 8, (name, first, worst)


def test_twin_catches_replay_after_the_network_evidence_expires():
    _, _, rows = pipeline(1, "replay_attack")
    late = rows[60 + 40 :]  # well past the 10 s network window
    assert all(sc.network == 0.0 for _, _, sc in late)
    assert all(sc.twin >= 0.8 for _, _, sc in late)  # still flagged through breaker state and battery response


def test_twin_ignores_observed_breaker_state_when_forming_expectations():
    e = warmed()
    tw1, tw2 = GridTwin(), GridTwin()
    obs = e.step().telemetry
    a = tw1.compute(obs)
    b = tw2.compute(obs.model_copy(update={"cb_crit": False, "cb_main": False, "cb_pv": False}))
    assert a.expected == b.expected  # expectations come from the authorised command log only
    assert b.residual["breaker_mismatch"] == 3.0 and a.residual["breaker_mismatch"] == 0.0


def test_twin_only_follows_authorised_commands():
    e = warmed()
    tw = GridTwin()
    e.start_scenario("unauthorised_breaker_trip")  # emits an UNAUTHORISED event, not a command
    run(e, 3)
    tw.sync(e.command_log)
    assert tw.breakers["cb_crit"] is True
    e2 = warmed()
    e2.start_scenario("planned_switching")
    tw2 = GridTwin()
    tw2.sync(e2.command_log)
    assert tw2.breakers["cb_nc"] is False


def test_subtle_variants_are_stealthy_for_the_baseline_but_the_ramp_is_eventually_caught():
    first, _, _ = pipeline(1, "fdi_small")
    assert first is None  # small bias, no network trace: missed by design
    first, _, _ = pipeline(1, "fdi_slow_ramp")
    assert first is not None and first > 10


# ---------------- containment and recovery ----------------
def test_containment_is_staged_and_recovers_each_scenario():
    for name in ("unauthorised_breaker_trip", "false_data_injection", "sensor_drift", "stuck_breaker",
                 "pv_inverter_trip", "dos_flood", "replay_attack"):
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
        assert all(e.plant.breakers.values()) and not e.plant.stuck, name


def test_containment_reconnects_the_hospital_first():
    e = warmed()
    e.start_scenario("unauthorised_breaker_trip")
    run(e, 20)
    e.begin_containment()
    run(e, 8)
    actions = [a["action"] for a in e.containment_log]
    assert any("Blocked source" in a for a in actions)
    assert any("hospital feeder breaker" in a for a in actions)
    assert e.command_log[-1].register == "BESS_MODE" and e.command_log[-1].value == "AUTO"


def test_recovery_verifier_requires_dwell_and_can_be_unresolved():
    v = RecoveryVerifier(dwell=10, timeout=30)
    v.start(0.0)
    for i in range(1, 9):
        assert v.update(nominal_obs(t=float(i))).state == "recovering"  # dwell not yet met
    assert v.update(nominal_obs(t=11.0)).state == "recovered"

    bad = dict(frequency=49.0)
    v2 = RecoveryVerifier(dwell=10, timeout=30)
    v2.start(0.0)
    states = [v2.update(nominal_obs(t=float(i), **bad)).state for i in range(1, 40)]
    assert states[0] == "recovering" and states[-1] == "unresolved"
    # an open breaker is never "recovered", even with perfect numbers
    v3 = RecoveryVerifier(dwell=2, timeout=30)
    v3.start(0.0)
    assert all(v3.update(nominal_obs(t=float(i), cb_crit=False)).state == "recovering" for i in range(1, 10))


# ---------------- dataset and API ----------------
def test_same_seed_gives_identical_runs():
    a, ea = generate_run("replay_attack", 5, ticks=200, start=50, stop=150)
    b, eb = generate_run("replay_attack", 5, ticks=200, start=50, stop=150)
    assert a == b and ea == eb


def test_dataset_labels_and_files(tmp_path):
    rows, _ = generate_run("unauthorised_breaker_trip", 3, ticks=200, start=50, stop=150)
    assert set(rows[0]) == set(COLUMNS)
    assert [r["is_attack"] for r in rows[:50]] == [0] * 50
    assert all(r["is_attack"] == 1 for r in rows[50:150]) and all(r["is_attack"] == 0 for r in rows[150:])
    rows, _ = generate_run("planned_switching", 3, ticks=200, start=50, stop=150)
    assert all(r["is_anomaly"] == 0 and r["kind"] == "benign" for r in rows[50:150])
    rows, _ = generate_run("stuck_breaker", 3, ticks=200, start=50, stop=150)
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
        for _ in range(20):
            rt.step()
        c.post("/scenario/start", json={"name": "stuck_breaker"})
        for _ in range(25):
            rt.step()
        iid = c.get("/incidents").json()[0]["id"]
        c.post(f"/incident/{iid}/approve-response")
        for _ in range(60):
            rt.step()
        body = c.get("/recovery").json()
        assert body["report"]["state"] == "recovered" and body["actions"]
        assert len(c.get("/scenarios").json()) == len(scenarios.SCENARIO_INFO)
