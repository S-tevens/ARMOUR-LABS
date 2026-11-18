"""Physics invariants (owner: P3): cheap, fully explainable consistency checks between signals.

Each invariant is a relation that must hold in normal operation however the load or weather changes. Its tolerance is
FITTED from normal data (six standard deviations of the normal residual, with a small floor), not hand-set. A ratio of
1.0 or more means the relation is broken.

  power_balance      grid import = loads - solar - battery (conservation of energy)
  frequency_band     while connected to a stiff grid, the frequency stays at 50 Hz
  voltage_vs_import  bus voltage follows the import level (fitted line)
  breaker_vs_load    an open breaker means its feeder carries no load
  pv_vs_irradiance   solar output follows the weather station (fitted ratio), and is zero when its breaker is open
  stale_updates      measurements never repeat exactly: identical consecutive readings mean updates are being lost

Caveat: the simulated plant is simple and these relations are close to exact in it, so the invariants look stronger here
than they would on a real grid, where tolerances must be fitted on real data and are wider.
"""
from __future__ import annotations

import numpy as np

from core.contracts import Telemetry
from detect.features import INDEX

NAMES = ["power_balance", "frequency_band", "voltage_vs_import", "breaker_vs_load", "pv_vs_irradiance", "stale_updates"]
LABEL = {
    "power_balance": "Power balance",
    "frequency_band": "Frequency",
    "voltage_vs_import": "Voltage against import",
    "breaker_vs_load": "Open breaker with load",
    "pv_vs_irradiance": "Solar against weather",
    "stale_updates": "Repeated readings",
}
LOAD_TOL = 20.0  # normalised kW: a feeder behind an open breaker should read about zero


class Invariants:
    def __init__(self) -> None:
        self.fitted = False

    def fit(self, runs) -> "Invariants":
        from detect.features import WINDOW

        X = np.vstack([r.X[WINDOW:] for r in runs])
        obs = [o for r in runs for o in r.obs[WINDOW:]]
        bal = X[:, INDEX["balance_residual"]]
        self.tol_balance = max(10.0, 6.0 * float(bal.std()))
        grid = np.array([o.cb_main for o in obs])
        freq = np.array([o.frequency for o in obs])
        self.tol_freq = max(0.05, 6.0 * float((freq[grid] - 50.0).std()))
        imp = X[:, INDEX["grid_import_kw"]]  # per-unit (divided by the substation size)
        volt = np.array([o.bus_voltage for o in obs])
        A = np.vstack([np.ones_like(imp), imp]).T
        (self.v_a, self.v_b), *_ = np.linalg.lstsq(A, volt, rcond=None)
        self.tol_volt = max(0.008, 6.0 * float((volt - A @ np.array([self.v_a, self.v_b])).std()))
        irr = X[:, INDEX["irradiance"]]
        pv = X[:, INDEX["pv_kw"]]
        pv_on = X[:, INDEX["cb_pv"]] > 0.5
        self.k_pv = float((pv[pv_on] * irr[pv_on]).sum() / (irr[pv_on] ** 2).sum())
        self.tol_pv = max(15.0, 6.0 * float((pv[pv_on] - self.k_pv * irr[pv_on]).std()))
        self.fitted = True
        return self

    def ratios(self, obs: Telemetry, x: np.ndarray) -> dict[str, float]:
        f = x[INDEX["frequency"]]
        r = {
            "power_balance": abs(x[INDEX["balance_residual"]]) / self.tol_balance,
            "frequency_band": abs(f - 50.0) / self.tol_freq if obs.cb_main else 0.0,
            "voltage_vs_import": (
                abs(obs.bus_voltage - (self.v_a + self.v_b * x[INDEX["grid_import_kw"]])) / self.tol_volt if abs(f - 50.0) < 0.3 else 0.0
            ),
            "breaker_vs_load": max(
                0.0 if obs.cb_crit else abs(x[INDEX["load_critical_kw"]]) / LOAD_TOL,
                0.0 if obs.cb_nc else abs(x[INDEX["load_noncritical_kw"]]) / LOAD_TOL,
            ),
            "pv_vs_irradiance": (
                abs(x[INDEX["pv_kw"]] - self.k_pv * x[INDEX["irradiance"]]) / self.tol_pv if obs.cb_pv else abs(x[INDEX["pv_kw"]]) / LOAD_TOL
            ),
            "stale_updates": x[INDEX["repeat_count"]] / 2.0,
        }
        return r

    @staticmethod
    def score(ratios: dict[str, float]) -> float:
        """0.8 means 'exactly at the tolerance', the same alert level as every other detector."""
        return float(min(1.0, 0.8 * max(ratios.values())))

    def explain(self, ratios: dict[str, float], obs: Telemetry, x: np.ndarray, limit: int = 2) -> list[str]:
        """Plain sentences for the broken relations, built only from the measured values."""
        out = []
        for name, ratio in sorted(ratios.items(), key=lambda kv: -kv[1]):
            if ratio < 1.0 or len(out) >= limit:
                continue
            if name == "power_balance":
                out.append(f"Power balance is off by {x[INDEX['balance_residual']]:.0f} kW: import does not match loads minus solar and battery")
            elif name == "frequency_band":
                out.append(f"Frequency reads {obs.frequency:.2f} Hz while connected to a grid that holds 50 Hz")
            elif name == "voltage_vs_import":
                exp = self.v_a + self.v_b * x[INDEX["grid_import_kw"]]
                out.append(f"Bus voltage {obs.bus_voltage:.3f} pu does not match the {exp:.3f} pu expected at this import level")
            elif name == "breaker_vs_load":
                which = "Hospital" if not obs.cb_crit and abs(x[INDEX["load_critical_kw"]]) > LOAD_TOL else "Campus"
                out.append(f"{which} feeder breaker is open but the feeder still reports load")
            elif name == "pv_vs_irradiance":
                out.append(f"Solar output {obs.pv_kw:.0f} kW does not match the weather station ({obs.irradiance:.0f} W/m2)")
            elif name == "stale_updates":
                out.append("Measurements are repeating exactly, so updates are being lost")
        return out
