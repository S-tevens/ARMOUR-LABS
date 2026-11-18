# ARMOUR LABS: Task Distribution and Teammate Prompts

Repo: https://github.com/S-tevens/ARMOUR-LABS
Companion doc: [ARMOUR_LABS_MVP_BUILD_PLAN.md](ARMOUR_LABS_MVP_BUILD_PLAN.md)

## 1. Setup (repo owner does this once)

1. Add both teammates as collaborators: GitHub repo → Settings → Collaborators → Add people (they accept the email invite).
2. Protect `main`: Settings → Branches → require a pull request before merging.
3. Create the skeleton folders and `docs/contracts.md` (copy the contracts from section 3 below), then push.

Folder ownership (nobody edits another person's folder without asking):

| Folder | Owner |
|---|---|
| `frontend/` | P1 (you) |
| `backend/sim/`, `backend/twin/`, `data/` | P2 |
| `backend/detect/`, `backend/incident/`, `backend/api/`, `backend/db/` | P3 |
| `docs/contracts.md` | all three (changes need everyone's OK) |

## 2. Who does what

### P1 (you): frontend and integration lead
| Build | Tasks |
|---|---|
| 1 | React + TS app shell, dark industrial theme, WebSocket client, mock server that replays the contract JSON, animated SVG plant (pipes, tank levels, pump and valve states), live readouts, status bar |
| 2 | Scenario selector and launch button, network topology panel (green/amber/red, path highlight), alert feed, plant reacting to attacks |
| 3 | Threat monitor (four score gauges, severity, confidence), metrics page (confusion matrix, baseline vs ML vs combined, labelled by data source) |
| 4 | Digital-twin comparison table (expected/observed/residual), incident investigation panel (evidence tagged observed/correlated/inferred, uncertainty), propagation graph, timeline |
| 5 | Response plan panel with approve button and dry-run preview, recovery verification table, replay scrubber, UI polish, demo script, integration of all three parts |

### P2: simulation, attacks and digital twin
| Build | Tasks |
|---|---|
| 1 | Deterministic plant model (Tank 1 → Pump 1 → Filter → Valve 1 → Tank 2 → Pump 2), noise, seeded simulation clock, 1 Hz telemetry over WebSocket |
| 2 | Attack engine: `unauthorised_valve_close`, `false_data_injection`; network/command event records with `authorised` flag; scenario start/stop API; plant reacts physically |
| 3 | Labelled datasets (normal, attacks, subtle variants), benign `sensor_drift` fault, configurable noise/disturbance/drift |
| 4 | Independent digital twin (own fitted parameters, inputs are the authorised command log only), residuals, normalised residuals, tolerance bands, observed-state leak test |
| 5 | Simulated containment (reject command, safe state, restore), twin dry-run of the response, recovery verification with tolerances and dwell time |

### P3: detection, incidents and API
| Build | Tasks |
|---|---|
| 1 | FastAPI skeleton, SQLite schema, append-only event log, mock detector returning "normal" |
| 2 | Threshold baseline detector on telemetry, first alert stream |
| 3 | Feature extraction, Isolation Forest trained on normal data, time-based train/test split, physics invariants (mass balance, pump on ⇒ flow, valve closed ⇒ no flow), evaluation script, `GET /metrics` |
| 4 | Evidence fusion with the §10 rule table, incident classification (attack/fault/unknown), time alignment of evidence, template-based explanations from real fields only, propagation graph data |
| 5 | Response recommendation, approve-response endpoint, incident replay endpoint, final evaluation numbers |

## 3. Shared contracts (copy into `docs/contracts.md`)

- **Telemetry tick** (WebSocket `/ws/telemetry`, 1 Hz, sent inside an envelope `{type, data}`; see `docs/contracts.md`, which is the source of truth): `{t, tick, tank1_level, tank2_level, pressure, flow, temperature, pump1, pump2, valve1, plc_status:{plc01,plc02,plc03}}`
- **Network/command event:** `{seq, t, src, dst, function_code, register, value, authorised:bool}`
- **Twin state:** `{t, expected:{...}, residual:{...}, norm_residual:{...}}`
- **Incident:** `{id, t_start, severity, confidence, affected_devices[], classification (attack|fault|unknown), scores:{network, controller, process, twin}, evidence[{type, text, tag: observed|correlated|inferred}], status}`
- **API:** `POST /scenario/start {name}`, `POST /scenario/stop`, `POST /incident/{id}/approve-response`, `GET /incidents`, `GET /incidents/{id}/replay`, `GET /metrics`
- **Scenarios:** `unauthorised_valve_close`, `false_data_injection`, `sensor_drift`
- **PLC mapping:** PLC-01 drives Pump 1 and Pump 2; PLC-02 drives Valve 1; PLC-03 reads all sensors.

## 4. Git workflow for everyone

```bash
git clone https://github.com/S-tevens/ARMOUR-LABS.git
cd ARMOUR-LABS
git checkout -b p2/build1-simulator      # branch name: <person>/<build>-<topic>
# ...work, then:
git add <your folder>
git commit -m "Build 1: plant simulator"
git push -u origin p2/build1-simulator   # then open a pull request on GitHub
```

Rules: never push straight to `main`; pull `main` before starting each build (`git pull origin main`); keep PRs small; the repo owner merges once the build's demo checkpoint passes. Do not commit secrets, `.env` files, virtual environments or `node_modules`.

## 5. Prompts to give each person (paste into Claude Code or any coding assistant)

### Common preamble (include in all three prompts)

```text
You are helping build ARMOUR LABS, an AI-powered digital twin for industrial
cyberattack detection, explanation and recovery, shown on a SIMULATED
water-treatment plant. Everything runs in software; never connect to real
equipment or networks.

Repo: https://github.com/S-tevens/ARMOUR-LABS (clone it first, work on a
feature branch named <role>/<build>-<topic>, never push to main, open a PR).
Read README.md, ARMOUR_LABS_MVP_BUILD_PLAN.md and docs/contracts.md first and
follow the JSON contracts exactly. If a contract must change, stop and tell me
instead of changing it. Only edit the folders I own. Stack: Python + FastAPI +
SQLite on the backend, React + TypeScript on the frontend. Use a fixed random
seed so runs are repeatable. Rules: an anomaly is evidence, not proof of an
attack; label illustrative values as such; never hard-code metrics; "Recovered"
is shown only when verification checks pass. Work one build at a time, finish
the build's acceptance check, and give me a short summary plus the commands to
run it before moving on. Add a short README in your folder explaining how to
run and test it.
```

### Prompt for P1 (you): frontend and integration

```text
[Common preamble]

Role: P1, frontend and integration. You own frontend/ only.
Start with Build 1: create a React + TypeScript (Vite) app with a dark
industrial theme (charcoal/navy background, green = healthy, amber =
suspicious, red = incident, blue = water flow). Build a mock server (or a
mock mode) that replays telemetry and events in the contract shapes, so the UI
works before the real backend exists, and a WebSocket client that can switch
to the real /ws/telemetry. Build an animated SVG plant: Tank 1 -> Pump 1 ->
Filter -> Valve 1 -> Tank 2 -> Pump 2 with flowing pipes, tank fill levels,
pump/valve states, sensor readouts and a "SYSTEM STATUS" bar. All visuals must
be driven by incoming data, not canned animation.
Then, in order: Build 2 (scenario selector, launch button, network topology
with green/amber/red nodes and highlighted path, alert feed), Build 3 (threat
monitor gauges, metrics page with confusion matrix and baseline vs ML vs
combined, labelled by data source), Build 4 (expected/observed/residual table,
incident panel with evidence tagged observed/correlated/inferred, propagation
graph, timeline), Build 5 (response plan with approve button and dry-run
preview, recovery verification table, replay scrubber, polish). Every build
must end in a frontend I can present at an evaluation.
```

### Prompt for P2: simulation, attacks and digital twin

```text
[Common preamble]

Role: P2, simulation, attack engine and digital twin. You own backend/sim/,
backend/twin/ and data/ only.
Build 1: a deterministic plant model (Tank 1 -> Pump 1 -> Filter -> Valve 1 ->
Tank 2 -> Pump 2) with simple understandable process rules, small realistic
sensor noise and a seeded simulation clock, publishing 1 Hz telemetry in the
contract shape over WebSocket /ws/telemetry. Normal state: valve open,
pressure ~2.1 bar, flow ~110 L/min.
Build 2: an attack engine with scenarios unauthorised_valve_close (closing the
valve raises pressure and collapses flow; Tank 1 risks overflow) and
false_data_injection (a sensor reports a manipulated value), plus network/
command event records with an `authorised` flag, and POST /scenario/start and
/scenario/stop. The plant must physically react.
Build 3: labelled datasets (normal, attacks, subtle small/slow variants), a
benign sensor_drift fault, configurable noise/disturbance/drift.
Build 4: an INDEPENDENT digital twin: its own equations and fitted parameters
(not the simulator's constants), whose only command input is the authorised
command log. Compute expected state, residuals, normalised residuals and
tolerance bands from held-out normal data. Include a test proving the twin's
output does not change when the observed valve state is altered.
Build 5: simulated containment (reject command, safe state, restore), a twin
dry-run predicting the response outcome, and recovery verification with
tolerances plus an N-second dwell time returning Recovered / Recovering /
Unresolved.
```

### Prompt for P3: detection, incidents and API

```text
[Common preamble]

Role: P3, detection, incident intelligence and API. You own backend/detect/,
backend/incident/, backend/api/ and backend/db/ only.
Build 1: a FastAPI app skeleton, SQLite schema with an append-only event log
(telemetry, events, alerts, incidents), and a mock detector that returns
"normal".
Build 2: a simple threshold baseline detector on telemetry that produces a
real alert stream from actual telemetry.
Build 3: feature extraction (rolling stats, rates of change, command
frequency), an Isolation Forest trained on normal data, a time-based
train/test split (no random splitting), physics-invariant checks (mass
balance, pump on => flow > 0, valve closed => downstream flow ~ 0), and an
evaluation script reporting precision, recall, F1, false-positive rate,
confusion matrix, detection latency and per-attack results for baseline vs ML
vs combined, exposed at GET /metrics. Normalise each detector score to [0,1]
by its percentile on held-out normal data.
Build 4: evidence fusion as an executable rule table (unauthorised command +
process change + twin residual => attack; single-sensor deviation with stable
neighbours => sensor fault/spoof; process deviation with no network/command
evidence => physical fault or model mismatch), time alignment of evidence,
classification attack/fault/unknown with confidence and an uncertainty reason,
template-based explanations that use only real alert fields (add a test that
fails if any number in the text is not in the incident data), and propagation
graph data with observed/correlated/inferred edges.
Build 5: response recommendation, POST /incident/{id}/approve-response, GET
/incidents/{id}/replay built from recorded events and timestamps, and the
final evaluation numbers.
```

## 6. Integration checkpoints
Each build ends with a 30-minute joint run on one machine: P2 and P3 start their backends, P1 points the frontend at the real WebSocket, and the build's acceptance check from the build plan is ticked off before merging to `main`.
