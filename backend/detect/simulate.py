"""Labelled simulator runs for training and evaluation (owner: P3).

One run = the substation simulated for `ticks` seconds, with an optional scenario active from `start` to `stop`.
Per tick it records what a monitoring system would see (reported telemetry, network events), the baseline scores, the
twin's residuals, and the streamed features, plus the ground-truth labels, which are used ONLY to score the detectors.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from core.contracts import NetworkEvent, Telemetry
from detect.features import FeatureExtractor
from detect.threshold import ThresholdDetector
from sim.engine import SimulationEngine
from sim.plant import PlantParams
from twin.twin import GridTwin


@dataclass
class Run:
    scenario: str
    seed: int
    kind: str  # normal | attack | fault | benign
    ticks: int
    start: int
    stop: int
    obs: list[Telemetry] = field(default_factory=list)
    events: list[list[NetworkEvent]] = field(default_factory=list)
    active: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool))
    is_anomaly: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool))
    is_attack: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool))
    network: np.ndarray = field(default_factory=lambda: np.zeros(0))
    process: np.ndarray = field(default_factory=lambda: np.zeros(0))
    twin: np.ndarray = field(default_factory=lambda: np.zeros(0))
    X: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))


def simulate_run(scenario: str | None, seed: int, ticks: int = 900, start: int = 300, stop: int = 600,
                 params: PlantParams | None = None, demand: float = 1.0) -> Run:
    """demand: a legitimate demand level (1.0 is the base case). The forecast is known to the twin, like the clock."""
    eng = SimulationEngine(seed, params)
    eng.plant.load_scale = demand
    twin = GridTwin(params)
    twin.demand_factor = demand
    det = ThresholdDetector()
    fx = FeatureExtractor((params or PlantParams()).scale)
    run = Run(scenario or "normal", seed, "normal", ticks, start, stop)
    act, anom, att, net, proc, tw, X = [], [], [], [], [], [], []
    for i in range(ticks):
        if scenario and i == start:
            eng.start_scenario(scenario)
        if scenario and i == stop:
            eng.stop_scenario()
        gt = eng.ground_truth()
        if gt["active"]:
            run.kind = gt["kind"]
        r = eng.step()
        twin.sync(eng.command_log)
        ts = twin.compute(r.telemetry)
        sc = det.score(r.telemetry, ts, r.events)
        run.obs.append(r.telemetry)
        run.events.append(r.events)
        act.append(gt["active"]); anom.append(gt["is_anomaly"]); att.append(gt["is_attack"])
        net.append(sc.network); proc.append(sc.process); tw.append(sc.twin)
        X.append(fx.update(r.telemetry, r.events))
    run.active, run.is_anomaly, run.is_attack = np.array(act), np.array(anom), np.array(att)
    run.network, run.process, run.twin, run.X = np.array(net), np.array(proc), np.array(tw), np.vstack(X)
    return run
