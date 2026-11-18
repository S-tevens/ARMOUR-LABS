# ARMOUR LABS

**AI-powered digital twin for industrial cyberattack detection, explanation and recovery.**

> Detect the attack. Understand the impact. Contain the threat. Verify recovery.

ARMOUR LABS is a cyber-physical security platform for Industrial Control Systems (ICS). It runs a software simulation of a small water-treatment plant and watches the network events, PLC commands, sensor telemetry and physical process together. A digital twin estimates how the plant *should* behave. ARMOUR LABS compares that expectation with what is observed, correlates the evidence across layers, and helps an operator understand, contain and recover from an incident.

Unlike an intrusion-detection dashboard that only lists alerts, ARMOUR LABS connects a cyber event to its physical consequences.

> **Status:** base project (v0.1). A working end-to-end skeleton: a simple plant simulator, two attack scenarios and one benign fault, a placeholder twin, a threshold baseline detector, a placeholder incident manager, a SQLite event log, a FastAPI + WebSocket backend and a live React dashboard. The ML detector, the independent twin, evidence fusion and a real evaluation are still to be built. Placeholders are marked `PLACEHOLDER` or `TODO` in the code.

## Quick start

Requirements: Python 3.11+ and Node 20+.

**Backend** (runs on http://localhost:8000):

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

**Frontend** (runs on http://localhost:5173):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, pick a scenario under "Attack simulator", watch the plant, scores and twin table react, then approve the simulated containment on the incident card.

**Tests:**

```bash
cd backend && python -m pytest
cd frontend && npm run build
```

Configuration (environment variables): `ARMOUR_SEED` (default 42), `ARMOUR_TICK_SECONDS` (default 1.0), `ARMOUR_DB` (SQLite path, default in-memory), `VITE_API_URL` (frontend, default http://localhost:8000).

## Repository layout

```text
backend/
  core/contracts.py   shared data models (source of truth)
  sim/                plant model, scenarios, engine          (P2)
  twin/               digital twin (placeholder)              (P2)
  detect/             detectors (threshold baseline)          (P3)
  incident/           incident manager (placeholder)          (P3)
  db/                 append-only SQLite event log            (P3)
  api/                FastAPI app, WebSocket, runtime         (P3)
  tests/
frontend/             React + TypeScript dashboard            (P1)
docs/contracts.md     message and API contracts
CONTRIBUTING.md       workflow, ownership and rules
```

## Everything runs in simulation

The plant, the network and every attack scenario exist only inside an isolated software simulation. Nothing connects to real PLCs, industrial networks or external systems.

## How it works

```text
Plant simulator ──► telemetry + network/command events
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
 ML + physics-invariant            Digital twin (expected state
 detectors                         from authorised commands only)
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

## MVP scope

- One simulated water-treatment plant (tanks, pumps, filter, valve, sensors, three PLCs, SCADA)
- Two attack scenarios (unauthorised valve close, false data injection) and one benign fault (sensor drift)
- A threshold baseline and an Isolation Forest detector, plus physics-invariant checks
- An independent digital twin with residual checks
- A live incident dashboard with network topology, twin comparison and evidence view
- Simulated containment with a twin dry-run, and recovery verification
- Incident replay from recorded events

## Planned tech stack

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript, SVG plant animation |
| Backend | Python, FastAPI, WebSockets |
| ML | scikit-learn (PyTorch only if justified) |
| Data | NumPy, Pandas |
| Storage | SQLite (append-only event log) |

## Build plan

The work is split across three people in five builds. Each build ends with a presentable frontend:

1. Live plant
2. Attack and impact
3. ML detection and metrics
4. Digital twin and incident intelligence
5. Containment, recovery and replay

Full plan, roles, shared JSON contracts, acceptance criteria and risks: **[ARMOUR_LABS_MVP_BUILD_PLAN.md](ARMOUR_LABS_MVP_BUILD_PLAN.md)**

## Evaluation approach

Accuracy alone is not reported. Planned metrics are precision, recall, F1, false-positive rate, confusion matrix, detection latency, per-attack results and recovery verification time. A threshold baseline, a single ML model and the combined approach are compared, using time-based train/test splits. Each result is labelled by source (public dataset or custom simulator).

## Guardrails

- An anomaly is evidence, not proof of an attack.
- Illustrative UI values are clearly labelled and never presented as measured results.
- "Recovered" is shown only when the verification checks pass.
- The LLM assistant, if built, only explains structured detection results. It does not detect anything.

## Research inspiration

*Machine Learning-Based Detection of Anomalies, Intrusions, and Threats in Industrial Control Systems*, IEEE Access, 2025. Any results reported by the paper are not results achieved by this project.

## Team

Armour Labs, a three-person team.

## License

No license has been chosen yet.
