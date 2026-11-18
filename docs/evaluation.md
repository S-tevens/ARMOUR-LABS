# Detection and evaluation

How the detectors work and how they are measured. The numbers are in the **Metrics** tab and in `backend/evaluation/results.json`.

## The detectors

| Detector | What it looks at | Trained? |
|---|---|---|
| Fixed limits | Frequency, voltage and battery charge against engineering limits | No (baseline) |
| Unauthorised-message rule | A network message from a source that is not on the allow-list | No |
| Digital twin | Distance between the readings and the state the authorised command log predicts | No (fitted gains only) |
| Physics checks | Relations that must hold together: power balance, frequency band, voltage against import, breaker against load, solar against weather, stale updates. Tolerances are fitted from normal data | Tolerances only |
| ML detectors | A 10-second window of 36 features (readings, changes, network counts). Three families are trained: Isolation Forest, a linear autoencoder (PCA reconstruction error) and a one-class SVM | Yes, on normal and harmless data only |
| Combined | Any of limits, network, twin, physics checks or the chosen ML model | |

The ML models never see an attack or a fault during training. Only normal operation, harmless changes (planned switching, passing clouds) and different demand levels are used.

An alert needs a score of 0.8 or more for two seconds in a row. The first 10 seconds of every run are a warm-up and are not scored.

## The protocol

- **Run-based splits.** Training, validation, model selection and test runs use different random seeds. A test (`test_training_validation_selection_and_test_seeds_never_overlap`) checks there is no overlap.
- **Model choice on validation attack runs**, separate from the test runs.
- **Test set:** 39 runs (27 attack or fault runs, 6 normal-change runs, 6 normal runs at different demand levels), 5.85 hours of normal operation for false-alarm counting.
- **Fresh-seed check:** the same protocol on seeds never looked at while developing the detectors. It is the cleaner estimate and is shown first.
- **Metrics:** precision, recall and F1 over every second, runs detected, median delay, false alarms per hour, and per-scenario results. Accuracy alone is not reported.

## What the numbers do and do not show

They are measured on this project's own simulator, so they show the pipeline works end to end, not how it would do on a real grid. The limits are listed in the Metrics tab and in the `limitations` field of the results. Notable ones:

- The physics checks and the autoencoder use relations the simulated plant follows almost exactly. Real data is noisier.
- Three runs per scenario: rates are indicative, with no confidence intervals.
- Isolation Forest detected nothing in this setup, and is reported as such.
- An autoencoder trained on normal data only (no harmless changes) raises many false alarms. That is shown as its own row.

## Running it

- Results are served by `GET /metrics`. `POST /metrics/run` recomputes them in the background (about 30 seconds) and writes `backend/evaluation/results.json`.
- From the command line: `cd backend && python -m evaluation.run`.
- The models train when the backend starts (about 10 seconds). Set `ARMOUR_ML=0` to skip this; the live ML and physics scores then stay at 0.
