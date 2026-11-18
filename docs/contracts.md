# Shared contracts

The single source of truth is `backend/core/contracts.py`. `frontend/src/types.ts` mirrors it.
**Changing a contract needs everyone's agreement.** Update the backend model, the TypeScript type and this file in the same pull request.

## The substation

```text
UTILITY ──[CB-MAIN]──┬──────────── bus ────────────┬──────────┐
                     │                             │          │
           [CB-PV]── PV array        [CB-BESS]── Battery      ├─[CB-CRIT]── Hospital (critical load)
                                                              └─[CB-NC]──── Campus (non-critical load)
```

IEDs (protection relays and controllers), all commanded by SCADA / the microgrid controller:

| IED | Role | Devices |
|---|---|---|
| **IED-01** | Utility interface | CB-MAIN, grid meter (frequency, voltage, import) |
| **IED-02** | Solar and battery | CB-PV, CB-BESS, PV inverter, battery set-points |
| **IED-03** | Load feeders | CB-CRIT (hospital), CB-NC (campus) |

IEDs receive commands from SCADA; they do not issue them. Protocols modelled: IEC 61850 style `OPERATE` for breakers and `WRITE_SETPOINT` for set-points.

## Units and conventions
- `t` is simulation time in seconds. `tick` is the integer tick counter (1 tick = 1 s by default).
- Powers are kW. `grid_import_kw`: positive = importing from the utility, negative = exporting. `bess_kw`: positive = discharging, negative = charging.
- `frequency` in Hz (nominal 50), `bus_voltage` in per unit (nominal 1.0), `bess_soc` in percent, `irradiance` in W/m2.
- Breakers (`cb_main`, `cb_pv`, `cb_bess`, `cb_crit`, `cb_nc`): `true` = closed.

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
`{t, tick, frequency, bus_voltage, grid_import_kw, pv_kw, bess_kw, bess_soc, load_critical_kw, load_noncritical_kw, irradiance, cb_main, cb_pv, cb_bess, cb_crit, cb_nc, ied_status:{ied01, ied02, ied03}}` where each IED status is `normal | suspicious | compromised`.

### NetworkEvent
`{seq, t, src, dst, function_code, register, value, authorised}`.
- Heartbeats: `SCADA -> IED-0x READ STATUS`, every 5 ticks, authorised.
- Commands: `OPERATE` on `CB_MAIN | CB_PV | CB_BESS | CB_CRIT | CB_NC` with value `OPEN` or `CLOSE`; `WRITE_SETPOINT` on `BESS_MODE` (`AUTO` or `HOLD`) and `IMPORT_TARGET_KW`.
- Replay is detectable through duplicate or stale `seq`/`t`, or a command invalid in the current state.

### TwinState
`{t, expected:{var: number}, residual:{var: number}, norm_residual:{var: number}}` for `frequency, bus_voltage, grid_import_kw, pv_kw, bess_kw, bess_soc, load_critical_kw, load_noncritical_kw, breaker_mismatch`. `breaker_mismatch` is the number of observed breaker states that differ from the states implied by the authorised command log (expected 0).

### Scores
`{t, network, controller, process, twin, invariants, ml}`, each in [0,1]. `invariants` (physics checks) and `ml` (trained anomaly model) stay 0 during the 10-second warm-up and when `ARMOUR_ML=0`. An alert is a score of 0.8 or more for two consecutive seconds. Open incidents show the latest scores and add `physics_check` and `ml_anomaly` evidence.

### Incident
`{id, t_start, severity (low|medium|high), confidence, affected_devices[], classification (attack|fault|unknown), scores{}, evidence[{type, text, tag}], status (open|responding|recovering|recovered|unresolved)}`. Evidence `tag` is `observed`, `correlated` or `inferred`. Evidence text must only use real measured values.

## REST
| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness, tick, active scenario |
| GET | `/scenarios` | list of scenarios (`name, label, kind, group, mitre, description`) |
| POST | `/scenario/start` `{name}` | start a scenario (404 if unknown) |
| POST | `/scenario/stop` | hard reset: end the scenario, repair faults, restore the normal lineup |
| GET | `/incidents` | all incidents |
| POST | `/incident/{id}/approve-response` | simulated containment; status becomes `recovering`, then `recovered` once checks pass |
| GET | `/incidents/{id}/replay` | recorded events/telemetry around the incident, from the event log |
| GET | `/recovery` | latest recovery verification report (`state` idle/recovering/recovered/unresolved, per-variable limits, seconds in range) plus the containment actions taken |
| GET | `/metrics` | evaluation results: `status` (`ok`, `running`, `error`, `not_computed`), `detectors[]`, `scenarios[]`, `protocol`, `training`, `fresh_check`, `limitations`, `source`. See docs/evaluation.md |
| POST | `/metrics/run` | recompute the evaluation in the background (about 30 s); returns `{started}`, false if one is already running |

## Scenarios
`kind` is the ground truth: `attack` (malicious), `fault` (physical or sensor fault, not malicious), `benign` (legitimate or natural change that must not be flagged). `group` is `core` (demo set) or `extra` (evaluation and subtle cases).

| name | kind | what it does |
|---|---|---|
| `unauthorised_breaker_trip` | attack | a non-SCADA source opens CB-CRIT: the hospital feeder loses power |
| `false_data_injection` | attack | spoofed frequency report (49.5 Hz); the controller reads it and over-discharges the battery while the real grid is fine |
| `replay_attack` | attack | recorded normal readings replayed while CB-CRIT is opened by an attacker; old messages re-sent with stale `seq`/`t` |
| `dos_flood` | attack | 25 unauthorised messages/s to IED-03, its heartbeats dropped, measurements go stale |
| `fdi_small` | attack | +0.02 pu voltage bias, no network trace (subtle) |
| `fdi_slow_ramp` | attack | slowly growing voltage bias, no network trace (subtle, resembles drift) |
| `sensor_drift` | fault | bus voltage sensor drifts, no network trace |
| `stuck_breaker` | fault | SCADA commands CB-NC open (authorised) but the mechanism is stuck and it stays closed |
| `pv_inverter_trip` | fault | the PV inverter trips offline, no network evidence |
| `planned_switching` | benign | SCADA opens CB-NC (authorised): same physical effect as a trip, but expected |
| `cloud_cover` | benign | irradiance drops to 30%; PV output falls and the weather station explains it |

## Digital twin
`twin/twin.py` is a model-based, independent expectation. It has its own parameters (not the simulator's constants), and its only command input is the **authorised command log** (`SimulationEngine.command_log`), never the observed breaker or set-point states. Other inputs: the clock (schedule/forecast) and the weather-station irradiance reading. A test proves its expectations do not change when observed breaker states change.

This is what separates the look-alike cases:
- authorised planned switching: the load drop is expected, no residual
- unauthorised trip: breaker state and load differ from the command log, residual
- stuck breaker: the command was authorised but the load did not drop, residual with no network evidence

## Containment and recovery
`POST /incident/{id}/approve-response` starts staged containment: t+0 block the source (attacks) and drop spoofing, replay and DoS effects; t+1 safe state (recalibrate meters, repair faults, hold the battery idle, reclose open breakers with the hospital feeder first); t+4 return the battery to automatic control. Changes are authorised SCADA commands, so they appear in the event stream and the command log.

Recovery is verified by `sim/recovery.py`: frequency 49.85-50.15 Hz, bus voltage 0.97-1.03 pu, utility import 150-480 kW, battery charge 35-90%, hospital load 340-460 kW, all five breakers closed, held for 10 s. `unresolved` after 90 s without recovery.
