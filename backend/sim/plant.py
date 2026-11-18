"""Campus microgrid substation model (owner: P2). Deterministic and seeded.

                 UTILITY ──[CB-MAIN]──┬────────── bus ──────────┬──────────┐
                                      │                         │          │
                            [CB-PV]──PV array        [CB-BESS]──Battery    │
                                                                           ├─[CB-CRIT]── Hospital (critical load)
                                                                           └─[CB-NC]──── Campus (non-critical load)

Process rules (simplified, understandable):
- Loads follow slow daily-like profiles and are only served while their breaker is closed.
- PV output = rated power x irradiance, and drops to zero if the inverter trips or CB-PV opens.
- The energy management system (EMS) steers the battery to hold grid import at a target, with a
  state-of-charge correction and a frequency droop term that reads the REPORTED frequency.
- Grid-connected: the utility holds frequency at 50 Hz and import = load - PV - battery.
- Islanded (CB-MAIN open): the battery forms the grid; any imbalance moves frequency and voltage.
- Sensor faults and attacks (bias, replay, stale updates) change what is REPORTED only. The EMS reads the
  reported frequency, so a spoofed frequency has a real physical consequence.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

import numpy as np

from core.contracts import IedStatus, Telemetry

F_NOM = 50.0
V_NOM = 1.0
PV_RATED_KW = 500.0
BESS_PMAX_KW = 250.0
BESS_CAP_KWH = 200.0
BESS_LAG = 0.4
SOC_TARGET = 60.0
SOC_GAIN_KW_PER_PCT = 10.0
IMPORT_TARGET_KW = 320.0
DROOP_KW_PER_HZ = 800.0
DROOP_DEADBAND_HZ = 0.1
LOAD_CRIT_BASE, LOAD_CRIT_AMP = 400.0, 30.0
LOAD_NC_BASE, LOAD_NC_AMP, LOAD_NC_PHASE = 300.0, 40.0, 1.0
LOAD_PERIOD_S = 600.0
IRR_BASE, IRR_AMP, IRR_PERIOD_S = 750.0, 150.0, 900.0  # W/m2
CLOUD_LAG = 0.1


@dataclass(frozen=True)
class PlantParams:
    """Sizes of one substation. Defaults are the original campus microgrid; the city layer scales them per district."""

    load_crit_base: float = LOAD_CRIT_BASE
    load_crit_amp: float = LOAD_CRIT_AMP
    load_nc_base: float = LOAD_NC_BASE
    load_nc_amp: float = LOAD_NC_AMP
    pv_rated_kw: float = PV_RATED_KW
    bess_pmax_kw: float = BESS_PMAX_KW
    bess_cap_kwh: float = BESS_CAP_KWH
    import_target_kw: float = IMPORT_TARGET_KW
    load_phase: float = 0.0  # shifts the load profiles so districts differ


BREAKERS = ("cb_main", "cb_pv", "cb_bess", "cb_crit", "cb_nc")
# Measurements an attacker can record and replay.
REPLAY_FIELDS = ("frequency", "bus_voltage", "grid_import_kw", "load_critical_kw", "load_noncritical_kw")


class Plant:
    def __init__(self, seed: int = 42, params: PlantParams | None = None) -> None:
        self.seed = seed
        self.p = params or PlantParams()
        self.rng = np.random.default_rng(seed)
        self.t = 0.0
        self.tick = 0
        # switchgear and set-points
        self.breakers: dict[str, bool] = {b: True for b in BREAKERS}  # True = closed
        self.stuck: set[str] = set()  # breakers that ignore commands (mechanical fault)
        self.import_target = self.p.import_target_kw
        self.bess_mode = "AUTO"  # AUTO | HOLD
        self.load_scale = 1.0  # demand multiplier (city-level events, e.g. an evening peak or a load-altering attack)
        self.grid_available = True  # False when the city network can no longer supply this substation
        # physical state
        self.freq = F_NOM
        self.volt = V_NOM
        self.grid_import = 320.0
        self.bess_kw = 0.0
        self.soc = SOC_TARGET
        self.pv = 0.0
        self.load_crit = LOAD_CRIT_BASE
        self.load_nc = LOAD_NC_BASE
        self.irradiance = IRR_BASE
        self.cloud = 1.0
        self.cloud_target = 1.0
        self.pv_inverter_ok = True
        # sensor faults / spoofing: change what is REPORTED (process untouched)
        self.sensor_bias: dict[str, float] = {"frequency": 0.0, "bus_voltage": 0.0, "grid_import_kw": 0.0}
        self.stale_prob = 0.0
        self.replay: dict | None = None
        self.ied_status: dict[str, str] = {"ied01": "normal", "ied02": "normal", "ied03": "normal"}
        self._obs_hist: deque[dict[str, float]] = deque(maxlen=60)
        self._last_vals: dict[str, float] | None = None

    # --- control -----------------------------------------------------------------
    def set_breaker(self, name: str, closed: bool) -> None:
        if name not in BREAKERS:
            raise ValueError(f"unknown breaker {name}")
        if name in self.stuck:
            return  # mechanism is stuck: the command has no effect
        self.breakers[name] = bool(closed)

    def start_replay(self, window: int = 30) -> None:
        """Report previously recorded readings instead of live ones."""
        hist = list(self._obs_hist)[-window:] or [
            {"frequency": F_NOM, "bus_voltage": V_NOM, "grid_import_kw": self.p.import_target_kw,
             "load_critical_kw": self.p.load_crit_base, "load_noncritical_kw": self.p.load_nc_base}
        ]
        self.replay = {f: [h[f] for h in hist] for f in REPLAY_FIELDS}
        self.replay["i"] = 0

    def clear_sensor_faults(self) -> None:
        self.sensor_bias = {k: 0.0 for k in self.sensor_bias}
        self.stale_prob = 0.0
        self.replay = None

    def reset_to_safe(self) -> None:
        """Hard reset: normal switching lineup, faults repaired, sensors clean."""
        self.breakers = {b: True for b in BREAKERS}
        self.stuck.clear()
        self.import_target = self.p.import_target_kw
        self.bess_mode = "AUTO"
        self.cloud_target = 1.0
        self.pv_inverter_ok = True
        self.clear_sensor_faults()
        self.ied_status = {"ied01": "normal", "ied02": "normal", "ied03": "normal"}

    # --- dynamics ------------------------------------------------------------------
    def step(self, dt: float = 1.0) -> Telemetry:
        b = self.breakers
        t = self.t
        irr_clear = IRR_BASE + IRR_AMP * math.sin(2.0 * math.pi * t / IRR_PERIOD_S)
        self.cloud += (self.cloud_target - self.cloud) * CLOUD_LAG
        self.irradiance = irr_clear * self.cloud
        self.pv = self.p.pv_rated_kw * self.irradiance / 1000.0 if (b["cb_pv"] and self.pv_inverter_ok) else 0.0
        phase = 2.0 * math.pi * t / LOAD_PERIOD_S + self.p.load_phase
        crit = self.p.load_crit_base + self.p.load_crit_amp * math.sin(phase)
        nc = self.p.load_nc_base + self.p.load_nc_amp * math.sin(phase + LOAD_NC_PHASE)
        self.load_crit = crit * self.load_scale if b["cb_crit"] else 0.0
        self.load_nc = nc * self.load_scale if b["cb_nc"] else 0.0
        load = self.load_crit + self.load_nc

        # energy management system: reads the REPORTED frequency
        f_reported = self.freq + self.sensor_bias["frequency"]
        connected = b["cb_main"] and self.grid_available
        if connected:
            target = self.import_target + SOC_GAIN_KW_PER_PCT * (SOC_TARGET - self.soc)
            dev = F_NOM - f_reported
            droop = 0.0 if abs(dev) < DROOP_DEADBAND_HZ else DROOP_KW_PER_HZ * dev
            want = load - self.pv - target + droop
        else:
            want = load - self.pv  # islanded: the battery forms the grid
        if not b["cb_bess"] or self.bess_mode != "AUTO":
            want = 0.0
        want = float(np.clip(want, -self.p.bess_pmax_kw, self.p.bess_pmax_kw))
        if self.soc <= 10.0:
            want = min(want, 0.0)
        if self.soc >= 95.0:
            want = max(want, 0.0)
        self.bess_kw += (want - self.bess_kw) * BESS_LAG
        if not b["cb_bess"]:
            self.bess_kw = 0.0
        self.soc = float(np.clip(self.soc - self.bess_kw * dt / (self.p.bess_cap_kwh * 3600.0) * 100.0, 0.0, 100.0))

        if connected:
            self.grid_import = load - self.pv - self.bess_kw
            self.freq = F_NOM  # the utility holds the frequency
            self.volt = V_NOM - 0.00003 * (self.grid_import - 300.0)
        else:
            self.grid_import = 0.0
            imbalance = self.pv + self.bess_kw - load
            f_target = float(np.clip(F_NOM + 2.0 * imbalance / 1000.0, 47.0, 52.0))
            self.freq += (f_target - self.freq) * 0.3
            self.volt += ((V_NOM + 0.03 * imbalance / 1000.0) - self.volt) * 0.3

        self.t += dt
        self.tick += 1
        return self.observe()

    def _is_nominal(self) -> bool:
        return (
            self.replay is None
            and self.stale_prob == 0.0
            and all(self.breakers.values())
            and not self.stuck
            and self.pv_inverter_ok
            and abs(self.cloud - 1.0) < 0.05
            and self.bess_mode == "AUTO"
            and self.import_target == self.p.import_target_kw
            and self.load_scale == 1.0
            and self.grid_available
            and all(abs(v) < 1e-9 for v in self.sensor_bias.values())
        )

    def true_state(self) -> dict[str, float | bool]:
        """Ground truth (for tests and evaluation only; detectors must not read this)."""
        return {
            "frequency": self.freq,
            "bus_voltage": self.volt,
            "grid_import_kw": self.grid_import,
            "pv_kw": self.pv,
            "bess_kw": self.bess_kw,
            "bess_soc": self.soc,
            "load_critical_kw": self.load_crit,
            "load_noncritical_kw": self.load_nc,
            "irradiance": self.irradiance,
            **dict(self.breakers),
        }

    def observe(self) -> Telemetry:
        n = self.rng.normal
        bias = self.sensor_bias
        vals = {
            "frequency": self.freq + n(0, 0.01) + bias["frequency"],
            "bus_voltage": self.volt + n(0, 0.002) + bias["bus_voltage"],
            "grid_import_kw": self.grid_import + n(0, 3.0) + bias["grid_import_kw"],
            "pv_kw": self.pv + n(0, 3.0),
            "bess_kw": self.bess_kw + n(0, 2.0),
            "bess_soc": self.soc + n(0, 0.05),
            "load_critical_kw": self.load_crit + n(0, 2.0),
            "load_noncritical_kw": self.load_nc + n(0, 2.0),
            "irradiance": self.irradiance + n(0, 5.0),
        }
        vals = {k: round(float(v), 4 if k == "bus_voltage" else 3) for k, v in vals.items()}
        if self.replay is not None:
            r = self.replay
            i = r["i"] % len(r["frequency"])
            for f in REPLAY_FIELDS:
                vals[f] = r[f][i]
            r["i"] += 1
        elif self.stale_prob > 0 and self._last_vals is not None and self.rng.random() < self.stale_prob:
            vals = dict(self._last_vals)  # missed update: measurements repeat the previous report
        if self._is_nominal():
            # An attacker can only record what the substation reported while it was running normally.
            self._obs_hist.append({f: vals[f] for f in REPLAY_FIELDS})
        self._last_vals = vals
        return Telemetry(
            t=self.t,
            tick=self.tick,
            cb_main=self.breakers["cb_main"],
            cb_pv=self.breakers["cb_pv"],
            cb_bess=self.breakers["cb_bess"],
            cb_crit=self.breakers["cb_crit"],
            cb_nc=self.breakers["cb_nc"],
            ied_status=IedStatus(**self.ied_status),
            **vals,
        )
