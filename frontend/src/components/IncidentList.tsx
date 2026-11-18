import type { Incident } from "../types";

const STEPS: Incident["status"][] = ["open", "recovering", "recovered"];
const STEP_LABEL: Record<string, string> = { open: "Detected", recovering: "Recovering", recovered: "Recovered" };

export default function IncidentList({ incidents, onApprove }: { incidents: Incident[]; onApprove: (id: string) => void }) {
  if (incidents.length === 0) {
    return (
      <section className="glass incidents">
        <h2>Incidents</h2>
        <p className="empty">No incidents. Start a scenario in the simulator to see one.</p>
      </section>
    );
  }
  return (
    <section className="incidents-wrap">
      {incidents.map((i) => {
        const at = Math.max(0, STEPS.indexOf(i.status));
        return (
          <article key={i.id} className={`glass incident ${i.status}`}>
            <header>
              <h2>{i.id}</h2>
              <span className={`pill sev-${i.severity}`}>{i.severity} severity</span>
              <span className="pill neutral">Cause: {i.classification}</span>
              {i.affected_devices.length > 0 && <span className="muted small">Affected: {i.affected_devices.join(", ")}</span>}
              {i.status === "open" && (
                <button className="btn primary" onClick={() => onApprove(i.id)}>Approve simulated containment</button>
              )}
            </header>
            <ol className="steps" aria-label="Incident progress">
              {STEPS.map((s, k) => (
                <li key={s} className={k < at ? "done" : k === at ? "now" : ""}>{STEP_LABEL[s]}</li>
              ))}
            </ol>
            <ul className="evidence">
              {i.evidence.map((e, k) => (
                <li key={k}><span className={`tag ${e.tag}`}>{e.tag}</span>{e.text}</li>
              ))}
            </ul>
          </article>
        );
      })}
    </section>
  );
}
