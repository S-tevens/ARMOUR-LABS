import { useState } from "react";
import Meter from "./Meter";
import { HISTORY } from "../useStream";
import type { Telemetry, TwinState } from "../types";

type Key = "grid_import_kw" | "frequency" | "bus_voltage";
const CFG: Record<Key, { label: string; unit: string; digits: number; domain: [number, number]; ticks: number[] }> = {
  grid_import_kw: { label: "Utility import", unit: "kW", digits: 0, domain: [-200, 700], ticks: [-200, 0, 300, 700] },
  frequency: { label: "Frequency", unit: "Hz", digits: 2, domain: [49, 51], ticks: [49, 49.5, 50, 50.5, 51] },
  bus_voltage: { label: "Voltage", unit: "pu", digits: 3, domain: [0.9, 1.1], ticks: [0.9, 0.95, 1, 1.05, 1.1] },
};
const W = 620, Ht = 190, PL = 34, PR = 8, PT = 10, PB = 20;

export default function TwinChart({ history, twinHistory }: { history: Telemetry[]; twinHistory: TwinState[] }) {
  const [key, setKey] = useState<Key>("grid_import_kw");
  const c = CFG[key];
  const n = history.length;
  const off = HISTORY - 1 - (n - 1); // right-align: newest sample at the right edge
  const X = (i: number) => PL + ((i + off) / (HISTORY - 1)) * (W - PL - PR);
  const Y = (v: number) => PT + (1 - (v - c.domain[0]) / (c.domain[1] - c.domain[0])) * (Ht - PT - PB);
  const obs = history.map((h, i) => `${X(i).toFixed(1)},${Y(h[key]).toFixed(1)}`);
  const m = Math.min(history.length, twinHistory.length);
  const exp = twinHistory.slice(-m).map((t, i) => `${X(n - m + i).toFixed(1)},${Y(t.expected[key]).toFixed(1)}`);
  const within = m ? twinHistory.slice(-m).filter((t) => Math.abs(t.norm_residual[key] ?? 0) <= 4).length / m : 1;
  const last = history[n - 1];
  const lastExp = twinHistory[twinHistory.length - 1];

  return (
    <section className="glass chart">
      <header className="panel-head">
        <h2>Expected and observed</h2>
        <div className="seg" role="tablist" aria-label="Variable">
          {(Object.keys(CFG) as Key[]).map((k) => (
            <button key={k} role="tab" aria-selected={key === k} className={key === k ? "on" : ""} onClick={() => setKey(k)}>
              {CFG[k].label}
            </button>
          ))}
        </div>
      </header>
      <div className="chart-readout">
        <div>
          <span className="numeral sm">{last ? last[key].toFixed(c.digits) : "–"}<small>{c.unit}</small></span>
          <span className="sub">{lastExp ? `Twin expects ${lastExp.expected[key].toFixed(c.digits)} ${c.unit}` : ""}</span>
        </div>
        <Meter label="Within twin tolerance" display={`${Math.round(within * 100)}%`} value={within} tone={within > 0.9 ? "green" : within > 0.6 ? "amber" : "red"} />
      </div>
      <svg viewBox={`0 0 ${W} ${Ht}`} className="line-chart" role="img" aria-label={`${c.label} over the last ${n} seconds`}>
        <defs>
          <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#2F6BFF" stopOpacity="0.28" />
            <stop offset="1" stopColor="#2F6BFF" stopOpacity="0" />
          </linearGradient>
        </defs>
        {c.ticks.map((tk) => (
          <g key={tk}>
            <line x1={PL} x2={W - PR} y1={Y(tk)} y2={Y(tk)} className="grid" />
            <text x={PL - 8} y={Y(tk) + 4} textAnchor="end" className="axis">{tk}</text>
          </g>
        ))}
        {n > 1 && (
          <>
            <polygon points={`${obs.join(" ")} ${X(n - 1)},${Y(c.domain[0])} ${X(0)},${Y(c.domain[0])}`} fill="url(#area)" />
            {exp.length > 1 && <polyline points={exp.join(" ")} className="line-exp" />}
            <polyline points={obs.join(" ")} className="line-obs" />
            <circle cx={X(n - 1)} cy={Y(last[key])} r={4.5} className="dot" />
          </>
        )}
      </svg>
      <footer className="legend"><span><i className="k obs" /> Observed</span><span><i className="k exp" /> Expected by the twin</span><span className="muted">Last {n}s</span></footer>
    </section>
  );
}
