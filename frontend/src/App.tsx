import { useEffect, useState } from "react";
import { approveResponse, getScenarios, startScenario, stopScenario } from "./api";
import PlantView from "./components/PlantView";
import { useStream } from "./useStream";
import type { Incident, ScenarioInfo } from "./types";

const VARS = ["pressure", "flow", "tank1_level", "tank2_level", "temperature"] as const;

function ScoreBar({ label, value }: { label: string; value: number }) {
  const cls = value >= 0.8 ? "red" : value >= 0.4 ? "amber" : "green";
  return (
    <div className="score">
      <span>{label}</span>
      <div className="bar"><div className={`fill ${cls}`} style={{ width: `${value * 100}%` }} /></div>
      <b>{value.toFixed(2)}</b>
    </div>
  );
}

export default function App() {
  const s = useStream();
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getScenarios().then(setScenarios).catch(() => setError("Backend not reachable. Start it on port 8000."));
  }, []);

  const incidents = Object.values(s.incidents).sort((a, b) => b.t_start - a.t_start);
  const active: Incident | undefined = incidents.find((i) => i.status !== "recovered" && i.status !== "unresolved");
  const status = !s.connected ? "OFFLINE" : active ? "INCIDENT" : "NORMAL";

  const run = (fn: () => Promise<unknown>) => fn().catch((e) => setError(String(e)));

  return (
    <div className="app">
      <header>
        <h1>ARMOUR LABS</h1>
        <span className={`status st-${status.toLowerCase()}`}>SYSTEM STATUS: {status}</span>
      </header>
      {error && <div className="error">{error}</div>}

      <main>
        <section className="panel wide">
          <h2>Live plant view</h2>
          <PlantView t={s.telemetry} />
        </section>

        <section className="panel">
          <h2>Threat monitor <small>baseline detector, illustrative</small></h2>
          {s.scores ? (
            <>
              <ScoreBar label="Network" value={s.scores.network} />
              <ScoreBar label="Controller" value={s.scores.controller} />
              <ScoreBar label="Process" value={s.scores.process} />
              <ScoreBar label="Twin residual" value={s.scores.twin} />
            </>
          ) : <div className="empty">No scores yet</div>}
          <div className="count">Active incidents: <b>{active ? 1 : 0}</b></div>
        </section>

        <section className="panel">
          <h2>Attack simulator <small>simulation only</small></h2>
          <div className="buttons">
            {scenarios.map((sc) => (
              <button key={sc.name} className={sc.kind} title={sc.description} onClick={() => run(() => startScenario(sc.name))}>
                {sc.label}
              </button>
            ))}
            <button onClick={() => run(stopScenario)}>Stop / reset</button>
          </div>
        </section>

        <section className="panel">
          <h2>Digital twin <small>placeholder nominal values</small></h2>
          <table>
            <thead><tr><th>Variable</th><th>Expected</th><th>Observed</th><th>Residual</th></tr></thead>
            <tbody>
              {s.twin && s.telemetry && VARS.map((v) => {
                const r = s.twin!.norm_residual[v] ?? 0;
                return (
                  <tr key={v} className={Math.abs(r) > 4 ? "bad" : ""}>
                    <td>{v}</td>
                    <td>{s.twin!.expected[v].toFixed(2)}</td>
                    <td>{s.telemetry![v].toFixed(2)}</td>
                    <td>{s.twin!.residual[v].toFixed(2)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>

        <section className="panel">
          <h2>Network events</h2>
          <ul className="events">
            {s.events.slice(0, 12).map((e) => (
              <li key={e.seq} className={e.authorised ? "" : "bad"}>
                <code>{e.t.toFixed(0)}s</code> {e.src} → {e.dst} {e.function_code} {e.register}={String(e.value)}
                {!e.authorised && <b> UNAUTHORISED</b>}
              </li>
            ))}
          </ul>
        </section>

        <section className="panel wide">
          <h2>Incidents</h2>
          {incidents.length === 0 && <div className="empty">No incidents</div>}
          {incidents.map((i) => (
            <div key={i.id} className={`incident ${i.status}`}>
              <div className="inc-head">
                <b>{i.id}</b> <span className="pill">{i.severity}</span> <span className="pill">{i.classification}</span>
                <span className="pill">{i.status}</span>
                {i.affected_devices.length > 0 && <span>Affected: {i.affected_devices.join(", ")}</span>}
                {i.status === "open" && (
                  <button onClick={() => run(() => approveResponse(i.id))}>Approve simulated containment</button>
                )}
              </div>
              <ul>
                {i.evidence.map((e, k) => (
                  <li key={k}><span className={`tag ${e.tag}`}>{e.tag}</span> {e.text}</li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}
