# ARMOUR LABS
## AI-Powered Digital Twin for Industrial Cyberattack Detection, Explanation, and Recovery

> **Project tagline:** Detect the attack. Understand the impact. Contain the threat. Verify recovery.

---

## 1. Project Overview

**ARMOUR LABS** is an AI-powered cyber-physical security platform for Industrial Control Systems (ICS). It creates a live digital twin of a simulated industrial facility and monitors its network activity, PLC commands, sensor telemetry, and physical process behaviour.

Machine-learning models detect suspicious patterns. A digital twin independently estimates how the industrial process should behave under normal conditions. ARMOUR LABS compares observed behaviour with these expected states to identify cyber-physical inconsistencies, assess their impact, and help operators investigate incidents.

When a simulated attack occurs, ARMOUR LABS aims to:

1. Detect abnormal network, command, or process behaviour.
2. Identify the affected device and industrial process.
3. Explain the evidence behind the alert.
4. Visualise how the incident propagates through the plant.
5. Recommend or simulate safe containment actions.
6. Verify whether the plant has returned to an acceptable operating state.

Unlike a conventional intrusion-detection dashboard that primarily displays alerts, ARMOUR LABS connects a cyber event to its potential physical consequences.

### Research foundation

The project takes inspiration from:

**“Machine Learning-Based Detection of Anomalies, Intrusions, and Threats in Industrial Control Systems” — IEEE Access, 2025.** *(TODO: add authors and DOI before submission.)*

The paper explores machine-learning approaches such as CNN, LSTM, SVM, and Isolation Forest for detecting anomalies and threats in industrial control systems. ARMOUR LABS uses this research direction as a foundation and extends the concept with a simulated industrial digital twin, cross-layer event correlation, visual incident investigation, and recovery verification.

*The implementation should independently validate its models and results. Any accuracy or F1 score reported by the paper must not be presented as a result achieved by ARMOUR LABS.*

---

## 2. Problem Statement

Industrial Control Systems operate critical infrastructure, including:

- Water and wastewater treatment plants
- Power generation and distribution facilities
- Manufacturing plants
- Oil and gas facilities
- Chemical processing facilities
- Smart factories

A cyberattack on an ICS can affect more than computers or network traffic. An unauthorised PLC command or manipulated sensor reading can change the behaviour of pumps, valves, motors, pressure systems, and production processes.

A conventional alert may indicate that network traffic is unusual, but an operator still needs to determine:

- Which device or process is affected?
- What physical consequences could follow?
- Is the anomaly caused by a cyberattack, equipment fault, sensor failure, or normal operating change?
- How did the event propagate through the plant?
- What response is appropriate?
- Has the process actually recovered after mitigation?

ARMOUR LABS addresses these questions by correlating network events, controller commands, sensor readings, process behaviour, and digital-twin predictions.

---

## 3. Proposed Demonstration Environment

### Why a water-treatment plant?

The initial prototype will simulate a small water-treatment facility. It is a useful buildathon environment because its components and process flow are easy to understand visually.

The simulated plant can contain:

- Raw-water and clean-water tanks
- Pumps
- Filters
- Valves
- Flow sensors
- Pressure sensors
- Temperature sensors
- Tank-level sensors
- PLCs
- A SCADA workstation
- A segmented industrial network

A simplified process flow:

```text
RAW WATER
    |
    v
+-----------+
|  TANK 1   |
+-----+-----+
      |
      v
    PUMP 1
      |
      v
   FILTER
      |
      v
    VALVE 1
      |
      v
+-----------+
|  TANK 2   |
+-----+-----+
      |
      v
    PUMP 2
      |
      v
 CLEAN WATER
```

The simulator continuously updates tank levels, flow, pressure, temperature, pump states, valve states, and controller states.

The plant is simulated entirely in software. No real industrial equipment or production network is required.

---

## 4. Main System Components

ARMOUR LABS is organised into seven components:

1. **Industrial Process Simulator** — models the plant and generates normal operating telemetry.
2. **ICS Network Simulator** — represents SCADA, PLCs, sensors, actuators, and their communication.
3. **Attack Scenario Engine** — injects controlled attack scenarios into the isolated simulation.
4. **ML Detection Engine** — detects suspicious network and process behaviour.
5. **Digital Twin** — predicts expected process behaviour and calculates deviations.
6. **Incident Intelligence Engine** — correlates evidence, identifies likely causes, and explains alerts.
7. **Response and Visualisation Layer** — presents incidents, simulates containment, and verifies recovery.

### High-level architecture

```text
             INDUSTRIAL PLANT SIMULATOR
                         |
              Sensors, PLCs, Actuators
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
            Expected vs. Observed State
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

## 5. Industrial Process Simulator

The process simulator models how the plant behaves over time.

It maintains a state for each component. For example:

```text
Tank 1 level:       62%
Tank 2 level:       48%
Pressure:           2.1 bar
Flow rate:          110 L/min
Temperature:        27 °C
Pump 1:             ON
Valve 1:            OPEN
PLC-01:             NORMAL
```

The simulator applies simplified process rules. For example:

- A running pump increases downstream flow.
- Opening a valve changes flow through a pipe.
- Tank levels rise or fall depending on inflow and outflow.
- Pressure changes in response to flow restrictions and pump behaviour.
- Sensor values include small, realistic variations.

The simulator should produce a timestamped telemetry stream that can be consumed by the detection engine and dashboard.

**Implementation note:** Begin with a deterministic, understandable process model. Add noise and more complex dynamics only after the basic system is reliable.

---

## 6. ICS Network Simulation

The network simulator represents the relationships between industrial devices.

Example topology:

```text
                  EXTERNAL NETWORK
                         |
                      FIREWALL
                         |
                       SCADA
                         |
             +-----------+-----------+
             |           |           |
           PLC-01      PLC-02      PLC-03
             |           |           |
        PUMP 1 / 2     VALVE 1    SENSORS
                                (flow, pressure,
                                 temperature, levels)
```

Mapping used throughout this document: PLC-01 drives Pump 1 and Pump 2; PLC-02 drives Valve 1; PLC-03 reads all sensors. PLCs receive commands from SCADA and drive actuators; they do not issue commands themselves.

Each device has a state:

- **Green — Normal**
- **Yellow — Suspicious**
- **Red — Confirmed or simulated compromise**

The dashboard displays the topology and highlights the source, target, and affected components when an incident occurs.

For the prototype, network events can be generated as structured records rather than requiring a real industrial network. This keeps the demonstration safe, reproducible, and easy to test.

---

## 7. Attack Scenario Engine

The attack engine allows a presenter or evaluator to trigger controlled scenarios inside the simulation.

### Initial scenarios

| Scenario | What the simulation changes | What ARMOUR LABS should detect |
|---|---|---|
| False data injection | A sensor reports a manipulated value | Sensor inconsistency and process deviation |
| Unauthorised PLC command | A controller receives an unexpected command | Command and state-transition anomaly |
| Sensor spoofing | A sensor value is altered to misrepresent the plant | Disagreement between related sensors and twin |
| Replay simulation | An old command or telemetry sequence is replayed | Repeated or stale event patterns |
| Denial-of-service simulation | A simulated device receives excessive requests or misses updates | Traffic-rate or availability anomaly |

All attack scenarios must remain inside the project's isolated software simulation. Do not target real PLCs, industrial networks, or external systems.

### Example: unauthorised valve command

Normal state:

```text
Valve 1 = OPEN
Pressure = 2.1 bar
Flow = 110 L/min
```

Simulated incident:

```text
Unauthorised write to PLC-02: VALVE 1 = CLOSE (source not SCADA)
Observed pressure: 4.8 bar   (pump pushing against a closed valve)
Observed flow: 12 L/min
```

Physics note: closing a valve downstream of a running pump raises upstream pressure and collapses flow, and Tank 1 risks overflowing. (Opening a valve would normally lower pressure, so it is not used as the main example.)

The simulator changes the process state according to its rules. ARMOUR LABS receives the resulting network events and telemetry and attempts to detect and explain the incident.

---

## 8. Machine-Learning Detection Engine

The ML layer is inspired by the candidate approaches in the IEEE research paper.

### Candidate models

- **1D CNN:** learns local patterns in time-windowed telemetry or network features.
- **LSTM:** models temporal sequences and changes in system behaviour.
- **Support Vector Machine (SVM):** provides a supervised classification baseline.
- **Isolation Forest:** detects unusual observations when labelled attack examples are limited.

Do not assume that all four models are necessary. Start with a strong baseline and add complexity only when it improves measured performance.

### Detection streams

**A. Network behaviour**

Potential features:

- Event or packet rate
- Source and destination device
- Protocol or message type
- Connection frequency
- Command frequency
- Failed or unexpected communication
- Timing and sequence patterns

**B. Process telemetry**

Potential features:

- Pressure
- Flow rate
- Temperature
- Tank level
- Pump state
- Valve state
- Rate of change of sensor readings

**C. Controller behaviour**

Potential features:

- Command type
- Command source
- Expected state transition
- Command frequency
- Whether a command is valid in the current operating state

### Evidence fusion

The system combines evidence from multiple detectors rather than trusting one model in isolation.

Illustrative output:

```text
Network anomaly score:       0.91
Controller anomaly score:    0.87
Process anomaly score:       0.94
Digital-twin residual score: 0.96
```

These are example values for illustrating the interface, not measured project results. The team must define and validate the score-normalisation and fusion method.

---

## 9. Digital Twin and Expected-State Comparison

The digital twin is a central differentiator.

It maintains a virtual representation of the plant and estimates what the process should look like under the current operating conditions.

For each time step, ARMOUR LABS compares:

- **Expected state:** the state predicted by the process model.
- **Observed state:** the state reported by the simulated sensors and controllers.

Example:

| Variable | Expected | Observed | Interpretation |
|---|---:|---:|---|
| Pressure | 2.2 bar | 4.8 bar | Large deviation |
| Flow | 112 L/min | 12 L/min | Large deviation |
| Valve 1 | Open | Closed | State mismatch |
| Temperature | 27 °C | 27 °C | No notable deviation |

A residual is the difference between an observed value and its expected value. For a numeric variable:

```text
Residual = Observed value - Expected value
```

Residuals should be normalised using suitable operating ranges or historical variability so that measurements with different units can be compared.

A large residual is evidence of unexpected behaviour, not proof of a cyberattack. ARMOUR LABS must correlate it with network and controller evidence before assigning a likely cause.

---

## 10. Distinguishing Cyberattacks from Equipment or Sensor Faults

An important project objective is to avoid treating every abnormal reading as a cyberattack.

For example, if pressure rises unexpectedly, possible causes include:

- A faulty pressure sensor
- A pump malfunction
- A stuck valve
- An incorrect but legitimate operator command
- A simulated cyberattack

ARMOUR LABS should correlate evidence across layers.

| Evidence | Possible interpretation |
|---|---|
| Sensor value changes, related sensors remain stable | Possible sensor fault or spoofing |
| Pump state and flow disagree | Possible actuator or equipment issue |
| Unexpected command precedes process change | Possible unauthorised command |
| Unusual network activity and invalid command occur together | Stronger cyberattack evidence |
| Process deviates without suspicious network or command activity | Possible physical fault or model mismatch |

The system should present a **likely cause with supporting evidence and uncertainty**, not claim certainty where the data cannot support it.

---

## 11. Explainable AI and Incident Explanation

When an alert is raised, ARMOUR LABS should show the evidence behind it.

Example interface:

```text
INCIDENT: UNAUTHORISED VALVE COMMAND
Affected device: PLC-02 (controls Valve 1)
Severity: HIGH

Evidence:
- Unexpected command received from a non-SCADA source
- Valve state changed outside expected sequence
- Pressure exceeded its normal operating range
- Flow deviated from the digital-twin prediction
- Related network activity was unusual
```

Feature-importance methods such as SHAP may be used where appropriate for the selected model. For simpler detectors, show direct evidence such as residuals, thresholds, and the events that triggered the alert.

A natural-language explanation can be generated from structured detection results:

> PLC-02 received a valve-close command from a source other than SCADA that was not expected in the current operating state. The valve state changed, followed by pressure and flow deviations from the digital-twin prediction. The combined evidence indicates a likely controller-related security incident.

The explanation layer must not invent evidence or make unsupported claims. It should use the actual alert fields and measurements produced by the detection system.

---

## 12. Root-Cause and Impact Visualisation

ARMOUR LABS displays a causal or event-propagation view that connects the incident to affected plant components.

Example:

```text
SIMULATED SECURITY INCIDENT
             |
             v
     PLC-02 command
             |
             v
       Valve 1 closes
             |
        +----+----+
        |         |
        v         v
   Flow drops  Pressure rises
        |         |
        +----+----+
             |
             v
      Tank instability
             |
             v
       Plant risk
```

The visualisation should distinguish:

- Directly observed events
- Correlated evidence
- Inferred causal relationships

This distinction is important: a sequence of correlated events does not automatically prove causation.

---

## 13. Response and Containment

After an incident is identified, ARMOUR LABS presents a response plan.

Example:

1. Flag the affected controller.
2. Reject the suspicious command in the simulation.
3. Place the affected subsystem into a predefined safe state.
4. Apply the simulated recovery procedure.
5. Continue monitoring telemetry and network events.

The buildathon prototype should use **simulated containment**, not send commands to real industrial equipment.

The operator should be able to inspect and approve the proposed response. This makes the demonstration safer and communicates that real industrial response requires engineering validation and operational safeguards.

---

## 14. Recovery Verification

A successful response is not simply an alert disappearing. ARMOUR LABS checks whether the simulated plant has returned to acceptable operating limits.

Example:

| Variable | During incident | After simulated recovery |
|---|---:|---:|
| Pressure | 4.8 bar | 2.2 bar |
| Flow | 12 L/min | 110 L/min |
| Valve 1 | Closed | Open |
| Tank 1 level | 82% | 64% |
| Network anomaly | High | Normal |

The digital twin checks whether observed process values are again within defined tolerances.

Possible final states:

- **Recovered:** monitored values are within acceptable limits.
- **Recovering:** values are moving towards acceptable limits.
- **Unresolved:** one or more important deviations remain.

The dashboard should only display “Recovered” when the verification conditions are actually satisfied.

---

## 15. Incident Timeline and Replay

Every simulated incident should be recorded as a sequence of timestamped events.

Example:

```text
10:42:01  Plant operating normally
10:42:04  Unexpected PLC command generated
10:42:06  Valve state changes
10:42:07  Process anomaly detected
10:42:08  Network and process evidence correlated
10:42:09  Incident classified
10:42:10  Simulated containment begins
10:42:11  Recovery checks pass
```

The dashboard should support incident replay so judges can rewind and inspect how the event unfolded.

Replay should use recorded events and timestamps, not a fabricated sequence.

---

## 16. AI Investigation Assistant

An optional LLM-based assistant can let an operator ask questions about an incident.

Example questions:

- Why was PLC-02 flagged?
- Which process variables changed?
- What evidence supports the incident classification?
- Which components were affected?
- What response is recommended?
- Has recovery been verified?

The LLM is **not the primary attack detector**. ML models and deterministic process checks produce the detection evidence. The LLM converts those structured results into readable explanations and answers.

---

## 17. Visual Dashboard: How ARMOUR LABS Should Stand Out

The dashboard is a major part of the buildathon experience. It should feel like an industrial security operations centre connected to a live digital twin, rather than a generic admin template.

### Main dashboard layout

**A. Live plant view — visual centrepiece**

Show the water-treatment process with animated:

- Water flow through pipes
- Tank fill levels
- Pump states
- Valve positions
- Sensor readings
- Device health indicators

**B. Threat monitor**

Show:

- Current security status
- Active incident count
- Detection scores
- Affected device
- Severity and confidence
- Recent alerts

**C. Network topology**

Show SCADA, PLCs, sensors, and actuators as connected nodes. Highlight the source and propagation path of an incident.

**D. Digital-twin comparison**

Show expected versus observed values, residuals, and acceptable operating ranges.

**E. Incident investigation**

Show the timeline, evidence, affected components, and likely root cause.

**F. Response and recovery**

Show proposed actions, simulated action status, and recovery verification.

### Visual design direction

- Dark charcoal or deep navy background
- Green for healthy operation
- Amber for suspicious behaviour
- Red for active incidents
- Blue for water/process flow
- Clear typography and strong visual hierarchy
- Smooth but restrained animations
- Large, readable metrics
- Consistent component states
- No clutter or decorative graphs without meaning

### Suggested screen structure

```text
+------------------------------------------------------------------+
| ARMOUR LABS                         SYSTEM STATUS: NORMAL              |
+-------------------------------+----------------------------------+
|                               |                                  |
|       LIVE PLANT VIEW         |       THREAT MONITOR              |
|                               |                                  |
|  Tank -> Pump -> Filter       |  Current threat level             |
|       -> Valve -> Tank        |  Network anomaly                  |
|                               |  Process anomaly                  |
|  Animated process flow        |  Active incidents                 |
|                               |                                  |
+-------------------------------+----------------------------------+
|                               |                                  |
|       NETWORK TOPOLOGY        |       DIGITAL TWIN               |
|                               |                                  |
|  SCADA -- PLC-01              |  Variable  Expected  Observed     |
|       |-- PLC-02              |  Pressure  ...       ...          |
|       |-- PLC-03              |  Flow      ...       ...          |
|                               |  Valve     ...       ...          |
+-------------------------------+----------------------------------+
|                         INCIDENT TIMELINE                         |
+------------------------------------------------------------------+
| Evidence | Root Cause | Response Plan | Recovery Verification    |
+------------------------------------------------------------------+
```

### The visual “wow” moment

The most important demo sequence is:

1. Start with a healthy, animated plant.
2. Select a simulated attack scenario.
3. Trigger the attack.
4. Highlight the affected PLC and network path.
5. Show the physical process reacting.
6. Display the digital-twin mismatch.
7. Reveal the detection evidence and explanation.
8. Show the incident propagation graph.
9. Run simulated containment.
10. Show the process returning to acceptable limits.
11. Display recovery verification.

The visual change should be driven by the actual simulation state and detection events. Avoid simply playing a pre-rendered animation that is disconnected from the backend.

---

## 18. Suggested Technology Stack

| Layer | Suggested technology | Purpose |
|---|---|---|
| Frontend | React + TypeScript | Main application |
| Plant visualisation | SVG/Canvas; optionally Three.js | Animated industrial process |
| Charts | Recharts or equivalent | Telemetry and model metrics |
| Backend | Python + FastAPI | APIs and orchestration |
| Real-time updates | WebSockets | Stream telemetry and alerts |
| ML | PyTorch, scikit-learn | Detection models |
| Data processing | NumPy, Pandas | Feature engineering |
| Database | SQLite (append-only event log; PostgreSQL optional later) | Incidents, events, telemetry, replay |
| Simulation | Custom Python simulator | Plant dynamics and attack scenarios |

**Implementation recommendation:** Start with a polished 2D SVG/Canvas plant. Add 3D only if the core simulator, detection, and incident flow are already working. A coherent, responsive 2D visualisation is better than an unfinished 3D environment.

---

## 19. Team Division (5–6 Members)

| Member | Responsibility | Deliverables |
|---|---|---|
| 1 | Industrial simulation | Plant state, process rules, telemetry generator |
| 2 | Machine learning | Dataset preparation, baselines, training, evaluation |
| 3 | Cybersecurity and attack engine | Network events, attack scenarios, incident injection |
| 4 | Digital twin | Expected-state model, residuals, recovery checks |
| 5 | Frontend and visualisation | Plant animation, topology, dashboard, replay UI |
| 6 (if available) | Integration and incident intelligence | API integration, explanation layer, testing, demo |

For a five-person team, combine integration and incident intelligence with the backend or frontend role, depending on each member’s strengths.

---

## 20. Implementation Roadmap

Build the project in stages. The first goal is a reliable end-to-end demonstration, not a large collection of disconnected features.

### Phase 1 — Working simulation

- Build the water-treatment process model.
- Define plant components and state transitions.
- Generate normal telemetry.
- Display the plant in a basic frontend.

**Milestone:** The plant runs normally and updates live.

### Phase 2 — Attack scenarios

- Implement at least two controlled attack scenarios.
- Record the injected events.
- Make the plant respond to the simulated attack.
- Display affected components.

**Milestone:** A judge can trigger an attack and see its impact.

### Phase 3 — Detection

- Prepare or select a suitable ICS dataset.
- Define features and labels.
- Train and evaluate a baseline detector.
- Add process anomaly checks.
- Stream detection results to the frontend.

**Milestone:** The system detects attacks or anomalies from actual generated input and reports measurable results.

### Phase 4 — Digital twin

- Implement expected-state predictions.
- Calculate residuals.
- Compare observed and expected telemetry.
- Define tolerances for normal operation.

**Milestone:** The dashboard shows meaningful expected-versus-observed differences.

### Phase 5 — Incident intelligence

- Correlate network, controller, and process evidence.
- Identify affected devices.
- Generate an evidence-based incident explanation.
- Display the incident propagation view.

**Milestone:** The system explains why an incident was raised.

### Phase 6 — Response and recovery

- Implement simulated containment actions.
- Define safe-state behaviour in the simulator.
- Verify process recovery.
- Record incident events for replay.

**Milestone:** The complete detect-to-recovery workflow works end to end.

### Phase 7 — Polish and evaluation

- Improve animations and layout.
- Test normal and attack scenarios.
- Measure precision, recall, F1, false-positive rate, and detection latency.
- Prepare a repeatable demo.
- Test the demo on the presentation machine.

**Milestone:** A stable, understandable, evidence-backed presentation.

---

## 21. Evaluation Metrics

Do not evaluate the project using accuracy alone. In an imbalanced cybersecurity dataset, accuracy can hide poor attack detection.

Report:

- Precision
- Recall
- F1 score
- False-positive rate
- Confusion matrix
- Detection latency
- Per-attack-type performance
- Recovery verification time

Also compare:

1. A simple threshold-based baseline.
2. One selected ML model.
3. The combined detection approach.

Use a clear train/test split. For time-series data, avoid random splitting that leaks adjacent time windows into both training and test sets.

Clearly label whether each result comes from a public dataset, the custom simulator, or both.

---

## 21A. Design Decisions Added After Review

**Digital-twin independence.** The twin must not be a copy of the simulator. It uses its own fitted, imperfect parameters. Its inputs are the *authorised* command log and schedule from SCADA, never the observed actuator states. Otherwise the twin would predict the attack's effect and residuals would vanish. The simulator adds sensor noise, demand disturbances, and slow drift so that normal residuals are non-zero and thresholds are meaningful.

**Physics-invariant checks (deterministic detector).** Mass balance (change in tank level ≈ inflow − outflow), pump ON ⇒ flow > 0, valve closed ⇒ downstream flow ≈ 0. These are cheap, explainable, and catch spoofed sensors that look normal while the process changes.

**Benign fault scenarios (required).** Include at least one non-attack case: sensor drift, a stuck valve, or a legitimate operator setpoint change. ARMOUR LABS must classify it as "likely physical fault or legitimate change", not an attack. This also gives an honest false-positive measurement.

**Network record schema.** Each event: `seq`, `timestamp`, `src`, `dst`, `function_code`, `register`, `value`. Replay is detected via duplicate or stale `seq`/`timestamp` or a command invalid in the current state. State what the simulated attacker can and cannot forge.

**Evidence fusion (MVP).** Normalise each detector score to [0,1] using its percentile on held-out normal data. Fuse with an explicit rule table (the Section 10 table made executable). Learned fusion is out of scope for the MVP.

**Recovery verification.** "Recovered" requires every monitored variable within its tolerance for N consecutive seconds (dwell time), to avoid flicker.

**Containment dry-run.** Before the operator approves a response, run it on the twin and show the predicted outcome, because a "safe state" can itself be unsafe (for example, closing a valve while a pump runs).

**MITRE ATT&CK for ICS mapping.** Unauthorised PLC command: T0855 Unauthorized Command Message. Sensor spoofing / false data injection: T0856 Spoof Reporting Message. Valve/pump manipulation: T0831 Manipulation of Control. DoS simulation: T0814 Denial of Service.

**Datasets.** SWaT/WADI require an access request. BATADAL or HAI are freely available. Use a public dataset for model credibility and the simulator for the live demo, labelling each result's source. Include subtle attacks (small-magnitude injection, slow ramps) and report failures honestly.

**Determinism and integration.** Fixed random seed and simulation clock; append-only SQLite event log doubles as the replay source. Agree telemetry, event, and alert JSON schemas on day 1. The LLM assistant and any 3D view are stretch goals.

---

## 22. Buildathon Differentiation

A basic project might say:

> Our model detects industrial cyberattacks with high accuracy.

ARMOUR LABS demonstrates a complete cyber-physical incident:

```text
NORMAL OPERATION
       |
       v
SIMULATED ATTACK
       |
       v
NETWORK / PROCESS ANOMALY
       |
       v
AI DETECTION
       |
       v
EVIDENCE-BASED EXPLANATION
       |
       v
AFFECTED COMPONENTS
       |
       v
SIMULATED CONTAINMENT
       |
       v
RECOVERY VERIFICATION
```

Compared with commercial ICS monitoring tools (e.g. Dragos, Claroty, Nozomi), the focus here is twin-based expected-state comparison, a containment dry-run, and verified recovery. The strongest differentiators are:

1. **Cyber-physical correlation:** connect network events to physical process behaviour.
2. **Digital-twin comparison:** show expected and observed process states.
3. **Attack propagation visualisation:** make the incident understandable at a glance.
4. **Evidence-based explanation:** show why the system raised an alert.
5. **Safe response simulation:** demonstrate containment without touching real equipment.
6. **Recovery verification:** prove that the simulated process returned to defined operating limits.
7. **Incident replay:** let judges inspect the event sequence.

---

## 23. Suggested 2–3 Minute Demo Script

### 0:00–0:25 — Introduce the plant

“This is ARMOUR LABS, a cyber-physical security platform for industrial control systems. We are showing it on a simulated water-treatment plant. It monitors the industrial network and the physical process together.”

Show the normal plant, telemetry, and network topology.

### 0:25–0:45 — Trigger an attack

“Let's simulate an unauthorised PLC command.”

Select the scenario and launch it.

Show the PLC event and the plant response.

### 0:45–1:15 — Detect and explain

Show the alert, anomaly scores, digital-twin residuals, and evidence.

Explain which device was affected and why the event is suspicious.

### 1:15–1:40 — Show impact

Reveal the incident path from the PLC command to the valve and the process deviations.

### 1:40–2:10 — Contain

Run the simulated response. Show the affected subsystem entering its predefined safe state.

### 2:10–2:40 — Verify recovery

Show expected and observed values returning within acceptable limits.

End with:

**“ARMOUR LABS — Detect the attack. Understand the impact. Contain the threat. Verify recovery.”**

---

## 24. Final Project Pitch

ARMOUR LABS is an AI-powered digital twin for industrial cybersecurity. It monitors network activity, PLC commands, sensor telemetry, and physical process behaviour to identify suspicious activity and understand its impact on industrial operations.

Unlike traditional intrusion-detection systems that primarily flag unusual network traffic, ARMOUR LABS correlates cyber events with the physical behaviour of the plant. Its machine-learning detection engine identifies anomalies, while its digital twin compares observed behaviour against expected process states.

When a simulated attack occurs, ARMOUR LABS identifies affected components, presents the evidence behind the alert, visualises how the incident affects the plant, recommends or simulates containment actions, and verifies whether the system has returned to acceptable operating conditions.

The project moves industrial cybersecurity beyond passive alerts towards an explainable, visual, and recovery-oriented cyber-physical defence workflow.

**DETECT → EXPLAIN → LOCALISE → CONTAIN → RECOVER → VERIFY**

---

## 25. Scope and Engineering Guardrails

To keep the project credible and achievable:

- Treat the water-treatment facility as a software simulation, not a real plant.
- Keep all attack scenarios inside the isolated simulator.
- Do not connect the prototype to production ICS equipment.
- Do not claim that an anomaly proves malicious activity.
- Distinguish measured model outputs from illustrative UI values.
- Do not claim recovery until defined verification checks pass.
- Keep the LLM in the explanation role; use measurable detectors for detection.
- Prioritise one complete, reliable scenario over five incomplete attack types.
- Record the dataset, preprocessing, split strategy, and evaluation metrics.
- Make the visual dashboard reflect live backend state rather than a disconnected animation.

**Recommended minimum viable build:** one simulated plant, two attack scenarios, one evaluated ML detector, a digital-twin residual check, a live incident dashboard, one simulated containment workflow, and recovery verification.

That is a much stronger foundation than attempting every feature at once.
