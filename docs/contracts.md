# Shared contracts

The single source of truth is `backend/core/contracts.py`. `frontend/src/types.ts` mirrors it.
**Changing a contract needs all three contributors to agree.** Update the backend model, the TypeScript type and this file in the same pull request.

## Units and conventions
- `t` is simulation time in seconds. `tick` is the integer tick counter (1 tick = 1 s by default).
- `pump1`, `pump2`: `true` = running. `valve1`: `true` = open.
- Levels are percent (0-100), pressure in bar, flow in L/min, temperature in °C.
- PLC mapping: **PLC-01** drives Pump 1 and Pump 2; **PLC-02** drives Valve 1; **PLC-03** reads all sensors. PLCs receive commands from SCADA; they do not issue them.

## WebSocket `GET /ws/telemetry`
Each message is an envelope `{ "type": ..., "data": ... }`. Types:

| type | data | when |
|---|---|---|
| `telemetry` | Telemetry | every tick |
| `event` | NetworkEvent | when a network/command event happens (heartbeats every 5 ticks) |
| `twin` | TwinState | every tick |
| `scores` | Scores | every tick |
| `incident` | Incident | when an incident is created or its status changes |

### Telemetry
`{t, tick, tank1_level, tank2_level, pressure, flow, temperature, pump1, pump2, valve1, plc_status:{plc01, plc02, plc03}}` where each PLC status is `normal | suspicious | compromised`.

### NetworkEvent
`{seq, t, src, dst, function_code, register, value, authorised}`. Replay is detectable through duplicate/stale `seq`/`t` or a command invalid in the current state.

### TwinState
`{t, expected:{var: number}, residual:{var: number}, norm_residual:{var: number}}` for `tank1_level, tank2_level, pressure, flow, temperature`.

### Scores
`{t, network, controller, process, twin}`, each in [0,1].

### Incident
`{id, t_start, severity (low|medium|high), confidence, affected_devices[], classification (attack|fault|unknown), scores{}, evidence[{type, text, tag}], status (open|responding|recovering|recovered|unresolved)}`. Evidence `tag` is `observed`, `correlated` or `inferred`. Evidence text must only use real measured fields.

## REST
| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness, tick, active scenario |
| GET | `/scenarios` | list of scenarios (`name, label, kind, group, mitre, description`) |
| POST | `/scenario/start` `{name}` | start a scenario (404 if unknown) |
| POST | `/scenario/stop` | stop the scenario and restore the safe lineup |
| GET | `/incidents` | all incidents |
| POST | `/incident/{id}/approve-response` | simulated containment; status becomes `recovering`, then `recovered` once checks pass |
| GET | `/incidents/{id}/replay` | recorded events/telemetry around the incident, from the event log |
| GET | `/recovery` | latest recovery verification report (`state` idle/recovering/recovered/unresolved, per-variable limits, seconds in range) plus the containment actions taken |
| GET | `/metrics` | evaluation results (not implemented yet) |

## Scenarios
`kind` is the ground truth: `attack` (malicious), `fault` (physical or sensor fault, not malicious), `benign` (legitimate operating change that must not be flagged). `group` is `core` (demo set) or `extra` (evaluation and subtle cases).

| name | kind | what it does |
|---|---|---|
| `unauthorised_valve_close` | attack | non-SCADA write closes Valve 1 on PLC-02 |
| `false_data_injection` | attack | spoofed report biases reported pressure (+2.5 bar) |
| `replay_attack` | attack | recorded pressure/flow replayed while an attacker closes Valve 1; old messages re-sent with stale `seq`/`t` |
| `dos_flood` | attack | 25 unauthorised messages/s to PLC-03, heartbeats dropped, sensor updates go stale |
| `fdi_small` | attack | +0.35 bar bias, no network trace (subtle) |
| `fdi_slow_ramp` | attack | slowly growing bias, no network trace (subtle, resembles drift) |
| `sensor_drift` | fault | pressure sensor drifts, no network trace |
| `stuck_valve` | fault | Valve 1 stuck half open though commanded open |
| `filter_clog` | fault | filter clogs gradually: flow down, pressure up |
| `operator_setpoint_change` | benign | authorised SCADA command, Pump 1 to 85% |

## Containment and recovery
`POST /incident/{id}/approve-response` starts staged containment: t+0 block the source (attacks) and drop spoofing, t+1 safe state (recalibrate, service faults, Pump 1 to 60%, reopen Valve 1), t+4 restore Pump 1 to full speed. Changes are authorised SCADA commands, so they appear in the event stream and the command log.

Recovery is verified by `sim/recovery.py`: pressure 1.8-2.5 bar, flow 95-125 L/min, Tank 1 52-72%, Tank 2 38-58%, Valve 1 open and both pumps on, held for 10 s. `unresolved` after 90 s without recovery.

## Authorised command log
`SimulationEngine.command_log` holds only authorised write commands. The independent digital twin must use this as its only command input.
