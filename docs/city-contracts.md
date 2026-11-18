# City contracts

The city layer sits above the substation layer ([contracts.md](contracts.md)). Sources of truth: `backend/city/` (model), `backend/api/city_runtime.py` (what is streamed), `backend/core/contracts.py` (the shared `Incident`), mirrored in `frontend/src/city/types.ts`. Changing a shape needs everyone's agreement and an update to all three places in one pull request.

> **Real topology, simulated physics.** The default grid is Bengaluru's, built from OpenStreetMap (substations, mapped line routes, hospitals, metro stations). Many ties are inferred because OpenStreetMap's line mapping is incomplete (shown dashed), and all loads, ratings, populations and attacks are simulated. It is not BESCOM or KPTCL data. The small fictional `synthetic.json` network is the test fixture; select it with `ARMOUR_CITY=synthetic`.

## Model

- **Nodes:** the 37 simulated nodes are the 220 kV and 400 kV substations from OpenStreetMap (ids such as `nimhans`, `hoodi`). Each has a population and a base load (MW, simulated from the 66 kV substations it would feed) and facilities with a priority (hospital 1; metro and airport 2). In the code and the API they are still called districts. The five 400 kV nodes are the grid entry points, fed from the state grid.
- **Network:** 51 lines: 8 mapped in OpenStreetMap (`source: osm`, with the real route as a `path`), 38 inferred ties (`source: inferred`) and 5 grid-entry lines (`source: grid-entry`, from the state grid to each 400 kV node; the state grid is the power-flow slack). Ratings are simulated: `city/tools/build_osm_city.py` calibrates them so normal operation sits at 45-68 % loading and the demo scenarios behave sensibly.
- **Power flow:** linear (DC). Each line's susceptance is proportional to its capacity, so equal loading percentages mean equal angle differences. A line whose loading stays above 110 % for 6 s trips (above 140 % it trips at once). At most one line trips per tick, so a cascade unfolds visibly. Districts cut off from the grid go dark.
- **Each substation is a full substation unit** (the model in `contracts.md`) with sizes scaled for that district. When the city cuts a district off, its substation islands; when the city raises demand, its loads rise. The featured substation is `nimhans`.
- **Frequency:** a simple load-rejection model, 50 Hz plus 2 Hz times the fraction of load lost, with a lag. It is a display signal, not a stability model.
- **Accelerated time:** impact accounting and hospital backup run at 1 simulated minute per second (`MINUTES_PER_TICK`). A hospital has 90 minutes of backup, so it lasts 90 s in a demo. The UI says so.

## REST

| Method | Path | Purpose |
|---|---|---|
| GET | `/city` | `{layout, state, incidents}`: static layout, the latest state, all city incidents |
| GET | `/city/scenarios` | city scenarios (`name, label, kind, group, mitre, description`) |
| POST | `/city/scenario/start` `{name, districts?}` | start a city scenario (404 unknown, 422 invalid district) |
| POST | `/city/scenario/stop` | hard reset to a healthy city |
| GET | `/city/incidents` | all city incidents |
| POST | `/city/incident/{id}/approve-response` | approve containment: status `recovering`, then `recovered` or `unresolved` |
| GET | `/city/recovery` | `{report, actions}`: the checklist and the containment actions so far |

The substation endpoints (`/scenario/start`, `/incidents`, `/incident/{id}/approve-response`, `/incidents/{id}/replay`, `/recovery`, and the WebSocket `/ws/telemetry`) accept an optional `district` query parameter. Without it they act on the featured district, so the original single-substation API is unchanged.

## WebSocket `GET /ws/city`

Envelopes `{type, data}`, one `city` message per tick:

| type | data |
|---|---|
| `city` | CityState (below) |
| `city_incident` | Incident, when created or its status changes |
| `city_event` | NetworkEvent (unauthorised events and authorised commands; routine heartbeats are not sent) |

### Layout (`/city` → `layout`)
```text
name, note, data_note, attribution, center, zoom, featured
feeders[]:   name, lat, lon, voltage_kv, parent        # the 66 kV substations, shown as context
districts[]: id, name, lat, lon, voltage_kv, entry, population, base_load_mw,
             facilities[]: id, type, priority, name, lat, lon
lines[]:     id, from, to, capacity_mw, voltage_kv, source (osm | inferred | grid-entry), path[[lat, lon], ...]
```
`from` is `GRID` for the grid-entry lines. `path` is the real mapped route for `osm` lines. (The synthetic fixture uses `x`, `y` and `terminal` instead of coordinates.)

### CityState
```text
t, tick, frequency, scenario, status (normal | attention | incident), incident_id, accelerated, featured
districts[]: id, name, x, y, population, status (ok | attention | dark | stale),
             served_pct, people_unserved, load_mw,
             facilities[]: id, type, priority, status (ok | backup | down), backup_minutes_left
lines[]:     id, from, to, flow_mw, capacity_mw, loading, status (in_service | tripped | fault | open)
impact:      people_unserved, hospitals_on_backup, hospitals_down, critical_sites_down,
             energy_not_served_mwh, restoration_pct
recovery:    state (idle | recovering | recovered | unresolved), elapsed, seconds_in_range, dwell,
             checks[]: name, ok, detail
actions[]:   the latest containment actions (plain sentences)
failures[]:  the order things failed in this incident (the domino): n, t, kind (line | district | facility), id, text
twin, scores: summaries for debugging (max_norm_residual, topology and district mismatch; the four scores)
```
`attention` on a district means an adjacent line is above 90 % loading. `stale` means the control centre has lost sight of it. A line is `open` when an authorised command opened it (planned work), `tripped` when protection did, `fault` after an equipment fault.

### Incident additions
`district` (substation incidents: which district) and `campaign_id` (city incidents that span two or more districts share `CMP-001`). City incident ids start with `CIT-`.

## City scenarios

| name | kind | what it does |
|---|---|---|
| `coordinated_substation_trip` | attack | opens the breakers of three central substations with hospitals (`scenario_defaults.trip_districts`: East Division Compound, A Station, NIMHANS); also reaches each substation's own unit |
| `load_altering_attack` | attack | compromised chargers and smart devices push city demand up 75 %; lines overload and trip in a cascade |
| `comms_loss` | attack | a message flood blinds the control centre to one substation (default Puttenahalli); no physical change |
| `planned_maintenance` | benign | SCADA opens a transmission line (`maintenance_line`, authorised); power reroutes |
| `evening_peak` | benign | demand rises 25 % on the schedule the twin knows about |
| `line_fault` | fault | a transmission line (`fault_line`) trips on a fault; power reroutes |

## City twin
`backend/city/twin.py`. Expected city behaviour from the **authorised command log** (district-breaker and line commands) and the **scheduled demand forecast** only. It has its own demand model (a slightly different ripple), and a test proves its expectations do not change when the observed topology changes. Residuals: per-line flow residuals (scaled to 6 % of capacity), `topology_mismatch` (lines out that were not commanded out) and `district_mismatch` (districts dark that were not commanded dark).

## Detection and classification (rule-based v0)
Scores: network (an unauthorised message in the last 10 s), process (fixed limits: a dark district, line loading, frequency) and twin (largest normalised residual). An alert at 0.8 or more opens one city incident. The classification is a small executable rule table:

| Evidence | Classification |
|---|---|
| an unauthorised command was seen | attack (confidence 0.8 when impact, overload or an unexplained trip agrees, otherwise 0.6) |
| an unexplained line trip and no unauthorised message | fault (0.6) |
| anything else | unknown (0.3) |

Confidence values are heuristic labels for the rule table, not calibrated probabilities. Evidence text is built only from real values; an open incident keeps every unauthorised event it has seen and refreshes the impact as it evolves.

## Containment and recovery
`POST /city/incident/{id}/approve-response`, staged:
1. **Block** the malicious source, stop the load-altering effect, restore the control centre's view.
2. Wait until demand is back on its schedule.
3. **Isolate** districts left dark by a cascade, so lines can be reclosed with no load on them.
4. **Reclose** (and repair, for faults) out-of-service lines.
5. **Re-energise** districts one at a time, hospital districts first, only if doing so would not overload a line; otherwise hold the district and retry.

Every step is an authorised SCADA command (so it appears in the command log and the twin follows it). Recovery is verified by `backend/city/recovery.py`: every district energised, every line in service (except lines opened by an authorised command), no line above 90 % loading, every hospital on grid power, frequency within 49.9-50.1 Hz, all held for 10 s. `unresolved` after 150 s.

## Scenario defaults and the domino record
Scenario defaults live in the layout file (`scenario_defaults`: `trip_districts`, `stale_districts`, `fault_line`, `maintenance_line`) and are chosen by the build script, which also verifies that normal operation, the evening peak, the maintenance and the fault cause no blackout, that the coordinated trip darkens exactly the three configured substations, and that the load-altering attack cascades and is restored.

`failures` in the state records, per incident, the order in which things failed: a line tripping by protection, a substation losing power, a hospital switching to backup or running out of it. It resets when a scenario starts or stops. The Network tab's expanded graph replays it step by step. Every step is something that actually failed in the simulation.
