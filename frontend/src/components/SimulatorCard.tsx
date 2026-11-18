import { useState } from "react";
import type { ScenarioInfo } from "../types";

const GROUPS: { kind: ScenarioInfo["kind"]; label: string }[] = [
  { kind: "attack", label: "Attacks" },
  { kind: "fault", label: "Faults" },
  { kind: "benign", label: "Legitimate changes" },
];

export default function SimulatorCard({
  scenarios,
  onStart,
  onStop,
  title = "Simulator",
}: {
  title?: string;
  scenarios: ScenarioInfo[];
  onStart: (name: string) => void;
  onStop: () => void;
}) {
  const core = scenarios.filter((s) => s.group === "core");
  const extra = scenarios.filter((s) => s.group === "extra");
  const [pick, setPick] = useState("");
  const picked = extra.find((s) => s.name === pick);

  return (
    <section className="sim glass" aria-label="Attack simulator">
      <h2>{title}</h2>
      <p className="hint">Runs inside the simulation only.</p>
      <div className="sim-buttons">
        {core.map((s) => (
          <button key={s.name} className={`btn ${s.kind}`} title={s.description} onClick={() => onStart(s.name)}>
            <i /> {s.label}
          </button>
        ))}
      </div>
      {extra.length > 0 && (
        <div className="sim-more">
          <label htmlFor="more-scenarios">More scenarios</label>
          <div className="sim-more-row">
            <select id="more-scenarios" value={pick} onChange={(e) => setPick(e.target.value)}>
              <option value="">Choose…</option>
              {GROUPS.map((g) => {
                const items = extra.filter((s) => s.kind === g.kind);
                return items.length === 0 ? null : (
                  <optgroup key={g.kind} label={g.label}>
                    {items.map((s) => <option key={s.name} value={s.name}>{s.label}</option>)}
                  </optgroup>
                );
              })}
            </select>
            <button className="btn primary compact" disabled={!picked} onClick={() => picked && onStart(picked.name)}>Start</button>
          </div>
          {picked && <p className="hint">{picked.description}</p>}
        </div>
      )}
      <button className="btn ghost wide" onClick={onStop}>Stop and reset</button>
    </section>
  );
}
