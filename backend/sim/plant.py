"""Deterministic water-treatment plant model (owner: P2).

Flow: raw water -> Tank 1 -> Pump 1 -> Filter -> Valve 1 -> Tank 2 -> Pump 2 -> clean water.

Process rules (simplified, understandable):
- Flow through the line = pump output x filter factor x valve factor. A closed valve leaves a small bypass flow.
- Pressure rises when the valve restricts flow (pump pushing against it) and when the filter clogs.
- Pump speed scales flow linearly and pressure with the square of speed.
- Tank levels follow inflow minus outflow, with simple level regulation on the raw inlet and the Pump 2 outlet.
- Tank 2 sees a slow sinusoidal demand disturbance.
- Sensors add seeded noise. Sensor faults/attacks (bias, replay, stale updates) change what is REPORTED only.
"""
from __future__ import annotations

import math
from collections import deque

import numpy as np

from core.contracts import PlcStatus, Telemetry

RAW_INFLOW_LPM = 110.0  # raw water into Tank 1
NOMINAL_FLOW_LPM = 110.0
NOMINAL_PRESSURE_BAR = 2.1
BLOCKED_PRESSURE_BAR = 4.8  # pump pushing against a closed valve
BLOCKED_FLOW_LPM = 12.0
BLOCKED_RATIO = BLOCKED_FLOW_LPM / NOMINAL_FLOW_LPM
TANK_CAPACITY_L = 600.0
LAG = 0.35  # first-order response per second
LEVEL_GAIN_LPM_PER_PCT = 8.0  # inlet/outlet throttle as levels drift from the setpoint
TANK1_SETPOINT = 62.0
TANK2_SETPOINT = 48.0
CLOG_FLOW_LOSS = 0.45  # fully clogged filter cuts pump output by this fraction
CLOG_PRESSURE_RISE = 0.8  # and raises pressure by this fraction
DEMAND_PERIOD_S = 300.0


class Plant:
    def __init__(self, seed: int = 42, disturbances: bool = True) -> None:
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.t = 0.0
        self.tick = 0
        # true process state
        self.tank1 = TANK1_SETPOINT
        self.tank2 = TANK2_SETPOINT
        self.pressure = NOMINAL_PRESSURE_BAR
        self.flow = NOMINAL_FLOW_LPM
        self.temperature = 27.0
        # actuators (True = running / open)
        self.pump1 = True
        self.pump2 = True
        self.valve1 = True
        self.pump1_speed = 1.0  # 0..1 setpoint
        # physical faults
        self.valve_stuck: float | None = None  # opening fraction the valve is stuck at (ignores commands)
        self.filter_clog = 0.0  # 0..1
        self.clog_rate = 0.0  # added per second
        # process disturbance
        self.demand_amp = 4.0 if disturbances else 0.0  # L/min swing on the Pump 2 outlet
        # sensor faults / spoofing: change what sensors REPORT (process untouched)
        self.sensor_bias: dict[str, float] = {"pressure": 0.0, "flow": 0.0, "tank1_level": 0.0}
        self.stale_prob = 0.0  # chance a tick repeats the previous sensor report (missed update)
        self.replay: dict | None = None  # recorded readings being replayed instead of live ones
        self.plc_status: dict[str, str] = {"plc01": "normal", "plc02": "normal", "plc03": "normal"}
        self._obs_hist: deque[dict[str, float]] = deque(maxlen=60)
        self._last_vals: dict[str, float] | None = None

    # --- control -----------------------------------------------------------------
    def set_actuator(self, name: str, value: bool) -> None:
        if name not in ("pump1", "pump2", "valve1"):
            raise ValueError(f"unknown actuator {name}")
        setattr(self, name, bool(value))

    def set_pump_speed(self, speed: float) -> None:
        self.pump1_speed = float(np.clip(speed, 0.0, 1.0))

    def start_replay(self, window: int = 30) -> None:
        """Start reporting previously recorded pressure/flow readings instead of live ones."""
        hist = list(self._obs_hist)[-window:] or [{"pressure": 2.1, "flow": 110.0}]  # nominal if nothing recorded
        self.replay = {"pressure": [h["pressure"] for h in hist], "flow": [h["flow"] for h in hist], "i": 0}

    def clear_sensor_faults(self) -> None:
        self.sensor_bias = {k: 0.0 for k in self.sensor_bias}
        self.stale_prob = 0.0
        self.replay = None

    def reset_to_safe(self) -> None:
        """Hard reset: normal actuator lineup, faults repaired, sensors clean."""
        self.pump1 = self.pump2 = self.valve1 = True
        self.pump1_speed = 1.0
        self.valve_stuck = None
        self.filter_clog = 0.0
        self.clog_rate = 0.0
        self.clear_sensor_faults()
        self.plc_status = {"plc01": "normal", "plc02": "normal", "plc03": "normal"}

    @property
    def valve_open_fraction(self) -> float:
        if self.valve_stuck is not None:
            return self.valve_stuck
        return 1.0 if self.valve1 else 0.0

    # --- dynamics ------------------------------------------------------------------
    def step(self, dt: float = 1.0) -> Telemetry:
        self.filter_clog = float(np.clip(self.filter_clog + self.clog_rate * dt, 0.0, 1.0))
        speed = self.pump1_speed
        if self.pump1:
            open_frac = self.valve_open_fraction
            pump_flow = NOMINAL_FLOW_LPM * speed * (1.0 - CLOG_FLOW_LOSS * self.filter_clog)
            target_flow = pump_flow * (BLOCKED_RATIO + (1.0 - BLOCKED_RATIO) * open_frac)
            p_open = NOMINAL_PRESSURE_BAR * speed**2 * (1.0 + CLOG_PRESSURE_RISE * self.filter_clog)
            p_block = BLOCKED_PRESSURE_BAR * speed**2
            target_p = p_open + (p_block - p_open) * (1.0 - open_frac)
        else:
            target_flow, target_p = 0.0, 0.0
        self.flow += (target_flow - self.flow) * LAG
        self.pressure += (target_p - self.pressure) * LAG

        # Raw inlet and Pump 2 outlet throttle with level, so levels recover after an upset.
        inflow = max(0.0, RAW_INFLOW_LPM + LEVEL_GAIN_LPM_PER_PCT * (TANK1_SETPOINT - self.tank1))
        out2 = 0.0
        if self.pump2 and self.tank2 > 2.0:
            demand = self.demand_amp * math.sin(2.0 * math.pi * self.t / DEMAND_PERIOD_S)
            out2 = max(0.0, NOMINAL_FLOW_LPM + demand + LEVEL_GAIN_LPM_PER_PCT * (self.tank2 - TANK2_SETPOINT))
        self.tank1 += (inflow - self.flow) / 60.0 / TANK_CAPACITY_L * 100.0 * dt
        self.tank2 += (self.flow - out2) / 60.0 / TANK_CAPACITY_L * 100.0 * dt
        self.tank1 = float(np.clip(self.tank1, 0.0, 100.0))
        self.tank2 = float(np.clip(self.tank2, 0.0, 100.0))

        self.t += dt
        self.tick += 1
        return self.observe()

    def _is_nominal(self) -> bool:
        return (
            self.replay is None
            and self.stale_prob == 0.0
            and self.valve_open_fraction == 1.0
            and self.pump1_speed >= 0.95
            and self.filter_clog < 0.05
            and all(abs(b) < 1e-9 for b in self.sensor_bias.values())
        )

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
            "pump1_speed": self.pump1_speed,
            "valve_open_fraction": self.valve_open_fraction,
            "filter_clog": self.filter_clog,
        }

    def observe(self) -> Telemetry:
        n = self.rng.normal
        b = self.sensor_bias
        vals = {
            "tank1_level": self.tank1 + n(0, 0.05) + b["tank1_level"],
            "tank2_level": self.tank2 + n(0, 0.05),
            "pressure": self.pressure + n(0, 0.03) + b["pressure"],
            "flow": self.flow + n(0, 1.0) + b["flow"],
            "temperature": self.temperature + n(0, 0.05),
        }
        vals = {k: round(float(v), 3) for k, v in vals.items()}
        if self.replay is not None:
            r = self.replay
            i = r["i"] % len(r["pressure"])
            vals["pressure"], vals["flow"] = r["pressure"][i], r["flow"][i]
            r["i"] += 1
        elif self.stale_prob > 0 and self._last_vals is not None and self.rng.random() < self.stale_prob:
            vals = dict(self._last_vals)  # missed update: sensors repeat their previous report
        if self._is_nominal():
            # An attacker can only record what the plant reported while it was running normally.
            self._obs_hist.append({"pressure": vals["pressure"], "flow": vals["flow"]})
        self._last_vals = vals
        return Telemetry(
            t=self.t,
            tick=self.tick,
            pump1=self.pump1,
            pump2=self.pump2,
            valve1=self.valve1,  # reported commanded state, even if the valve is physically stuck
            plc_status=PlcStatus(**self.plc_status),
            **vals,
        )
