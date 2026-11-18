"""Simulated containment (owner: P2). Staged, so the process is never snapped back instantly.

Stage 0 (t+0): block the malicious source (attacks only) and drop spoofing/replay/DoS effects.
Stage 1 (t+1): safe state: recalibrate sensors, service faults, reduce Pump 1 speed, open Valve 1.
Stage 4 (t+4): restore: return Pump 1 to full speed and clear PLC flags.

Every change to the plant goes through an authorised SCADA command or a logged maintenance action,
so the digital twin's authorised command log reflects the response.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sim.scenarios import ATTACKER_IP, SCENARIO_INFO

if TYPE_CHECKING:
    from sim.engine import SimulationEngine

SAFE_SPEED = 0.6
SAFE_STATE_AT = 1
RESTORE_AT = 4


class Containment:
    def __init__(self, scenario: str | None, start_tick: int) -> None:
        self.scenario = scenario
        self.start_tick = start_tick
        self.done = False

    def on_tick(self, eng: "SimulationEngine") -> None:
        n = eng.plant.tick - self.start_tick
        if n == 0:
            self._block(eng)
        elif n == SAFE_STATE_AT:
            self._safe_state(eng)
        elif n >= RESTORE_AT:
            self._restore(eng)
            self.done = True

    def _block(self, eng: "SimulationEngine") -> None:
        p = eng.plant
        kind = SCENARIO_INFO.get(self.scenario or "", {}).get("kind")
        if kind == "attack":
            eng.emit("FIREWALL", ATTACKER_IP, "BLOCK", "SOURCE", ATTACKER_IP, True)
            eng.log_action(f"Blocked source {ATTACKER_IP} at the firewall; unauthorised commands now rejected")
            p.clear_sensor_faults()
            eng.suppress_heartbeat.clear()
            eng.log_action("Dropped spoofed readings; sensors report live values again")
        else:
            eng.log_action("No malicious source to block")
        eng.active = None  # the scenario's effects are handled below, not re-applied every tick

    def _safe_state(self, eng: "SimulationEngine") -> None:
        p = eng.plant
        p.clear_sensor_faults()
        eng.log_action("Recalibrated sensors")
        if p.valve_stuck is not None:
            p.valve_stuck = None
            eng.log_action("Serviced Valve 1 actuator")
        if p.filter_clog > 0 or p.clog_rate > 0:
            p.filter_clog, p.clog_rate = 0.0, 0.0
            eng.log_action("Cleaned the filter")
        eng.command("PLC-01", "PUMP1_SPEED", SAFE_SPEED)
        eng.log_action(f"Pump 1 reduced to {int(SAFE_SPEED * 100)}% (safe state)")
        if not p.valve1:
            eng.command("PLC-02", "VALVE1", "OPEN")
            eng.log_action("Valve 1 reopened by SCADA")

    def _restore(self, eng: "SimulationEngine") -> None:
        p = eng.plant
        eng.command("PLC-01", "PUMP1_SPEED", 1.0)
        for k in p.plc_status:
            p.plc_status[k] = "normal"
        eng.log_action("Pump 1 returned to full speed; controllers cleared")
