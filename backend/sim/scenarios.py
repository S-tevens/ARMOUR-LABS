"""Attack, fault and benign scenarios for the microgrid substation (owner: P2). Simulation only.

kind:
  attack - malicious activity (ground truth: is_attack)
  fault  - physical or sensor fault, not malicious (ground truth: anomaly but not attack)
  benign - legitimate operating or natural change that detectors must NOT flag
group: "core" scenarios are the demo set; "extra" ones are for evaluation and subtle cases.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid a circular import at runtime
    from sim.engine import SimulationEngine

ATTACKER_IP = "10.0.0.66"
FLOOD_PER_TICK = 25
FREQ_SPOOF_HZ = -0.5  # reported 49.5 Hz while the real frequency is 50 Hz
VOLT_SMALL_BIAS_PU = 0.02
VOLT_DRIFT_PER_TICK = 0.0007
VOLT_RAMP_PER_TICK = 0.0008
VOLT_RAMP_CAP_PU = 0.06
CLOUD_FACTOR = 0.3

SCENARIO_INFO: dict[str, dict] = {
    "unauthorised_breaker_trip": {
        "label": "Unauthorised breaker trip",
        "kind": "attack",
        "group": "core",
        "mitre": "T0855 Unauthorized Command Message",
        "description": "A non-SCADA source opens CB-CRIT. The hospital feeder loses power.",
    },
    "false_data_injection": {
        "label": "False frequency report",
        "kind": "attack",
        "group": "core",
        "mitre": "T0856 Spoof Reporting Message",
        "description": "A spoofed frequency of 49.5 Hz makes the controller over-discharge the battery. The grid itself is fine.",
    },
    "sensor_drift": {
        "label": "Voltage sensor drift (fault)",
        "kind": "fault",
        "group": "core",
        "mitre": None,
        "description": "The bus voltage sensor slowly drifts. No malicious network activity.",
    },
    "replay_attack": {
        "label": "Replay attack",
        "kind": "attack",
        "group": "extra",
        "mitre": "T0856 Spoof Reporting Message",
        "description": "Recorded normal readings and old messages are replayed while CB-CRIT is opened by an attacker.",
    },
    "dos_flood": {
        "label": "Denial of service",
        "kind": "attack",
        "group": "extra",
        "mitre": "T0814 Denial of Service",
        "description": "A message flood hits IED-03. Heartbeats are dropped and measurements go stale.",
    },
    "planned_switching": {
        "label": "Planned switching (legitimate)",
        "kind": "benign",
        "group": "extra",
        "mitre": None,
        "description": "SCADA opens CB-NC for planned work. Same physical effect as a trip, but authorised.",
    },
    "cloud_cover": {
        "label": "Passing clouds (natural)",
        "kind": "benign",
        "group": "extra",
        "mitre": None,
        "description": "Irradiance drops to 30%. PV output falls, which the weather station explains.",
    },
    "stuck_breaker": {
        "label": "Stuck breaker (fault)",
        "kind": "fault",
        "group": "extra",
        "mitre": None,
        "description": "SCADA commands CB-NC open, but the mechanism is stuck and it stays closed.",
    },
    "pv_inverter_trip": {
        "label": "PV inverter trip (fault)",
        "kind": "fault",
        "group": "extra",
        "mitre": None,
        "description": "The PV inverter trips offline. No network evidence.",
    },
    "fdi_small": {
        "label": "Small false data (subtle)",
        "kind": "attack",
        "group": "extra",
        "mitre": "T0856 Spoof Reporting Message",
        "description": "A small voltage bias with no network trace, designed to stay below simple thresholds.",
    },
    "fdi_slow_ramp": {
        "label": "Slow-ramp false data (subtle)",
        "kind": "attack",
        "group": "extra",
        "mitre": "T0856 Spoof Reporting Message",
        "description": "Reported voltage creeps up like a failing sensor, with no network trace. Hardest to tell from drift.",
    },
}


def start(name: str, eng: "SimulationEngine") -> None:
    p = eng.plant
    if name == "unauthorised_breaker_trip":
        p.set_breaker("cb_crit", False)
        p.ied_status["ied03"] = "compromised"
        eng.emit(ATTACKER_IP, "IED-03", "OPERATE", "CB_CRIT", "OPEN", False)
    elif name == "false_data_injection":
        p.sensor_bias["frequency"] = FREQ_SPOOF_HZ
        p.ied_status["ied01"] = "suspicious"
        eng.emit(ATTACKER_IP, "SCADA", "REPORT", "FREQUENCY", "spoofed", False)
    elif name == "sensor_drift":
        p.ied_status["ied01"] = "suspicious"
    elif name == "replay_attack":
        p.start_replay(30)  # meters now report recorded normal readings
        p.set_breaker("cb_crit", False)  # the real manipulation hidden behind the replay
        p.ied_status["ied03"] = "compromised"
        p.ied_status["ied01"] = "suspicious"
        eng.emit(ATTACKER_IP, "IED-03", "OPERATE", "CB_CRIT", "OPEN", False)
        _replay_old_messages(eng)
    elif name == "dos_flood":
        p.stale_prob = 0.5
        p.ied_status["ied03"] = "suspicious"
        eng.suppress_heartbeat.add("IED-03")
    elif name == "planned_switching":
        eng.command("CB_NC", "OPEN")
    elif name == "cloud_cover":
        p.cloud_target = CLOUD_FACTOR
    elif name == "stuck_breaker":
        p.stuck.add("cb_nc")  # mechanism fails first, then the authorised command is sent
        p.ied_status["ied03"] = "suspicious"
        eng.command("CB_NC", "OPEN")
    elif name == "pv_inverter_trip":
        p.pv_inverter_ok = False
        p.ied_status["ied02"] = "suspicious"
    elif name == "fdi_small":
        p.sensor_bias["bus_voltage"] = VOLT_SMALL_BIAS_PU  # stealthy: no unauthorised network event
        p.ied_status["ied01"] = "suspicious"
    elif name == "fdi_slow_ramp":
        p.ied_status["ied01"] = "suspicious"  # stealthy: no unauthorised network event
    else:
        raise KeyError(name)


def on_tick(name: str, eng: "SimulationEngine", n: int) -> None:
    """Called every tick while the scenario is active. n = ticks since it started."""
    p = eng.plant
    if name == "sensor_drift":
        p.sensor_bias["bus_voltage"] = VOLT_DRIFT_PER_TICK * n
    elif name == "fdi_slow_ramp":
        p.sensor_bias["bus_voltage"] = min(VOLT_RAMP_CAP_PU, VOLT_RAMP_PER_TICK * n)
    elif name == "dos_flood":
        for _ in range(FLOOD_PER_TICK):
            eng.emit(ATTACKER_IP, "IED-03", "READ", "STATUS", "flood", False)
    elif name == "replay_attack" and n % 5 == 0 and n > 0:
        _replay_old_messages(eng)


def _replay_old_messages(eng: "SimulationEngine") -> None:
    """Re-send old authorised messages with their ORIGINAL seq and timestamp (stale and duplicated)."""
    now = eng.plant.t
    old = [e for e in eng.event_log if e.authorised and e.t < now - 10.0][-3:]
    for e in old:
        eng.emit(e.src, e.dst, e.function_code, e.register, e.value, False, seq=e.seq, t=e.t)
