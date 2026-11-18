import type { Incident, Telemetry } from "../types";

// Isometric projection. u runs down-right, v runs down-left, z is height in pixels.
const S = 46;
const K = S * 0.866;
const H = S * 0.5;
const OX = 260;
const OY = 150;
export const VB_W = 800;
export const VB_H = 490;
const BUS_Z = 18;

type Pt = [number, number];
const P = (u: number, v: number, z = 0): Pt => [OX + (u - v) * K, OY + (u + v) * H - z];
const pts = (a: Pt[]) => a.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
/** Position as a percentage of the viewBox, for HTML callouts layered over the SVG. */
export const pct = (u: number, v: number, z = 0) => {
  const [x, y] = P(u, v, z);
  return { left: `${(x / VB_W) * 100}%`, top: `${(y / VB_H) * 100}%` };
};

function Slab({ u0, u1, v0, v1, depth }: { u0: number; u1: number; v0: number; v1: number; depth: number }) {
  const top = [P(u0, v0), P(u1, v0), P(u1, v1), P(u0, v1)];
  const down = (p: Pt): Pt => [p[0], p[1] + depth];
  return (
    <g>
      <polygon points={pts([top[3], top[2], down(top[2]), down(top[3])])} fill="rgba(190,203,232,0.7)" />
      <polygon points={pts([top[2], top[1], down(top[1]), down(top[2])])} fill="rgba(190,203,232,0.55)" />
      <polygon points={pts(top)} fill="rgba(255,255,255,0.82)" />
      {[-4, -2, 0, 2, 4].map((v) => <polyline key={`v${v}`} points={pts([P(u0, v), P(u1, v)])} className="floor-line" />)}
      {[0, 2, 4, 6, 8].map((u) => <polyline key={`u${u}`} points={pts([P(u, v0), P(u, v1)])} className="floor-line" />)}
    </g>
  );
}

function Box({ u, v, w, d, h, top, side, alarm = false }: { u: number; v: number; w: number; d: number; h: number; top: string; side: string; alarm?: boolean }) {
  const u0 = u - w / 2, u1 = u + w / 2, v0 = v - d / 2, v1 = v + d / 2;
  const stroke = alarm ? "var(--red)" : "#fff";
  return (
    <g>
      <ellipse cx={P(u, v)[0] + 6} cy={P(u, v)[1] + 3} rx={w * K * 0.95} ry={w * H * 0.55} fill="rgba(60,80,140,0.10)" />
      <polygon points={pts([P(u0, v1), P(u1, v1), P(u1, v1, h), P(u0, v1, h)])} fill={side} stroke={stroke} strokeWidth={alarm ? 1.6 : 0.6} />
      <polygon points={pts([P(u1, v0), P(u1, v1), P(u1, v1, h), P(u1, v0, h)])} fill={side} opacity={0.78} stroke={stroke} strokeWidth={alarm ? 1.6 : 0.6} />
      <polygon points={pts([P(u0, v0, h), P(u1, v0, h), P(u1, v1, h), P(u0, v1, h)])} fill={top} stroke={stroke} strokeWidth={alarm ? 1.6 : 1} />
    </g>
  );
}

/** Power line. Dashes animate along the line when power flows; `rev` flips the direction. */
function Wire({ path, on, kw, rev }: { path: Pt[]; on: boolean; kw: number; rev: boolean }) {
  const flowing = on && Math.abs(kw) > 5;
  const dur = Math.max(0.45, 2.6 - Math.abs(kw) / 200);
  const d = pts(path);
  return (
    <g>
      <polyline points={d} className={on ? "pipe-base" : "pipe-base off"} />
      {flowing && <polyline points={d} className={`pipe-flow${rev ? " rev" : ""}`} style={{ animationDuration: `${dur}s` }} />}
    </g>
  );
}

/** A feeder from the bus (a) through a breaker (br) to a device (b). rev = power flows from the device toward the bus. */
function Feeder({ a, br, b, closed, kw, rev }: { a: Pt; br: Pt; b: Pt; closed: boolean; kw: number; rev: boolean }) {
  return (
    <g>
      <Wire path={[a, br]} on={closed} kw={kw} rev={rev} />
      <Wire path={[br, b]} on={closed} kw={kw} rev={rev} />
    </g>
  );
}

function Breaker({ u, v, closed, label, alarm }: { u: number; v: number; closed: boolean; label: string; alarm?: boolean }) {
  const [x, y] = P(u, v, 34);
  return (
    <g>
      <Box u={u} v={v} w={0.36} d={0.36} h={14} top={closed ? "#DDF5E7" : "#FFE3E4"} side={closed ? "#B7E3C9" : "#F2B4B7"} alarm={alarm} />
      <circle cx={P(u, v, 14)[0]} cy={P(u, v, 14)[1]} r={3.5} fill={closed ? "var(--green)" : "var(--red)"} className={closed ? "" : "led alarm"} />
      <text x={x} y={y} textAnchor="middle" className="svg-small">{label}</text>
    </g>
  );
}

function Pylon() {
  const [x, y] = P(-0.9, 0.2);
  return (
    <g stroke="#A9B6D3" strokeWidth={2} fill="none" strokeLinecap="round" strokeLinejoin="round">
      <path d={`M ${x - 16} ${y} L ${x} ${y - 100} L ${x + 16} ${y}`} />
      <path d={`M ${x - 11} ${y - 36} H ${x + 11} M ${x - 7} ${y - 68} H ${x + 7} M ${x - 12} ${y - 36} L ${x + 7} ${y - 68} M ${x + 12} ${y - 36} L ${x - 7} ${y - 68}`} strokeWidth={1.4} />
      <path d={`M ${x - 26} ${y - 88} H ${x + 26} M ${x - 22} ${y - 72} H ${x + 22}`} strokeWidth={2.4} />
    </g>
  );
}

export default function IsoPlant({ t, incident }: { t: Telemetry; incident: Incident | undefined }) {
  const alarm = incident && incident.status !== "recovered";
  const energised = t.cb_main || t.pv_kw > 5 || Math.abs(t.bess_kw) > 5;
  const soc = Math.max(0, Math.min(100, t.bess_soc));
  const socColor = soc < 20 ? "var(--red)" : soc < 35 ? "var(--amber)" : "var(--green)";
  const pvOn = t.cb_pv && t.pv_kw > 5;

  // key points
  const busA = P(1.5, 0, BUS_Z), busB = P(8.2, 0, BUS_Z);
  const hospitalOn = t.cb_crit && t.load_critical_kw > 5;
  const campusOn = t.cb_nc && t.load_noncritical_kw > 5;

  return (
    <svg viewBox={`0 0 ${VB_W} ${VB_H}`} className="iso" role="img" aria-label="Live isometric substation view">
      <Slab u0={-1.4} u1={8.8} v0={-4.4} v1={4.4} depth={12} />
      {alarm && <polygon points={pts([P(-1.4, -4.4), P(8.8, -4.4), P(8.8, 4.4), P(-1.4, 4.4)])} fill="rgba(229,72,77,0.05)" />}

      {/* utility connection and bus */}
      <Wire path={[P(0.6, 0, BUS_Z), busA]} on kw={t.grid_import_kw} rev={t.grid_import_kw < 0} />
      <Wire path={[busA, P(4, 0, BUS_Z)]} on={energised && t.cb_main} kw={t.grid_import_kw} rev={t.grid_import_kw < 0} />
      <Wire path={[P(4, 0, BUS_Z), busB]} on={energised} kw={0} rev={false} />

      {/* feeders: PV and battery (sources), hospital and campus (loads) */}
      <Feeder a={P(3, 0, BUS_Z)} br={P(3, -1.2, BUS_Z)} b={P(3, -2.4, BUS_Z)} closed={t.cb_pv} kw={t.pv_kw} rev />
      <Feeder a={P(5.6, 0, BUS_Z)} br={P(5.6, -1.2, BUS_Z)} b={P(5.6, -2.4, BUS_Z)} closed={t.cb_bess} kw={t.bess_kw} rev={t.bess_kw > 0} />
      <Feeder a={P(4, 0, BUS_Z)} br={P(4, 1.2, BUS_Z)} b={P(4, 2.3, BUS_Z)} closed={t.cb_crit} kw={t.load_critical_kw} rev={false} />
      <Feeder a={P(7, 0, BUS_Z)} br={P(7, 1.2, BUS_Z)} b={P(7, 2.3, BUS_Z)} closed={t.cb_nc} kw={t.load_noncritical_kw} rev={false} />
      {[P(3, 0, BUS_Z), P(4, 0, BUS_Z), P(5.6, 0, BUS_Z), P(7, 0, BUS_Z), busA].map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={4} className={`node ${energised ? "ok" : "bad"}`} />
      ))}

      {/* equipment, back to front */}
      <Pylon />
      <Box u={0.2} v={0} w={1.0} d={0.8} h={26} top="#F6F8FD" side="#D5DDF0" />
      <Breaker u={1.5} v={0} closed={t.cb_main} label="CB-MAIN" alarm={!t.cb_main} />

      {/* PV array: 3 x 2 panels */}
      {[2.3, 3.0, 3.7].flatMap((u) => [-3.0, -3.7].map((v) => (
        <Box key={`${u}${v}`} u={u} v={v} w={0.62} d={0.55} h={5} top={pvOn ? "#3F73E8" : "#B9C5DD"} side={pvOn ? "#9DB6EE" : "#D3DAEA"} />
      )))}
      <Breaker u={3} v={-1.2} closed={t.cb_pv} label="CB-PV" alarm={!t.cb_pv} />

      {/* battery container with a charge bar on top */}
      <Box u={5.6} v={-3.3} w={1.8} d={0.9} h={30} top="#F6F8FD" side="#D5DDF0" />
      <polygon points={pts([P(4.85, -3.45, 31), P(6.35, -3.45, 31), P(6.35, -3.15, 31), P(4.85, -3.15, 31)])} fill="#DDE3F0" />
      <polygon points={pts([P(4.85, -3.45, 31.5), P(4.85 + 1.5 * (soc / 100), -3.45, 31.5), P(4.85 + 1.5 * (soc / 100), -3.15, 31.5), P(4.85, -3.15, 31.5)])} fill={socColor} />
      <Breaker u={5.6} v={-1.2} closed={t.cb_bess} label="CB-BESS" alarm={!t.cb_bess} />

      {/* hospital: white building with a red cross on its front face */}
      <Breaker u={4} v={1.2} closed={t.cb_crit} label="CB-CRIT" alarm={!t.cb_crit} />
      <Box u={4.0} v={3.3} w={1.7} d={1.4} h={40} top={hospitalOn ? "#F6F8FD" : "#C9CEDB"} side={hospitalOn ? "#E3E9F6" : "#AEB5C6"} alarm={!t.cb_crit} />
      <polygon points={pts([P(4.85, 2.95, 24), P(4.85, 3.65, 24), P(4.85, 3.65, 30), P(4.85, 2.95, 30)])} fill={hospitalOn ? "var(--red)" : "#9aa4bc"} />
      <polygon points={pts([P(4.85, 3.2, 17), P(4.85, 3.4, 17), P(4.85, 3.4, 37), P(4.85, 3.2, 37)])} fill={hospitalOn ? "var(--red)" : "#9aa4bc"} />

      {/* campus: two buildings */}
      <Breaker u={7} v={1.2} closed={t.cb_nc} label="CB-NC" alarm={false} />
      <Box u={6.6} v={3.2} w={1.1} d={1.0} h={26} top={campusOn ? "#F6F8FD" : "#D5DAE6"} side={campusOn ? "#E3E9F6" : "#BDC4D4"} />
      <Box u={7.6} v={3.4} w={1.0} d={1.2} h={34} top={campusOn ? "#F6F8FD" : "#D5DAE6"} side={campusOn ? "#E3E9F6" : "#BDC4D4"} />
    </svg>
  );
}
