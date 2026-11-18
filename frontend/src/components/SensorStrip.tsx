import Spark from "./Spark";
import type { Telemetry, TwinState } from "../types";

type Key = "pressure" | "flow" | "tank1_level" | "tank2_level";

const ITEMS: { key: Key; label: string; unit: string; digits: number; domain: [number, number] }[] = [
  { key: "pressure", label: "Line pressure", unit: "bar", digits: 2, domain: [0, 6] },
  { key: "flow", label: "Flow rate", unit: "L/min", digits: 0, domain: [0, 140] },
  { key: "tank1_level", label: "Tank 1 level", unit: "%", digits: 1, domain: [0, 100] },
  { key: "tank2_level", label: "Tank 2 level", unit: "%", digits: 1, domain: [0, 100] },
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
