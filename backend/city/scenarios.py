"""City scenarios (owner: P2). Simulation only.

kind: attack | fault | benign (same meaning as the substation scenarios).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from city.engine import CityEngine

ATTACKER_IP = "10.0.0.66"
ATTACK_DEMAND_FACTOR = 1.75
EVENING_PEAK_FACTOR = 1.25
FLOOD_PER_TICK = 25

SCENARIO_INFO: dict[str, dict] = {
    "coordinated_substation_trip": {
        "label": "Coordinated substation trip",
        "kind": "attack",
        "group": "core",
        "mitre": "T0855 Unauthorized Command Message",
        "description": "An attacker opens the breakers of three central substations at once (the Ukraine 2015 pattern).",
    },
    "load_altering_attack": {
        "label": "Load-altering attack",
        "kind": "attack",
        "group": "core",
        "mitre": "T0831 Manipulation of Control",
        "description": "Compromised chargers and smart devices push city demand up 75 %. Lines overload and trip in a cascade.",
    },
    "comms_loss": {
        "label": "Control-centre comms loss",
        "kind": "attack",
        "group": "extra",
        "mitre": "T0814 Denial of Service",
        "description": "A message flood blinds the control centre to one district. No physical change.",
    },
    "planned_maintenance": {
        "label": "Planned line maintenance (legitimate)",
        "kind": "benign",
        "group": "extra",
        "mitre": None,
        "description": "SCADA opens a transmission line for maintenance. Power reroutes; nothing should be flagged.",
    },
    "evening_peak": {
        "label": "Hot-evening demand peak (natural)",
        "kind": "benign",
        "group": "extra",
        "mitre": None,
        "description": "Demand rises 25 % on the forecast schedule. Lines get busy but stay in limits.",
    },
    "line_fault": {
        "label": "Line fault (equipment)",
        "kind": "fault",
        "group": "extra",
        "mitre": None,
        "description": "A transmission line trips on a fault. No malicious traffic; power reroutes.",
    },
}


def start(name: str, eng: "CityEngine", districts: list[str] | None = None) -> None:
    if name == "coordinated_substation_trip":
        for did in districts or eng.cfg.defaults["trip_districts"]:
            if did not in eng.main_closed:
                raise ValueError(f"unknown district {did}")
            eng.main_closed[did] = False
            eng.emit(ATTACKER_IP, f"SUB-{did.upper()}", "OPERATE", "DIST_MAIN", "OPEN", False)
            eng.unit_actions.append((did, "unauthorised_grid_loss"))
    elif name == "load_altering_attack":
        eng.attack_target = ATTACK_DEMAND_FACTOR
        eng.emit(ATTACKER_IP, "EV-GATEWAY", "WRITE_SETPOINT", "CHARGER_LOAD", "MAX", False)
    elif name == "comms_loss":
        chosen = districts or eng.cfg.defaults["stale_districts"]
        unknown = [d for d in chosen if d not in eng.main_closed]
        if unknown:
            raise ValueError(f"unknown district {unknown[0]}")
        eng.stale = set(chosen)
    elif name == "planned_maintenance":
        eng.command(f"LINE_{eng.cfg.defaults['maintenance_line']}", "OPEN")
    elif name == "evening_peak":
        eng.forecast_target = EVENING_PEAK_FACTOR
    elif name == "line_fault":
        fault = eng.cfg.defaults["fault_line"]
        eng.service.discard(fault)
        eng.out_reason[fault] = "fault"
        eng.emit(f"RELAY-{fault}", "CITY-SCADA", "TRIP", fault, "fault", True)  # a legitimate protection report
    else:
        raise KeyError(name)


def on_tick(name: str, eng: "CityEngine", n: int) -> None:
    if name == "load_altering_attack" and n > 0 and n % 10 == 0:
        eng.emit(ATTACKER_IP, "EV-GATEWAY", "WRITE_SETPOINT", "CHARGER_LOAD", "MAX", False)
    elif name == "comms_loss":
        for did in eng.stale:
            for _ in range(FLOOD_PER_TICK):
                eng.emit(ATTACKER_IP, f"SUB-{did.upper()}", "READ", "STATUS", "flood", False)
