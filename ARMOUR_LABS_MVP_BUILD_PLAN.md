# ARMOUR LABS: MVP Build Plan (3 people)

Domain: a **campus microgrid substation** (utility feed, solar, battery, hospital feeder, campus feeder, three IEDs, SCADA).

Scope follows §25 of the project description: one simulated substation, the core scenarios plus the look-alikes, one evaluated ML detector, the independent twin, a live incident dashboard, one simulated containment workflow, and recovery verification.

## 1. Where we are

| Build | Goal | State |
|---|---|---|
| 1 | Live substation | **Done** |
| 2 | Attack and impact | **Done** |
| 3 | ML detection and metrics | Not started (baseline detector only) |
| 4 | Digital twin and incident intelligence | **Twin v0 done**; classification, fusion, explanations, propagation graph not started |
| 5 | Containment, recovery, replay | **Containment and recovery done**; dry-run, replay scrubber, polish not started |

Already working in the repo: the simulator (11 scenarios), the model-based twin, staged containment, recovery verification, the dataset generator, the FastAPI backend and SQLite log, and the dashboard (30 backend tests pass).

## 2. Roles

| Person | Role | Owns |
|---|---|---|
| **P1** | Frontend and integration lead | `frontend/`: dashboard, replay UI, metrics page, incident panel, demo script, final integration |
| **P2** | Simulation, attacks and twin | `backend/sim/`, `backend/twin/`, `data/`: model refinement, twin fitting and tuning, dry-run, datasets |
| **P3** | Detection and incident intelligence | `backend/detect/`, `backend/incident/`, `backend/api/`, `backend/db/`: ML, physics checks, fusion, explanations, metrics |

## 3. Contracts

The contracts are fixed in `backend/core/contracts.py` and documented in `docs/contracts.md`. Everyone builds against them. Changing one needs all three people to agree, with the backend model, `frontend/src/types.ts` and the docs updated in the same pull request.

Key points: telemetry carries `frequency, bus_voltage, grid_import_kw, pv_kw, bess_kw, bess_soc, load_critical_kw, load_noncritical_kw, irradiance`, five breaker states and three IED statuses; events carry an `authorised` flag; the twin's only command input is the authorised command log.

## 4. Builds

Each build ends with a **demo checkpoint**: what P1's frontend shows at an evaluation, using real backend data.

### Build 1: Live substation (done)
Simulated substation with seeded noise, 1 Hz telemetry over WebSocket, animated isometric view, relay panel, sensor strip.
- **Acceptance:** runs 10 minutes without drift or crash; values stay in normal ranges (tested).

### Build 2: Attack and impact (done)
Scenario engine and API, network events with an `authorised` flag, topology view with attacker path, alert feed, the substation reacting.
- **Acceptance:** each scenario is reproducible from the same seed; alerts come from real data (tested).

### Build 3: ML detection and metrics
- **P3:** feature extraction (rolling statistics, rates of change, command frequency, sequence checks); train an Isolation Forest on normal simulator data with a run-based train/test split; physics-invariant checks (power balance: import = load − PV − battery, breaker open implies zero feeder load, frequency plausible on a stiff grid); score normalisation by percentile on held-out normal data; evaluation script reporting precision, recall, F1, false-positive rate, confusion matrix, detection latency and per-scenario results for baseline vs ML vs combined; `GET /metrics`.
- **P2:** regenerate and extend datasets (`python -m sim.dataset`); add more seeds and variants as needed.
- **P1:** metrics page (confusion matrix, comparison table, labelled by data source), live score display.
- **Demo checkpoint:** scores move live during an attack; the metrics tab shows measured results, including honest misses on the subtle attacks.
- **Acceptance:** train/test split by run; every number shown is computed, none hard-coded; benign scenarios produce no false alarms in the measured results.

### Build 4: Digital twin tuning and incident intelligence
- **P2:** fit the twin's parameters from normal data (load profiles, PV efficiency, battery lag) and set tolerance bands from held-out normal data; keep the "observed state does not change expectations" test passing.
- **P3:** evidence fusion as an executable rule table (see §10 of the description): attack, fault or unknown with confidence and an uncertainty reason; time alignment of network, command and process evidence; template-based explanations built only from real fields (a test fails if any number in the text is not in the incident data); propagation-graph data with observed, correlated and inferred edges.
- **P1:** incident panel with evidence tags, likely cause with uncertainty, propagation graph, and timeline.
- **Demo checkpoint:** the unauthorised trip is classified as an attack; the stuck breaker as a fault; planned switching raises nothing.
- **Acceptance:** the benign and fault scenarios are not classified as attacks (tested).

### Build 5: Containment dry-run, replay, polish
- **P2:** twin dry-run of a proposed containment (predicted outcome and any unsafe side effect, for example reclosing onto a fault).
- **P3:** response recommendation and replay endpoint options (time range, playback).
- **P1:** response panel with dry-run preview, recovery table, replay scrubber, UI polish, rehearsed demo script, recorded fallback video.
- **Demo checkpoint:** the full flow: healthy, look-alike, attack, detect, explain, approve containment, recovery verified, replay.
- **Acceptance:** "Recovered" appears only when the checks pass; replay uses recorded events and timestamps.

## 5. Working rules
- **Contracts first:** schema changes go through all three people.
- **Integration points:** each build ends with a 30-minute joint run on one machine before the demo checkpoint.
- **Branches:** one feature branch per person per build; merge to `main` through a pull request once CI passes.
- **Guardrails:** simulation only; no claim that an anomaly proves malice; illustrative values labelled; the LLM assistant is a stretch goal and never used for detection.

## 6. Risks and mitigations
- **Integration slip:** mitigated by fixed contracts and the working base.
- **Twin becomes circular:** keep it independent with its own parameters and the authorised command log as its only command input.
- **Too-perfect metrics:** include the subtle attacks and report failures.
- **Demo machine surprises:** run the build-5 demo on the presentation machine; keep a recorded fallback video.
- **Cut order if time runs short:** replay UI, then the denial-of-service scenario, then extra ML models (CNN/LSTM are not planned), never the detect-to-recovery flow.

## 7. Verification (end to end)
1. Start backend and frontend; confirm live telemetry and animation.
2. Run each scenario from the UI; confirm alert, scores, twin mismatch, evidence and propagation view.
3. Run planned switching and passing clouds; confirm no incident is raised.
4. Run the stuck breaker; confirm it is classified as a fault, not an attack.
5. Approve containment; confirm "Recovered" appears only after the dwell time.
6. Open replay and confirm it matches the recorded timestamps.
7. Run the evaluation script and confirm the metrics page matches its output.
