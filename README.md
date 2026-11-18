# ARMOUR LABS

**AI-powered digital twin for industrial cyberattack detection, explanation and recovery.**

> Detect the attack. Understand the impact. Contain the threat. Verify recovery.

ARMOUR LABS is a cyber-physical security platform for Industrial Control Systems (ICS). It runs a software simulation of a small water-treatment plant and watches the network events, PLC commands, sensor telemetry and physical process together. A digital twin estimates how the plant *should* behave. ARMOUR LABS compares that expectation with what is observed, correlates the evidence across layers, and helps an operator understand, contain and recover from an incident.

Unlike an intrusion-detection dashboard that only lists alerts, ARMOUR LABS connects a cyber event to its physical consequences.

**Everything runs in simulation.** The plant, the network and every attack scenario exist only inside an isolated software simulation. Nothing connects to real PLCs, industrial networks or external systems.

## Project status

This is the base project (v0.1): a working end-to-end skeleton that you can run today.

| Area | State |
|---|---|
| Plant simulator, 10 scenarios, staged containment, recovery verification, labelled dataset generator | Working |
| FastAPI backend with a WebSocket stream and an append-only SQLite event log | Working |
| Live dashboard (isometric plant, controllers, twin chart, detector scores, network graph, incidents) | Working |
| Threshold baseline detector | Working (baseline only) |
| Independent digital twin | Placeholder: returns fixed nominal values |
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

Open **http://localhost:5173** in your browser. The status pill at the top right should read **Plant normal**, and the plant should be animating.

### 5. Try the demo

1. On the **Dashboard** tab, find the **Simulator** card on the plant view.
2. Click **Unauthorised valve close**. Within a few seconds the status turns to **Incident in progress**, Valve 1 turns red, pressure jumps, flow collapses, and PLC-02 shows **Compromised**.
3. Click **Approve containment**. The response runs in stages (block the source, enter a safe state, restore) and the process returns to normal.
4. The incident is marked **Recovered** only after the plant has stayed within its limits for 10 seconds.
5. Open the **Network** tab to see the red attacker path to PLC-02 and the message table, and the **Incidents** tab for the evidence list and progress.

Try the other scenarios too: replay attack, denial of service, sensor drift, stuck valve, filter clogging, and the legitimate operator speed change, which must **not** be flagged as an attack. **Stop and reset** returns the plant to normal at any time.

### 6. Stop everything

Press `Ctrl+C` in each terminal.

---

## Run the tests

```bash
cd backend
python -m pytest            # backend: 23 tests
cd ../frontend
npm run build               # frontend: type-check and production build
```

Run the backend tests with the virtual environment active (or use `.venv/Scripts/python -m pytest` on Windows and `.venv/bin/python -m pytest` on macOS/Linux). The same checks run automatically on every pull request.

## Generate labelled datasets

```bash
cd backend
python -m sim.dataset --out ../data/generated
```

This writes 24 simulator runs (normal and every scenario) as CSV plus network-event files and a `manifest.json`. The files are not committed because they are reproducible. See [data/README.md](data/README.md) for the labels and how to split them without leaking time windows.

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
| You started a scenario and the plant looks stuck | Click **Stop and reset**. |

---

## How it works

```text
Plant simulator ──► telemetry + network/command events
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
 Detectors (baseline today;        Digital twin (expected state
 ML + physics checks planned)      from authorised commands only)
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

### Scenarios

| Scenario | Kind | What it does |
|---|---|---|
| Unauthorised valve close | attack | A non-SCADA source closes Valve 1: pressure rises, flow collapses |
| False data injection | attack | A spoofed report biases the reported pressure |
| Replay attack | attack | Recorded readings are replayed while Valve 1 is closed; old messages are re-sent |
| Denial of service | attack | A message flood hits PLC-03, heartbeats drop, sensor updates go stale |
| Small false data | attack | A small bias with no network trace (subtle) |
| Slow-ramp false data | attack | A creeping bias with no network trace (looks like drift) |
| Sensor drift | fault | The pressure sensor drifts, no malicious traffic |
| Stuck valve | fault | Valve 1 sticks half open although commanded open |
| Filter clogging | fault | Flow falls and pressure rises slowly |
| Operator speed change | benign | An authorised SCADA command lowers Pump 1 to 85% |

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
  sim/                plant, scenarios, engine, containment, recovery, dataset generator
  twin/               digital twin (placeholder)
  detect/             detectors (threshold baseline)
  incident/           incident manager (placeholder)
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
