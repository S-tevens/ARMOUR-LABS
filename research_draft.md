# ARMOUR LABS: relation to prior research (draft)

This draft explains how ARMOUR LABS relates to the research paper that inspired it, what we took, what we changed, and how our results should and should not be read. All figures for our work come from `backend/evaluation/results.json` (the "Metrics" tab) and are measured on our own simulator.

## 1. The paper

D. Benka, D. Horváth, L. Špendla, G. Gašpar and M. Strémy, *Machine Learning-Based Detection of Anomalies, Intrusions, and Threats in Industrial Control Systems*, IEEE Access, vol. 13, pp. 12502-12514, 2025. DOI: [10.1109/ACCESS.2025.3530902](https://doi.org/10.1109/ACCESS.2025.3530902). Licensed CC BY 4.0. A copy is in [docs/research/benka-2025-ml-anomaly-detection-ics.pdf](docs/research/benka-2025-ml-anomaly-detection-ics.pdf).

### What the paper does
- **Setting:** lateral attacks between PLCs. Four real Siemens S7-300 PLCs on a managed switch; a sniffer on a mirrored port records the packets.
- **Data:** 10,000 captured packets, 70 % normal and 30 % attack, plus 100 packets for testing. Features are packet metadata, protocol information, payload content and traffic volume and timing.
- **Attacks injected:** replay, unauthorised data modification and command injection, and communication floods, including spoofed addresses and altered headers.
- **Models compared:** 1D CNN, LSTM, Isolation Forest and a linear SVM, with grid search over parameters.
- **Reported results (its Table 7):** 1D CNN testing accuracy 0.92 and F1 0.91; LSTM 0.75 and 0.77; Isolation Forest 0.70 and 0.68; SVM 0.52 and 0.51.
- **Its own caveats:** it calls for validation on real deployments, notes that labelled data is hard to obtain, and lists interpretability and adversarial robustness as open issues.

## 2. What we took from the paper

| Taken | How we used it |
|---|---|
| The idea that ML anomaly detection suits industrial control systems | It is one of our detection layers, not the whole system |
| The threat focus: attacks on PLC and relay communication | Our scenarios target the substation's IEDs and SCADA commands |
| The attack types (replay, unauthorised commands, data manipulation, floods) | Our scenarios include replay attack, unauthorised breaker trip, false data injection and DoS flood |
| Two model families: Isolation Forest and SVM | We trained Isolation Forest and a one-class SVM |
| Precision, recall and F1 instead of accuracy alone, because attack data is imbalanced | We report these and more (see section 4) |

## 3. What we did not take, and what we added

**Not taken:** the paper's 1D CNN and LSTM (we did not build or test them), its dataset, its hardware, its code, and its numbers.

**Added by us:**

1. **Grid telemetry, not only packets.** Our detectors use meter readings (frequency, voltage, import, solar, battery, breaker states) together with network events. We turn a 10-second window into 36 features.
2. **An independent digital twin.** It predicts the expected state from the authorised command log only, never from observed actuator states, so an attack's physical effect shows up as a residual instead of being predicted away.
3. **Physics checks.** Relations that must hold together (power balance, frequency band, voltage against import, breaker against load, solar against weather, stale updates). Tolerances are fitted from normal data and each alert explains itself in plain words.
4. **A different ML model.** A PCA autoencoder (reconstruction error) was chosen on separate validation runs. It is not one of the paper's four models.
5. **Attack versus fault separation.** Benign cases (planned switching, passing clouds) and faults (sensor drift, stuck breaker, inverter trip) are simulated, so false alarms can be measured and faults are not labelled as attacks.
6. **City layer.** A real Bengaluru grid from OpenStreetMap (hybrid of real, inferred and simulated data, each labelled) with power flow, protection trips, cascading failures, hospital backup timers, impact counters and priority restoration.
7. **Containment and recovery verification,** and replay of incidents from an append-only event log.
8. **A stricter evaluation** (section 4).

## 4. Our evaluation, and how it differs

- **Test set:** 39 simulated runs the models never trained on: 27 attack or fault runs, 6 normal-change runs and 6 normal runs at different demand levels, giving 5.85 hours of normal operation for counting false alarms.
- **Splits by run, not by packet.** Training, validation, model-selection and test seeds never overlap; a test enforces this.
- **Training uses no attacks or faults.** Only normal operation, harmless changes and different demand levels.
- **The model is chosen on validation runs,** separate from the test runs. The PCA autoencoder found 8 of 9 validation attacks with no false-alarm runs.
- **Fresh-seed check:** the same protocol on seeds never looked at during development. This is the cleaner estimate.
- **Alert rule:** a score of 0.8 or more for two seconds in a row. The first 10 seconds of each run are warm-up and are not scored.
- **Metrics:** precision, recall and F1 over every second, runs detected, median delay, false alarms per hour, and per-scenario results.

### Results on the fresh seeds (simulator data)

| Detector | Attacks and faults found (of 27) | False alarms per hour |
|---|---|---|
| Fixed limits (baseline) | 9 | 0 |
| Unauthorised-message rule | 12 | 0 |
| Digital twin | 21 | 0 |
| Physics checks | 21 | 0 |
| Isolation Forest | 0 | 0 |
| One-class SVM | 21 | 0.34 |
| Autoencoder, normal data only | 24 | 10.94 |
| PCA autoencoder (live ML model) | 24 | 0 |
| Combined (alert if any of: fixed limits, message rule, twin, physics checks, PCA autoencoder) | 27 | 0 |

Points worth stating plainly:
- Isolation Forest detected nothing in our setup. The paper also found it weaker than the CNN (accuracy 0.70).
- An autoencoder trained on normal data only raised about 11 false alarms per hour. Adding harmless changes and different demand levels to its training data removed them.
- No single detector finds everything; the combination does, which is the case for a layered design.

## 5. Why our numbers cannot be compared with the paper's

- Different data: its real captured packets against our simulated grid telemetry.
- Different task: classifying individual packets against detecting an attack within a running system.
- Different test size: 100 packets against 39 runs of 750 to 900 seconds.
- Different metrics and splits.

We therefore do not claim to beat or reproduce the paper's results.

## 6. Limitations

- **Simulator only.** The same simulator produces our training and test data. The results show that the pipeline works end to end, not how it would perform on a real grid or on a public dataset.
- **Simplified physics.** The physics checks and the autoencoder use relations the simulated plant follows almost exactly. Real data is noisier, tolerances would be wider and detection weaker.
- **Few runs.** Three runs per scenario, so detection rates are indicative and no confidence intervals are given.
- **The city grid is a hybrid.** OpenStreetMap maps only some substations, lines and facilities; most links between substations are inferred, and loads, ratings and all attacks are simulated. It is not BESCOM or KPTCL data.
- **Models not tried.** We did not test deep sequence models such as the paper's CNN and LSTM.

## 7. Short answer for reviewers

ARMOUR LABS is inspired by the paper, not built on it. We took the research direction, the attack types and two model families. We changed the problem from packet classification on a PLC network to detecting and explaining attacks on a power grid, using an independent digital twin, physics checks, ML on grid telemetry, a city-level impact model and recovery verification, and we evaluate it with a stricter protocol on our own simulator. We did not reuse the paper's data, code or results, and our numbers are not comparable to theirs.
