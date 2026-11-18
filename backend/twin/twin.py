"""Digital twin of the microgrid substation (owner: P2).

An independent, model-based expectation of how the substation SHOULD behave. It deliberately does not
copy the simulator: it has its own (slightly different) parameters, and its only command input is the
AUTHORISED command log, never the observed breaker or set-point states. That is what lets it tell:

  - an authorised planned switching (expected: feeder load drops, no residual)
  - from an unauthorised trip (breaker state and loads differ from the command log -> residual)
  - and from a stuck breaker (the command was authorised but the load did not drop -> residual).

Other inputs: the clock (a schedule / forecast) and the weather-station irradiance reading.

v0: parameters are hand-set and should be FITTED from normal data and tolerance-tuned (see the build
plan, Build 4). Residual scales below are placeholders derived from noise levels.
"""
from __future__ import annotations

import math

import numpy as np

from core.contracts import NetworkEvent, Telemetry, TwinState
from sim.plant import PlantParams

# The twin's own parameters (intentionally not identical to the simulator's).
PV_RATED_KW = 500.0
PV_EFF = 0.99
LOAD_CRIT_BASE, LOAD_CRIT_AMP = 401.0, 28.0
LOAD_NC_BASE, LOAD_NC_AMP, LOAD_NC_PHASE = 299.0, 42.0, 1.0
LOAD_PERIOD_S = 600.0
BESS_PMAX_KW = 250.0
BESS_CAP_KWH = 205.0
BESS_LAG = 0.38
SOC_TARGET = 60.0
SOC_GAIN_KW_PER_PCT = 10.0
DEFAULT_IMPORT_TARGET_KW = 320.0
SOC_OBSERVER_GAIN = 0.01

# Normalisation scale per variable: roughly one standard deviation of the residual in normal operation.
SCALE = {
    "frequency": 0.03,
    "bus_voltage": 0.006,
    "grid_import_kw": 25.0,
    "pv_kw": 12.0,
    "bess_kw": 20.0,
    "bess_soc": 2.0,
    "load_critical_kw": 8.0,
    "load_noncritical_kw": 8.0,
    "breaker_mismatch": 0.15,
}
BREAKER_FIELDS = ("cb_main", "cb_pv", "cb_bess", "cb_crit", "cb_nc")
REGISTER_TO_BREAKER = {"CB_MAIN": "cb_main", "CB_PV": "cb_pv", "CB_BESS": "cb_bess", "CB_CRIT": "cb_crit", "CB_NC": "cb_nc"}


class GridTwin:
    def __init__(self, params: PlantParams | None = None) -> None:
        # The twin's own parameters: the substation's sizes (which operators know), with its own small modelling errors.
        p = params or PlantParams()
        self.pv_rated = p.pv_rated_kw
        self.crit_base, self.crit_amp = p.load_crit_base * (401.0 / 400.0), p.load_crit_amp * (28.0 / 30.0)
        self.nc_base, self.nc_amp = p.load_nc_base * (299.0 / 300.0), p.load_nc_amp * (42.0 / 40.0)
        self.pmax = p.bess_pmax_kw
        self.cap = p.bess_cap_kwh * (205.0 / 200.0)
        self.load_phase = p.load_phase
        self.scale = p.scale
        self.demand_factor = 1.0  # the demand FORECAST (a schedule, like the clock); attacks do not change it
        self.breakers = {b: True for b in BREAKER_FIELDS}  # EXPECTED states, from authorised commands only
        self.import_target = p.import_target_kw
        self.bess_mode = "AUTO"
        self.bess_kw = 0.0
        self.soc = SOC_TARGET
        self._synced = 0

    def sync(self, command_log: list[NetworkEvent]) -> None:
        """Apply new AUTHORISED commands. The log must contain authorised writes only."""
        for cmd in command_log[self._synced:]:
            if not cmd.authorised:
                continue
            if cmd.register in REGISTER_TO_BREAKER:
                self.breakers[REGISTER_TO_BREAKER[cmd.register]] = cmd.value in ("CLOSE", True, 1)
            elif cmd.register == "BESS_MODE":
                self.bess_mode = str(cmd.value)
            elif cmd.register == "IMPORT_TARGET_KW":
                self.import_target = float(cmd.value)
        self._synced = len(command_log)

    def compute(self, obs: Telemetry) -> TwinState:
        b = self.breakers
        t = obs.t - 1.0  # the simulator evaluates its profiles one tick before it reports
        phase = 2.0 * math.pi * t / LOAD_PERIOD_S + self.load_phase
        pv = self.pv_rated * obs.irradiance / 1000.0 * PV_EFF if b["cb_pv"] else 0.0
        crit = (self.crit_base + self.crit_amp * math.sin(phase)) * self.demand_factor if b["cb_crit"] else 0.0
        nc = (self.nc_base + self.nc_amp * math.sin(phase + LOAD_NC_PHASE)) * self.demand_factor if b["cb_nc"] else 0.0
        load = crit + nc

        if b["cb_main"]:
            target = self.import_target + SOC_GAIN_KW_PER_PCT * (SOC_TARGET - self.soc)
            want = load - pv - target
        else:
            want = load - pv
        if not b["cb_bess"] or self.bess_mode != "AUTO":
            want = 0.0
        want = float(np.clip(want, -self.pmax, self.pmax))
        if self.soc <= 10.0:
            want = min(want, 0.0)
        if self.soc >= 95.0:
            want = max(want, 0.0)
        self.bess_kw += (want - self.bess_kw) * BESS_LAG
        if not b["cb_bess"]:
            self.bess_kw = 0.0
        self.soc = float(np.clip(self.soc - self.bess_kw / (self.cap * 3600.0) * 100.0, 0.0, 100.0))
        # state estimation: pull the integrated charge slowly toward the measurement, so an incident that really changed the
        # battery charge does not leave the twin permanently wrong (time constant about 100 s)
        self.soc += SOC_OBSERVER_GAIN * (obs.bess_soc - self.soc)

        if b["cb_main"]:
            grid = load - pv - self.bess_kw
            freq = 50.0
            volt = 1.0 - 0.00003 * (grid / self.scale - 300.0)
        else:
            grid = 0.0
            imbalance = pv + self.bess_kw - load
            freq = float(np.clip(50.0 + 2.0 * imbalance / 1000.0, 47.0, 52.0))
            volt = 1.0 + 0.03 * imbalance / 1000.0

        expected = {
            "frequency": freq,
            "bus_voltage": volt,
            "grid_import_kw": grid,
            "pv_kw": pv,
            "bess_kw": self.bess_kw,
            "bess_soc": self.soc,
            "load_critical_kw": crit,
            "load_noncritical_kw": nc,
            "breaker_mismatch": 0.0,
        }
        observed = {k: float(getattr(obs, k)) for k in expected if k != "breaker_mismatch"}
        observed["breaker_mismatch"] = float(sum(getattr(obs, f) != b[f] for f in BREAKER_FIELDS))
        residual = {k: round(observed[k] - expected[k], 4) for k in expected}
        norm = {k: round(residual[k] / SCALE[k], 3) for k in expected}
        return TwinState(
            t=obs.t,
            expected={k: round(v, 4) for k, v in expected.items()},
            residual=residual,
            norm_residual=norm,
        )
