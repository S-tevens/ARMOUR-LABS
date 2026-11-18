import type { ScenarioInfo } from "../types";

export default function SimulatorCard({
  scenarios,
  onStart,
  onStop,
}: {
  scenarios: ScenarioInfo[];
  onStart: (name: string) => void;
  onStop: () => void;
}) {
  return (
    <section className="sim glass" aria-label="Attack simulator">
      <h2>Simulator</h2>
      <p className="hint">Runs inside the simulation only. Red: attack. Amber: fault. Green: legitimate change.</p>
      <div className="sim-buttons">
        {scenarios.map((s) => (
          <button key={s.name} className={`btn ${s.kind}`} title={s.description} onClick={() => onStart(s.name)}>
            <i /> {s.label}
          </button>
        ))}
        <button className="btn ghost" onClick={onStop}>Stop and reset</button>
      </div>
    </section>
  );
}
