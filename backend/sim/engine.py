"""Simulation engine: advances the plant, runs scenarios and containment, emits network events."""
from __future__ import annotations

from dataclasses import dataclass, field

from core.contracts import NetworkEvent, Telemetry
from sim import scenarios
from sim.containment import Containment
from sim.plant import Plant

HEARTBEAT_EVERY_TICKS = 5
PLCS = ("PLC-01", "PLC-02", "PLC-03")
EVENT_LOG_CAP = 5000


@dataclass
class StepResult:
    telemetry: Telemetry
    events: list[NetworkEvent] = field(default_factory=list)


class SimulationEngine:
    def __init__(self, seed: int = 42, disturbances: bool = True) -> None:
        self.plant = Plant(seed, disturbances)
        self.seq = 0
        self.active: str | None = None
        self._active_since_tick = 0
        self._pending: list[NetworkEvent] = []
        self.event_log: list[NetworkEvent] = []  # every event emitted (replay attacks copy from here)
        self.command_log: list[NetworkEvent] = []  # AUTHORISED write commands only (input for the digital twin)
        self.suppress_heartbeat: set[str] = set()  # PLCs whose heartbeats are dropped (DoS)
        self.containment: Containment | None = None
        self.containment_log: list[dict] = []

    # --- events --------------------------------------------------------------------
    def emit(self, src, dst, function_code, register, value, authorised, *, seq=None, t=None) -> NetworkEvent:
        """Emit a network event. Pass seq/t to re-send an OLD message (replay)."""
        if seq is None:
            self.seq += 1
            seq = self.seq
        e = NetworkEvent(
            seq=seq,
            t=self.plant.t if t is None else t,
            src=src,
            dst=dst,
            function_code=function_code,
            register=register,
            value=value,
            authorised=authorised,
        )
        self._pending.append(e)
        self.event_log.append(e)
        del self.event_log[:-EVENT_LOG_CAP]
        return e

    def command(self, dst: str, register: str, value) -> None:
        """An AUTHORISED command from SCADA: logged, and applied to the plant."""
        e = self.emit("SCADA", dst, "WRITE_REG" if register.endswith("SPEED") else "WRITE_COIL", register, value, True)
        self.command_log.append(e)
        p = self.plant
        if register == "PUMP1_SPEED":
            p.set_pump_speed(float(value))
        elif register == "VALVE1":
            p.set_actuator("valve1", value in (True, "OPEN", 1))
        else:
            raise ValueError(f"unknown register {register}")

    # --- scenarios -----------------------------------------------------------------
    def start_scenario(self, name: str) -> None:
        if name not in scenarios.SCENARIO_INFO:
            raise KeyError(name)
        if self.active:
            self.stop_scenario()
        self.active = name
        self._active_since_tick = self.plant.tick
        scenarios.start(name, self)

    def stop_scenario(self) -> None:
        """Hard reset: ends the scenario, repairs faults, restores the safe lineup."""
        self.active = None
        self.suppress_heartbeat.clear()
        self.containment = None
        self.plant.reset_to_safe()

    def ground_truth(self) -> dict:
        """What is really happening (for datasets and evaluation; detectors must not read this)."""
        info = scenarios.SCENARIO_INFO.get(self.active) if self.active else None
        kind = info["kind"] if info else "normal"
        return {
            "scenario": self.active or "normal",
            "kind": kind,
            "active": bool(self.active),
            "is_attack": kind == "attack",
            "is_anomaly": kind in ("attack", "fault"),
        }

    # --- containment ---------------------------------------------------------------
    def begin_containment(self) -> None:
        """Operator-approved simulated response, run in stages over the next few ticks."""
        self.containment_log = []
        self.containment = Containment(self.active, self.plant.tick)

    def log_action(self, text: str) -> None:
        self.containment_log.append({"t": self.plant.t, "action": text})

    # --- stepping ------------------------------------------------------------------
    def step(self, dt: float = 1.0) -> StepResult:
        if self.active:
            scenarios.on_tick(self.active, self, self.plant.tick - self._active_since_tick)
        if self.containment:
            self.containment.on_tick(self)
            if self.containment.done:
                self.containment = None
        if self.plant.tick % HEARTBEAT_EVERY_TICKS == 0:
            for plc in PLCS:
                if plc not in self.suppress_heartbeat:
                    self.emit("SCADA", plc, "READ", "STATUS", "ok", True)
        telemetry = self.plant.step(dt)
        events, self._pending = self._pending, []
        return StepResult(telemetry=telemetry, events=events)
