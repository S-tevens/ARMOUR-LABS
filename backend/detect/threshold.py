"""Threshold baseline detector (owner: P3).

Baseline only. Add the Isolation Forest, physics invariants and percentile score normalisation
alongside this, and keep this as the comparison baseline.

- network / controller: unauthorised messages seen recently (placeholder: same rule for both)
- process: fixed engineering limits, independent of the twin (frequency, voltage, battery charge)
- twin: distance from the digital twin's expected state
"""
from __future__ import annotations

from collections import deque

from core.contracts import NetworkEvent, Scores, Telemetry, TwinState

ALERT_THRESHOLD = 0.8
RECENT_WINDOW_S = 10.0
FREQ_LIMIT_HZ = 0.5  # |f - 50| at which the process score reaches 1
VOLT_LIMIT_PU = 0.05
SOC_LOW_PCT = 20.0


class ThresholdDetector:
    def __init__(self) -> None:
        self._unauthorised: deque[float] = deque()  # timestamps of unauthorised events

    def score(self, obs: Telemetry, twin: TwinState, events: list[NetworkEvent]) -> Scores:
        for e in events:
            if not e.authorised:
                self._unauthorised.append(e.t)
        while self._unauthorised and obs.t - self._unauthorised[0] > RECENT_WINDOW_S:
            self._unauthorised.popleft()
        net = 0.9 if self._unauthorised else 0.0

        process = min(
            1.0,
            max(
                abs(obs.frequency - 50.0) / FREQ_LIMIT_HZ,
                abs(obs.bus_voltage - 1.0) / VOLT_LIMIT_PU,
                max(0.0, SOC_LOW_PCT - obs.bess_soc) / 10.0,
            ),
        )
        twin_score = min(1.0, max(abs(v) for v in twin.norm_residual.values()) / 6.0)
        return Scores(
            t=obs.t,
            network=round(net, 3),
            controller=round(net, 3),  # placeholder: no separate controller model yet
            process=round(process, 3),
            twin=round(twin_score, 3),
        )

    @staticmethod
    def is_alert(s: Scores) -> bool:
        return max(s.network, s.controller, s.process, s.twin) >= ALERT_THRESHOLD
