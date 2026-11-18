# ARMOUR LABS: Task Distribution and Teammate Prompts

Repo: https://github.com/S-tevens/ARMOUR-LABS
Companion docs: [ARMOUR_LABS_MVP_BUILD_PLAN.md](ARMOUR_LABS_MVP_BUILD_PLAN.md), [docs/contracts.md](docs/contracts.md), [CONTRIBUTING.md](CONTRIBUTING.md)

Domain: a **campus microgrid substation** (utility, solar, battery, hospital feeder, campus feeder, three IEDs, SCADA). The base project already runs end to end; these tasks build on it.

## 1. Setup (repo owner does this once)

1. Add both teammates as collaborators: GitHub repo, Settings, Collaborators.
2. Protect `main`: Settings, Branches, require a pull request before merging.
3. Put the teammates' GitHub usernames in `.github/CODEOWNERS`.

Folder ownership (nobody edits another person's folder without asking):

| Folder | Owner |
|---|---|
| `frontend/` | P1 |
| `backend/sim/`, `backend/twin/`, `data/` | P2 |
| `backend/detect/`, `backend/incident/`, `backend/api/`, `backend/db/` | P3 |
| `backend/core/contracts.py`, `frontend/src/types.ts`, `docs/contracts.md` | all three (changes need everyone's OK) |

## 2. What already works (do not rebuild)

- Substation simulator with 11 scenarios (attacks, faults, benign look-alikes), seeded and deterministic.
- Model-based digital twin v0 using the authorised command log only.
- Staged containment and recovery verification with a dwell time.
- Labelled dataset generator (`python -m sim.dataset`).
- FastAPI backend, WebSocket stream, SQLite event log, incident manager (placeholder classification), threshold baseline detector.
- Dashboard: isometric substation, relays, sensor strip, twin chart, detector scores, network graph, incidents.
- 30 backend tests and CI.

## 3. Who does what (remaining work)

### P1: frontend and integration lead
| Build | Tasks |
|---|---|
| 3 | Metrics page (confusion matrix, baseline vs ML vs combined, labelled by data source); live score display polish |
| 4 | Incident panel: evidence tagged observed/correlated/inferred, likely cause with uncertainty, propagation graph, timeline |
| 5 | Response panel with dry-run preview, recovery verification table, replay scrubber (timeline), UI polish, demo script, recorded fallback video, final integration |

### P2: simulation and twin
| Build | Tasks |
|---|---|
| 3 | Extra seeds and variants for the datasets; keep the simulator deterministic; check scenario timing against detector needs |
| 4 | Fit the twin's parameters from normal data (loads, PV efficiency, battery lag); set tolerance bands from held-out normal data; keep the "observed state does not change expectations" test passing |
| 5 | Twin dry-run of a proposed containment: predicted outcome and any unsafe side effect (for example reclosing onto a fault) |

### P3: detection, incidents and API
| Build | Tasks |
|---|---|
| 3 | Feature extraction; Isolation Forest with a run-based train/test split; physics invariants (power balance, breaker open means zero feeder load, plausible frequency); percentile score normalisation; evaluation script and `GET /metrics` |
| 4 | Evidence fusion rule table (attack, fault, unknown with confidence); time alignment of evidence; template explanations from real fields only; propagation-graph data |
| 5 | Response recommendation; replay endpoint options; final evaluation numbers |

## 4. Contracts

The single source of truth is `backend/core/contracts.py`, documented in `docs/contracts.md`. Read it before writing code. Key points:

- Telemetry: `frequency, bus_voltage, grid_import_kw, pv_kw, bess_kw, bess_soc, load_critical_kw, load_noncritical_kw, irradiance`, breakers `cb_main, cb_pv, cb_bess, cb_crit, cb_nc` (true = closed), and `ied_status` for IED-01..03.
- The WebSocket `/ws/telemetry` sends envelopes `{type, data}` with types `telemetry, event, twin, scores, incident`.
- REST: `/scenarios`, `/scenario/start|stop`, `/incidents`, `/incident/{id}/approve-response`, `/incidents/{id}/replay`, `/recovery`, `/metrics`.
- Scenarios: `unauthorised_breaker_trip`, `false_data_injection`, `replay_attack`, `dos_flood`, `fdi_small`, `fdi_slow_ramp`, `sensor_drift`, `stuck_breaker`, `pv_inverter_trip`, `planned_switching`, `cloud_cover`.
- IED mapping: IED-01 utility interface (CB-MAIN, grid meter); IED-02 solar and battery (CB-PV, CB-BESS); IED-03 load feeders (CB-CRIT hospital, CB-NC campus).

## 5. Git workflow for everyone

```bash
git clone https://github.com/S-tevens/ARMOUR-LABS.git
cd ARMOUR-LABS
git checkout -b p2/build3-datasets        # branch name: <person>/<build>-<topic>
# ...work, run the checks in CONTRIBUTING.md, then:
git add <your folder>
git commit -m "Build 3: extra dataset seeds"
git push -u origin p2/build3-datasets     # then open a pull request on GitHub
```

Rules: never push straight to `main`; pull `main` before starting each build (`git pull origin main`); keep PRs small; the repo owner merges once the build's demo checkpoint passes. Do not commit secrets, `.env` files, virtual environments, `node_modules` or generated datasets.

## 6. Prompts to give each person (paste into Claude Code or any coding assistant)

### Common preamble (include in all three prompts)

```text
You are helping build ARMOUR LABS, an AI-powered digital twin for power-grid
cyberattack detection, explanation and recovery, demonstrated on a SIMULATED campus
microgrid substation (utility, solar, battery, a hospital feeder and a campus feeder,
three IEDs, SCADA). Everything runs in software; never connect to real equipment,
relays or networks.

Repo: https://github.com/S-tevens/ARMOUR-LABS. Clone it, read README.md,
ARMOUR_LABS_MVP_BUILD_PLAN.md and docs/contracts.md, and run the project first
(the README explains how). A working base already exists: do not rebuild it. Work on
a feature branch named <role>/<build>-<topic>, never push to main, and open a pull
request. Follow the JSON contracts exactly; if a contract must change, stop and tell
me instead of changing it. Only edit the folders I own. Stack: Python + FastAPI +
SQLite on the backend, React + TypeScript on the frontend. Use fixed random seeds.
Rules: an anomaly is evidence, not proof of an attack; label illustrative values;
never hard-code metrics; "Recovered" is shown only when verification checks pass; a
planned, authorised breaker operation must not be flagged as an attack. Run the tests
(backend: python -m pytest, frontend: npm run build) before each pull request. Work one
build at a time, finish its acceptance check, and give me a short summary plus the
commands to run it before moving on.
```

### Prompt for P1: frontend and integration

```text
[Common preamble]

Role: P1, frontend and integration. You own frontend/ only. The dashboard already
exists (isometric substation view, relays panel, sensor strip, twin chart, detector
scores, network graph, incidents) in a light frosted-glass style; keep that visual
language and the existing components' patterns.
Build 3: a Metrics page that reads GET /metrics (confusion matrix, precision/recall/F1,
false-positive rate, detection latency, baseline vs ML vs combined) and labels every
result by data source (simulator or public dataset). Until the endpoint exists, show
an honest empty state ("no measured results yet"), never invented numbers.
Build 4: an incident panel showing evidence tagged observed/correlated/inferred, the
likely cause with its uncertainty, a propagation graph (incident -> command -> breaker
-> feeder -> impact) and a timeline.
Build 5: a response panel with the dry-run preview, the recovery verification table
from GET /recovery, a replay scrubber driven by GET /incidents/{id}/replay, UI polish,
a rehearsed demo script (see section 23 of the project description) and a recorded
fallback video. Every build must end in a frontend I can present at an evaluation.
```

### Prompt for P2: simulation and digital twin

```text
[Common preamble]

Role: P2, simulation and digital twin. You own backend/sim/, backend/twin/ and data/ only.
The substation model, 11 scenarios, staged containment, recovery verification, dataset
generator and a model-based twin v0 already exist. Read sim/plant.py, sim/scenarios.py,
twin/twin.py and the tests first.
Build 3: extend the dataset generator with extra seeds and variants if the detector
work needs them; keep the simulator deterministic.
Build 4: FIT the twin's parameters from normal simulator data (load profiles, PV
efficiency, battery lag) instead of hand-set values, and set tolerance bands and
residual scales from held-out normal data. Keep these properties, with tests: the
twin's expectations come only from the authorised command log (they do not change when
observed breaker states change), it stays quiet in normal operation across seeds,
planned switching and passing clouds raise no residual alarm, and the stuck breaker
and unauthorised trip do.
Build 5: a twin dry-run of a proposed containment that predicts the outcome (time to
return within the recovery limits) and flags unsafe side effects, such as reclosing a
breaker onto a fault.
```

### Prompt for P3: detection, incidents and API

```text
[Common preamble]

Role: P3, detection, incident intelligence and API. You own backend/detect/,
backend/incident/, backend/api/ and backend/db/ only. A threshold baseline detector, a
placeholder incident manager (always "unknown"), the SQLite event log and the API
already exist. Read detect/threshold.py, incident/manager.py and the tests first.
Build 3: feature extraction (rolling statistics, rates of change, command frequency,
sequence-number checks), an Isolation Forest trained on normal simulator data with a
run-based train/test split (never random rows), physics-invariant checks (power balance
import = load - PV - battery, breaker open implies zero feeder load, plausible
frequency on a stiff grid), percentile score normalisation on held-out normal data, and
an evaluation script reporting precision, recall, F1, false-positive rate, confusion
matrix, detection latency and per-scenario results for baseline vs ML vs combined,
exposed at GET /metrics. Benign scenarios must not produce false alarms.
Build 4: evidence fusion as an executable rule table (unauthorised command + breaker
mismatch + twin residual => attack; authorised command whose effect did not happen =>
equipment fault; residual with no network or command evidence => physical fault or
model mismatch; authorised and explained => no incident), time alignment of evidence,
classification attack/fault/unknown with confidence and an uncertainty reason,
template explanations that use only real incident fields (add a test that fails if any
number in the text is not in the incident data), and propagation-graph data with
observed/correlated/inferred edges.
Build 5: response recommendation, replay endpoint options, and the final evaluation
numbers.
```

## 7. Integration checkpoints
Each build ends with a 30-minute joint run on one machine: P2 and P3 start their backends, P1 points the frontend at the real WebSocket, and the build's acceptance check from the build plan is ticked off before merging to `main`.
