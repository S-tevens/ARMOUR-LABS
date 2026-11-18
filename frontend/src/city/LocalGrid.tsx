import CityMap from "./CityMap";
import type { CityLayout, CityState } from "./types";

const MAX_NEIGHBOURS = 6;
const MIN_SEPARATION = 1.45; // in grid units, so tiles never overlap

/**
 * The selected substation and the substations it is wired to, laid out in the isometric style.
 * Positions follow the real bearings from the map, then are nudged apart so tiles do not overlap.
 */
export function neighbourhood(layout: CityLayout, state: CityState, id: string) {
  const sel = layout.districts.find((d) => d.id === id);
  if (!sel) return null;
  const links = layout.lines.filter((l) => l.source !== "grid-entry" && (l.from === id || l.to === id));
  const neighbourIds = links
    .map((l) => ({ id: l.from === id ? l.to : l.from, cap: l.capacity_mw }))
    .sort((a, b) => b.cap - a.cap)
    .slice(0, MAX_NEIGHBOURS)
    .map((n) => n.id);
  const ids = [id, ...neighbourIds];
  const members = ids.map((i) => layout.districts.find((d) => d.id === i)!).filter(Boolean);

  // bearings -> iso grid. dx east, dy south, in km.
  const km = (d: { lat?: number | null; lon?: number | null }) => ({
    x: ((d.lon ?? 0) - (sel.lon ?? 0)) * 111.32 * Math.cos(((sel.lat ?? 13) * Math.PI) / 180),
    y: -((d.lat ?? 0) - (sel.lat ?? 0)) * 110.57,
  });
  const far = Math.max(1, ...members.map((m) => Math.hypot(km(m).x, km(m).y)));
  const k = 2.6 / far;
  const pos = new Map<string, { u: number; v: number }>();
  for (const m of members) {
    const { x, y } = km(m);
    const a = (x * k) / 0.866, b = (y * k) / 0.5; // screen x = (u - v) * 0.866, screen y = (u + v) * 0.5
    pos.set(m.id, { u: (a + b) / 2, v: (b - a) / 2 });
  }
  const screen = (p: { u: number; v: number }) => ({ x: (p.u - p.v) * 0.866, y: (p.u + p.v) * 0.5 });
  for (let pass = 0; pass < 80; pass++) {
    for (let i = 0; i < members.length; i++) {
      for (let j = i + 1; j < members.length; j++) {
        const pi = pos.get(members[i].id)!, pj = pos.get(members[j].id)!;
        const si = screen(pi), sj = screen(pj);
        const dx = sj.x - si.x, dy = (sj.y - si.y) * 1.5;
        const d = Math.hypot(dx, dy) || 0.001;
        if (d < MIN_SEPARATION) {
          const push = ((MIN_SEPARATION - d) / 2) / d;
          // move apart along the screen vector, then convert back to grid units
          const mx = dx * push, my = (dy * push) / 1.5;
          const du = (mx / 0.866 + my / 0.5) / 2, dv = (my / 0.5 - mx / 0.866) / 2;
          const keepFirst = members[i].id === id;
          const keepSecond = members[j].id === id;
          if (!keepFirst) { pi.u -= du * (keepSecond ? 2 : 1); pi.v -= dv * (keepSecond ? 2 : 1); }
          if (!keepSecond) { pj.u += du * (keepFirst ? 2 : 1); pj.v += dv * (keepFirst ? 2 : 1); }
        }
      }
    }
  }

  const inSet = new Set(ids);
  const placed = (d: (typeof members)[number]) => ({ ...d, x: pos.get(d.id)!.u, y: pos.get(d.id)!.v });
  const layoutDistricts = members.map(placed);
  const entryLines = layout.lines
    .filter((l) => l.source === "grid-entry" && inSet.has(l.to))
    .map((l) => {
      const d = pos.get(l.to)!;
      return { ...l, terminal: [d.u - 0.6, d.v - 0.9] as [number, number] };
    });
  const layoutLines = [...layout.lines.filter((l) => l.source !== "grid-entry" && inSet.has(l.from) && inSet.has(l.to)), ...entryLines];
  const lineIds = new Set(layoutLines.map((l) => l.id));
  const stateDistricts = state.districts.filter((d) => inSet.has(d.id)).map((d) => ({ ...d, x: pos.get(d.id)!.u, y: pos.get(d.id)!.v }));
  const stateLines = state.lines.filter((l) => lineIds.has(l.id));
  return {
    layout: { ...layout, districts: layoutDistricts, lines: layoutLines },
    state: { ...state, districts: stateDistricts, lines: stateLines },
    mapped: layoutLines.filter((l) => l.source === "osm").length,
    inferred: layoutLines.filter((l) => l.source === "inferred").length,
    total: links.length,
  };
}

/** The popup that appears when a substation is selected on the real map. */
export default function LocalGrid({
  layout, state, id, onClose, onOpen,
}: { layout: CityLayout; state: CityState; id: string; onClose: () => void; onOpen: (id: string) => void }) {
  const hood = neighbourhood(layout, state, id);
  const lay = layout.districts.find((d) => d.id === id);
  const st = state.districts.find((d) => d.id === id);
  if (!hood || !lay || !st) return null;
  const status = st.status === "dark" ? "Without power" : st.status === "attention" ? "Needs attention" : st.status === "stale" ? "No data" : "Supplied";
  return (
    <aside className="localgrid glass" aria-label={`${lay.name} local grid`}>
      <header>
        <div>
          <h2>{lay.name}</h2>
          <span className="muted small">{lay.voltage_kv ? `${lay.voltage_kv} kV substation, ` : ""}{status.toLowerCase()}</span>
        </div>
        <button className="x" aria-label="Close" onClick={onClose}>&times;</button>
      </header>
      <CityMap layout={hood.layout} state={hood.state} selected={id} onSelect={() => undefined} spacing={1} />
      <footer>
        <span className="muted small">
          Wired to {hood.total} substation{hood.total === 1 ? "" : "s"}
          {hood.total > 0 ? ` (${hood.mapped} mapped, ${hood.inferred} inferred)` : ""}
        </span>
        <button className="btn primary" onClick={() => onOpen(id)}>Open substation view</button>
      </footer>
    </aside>
  );
}
