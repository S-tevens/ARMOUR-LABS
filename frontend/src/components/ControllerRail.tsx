import { useState } from "react";
import type { IedState, Telemetry, TwinState } from "../types";

type Key = "ied01" | "ied02" | "ied03";
interface Row { name: string; reading: string; ok: boolean; pill: string }

const LABEL: Record<IedState, string> = { normal: "Normal", suspicious: "Suspicious", compromised: "Compromised" };
const kw = (v: number) => `${v.toFixed(0)} kW`;
const closed = (b: boolean): Pick<Row, "reading" | "ok" | "pill"> => ({ reading: b ? "Closed" : "Open", ok: b, pill: b ? "Closed" : "Open" });

function buildRows(t: Telemetry, twin: TwinState | null): Record<Key, Row[]> {
  const off = (k: string) => (twin ? Math.abs(twin.norm_residual[k] ?? 0) > 4 : false);
  const meter = (name: string, key: string, reading: string): Row => ({ name, reading, ok: !off(key), pill: off(key) ? "Off twin" : "In range" });
  return {
    ied01: [
      { name: "Main breaker", ...closed(t.cb_main) },
      meter("Frequency", "frequency", `${t.frequency.toFixed(2)} Hz`),
      meter("Bus voltage", "bus_voltage", `${t.bus_voltage.toFixed(3)} pu`),
      meter("Utility import", "grid_import_kw", kw(t.grid_import_kw)),
    ],
    ied02: [
      { name: "PV breaker", ...closed(t.cb_pv) },
      meter("PV output", "pv_kw", kw(t.pv_kw)),
      { name: "Battery breaker", ...closed(t.cb_bess) },
      meter("Battery power", "bess_kw", `${t.bess_kw >= 0 ? "+" : ""}${t.bess_kw.toFixed(0)} kW`),
    ],
    ied03: [
      { name: "Hospital breaker", ...closed(t.cb_crit) },
      meter("Hospital load", "load_critical_kw", kw(t.load_critical_kw)),
      { name: "Campus breaker", ...closed(t.cb_nc) },
      meter("Campus load", "load_noncritical_kw", kw(t.load_noncritical_kw)),
    ],
  };
}

const Chevron = ({ open }: { open: boolean }) => (
  <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" style={{ transform: open ? "rotate(180deg)" : undefined, transition: "transform .2s" }}>
    <path d="M3 5.5 7 9.5 11 5.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const RelayIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
    <rect x="3.5" y="3.5" width="13" height="13" rx="3" fill="none" stroke="currentColor" strokeWidth="1.5" />
    <path d="M6.5 11.5 9 8l1.8 2.6L13.5 7" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const IEDS: { key: Key; id: string; role: string }[] = [
  { key: "ied01", id: "IED-01", role: "Utility interface" },
  { key: "ied02", id: "IED-02", role: "Solar and battery" },
  { key: "ied03", id: "IED-03", role: "Load feeders" },
];

export default function ControllerRail({ t, twin }: { t: Telemetry | null; twin: TwinState | null }) {
  const [filter, setFilter] = useState<"all" | "normal" | "attention">("all");
  const [open, setOpen] = useState<Record<string, boolean>>({ ied01: false, ied02: false, ied03: true });
  const rows = t ? buildRows(t, twin) : null;
  const attention = (k: Key) => !!t && !!rows && (t.ied_status[k] !== "normal" || rows[k].some((r) => !r.ok));
  const counts = { normal: IEDS.filter((x) => !attention(x.key)).length, attention: IEDS.filter((x) => attention(x.key)).length };
  const shown = IEDS.filter((x) => filter === "all" || (filter === "attention") === attention(x.key));

  return (
    <aside className="rail glass" aria-label="Protection relays">
      <h2>Protection relays</h2>
      <div className="chips" role="tablist" aria-label="Filter relays">
        <button role="tab" aria-selected={filter === "all"} className={filter === "all" ? "on" : ""} onClick={() => setFilter("all")}>All</button>
        <button role="tab" aria-selected={filter === "normal"} className={filter === "normal" ? "on" : ""} onClick={() => setFilter("normal")}><i className="dot green" /> Normal {counts.normal}</button>
        <button role="tab" aria-selected={filter === "attention"} className={filter === "attention" ? "on" : ""} onClick={() => setFilter("attention")}><i className="dot red" /> Attention {counts.attention}</button>
      </div>
      {!t && <p className="empty">Waiting for the substation…</p>}
      {t && shown.length === 0 && <p className="empty">No relays match this filter.</p>}
      {t && rows && shown.map(({ key, id, role }) => {
        const st = t.ied_status[key];
        // Open automatically when a relay needs attention.
        const isOpen = open[key] || attention(key);
        return (
          <article className={`ied ${st}`} key={id}>
            <button className="ied-head" aria-expanded={isOpen} onClick={() => setOpen((o) => ({ ...o, [key]: !isOpen }))}>
              <span className="ied-icon"><RelayIcon /></span>
              <span className="ied-name">
                <b>{id}</b>
                <span className="role">{role}</span>
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
