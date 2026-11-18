"""Incident manager (owner: P3).

PLACEHOLDER: opens one incident when an alert fires and always classifies it as
"unknown". The real evidence fusion (attack vs fault vs unknown, with uncertainty)
goes here. Evidence text only uses real measured values from the twin's residuals and events.

Recovery status comes from sim.recovery.RecoveryVerifier, never from the alert going quiet.
"""
from __future__ import annotations

import re

from core.contracts import Evidence, Incident, NetworkEvent, Scores, Telemetry, TwinState
from sim.recovery import RecoveryReport, RecoveryVerifier

LABELS = {
    "frequency": ("Frequency", "Hz", 2),
    "bus_voltage": ("Bus voltage", "pu", 3),
    "grid_import_kw": ("Grid import", "kW", 0),
    "pv_kw": ("PV output", "kW", 0),
    "bess_kw": ("Battery power", "kW", 0),
    "bess_soc": ("Battery charge", "%", 1),
    "load_critical_kw": ("Hospital feeder load", "kW", 0),
    "load_noncritical_kw": ("Campus feeder load", "kW", 0),
}
IED_NAMES = {"ied01": "IED-01", "ied02": "IED-02", "ied03": "IED-03"}
EVIDENCE_THRESHOLD = 4.0  # normalised residual
MAX_RESIDUAL_EVIDENCE = 3


def _shape(e: Evidence) -> tuple[str, str]:
    """An evidence line with its numbers removed, so a repeated statement with new values is recognised as the same."""
    return e.type, re.sub(r"[-+]?\d+(?:\.\d+)?", "#", e.text)


def _residual_evidence(twin: TwinState) -> list[Evidence]:
    ranked = sorted(twin.norm_residual.items(), key=lambda kv: abs(kv[1]), reverse=True)
    out: list[Evidence] = []
    for name, norm in ranked:
        if abs(norm) < EVIDENCE_THRESHOLD or len(out) >= MAX_RESIDUAL_EVIDENCE:
            continue
        if name == "breaker_mismatch":
            n = int(round(twin.residual[name]))
            out.append(Evidence(type="breaker_mismatch", tag="observed",
                                text=f"{n} breaker state{'s' if n != 1 else ''} differ from the authorised command log"))
            continue
        label, unit, digits = LABELS[name]
        exp = twin.expected[name]
        obs = exp + twin.residual[name]
        out.append(Evidence(type="twin_residual", tag="observed",
                            text=f"{label} {obs:.{digits}f} {unit} vs expected {exp:.{digits}f} {unit}"))
    return out


class IncidentManager:
    def __init__(self) -> None:
        self.incidents: dict[str, Incident] = {}
        self._counter = 0
        self.verifier = RecoveryVerifier()
        self.last_report: RecoveryReport = RecoveryReport(state="idle")

    def active(self) -> Incident | None:
        for inc in self.incidents.values():
            if inc.status in ("open", "responding", "recovering"):
                return inc
        return None

    def update(
        self, obs: Telemetry, twin: TwinState, scores: Scores, alert: bool, events: list[NetworkEvent],
        extra: list[Evidence] | None = None,
    ) -> Incident | None:
        """Returns an incident when one is created or changes status; otherwise None."""
        inc = self.active()
        if inc is None:
            if not alert:
                return None
            self._counter += 1
            evidence = _residual_evidence(twin) + list(extra or [])
            for e in events:
                if not e.authorised:
                    evidence.append(Evidence(
                        type="unauthorised_event", tag="observed",
                        text=f"Unauthorised {e.function_code} {e.register}={e.value} from {e.src} to {e.dst}"))
            affected = sorted({e.dst for e in events if not e.authorised})
            if not affected:
                affected = sorted(IED_NAMES[k] for k, v in obs.ied_status.model_dump().items() if v != "normal")
            inc = Incident(
                id=f"INC-{self._counter:03d}",
                t_start=obs.t,
                severity="high" if max(scores.model_dump(exclude={"t"}).values()) >= 0.9 else "medium",
                confidence=0.0,  # TODO: real confidence from fusion
                affected_devices=affected,
                classification="unknown",  # TODO: attack/fault/unknown from evidence fusion
                scores=scores.model_dump(exclude={"t"}),
                evidence=evidence,
                status="open",
            )
            self.incidents[inc.id] = inc
            return inc

        if inc.status == "open":
            inc.scores = scores.model_dump(exclude={"t"})  # the open incident shows the latest scores
            # keep gathering evidence as the slower detectors confirm it; the same sentence with new numbers is not new
            have = {_shape(e) for e in inc.evidence}
            fresh = [e for e in (extra or []) if _shape(e) not in have]
            inc.evidence += fresh[: max(0, 8 - len(inc.evidence))]
        if inc.status == "recovering":
            self.last_report = self.verifier.update(obs)
            if self.last_report.state == "recovered":
                inc.status = "recovered"
                return inc
            if self.last_report.state == "unresolved":
                inc.status = "unresolved"
                return inc
        return None

    def begin_recovery(self, incident_id: str, t: float = 0.0) -> Incident:
        inc = self.incidents[incident_id]
        inc.status = "recovering"
        self.verifier.start(t)
        self.last_report = RecoveryReport(state="recovering")
        return inc
