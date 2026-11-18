import { useState } from "react";
import type { PlcState, Telemetry, TwinState } from "../types";

type Key = "plc01" | "plc02" | "plc03";
interface Row { name: string; reading: string; ok: boolean; pill: string }

const LABEL: Record<PlcState, string> = { normal: "Normal", suspicious: "Suspicious", compromised: "Compromised" };

function buildRows(t: Telemetry, twin: TwinState | null): Record<Key, Row[]> {
  const off = (k: string) => (twin ? Math.abs(twin.norm_residual[k] ?? 0) > 4 : false);
  return {
    plc01: [
      { name: "Pump 1", reading: t.pump1 ? "Running" : "Stopped", ok: t.pump1, pill: t.pump1 ? "Running" : "Stopped" },
      { name: "Pump 2", reading: t.pump2 ? "Running" : "Stopped", ok: t.pump2, pill: t.pump2 ? "Running" : "Stopped" },
    ],
    plc02: [{ name: "Valve 1", reading: t.valve1 ? "Open" : "Closed", ok: t.valve1, pill: t.valve1 ? "Open" : "Closed" }],
    plc03: [
      { name: "Pressure", reading: `${t.pressure.toFixed(2)} bar`, ok: !off("pressure"), pill: off("pressure") ? "Off twin" : "In range" },
      { name: "Flow", reading: `${t.flow.toFixed(0)} L/min`, ok: !off("flow"), pill: off("flow") ? "Off twin" : "In range" },
      { name: "Temperature", reading: `${t.temperature.toFixed(1)} °C`, ok: !off("temperature"), pill: off("temperature") ? "Off twin" : "In range" },
    ],
  };
}

const Chevron = ({ open }: { open: boolean }) => (
  <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" style={{ transform: open ? "rotate(180deg)" : undefined, transition: "transform .2s" }}>
    <path d="M3 5.5 7 9.5 11 5.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const ChipIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
    <rect x="4" y="4" width="12" height="12" rx="3" fill="none" stroke="currentColor" strokeWidth="1.5" />
    <path d="M8 1.5v2.5M12 1.5v2.5M8 16v2.5M12 16v2.5M1.5 8h2.5M1.5 12h2.5M16 8h2.5M16 12h2.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
  </svg>
);

export default function ControllerRail({ t, twin }: { t: Telemetry | null; twin: TwinState | null }) {
  const [filter, setFilter] = useState<"all" | "normal" | "attention">("all");
  const [open, setOpen] = useState<Record<string, boolean>>({ plc01: true, plc02: true, plc03: true });
  const rows = t ? buildRows(t, twin) : null;
  const ids: { key: Key; id: string }[] = [
    { key: "plc01", id: "PLC-01" },
    { key: "plc02", id: "PLC-02" },
    { key: "plc03", id: "PLC-03" },
  ];
  const attention = (k: Key) => !!t && !!rows && (t.plc_status[k] !== "normal" || rows[k].some((r) => !r.ok));
  const counts = { all: ids.length, normal: ids.filter((x) => !attention(x.key)).length, attention: ids.filter((x) => attention(x.key)).length };
  const shown = ids.filter((x) => filter === "all" || (filter === "attention") === attention(x.key));

  return (
    <aside className="rail glass" aria-label="Controllers">
      <h2>Controllers</h2>
      <div className="chips" role="tablist" aria-label="Filter controllers">
        <button role="tab" aria-selected={filter === "all"} className={filter === "all" ? "on" : ""} onClick={() => setFilter("all")}>All</button>
        <button role="tab" aria-selected={filter === "normal"} className={filter === "normal" ? "on" : ""} onClick={() => setFilter("normal")}><i className="dot green" /> Normal {counts.normal}</button>
        <button role="tab" aria-selected={filter === "attention"} className={filter === "attention" ? "on" : ""} onClick={() => setFilter("attention")}><i className="dot red" /> Attention {counts.attention}</button>
      </div>
      {!t && <p className="empty">Waiting for the plant…</p>}
      {t && shown.length === 0 && <p className="empty">No controllers match this filter.</p>}
      {t && rows && shown.map(({ key, id }) => {
        const st = t.plc_status[key];
        const isOpen = open[key];
        return (
          <article className={`plc ${st}`} key={id}>
            <button className="plc-head" aria-expanded={isOpen} onClick={() => setOpen((o) => ({ ...o, [key]: !o[key] }))}>
              <span className="plc-icon"><ChipIcon /></span>
              <span className="plc-name">
                <b>{id}</b>
                <span className={`state-line ${st}`}><i /> {LABEL[st]}</span>
              </span>
              <Chevron open={isOpen} />
            </button>
            {isOpen && (
              <table className="mini">
                <thead><tr><th>Device</th><th>Reading</th><th>Status</th></tr></thead>
                <tbody>
                  {rows[key].map((r) => (
                    <tr key={r.name}>
                      <td><i className={`dot ${r.ok ? "green" : "red"}`} /> {r.name}</td>
                      <td>{r.reading}</td>
                      <td><span className={`pill ${r.ok ? "ok" : "bad"}`}>{r.pill}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </article>
        );
      })}
    </aside>
  );
}
