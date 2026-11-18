# Guided demo

The **Guided demo** button (top right) runs the whole story on the city grid, narrated step by step, in about two minutes:

| Step | What happens |
|---|---|
| 1 Normal | The city is reset and shown calm: every substation supplied, no alerts |
| 2 Attack | The *coordinated substation trip* scenario starts: three central substations are opened at once (the pattern of the 2015 Ukraine attack) |
| 3 Detect | The incident appears; the panel shows how fast it was detected, how it was classified and which detectors raised the alert |
| 4 Explain | The "In plain words" summary (Gemini if a key is set, otherwise the template) with the first pieces of evidence |
| 5 Contain | The demo approves the staged, simulated containment for the operator; power is restored hospital first |
| 6 Recover | The recovery checks are shown until the grid has stayed in range for the required time |

Finally a summary card shows the peak impact (people without power, hospitals affected), the detection time and the time from approval to verified recovery, all in simulated time.

## Controls

- **Pause / Resume** freezes the timers.
- **Next step** skips the minimum reading time of the current step (it still waits for the system to be ready, for example for the incident to appear).
- **Stop** closes the guide and leaves the simulation as it is. **Run again** replays it.

## Notes

- The demo only uses the normal API (`/city/scenario/stop`, `/city/scenario/start`, `/city/incident/{id}/approve-response`); it adds nothing to the backend.
- It **resets the city and its incidents** when it starts.
- If a step does not complete within 75 seconds (for example the backend stopped), the demo ends and says so.
- The times shown are simulated seconds. Every figure is simulated; none is utility data.
- For the Gemini summary in step 4, start the backend with `GEMINI_API_KEY` set (see [explanations.md](explanations.md)). Without it the template text is shown.
