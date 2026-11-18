"""Simulated containment (owner: P2). Staged, so the substation is never snapped back instantly.

Stage 0 (t+0): block the malicious source (attacks only) and drop spoofing, replay and DoS effects.
Stage 1 (t+1): safe state: recalibrate sensors, repair faults, hold the battery idle, and reclose any
               open breaker (hospital feeder first).
Stage 4 (t+4): restore: return the battery to automatic control and clear the IED flags.

Every change to the substation goes through an authorised SCADA command or a logged maintenance
action, so the digital twin's authorised command log reflects the response.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sim.scenarios import ATTACKER_IP, SCENARIO_INFO

if TYPE_CHECKING:
    from sim.engine import SimulationEngine

SAFE_STATE_AT = 1
RESTORE_AT = 4
RECLOSE_ORDER = ("CB_CRIT", "CB_MAIN", "CB_PV", "CB_BESS", "CB_NC")  # critical load first
LABEL = {"CB_MAIN": "main breaker", "CB_PV": "PV breaker", "CB_BESS": "battery breaker",
         "CB_CRIT": "hospital feeder breaker", "CB_NC": "campus feeder breaker"}


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
            eng.log_action("Dropped spoofed readings; meters report live values again")
        else:
            eng.log_action("No malicious source to block")
        eng.active = None  # effects are handled below, not re-applied every tick

    def _safe_state(self, eng: "SimulationEngine") -> None:
        p = eng.plant
        p.clear_sensor_faults()
        eng.log_action("Recalibrated meters")
        if p.stuck:
            p.stuck.clear()
            eng.log_action("Serviced the stuck breaker mechanism")
        if not p.pv_inverter_ok:
            p.pv_inverter_ok = True
            eng.log_action("Restarted the PV inverter")
        p.cloud_target = 1.0
        eng.command("BESS_MODE", "HOLD")
        eng.log_action("Battery held idle (safe state)")
        for reg in RECLOSE_ORDER:
            breaker = {"CB_MAIN": "cb_main", "CB_PV": "cb_pv", "CB_BESS": "cb_bess",
                       "CB_CRIT": "cb_crit", "CB_NC": "cb_nc"}[reg]
            if not p.breakers[breaker]:
                eng.command(reg, "CLOSE")
                eng.log_action(f"Reclosed the {LABEL[reg]} from SCADA")

    def _restore(self, eng: "SimulationEngine") -> None:
        p = eng.plant
        eng.command("BESS_MODE", "AUTO")
        for k in p.ied_status:
            p.ied_status[k] = "normal"
        eng.log_action("Battery returned to automatic control; IEDs cleared")
