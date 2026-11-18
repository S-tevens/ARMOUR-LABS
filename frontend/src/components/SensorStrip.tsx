import Spark from "./Spark";
import type { Telemetry, TwinState } from "../types";

type Key = "pressure" | "flow" | "tank1_level" | "tank2_level";

const ITEMS: { key: Key; label: string; unit: string; digits: number; domain: [number, number] }[] = [
  { key: "pressure", label: "Line pressure", unit: "bar", digits: 2, domain: [0, 6] },
  { key: "flow", label: "Flow rate", unit: "L/min", digits: 0, domain: [0, 140] },
  { key: "tank1_level", label: "Tank 1 level", unit: "%", digits: 1, domain: [0, 100] },
  { key: "tank2_level", label: "Tank 2 level", unit: "%", digits: 1, domain: [0, 100] },
];

export default function SensorStrip({ history, twin }: { history: Telemetry[]; twin: TwinState | null }) {
  const now = history[history.length - 1];
  return (
    <section className="strip glass" aria-label="Sensor readings">
      {ITEMS.map((it) => {
        const val = now ? now[it.key] : null;
        const off = twin ? Math.abs(twin.norm_residual[it.key] ?? 0) > 4 : false;
        return (
          <div className="strip-item" key={it.key}>
            <div className="strip-text">
              <span className="label">{it.label}</span>
              <span className="numeral">
                {val === null ? "–" : val.toFixed(it.digits)}
                <small>{it.unit}</small>
              </span>
              <span className={`sub ${off ? "bad" : ""}`}>
                {twin ? (off ? "Away from the twin" : `Twin expects ${twin.expected[it.key].toFixed(it.digits)}`) : " "}
              </span>
            </div>
            <Spark values={history.map((h) => h[it.key])} domain={it.domain} color={off ? "#E5484D" : "#2F6BFF"} />
          </div>
        );
      })}
    </section>
  );
}
