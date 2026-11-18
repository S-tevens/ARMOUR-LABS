import { people } from "./ImpactStrip";
import type { DistrictState, FacilityState, LayoutDistrict } from "./types";

const TYPE: Record<string, string> = { hospital: "Hospital", water: "Water pumping", metro: "Metro", airport: "Airport", tech: "Tech park" };
const STATUS_TEXT: Record<string, string> = { ok: "Supplied", attention: "Supplied, needs attention", dark: "Without power", stale: "No data from the control centre" };

function FacilityPill({ f }: { f: FacilityState }) {
  if (f.status === "ok") return <span className="pill ok">On grid</span>;
  if (f.status === "backup") return <span className="pill warn">Backup, {f.backup_minutes_left} min</span>;
  return <span className="pill bad">No power</span>;
}

export default function DistrictCard({ d, lay, onOpen }: { d: DistrictState | undefined; lay: LayoutDistrict | undefined; onOpen: (id: string) => void }) {
  if (!d) {
    return (
      <section className="dcard glass">
        <h2>Substation</h2>
        <p className="empty">Select a substation on the map to see what it supplies.</p>
      </section>
    );
  }
  const names = new Map((lay?.facilities ?? []).map((f) => [f.id, f.name]));
  return (
    <section className="dcard glass" aria-label={`${d.name} details`}>
      <header className="panel-head">
        <h2>{d.name}</h2>
        <span className={`state-line ${d.status === "dark" ? "compromised" : d.status === "ok" ? "normal" : "suspicious"}`}><i /> {STATUS_TEXT[d.status]}</span>
      </header>
      <p className="muted small dsub">
        {lay?.voltage_kv ? `${lay.voltage_kv} kV, ` : ""}serves about {people(d.population)} people{d.status === "dark" ? `, ${people(d.people_unserved)} without power` : ""}
      </p>
      <ul className="facs">
        {d.facilities.map((f) => (
          <li key={f.id}><span title={names.get(f.id) || undefined}>{names.get(f.id) || TYPE[f.type]}</span><FacilityPill f={f} /></li>
        ))}
        {d.facilities.length === 0 && <li className="muted">No hospitals or metro mapped nearby</li>}
      </ul>
      <button className="btn primary wide" onClick={() => onOpen(d.id)}>Open substation view</button>
      <p className="muted small dsub">Simulated demand now {d.load_mw.toFixed(0)} MW</p>
    </section>
  );
}
