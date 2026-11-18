"""Deterministic water-treatment plant model (owner: P2).

Flow: raw water -> Tank 1 -> Pump 1 -> Filter -> Valve 1 -> Tank 2 -> Pump 2 -> clean water.

This is a deliberately simple starting model. Replace/extend the dynamics, but keep
the Telemetry output shape (core/contracts.py) and the seeded determinism.
"""
from __future__ import annotations

import numpy as np

from core.contracts import PlcStatus, Telemetry

RAW_INFLOW_LPM = 110.0  # raw water into Tank 1
NOMINAL_FLOW_LPM = 110.0
NOMINAL_PRESSURE_BAR = 2.1
BLOCKED_PRESSURE_BAR = 4.8  # pump pushing against a closed valve
BLOCKED_FLOW_LPM = 12.0
TANK_CAPACITY_L = 600.0
LAG = 0.35  # first-order response per second


class Plant:
    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.t = 0.0
        self.tick = 0
        # true process state
        self.tank1 = 62.0
        self.tank2 = 48.0
        self.pressure = NOMINAL_PRESSURE_BAR
        self.flow = NOMINAL_FLOW_LPM
        self.temperature = 27.0
        # actuators (True = running / open)
        self.pump1 = True
        self.pump2 = True
        self.valve1 = True
        # sensor faults / spoofing: additive bias on what sensors REPORT (process is untouched)
        self.sensor_bias: dict[str, float] = {"pressure": 0.0, "flow": 0.0, "tank1_level": 0.0}
        self.plc_status: dict[str, str] = {"plc01": "normal", "plc02": "normal", "plc03": "normal"}

    # --- control -----------------------------------------------------------------
    def set_actuator(self, name: str, value: bool) -> None:
        if name not in ("pump1", "pump2", "valve1"):
            raise ValueError(f"unknown actuator {name}")
        setattr(self, name, bool(value))

    def reset_to_safe(self) -> None:
        """Simulated containment/restore: normal actuator lineup, no sensor bias."""
        self.pump1 = self.pump2 = self.valve1 = True
        self.sensor_bias = {k: 0.0 for k in self.sensor_bias}
        self.plc_status = {"plc01": "normal", "plc02": "normal", "plc03": "normal"}

    # --- dynamics ------------------------------------------------------------------
    def step(self, dt: float = 1.0) -> Telemetry:
        if self.pump1 and self.valve1:
            target_flow, target_p = NOMINAL_FLOW_LPM, NOMINAL_PRESSURE_BAR
        elif self.pump1:
            target_flow, target_p = BLOCKED_FLOW_LPM, BLOCKED_PRESSURE_BAR
        else:
            target_flow, target_p = 0.0, 0.0
        self.flow += (target_flow - self.flow) * LAG
        self.pressure += (target_p - self.pressure) * LAG

        out2 = NOMINAL_FLOW_LPM if (self.pump2 and self.tank2 > 2.0) else 0.0
        self.tank1 += (RAW_INFLOW_LPM - self.flow) / 60.0 / TANK_CAPACITY_L * 100.0 * dt
        self.tank2 += (self.flow - out2) / 60.0 / TANK_CAPACITY_L * 100.0 * dt
        self.tank1 = float(np.clip(self.tank1, 0.0, 100.0))
        self.tank2 = float(np.clip(self.tank2, 0.0, 100.0))

        self.t += dt
        self.tick += 1
        return self.observe()

    def true_state(self) -> dict[str, float | bool]:
        """Ground truth (for tests and evaluation only; detectors must not read this)."""
        return {
            "tank1_level": self.tank1,
            "tank2_level": self.tank2,
            "pressure": self.pressure,
            "flow": self.flow,
            "temperature": self.temperature,
            "pump1": self.pump1,
            "pump2": self.pump2,
            "valve1": self.valve1,
        }

    def observe(self) -> Telemetry:
        n = self.rng.normal
        b = self.sensor_bias
        return Telemetry(
            t=self.t,
            tick=self.tick,
            tank1_level=round(self.tank1 + n(0, 0.05) + b["tank1_level"], 3),
            tank2_level=round(self.tank2 + n(0, 0.05), 3),
            pressure=round(self.pressure + n(0, 0.03) + b["pressure"], 3),
            flow=round(self.flow + n(0, 1.0) + b["flow"], 3),
            temperature=round(self.temperature + n(0, 0.05), 3),
            pump1=self.pump1,
            pump2=self.pump2,
            valve1=self.valve1,
            plc_status=PlcStatus(**self.plc_status),
        )
