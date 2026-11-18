"""City recovery verification (owner: P2).

"Recovered" only when, for `dwell` consecutive seconds: every district is energised, every line is in service
(except lines opened by an authorised command), no line is above 90 % loading, every hospital is back on grid
power, and the frequency is within 49.9-50.1 Hz. "Unresolved" after `timeout` seconds.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

DWELL_S = 10.0
TIMEOUT_S = 150.0
MAX_LOADING = 0.9
FREQ_BAND = (49.9, 50.1)


@dataclass
class CityRecoveryReport:
    state: str  # idle | recovering | recovered | unresolved
    elapsed: float = 0.0
    seconds_in_range: float = 0.0
    dwell: float = DWELL_S
    checks: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class CityRecoveryVerifier:
    def __init__(self, dwell: float = DWELL_S, timeout: float = TIMEOUT_S) -> None:
        self.dwell, self.timeout = dwell, timeout
        self.state = "idle"
        self._t0 = 0.0
        self._since: float | None = None

    def start(self, t: float) -> None:
        self.state, self._t0, self._since = "recovering", t, None

    def update(self, st: dict, authorised_open_lines: set[str]) -> CityRecoveryReport:
        if self.state == "idle":
            return CityRecoveryReport("idle", dwell=self.dwell)
        dark = [d["name"] for d in st["districts"] if d["status"] == "dark"]
        out = [l["id"] for l in st["lines"] if l["status"] != "in_service" and l["id"] not in authorised_open_lines]
        hot = [l["id"] for l in st["lines"] if l["loading"] > MAX_LOADING]
        hosp = [f["id"] for d in st["districts"] for f in d["facilities"] if f["type"] == "hospital" and f["status"] != "ok"]
        f_ok = FREQ_BAND[0] <= st["frequency"] <= FREQ_BAND[1]
        checks = [
            {"name": "All districts energised", "ok": not dark, "detail": ", ".join(dark)},
            {"name": "All lines in service", "ok": not out, "detail": ", ".join(out)},
            {"name": "No line above 90 % loading", "ok": not hot, "detail": ", ".join(hot)},
            {"name": "Hospitals on grid power", "ok": not hosp, "detail": ", ".join(hosp)},
            {"name": "Frequency within 49.9-50.1 Hz", "ok": f_ok, "detail": f"{st['frequency']:.2f} Hz"},
        ]
        all_ok = all(c["ok"] for c in checks)
        t = st["t"]
        if self.state == "recovering":
            self._since = (t if self._since is None else self._since) if all_ok else None
        held = 0.0 if self._since is None else t - self._since
        if self.state == "recovering":
            if all_ok and held >= self.dwell:
                self.state = "recovered"
            elif t - self._t0 >= self.timeout:
                self.state = "unresolved"
        return CityRecoveryReport(self.state, t - self._t0, held, self.dwell, checks)
