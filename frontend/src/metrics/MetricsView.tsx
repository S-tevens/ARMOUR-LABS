import { useCallback, useEffect, useRef, useState } from "react";
import { getMetrics, runMetrics } from "../api";
import type { Block, Detector, Metrics } from "./types";

const pct = (v: number) => `${Math.round(v * 100)}%`;
const secs = (v: number | null) => (v == null ? "never" : `${v < 10 ? v.toFixed(1) : Math.round(v)} s`);
const KIND: Record<string, string> = { attack: "Attack", fault: "Fault", benign: "Normal change" };

function Cell({ found, total, benign }: { found: number; total: number; benign: boolean }) {
  // For attacks and faults a high count is good; for normal changes any count is a false alarm.
  const cls = benign ? (found === 0 ? "m-good" : "m-bad") : found === total ? "m-good" : found === 0 ? "m-bad" : "m-mid";
  return <td className={`m-cell ${cls}`}>{benign ? (found === 0 ? "quiet" : `${found}/${total} alarmed`) : `${found}/${total}`}</td>;
}

function Confusion({ d, hours }: { d: Detector; hours: number }) {
  const t = d.tick;
  const box = (n: number, title: string, sub: string, good: boolean) => (
    <div className={`conf-box ${good ? "m-good" : "m-bad"}`}>
      <b>{n.toLocaleString()}</b>
      <span>{title}</span>
      <small>{sub}</small>
    </div>
  );
  return (
    <div className="conf">
      {box(t.tp, "Attack seconds caught", "alert while something was wrong", true)}
      {box(t.fn, "Attack seconds missed", "no alert while something was wrong", t.fn === 0)}
      {box(t.fp, "False alarm seconds", `alert during normal operation (${hours.toFixed(1)} h tested)`, t.fp === 0)}
      {box(t.tn, "Quiet seconds", "no alert during normal operation", true)}
    </div>
  );
}

export default function MetricsView() {
  const [m, setM] = useState<Metrics | null>(null);
  const [last, setLast] = useState<Metrics | null>(null); // last results, kept on screen while a new run is going
  const [err, setErr] = useState<string | null>(null);
  const [which, setWhich] = useState<"fresh" | "main">("fresh");
  const [pick, setPick] = useState("pca");
  const timer = useRef<number | undefined>(undefined);

  const load = useCallback(async () => {
    try {
      const r = await getMetrics();
      setM(r);
      setErr(null);
      if (r.status === "ok") setLast(r);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not reach the backend");
    }
  }, []);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (m?.status !== "running") return;
    timer.current = window.setInterval(() => void load(), 1500);
    return () => window.clearInterval(timer.current);
  }, [m?.status, load]);

  const run = async () => {
    try { await runMetrics(); } catch (e) { setErr(e instanceof Error ? e.message : "Could not start"); return; }
    void load();
  };

  const data = last;
  const block: Block | undefined = data ? (which === "fresh" && data.fresh_check ? data.fresh_check : (data as Block)) : undefined;
  const live = data?.training?.selected_model;
  const running = m?.status === "running";
  const picked = block ? block.detectors.find((x) => x.key === pick) ?? block.detectors[0] : undefined;

  return (
    <main className="stack metrics">
      <section className="glass m-head">
        <div>
          <h2>How well does detection work?</h2>
          <p className="muted">
            Every detector was tested on the same {block?.protocol?.test_runs ?? 39} simulated runs it never trained on.
            Source: custom simulator, not a public dataset or real grid data.
          </p>
        </div>
        <div className="m-actions">
          <button className="btn" onClick={run} disabled={running}>{running ? "Running…" : "Run evaluation"}</button>
          <span className="muted small">
            {running
              ? `Working: ${m?.progress ?? "starting"} (${m?.elapsed_s ?? 0} s)`
              : data?.generated_at ? `Last run ${new Date(data.generated_at).toLocaleString()} · ${data.duration_s} s` : ""}
          </span>
        </div>
      </section>

      {err && <div className="error">Could not load results: {err}. Is the backend running?</div>}
      {m?.status === "error" && <div className="error">The last evaluation failed: {m.error}</div>}
      {m?.status === "not_computed" && !data && (
        <p className="empty glass">No results yet. Press “Run evaluation” (about 30 seconds) or run <code>python -m evaluation.run</code>.</p>
      )}

      {data && block && (
        <>
          <div className="seg" role="group" aria-label="Test set">
            <button className={which === "fresh" ? "on" : ""} onClick={() => setWhich("fresh")} disabled={!data.fresh_check}>Fresh seeds (cleaner estimate)</button>
            <button className={which === "main" ? "on" : ""} onClick={() => setWhich("main")}>Development test set</button>
          </div>
          {block.note && <p className="muted small">{block.note}</p>}

          <section className="glass m-card">
            <header className="panel-head">
              <h2>Detector comparison</h2>
              <span className="muted small">
                {block.protocol.attack_or_fault_runs} attack and fault runs · {block.protocol.benign_runs} normal-change runs · {block.protocol.negative_hours.toFixed(1)} h of normal operation
              </span>
            </header>
            <div className="m-scroll">
              <table className="m-table">
                <thead>
                  <tr><th>Detector</th><th>Attacks and faults found</th><th>Typical delay</th><th>False alarms per hour</th><th>Precision</th><th>Recall</th><th>F1</th></tr>
                </thead>
                <tbody>
                  {block.detectors.map((d) => (
                    <tr key={d.key} className={`${d.key === live ? "live" : ""} ${d.key === "combined" ? "combo" : ""}`} onClick={() => setPick(d.key)}>
                      <td>
                        <b>{d.label}</b>{d.key === live && <em className="tag">live ML</em>}
                        <small>{d.description}</small>
                      </td>
                      <td>
                        <div className="bar"><i style={{ width: pct(d.runs.rate) }} /></div>
                        <span>{d.runs.detected} of {d.runs.total} ({pct(d.runs.rate)})</span>
                      </td>
                      <td>{secs(d.runs.median_delay_s)}</td>
                      <td className={d.false_alarms.per_hour > 0 ? "m-bad-text" : ""}>{d.false_alarms.per_hour.toFixed(2)}</td>
                      <td>{pct(d.tick.precision)}</td>
                      <td>{pct(d.tick.recall)}</td>
                      <td>{d.tick.f1.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted small">
              An alert needs a score of 0.8 or more for two seconds in a row. Precision, recall and F1 count every second of every run. Click a row to see its counts below.
            </p>
          </section>

          <section className="glass m-card">
            <header className="panel-head">
              <h2>What each detector catches</h2>
              <span className="muted small">Runs detected per scenario. Normal changes should stay quiet.</span>
            </header>
            <div className="m-scroll">
              <table className="m-table matrix">
                <thead>
                  <tr><th>Scenario</th>{block.detectors.map((d) => <th key={d.key}>{d.label}</th>)}</tr>
                </thead>
                <tbody>
                  {block.scenarios.map((s) => (
                    <tr key={s.name}>
                      <td><b>{s.label}</b><small>{KIND[s.kind] ?? s.kind}</small></td>
                      {block.detectors.map((d) => {
                        const c = s.per_detector[d.key];
                        return c ? <Cell key={d.key} found={c.detected} total={c.runs} benign={s.kind === "benign"} /> : <td key={d.key} />;
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {picked && (
            <section className="glass m-card">
              <header className="panel-head">
                <h2>Counts for one detector</h2>
                <select value={picked.key} onChange={(e) => setPick(e.target.value)} aria-label="Detector">
                  {block.detectors.map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}
                </select>
              </header>
              <Confusion d={picked} hours={block.protocol.negative_hours} />
            </section>
          )}

          {data.training && (
            <section className="glass m-card">
              <header className="panel-head"><h2>How the machine learning model was chosen</h2></header>
              <p className="muted">
                Three model types were trained only on normal and harmless operation (no attacks). A separate set of validation runs picked the one that found the most attacks without false alarms. The test runs above were not used for this choice.
              </p>
              <div className="m-scroll">
                <table className="m-table">
                  <thead><tr><th>Model</th><th>Found on validation runs</th><th>False-alarm runs</th><th /></tr></thead>
                  <tbody>
                    {Object.entries(data.training.selection).map(([k, v]) => (
                      <tr key={k} className={k === data.training?.selected_model ? "live" : ""}>
                        <td><b>{v.label}</b></td>
                        <td>{v.detected} of {v.of}</td>
                        <td>{v.false_alarm_runs}</td>
                        <td>{k === data.training?.selected_model && <em className="tag">chosen</em>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="muted small">Trained on {data.training.train_rows.toLocaleString()} seconds of simulated data in {data.training.seconds_to_train} s.</p>
            </section>
          )}

          {data.limitations && (
            <section className="glass m-card limits">
              <header className="panel-head"><h2>What these numbers do not show</h2></header>
              <ul>{data.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
            </section>
          )}
        </>
      )}
    </main>
  );
}
