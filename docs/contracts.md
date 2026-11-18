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
| GET | `/scenarios` | list of scenarios (`name, label, kind, mitre, description`) |
| POST | `/scenario/start` `{name}` | start a scenario (404 if unknown) |
| POST | `/scenario/stop` | stop the scenario and restore the safe lineup |
| GET | `/incidents` | all incidents |
| POST | `/incident/{id}/approve-response` | simulated containment; status becomes `recovering`, then `recovered` once checks pass |
| GET | `/incidents/{id}/replay` | recorded events/telemetry around the incident, from the event log |
| GET | `/metrics` | evaluation results (not implemented yet) |

## Scenarios
`unauthorised_valve_close` (attack), `false_data_injection` (attack), `sensor_drift` (benign fault).
