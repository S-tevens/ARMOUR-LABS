"""Digital twin (owner: P2).

PLACEHOLDER: returns fixed nominal values. The real twin must be INDEPENDENT of the
simulator (own fitted parameters) and may only use the AUTHORISED command log as input,
never observed actuator states. See ARMOUR_LABS_MVP_BUILD_PLAN.md, Build 4.
"""
from __future__ import annotations

from core.contracts import Telemetry, TwinState

NOMINAL = {"tank1_level": 62.0, "tank2_level": 48.0, "pressure": 2.1, "flow": 110.0, "temperature": 27.0}
# Normalisation scale per variable (placeholder: replace with std from held-out normal data).
SCALE = {"tank1_level": 3.0, "tank2_level": 3.0, "pressure": 0.15, "flow": 5.0, "temperature": 1.0}


class NominalTwin:
    def compute(self, obs: Telemetry) -> TwinState:
        expected = dict(NOMINAL)
        residual = {k: round(getattr(obs, k) - v, 4) for k, v in expected.items()}
        norm = {k: round(residual[k] / SCALE[k], 3) for k in expected}
        return TwinState(t=obs.t, expected=expected, residual=residual, norm_residual=norm)
