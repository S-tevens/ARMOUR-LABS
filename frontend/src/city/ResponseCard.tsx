import type { CityState } from "./types";

/** Shown while the city is being restored: the verification checklist and the latest actions. */
export default function ResponseCard({ s }: { s: CityState }) {
  const r = s.recovery;
  if (r.state === "idle") return null;
  const passed = r.checks.filter((c) => c.ok).length;
  const title = r.state === "recovered" ? "City recovered" : r.state === "unresolved" ? "Recovery unresolved" : "Restoring the city";
  return (
    <section className={`rcard glass ${r.state}`} aria-label="Recovery">
      <header className="panel-head">
        <h2>{title}</h2>
        <span className="muted small">{passed} of {r.checks.length} checks</span>
      </header>
      <ul className="checks">
        {r.checks.map((c) => (
          <li key={c.name} className={c.ok ? "ok" : "no"}>
            <i aria-hidden="true">{c.ok ? "✓" : ""}</i>
            <span>{c.name}{!c.ok && c.detail ? <small>{c.detail}</small> : null}</span>
          </li>
        ))}
      </ul>
      {r.state === "recovering" && (
        <p className="muted small">Recovered is shown only after all checks hold for {r.dwell} s ({Math.floor(r.seconds_in_range)} s so far).</p>
      )}
      {s.actions.length > 0 && (
        <ul className="actions">
          {s.actions.slice(-4).map((a, i) => <li key={i}>{a}</li>)}
        </ul>
      )}
    </section>
  );
}
