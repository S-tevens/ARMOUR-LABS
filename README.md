# ARMOUR LABS

**AI-powered digital twin for power-grid cyberattack detection, explanation and recovery.**

> Detect the attack. Understand the impact. Contain the threat. Verify recovery.

ARMOUR LABS protects a **campus microgrid substation**: a utility feed, solar array, battery storage, a hospital feeder and a campus feeder, all switched by protection relays (IEDs) that a SCADA system commands. It watches the network messages, breaker commands, meter readings and the physical power flows together. A digital twin estimates how the substation *should* behave given the commands that were actually authorised. ARMOUR LABS compares that expectation with what is observed, correlates the evidence across layers, and helps an operator understand, contain and recover from an incident.

Unlike an intrusion-detection dashboard that only lists alerts, ARMOUR LABS connects a cyber event to its physical consequence: "someone opened the hospital's breaker" becomes "the hospital feeder is de-energised, the battery is absorbing the lost load, and the command did not come from SCADA".

**It scales from one substation to a whole city grid.** The **City** tab is a real map of Bengaluru built from OpenStreetMap: the real 220 kV and 400 kV substations (Hoodi, Yelahanka, Peenya, NIMHANS, HSR Layout and 30 more), the mapped line routes between them, and the hospitals and Namma Metro stations they would supply. Click a substation and an isometric view of its local grid opens; click again to drop into its detailed microgrid. The **Network** tab shows the whole grid as an interconnected graph with an expand view that replays, step by step, how a failure spreads (the domino effect). **This is not utility data**: where OpenStreetMap has no mapped line the connection is inferred and drawn dashed, and all loads, ratings and attacks are simulated. See [Data sources and licence](#data-sources-and-licence).

**Everything runs in simulation.** The substation, the network and every attack scenario exist only inside an isolated software simulation. Nothing connects to real relays, grids or external systems.

## Why a microgrid substation

- **High stakes people understand:** blackouts, and a hospital on the feeder. Real grid attacks (Ukraine 2015 and 2016) used exactly these techniques: unauthorised breaker commands and spoofed data.
- **Clean twin signals:** frequency, voltage and power balance follow physical rules, so "expected vs observed" is meaningful.
- **A look-alike problem worth solving:** a planned, authorised breaker opening and an attacker's opening have the same physical effect. Only the authorisation, checked against the command log, tells them apart.

## Project status

This is the base project: a working end-to-end system you can run today.

| Area | State |
|---|---|
| Microgrid simulator, 11 scenarios, staged containment, recovery verification, labelled dataset generator | Working |
| Model-based, independent digital twin (authorised command log as its only command input) | Working (v0: hand-set parameters, to be fitted and tuned) |
| FastAPI backend with a WebSocket stream and an append-only SQLite event log | Working |
| Live dashboard (isometric substation, relays, twin chart, detector scores, network graph, incidents) | Working |
| **City layer:** real Bengaluru substations, mapped line routes, hospitals and metro from OpenStreetMap on a real map; linear power flow, line overloads and cascades, hospital backup timers, impact counters, 6 city scenarios, priority restoration, city twin, rule-based classification and campaign grouping, recovery verification | Working |
| **Grid graph and domino replay** (Network tab, expandable) | Working |
| **3D city map** (City tab default, 2D map kept as a toggle): 3D buildings, streets and water from OpenFreeMap/OpenStreetMap tiles under the live grid, with hospitals, metro and other facilities. Building heights are source values, not surveys. Needs internet; falls back to the 2D map | Working |
| Detectors: fixed limits, unauthorised-message rule, twin residuals, physics checks (fitted tolerances) and a trained anomaly model (autoencoder chosen on validation runs) | Working |
| Incident classification (attack, fault, unknown) | City: rule-based v0 (executable rule table). Substation: placeholder, always "unknown" |
| **Metrics tab** and `/metrics`: 9 detectors compared on 39 held-out simulated runs, per-scenario matrix, fresh-seed check, limitations | Working (simulator data only) |

Placeholders are marked `PLACEHOLDER` or `TODO` in the code. The live detector scores come from the running detectors. Measured results are on the Metrics tab and are labelled as coming from the custom simulator, not from real grid data. See [docs/evaluation.md](docs/evaluation.md).

---

## Run it on your computer

### 1. What you need

| Tool | Version | Check it with |
|---|---|---|
| Git | any recent | `git --version` |
| Python | 3.11 or newer | `python --version` (on Windows you can also try `py --version`) |
| Node.js | 20 or newer (includes npm) | `node --version` |

You also need free ports **8000** (backend) and **5173** (frontend).

### 2. Get the code

```bash
git clone https://github.com/S-tevens/ARMOUR-LABS.git
cd ARMOUR-LABS
```

### 3. Start the backend (Terminal 1)

**Windows (PowerShell):**

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --port 8000
```

If PowerShell refuses to activate with an execution-policy error, either run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or skip activation and run the tools through the virtual environment directly:

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn main:app --port 8000
```

**Windows (Command Prompt):** use `.venv\Scripts\activate.bat` instead of the `.ps1` line.

**macOS / Linux:**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --port 8000
```

You should see `Uvicorn running on http://127.0.0.1:8000`. Check it at http://localhost:8000/health, which should return `{"status":"ok", ...}`. Leave this terminal running.

### 4. Start the frontend (Terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser. The status pill at the top right should read **Substation normal**, and power should be flowing through the animated substation.

### 5. Try the demo

**Start with the City tab.** You see a real map of Bengaluru with the grid on top (green dots are substations, solid lines are mapped power lines, dashed lines are inferred ties). In the **City simulator** card, run **Coordinated substation trip**. Within seconds the status turns red: three central substations go dark with a red marker, the headline strip shows how many people are without power and how many hospitals are on backup, and "What's happening" lists the likely cause and the most urgent consequences in plain sentences. **Click a dark substation**: an isometric view of its local grid opens on the map, and the side card lists what it supplies. Click **Approve containment**: the source is blocked and substations are restored hospitals first, with a live checklist; the grid is marked **Recovered** only after every check holds for 10 seconds. Then try **Load-altering attack**: demand surges, one overloaded line trips, and a chain of substations in the west of the city goes dark (a cascade). Open the **Network** tab, press **Expand**, and use **Replay** or the slider to watch the failure spread one step at a time. The look-alikes (**Planned line maintenance**, **Hot-evening demand peak**) raise no incident, and **Line fault** is classified as equipment, not an attack. Backup time and energy run accelerated (1 second is 1 minute).

**Then drill down.** Click a district and choose **Open substation view** for its detailed microgrid:

1. On the **Substation** tab, find the **Simulator** card on the substation view.
2. Click **Unauthorised breaker trip**. Within a few seconds the status turns to **Incident in progress**: the hospital building greys out with a red outline, its breaker CB-CRIT opens, IED-03 shows **Compromised**, and the battery starts absorbing the lost load. The callout quotes the unauthorised command and its source.
3. Click **Approve containment**. The response runs in stages (block the source, hold the battery, reclose the hospital breaker first, return to automatic control).
4. The incident is marked **Recovered** only after frequency, voltage, import, battery charge and hospital load have stayed within limits with all breakers closed for 10 seconds.
5. Open the **Network** tab to see the red attacker path to IED-03 and the message table, and the **Incidents** tab for the evidence list and progress.

Then try the look-alikes, which show why the twin matters:
- **Planned switching (legitimate)** opens the campus breaker with an *authorised* command. The physical effect resembles a trip, but no incident is raised.
- **Passing clouds (natural)** drops solar output, which the weather station explains. No incident.
- **Stuck breaker (fault)** is a legitimate open command that did not take effect: an incident is raised with no network evidence, pointing to equipment rather than an attacker.
- **False frequency report** shows a spoofed 49.5 Hz reading making the controller drain the battery while the real grid is fine.
- **Replay attack** keeps the meters looking normal while the hospital feeder is opened. The network evidence expires after 10 seconds, but the twin keeps flagging it through the breaker state and the battery's response.

**Stop and reset** returns the substation to normal at any time.

### 6. Stop everything

Press `Ctrl+C` in each terminal.

---

## Run the tests

```bash
cd backend
python -m pytest            # backend: 74 tests (about a minute)
cd ../frontend
npm run build               # frontend: type-check and production build
```

Run the backend tests with the virtual environment active (or use `.venv/Scripts/python -m pytest` on Windows and `.venv/bin/python -m pytest` on macOS/Linux). The same checks run automatically on every pull request.

## Generate labelled datasets

```bash
cd backend
python -m sim.dataset --out ../data/generated
```

This writes 26 simulator runs (normal and every scenario) as CSV plus network-event files and a `manifest.json`. The files are not committed because they are reproducible. See [data/README.md](data/README.md) for the labels and how to split them without leaking time windows.

## Configuration

Set these environment variables before starting the backend (all optional):

| Variable | Default | Meaning |
|---|---|---|
| `ARMOUR_SEED` | `42` | Random seed. The same seed gives the same simulation. |
| `ARMOUR_TICK_SECONDS` | `1.0` | Real seconds per simulated second. Use `0.2` for a faster demo. |
| `ARMOUR_DB` | in memory | Path of an SQLite file, to keep the event log between restarts. |
| `ARMOUR_AUTOSTART` | `1` | Set `0` to stop the simulation starting by itself (used by tests). |
| `ARMOUR_ML` | `1` | Set `0` to skip training the ML detectors at start-up (about 10 s). Live ML and physics scores then stay 0. |
| `ARMOUR_CITY` | `osm` | Grid layout: `osm` (real Bengaluru topology) or `synthetic` (small fictional test network). |

For the frontend, `VITE_API_URL` (default `http://localhost:8000`) points the dashboard at a backend on another address.

Example (PowerShell): `$env:ARMOUR_TICK_SECONDS = "0.5"; uvicorn main:app --port 8000`
Example (macOS/Linux): `ARMOUR_TICK_SECONDS=0.5 uvicorn main:app --port 8000`

## Troubleshooting

| Problem | Fix |
|---|---|
| Dashboard says "Backend offline" or "Can't reach the backend" | Start the backend (step 3) and check http://localhost:8000/health. |
| `python` is not found on Windows | Install Python from python.org and tick "Add python.exe to PATH", or use `py` instead of `python`. |
| `Activate.ps1 cannot be loaded` | Use the execution-policy command or the direct `.venv\Scripts\python` commands in step 3. |
| `Address already in use` on port 8000 or 5173 | Another program is using it. Stop it, or pick another port: `uvicorn main:app --port 8001` and `VITE_API_URL=http://localhost:8001` for the frontend. |
| `ModuleNotFoundError` when starting the backend | Run `uvicorn` from inside the `backend/` folder with the virtual environment active. |
| Frontend shows old data after a code change | Hard refresh the page (`Ctrl+Shift+R`). |
| The map shows no streets, only the grid | The basemap tiles load from OpenStreetMap's servers, so they need internet. The grid overlay and everything else work offline. |
| You started a scenario and the substation looks stuck | Click **Stop and reset**. |

---

## How it works

```text
Substation simulator ──► meter readings + network/command events
                              │
             ┌────────────────┴────────────────┐
             ▼                                 ▼
   Detectors (limits, rules, physics  Digital twin: expected state from
   checks, trained ML model)         the AUTHORISED command log only
             │                                 │
             └──────────► evidence fusion ◄────┘
                                │
                                ▼
          incident classification (attack / fault / unknown)
                                │
                                ▼
     explanation → simulated containment → recovery verification
                                │
                                ▼
                   live dashboard + incident replay
```

### The substation model

Loads follow slow profiles (hospital about 400 kW, campus about 300 kW). Solar (500 kW rated) follows irradiance. A battery (250 kW, 200 kWh) is steered by an energy management system that holds utility import near a target and applies a frequency droop term that reads the **reported** frequency, so a spoofed measurement has a real physical effect. Grid-connected, the utility holds 50 Hz; islanded, any imbalance moves frequency and voltage.

### Scenarios

| Scenario | Kind | What it does |
|---|---|---|
| Unauthorised breaker trip | attack | A non-SCADA source opens the hospital breaker |
| False frequency report | attack | A spoofed 49.5 Hz makes the controller over-discharge the battery |
| Replay attack | attack | Recorded readings are replayed while the hospital breaker is opened; old messages are re-sent |
| Denial of service | attack | A message flood hits IED-03, heartbeats drop, measurements go stale |
| Small false data | attack | A small voltage bias with no network trace (subtle) |
| Slow-ramp false data | attack | A creeping voltage bias with no network trace (looks like drift) |
| Voltage sensor drift | fault | The voltage sensor drifts, no malicious traffic |
| Stuck breaker | fault | An authorised open command does not take effect |
| PV inverter trip | fault | Solar output drops to zero, no network evidence |
| Planned switching | benign | An authorised SCADA command opens the campus breaker |
| Passing clouds | benign | Irradiance drops; the weather station explains it |

Full contracts, endpoints and message shapes: [docs/contracts.md](docs/contracts.md).

### Technology

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, SVG, Leaflet (2D map), MapLibre GL and three.js (3D map) |
| Backend | Python, FastAPI, WebSockets, NumPy |
| Storage | SQLite (append-only event log, also the source for replay) |
| ML | scikit-learn (PCA autoencoder, Isolation Forest, one-class SVM) |

## Repository layout

```text
backend/
  core/contracts.py   shared data models (source of truth)
  sim/                substation model, scenarios, engine, containment, recovery, dataset generator
  twin/               model-based digital twin
  detect/             detectors: limits, features, physics checks, ML models, training bundle, alert rule
  evaluation/         evaluation protocol, metrics, results.json, background service
  incident/           incident manager (placeholder classification)
  db/                 append-only SQLite event log
  api/                FastAPI app, WebSocket stream, runtime
  city/               city model: layout, power flow, engine, scenarios, containment, recovery, twin, detection
  city/data/          bengaluru_osm.json (real topology, simulated electrical model) and synthetic.json (test fixture)
  city/tools/         fetch_osm.py and build_osm_city.py: rebuild the grid data from OpenStreetMap
  tests/              backend tests
frontend/             React + TypeScript dashboard (src/city/ is the city view)
data/                 dataset notes (generated files are not committed)
docs/contracts.md     message and API contracts
```

## Documents

- [docs/city-3d.md](docs/city-3d.md): the 3D city map, its data sources and limits.
- [docs/evaluation.md](docs/evaluation.md): detectors, evaluation protocol and what the numbers do not show.
- [ARMOUR_LABS_CITY_LAYER_PLAN.md](ARMOUR_LABS_CITY_LAYER_PLAN.md): the city layer plan, with per-person tasks and the frontend clarity rules.
- [docs/city-contracts.md](docs/city-contracts.md): city messages and endpoints.
- [ARMOUR_LABS_PROJECT_DESCRIPTION.md](ARMOUR_LABS_PROJECT_DESCRIPTION.md): the full project description.
- [ARMOUR_LABS_MVP_BUILD_PLAN.md](ARMOUR_LABS_MVP_BUILD_PLAN.md): builds, acceptance checks and risks.
- [ARMOUR_LABS_TASK_DISTRIBUTION.md](ARMOUR_LABS_TASK_DISTRIBUTION.md): who builds what.
- [CONTRIBUTING.md](CONTRIBUTING.md): workflow, folder ownership and rules.

## Data sources and licence

**What is real, what is inferred, what is simulated.** The Bengaluru grid is a hybrid, and the interface says so:

| | What | Source |
|---|---|---|
| Real | 37 substation locations, names and voltage levels (220 kV and 400 kV, including the five 400 kV entry points); 54 further 66 kV substations shown as context; mapped 220/400 kV line routes; 30 larger hospitals; 87 Namma Metro stations; Kempegowda Airport (added by hand) | OpenStreetMap |
| Inferred | Most links between substations: OpenStreetMap maps only 8 of the 46 ties, so the rest are inferred from the voltage hierarchy and proximity (each substation gets at least two ties, separate pieces are joined). Shown dashed. The real topology is not public | This project |
| Simulated | Loads (from the number of mapped 66 kV substations each node would feed), populations, line ratings (calibrated so normal operation sits at 45-68 % loading), which hospital or metro station a substation supplies (by proximity), and every attack | This project |

Nothing here is BESCOM or KPTCL data, and the simulated outages are hypothetical.

**3D map.** The 3D view loads its style and vector tiles at run time from [OpenFreeMap](https://openfreemap.org) (OpenMapTiles data from OpenStreetMap), so it needs an internet connection; the attribution stays on the map. Building heights come from the tile source and can be estimates. See [docs/city-3d.md](docs/city-3d.md).

**Licence and attribution.** Map data (c) OpenStreetMap contributors, available under the [Open Database Licence (ODbL)](https://www.openstreetmap.org/copyright). `backend/city/data/bengaluru_osm.json` is a derived database: keep the attribution, and if you redistribute an adapted version, share it under the same licence. The basemap tiles come from the public OpenStreetMap tile servers, which are fine for a demo but not for heavy use; for production, host your own tiles or use a tile provider.

**Rebuild the data** (needs internet; the result is committed, so the app never needs this):

```bash
cd backend
python -m city.tools.fetch_osm        # downloads the raw OpenStreetMap data (be patient: the public servers are often busy)
python -m city.tools.build_osm_city   # builds city/data/bengaluru_osm.json and tunes the simulated ratings
```

## Evaluation approach

Accuracy alone is not reported. The Metrics tab shows precision, recall, F1, false alarms per hour, detection delay, per-scenario results and a confusion matrix, for a threshold baseline, the individual detectors, three ML families and the combined approach. Splits are by run with no shared seeds, the ML model is chosen on separate validation runs, a fresh-seed check is included, and every result is labelled as coming from the custom simulator. Details and caveats: [docs/evaluation.md](docs/evaluation.md).

## Guardrails

- An anomaly is evidence, not proof of an attack.
- Illustrative UI values are labelled and never presented as measured results.
- "Recovered" is shown only when the verification checks pass.
- The LLM assistant, if built, only explains structured detection results. It does not detect anything.

## Research inspiration

*Machine Learning-Based Detection of Anomalies, Intrusions, and Threats in Industrial Control Systems*, IEEE Access, 2025. Any results reported by the paper are not results achieved by this project.

## Team

Armour Labs, a three-person team.

## License

No license has been chosen yet.
