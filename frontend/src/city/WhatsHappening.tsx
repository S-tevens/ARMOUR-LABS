import { people } from "./ImpactStrip";
import type { CityState } from "./types";
import type { Incident } from "../types";

interface Item { key: string; level: "critical" | "warn" | "info"; text: string; weight: number; district?: string }

const TYPE: Record<string, string> = { hospital: "Hospital", water: "Water pumping", metro: "Metro", airport: "Airport feed", tech: "Tech park" };
const PLURAL: Record<string, string> = { hospital: "hospitals", water: "water stations", metro: "metro facilities", airport: "airport feeds", tech: "tech parks" };
const CAUSE: Record<string, string> = { attack: "Likely attack", fault: "Likely equipment fault", unknown: "Cause not yet known" };

/** Plain sentences, ranked by impact. Every number and name comes from the live city state and the incident. */
export function buildItems(s: CityState, incident: Incident | undefined): Item[] {
  const items: Item[] = [];
  const name = (id: string) => (id === "GRID" ? "the state grid" : s.districts.find((d) => d.id === id)?.name ?? id);
  if (incident && incident.evidence.length > 0) {
    items.push({ key: "inc", level: "critical", weight: 1e12, text: `${CAUSE[incident.classification]}: ${incident.evidence[0].text}` });
  }
  for (const d of s.districts) {
    // group identical facilities (two hospitals on backup near one substation read as one line)
    const groups = new Map<string, { type: string; status: string; priority: number; n: number; minutes: number }>();
    for (const f of d.facilities) {
      if (f.status === "ok") continue;
      const key = `${f.type}:${f.status}`;
      const g = groups.get(key) ?? { type: f.type, status: f.status, priority: f.priority, n: 0, minutes: 1e9 };
      g.n += 1;
      g.minutes = Math.min(g.minutes, f.backup_minutes_left);
      groups.set(key, g);
    }
    for (const [key, g] of groups) {
      // Hospitals first: a hospital on backup with minutes running out outranks any other facility.
      const hospital = g.type === "hospital";
      const what = g.n > 1 ? `${g.n} ${PLURAL[g.type]} near ${d.name} substation are` : `${TYPE[g.type]} near ${d.name} substation is`;
      if (g.status === "down") items.push({ key: `${d.id}:${key}`, level: "critical", weight: hospital ? 2e9 : g.priority <= 2 ? 9e8 : 4e8, district: d.id, text: `${what} without power` });
      else items.push({ key: `${d.id}:${key}`, level: "critical", weight: 1e9 - g.minutes, district: d.id, text: `${what} on backup power, about ${g.minutes} min left` });
    }
    if (d.status === "dark") items.push({ key: `d-${d.id}`, level: "critical", weight: d.people_unserved, district: d.id, text: `${d.name} substation is without power (${people(d.people_unserved)} people)` });
    if (d.status === "stale") items.push({ key: `s-${d.id}`, level: "warn", weight: 3e8, district: d.id, text: `The control centre has lost sight of ${d.name} substation` });
  }
  for (const l of s.lines) {
    const route = `${name(l.from)} to ${name(l.to)}`;
    if (l.status === "tripped" || l.status === "fault") items.push({ key: `l-${l.id}`, level: "warn", weight: 2e8, text: `Line ${l.id} (${route}) is out of service` });
    else if (l.status === "open") items.push({ key: `l-${l.id}`, level: "info", weight: 1e6, text: `Line ${l.id} (${route}) is open for planned maintenance` });
    else if (l.loading > 1.0) items.push({ key: `l-${l.id}`, level: "warn", weight: 1.5e8, text: `Line ${l.id} is carrying ${Math.round(l.loading * 100)}% of its capacity` });
    else if (l.loading > 0.9) items.push({ key: `l-${l.id}`, level: "info", weight: 1e8, text: `Line ${l.id} is close to its limit (${Math.round(l.loading * 100)}%)` });
  }
  return items.sort((a, b) => b.weight - a.weight);
}

const MAX = 6;

export default function WhatsHappening({
  state, incident, onSelect,
}: { state: CityState; incident: Incident | undefined; onSelect: (id: string) => void }) {
  const items = buildItems(state, incident);
  const shown = items.slice(0, MAX);
  return (
    <aside className="happening glass" aria-label="What's happening">
      <h2>What's happening</h2>
      {items.length === 0 && (
        <p className="all-clear"><span className="kpi-badge ok"><svg viewBox="0 0 10 10" width="9" height="9" aria-hidden="true"><path d="M2 5.2 4.2 7.4 8 3" fill="none" stroke="#fff" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg></span>Everything is running normally.</p>
      )}
      <ol className="hlist">
        {shown.map((it) => (
          <li key={it.key} className={it.level}>
            <i aria-hidden="true" />
            {it.district ? <button onClick={() => onSelect(it.district!)}>{it.text}</button> : <span>{it.text}</span>}
          </li>
        ))}
      </ol>
      {items.length > MAX && <p className="muted small more">and {items.length - MAX} more</p>}
    </aside>
  );
}
