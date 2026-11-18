import Meter from "./Meter";
import type { Scores } from "../types";

const ROWS: { key: "network" | "controller" | "process" | "twin"; label: string; note: string }[] = [
  { key: "network", label: "Network", note: "Unauthorised messages" },
  { key: "controller", label: "Controller", note: "Commands outside the schedule" },
  { key: "process", label: "Process", note: "Pressure and flow behaviour" },
  { key: "twin", label: "Digital twin", note: "Distance from expected state" },
];

const tone = (v: number): "green" | "amber" | "red" => (v >= 0.8 ? "red" : v >= 0.4 ? "amber" : "green");

export default function ScoreBars({ scores }: { scores: Scores | null }) {
  return (
    <section className="glass scores">
      <header className="panel-head">
        <h2>Detector scores</h2>
        <span className="muted small">Baseline detector, not measured results</span>
      </header>
      {ROWS.map((r) => {
        const v = scores ? scores[r.key] : 0;
        return (
          <div className="score-row" key={r.key}>
            <div className="score-label"><b>{r.label}</b><span>{r.note}</span></div>
            <Meter label="" display={v.toFixed(2)} value={v} tone={tone(v)} threshold={0.8} />
          </div>
        );
      })}
      <footer className="legend"><span className="muted">The tick marks the 0.8 alert threshold</span></footer>
    </section>
  );
}
