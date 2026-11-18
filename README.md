# ARMOUR LABS

**AI-powered digital twin for power-grid cyberattack detection, explanation and recovery.**

> Detect the attack. Understand the impact. Contain the threat. Verify recovery.

ARMOUR LABS protects a **campus microgrid substation**: a utility feed, solar array, battery storage, a hospital feeder and a campus feeder, all switched by protection relays (IEDs) that a SCADA system commands. It watches the network messages, breaker commands, meter readings and the physical power flows together. A digital twin estimates how the substation *should* behave given the commands that were actually authorised. ARMOUR LABS compares that expectation with what is observed, correlates the evidence across layers, and helps an operator understand, contain and recover from an incident.

Unlike an intrusion-detection dashboard that only lists alerts, ARMOUR LABS connects a cyber event to its physical consequence: "someone opened the hospital's breaker" becomes "the hospital feeder is de-energised, the battery is absorbing the lost load, and the command did not come from SCADA".

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
| Threshold baseline detector | Working (baseline only) |
| Incident classification (attack, fault, unknown) | Placeholder: always "unknown" |
| ML detector (Isolation Forest), physics checks, evidence fusion, evaluation and `/metrics` | Not built yet |

Placeholders are marked `PLACEHOLDER` or `TODO` in the code. The detector scores shown in the dashboard come from the baseline and are **not measured results**.

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

1. On the **Dashboard** tab, find the **Simulator** card on the substation view.
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
python -m pytest            # backend: 30 tests
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
| You started a scenario and the substation looks stuck | Click **Stop and reset**. |

---

## How it works

```text
Substation simulator ──► meter readings + network/command events
                              │
             ┌────────────────┴────────────────┐
             ▼                                 ▼
   Detectors (baseline today;        Digital twin: expected state from
   ML + physics checks planned)      the AUTHORISED command log only
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
| Frontend | React 18, TypeScript, Vite, SVG |
| Backend | Python, FastAPI, WebSockets, NumPy |
| Storage | SQLite (append-only event log, also the source for replay) |
| Planned ML | scikit-learn (PyTorch only if justified) |

## Repository layout

```text
backend/
  core/contracts.py   shared data models (source of truth)
  sim/                substation model, scenarios, engine, containment, recovery, dataset generator
  twin/               model-based digital twin
  detect/             detectors (threshold baseline)
  incident/           incident manager (placeholder classification)
  db/                 append-only SQLite event log
  api/                FastAPI app, WebSocket stream, runtime
  tests/              backend tests
frontend/             React + TypeScript dashboard
data/                 dataset notes (generated files are not committed)
docs/contracts.md     message and API contracts
```

## Documents

- [ARMOUR_LABS_PROJECT_DESCRIPTION.md](ARMOUR_LABS_PROJECT_DESCRIPTION.md): the full project description.
- [ARMOUR_LABS_MVP_BUILD_PLAN.md](ARMOUR_LABS_MVP_BUILD_PLAN.md): builds, acceptance checks and risks.
- [ARMOUR_LABS_TASK_DISTRIBUTION.md](ARMOUR_LABS_TASK_DISTRIBUTION.md): who builds what.
- [CONTRIBUTING.md](CONTRIBUTING.md): workflow, folder ownership and rules.

## Evaluation approach

Accuracy alone is not reported. Planned metrics are precision, recall, F1, false-positive rate, confusion matrix, detection latency, per-attack results and recovery verification time. A threshold baseline, a single ML model and the combined approach are compared using time-based train/test splits, and each result is labelled by source (public dataset or custom simulator).

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
