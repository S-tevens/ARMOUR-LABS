import { useEffect, useState } from "react";
import { approveResponse, getScenarios, startScenario, stopScenario } from "./api";
import ControllerRail from "./components/ControllerRail";
import EventTable from "./components/EventTable";
import IncidentList from "./components/IncidentList";
import IsoPlant, { pct } from "./components/IsoPlant";
import NetworkGraph from "./components/NetworkGraph";
import ScoreBars from "./components/ScoreBars";
import SensorStrip from "./components/SensorStrip";
import SimulatorCard from "./components/SimulatorCard";
import TwinChart from "./components/TwinChart";
import { useStream } from "./useStream";
import type { ScenarioInfo } from "./types";

type Tab = "dashboard" | "network" | "incidents";
const TABS: { id: Tab; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "network", label: "Network" },
  { id: "incidents", label: "Incidents" },
];

function Callout({ at, title, children, tone = "" }: { at: { left: string; top: string }; title: string; children: React.ReactNode; tone?: string }) {
  return (
    <div className={`callout glass ${tone}`} style={at}>
      <b>{title}</b>
      <span>{children}</span>
    </div>
  );
}

export default function App() {
  const s = useStream();
  const [tab, setTab] = useState<Tab>("dashboard");
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getScenarios().then(setScenarios).catch(() => setError("Can't reach the backend on port 8000. Start it with: uvicorn main:app"));
  }, []);

  const incidents = Object.values(s.incidents).sort((a, b) => b.t_start - a.t_start);
  const active = incidents.find((i) => i.status !== "recovered" && i.status !== "unresolved");
  const state = !s.connected ? "offline" : active ? "incident" : "normal";
  const stateText = { offline: "Backend offline", incident: "Incident in progress", normal: "Plant normal" }[state];
  const run = (fn: () => Promise<unknown>) => fn().then(() => setError(null)).catch((e) => setError(String(e)));
  const t = s.telemetry;

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <svg width="30" height="30" viewBox="0 0 30 30" aria-hidden="true">
            <path d="M15 2 L26 6 V15 C26 21 21 25.5 15 28 C9 25.5 4 21 4 15 V6 Z" fill="#2F6BFF" />
            <path d="M15 8 L20 17 H10 Z" fill="#fff" opacity="0.92" />
          </svg>
          <span>Armour Labs<small>Water treatment simulation</small></span>
        </div>
        <nav className="tabs glass" aria-label="Views">
          {TABS.map((x) => (
            <button key={x.id} className={tab === x.id ? "on" : ""} aria-current={tab === x.id ? "page" : undefined} onClick={() => setTab(x.id)}>
              {x.label}
              {x.id === "incidents" && active && <i className="badge" />}
            </button>
          ))}
        </nav>
        <div className={`state glass st-${state}`} role="status"><i />{stateText}</div>
      </header>

      {error && <div className="error" role="alert">{error}</div>}

      {tab === "dashboard" && (
        <main className="dash">
          <SensorStrip history={s.history} twin={s.twin} />
          <div className="stage">
            <ControllerRail t={t} />
            <section className={`hero ${active ? "alarm" : ""}`} aria-label="Live plant">
              {t ? (
                <>
                  <IsoPlant t={t} incident={active} />
                  <Callout at={pct(0, 0, 150)} title="Tank 1">{t.tank1_level.toFixed(1)}% full</Callout>
                  <Callout at={pct(5, -3.4, 150)} title="Tank 2">{t.tank2_level.toFixed(1)}% full</Callout>
                  <Callout at={pct(5, 0, 70)} title="Line pressure" tone={t.pressure > 3.5 ? "bad" : ""}>{t.pressure.toFixed(2)} bar</Callout>
                  <Callout at={pct(5, -1.5, 86)} title={`Valve 1 ${t.valve1 ? "open" : "closed"}`} tone={t.valve1 ? "" : "bad"}>
                    {t.valve1 ? "PLC-02 normal" : active?.evidence.find((e) => e.type === "unauthorised_event")?.text ?? "Closed outside the schedule"}
                  </Callout>
                </>
              ) : (
                <p className="empty hero-empty">Waiting for plant telemetry…</p>
              )}
              <SimulatorCard
                scenarios={scenarios}
                onStart={(n) => run(() => startScenario(n))}
                onStop={() => run(stopScenario)}
              />
              {active && (
                <div className="alert glass" role="alert">
                  <b>{active.id}</b> Cause not yet classified
                  {active.status === "open" && <button className="btn primary" onClick={() => run(() => approveResponse(active.id))}>Approve containment</button>}
                  {active.status === "recovering" && <span className="muted">Checking recovery…</span>}
                </div>
              )}
            </section>
          </div>
          <div className="lower">
            <TwinChart history={s.history} twinHistory={s.twinHistory} />
            <ScoreBars scores={s.scores} />
          </div>
        </main>
      )}

      {tab === "network" && (
        <main className="stack">
          <NetworkGraph t={t} links={s.links} />
          <EventTable events={s.events} />
        </main>
      )}

      {tab === "incidents" && (
        <main className="stack">
          <IncidentList incidents={incidents} onApprove={(id) => run(() => approveResponse(id))} />
        </main>
      )}
    </div>
  );
}
