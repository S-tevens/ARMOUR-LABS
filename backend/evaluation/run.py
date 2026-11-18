"""Detector evaluation (owner: P3).

Usage (from backend/):  python -m evaluation.run      writes evaluation/results.json

PROTOCOL
  Held-out test runs only. Seeds never used for training, calibration or model selection (see detect/bundle.py):
    normal operation : seeds 201-203, 900 s each, plus seeds 211-213 at other demand levels (0.85, 1.15, 1.3 times)
    every scenario   : seeds 301-303, 750 s each; the scenario is active from t=300 s to t=600 s, then the substation is
                       reset and run for another 150 s
  An alert is a detector score >= 0.8 for two consecutive seconds (the same rule for every detector).
  Labels (used only to score, never as detector inputs):
    positive : an attack or a fault is active
    negative : normal operation, a legitimate or natural change (planned switching, passing clouds), and the time before
               a scenario starts. The 30 s after a scenario ends is excluded (the process is still settling).
  Reported: tick-level confusion matrix, precision, recall, F1, false-positive rate; per-run detection and delay;
  false alarms per hour; and per-scenario results for every detector.

SOURCE. The custom simulator, not a public dataset. See the limitations list in the output.
"""
from __future__ import annotations

import datetime
import json
import time
from pathlib import Path

import numpy as np

from detect.alerting import first_alert, persist
from detect.features import WINDOW
from detect.bundle import SCENARIO_START, SCENARIO_STOP, SCENARIO_TICKS, NORMAL_TICKS, get_bundle
from detect.simulate import simulate_run
from sim.scenarios import SCENARIO_INFO

RESULTS = Path(__file__).parent / "results.json"
TEST_NORMAL_SEEDS = (201, 202, 203)
TEST_NORMAL_DEMAND = ((211, 0.85), (212, 1.15), (213, 1.3))  # normal operation at other (legitimate) demand levels
TEST_SCENARIO_SEEDS = (301, 302, 303)
GRACE_S = 30

DETECTORS = [
    ("limits", "Fixed limits", "baseline", "Frequency, voltage and battery charge against engineering limits. The simple threshold baseline."),
    ("network", "Unauthorised-message rule", "baseline", "Alerts when a message from a source that is not on the allow-list is seen."),
    ("twin", "Digital twin", "digital twin", "Distance between the readings and what the authorised commands say should be happening."),
    ("invariants", "Physics checks", "physics", "Consistency relations between signals (power balance, frequency, breaker and load, solar and weather)."),
    ("iforest", "Isolation Forest", "machine learning", "Tree-based unsupervised anomaly detector."),
    ("ocsvm", "One-class SVM", "machine learning", "Unsupervised boundary around normal behaviour."),
    ("pca_pure", "Autoencoder, normal data only", "machine learning", "The linear autoencoder trained without any legitimate operating changes."),
    ("pca", "Linear autoencoder (PCA)", "machine learning", "Unsupervised: learns how signals normally relate and flags readings that break those relations. Drives the live dashboard."),
    ("combined", "Combined", "fusion", "Fixed limits, unauthorised-message rule, twin, physics checks and the autoencoder, any of which can raise an alert."),
]

LIMITATIONS = [
    "Everything is measured on the project's own simulator, not on a public dataset or a real grid. The same simulator makes the training and test data, so these numbers show that the pipeline works, not how it would perform in the real world.",
    "The physics checks and the autoencoder exploit relations the simple simulated plant follows almost exactly. A real grid is noisier, so real tolerances are wider and detection would be weaker.",
    "Only 3 runs per scenario: detection rates are indicative, with wide uncertainty, and no confidence intervals are given.",
    "Tick-level precision and recall are dominated by the many quiet seconds. Detection per run, delay and false alarms per hour are the more meaningful numbers.",
    "A stuck breaker is physically consistent with the readings. Only the twin, which knows the command was authorised but did not take effect, can catch it.",
    "The detectors were developed while looking at the main test runs (to find modelling bugs), so those numbers are a development estimate. The fresh-seed check uses seeds that were never looked at and is the cleaner figure. No threshold or model was tuned to improve either set of numbers.",
    "A different seed changes only the measurement noise, because the scenarios themselves are deterministic. Matching results on new seeds therefore show robustness to noise, not to new kinds of attack the detectors have never been designed for.",
    "Models were trained and calibrated only on normal operation and legitimate changes. They never saw an attack or fault, and the model driving the dashboard was chosen on separate validation runs, not on these test runs.",
]


def _alerts(bundle, run) -> dict[str, np.ndarray]:
    inv = bundle.invariants
    a = {
        "limits": persist(run.process >= 0.8),
        "network": persist(run.network >= 0.8),
        "twin": persist(run.twin >= 0.8),
        "invariants": persist(np.array([inv.score(inv.ratios(o, x)) >= 0.8 for o, x in zip(run.obs, run.X)])),
    }
    for key in ("iforest", "ocsvm", "pca"):
        a[key] = persist(bundle.models[key].score01(run.X) >= 0.8)
    a["pca_pure"] = persist(bundle.pure["pca"].score01(run.X) >= 0.8)
    a["combined"] = a["network"] | a["limits"] | a["twin"] | a["invariants"] | a["pca"]
    for v in a.values():
        v[:WINDOW] = False  # warm-up: the feature window is not full yet, as in the live system
    return a


def _ratio(n, d):
    return round(n / d, 3) if d else None


def run_evaluation(progress=None, seed_offset: int = 0) -> dict:
    """seed_offset shifts every test seed, to evaluate on runs that were never looked at during development."""
    t0 = time.perf_counter()
    bundle = get_bundle()
    say = progress or (lambda *_: None)

    runs = []
    for s in TEST_NORMAL_SEEDS:
        runs.append(simulate_run(None, s + seed_offset, NORMAL_TICKS))
    for s, d in TEST_NORMAL_DEMAND:
        runs.append(simulate_run(None, s + seed_offset, NORMAL_TICKS, demand=d))
    for name in SCENARIO_INFO:
        for s in TEST_SCENARIO_SEEDS:
            runs.append(simulate_run(name, s + seed_offset, SCENARIO_TICKS, SCENARIO_START, SCENARIO_STOP))
            say(f"simulated {name} seed {s + seed_offset}")

    keys = [k for k, *_ in DETECTORS]
    tick = {k: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for k in keys}
    neg_ticks = 0
    fa_events = {k: 0 for k in keys}
    delays = {k: [] for k in keys}
    detected = {k: 0 for k in keys}
    positives = 0
    benign_runs = 0
    benign_alarmed = {k: 0 for k in keys}
    scen = {n: {k: {"detected": 0, "delays": []} for k in keys} for n in SCENARIO_INFO}
    scen_runs = {n: 0 for n in SCENARIO_INFO}

    for run in runs:
        alerts = _alerts(bundle, run)
        pos = run.is_anomaly & run.active
        valid = np.ones(run.ticks, dtype=bool)
        if run.scenario != "normal":
            valid[run.stop: run.stop + GRACE_S] = False  # the process is still settling after the scenario ends
        neg = (~pos) & valid
        neg_ticks += int(neg.sum())
        kind = run.kind
        if run.scenario != "normal":
            scen_runs[run.scenario] += 1
            if kind == "benign":
                benign_runs += 1
            elif kind in ("attack", "fault"):
                positives += 1
        for k in keys:
            a = alerts[k]
            tick[k]["tp"] += int((a & pos & valid).sum())
            tick[k]["fn"] += int((~a & pos & valid).sum())
            tick[k]["fp"] += int((a & neg).sum())
            tick[k]["tn"] += int((~a & neg).sum())
            edges = a & ~np.concatenate([[False], a[:-1]]) & neg
            fa_events[k] += int(edges.sum())
            if run.scenario == "normal":
                continue
            lat = first_alert(a, run.start, run.stop)
            if kind in ("attack", "fault"):
                if lat is not None:
                    detected[k] += 1
                    delays[k].append(lat)
                    scen[run.scenario][k]["detected"] += 1
                    scen[run.scenario][k]["delays"].append(lat)
            elif kind == "benign" and lat is not None:
                benign_alarmed[k] += 1
                scen[run.scenario][k]["detected"] += 1  # for a benign scenario this counts false alarms

    hours = neg_ticks / 3600.0
    detectors = []
    for k, label, family, desc in DETECTORS:
        t = tick[k]
        prec, rec = _ratio(t["tp"], t["tp"] + t["fp"]), _ratio(t["tp"], t["tp"] + t["fn"])
        f1 = round(2 * prec * rec / (prec + rec), 3) if prec and rec else (0.0 if rec == 0 or prec == 0 else None)
        detectors.append({
            "key": k, "label": label, "family": family, "description": desc,
            "tick": {**t, "precision": prec, "recall": rec, "f1": f1, "fpr": _ratio(t["fp"], t["fp"] + t["tn"])},
            "runs": {"detected": detected[k], "total": positives, "rate": _ratio(detected[k], positives),
                     "median_delay_s": float(np.median(delays[k])) if delays[k] else None,
                     "mean_delay_s": round(float(np.mean(delays[k])), 1) if delays[k] else None},
            "false_alarms": {"events": fa_events[k], "per_hour": round(fa_events[k] / hours, 2) if hours else None,
                             "benign_runs_alarmed": benign_alarmed[k], "benign_runs": benign_runs},
        })

    scenarios = []
    for n, info in SCENARIO_INFO.items():
        scenarios.append({
            "name": n, "label": info["label"], "kind": info["kind"], "runs": scen_runs[n],
            "per_detector": {
                k: {"detected": scen[n][k]["detected"], "runs": scen_runs[n],
                    "median_delay_s": float(np.median(scen[n][k]["delays"])) if scen[n][k]["delays"] else None}
                for k in keys
            },
        })

    selected = bundle.selected
    return {
        "status": "ok",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "duration_s": round(time.perf_counter() - t0, 1),
        "source": "custom simulator (not a public dataset)",
        "protocol": {
            "test_normal_seeds": [s + seed_offset for s in TEST_NORMAL_SEEDS],
            "test_normal_demand_levels": [[s + seed_offset, d] for s, d in TEST_NORMAL_DEMAND],
            "test_scenario_seeds": [s + seed_offset for s in TEST_SCENARIO_SEEDS],
            "normal_run_s": NORMAL_TICKS, "scenario_run_s": SCENARIO_TICKS,
            "scenario_active_s": [SCENARIO_START, SCENARIO_STOP], "grace_after_scenario_s": GRACE_S,
            "alert_rule": "score at or above 0.8 for two consecutive seconds",
            "test_runs": len(runs), "negative_seconds": neg_ticks, "negative_hours": round(hours, 2),
            "attack_or_fault_runs": positives, "benign_runs": benign_runs,
        },
        "training": {**bundle.info, "selected_model": selected, "selection": bundle.selection,
                     "alert_levels": {k: {"median": round(m.med, 3), "alert": round(m.thr, 3)} for k, m in bundle.models.items()}},
        "detectors": detectors,
        "scenarios": scenarios,
        "limitations": LIMITATIONS,
    }


FRESH_OFFSET = 1000


def full_evaluation(progress=None) -> dict:
    """The main evaluation plus a fresh-seed check on runs never looked at during development."""
    res = run_evaluation(progress)
    fresh = run_evaluation(progress, seed_offset=FRESH_OFFSET)
    res["fresh_check"] = {
        "note": "The same protocol on seeds that were never looked at while the detectors were being developed, so it is the cleaner estimate.",
        "seed_offset": FRESH_OFFSET, "protocol": fresh["protocol"], "detectors": fresh["detectors"], "scenarios": fresh["scenarios"],
    }
    res["duration_s"] = round(res["duration_s"] + fresh["duration_s"], 1)
    return res


def main() -> None:
    res = full_evaluation(progress=lambda m: print(" ", m))
    RESULTS.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(f"\nwrote {RESULTS} in {res['duration_s']} s ({res['protocol']['test_runs']} test runs)\n")
    print(f"{'detector':34}{'recall':>8}{'precision':>10}{'F1':>7}{'runs found':>12}{'median delay':>14}{'false alarms/h':>16}{'benign alarmed':>16}")
    for d in res["detectors"]:
        t, r, f = d["tick"], d["runs"], d["false_alarms"]
        fmt = lambda x: "n/a" if x is None else f"{x:.2f}"
        print(f"{d['label']:34}{fmt(t['recall']):>8}{fmt(t['precision']):>10}{fmt(t['f1']):>7}{r['detected']:>7}/{r['total']:<4}{('-' if r['median_delay_s'] is None else str(r['median_delay_s'])+' s'):>14}{f['per_hour']:>16}{f['benign_runs_alarmed']:>11}/{f['benign_runs']}")


if __name__ == "__main__":
    main()
