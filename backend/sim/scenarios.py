"""Attack and fault scenarios (owner: P2). All of this stays inside the simulation."""
from __future__ import annotations

from typing import Callable

from sim.plant import Plant

ATTACKER_IP = "10.0.0.66"

# Emit callback signature: emit(src, dst, function_code, register, value, authorised)
Emit = Callable[[str, str, str, str, object, bool], None]

SCENARIO_INFO: dict[str, dict] = {
    "unauthorised_valve_close": {
        "label": "Unauthorised valve close",
        "kind": "attack",
        "mitre": "T0855 Unauthorized Command Message",
        "description": "A non-SCADA source writes Valve 1 = CLOSE on PLC-02. Pressure rises, flow collapses.",
    },
    "false_data_injection": {
        "label": "False data injection",
        "kind": "attack",
        "mitre": "T0856 Spoof Reporting Message",
        "description": "A spoofed report biases the reported pressure. The real process is unchanged.",
    },
    "sensor_drift": {
        "label": "Sensor drift (benign fault)",
        "kind": "fault",
        "mitre": None,
        "description": "The pressure sensor slowly drifts. No malicious network activity.",
    },
}


def start(name: str, plant: Plant, emit: Emit) -> None:
    if name == "unauthorised_valve_close":
        plant.set_actuator("valve1", False)
        plant.plc_status["plc02"] = "compromised"
        emit(ATTACKER_IP, "PLC-02", "WRITE_COIL", "VALVE1", "CLOSE", False)
    elif name == "false_data_injection":
        plant.sensor_bias["pressure"] = 2.5
        plant.plc_status["plc03"] = "suspicious"
        emit(ATTACKER_IP, "SCADA", "REPORT", "PRESSURE", "spoofed", False)
    elif name == "sensor_drift":
        plant.plc_status["plc03"] = "suspicious"
    else:
        raise KeyError(name)


def on_tick(name: str, plant: Plant, ticks_since_start: int) -> None:
    if name == "sensor_drift":
        plant.sensor_bias["pressure"] = 0.04 * ticks_since_start


def stop(plant: Plant) -> None:
    plant.reset_to_safe()
