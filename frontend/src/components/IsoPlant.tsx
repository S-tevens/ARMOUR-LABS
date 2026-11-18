import type { Incident, Telemetry } from "../types";

// Isometric projection. u runs down-right, v runs down-left, z is height in pixels.
const S = 62;
const K = S * 0.866;
const H = S * 0.5;
const OX = 150;
const OY = 168;
export const VB_W = 820;
export const VB_H = 430;

const P = (u: number, v: number, z = 0): [number, number] => [OX + (u - v) * K, OY + (u + v) * H - z];
const pts = (a: [number, number][]) => a.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
/** Position as a percentage of the viewBox, for HTML callouts layered over the SVG. */
export const pct = (u: number, v: number, z = 0) => {
  const [x, y] = P(u, v, z);
  return { left: `${(x / VB_W) * 100}%`, top: `${(y / VB_H) * 100}%` };
};

function slab(u0: number, u1: number, v0: number, v1: number, depth: number, fill: string, side: string) {
  const top = [P(u0, v0), P(u1, v0), P(u1, v1), P(u0, v1)];
  const down = (p: [number, number]): [number, number] => [p[0], p[1] + depth];
  return (
    <g>
      <polygon points={pts([top[3], top[2], down(top[2]), down(top[3])])} fill={side} />
      <polygon points={pts([top[2], top[1], down(top[1]), down(top[2])])} fill={side} opacity={0.8} />
      <polygon points={pts(top)} fill={fill} />
    </g>
  );
}

function Tank({ u, v, r, h, level, id }: { u: number; v: number; r: number; h: number; level: number; id: string }) {
  const [cx, cy] = P(u, v);
  const rx = r * K * 1.414;
  const ry = r * H * 1.414;
  const fillH = (Math.max(0, Math.min(100, level)) / 100) * h;
  const body = `M ${cx - rx} ${cy - h} L ${cx - rx} ${cy} A ${rx} ${ry} 0 0 0 ${cx + rx} ${cy} L ${cx + rx} ${cy - h} Z`;
  const water = `M ${cx - rx} ${cy - fillH} L ${cx - rx} ${cy} A ${rx} ${ry} 0 0 0 ${cx + rx} ${cy} L ${cx + rx} ${cy - fillH} Z`;
  return (
    <g>
      <ellipse cx={cx} cy={cy + 4} rx={rx + 4} ry={ry + 3} fill="rgba(60,80,140,0.12)" />
      <path d={body} fill={`url(#glass-${id})`} stroke="rgba(255,255,255,0.95)" strokeWidth={1.5} />
      <path d={water} fill={`url(#water-${id})`} />
      <ellipse cx={cx} cy={cy - fillH} rx={rx} ry={ry} fill="rgba(120,170,255,0.55)" />
      <ellipse cx={cx} cy={cy - h} rx={rx} ry={ry} fill="rgba(255,255,255,0.55)" stroke="rgba(255,255,255,0.95)" strokeWidth={1.5} />
      <defs>
        <linearGradient id={`glass-${id}`} x1="0" x2="1">
          <stop offset="0" stopColor="rgba(255,255,255,0.85)" />
          <stop offset="0.5" stopColor="rgba(235,242,255,0.55)" />
          <stop offset="1" stopColor="rgba(205,220,248,0.7)" />
        </linearGradient>
        <linearGradient id={`water-${id}`} x1="0" x2="1">
          <stop offset="0" stopColor="#5E96FF" stopOpacity={0.75} />
          <stop offset="1" stopColor="#2F6BFF" stopOpacity={0.85} />
        </linearGradient>
      </defs>
    </g>
  );
}

function Pump({ u, v, on }: { u: number; v: number; on: boolean }) {
  const [cx, cy] = P(u, v);
  const rx = 0.42 * K * 1.414;
  const ry = 0.42 * H * 1.414;
  const h = 34;
  return (
    <g>
      <ellipse cx={cx} cy={cy + 3} rx={rx + 3} ry={ry + 2} fill="rgba(60,80,140,0.14)" />
      <path d={`M ${cx - rx} ${cy - h} L ${cx - rx} ${cy} A ${rx} ${ry} 0 0 0 ${cx + rx} ${cy} L ${cx + rx} ${cy - h} Z`} fill="#E6ECF8" stroke="#fff" strokeWidth={1.5} />
      <ellipse cx={cx} cy={cy - h} rx={rx} ry={ry} fill="#F6F8FD" stroke="#fff" strokeWidth={1.5} />
      <circle cx={cx} cy={cy - h} r={5} fill={on ? "var(--green)" : "#B8C2D8"} className={on ? "led" : ""} />
    </g>
  );
}

function Box({ u, v, w, d, h, top, side }: { u: number; v: number; w: number; d: number; h: number; top: string; side: string }) {
  const u0 = u - w / 2, u1 = u + w / 2, v0 = v - d / 2, v1 = v + d / 2;
  return (
    <g>
      <polygon points={pts([P(u0, v1), P(u1, v1), P(u1, v1, h), P(u0, v1, h)])} fill={side} />
      <polygon points={pts([P(u1, v0), P(u1, v1), P(u1, v1, h), P(u1, v0, h)])} fill={side} opacity={0.78} />
      <polygon points={pts([P(u0, v0, h), P(u1, v0, h), P(u1, v1, h), P(u0, v1, h)])} fill={top} stroke="#fff" strokeWidth={1} />
    </g>
  );
}

export default function IsoPlant({ t, incident }: { t: Telemetry; incident: Incident | undefined }) {
  const flowing = t.flow > 5;
  const dur = flowing ? Math.max(0.35, 140 / t.flow) : 0;
  const blocked = !t.valve1;
  const pipeZ = 22;
  const route = pts([P(0.85, 0, pipeZ), P(5, 0, pipeZ), P(5, -2.55, pipeZ)]);
  const route2 = pts([P(5, -4.25, pipeZ), P(5, -4.8, pipeZ)]);
  const out = pts([P(5, -5.6, pipeZ), P(5, -6.2, pipeZ)]);
  const flowCls = `pipe-flow ${blocked ? "blocked" : ""}`;
  const style = flowing ? { animationDuration: `${dur}s` } : { animation: "none", opacity: 0 };
  const alarm = incident && incident.status !== "recovered";

  return (
    <svg viewBox={`0 0 ${VB_W} ${VB_H}`} className="iso" role="img" aria-label="Live isometric plant view">
      {/* floor */}
      {slab(-1.3, 6.0, -1.1, 1.1, 14, "rgba(255,255,255,0.8)", "rgba(190,203,232,0.7)")}
      {slab(3.9, 6.1, -6.3, 1.1, 14, "rgba(255,255,255,0.8)", "rgba(190,203,232,0.7)")}
      {alarm && <polygon points={pts([P(3.9, -6.3), P(6.1, -6.3), P(6.1, 1.1), P(3.9, 1.1)])} fill="rgba(229,72,77,0.06)" />}

      {/* pipes */}
      {[route, route2, out].map((d, i) => (
        <g key={i}>
          <polyline points={d} className="pipe-base" />
          <polyline points={d} className={flowCls} style={style} />
        </g>
      ))}

      {/* equipment, back to front */}
      <Pump u={5} v={-5.2} on={t.pump2} />
      <Tank u={0} v={0} r={0.85} h={104} level={t.tank1_level} id="t1" />
      <Tank u={5} v={-3.4} r={0.85} h={104} level={t.tank2_level} id="t2" />
      <Pump u={2} v={0} on={t.pump1} />
      <Box u={3.4} v={0} w={1.1} d={0.8} h={34} top="#F6F8FD" side="#D5DDF0" />
      <g>
        <Box u={5} v={-1.5} w={0.55} d={0.55} h={24} top={blocked ? "#FFE3E4" : "#DDF5E7"} side={blocked ? "#F2B4B7" : "#B7E3C9"} />
        <circle cx={P(5, -1.5, 24)[0]} cy={P(5, -1.5, 24)[1]} r={6} fill={blocked ? "var(--red)" : "var(--green)"} className={blocked ? "led alarm" : "led"} />
      </g>
    </svg>
  );
}
