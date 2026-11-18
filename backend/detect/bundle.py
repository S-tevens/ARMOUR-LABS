"""Trains and holds the detectors (owner: P3).

DATA SPLIT. Every run has its own random seed, and the sets below never overlap with the evaluation runs
(evaluation/protocol.py uses seeds 201+ and 301+). Splits are by RUN, never by random rows, so adjacent time windows cannot
leak between training and test.

  fit the models and invariants   : TRAIN_NORMAL (+ TRAIN_BENIGN: legitimate operating changes ARE normal operation)
  set each alert level            : VAL_NORMAL (+ VAL_BENIGN), held-out runs
  choose which model drives the
  live dashboard                  : SELECTION runs (attack, fault and benign scenarios on seeds 401-402). These are
                                    used ONLY for this choice, never for training and never in the test results
  never used for training         : any attack or fault run

For each model family two versions are trained so the effect of one choice is visible: "normal only" and "normal plus
legitimate changes". Neither ever sees an attack or a fault.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import numpy as np

from detect.alerting import first_alert, persist
from detect.features import WINDOW
from detect.invariants import Invariants
from detect.ml import AnomalyModel, IsolationForestModel, OneClassSVMModel, PCAModel
from detect.simulate import Run, simulate_run
from sim.scenarios import SCENARIO_INFO

TRAIN_NORMAL = (101, 102, 103, 104)
VAL_NORMAL = (105, 106)
TRAIN_DEMAND = ((121, 0.8), (122, 0.9), (123, 1.1), (124, 1.25), (125, 1.35))  # legitimate demand levels
VAL_DEMAND = ((126, 0.95), (127, 1.2))
TRAIN_BENIGN = (("planned_switching", 111), ("planned_switching", 112), ("cloud_cover", 113), ("cloud_cover", 114))
VAL_BENIGN = (("planned_switching", 115), ("cloud_cover", 116))
SELECTION_SEEDS = (401, 402)
NORMAL_TICKS = 900
SCENARIO_TICKS, SCENARIO_START, SCENARIO_STOP = 750, 300, 600
FAMILIES = (IsolationForestModel, PCAModel, OneClassSVMModel)


@dataclass
class Bundle:
    invariants: Invariants
    models: dict[str, AnomalyModel]  # trained on normal data plus legitimate changes
    pure: dict[str, AnomalyModel]  # trained on normal data only
    selected: str = "pca"
    selection: dict = field(default_factory=dict)
    info: dict = field(default_factory=dict)

    @property
    def ml(self) -> AnomalyModel:
        """The model that drives the live dashboard."""
        return self.models[self.selected]


def _runs(normal_seeds, scenarios, demand=()) -> list[Run]:
    runs = [simulate_run(None, s, NORMAL_TICKS) for s in normal_seeds]
    runs += [simulate_run(sc, s, SCENARIO_TICKS, SCENARIO_START, SCENARIO_STOP) for sc, s in scenarios]
    runs += [simulate_run(None, s, NORMAL_TICKS, demand=d) for s, d in demand]
    return runs


def _select(models: dict[str, AnomalyModel]) -> tuple[str, dict]:
    """Choose the live model from the selection runs: most attacks and faults detected, fewest false alarms on legitimate
    changes, then the shortest delay."""
    runs = {name: simulate_run(name, SELECTION_SEEDS[0], SCENARIO_TICKS, SCENARIO_START, SCENARIO_STOP) for name in SCENARIO_INFO}
    scores: dict[str, dict] = {}
    for key, m in models.items():
        detected = delays = false_alarm_runs = positives = 0
        for name, run in runs.items():
            alert = persist(m.score01(run.X) >= 0.8)
            alert[:WINDOW] = False
            lat = first_alert(alert, SCENARIO_START, SCENARIO_STOP)
            if SCENARIO_INFO[name]["kind"] in ("attack", "fault"):
                positives += 1
                if lat is not None:
                    detected += 1
                    delays += lat
            elif lat is not None and SCENARIO_INFO[name]["kind"] == "benign":
                false_alarm_runs += 1
        scores[key] = {"label": m.label, "detected": detected, "of": positives, "false_alarm_runs": false_alarm_runs,
                       "mean_delay_s": round(delays / detected, 1) if detected else None}
    best = max(scores, key=lambda k: (scores[k]["detected"] - 0.5 * scores[k]["false_alarm_runs"],
                                      -(scores[k]["mean_delay_s"] or 1e9)))
    return best, scores


def build_bundle() -> Bundle:
    t0 = time.perf_counter()
    train_normal = _runs(TRAIN_NORMAL, ())
    train_benign = _runs((), TRAIN_BENIGN, TRAIN_DEMAND)  # legitimate changes: switching, clouds and demand levels
    val_normal = _runs(VAL_NORMAL, ())
    val_benign = _runs((), VAL_BENIGN, VAL_DEMAND)
    stack = lambda runs: np.vstack([r.X[WINDOW:] for r in runs])  # the first WINDOW seconds are warm-up
    inv = Invariants().fit(train_normal + train_benign)
    models, pure = {}, {}
    for fam in FAMILIES:
        pure[fam.key] = fam(f"{fam.label}, normal data only").fit(stack(train_normal), [r.X[WINDOW:] for r in val_normal])
        models[fam.key] = fam(f"{fam.label}, normal data plus legitimate changes").fit(
            stack(train_normal + train_benign), [r.X[WINDOW:] for r in val_normal + val_benign])
    selected, selection = _select(models)
    info = {
        "train_normal_seeds": list(TRAIN_NORMAL), "train_benign": [list(x) for x in TRAIN_BENIGN], "train_demand_levels": [list(x) for x in TRAIN_DEMAND],
        "validation_normal_seeds": list(VAL_NORMAL), "validation_benign": [list(x) for x in VAL_BENIGN], "validation_demand_levels": [list(x) for x in VAL_DEMAND],
        "selection_seeds": list(SELECTION_SEEDS), "train_rows": int(len(stack(train_normal + train_benign))),
        "seconds_to_train": round(time.perf_counter() - t0, 1),
        "tolerances": {"power_balance_kw": round(inv.tol_balance, 1), "frequency_hz": round(inv.tol_freq, 3),
                       "voltage_pu": round(inv.tol_volt, 4), "solar_kw": round(inv.tol_pv, 1)},
    }
    return Bundle(inv, models, pure, selected, selection, info)


_lock = threading.Lock()
_bundle: Bundle | None = None


def get_bundle() -> Bundle:
    """Trains on first use (a few seconds) and then reuses the result."""
    global _bundle
    with _lock:
        if _bundle is None:
            _bundle = build_bundle()
        return _bundle


def peek_bundle() -> Bundle | None:
    """The trained bundle if it is ready, without waiting for training."""
    return _bundle
