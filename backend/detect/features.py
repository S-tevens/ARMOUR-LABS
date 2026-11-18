"""Streaming feature extraction for the ML detector and the physics checks (owner: P3).

The same class runs live (one call per tick) and offline (over a recorded run), so the features are identical in
both. Powers are divided by the substation's `scale`, so one model works for every substation in the city.

Only information a real monitoring system would have is used: the reported measurements, breaker states and the
network messages (including whether a source is on the allow-list). The ground-truth columns of the datasets and the
scenario labels are never used, and neither are the IED security flags, which the simulator sets from the scenario.
"""
from __future__ import annotations

from collections import deque

import numpy as np

from core.contracts import NetworkEvent, Telemetry

WINDOW = 10  # samples
EVENT_WINDOW_S = 10.0
STALE_AFTER_S = 5.0  # a message stamped this much older than its arrival looks replayed

RAW = ["frequency", "bus_voltage", "grid_import_kw", "pv_kw", "bess_kw", "bess_soc",
       "load_critical_kw", "load_noncritical_kw", "irradiance"]
POWER = {"grid_import_kw", "pv_kw", "bess_kw", "load_critical_kw", "load_noncritical_kw"}
BREAKERS = ["cb_main", "cb_pv", "cb_bess", "cb_crit", "cb_nc"]
FEATURE_NAMES = [
    *RAW, *BREAKERS, "n_open", "balance_residual",
    "std_frequency", "std_bus_voltage", "std_grid_import", "std_bess", "std_load_critical", "std_load_noncritical",
    "d_grid_import", "d_load_critical", "d_load_noncritical", "d_pv", "repeat_count",
    "net_unauthorised", "net_events", "net_stale",
]
INDEX = {n: i for i, n in enumerate(FEATURE_NAMES)}

# readable names for explanations
FEATURE_LABELS = {
    "frequency": "frequency", "bus_voltage": "bus voltage", "grid_import_kw": "utility import", "pv_kw": "solar output",
    "bess_kw": "battery power", "bess_soc": "battery charge", "load_critical_kw": "hospital load",
    "load_noncritical_kw": "campus load", "irradiance": "irradiance",
    "cb_main": "main breaker", "cb_pv": "solar breaker", "cb_bess": "battery breaker", "cb_crit": "hospital breaker",
    "cb_nc": "campus breaker", "n_open": "number of open breakers", "balance_residual": "power balance",
    "std_frequency": "frequency variation", "std_bus_voltage": "voltage variation", "std_grid_import": "import variation",
    "std_bess": "battery variation", "std_load_critical": "hospital load variation", "std_load_noncritical": "campus load variation",
    "d_grid_import": "import change", "d_load_critical": "hospital load change", "d_load_noncritical": "campus load change",
    "d_pv": "solar change", "repeat_count": "repeated readings",
    "net_unauthorised": "unauthorised messages", "net_events": "message rate", "net_stale": "stale messages",
}


class FeatureExtractor:
    def __init__(self, scale: float = 1.0) -> None:
        self.scale = max(scale, 1e-6)
        self._hist: deque[dict[str, float]] = deque(maxlen=WINDOW)
        self._events: deque[tuple[float, bool, float]] = deque()  # (arrival time, authorised, message timestamp)

    @property
    def ready(self) -> bool:
        """True once the rolling window is full. Detectors do not score during warm-up, live or offline."""
        return len(self._hist) >= WINDOW

    def reset(self) -> None:
        self._hist.clear()
        self._events.clear()

    def update(self, obs: Telemetry, events: list[NetworkEvent]) -> np.ndarray:
        s = self.scale
        cur = {n: (getattr(obs, n) / s if n in POWER else float(getattr(obs, n))) for n in RAW}
        self._hist.append(cur)
        h = self._hist

        def col(name: str) -> np.ndarray:
            return np.fromiter((x[name] for x in h), dtype=float, count=len(h))

        for e in events:
            self._events.append((obs.t, e.authorised, e.t))
        while self._events and obs.t - self._events[0][0] > EVENT_WINDOW_S:
            self._events.popleft()

        breakers = [float(getattr(obs, b)) for b in BREAKERS]
        balance = cur["grid_import_kw"] - (cur["load_critical_kw"] + cur["load_noncritical_kw"] - cur["pv_kw"] - cur["bess_kw"])
        tuples = [(x["frequency"], x["grid_import_kw"], x["pv_kw"]) for x in h]
        repeats = sum(1 for a, b in zip(tuples, tuples[1:]) if a == b)

        def delta(name: str) -> float:
            c = col(name)
            return float(c[-1] - c[:-1].mean()) if len(c) > 1 else 0.0

        vec = [
            *[cur[n] for n in RAW], *breakers, float(len(breakers) - sum(breakers)), balance,
            float(col("frequency").std()), float(col("bus_voltage").std()), float(col("grid_import_kw").std()),
            float(col("bess_kw").std()), float(col("load_critical_kw").std()), float(col("load_noncritical_kw").std()),
            delta("grid_import_kw"), delta("load_critical_kw"), delta("load_noncritical_kw"), delta("pv_kw"), float(repeats),
            float(sum(1 for _, ok, _ in self._events if not ok)), float(len(self._events)),
            float(sum(1 for arr, _, ts in self._events if arr - ts > STALE_AFTER_S)),
        ]
        return np.asarray(vec, dtype=float)
