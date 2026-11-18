import type { PlcState, Telemetry } from "../types";

const LABEL: Record<PlcState, string> = { normal: "Normal", suspicious: "Suspicious", compromised: "Compromised" };

export default function ControllerRail({ t }: { t: Telemetry | null }) {
  const rows = t
    ? [
        { id: "PLC-01", key: "plc01" as const, detail: [["Pump 1", t.pump1 ? "Running" : "Stopped"], ["Pump 2", t.pump2 ? "Running" : "Stopped"]] },
        { id: "PLC-02", key: "plc02" as const, detail: [["Valve 1", t.valve1 ? "Open" : "Closed"]] },
        { id: "PLC-03", key: "plc03" as const, detail: [["Pressure", `${t.pressure.toFixed(2)} bar`], ["Flow", `${t.flow.toFixed(0)} L/min`], ["Temperature", `${t.temperature.toFixed(1)} °C`]] },
      ]
    : [];
  return (
    <aside className="rail glass" aria-label="Controllers">
      <h2>Controllers</h2>
      {!t && <p className="empty">Waiting for the plant…</p>}
      {rows.map((r) => {
        const st = t!.plc_status[r.key];
        return (
          <article className={`plc ${st}`} key={r.id}>
            <header>
              <b>{r.id}</b>
              <span className={`chip ${st}`}><i /> {LABEL[st]}</span>
            </header>
            <dl>
              {r.detail.map(([k, v]) => (
                <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
              ))}
            </dl>
          </article>
        );
      })}
    </aside>
  );
}
