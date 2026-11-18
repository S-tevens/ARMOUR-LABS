"""Recovery verification (owner: P2).

"Recovered" is only reported when every monitored variable has stayed inside its tolerance, with
Valve 1 open and both pumps running, for `dwell` consecutive seconds. Otherwise the state is
"recovering", or "unresolved" once `timeout` seconds pass without recovery.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from core.contracts import Telemetry

TOLERANCE: dict[str, tuple[float, float]] = {
    "pressure": (1.8, 2.5),
    "flow": (95.0, 125.0),
    "tank1_level": (52.0, 72.0),
    "tank2_level": (38.0, 58.0),
}
DWELL_S = 10.0
TIMEOUT_S = 90.0


@dataclass
class VarCheck:
    name: str
    value: float
    lo: float
    hi: float
    in_range: bool
    improving: bool


@dataclass
class RecoveryReport:
    state: str  # idle | recovering | recovered | unresolved
    elapsed: float = 0.0
    seconds_in_range: float = 0.0
    dwell: float = DWELL_S
    valve_open: bool = True
    pumps_on: bool = True
    variables: list[VarCheck] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _distance(v: float, lo: float, hi: float) -> float:
    return 0.0 if lo <= v <= hi else min(abs(v - lo), abs(v - hi))


class RecoveryVerifier:
    def __init__(self, tolerance=TOLERANCE, dwell: float = DWELL_S, timeout: float = TIMEOUT_S) -> None:
        self.tolerance = tolerance
        self.dwell = dwell
        self.timeout = timeout
        self.state = "idle"
        self._t0 = 0.0
        self._in_range_since: float | None = None
        self._prev: dict[str, float] = {}

    def start(self, t: float) -> None:
        self.state = "recovering"
        self._t0 = t
        self._in_range_since = None
        self._prev = {}

    def update(self, obs: Telemetry) -> RecoveryReport:
        if self.state == "idle":
            return RecoveryReport(state="idle", dwell=self.dwell)
        checks: list[VarCheck] = []
        for name, (lo, hi) in self.tolerance.items():
            v = float(getattr(obs, name))
            d = _distance(v, lo, hi)
            prev = self._prev.get(name)
            checks.append(VarCheck(name, v, lo, hi, d == 0.0, prev is None or d < prev or d == 0.0))
            self._prev[name] = d
        lineup_ok = obs.valve1 and obs.pump1 and obs.pump2
        all_ok = lineup_ok and all(c.in_range for c in checks)

        if self.state == "recovering":
            if all_ok:
                self._in_range_since = obs.t if self._in_range_since is None else self._in_range_since
            else:
                self._in_range_since = None
        held = 0.0 if self._in_range_since is None else obs.t - self._in_range_since
        if self.state == "recovering":
            if all_ok and held >= self.dwell:
                self.state = "recovered"
            elif obs.t - self._t0 >= self.timeout:
                self.state = "unresolved"
        return RecoveryReport(
            state=self.state,
            elapsed=obs.t - self._t0,
            seconds_in_range=held,
            dwell=self.dwell,
            valve_open=obs.valve1,
            pumps_on=obs.pump1 and obs.pump2,
            variables=checks,
        )
