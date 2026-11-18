# ARMOUR LABS
## AI-Powered Digital Twin for Power-Grid Cyberattack Detection, Explanation, and Recovery

> **Project tagline:** Detect the attack. Understand the impact. Contain the threat. Verify recovery.

---

## 1. Project Overview

**ARMOUR LABS** is an AI-powered cyber-physical security platform for electric power systems. It creates a live digital twin of a simulated **campus microgrid substation** and monitors its network activity, breaker commands, meter readings and physical power flows.

Machine-learning models detect suspicious patterns. A digital twin independently estimates how the substation should behave given the commands that were actually authorised. ARMOUR LABS compares observed behaviour with these expected states to identify cyber-physical inconsistencies, assess their impact, and help operators investigate incidents.

When a simulated attack occurs, ARMOUR LABS aims to:

1. Detect abnormal network, command, or power-flow behaviour.
2. Identify the affected device and the part of the grid it feeds.
3. Explain the evidence behind the alert.
4. Visualise how the incident propagates through the substation.
5. Recommend or simulate safe containment actions.
6. Verify whether the substation has returned to an acceptable operating state.

Unlike a conventional intrusion-detection dashboard that primarily displays alerts, ARMOUR LABS connects a cyber event to its potential physical consequences.

### Research foundation

The project takes inspiration from:

**"Machine Learning-Based Detection of Anomalies, Intrusions, and Threats in Industrial Control Systems" — IEEE Access, 2025.** *(TODO: add authors and DOI before submission.)*

The paper explores machine-learning approaches such as CNN, LSTM, SVM, and Isolation Forest for detecting anomalies and threats in industrial control systems. ARMOUR LABS uses this research direction as a foundation and extends the concept with a simulated grid digital twin, cross-layer event correlation, visual incident investigation, and recovery verification.

*The implementation should independently validate its models and results. Any accuracy or F1 score reported by the paper must not be presented as a result achieved by ARMOUR LABS.*

---

## 2. Problem Statement

Electric grids and microgrids serve hospitals, campuses, data centres, factories and cities. A cyberattack on them can affect far more than computers: an unauthorised breaker command can cut power to a hospital, and a spoofed measurement can make a controller take a harmful action while the real grid is perfectly healthy. Real incidents, such as the attacks on the Ukrainian grid in 2015 and 2016, used exactly these techniques.

A conventional alert may indicate that network traffic is unusual, but an operator still needs to determine:

- Which device and which part of the grid is affected?
- What physical consequences could follow (loss of supply, instability, equipment stress)?
- Is the anomaly caused by a cyberattack, an equipment fault, a sensor failure, a natural change such as clouds, or legitimate planned work?
- How did the event propagate through the substation?
- What response is appropriate, and is it safe?
- Has the system actually recovered after mitigation?

A particularly hard case is the **look-alike**: a planned, authorised breaker opening and an attacker's unauthorised opening have the same physical effect. Only the authorisation, checked against the command log, tells them apart. ARMOUR LABS addresses these questions by correlating network events, breaker commands, meter readings, power flows, and digital-twin predictions.

---

## 3. Demonstration Environment: a Campus Microgrid Substation

The prototype simulates a small campus microgrid substation. It is a strong buildathon environment because the stakes are immediately understandable and the components map cleanly onto a single-line diagram.

```text
UTILITY ──[CB-MAIN]──┬──────────── bus ────────────┬──────────┐
                     │                             │          │
           [CB-PV]── PV array        [CB-BESS]── Battery      ├─[CB-CRIT]── Hospital (critical load)
                                                              └─[CB-NC]──── Campus (non-critical load)
```

- **Utility connection** with a main breaker (CB-MAIN) and grid meter (frequency, voltage, import).
- **Solar array** (500 kW rated) with an inverter and breaker (CB-PV).
- **Battery storage** (250 kW, 200 kWh) with a breaker (CB-BESS), steered by an energy management system.
- **Hospital feeder** (critical load, about 400 kW) with breaker CB-CRIT.
- **Campus feeder** (non-critical load, about 300 kW) with breaker CB-NC.
- **Weather station** (irradiance).
- **Three protection relays (IEDs)** and a **SCADA / microgrid controller** on a segmented network.

The substation is simulated entirely in software. No real equipment or grid is required.

---

## 4. Main System Components

1. **Substation Simulator** — models loads, solar, battery, breakers, frequency and voltage, and generates normal telemetry.
2. **ICS Network Simulator** — represents SCADA, the three IEDs and their message exchange.
3. **Attack Scenario Engine** — injects controlled attack, fault and benign scenarios into the isolated simulation.
4. **ML Detection Engine** — detects suspicious network and process behaviour.
5. **Digital Twin** — predicts expected behaviour from authorised commands and calculates deviations.
6. **Incident Intelligence Engine** — correlates evidence, identifies likely causes, and explains alerts.
7. **Response and Visualisation Layer** — presents incidents, simulates containment, and verifies recovery.

### High-level architecture

```text
              SUBSTATION SIMULATOR
                      |
           Meters, IEDs, Breakers
                      |
           +----------+----------+
           |                     |
     Process Telemetry      ICS Network Events
           |                     |
           v                     v
    Feature Extraction     Network Features
           |                     |
           v                     v
    Process Anomaly        Network Anomaly
       Detection              Detection
           |                     |
           +----------+----------+
                      |
               Evidence Fusion
                      |
                      v
               DIGITAL TWIN
      Expected (from authorised commands)
              vs. Observed State
                      |
                      v
            INCIDENT CLASSIFICATION
                      |
                      v
          ROOT-CAUSE / IMPACT VIEW
                      |
                      v
           RESPONSE RECOMMENDATION
                      |
                      v
            SIMULATED CONTAINMENT
                      |
                      v
            RECOVERY VERIFICATION
                      |
                      v
                LIVE DASHBOARD
```

---

## 5. Substation Simulator

The simulator models how the microgrid behaves over time, with a state for each component:

```text
Frequency:          50.00 Hz
Bus voltage:        1.000 pu
Utility import:     324 kW
PV output:          380 kW
Battery:            +40 kW (discharging), 60 % charge
Hospital feeder:    403 kW   (CB-CRIT closed)
Campus feeder:      334 kW   (CB-NC closed)
```

Simplified process rules:

- Loads follow slow profiles and are only served while their breaker is closed.
- PV output follows irradiance, and drops to zero if the inverter trips or CB-PV opens.
- The energy management system steers the battery to hold utility import near a target, corrects for state of charge, and applies a frequency droop term that reads the **reported** frequency.
- Grid-connected: the utility holds 50 Hz and import = load − PV − battery.
- Islanded (CB-MAIN open): the battery forms the grid, and any imbalance moves frequency and voltage.
- Sensor faults and attacks (bias, replay, stale updates) change what is reported only. Because the controller reads the reported frequency, a spoofed measurement has a real physical effect.

The simulator is seeded and deterministic, and produces a timestamped telemetry stream for the detection engine and dashboard.

---

## 6. ICS Network Simulation

```text
                  EXTERNAL NETWORK
                         |
                      FIREWALL
                         |
              SCADA / microgrid controller
                         |
             +-----------+-----------+
             |           |           |
          IED-01       IED-02      IED-03
     (utility iface) (solar+batt) (load feeders)
             |           |           |
        CB-MAIN,     CB-PV, CB-BESS, CB-CRIT,
        grid meter   inverter        CB-NC
```

Each IED has a security state: **normal** (green), **suspicious** (amber), **compromised** (red). Network events are structured records (`seq, t, src, dst, function_code, register, value, authorised`) using IEC 61850 style `OPERATE` for breakers and `WRITE_SETPOINT` for set-points, which keeps the demonstration safe, reproducible and easy to test.

---

## 7. Attack Scenario Engine

All scenarios stay inside the isolated simulation. Do not target real relays, grids or external systems.

### Scenarios

| Scenario | Kind | What the simulation changes | What ARMOUR LABS should detect |
|---|---|---|---|
| Unauthorised breaker trip | attack | A non-SCADA source opens CB-CRIT; the hospital loses power | Command not in the authorised log, breaker/load mismatch |
| False frequency report | attack | A spoofed 49.5 Hz makes the controller over-discharge the battery; the grid is fine | Implausible frequency on a stiff grid, battery response without cause |
| Replay attack | attack | Recorded normal readings are replayed while CB-CRIT is opened | Duplicate/stale messages; breaker state and battery response contradict the readings |
| Denial of service | attack | Message flood to IED-03, heartbeats dropped, measurements go stale | Traffic-rate and availability anomaly |
| Small false data | attack | +0.02 pu voltage bias with no network trace | Subtle twin residual (designed to test the limits) |
| Slow-ramp false data | attack | Voltage creeps up like a failing sensor, no network trace | Growing twin residual; hard to tell from drift |
| Voltage sensor drift | fault | The voltage sensor drifts | Residual with no network or command evidence |
| Stuck breaker | fault | An authorised open command does not take effect | Authorised command but load did not drop: equipment fault, not attack |
| PV inverter trip | fault | Solar output drops to zero | Large PV residual despite normal irradiance, no network evidence |
| Planned switching | benign | SCADA opens CB-NC (authorised) | **Nothing**: the twin expects the load drop |
| Passing clouds | benign | Irradiance falls to 30% | **Nothing**: the weather station explains the PV drop |

### Example: unauthorised breaker trip

Normal state:

```text
CB-CRIT = CLOSED     Hospital feeder = 403 kW
Utility import = 324 kW     Battery = +40 kW
```

Simulated incident:

```text
Unauthorised OPERATE CB_CRIT=OPEN from 10.0.0.66 to IED-03 (source is not SCADA)
Hospital feeder = 0 kW (de-energised)
Utility import = 185 kW, battery absorbing 250 kW
```

The simulator changes the process according to its rules. ARMOUR LABS receives the resulting network events and telemetry and attempts to detect and explain the incident.

---

## 8. Machine-Learning Detection Engine

The ML layer is inspired by the candidate approaches in the IEEE research paper.

### Candidate models

- **1D CNN:** learns local patterns in time-windowed telemetry or network features.
- **LSTM:** models temporal sequences and changes in system behaviour.
- **Support Vector Machine (SVM):** a supervised classification baseline.
- **Isolation Forest:** detects unusual observations when labelled attack examples are limited.

Do not assume that all four models are necessary. Start with a strong baseline and add complexity only when it improves measured performance.

### Detection streams

**A. Network behaviour:** event rate, source and destination IED, function code and register, command frequency, failed or unexpected communication, sequence-number and timing patterns.

**B. Process telemetry:** frequency, bus voltage, utility import, PV and battery power, battery state of charge, feeder loads, breaker states, rates of change.

**C. Controller behaviour:** command type and source, whether a command is authorised, whether it is valid in the current operating state, command frequency.

### Evidence fusion

The system combines evidence from multiple detectors rather than trusting one model in isolation. Each detector's score is normalised to [0, 1] using its percentile on held-out normal data, then combined by an explicit, explainable rule table (the Section 10 table made executable). Learned fusion is out of scope for the MVP.

The dashboard currently shows baseline scores (illustrative until real detectors replace them), for example:

```text
Network score:       0.90
Controller score:    0.90
Process score:       0.04   (fixed engineering limits, independent of the twin)
Digital-twin score:  1.00
```

---

## 9. Digital Twin and Expected-State Comparison

The digital twin is a central differentiator. It maintains an independent model of the substation and estimates what the readings should look like **given the commands that were actually authorised**.

Design rules:

- **Independent:** it has its own parameters (not the simulator's constants) so it does not simply echo the simulator.
- **Authorised commands only:** its only command input is the authorised command log, never the observed breaker or set-point states. If it read observed states it would predict the attack's own effect and the residual would vanish. A test proves its expectations do not change when observed breaker states change.
- **Other inputs:** the clock (schedule and forecast) and the weather-station irradiance reading.

Example (unauthorised breaker trip):

| Variable | Expected | Observed | Interpretation |
|---|---:|---:|---|
| CB-CRIT | Closed | Open | State mismatch |
| Hospital load | 403 kW | 0 kW | Large deviation |
| Utility import | 324 kW | 185 kW | Large deviation |
| Frequency | 50.00 Hz | 50.00 Hz | No notable deviation |

A residual is the difference between an observed value and its expected value:

```text
Residual = Observed value - Expected value
```

Residuals are normalised by scales derived from normal-operation variability so that different units can be compared. A large residual is evidence of unexpected behaviour, not proof of a cyberattack. ARMOUR LABS must correlate it with network and command evidence before assigning a likely cause.

---

## 10. Distinguishing Cyberattacks from Faults and Legitimate Changes

An important objective is to avoid treating every abnormal reading as a cyberattack. For example, if hospital load drops to zero, possible causes include an unauthorised trip, a stuck or failed breaker, a feeder fault, planned switching, or a metering fault.

| Evidence | Possible interpretation |
|---|---|
| Breaker opens with no matching authorised command | Possible unauthorised command |
| Authorised open command, load does not drop | Equipment fault (stuck breaker) |
| Authorised open command, load drops as expected | Planned switching: no incident |
| One reading deviates, related signals stay consistent | Possible sensor fault or spoofing |
| Reported frequency implausible on a stiff grid, battery reacts | Possible false data injection |
| PV falls and irradiance falls together | Natural change (clouds) |
| PV falls with normal irradiance, no network activity | Equipment fault (inverter) |
| Readings look normal but breaker state and battery response disagree | Possible replay or masking |
| Unusual network activity and an invalid command occur together | Stronger cyberattack evidence |

The system presents a **likely cause with supporting evidence and uncertainty**, not certainty where the data cannot support it.

---

## 11. Explainable AI and Incident Explanation

When an alert is raised, ARMOUR LABS shows the evidence behind it.

```text
INCIDENT: UNAUTHORISED BREAKER COMMAND
Affected device: IED-03 (hospital and campus feeders)
Severity: HIGH

Evidence:
- Unauthorised OPERATE CB_CRIT=OPEN from 10.0.0.66 (not SCADA)
- 1 breaker state differs from the authorised command log
- Hospital feeder load 0 kW vs expected 403 kW
- Utility import 185 kW vs expected 324 kW
```

Feature-importance methods such as SHAP may be used where appropriate for the selected model. For simpler detectors, show direct evidence such as residuals, thresholds, and the events that triggered the alert. A natural-language explanation is generated from structured detection results and must not invent evidence or make unsupported claims.

---

## 12. Root-Cause and Impact Visualisation

ARMOUR LABS displays an event-propagation view that connects the incident to affected components:

```text
SIMULATED SECURITY INCIDENT
            |
            v
   Unauthorised command to IED-03
            |
            v
      CB-CRIT opens
            |
       +----+----+
       |         |
       v         v
 Hospital feeder   Battery absorbs
 de-energised      lost load
       |
       v
   Patient-care risk
```

The visualisation distinguishes directly observed events, correlated evidence and inferred causal relationships. A sequence of correlated events does not automatically prove causation.

---

## 13. Response and Containment

After an incident is identified, ARMOUR LABS presents a staged response plan. The prototype uses **simulated containment**, not commands to real equipment, and the operator inspects and approves it.

1. **Block** the malicious source at the firewall and drop spoofing, replay and flood effects.
2. **Safe state:** recalibrate meters, repair faults, hold the battery idle, and reclose open breakers with the **hospital feeder first**.
3. **Restore:** return the battery to automatic control and clear IED flags.
4. Continue monitoring telemetry and network events.

Containment changes are authorised SCADA commands, so they appear in the event stream and in the twin's command log. A planned refinement is a **twin dry-run** that predicts the outcome of a response before the operator approves it, because a "safe state" can itself be unsafe (for example, reclosing onto a fault).

---

## 14. Recovery Verification

A successful response is not simply an alert disappearing. ARMOUR LABS checks whether the substation has returned to acceptable operating limits.

| Check | Acceptable limit |
|---|---|
| Frequency | 49.85–50.15 Hz |
| Bus voltage | 0.97–1.03 pu |
| Utility import | 150–480 kW |
| Battery charge | 35–90 % |
| Hospital load | 340–460 kW |
| Breakers | All five closed |

The values must stay within limits for 10 consecutive seconds (dwell time) so the status does not flicker. Possible final states: **Recovered**, **Recovering** (moving towards limits), **Unresolved** (limits not reached within 90 seconds). The dashboard only displays "Recovered" when the verification conditions are actually satisfied.

---

## 15. Incident Timeline and Replay

Every simulated incident is recorded as a sequence of timestamped events in an append-only event log.

```text
10:42:01  Substation operating normally
10:42:04  Unauthorised OPERATE CB_CRIT=OPEN from 10.0.0.66
10:42:04  Hospital feeder de-energised
10:42:05  Twin residuals and unauthorised command correlated
10:42:06  Incident opened
10:42:12  Containment approved: source blocked, battery held
10:42:14  Hospital breaker reclosed from SCADA
10:42:31  Recovery checks pass (10 s dwell)
```

The dashboard supports incident replay so judges can rewind and inspect how the event unfolded. Replay uses recorded events and timestamps, not a fabricated sequence.

---

## 16. AI Investigation Assistant

An optional LLM-based assistant can let an operator ask questions about an incident (why IED-03 was flagged, which feeders were affected, what response is recommended, whether recovery is verified). The LLM is **not the primary attack detector**. ML models and deterministic checks produce the detection evidence; the LLM converts those structured results into readable explanations and answers. This is a stretch goal.

---

## 17. Visual Dashboard

The dashboard should feel like a grid operations centre connected to a live digital twin, in a light, frosted-glass style.

- **Live substation view:** an isometric substation (utility pylon and transformer, solar array, battery with a charge bar, hospital and campus buildings, breakers) with animated power flow whose direction and speed follow the real values. A de-energised feeder greys out and is outlined in red.
- **Sensor strip:** frequency, voltage, utility import and battery charge, each with a badge showing whether it is within the twin's tolerance.
- **Protection relays:** the three IEDs with their breakers and readings, filterable by status.
- **Expected vs observed chart** with a "within twin tolerance" meter.
- **Detector scores** with the alert threshold marked.
- **Network view:** SCADA and the IEDs, with message counts and a red attacker path.
- **Incidents:** evidence, progress (Detected, Recovering, Recovered) and the approve-containment action.

Design direction: pale background, green for healthy, amber for suspicious, red for incidents, blue for power flow, clear typography, restrained animation, large readable metrics, no decorative graphs without meaning.

### The visual "wow" moment

1. Start with a healthy, animated substation.
2. Select a simulated attack scenario and trigger it.
3. Highlight the affected IED and network path.
4. Show the physical process reacting (the hospital feeder goes dark).
5. Display the digital-twin mismatch.
6. Reveal the detection evidence.
7. Run simulated containment, reclosing the hospital first.
8. Show recovery verification passing.

The visual change is driven by the actual simulation state and detection events, not a pre-rendered animation.

---

## 18. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React + TypeScript (Vite) | Main application |
| Substation visualisation | SVG | Animated isometric view |
| Backend | Python + FastAPI | APIs and orchestration |
| Real-time updates | WebSockets | Stream telemetry and alerts |
| ML | scikit-learn (PyTorch only if justified) | Detection models |
| Data processing | NumPy, Pandas | Feature engineering |
| Storage | SQLite (append-only event log) | Incidents, events, replay |
| Simulation | Custom Python simulator | Substation dynamics and scenarios |

---

## 19. Team Division (3 Members)

| Member | Responsibility | Deliverables |
|---|---|---|
| P1 | Frontend and integration | Dashboard, substation view, relays, network, incident and replay UI, demo |
| P2 | Simulation, attacks and twin | Substation model, scenarios, independent twin, containment, recovery checks |
| P3 | Detection and incident intelligence | Features, ML detector, physics checks, evidence fusion, explanations, API, evaluation |

---

## 20. Implementation Roadmap

Build in stages. The first goal is a reliable end-to-end demonstration, not a large collection of disconnected features. See [ARMOUR_LABS_MVP_BUILD_PLAN.md](ARMOUR_LABS_MVP_BUILD_PLAN.md) for the builds and acceptance checks.

1. **Working simulation:** the substation runs normally and updates live.
2. **Attack scenarios:** a judge can trigger an attack and see its impact.
3. **Detection:** the system detects attacks from generated input and reports measurable results.
4. **Digital twin:** the dashboard shows meaningful expected-versus-observed differences.
5. **Incident intelligence:** the system explains why an incident was raised.
6. **Response and recovery:** the complete detect-to-recovery workflow works end to end.
7. **Polish and evaluation:** a stable, repeatable, evidence-backed presentation.

---

## 21. Evaluation Metrics

Do not evaluate using accuracy alone. In an imbalanced cybersecurity dataset, accuracy can hide poor attack detection. Report:

- Precision, recall, F1 score, false-positive rate, confusion matrix
- Detection latency and per-attack-type performance
- Recovery verification time

Also compare a simple threshold baseline, one selected ML model, and the combined detection approach. Use a clear train/test split. For time-series data, split by run, never randomly by row, so adjacent time windows do not leak between training and test. Clearly label whether each result comes from a public dataset, the custom simulator, or both.

### Design decisions that keep the evaluation honest

- **Benign cases are required:** planned switching and passing clouds must not raise an incident. They are the only way to measure false positives honestly.
- **Subtle attacks are included:** small and slow-ramp false data with no network trace. Report where detection fails.
- **Look-alike pairs:** planned switching vs unauthorised trip, and stuck breaker vs unauthorised trip, test whether the system reasons about authorisation rather than only about physics.
- **Datasets:** the simulator generates labelled runs. SWaT and WADI require an access request and are water-focused; for a public power-system dataset consider freely available options and keep results labelled by source.
- **Determinism:** fixed random seeds make every run repeatable.

---

## 22. Buildathon Differentiation

A basic project might say: *"Our model detects industrial cyberattacks with high accuracy."*

ARMOUR LABS demonstrates a complete cyber-physical incident:

```text
NORMAL OPERATION -> SIMULATED ATTACK -> NETWORK / PROCESS ANOMALY -> AI DETECTION
-> EVIDENCE-BASED EXPLANATION -> AFFECTED FEEDERS -> SIMULATED CONTAINMENT
-> RECOVERY VERIFICATION
```

Compared with commercial ICS monitoring tools (for example Dragos, Claroty, Nozomi), the focus is twin-based expected-state comparison anchored on the authorised command log, a containment dry-run, and verified recovery. The strongest differentiators:

1. **Authorisation-aware twin:** the same physical event is judged differently depending on whether it was commanded.
2. **Cyber-physical correlation:** connect network events to power-flow behaviour.
3. **Look-alike handling:** planned switching, natural changes and faults do not raise false attack alerts.
4. **Attack propagation visualisation** that is understandable at a glance.
5. **Evidence-based explanation:** show why the system raised an alert.
6. **Safe response simulation** that restores the hospital first, without touching real equipment.
7. **Recovery verification:** prove the substation returned to defined limits.
8. **Incident replay:** let judges inspect the event sequence.

### MITRE ATT&CK for ICS mapping

| Scenario | Technique |
|---|---|
| Unauthorised breaker trip | T0855 Unauthorized Command Message |
| False data injection, replay, subtle variants | T0856 Spoof Reporting Message |
| Denial of service | T0814 Denial of Service |

---

## 23. Suggested 2–3 Minute Demo Script

**0:00–0:25 — Introduce the substation.** "This is ARMOUR LABS, protecting a campus microgrid with a hospital on one of its feeders. It watches the network and the physical power flows together." Show the healthy, animated substation.

**0:25–0:45 — Show the look-alike.** "Operators open breakers all the time." Start *Planned switching*. The campus feeder goes dark, and nothing is flagged, because the command was authorised.

**0:45–1:15 — Trigger an attack.** Reset, then start *Unauthorised breaker trip*. The hospital goes dark. Show the alert, the unauthorised command from 10.0.0.66, and the twin mismatch: same physical effect, but this one was never commanded.

**1:15–1:40 — Show impact.** The affected IED turns red on the network view; the callout shows the evidence; the battery absorbs the lost load.

**1:40–2:10 — Contain.** Approve containment. The source is blocked and the hospital breaker is reclosed first.

**2:10–2:40 — Verify recovery.** Show the checks passing and the status turning to Recovered only after the dwell time.

End with: **"ARMOUR LABS — Detect the attack. Understand the impact. Contain the threat. Verify recovery."**

---

## 24. Final Project Pitch

ARMOUR LABS is an AI-powered digital twin for power-grid cybersecurity. It monitors network activity, breaker commands, meter readings and physical power flows to identify suspicious activity and understand its impact on supply to critical loads such as hospitals.

Unlike traditional intrusion-detection systems that primarily flag unusual network traffic, ARMOUR LABS correlates cyber events with the physical behaviour of the substation. Its detection engine identifies anomalies, while its digital twin, anchored on the authorised command log, compares observed behaviour against what should be happening and tells planned work, faults and natural changes apart from attacks.

When a simulated attack occurs, ARMOUR LABS identifies affected feeders, presents the evidence behind the alert, visualises the impact, simulates a safe containment, and verifies that the substation has returned to acceptable operating conditions.

**DETECT → EXPLAIN → LOCALISE → CONTAIN → RECOVER → VERIFY**

---

## 25. Scope and Engineering Guardrails

- Treat the substation as a software simulation, not a real grid.
- Keep all attack scenarios inside the isolated simulator.
- Do not connect the prototype to real relays, SCADA or grid equipment.
- Do not claim that an anomaly proves malicious activity.
- Distinguish measured model outputs from illustrative UI values.
- Do not claim recovery until defined verification checks pass.
- Keep the LLM in the explanation role; use measurable detectors for detection.
- Prioritise one complete, reliable scenario over many incomplete ones.
- Record the dataset, preprocessing, split strategy, and evaluation metrics.
- Make the dashboard reflect live backend state rather than a disconnected animation.

**Recommended minimum viable build:** one simulated substation, the core scenarios plus the look-alikes, one evaluated ML detector, the independent twin, a live incident dashboard, one simulated containment workflow, and recovery verification.
