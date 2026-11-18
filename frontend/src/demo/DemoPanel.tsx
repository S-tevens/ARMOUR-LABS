import { getCityExplanation } from "../city/api";
import type { CityStream } from "../city/useCityStream";
import PlainWords from "../components/PlainWords";
import { STEPS, type Demo } from "./useDemo";

const DETECTOR = { network: "network rules", controller: "controller checks", process: "process limits", twin: "digital twin", ml: "machine learning", invariants: "physics checks" } as Record<string, string>;
const n = (v: number) => v.toLocaleString();

/** The narrated guide that sits over the City view while the demo runs. */
export default function DemoPanel({ demo, stream }: { demo: Demo; stream: CityStream }) {
  const { phase, stats, incident, error } = demo;
  if (phase === "idle") return null;
  const st = stream.state;
  const at = STEPS.findIndex((s) => s.id === phase);
  const fired = incident ? Object.entries(incident.scores).filter(([, v]) => v >= 0.8).map(([k]) => DETECTOR[k] ?? k) : [];
  const step = STEPS[at];

  let title = "Demo finished";
  let text: React.ReactNode = "";
  if (phase === "normal") {
    title = "1 · Normal operation";
    text = `All ${st?.districts.length ?? 37} substations are supplied and no detector is raising an alert. This is the calm before the attack.`;
  } else if (phase === "attack") {
    title = "2 · The attack";
    text = "An attacker opens the breakers of three central substations at once, the pattern of the 2015 Ukraine grid attack. The attack is simulated; nothing real is touched.";
  } else if (phase === "detect") {
    title = "3 · Detection";
    text = incident
      ? `Detected ${stats.detectS ?? "a few"} s after the attack and classified as: ${incident.classification}. ${fired.length ? "Alerts came from the " + fired.join(", ") + "." : ""}`
      : "Waiting for the detectors…";
  } else if (phase === "explain") {
    title = "4 · Explanation";
    text = "The incident is explained in plain words, next to the evidence it is built from.";
  } else if (phase === "contain") {
    title = "5 · Containment";
    text = "An operator approves a staged, simulated containment. Power is restored hospital first.";
  } else if (phase === "recover") {
    title = "6 · Verified recovery";
    text = "Recovery only counts once the grid stays inside its normal limits for a set time. These are the checks it is waiting on.";
  } else {
    text = error ? error : "Here is what happened, start to finish.";
  }

  return (
    <aside className="demo glass" role="region" aria-label="Guided demo" aria-live="polite">
      <ol className="demo-steps" aria-label="Demo progress">
        {STEPS.map((s, k) => (
          <li key={s.id} className={phase === "done" ? "done" : k < at ? "done" : k === at ? "now" : ""}>{s.label}</li>
        ))}
      </ol>

      <h3>{title}</h3>
      <p className="demo-text">{text}</p>

      {st && phase !== "normal" && phase !== "done" && (
        <div className="demo-chips">
          <span><b>{n(st.impact.people_unserved)}</b> people without power</span>
          <span><b>{st.impact.hospitals_on_backup + st.impact.hospitals_down}</b> hospitals affected</span>
          <span><b>{st.impact.restoration_pct}%</b> restored</span>
        </div>
      )}

      {phase === "explain" && incident && (
        <>
          <PlainWords incident={incident} load={getCityExplanation} />
          <ul className="demo-evidence">
            {incident.evidence.slice(0, 3).map((e, k) => <li key={k}><span className={`tag ${e.tag}`}>{e.tag}</span>{e.text}</li>)}
          </ul>
        </>
      )}

      {phase === "contain" && st && st.actions.length > 0 && (
        <ul className="demo-evidence">{st.actions.slice(-3).map((a, k) => <li key={k}>{a}</li>)}</ul>
      )}

      {phase === "recover" && st && (
        <>
          <ul className="demo-checks">
            {st.recovery.checks.map((c) => <li key={c.name} className={c.ok ? "ok" : ""}><i aria-hidden="true">{c.ok ? "✓" : "…"}</i>{c.detail || c.name}</li>)}
          </ul>
          <p className="muted small">In range for {Math.round(st.recovery.seconds_in_range)} of {st.recovery.dwell} s needed.</p>
        </>
      )}

      {phase === "done" && !error && (
        <ul className="demo-summary">
          <li><b>{n(stats.peakUnserved)}</b> people lost power at the peak</li>
          <li><b>{stats.peakBackup + stats.peakDown}</b> hospitals affected (on backup or down)</li>
          <li>Detected <b>{stats.detectS ?? "?"} s</b> after the attack; power restored and verified <b>{stats.restoreS ?? "?"} s</b> after containment was approved (simulated time)</li>
        </ul>
      )}
      {phase === "done" && <p className="muted small">Everything shown is simulated. Loads, ratings and the attack are not utility data.</p>}

      <div className="demo-controls">
        {phase !== "done" ? (
          <>
            <button className="btn" onClick={demo.togglePause}>{demo.paused ? "Resume" : "Pause"}</button>
            <button className="btn" onClick={demo.next} disabled={demo.paused}>Next step{step && demo.secondsLeft > 0 ? ` (${demo.secondsLeft})` : ""}</button>
            <button className="btn quiet" onClick={demo.stop}>Stop</button>
          </>
        ) : (
          <>
            <button className="btn primary" onClick={demo.start}>Run again</button>
            <button className="btn quiet" onClick={demo.stop}>Close</button>
          </>
        )}
      </div>
    </aside>
  );
}
