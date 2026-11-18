"""Attack, fault and benign scenarios (owner: P2). All of this stays inside the simulation.

kind:
  attack - malicious activity (ground truth: is_attack)
  fault  - physical/sensor fault, not malicious (ground truth: anomaly but not attack)
  benign - legitimate operating change that detectors must NOT flag
group: "core" scenarios are the demo set; "extra" ones are for evaluation and subtle cases.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid a circular import at runtime
    from sim.engine import SimulationEngine

ATTACKER_IP = "10.0.0.66"
FLOOD_PER_TICK = 25
CLOG_RATE_PER_S = 1.0 / 400.0
SLOW_RAMP_PER_TICK = 0.03
SLOW_RAMP_CAP_BAR = 3.0
SMALL_BIAS_BAR = 0.35

SCENARIO_INFO: dict[str, dict] = {
    "unauthorised_valve_close": {
        "label": "Unauthorised valve close",
        "kind": "attack",
        "group": "core",
        "mitre": "T0855 Unauthorized Command Message",
        "description": "A non-SCADA source writes Valve 1 = CLOSE on PLC-02. Pressure rises, flow collapses.",
    },
    "false_data_injection": {
        "label": "False data injection",
        "kind": "attack",
        "group": "core",
        "mitre": "T0856 Spoof Reporting Message",
        "description": "A spoofed report biases the reported pressure. The real process is unchanged.",
    },
    "sensor_drift": {
        "label": "Sensor drift (benign fault)",
        "kind": "fault",
        "group": "core",
        "mitre": None,
        "description": "The pressure sensor slowly drifts. No malicious network activity.",
    },
    "replay_attack": {
        "label": "Replay attack",
        "kind": "attack",
        "group": "extra",
        "mitre": "T0856 Spoof Reporting Message",
        "description": "Old pressure/flow readings and old messages are replayed while Valve 1 is closed by an attacker.",
    },
    "dos_flood": {
        "label": "Denial of service",
        "kind": "attack",
        "group": "extra",
        "mitre": "T0814 Denial of Service",
        "description": "A message flood hits PLC-03. Heartbeats are dropped and sensor updates go stale.",
    },
    "operator_setpoint_change": {
        "label": "Operator speed change (legitimate)",
        "kind": "benign",
        "group": "extra",
        "mitre": None,
        "description": "SCADA lowers Pump 1 speed to 85%. Authorised, so it must not be flagged as an attack.",
    },
    "stuck_valve": {
        "label": "Stuck valve (fault)",
        "kind": "fault",
        "group": "extra",
        "mitre": None,
        "description": "Valve 1 sticks half open although it is commanded open. No network evidence.",
    },
    "filter_clog": {
        "label": "Filter clogging (fault)",
        "kind": "fault",
        "group": "extra",
        "mitre": None,
        "description": "The filter gradually clogs: flow falls and pressure rises slowly.",
    },
    "fdi_small": {
        "label": "Small false data (subtle)",
        "kind": "attack",
        "group": "extra",
        "mitre": "T0856 Spoof Reporting Message",
        "description": "A small constant pressure bias with no network trace, designed to stay below simple thresholds.",
    },
    "fdi_slow_ramp": {
        "label": "Slow-ramp false data (subtle)",
        "kind": "attack",
        "group": "extra",
        "mitre": "T0856 Spoof Reporting Message",
        "description": "Reported pressure creeps up slowly like a fault, with no network trace. Hardest to tell from sensor drift.",
    },
}


def start(name: str, eng: "SimulationEngine") -> None:
    p = eng.plant
    if name == "unauthorised_valve_close":
        p.set_actuator("valve1", False)
        p.plc_status["plc02"] = "compromised"
        eng.emit(ATTACKER_IP, "PLC-02", "WRITE_COIL", "VALVE1", "CLOSE", False)
    elif name == "false_data_injection":
        p.sensor_bias["pressure"] = 2.5
        p.plc_status["plc03"] = "suspicious"
        eng.emit(ATTACKER_IP, "SCADA", "REPORT", "PRESSURE", "spoofed", False)
    elif name == "sensor_drift":
        p.plc_status["plc03"] = "suspicious"
    elif name == "replay_attack":
        p.start_replay(30)  # sensors now report recorded normal pressure/flow
        p.set_actuator("valve1", False)  # the real manipulation hidden behind the replay
        p.plc_status["plc02"] = "compromised"
        p.plc_status["plc03"] = "suspicious"
        eng.emit(ATTACKER_IP, "PLC-02", "WRITE_COIL", "VALVE1", "CLOSE", False)
        _replay_old_messages(eng)
    elif name == "dos_flood":
        p.stale_prob = 0.5
        p.plc_status["plc03"] = "suspicious"
        eng.suppress_heartbeat.add("PLC-03")
    elif name == "operator_setpoint_change":
        eng.command("PLC-01", "PUMP1_SPEED", 0.85)
    elif name == "stuck_valve":
        p.valve_stuck = 0.5
        p.plc_status["plc02"] = "suspicious"
    elif name == "filter_clog":
        p.clog_rate = CLOG_RATE_PER_S
    elif name == "fdi_small":
        p.sensor_bias["pressure"] = SMALL_BIAS_BAR  # stealthy: no unauthorised network event
        p.plc_status["plc03"] = "suspicious"
    elif name == "fdi_slow_ramp":
        p.plc_status["plc03"] = "suspicious"  # stealthy: no unauthorised network event
    else:
        raise KeyError(name)


def on_tick(name: str, eng: "SimulationEngine", n: int) -> None:
    """Called every tick while the scenario is active. n = ticks since it started."""
    p = eng.plant
    if name == "sensor_drift":
        p.sensor_bias["pressure"] = 0.04 * n
    elif name == "fdi_slow_ramp":
        p.sensor_bias["pressure"] = min(SLOW_RAMP_CAP_BAR, SLOW_RAMP_PER_TICK * n)
    elif name == "dos_flood":
        for _ in range(FLOOD_PER_TICK):
            eng.emit(ATTACKER_IP, "PLC-03", "READ", "STATUS", "flood", False)
    elif name == "replay_attack" and n % 5 == 0 and n > 0:
        _replay_old_messages(eng)


def _replay_old_messages(eng: "SimulationEngine") -> None:
    """Re-send old authorised messages with their ORIGINAL seq and timestamp (stale and duplicated)."""
    now = eng.plant.t
    old = [e for e in eng.event_log if e.authorised and e.t < now - 10.0][-3:]
    for e in old:
        eng.emit(e.src, e.dst, e.function_code, e.register, e.value, False, seq=e.seq, t=e.t)
