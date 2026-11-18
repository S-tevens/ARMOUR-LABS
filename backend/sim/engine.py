"""Simulation engine: advances the plant, runs scenarios, emits network events."""
from __future__ import annotations

from dataclasses import dataclass, field

from core.contracts import NetworkEvent, Telemetry
from sim import scenarios
from sim.plant import Plant

HEARTBEAT_EVERY_TICKS = 5


@dataclass
class StepResult:
    telemetry: Telemetry
    events: list[NetworkEvent] = field(default_factory=list)


class SimulationEngine:
    def __init__(self, seed: int = 42) -> None:
        self.plant = Plant(seed)
        self.seq = 0
        self.active: str | None = None
        self._active_since_tick = 0
        self._pending: list[NetworkEvent] = []

    # --- events --------------------------------------------------------------------
    def _emit(self, src, dst, function_code, register, value, authorised) -> None:
        self.seq += 1
        self._pending.append(
            NetworkEvent(
                seq=self.seq,
                t=self.plant.t,
                src=src,
                dst=dst,
                function_code=function_code,
                register=register,
                value=value,
                authorised=authorised,
            )
        )

    # --- scenarios -----------------------------------------------------------------
    def start_scenario(self, name: str) -> None:
        if name not in scenarios.SCENARIO_INFO:
            raise KeyError(name)
        if self.active:
            self.stop_scenario()
        self.active = name
        self._active_since_tick = self.plant.tick
        scenarios.start(name, self.plant, self._emit)

    def stop_scenario(self) -> None:
        self.active = None
        scenarios.stop(self.plant)

    # --- stepping ------------------------------------------------------------------
    def step(self, dt: float = 1.0) -> StepResult:
        if self.active:
            scenarios.on_tick(self.active, self.plant, self.plant.tick - self._active_since_tick)
        if self.plant.tick % HEARTBEAT_EVERY_TICKS == 0:
            for plc in ("PLC-01", "PLC-02", "PLC-03"):
                self._emit("SCADA", plc, "READ", "STATUS", "ok", True)
        telemetry = self.plant.step(dt)
        events, self._pending = self._pending, []
        return StepResult(telemetry=telemetry, events=events)
