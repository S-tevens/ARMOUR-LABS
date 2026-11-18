"""The ML and physics detectors, the evaluation protocol and the live integration."""
import json
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.city_runtime import CityRuntime
from api.runtime import Runtime
from detect import bundle as bundle_mod
from detect.alerting import first_alert, persist
from detect.bundle import get_bundle, peek_bundle
from detect.features import FEATURE_NAMES
from detect.simulate import simulate_run
from evaluation import run as ev
from evaluation.run import RESULTS
from sim.plant import PlantParams


@pytest.fixture(scope="module")
def bundle():
    return get_bundle()


def alerts(bundle, run):
    inv = bundle.invariants
    return (
        persist(np.array([inv.score(inv.ratios(o, x)) >= 0.8 for o, x in zip(run.obs, run.X)])),
        persist(bundle.ml.score01(run.X) >= 0.8),
    )


def sized(scale):
    return PlantParams(
        load_crit_base=400 * scale, load_crit_amp=30 * scale, load_nc_base=300 * scale, load_nc_amp=40 * scale,
        pv_rated_kw=500 * scale, bess_pmax_kw=250 * scale, bess_cap_kwh=200 * scale, import_target_kw=320 * scale,
        load_phase=0.9 if scale != 1.0 else 0.0,
    )


# ---------------- features ----------------
def test_features_are_deterministic_and_complete():
    a, b = simulate_run(None, 5, 80), simulate_run(None, 5, 80)
    assert a.X.shape == (80, len(FEATURE_NAMES)) and np.array_equal(a.X, b.X)
    assert not np.isnan(a.X).any()


def test_features_do_not_use_labels_ground_truth_or_the_scenario_driven_security_flags():
    names = set(FEATURE_NAMES)
    assert not any(n.startswith("true_") or n in {"is_attack", "is_anomaly", "scenario", "kind", "active"} for n in names)
    assert not any(n.startswith("ied") for n in names)


def test_features_are_comparable_across_substation_sizes():
    xs = [simulate_run(None, 7, 300, params=sized(s)).X for s in (0.6, 2.2)]
    for name in ("grid_import_kw", "load_critical_kw", "pv_kw", "bus_voltage", "frequency"):
        i = FEATURE_NAMES.index(name)
        m0, m1 = xs[0][:, i].mean(), xs[1][:, i].mean()
        assert abs(m0 - m1) <= 0.15 * abs(m1) + 1e-3, (name, m0, m1)


# ---------------- alert rule ----------------
def test_alert_rule_needs_two_consecutive_ticks():
    a = persist(np.array([0, 1, 0, 1, 1, 1, 0], dtype=bool))
    assert list(a) == [False, False, False, False, True, True, False]
    assert first_alert(a, 2, 7) == 2 and first_alert(a, 0, 3) is None


# ---------------- physics checks ----------------
def test_physics_checks_are_quiet_in_normal_operation_and_legitimate_changes(bundle):
    inv = bundle.invariants
    for seed, demand in ((601, 1.0), (602, 0.85), (603, 1.3)):
        run = simulate_run(None, seed, 600, demand=demand)
        assert max(inv.score(inv.ratios(o, x)) for o, x in zip(run.obs, run.X)) < 0.8, (seed, demand)
    for sc in ("planned_switching", "cloud_cover"):
        a, _ = alerts(bundle, simulate_run(sc, 604, 750, 300, 600))
        assert not a.any(), sc


def test_physics_checks_catch_inconsistent_readings_and_say_why(bundle):
    expected = {"replay_attack": "feeder", "pv_inverter_trip": "solar", "false_data_injection": "frequency", "dos_flood": "repeating"}
    for sc, word in expected.items():
        run = simulate_run(sc, 605, 450, 300, 450)
        a, _ = alerts(bundle, run)
        lat = first_alert(a, 300, 450)
        assert lat is not None and lat <= 5, sc
        i = 300 + lat
        text = " ".join(bundle.invariants.explain(bundle.invariants.ratios(run.obs[i], run.X[i]), run.obs[i], run.X[i]))
        assert word in text.lower(), (sc, text)


def test_physics_check_tolerances_are_fitted_from_normal_data(bundle):
    t = bundle.info["tolerances"]
    assert 10 <= t["power_balance_kw"] <= 80 and 0.05 <= t["frequency_hz"] <= 0.2 and 0.008 <= t["voltage_pu"] <= 0.05


# ---------------- ML ----------------
def test_models_are_trained_selected_on_validation_and_calibrated(bundle):
    assert set(bundle.models) == {"iforest", "pca", "ocsvm"} and bundle.selected in bundle.models
    assert all(m.thr > m.med for m in bundle.models.values())
    sel = bundle.selection
    assert sel[bundle.selected]["detected"] == max(v["detected"] for v in sel.values())


def test_training_validation_selection_and_test_seeds_never_overlap():
    train = set(bundle_mod.TRAIN_NORMAL) | {s for _, s in bundle_mod.TRAIN_BENIGN} | {s for s, _ in bundle_mod.TRAIN_DEMAND}
    val = set(bundle_mod.VAL_NORMAL) | {s for _, s in bundle_mod.VAL_BENIGN} | {s for s, _ in bundle_mod.VAL_DEMAND}
    sel = set(bundle_mod.SELECTION_SEEDS)
    test = set(ev.TEST_NORMAL_SEEDS) | {s for s, _ in ev.TEST_NORMAL_DEMAND} | set(ev.TEST_SCENARIO_SEEDS)
    fresh = {s + ev.FRESH_OFFSET for s in test}
    groups = [train, val, sel, test, fresh]
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            assert not groups[i] & groups[j], (i, j)


def test_models_never_train_on_attacks_or_faults():
    from sim.scenarios import SCENARIO_INFO
    used = {sc for sc, _ in bundle_mod.TRAIN_BENIGN} | {sc for sc, _ in bundle_mod.VAL_BENIGN}
    assert used and all(SCENARIO_INFO[sc]["kind"] == "benign" for sc in used)


def test_ml_is_quiet_on_held_out_normal_operation_at_every_substation_size(bundle):
    for scale in (0.6, 1.0, 2.2):
        run = simulate_run(None, 610, 600, params=sized(scale))
        assert not persist(bundle.ml.score01(run.X) >= 0.8).any(), scale


def test_ml_detects_attacks_and_faults_fast_and_ignores_passing_clouds(bundle):
    for sc in ("unauthorised_breaker_trip", "false_data_injection", "replay_attack", "dos_flood", "pv_inverter_trip", "fdi_small"):
        _, ml = alerts(bundle, simulate_run(sc, 611, 450, 300, 450))
        lat = first_alert(ml, 300, 450)
        assert lat is not None and lat <= 5, (sc, lat)
    assert not alerts(bundle, simulate_run("cloud_cover", 612, 750, 300, 600))[1].any()


def test_ml_explanations_name_real_signals(bundle):
    run = simulate_run("pv_inverter_trip", 613, 340, 300, 340)
    names = [n for n, _ in bundle.ml.explain(run.X[330], k=3)]
    assert names and all(isinstance(n, str) and n for n in names)


# ---------------- live integration ----------------
def test_live_runtime_scores_are_real_and_quiet_when_nothing_is_wrong(bundle):
    rt = Runtime(seed=3, bundle=peek_bundle)
    seen = [m["data"] for _ in range(500) for m in rt.step() if m["type"] == "scores"]
    assert rt.incidents.incidents == {}
    assert max(s["ml"] for s in seen) < 0.8 and max(s["invariants"] for s in seen) < 0.8


def test_live_incident_carries_plain_evidence_from_the_detectors(bundle):
    rt = Runtime(seed=3, bundle=peek_bundle)
    for _ in range(30):
        rt.step()
    rt.engine.start_scenario("pv_inverter_trip")  # no network evidence: only the residuals and the ML/physics detectors see it
    for _ in range(10):
        rt.step()
    inc = next(iter(rt.incidents.incidents.values()))
    assert {"physics_check", "ml_anomaly"} <= {e.type for e in inc.evidence}
    assert inc.scores["invariants"] >= 0.8 and inc.scores["ml"] >= 0.8


def test_live_city_substations_stay_quiet_through_legitimate_demand_changes(bundle):
    c = CityRuntime(seed=42, city="synthetic", ml=True)
    for _ in range(200):
        c.step()
    c.engine.start_scenario("evening_peak")
    for _ in range(240):
        c.step()
    assert all(not u.incidents.incidents for u in c.units.values())


# ---------------- evaluation ----------------
def test_committed_results_are_internally_consistent():
    r = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert r["source"].startswith("custom simulator") and r["limitations"] and r["fresh_check"]["detectors"]
    for block in (r, r["fresh_check"]):
        by = {d["key"]: d for d in block["detectors"]}
        totals = set()
        for d in block["detectors"]:
            t = d["tick"]
            totals.add(t["tp"] + t["fp"] + t["fn"] + t["tn"])
            if t["tp"] + t["fp"]:
                assert t["precision"] == pytest.approx(t["tp"] / (t["tp"] + t["fp"]), abs=1e-3)
            assert t["recall"] == pytest.approx(t["tp"] / (t["tp"] + t["fn"]), abs=1e-3)
        assert len(totals) == 1  # every detector is scored on the same seconds
        comp = ("limits", "network", "twin", "invariants", "pca")
        assert by["combined"]["runs"]["detected"] >= max(by[k]["runs"]["detected"] for k in comp)  # an OR can only find more
        assert by["pca_pure"]["false_alarms"]["benign_runs_alarmed"] > by["pca"]["false_alarms"]["benign_runs_alarmed"]
        assert by["twin"]["runs"]["detected"] > 0 and by["iforest"]["runs"]["detected"] <= by["pca"]["runs"]["detected"]


def test_a_fresh_recompute_agrees_with_the_committed_numbers():
    fresh = ev.run_evaluation(seed_offset=2000)
    by = {d["key"]: d for d in fresh["detectors"]}
    saved = {d["key"]: d for d in json.loads(RESULTS.read_text(encoding="utf-8"))["detectors"]}
    assert fresh["protocol"]["test_runs"] == 39
    for k in ("twin", "invariants", "pca", "combined"):
        assert abs(by[k]["runs"]["detected"] - saved[k]["runs"]["detected"]) <= 1, k
    assert by["combined"]["false_alarms"]["per_hour"] <= 2.0


# ---------------- API ----------------
def test_metrics_endpoint_serves_results_and_runs_in_the_background(tmp_path, monkeypatch):
    path = tmp_path / "results.json"
    app = create_app(autostart=False, evaluation_path=path)
    with TestClient(app) as c:
        assert c.get("/metrics").json()["status"] == "not_computed"
        stub = {"detectors": [], "protocol": {}, "limitations": ["x"]}
        monkeypatch.setattr("evaluation.service.full_evaluation", lambda progress=None: stub)
        assert c.post("/metrics/run").json() == {"started": True}
        body = {}
        for _ in range(100):
            body = c.get("/metrics").json()
            if body["status"] == "ok":
                break
            time.sleep(0.05)
        assert body["status"] == "ok" and body["limitations"] == ["x"] and path.exists()
    with TestClient(create_app(autostart=False)) as c:
        committed = c.get("/metrics").json()
    assert committed["status"] == "ok" and len(committed["detectors"]) == 9 and committed["training"]["selected_model"] == "pca"
