"""Incident manager (owner: P3).

PLACEHOLDER: opens one incident when an alert fires and always classifies it as
"unknown". The real evidence fusion (attack vs fault vs unknown, with uncertainty)
goes here. Evidence text must only use real measured fields.
"""
from __future__ import annotations

from core.contracts import Evidence, Incident, NetworkEvent, Scores, Telemetry, TwinState

# Recovery check (placeholder): all within tolerance for DWELL_TICKS consecutive ticks.
TOLERANCE = {"pressure": (1.8, 2.5), "flow": (95.0, 125.0)}
DWELL_TICKS = 10


class IncidentManager:
    def __init__(self) -> None:
        self.incidents: dict[str, Incident] = {}
        self._counter = 0
        self._ok_ticks = 0

    def active(self) -> Incident | None:
        for inc in self.incidents.values():
            if inc.status in ("open", "responding", "recovering"):
                return inc
        return None

    def update(
        self, obs: Telemetry, twin: TwinState, scores: Scores, alert: bool, events: list[NetworkEvent]
    ) -> Incident | None:
        """Returns an incident when one is created or changes status; otherwise None."""
        inc = self.active()
        if inc is None:
            if not alert:
                return None
            self._counter += 1
            evidence = [
                Evidence(type="twin_residual", tag="observed",
                         text=f"Pressure {obs.pressure:.2f} bar vs expected {twin.expected['pressure']:.2f} bar"),
                Evidence(type="twin_residual", tag="observed",
                         text=f"Flow {obs.flow:.1f} L/min vs expected {twin.expected['flow']:.1f} L/min"),
            ]
            for e in events:
                if not e.authorised:
                    evidence.append(Evidence(
                        type="unauthorised_event", tag="observed",
                        text=f"Unauthorised {e.function_code} {e.register}={e.value} from {e.src} to {e.dst}"))
            inc = Incident(
                id=f"INC-{self._counter:03d}",
                t_start=obs.t,
                severity="high" if max(scores.model_dump(exclude={"t"}).values()) >= 0.9 else "medium",
                confidence=0.0,  # TODO: real confidence from fusion
                affected_devices=sorted({e.dst for e in events if not e.authorised}),
                classification="unknown",  # TODO: attack/fault/unknown from evidence fusion
                scores=scores.model_dump(exclude={"t"}),
                evidence=evidence,
                status="open",
            )
            self.incidents[inc.id] = inc
            return inc

        if inc.status == "recovering":
            ok = all(lo <= getattr(obs, k) <= hi for k, (lo, hi) in TOLERANCE.items())
            self._ok_ticks = self._ok_ticks + 1 if ok else 0
            if self._ok_ticks >= DWELL_TICKS:
                inc.status = "recovered"
                return inc
        return None

    def begin_recovery(self, incident_id: str) -> Incident:
        inc = self.incidents[incident_id]
        inc.status = "recovering"
        self._ok_ticks = 0
        return inc
