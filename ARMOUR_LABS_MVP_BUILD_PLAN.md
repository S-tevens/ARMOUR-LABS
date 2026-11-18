# ARMOUR LABS: MVP Build Plan (3 people)

Scope follows §25 of the project description: one simulated plant, two attack scenarios plus one benign fault, one evaluated ML detector, a digital-twin residual check, a live incident dashboard, one simulated containment workflow, and recovery verification.

## 1. Team roles

| Person | Role | Owns |
|---|---|---|
| **P1 (you)** | Frontend and integration lead | React + TS dashboard, plant SVG animation, topology, timeline/replay UI, WebSocket client, demo script, final integration |
| **P2** | Simulation, attacks and digital twin | Plant simulator, PLC/network event generator, attack and fault engine, independent twin, residuals, recovery checks |
| **P3** | Detection and incident intelligence | Feature extraction, Isolation Forest + threshold baseline, physics invariants, evidence fusion, incident classifier, explanation text, evaluation metrics, FastAPI incident endpoints |

Shared: FastAPI app skeleton and SQLite layer (P3 owns the code, P2 and P1 consume it).

## 2. Day-1 contracts (agree before anyone codes)

Everyone builds against these JSON shapes. P1 works from a mock server until real data arrives.

**Telemetry tick** (WebSocket `/ws/telemetry`, 1 Hz):
`{t, tick, tank1_level, tank2_level, pressure, flow, temperature, pump1, pump2, valve1, plc_status:{plc01,plc02,plc03}}`

**Network/command event**: `{seq, t, src, dst, function_code, register, value, authorised:bool}`

**Twin state**: `{t, expected:{...same vars}, residual:{...}, norm_residual:{...}}`

**Alert/incident**: `{id, t_start, severity, confidence, affected_devices[], classification (attack|fault|unknown), scores:{network, controller, process, twin}, evidence[{type, text, observed|correlated|inferred}], status}`

**Control API**: `POST /scenario/start {name}`, `POST /scenario/stop`, `POST /incident/{id}/approve-response`, `GET /incidents`, `GET /incidents/{id}/replay`, `GET /metrics`.

Scenarios: `unauthorised_valve_close` (main), `false_data_injection` (sensor spoof), `sensor_drift` (benign fault).

Repo layout: `backend/{sim,twin,detect,incident,api}`, `frontend/`, `data/`, `docs/`. Fixed random seed and a simulation clock for repeatable demos. SQLite is an append-only event log.

## 3. Builds (each ends with a presentable frontend)

Each build has a **demo checkpoint**: what P1's frontend shows at that evaluation, using real backend data wherever it exists and a clearly labelled mock where it doesn't.

### Build 1: Live plant (target: end of day 1-2)
- **P2:** deterministic plant model (Tank 1 → Pump 1 → Filter → Valve 1 → Tank 2 → Pump 2), noise, 1 Hz telemetry generator, telemetry over WebSocket.
- **P3:** FastAPI skeleton, SQLite schema, event logging, mock detector returning constant "normal".
- **P1:** React app shell, dark industrial theme, animated SVG plant (flowing pipes, tank levels, pump/valve states), live readouts, status bar "SYSTEM STATUS: NORMAL".
- **Demo checkpoint:** a healthy, animated plant driven by live backend telemetry.
- **Acceptance:** runs 10 minutes with no drift or crash; values stay in normal ranges.

### Build 2: Attack and impact (day 3-4)
- **P2:** attack engine with `unauthorised_valve_close` and `false_data_injection`; the plant physically reacts; network/command event records with `authorised` flag; scenario API.
- **P3:** simple threshold baseline detector on telemetry; first alert stream (no ML yet).
- **P1:** scenario selector and "Launch attack" button, network topology panel (green/amber/red nodes, highlighted path), plant view reacting (pressure spike, flow drop), alert feed.
- **Demo checkpoint:** judge picks a scenario, triggers it, sees the PLC and path highlight, the plant change, and a first alert.
- **Acceptance:** each scenario is reproducible from the same seed; the alert fires from real telemetry, not a timer.

### Build 3: ML detection and metrics (day 5-6)
- **P3:** features (rolling stats, rates of change, command frequency); train Isolation Forest on normal simulator data, time-based train/test split; physics-invariant checks (mass balance, pump-on ⇒ flow, valve-closed ⇒ no flow); evaluation script (precision, recall, F1, FPR, confusion matrix, detection latency, per-attack results) comparing threshold baseline vs ML vs combined; `GET /metrics`.
- **P2:** generate labelled datasets (normal, attacks, subtle variants); add `sensor_drift` benign fault.
- **P1:** threat monitor (four score gauges, severity, confidence), metrics page (confusion matrix, comparison table, labelled "source: simulator").
- **Demo checkpoint:** scores move live during an attack; a metrics tab shows measured results, including honest misses on subtle attacks.
- **Acceptance:** train/test split by time; every number in the UI is computed, none hard-coded.

### Build 4: Digital twin and incident intelligence (day 7-8)
- **P2:** independent twin (own fitted parameters, inputs are the *authorised* command log only); residuals and normalised residuals; tolerance bands.
- **P3:** evidence fusion with the §10 rule table (attack vs fault vs unknown); incident object with evidence tagged observed/correlated/inferred; template-based explanation built only from alert fields; propagation graph data.
- **P1:** digital-twin comparison table (expected vs observed vs residual, out-of-range highlighted), incident investigation panel (evidence list, likely cause with uncertainty, propagation graph), timeline.
- **Demo checkpoint:** the attack shows expected-vs-observed mismatch, an evidence-based explanation, and the propagation view; `sensor_drift` is labelled "likely physical fault".
- **Acceptance:** twin residuals are non-zero but within tolerance under normal operation; the benign fault is not classified as an attack.

### Build 5: Containment, recovery, replay and polish (day 9-10)
- **P2:** simulated containment (reject command, safe state, restore); twin dry-run of the response; recovery verification (tolerances plus N-second dwell) returning Recovered / Recovering / Unresolved.
- **P3:** response recommendation, approve-response endpoint, incident replay endpoint from recorded events; final evaluation run and numbers.
- **P1:** response plan panel with approve button and dry-run preview, recovery verification table, replay scrubber, UI polish, rehearsed full demo.
- **Demo checkpoint:** the full flow: healthy → attack → detect → explain → approve containment → recovery verified → replay.
- **Acceptance:** "Recovered" appears only when the checks pass; replay uses recorded events and timestamps.

## 4. Per-person summary

**P1 (frontend + integration):** B1 plant view → B2 topology and attack controls → B3 threat monitor and metrics → B4 twin table and incident panel → B5 response, recovery, replay, demo.

**P2 (sim + attacks + twin):** B1 simulator → B2 attacks and events → B3 datasets and benign fault → B4 twin and residuals → B5 containment and recovery.

**P3 (detection + incidents + API):** B1 API skeleton and SQLite → B2 threshold baseline → B3 ML, invariants, metrics → B4 fusion, incidents, explanations → B5 response, replay, final evaluation.

## 5. Working rules
- **Contracts first:** schema changes go through all three people; P1 never blocks, because the mock server serves the same shapes.
- **Integration points:** each build ends with a 30-minute joint integration run on one machine before the demo checkpoint.
- **Branches:** one feature branch per person per build; merge to `main` only when the checkpoint passes.
- **Guardrails (from §25):** simulation only; no claim that an anomaly proves malice; illustrative values labelled as such; the LLM assistant is a stretch goal and not used for detection.

## 6. Risks and mitigations
- **Integration slip:** mitigated by day-1 schemas and the mock server.
- **Twin detects only your own injection:** keep it independent with imperfect parameters and authorised-command inputs.
- **Too-perfect metrics:** include subtle attacks and report failures.
- **Demo machine surprises:** run the build-5 demo on the presentation machine; keep a recorded fallback video.
- **Cut order if time runs short:** replay UI, then the false_data_injection scenario, then LSTM/CNN (not planned), never the detect-to-recovery flow.

## 7. Verification (end-to-end)
1. Start backend and frontend; confirm live telemetry and animation.
2. Run each scenario from the UI; confirm alert, scores, twin mismatch, evidence, and propagation view.
3. Run `sensor_drift`; confirm it is classified as a fault.
4. Approve containment; confirm recovery only displays "Recovered" after the dwell time.
5. Open replay and confirm it matches the recorded timestamps.
6. Run the evaluation script and check the metrics page matches its output.
