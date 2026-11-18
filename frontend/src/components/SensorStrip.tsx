import Spark from "./Spark";
import type { Telemetry, TwinState } from "../types";

type Key = "frequency" | "bus_voltage" | "grid_import_kw" | "bess_soc";

const ITEMS: { key: Key; label: string; unit: string; digits: number; domain: [number, number] }[] = [
  { key: "frequency", label: "Grid frequency", unit: "Hz", digits: 2, domain: [49, 51] },
  { key: "bus_voltage", label: "Bus voltage", unit: "pu", digits: 3, domain: [0.9, 1.1] },
  { key: "grid_import_kw", label: "Utility import", unit: "kW", digits: 0, domain: [-200, 700] },
  { key: "bess_soc", label: "Battery charge", unit: "%", digits: 1, domain: [0, 100] },
];

/** Small square badge with an arrow: direction = which way the reading is off the twin, colour = within tolerance or not. */
function Badge({ residual, bad }: { residual: number; bad: boolean }) {
  const down = residual < 0;
  return (
    <span className={`kpi-badge ${bad ? "bad" : "ok"}`} title={bad ? "Away from the twin's expected value" : "Within the twin's tolerance"}>
      <svg viewBox="0 0 10 10" width="9" height="9" aria-hidden="true" style={{ transform: down ? "rotate(90deg)" : undefined }}>
        <path d="M2 8 L8 2 M3.2 2 H8 V6.8" fill="none" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}

export default function SensorStrip({ history, twin }: { history: Telemetry[]; twin: TwinState | null }) {
  const now = history[history.length - 1];
  return (
    <section className="kpis" aria-label="Sensor readings">
      {ITEMS.map((it) => {
        const val = now ? now[it.key] : null;
        const r = twin?.norm_residual[it.key] ?? 0;
        const bad = Math.abs(r) > 4;
        return (
          <div className="kpi" key={it.key} title={twin ? `Twin expects ${twin.expected[it.key].toFixed(it.digits)} ${it.unit}` : undefined}>
            <div className="kpi-text">
              <span className="numeral">
                {val === null ? "–" : val.toFixed(it.digits)}
                <small>{it.unit}</small>
                {twin && <Badge residual={r} bad={bad} />}
              </span>
              <span className="label">{it.label}</span>
            </div>
            <Spark values={history.map((h) => h[it.key])} domain={it.domain} color={bad ? "#E5484D" : "#2DB56A"} bars={22} />
          </div>
        );
      })}
    </section>
  );
}
