import { useEffect, useMemo, useRef, useState } from "react";
import type { CityLayout, CityState, DistrictStatus, Failure, FacilityStatus, LineStatus } from "./types";

const W = 900;
const H = 620;
const PAD = 54;
const STATUS_COLOR: Record<string, string> = { ok: "#2DB56A", attention: "#F0A030", dark: "#E5484D", stale: "#8A94AD" };
const FAC_GLYPH: Record<string, string> = { hospital: "+", metro: "M", airport: "A", water: "W", tech: "T" };
const FAC_STATUS: Record<FacilityStatus, string> = { ok: "#C3CDE3", backup: "#F0A030", down: "#E5484D" };

type Pt = { x: number; y: number };

/** Real positions (equirectangular), scaled into the frame, then nudged apart so nodes never sit on top of each other. */
function positions(layout: CityLayout): Map<string, Pt> {
  const ds = layout.districts.filter((d) => d.lat != null && d.lon != null);
  const lat0 = ds.reduce((a, d) => a + d.lat!, 0) / ds.length;
  const lon0 = ds.reduce((a, d) => a + d.lon!, 0) / ds.length;
  const raw = ds.map((d) => ({ id: d.id, x: (d.lon! - lon0) * Math.cos((lat0 * Math.PI) / 180), y: -(d.lat! - lat0) }));
  const minX = Math.min(...raw.map((p) => p.x)), maxX = Math.max(...raw.map((p) => p.x));
  const minY = Math.min(...raw.map((p) => p.y)), maxY = Math.max(...raw.map((p) => p.y));
  const k = Math.min((W - 2 * PAD) / (maxX - minX || 1), (H - 2 * PAD) / (maxY - minY || 1));
  const pts = raw.map((p) => ({ id: p.id, x: PAD + (p.x - minX) * k, y: PAD + (p.y - minY) * k }));
  for (let pass = 0; pass < 120; pass++) {
    for (let i = 0; i < pts.length; i++) {
      for (let j = i + 1; j < pts.length; j++) {
        const dx = pts[j].x - pts[i].x, dy = pts[j].y - pts[i].y;
        const d = Math.hypot(dx, dy) || 0.01;
        if (d < 30) {
          const push = (30 - d) / 2 / d;
          pts[i].x -= dx * push; pts[i].y -= dy * push; pts[j].x += dx * push; pts[j].y += dy * push;
        }
      }
    }
    for (const p of pts) { p.x = Math.min(W - PAD, Math.max(PAD, p.x)); p.y = Math.min(H - PAD, Math.max(PAD, p.y)); }
  }
  return new Map(pts.map((p) => [p.id, { x: p.x, y: p.y }]));
}

/** What the failures say about each element, as of a given step of the domino. */
function stepView(failures: Failure[], step: number) {
  const failed = new Map<string, Failure>();
  const later = new Set<string>();
  for (const f of failures) {
    const key = `${f.kind}:${f.id}`;
    if (f.n <= step) failed.set(key, f);
    else later.add(key);
  }
  return { failed, later };
}

function GraphSvg({
  layout, state, step, big, onSelect,
}: { layout: CityLayout; state: CityState; step: number; big: boolean; onSelect?: (id: string) => void }) {
  const pos = useMemo(() => positions(layout), [layout]);
  const { failed, later } = stepView(state.failures, step);
  const total = state.failures.length;
  const playing = step < total; // mid-replay: elements that fail later still look healthy

  const nodeStatus = (id: string, cur: DistrictStatus): DistrictStatus =>
    failed.has(`district:${id}`) ? "dark" : playing && later.has(`district:${id}`) ? "ok" : cur;
  const lineStatus = (id: string, cur: LineStatus): LineStatus =>
    failed.has(`line:${id}`) ? "tripped" : playing && later.has(`line:${id}`) ? "in_service" : cur;
  const facStatus = (id: string, cur: FacilityStatus): FacilityStatus => {
    const f = failed.get(`facility:${id}`);
    if (f) return f.text.includes("ran out") ? "down" : "backup";
    return playing && later.has(`facility:${id}`) ? "ok" : cur;
  };

  const byLine = new Map(state.lines.map((l) => [l.id, l]));
  const byState = new Map(state.districts.map((d) => [d.id, d]));
  const centroid = { x: W / 2, y: H / 2 };

  // the position of each failure, for the numbered badges and the chain between them
  const where = (f: Failure): Pt | null => {
    if (f.kind === "line") {
      const ln = layout.lines.find((l) => l.id === f.id);
      const a = ln && pos.get(ln.from), b = ln && pos.get(ln.to);
      return a && b ? { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 } : null;
    }
    const did = f.kind === "district" ? f.id : layout.districts.find((d) => d.facilities.some((x) => x.id === f.id))?.id;
    const p = did ? pos.get(did) : undefined;
    return p ? { x: p.x, y: p.y - (f.kind === "facility" ? 16 : 0) } : null;
  };
  const visible = state.failures.filter((f) => f.n <= step);
  const chain = visible.map(where).filter((p): p is Pt => !!p);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={`ggraph ${big ? "big" : ""}`} role="img" aria-label="Interconnected power grid graph">
      {layout.lines.filter((l) => l.source !== "grid-entry").map((l) => {
        const a = pos.get(l.from), b = pos.get(l.to), s = byLine.get(l.id);
        if (!a || !b || !s) return null;
        const st = lineStatus(l.id, s.status);
        const out = st !== "in_service";
        const hot = !out && !playing && s.loading > 1 ? "#E5484D" : !out && !playing && s.loading > 0.9 ? "#F0A030" : null;
        const color = out ? (st === "open" ? "#9AA4BC" : "#E5484D") : hot ?? (l.source === "osm" ? "#6F8BC4" : "#AEBBD8");
        return (
          <line key={l.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={color} strokeLinecap="round"
            strokeWidth={out ? 3 : 2 + 2.5 * Math.min(s.loading, 1.2)}
            strokeDasharray={out ? "3 7" : l.source === "inferred" ? "6 6" : undefined}>
            <title>{`${layout.districts.find((d) => d.id === l.from)?.name} to ${layout.districts.find((d) => d.id === l.to)?.name}: ${l.source === "osm" ? "mapped in OpenStreetMap" : "inferred tie"}, ${l.voltage_kv ?? ""} kV`}</title>
          </line>
        );
      })}

      {chain.length > 1 && <polyline points={chain.map((p) => `${p.x},${p.y}`).join(" ")} className="chain" fill="none" />}

      {layout.districts.map((d, i) => {
        const p = pos.get(d.id), cur = byState.get(d.id);
        if (!p || !cur) return null;
        const st = nodeStatus(d.id, cur.status);
        const r = Math.min(11, 5 + Math.sqrt(d.base_load_mw ?? 20) * 0.55);
        const out = d.entry ? (() => { // a short stub pointing away from the middle of the grid: the feed from the state grid
          const dx = p.x - centroid.x, dy = p.y - centroid.y, n = Math.hypot(dx, dy) || 1;
          return { x: p.x + (dx / n) * 30, y: p.y + (dy / n) * 30 };
        })() : null;
        const named = d.entry || st === "dark" || st === "stale" || failed.has(`district:${d.id}`);
        return (
          <g key={d.id} className={`gnode ${st}`} role="button" tabIndex={0} aria-label={`${d.name}: ${st === "dark" ? "without power" : "supplied"}`}
            onClick={() => onSelect?.(d.id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect?.(d.id); } }}>
            <title>{`${d.name}, ${d.voltage_kv ?? ""} kV`}</title>
            {out && (
              <g>
                <line x1={p.x} y1={p.y} x2={out.x} y2={out.y} stroke="#1A2340" strokeWidth={3} strokeLinecap="round" opacity={0.55} />
                <path d={`M ${out.x - 3} ${out.y - 5} L ${out.x + 4} ${out.y - 5} L ${out.x} ${out.y} L ${out.x + 4} ${out.y} L ${out.x - 3} ${out.y + 7} L ${out.x - 1} ${out.y + 1} L ${out.x - 5} ${out.y + 1} Z`} fill="#1A2340" opacity={0.7} />
                {i === layout.districts.findIndex((x) => x.entry) && <text x={out.x} y={out.y - 12} textAnchor="middle" className="gg-label muted">State grid</text>}
              </g>
            )}
            {d.entry && <circle cx={p.x} cy={p.y} r={r + 4} fill="none" stroke="#1A2340" strokeWidth={1.5} opacity={0.5} />}
            <circle cx={p.x} cy={p.y} r={r} fill={STATUS_COLOR[st]} stroke="#fff" strokeWidth={2} className={st === "dark" ? "pulse" : ""} />
            {d.facilities.map((f, k) => {
              const fs = cur.facilities.find((x) => x.id === f.id);
              const a = (-90 + (360 / d.facilities.length) * k) * (Math.PI / 180);
              const fx = p.x + Math.cos(a) * (r + 11), fy = p.y + Math.sin(a) * (r + 11);
              const status = facStatus(f.id, fs?.status ?? "ok");
              return (
                <g key={f.id}>
                  <title>{`${f.name ?? f.type}${status === "ok" ? "" : status === "backup" ? " (on backup power)" : " (no power)"}`}</title>
                  <circle cx={fx} cy={fy} r={6} fill="#fff" stroke={FAC_STATUS[status]} strokeWidth={2} />
                  <text x={fx} y={fy + 2.8} textAnchor="middle" className={`gg-glyph ${f.type}`}>{FAC_GLYPH[f.type]}</text>
                </g>
              );
            })}
            {named && <text x={p.x} y={p.y + r + (d.facilities.length ? 22 : 15)} textAnchor="middle" className={`gg-label ${st === "dark" ? "bad" : ""}`}>{d.name}</text>}
          </g>
        );
      })}

      {visible.map((f) => {
        const p = where(f);
        if (!p) return null;
        return (
          <g key={f.n} className="badge-n">
            <circle cx={p.x + (f.kind === "line" ? 0 : 12)} cy={p.y - (f.kind === "line" ? 0 : 12)} r={9} />
            <text x={p.x + (f.kind === "line" ? 0 : 12)} y={p.y - (f.kind === "line" ? 0 : 12) + 3.5} textAnchor="middle">{f.n}</text>
          </g>
        );
      })}
    </svg>
  );
}

function Legend() {
  return (
    <ul className="gg-legend" aria-label="Legend">
      <li><i className="dot green" /> Supplied</li>
      <li><i className="dot amber" /> Needs attention</li>
      <li><i className="dot red" /> Without power</li>
      <li><i className="ln solid" /> Mapped in OpenStreetMap</li>
      <li><i className="ln dashed" /> Inferred tie</li>
      <li><span className="gg-glyph-key hospital">+</span> Hospital <span className="gg-glyph-key">M</span> Metro <span className="gg-glyph-key">A</span> Airport</li>
    </ul>
  );
}

export default function GridGraphPanel({
  layout, state, onOpenSubstation,
}: { layout: CityLayout; state: CityState; onOpenSubstation: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<number | null>(null); // null = show everything that has failed so far
  const [playing, setPlaying] = useState(false);
  const total = state.failures.length;
  const eff = step ?? total;
  const closeRef = useRef<HTMLButtonElement>(null);

  // a new incident starts a new sequence
  const firstId = state.failures[0]?.id ?? "";
  useEffect(() => { setStep(null); setPlaying(false); }, [firstId, total === 0]);

  useEffect(() => {
    if (!playing) return;
    const t = window.setInterval(() => {
      setStep((s) => {
        const next = (s ?? 0) + 1;
        if (next >= total) { setPlaying(false); return null; }
        return next;
      });
    }, 850);
    return () => window.clearInterval(t);
  }, [playing, total]);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const replay = () => { setStep(0); setPlaying(true); };
  const real = layout.lines.filter((l) => l.source === "osm").length;
  const inferred = layout.lines.filter((l) => l.source === "inferred").length;
  const select = (id: string) => onOpenSubstation(id);

  return (
    <>
      <section className="glass ggpanel">
        <header className="panel-head">
          <div>
            <h2>Power grid network</h2>
            <span className="muted small">{layout.districts.length} substations, {real} mapped and {inferred} inferred links, with the hospitals, metro and airport they supply</span>
          </div>
          <button className="btn expand" onClick={() => setOpen(true)} aria-label="Expand the grid graph">
            <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M1.5 5V1.5H5M9 1.5h3.5V5M12.5 9v3.5H9M5 12.5H1.5V9" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
            Expand
          </button>
        </header>
        <GraphSvg layout={layout} state={state} step={total} big={false} onSelect={select} />
        <Legend />
        {total === 0 && <p className="muted small ggnote">Start a city scenario to watch a failure spread. Expand this view to replay it step by step.</p>}
      </section>

      {open && (
        <div className="gg-modal" role="dialog" aria-modal="true" aria-label="Power grid network, expanded" onClick={(e) => { if (e.target === e.currentTarget) setOpen(false); }}>
          <div className="gg-sheet glass">
            <header className="panel-head">
              <div>
                <h2>How a failure spreads through the grid</h2>
                <span className="muted small">{layout.attribution}</span>
              </div>
              <button ref={closeRef} className="btn expand" onClick={() => setOpen(false)}>Close</button>
            </header>
            <div className="gg-body">
              <div className="gg-canvas">
                <GraphSvg layout={layout} state={state} step={eff} big onSelect={select} />
                <Legend />
              </div>
              <aside className="gg-side">
                <h2>Failure sequence</h2>
                {total === 0 ? (
                  <p className="muted small">Nothing has failed. Start a city scenario, then come back here to replay how it spread, one step at a time.</p>
                ) : (
                  <>
                    <div className="gg-controls">
                      <button className="btn primary" onClick={() => (playing ? setPlaying(false) : replay())}>{playing ? "Pause" : "Replay"}</button>
                      <input type="range" min={0} max={total} value={eff} aria-label="Step of the failure sequence"
                        onChange={(e) => { setPlaying(false); setStep(Number(e.target.value) >= total ? null : Number(e.target.value)); }} />
                      <button className="btn ghost" onClick={() => { setPlaying(false); setStep(null); }}>Now</button>
                    </div>
                    <p className="muted small">Step {eff} of {total}. Each step is something that actually failed in the simulation, in order.</p>
                    <ol className="gg-seq">
                      {state.failures.map((f) => (
                        <li key={f.n} className={f.n <= eff ? "on" : ""} aria-current={f.n === eff ? "step" : undefined}>
                          <button onClick={() => { setPlaying(false); setStep(f.n >= total ? null : f.n); }}>
                            <b>{f.n}</b><span>{f.text}</span>
                          </button>
                        </li>
                      ))}
                    </ol>
                  </>
                )}
                <p className="muted small gg-prov">{layout.data_note}</p>
              </aside>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
