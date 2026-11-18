import type { CityLayout, CityState, DistrictState, FacilityState, LineState } from "./types";

// Isometric projection, same language as the substation view. u runs down-right, v runs down-left.
const S = 96;
const K = S * 0.866;
const H = S * 0.5;
const OX = 0;
const OY = 0;
const DEFAULT_SPACING = 1.45; // spacing between districts, in grid units (leaves room for the power lines)
const TILE = 0.45; // half-size of a district tile, in grid units

type Pt = [number, number];
const P = (u: number, v: number, z = 0): Pt => [OX + (u - v) * K, OY + (u + v) * H - z];
const pts = (a: Pt[]) => a.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");

function Block({ u, v, w, d, h, top, side, stroke = "#fff" }: { u: number; v: number; w: number; d: number; h: number; top: string; side: string; stroke?: string }) {
  const u0 = u - w / 2, u1 = u + w / 2, v0 = v - d / 2, v1 = v + d / 2;
  return (
    <g>
      <polygon points={pts([P(u0, v1), P(u1, v1), P(u1, v1, h), P(u0, v1, h)])} fill={side} stroke={stroke} strokeWidth={0.6} />
      <polygon points={pts([P(u1, v0), P(u1, v1), P(u1, v1, h), P(u1, v0, h)])} fill={side} opacity={0.78} stroke={stroke} strokeWidth={0.6} />
      <polygon points={pts([P(u0, v0, h), P(u1, v0, h), P(u1, v1, h), P(u0, v1, h)])} fill={top} stroke={stroke} strokeWidth={0.8} />
    </g>
  );
}

const OFFSETS: Pt[] = [[-0.2, -0.17], [0.19, -0.1], [-0.02, 0.22]];
const FILLER: [number, number, number][] = [[0.24, 0.2, 7], [-0.27, 0.16, 5], [0.3, -0.26, 6]];

function Facility({ f, u, v, dim }: { f: FacilityState; u: number; v: number; dim: boolean }) {
  const grey = dim || f.status === "down";
  const c = (a: string, b: string) => (grey ? ["#D3D8E4", "#B9C0D0"] : [a, b]);
  let body;
  if (f.type === "hospital") {
    const [t, s] = c("#FFFFFF", "#E3E9F6");
    const cross = grey ? "#9aa4bc" : "var(--red)";
    body = (
      <g>
        <Block u={u} v={v} w={0.3} d={0.3} h={24} top={t} side={s} />
        <polygon points={pts([P(u + 0.15, v - 0.08, 15), P(u + 0.15, v + 0.08, 15), P(u + 0.15, v + 0.08, 19), P(u + 0.15, v - 0.08, 19)])} fill={cross} />
        <polygon points={pts([P(u + 0.15, v - 0.025, 11), P(u + 0.15, v + 0.025, 11), P(u + 0.15, v + 0.025, 23), P(u + 0.15, v - 0.025, 23)])} fill={cross} />
      </g>
    );
  } else if (f.type === "water") {
    const [t, s] = c("#8DB4FF", "#C9DBFF");
    body = <Block u={u} v={v} w={0.26} d={0.26} h={14} top={t} side={s} />;
  } else if (f.type === "metro") {
    const [t, s] = c("#6B7791", "#A9B3C8");
    body = <Block u={u} v={v} w={0.36} d={0.22} h={9} top={t} side={s} />;
  } else if (f.type === "airport") {
    const [t, s] = c("#C8D0E0", "#DCE1EC");
    body = <Block u={u} v={v} w={0.44} d={0.16} h={4} top={t} side={s} />;
  } else {
    const [t, s] = c("#9DBBF5", "#C4D6F8");
    body = <Block u={u} v={v} w={0.26} d={0.26} h={36} top={t} side={s} />;
  }
  const [mx, my] = P(u, v, f.type === "tech" ? 46 : 32);
  return (
    <g>
      {body}
      {f.status === "backup" && <circle cx={mx} cy={my} r={5} fill="var(--amber)" stroke="#fff" strokeWidth={1.5} />}
      {f.status === "down" && <circle cx={mx} cy={my} r={5} fill="var(--red)" stroke="#fff" strokeWidth={1.5} />}
    </g>
  );
}

function StatusIcon({ d, x, y }: { d: DistrictState; x: number; y: number }) {
  if (d.status === "ok") return null;
  const color = d.status === "dark" ? "var(--red)" : d.status === "attention" ? "var(--amber)" : "#8A94AD";
  return (
    <g>
      <circle cx={x} cy={y} r={11} fill={color} stroke="#fff" strokeWidth={2} className={d.status === "dark" ? "led alarm" : ""} />
      {d.status === "dark" ? (
        <g stroke="#fff" strokeWidth={1.8} strokeLinecap="round" fill="none">
          <path d={`M ${x} ${y - 6} V ${y - 1}`} />
          <path d={`M ${x - 4} ${y - 4} A 5.5 5.5 0 1 0 ${x + 4} ${y - 4}`} />
        </g>
      ) : (
        <text x={x} y={y + 4.5} textAnchor="middle" fill="#fff" fontSize="13" fontWeight="700">{d.status === "stale" ? "?" : "!"}</text>
      )}
    </g>
  );
}

function Tile({ d, selected, onSelect, sp }: { d: DistrictState; selected: boolean; onSelect: (id: string) => void; sp: number }) {
  const dark = d.status === "dark";
  const u = d.x * sp, v = d.y * sp;
  const corners: Pt[] = [P(u - TILE, v - TILE), P(u + TILE, v - TILE), P(u + TILE, v + TILE), P(u - TILE, v + TILE)];
  const stroke = selected ? "var(--blue)" : dark ? "var(--red)" : d.status === "attention" ? "var(--amber)" : "rgba(255,255,255,0.95)";
  const fill = dark ? "#E4E7EF" : "rgba(255,255,255,0.9)";
  const [cx, cy] = P(u, v);
  const label = `${d.name}: ${dark ? "without power" : d.status === "attention" ? "needs attention" : d.status === "stale" ? "no data" : "normal"}`;
  const act = () => onSelect(d.id);
  return (
    <g
      className="tile"
      role="button"
      tabIndex={0}
      aria-label={label}
      aria-pressed={selected}
      onClick={act}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); act(); } }}
    >
      <title>{label}</title>
      <polygon points={pts(corners.map(([x, y]) => [x, y + 9] as Pt))} fill="rgba(190,203,232,0.75)" />
      <polygon points={pts(corners)} fill={fill} stroke={stroke} strokeWidth={selected ? 3 : dark || d.status === "attention" ? 2 : 1} strokeDasharray={d.status === "stale" ? "5 4" : undefined} />
      {FILLER.map(([du, dv, h], i) => (
        <Block key={i} u={u + du} v={v + dv} w={0.17} d={0.17} h={h} top={dark ? "#D3D8E4" : "#EEF2FA"} side={dark ? "#C2C8D6" : "#DCE3F1"} stroke="rgba(255,255,255,0.7)" />
      ))}
      {d.facilities.slice(0, 3).map((f, i) => <Facility key={f.id} f={f} u={u + OFFSETS[i][0]} v={v + OFFSETS[i][1]} dim={dark} />)}
      <StatusIcon d={d} x={cx} y={cy - 56} />
    </g>
  );
}

function Wire({ ln, a, b }: { ln: LineState; a: Pt; b: Pt }) {
  const path = pts([a, b]);
  const out = ln.status !== "in_service";
  const flowing = !out && Math.abs(ln.flow_mw) > 1;
  const hot = ln.loading > 1.0 ? "blocked" : ln.loading > 0.9 ? "hot" : "";
  const dur = Math.max(0.5, 3 - Math.abs(ln.flow_mw) / 40);
  const mid: Pt = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  const fault = ln.status === "tripped" || ln.status === "fault";
  return (
    <g>
      <title>{`Line ${ln.id}: ${ln.status === "in_service" ? `${Math.abs(ln.flow_mw).toFixed(0)} MW, ${Math.round(ln.loading * 100)}% of capacity` : ln.status === "open" ? "open for maintenance" : "out of service"}`}</title>
      <polyline points={path} className={out ? (fault ? "pipe-base trip" : "pipe-base off") : "pipe-base"} style={out ? undefined : { strokeWidth: 7 + 5 * Math.min(ln.loading, 1.2) }} />
      {flowing && <polyline points={path} className={`pipe-flow ${hot}${ln.flow_mw < 0 ? " rev" : ""}`} style={{ animationDuration: `${dur}s` }} />}
      {fault && (
        <g>
          <circle cx={mid[0]} cy={mid[1]} r={9} fill="var(--red)" stroke="#fff" strokeWidth={2} />
          <path d={`M ${mid[0] - 3.5} ${mid[1] - 3.5} L ${mid[0] + 3.5} ${mid[1] + 3.5} M ${mid[0] + 3.5} ${mid[1] - 3.5} L ${mid[0] - 3.5} ${mid[1] + 3.5}`} stroke="#fff" strokeWidth={2} strokeLinecap="round" />
        </g>
      )}
      {ln.status === "open" && <circle cx={mid[0]} cy={mid[1]} r={6} fill="#fff" stroke="#9aa4bc" strokeWidth={2} />}
    </g>
  );
}

function Pylon({ at }: { at: Pt }) {
  const [x, y] = at;
  return (
    <g stroke="#A9B6D3" strokeWidth={1.8} fill="none" strokeLinecap="round" strokeLinejoin="round">
      <path d={`M ${x - 12} ${y} L ${x} ${y - 52} L ${x + 12} ${y}`} />
      <path d={`M ${x - 9} ${y - 20} H ${x + 9} M ${x - 5} ${y - 38} H ${x + 5}`} strokeWidth={1.3} />
      <path d={`M ${x - 18} ${y - 46} H ${x + 18}`} strokeWidth={2.2} />
    </g>
  );
}

/** Bounding box of everything drawn, so the map always fills its frame. */
function bounds(layout: CityLayout, state: CityState, sp: number) {
  const xs: number[] = [], ys: number[] = [];
  const add = (x: number, y: number) => { xs.push(x); ys.push(y); };
  for (const d of state.districts) {
    const u = d.x * sp, v = d.y * sp;
    for (const [du, dv] of [[-TILE, -TILE], [TILE, -TILE], [TILE, TILE], [-TILE, TILE]]) add(...P(u + du, v + dv));
    add(...P(u, v, 70));
    const [bx, by] = P(u + TILE, v + TILE);
    add(bx - 50, by + 34);
    add(bx + 50, by + 34);
  }
  for (const l of layout.lines) {
    if (l.from === "GRID" && l.terminal) {
      const [x, y] = P(l.terminal[0] * sp, l.terminal[1] * sp, 6);
      add(x - 22, y - 60);
      add(x + 22, y + 30);
    }
  }
  const pad = 14;
  const x0 = Math.min(...xs) - pad, y0 = Math.min(...ys) - pad;
  return { x0, y0, w: Math.max(...xs) + pad - x0, h: Math.max(...ys) + pad - y0 };
}

export default function CityMap({
  layout, state, selected, onSelect, spacing = DEFAULT_SPACING,
}: { layout: CityLayout; state: CityState; selected: string | null; onSelect: (id: string) => void; spacing?: number }) {
  const sp = spacing;
  const pos = new Map<string, Pt>(state.districts.map((d) => [d.id, P(d.x * sp, d.y * sp, 6)]));
  const lineLayout = new Map(layout.lines.map((l) => [l.id, l]));
  const order = [...state.districts].sort((a, b) => a.x + a.y - (b.x + b.y));
  const grid = layout.lines.filter((l) => l.from === "GRID" && l.terminal);
  const box = bounds(layout, state, sp);
  return (
    <svg viewBox={`${box.x0.toFixed(0)} ${box.y0.toFixed(0)} ${box.w.toFixed(0)} ${box.h.toFixed(0)}`} className="citymap" role="group" aria-label={`Map of ${layout.name}`}>
      {state.lines.map((ln) => {
        const meta = lineLayout.get(ln.id);
        const a = ln.from === "GRID" && meta?.terminal ? P(meta.terminal[0] * sp, meta.terminal[1] * sp, 6) : pos.get(ln.from);
        const b = pos.get(ln.to);
        return a && b ? <Wire key={ln.id} ln={ln} a={a} b={b} /> : null;
      })}
      {grid.map((l, i) => {
        const at = P(l.terminal![0] * sp, l.terminal![1] * sp, 6);
        return (
          <g key={l.id}>
            <Pylon at={at} />
            {i === 0 && <text x={at[0]} y={at[1] + 18} textAnchor="middle" className="tile-label muted">State grid</text>}
          </g>
        );
      })}
      {order.map((d) => <Tile key={d.id} d={d} selected={selected === d.id} onSelect={onSelect} sp={sp} />)}
      {/* labels last, so neighbouring tiles never cover a name */}
      {order.map((d) => {
        const [, by] = P(d.x * sp + TILE, d.y * sp + TILE);
        const [cx] = P(d.x * sp, d.y * sp);
        return (
          <text key={`l-${d.id}`} x={cx} y={by + 20} textAnchor="middle" pointerEvents="none"
            className={`tile-label ${d.status === "dark" ? "bad" : ""} ${selected === d.id ? "sel" : ""}`}>{d.name}</text>
        );
      }).filter(Boolean)}
    </svg>
  );
}
