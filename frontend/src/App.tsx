import { useEffect, useState } from "react";
import { approveResponse, getScenarios, startScenario, stopScenario } from "./api";
import { approveCityResponse, getCityScenarios, startCityScenario, stopCityScenario } from "./city/api";
import CityView from "./city/CityView";
import GridGraphPanel from "./city/GridGraph";
import type { CityScenarioInfo } from "./city/types";
import { useCityStream } from "./city/useCityStream";
import ControllerRail from "./components/ControllerRail";
import EventTable from "./components/EventTable";
import IncidentList from "./components/IncidentList";
import IsoPlant, { pct } from "./components/IsoPlant";
import NetworkGraph from "./components/NetworkGraph";
import ScoreBars from "./components/ScoreBars";
import SensorStrip from "./components/SensorStrip";
import SimulatorCard from "./components/SimulatorCard";
import TwinChart from "./components/TwinChart";
import MetricsView from "./metrics/MetricsView";
import { useStream } from "./useStream";
import type { ScenarioInfo } from "./types";

type Tab = "city" | "dashboard" | "network" | "incidents" | "metrics";
const TABS: { id: Tab; label: string }[] = [
  { id: "city", label: "City" },
  { id: "dashboard", label: "Substation" },
  { id: "network", label: "Network" },
  { id: "incidents", label: "Incidents" },
  { id: "metrics", label: "Metrics" },
];

function Callout({ at, title, children, tone = "", below = false }: { at: { left: string; top: string }; title: string; children: React.ReactNode; tone?: string; below?: boolean }) {
  return (
    <div className={`callout glass ${tone} ${below ? "below" : ""}`} style={at}>
      <b>{title}</b>
      <span>{children}</span>
    </div>
  );
}

export default function App() {
  const city = useCityStream();
  const [tab, setTab] = useState<Tab>("city");
  const [district, setDistrict] = useState<string | undefined>(undefined); // undefined = the featured district
  const s = useStream(district);
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [cityScenarios, setCityScenarios] = useState<CityScenarioInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    getScenarios().then(setScenarios).catch(() => setError("Can't reach the backend on port 8000. Start it with: uvicorn main:app"));
    getCityScenarios().then(setCityScenarios).catch(() => undefined);
  }, []);

  const incidents = Object.values(s.incidents).sort((a, b) => b.t_start - a.t_start);
  const active = incidents.find((i) => i.status !== "recovered" && i.status !== "unresolved");
  const cityIncidents = Object.values(city.incidents).sort((a, b) => b.t_start - a.t_start);
  const cityActive = cityIncidents.find((i) => i.status === "open" || i.status === "recovering");
  const cityStatus = city.state?.status ?? "normal";
  const featured = city.layout?.featured;
  const shownDistrict = district ?? featured;
  const districtName = city.layout?.districts.find((d) => d.id === shownDistrict)?.name ?? "Substation";

  const onCity = tab === "city";
  const pill = !city.connected && !s.connected ? "offline" : onCity ? cityStatus : active ? "incident" : "normal";
  const pillText = {
    offline: "Backend offline", incident: "Incident in progress", attention: "City needs attention",
    normal: onCity ? "City normal" : "Substation normal",
  }[pill];
  const run = (fn: () => Promise<unknown>) => fn().then(() => setError(null)).catch((e) => setError(String(e)));
  const t = s.telemetry;
  const openSubstation = (id: string) => { setDistrict(id); setTab("dashboard"); };

  const Breadcrumb = () => (
    <nav className="crumbs" aria-label="Breadcrumb">
      <button onClick={() => setTab("city")}>City</button>
      <span aria-hidden="true">/</span>
      <b>{districtName}</b>
    </nav>
  );

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <img className="brand-logo" src="/logo.png" alt="Armour Labs" height="34" />
          <small>Power-grid cyber defence simulation</small>
        </div>
        <nav className="tabs glass" aria-label="Views">
          {TABS.map((x) => (
            <button key={x.id} className={tab === x.id ? "on" : ""} aria-current={tab === x.id ? "page" : undefined} onClick={() => setTab(x.id)}>
              {x.label}
              {x.id === "incidents" && active && <i className="badge" />}
              {x.id === "city" && cityActive && <i className="badge" />}
            </button>
          ))}
        </nav>
        <div className={`state glass st-${pill}`} role="status"><i />{pillText}</div>
      </header>

      {error && <div className="error" role="alert">{error}</div>}

      {tab === "city" && (
        <CityView
          stream={city}
          scenarios={cityScenarios}
          onStart={(n) => run(() => startCityScenario(n))}
          onStop={() => run(stopCityScenario)}
          onApprove={(id) => run(() => approveCityResponse(id))}
          onOpenSubstation={openSubstation}
        />
      )}

      {tab === "dashboard" && (
        <main className="dash">
          <Breadcrumb />
          <section className="pagehead">
            <div className="page-title">
              <h1>{districtName} substation</h1>
              <span className="muted small">Simulated substation, running for {t ? Math.round(t.t) : 0} s</span>
            </div>
            <SensorStrip history={s.history} twin={s.twin} />
          </section>
          <div className="stage">
            <ControllerRail t={t} twin={s.twin} />
            <section className={`hero ${active ? "alarm" : ""}`} aria-label="Live substation">
              {t ? (
                <div className="scene" style={{ transform: `scale(${zoom})` }}>
                  <IsoPlant t={t} incident={active} />
                  <Callout at={pct(0.2, 0, 58)} title="Utility" tone={t.cb_main && Math.abs(t.frequency - 50) <= 0.2 ? "" : "bad"}>
                    {!t.cb_main ? "Disconnected" : t.grid_import_kw >= 0 ? `Importing ${t.grid_import_kw.toFixed(0)} kW` : `Exporting ${(-t.grid_import_kw).toFixed(0)} kW`}
                    {`, ${t.frequency.toFixed(2)} Hz`}
                  </Callout>
                  <Callout at={pct(3, -3.4, 46)} title="Solar" tone={t.cb_pv && t.pv_kw > 5 ? "" : "bad"}>
                    {t.cb_pv && t.pv_kw > 5 ? `${t.pv_kw.toFixed(0)} kW` : "Offline"}
                  </Callout>
                  <Callout at={pct(5.6, -3.3, 62)} title={`Battery ${t.bess_soc.toFixed(0)}%`}>
                    {Math.abs(t.bess_kw) < 5 ? "Idle" : t.bess_kw > 0 ? `Discharging ${t.bess_kw.toFixed(0)} kW` : `Charging ${(-t.bess_kw).toFixed(0)} kW`}
                  </Callout>
                  <Callout below at={pct(3.7, 4.1, 0)} title={t.cb_crit ? "Hospital feeder" : "Hospital feeder de-energised"} tone={t.cb_crit ? "" : "bad"}>
                    {t.cb_crit ? `${t.load_critical_kw.toFixed(0)} kW` : active?.evidence.find((e) => e.type === "unauthorised_event")?.text ?? "Opened outside the command log"}
                  </Callout>
                  <Callout below at={pct(7.7, 4.2, 0)} title={t.cb_nc ? "Campus feeder" : "Campus feeder open"} tone={t.cb_nc ? "" : "bad"}>
                    {t.cb_nc ? `${t.load_noncritical_kw.toFixed(0)} kW` : "Breaker open"}
                  </Callout>
                </div>
              ) : (
                <p className="empty hero-empty">Waiting for substation telemetry…</p>
              )}
              <div className="zoom glass" role="group" aria-label="Zoom substation view">
                <button aria-label="Zoom in" onClick={() => setZoom((z) => Math.min(1.8, +(z + 0.2).toFixed(1)))}>+</button>
                <button aria-label="Zoom out" onClick={() => setZoom((z) => Math.max(0.8, +(z - 0.2).toFixed(1)))}>&minus;</button>
                <button aria-label="Reset zoom" onClick={() => setZoom(1)}>
                  <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M1.5 5V1.5H5M9 1.5h3.5V5M12.5 9v3.5H9M5 12.5H1.5V9" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
                </button>
              </div>
              <SimulatorCard
                scenarios={scenarios}
                onStart={(n) => run(() => startScenario(n, district))}
                onStop={() => run(() => stopScenario(district))}
              />
              {active && (
                <div className="alert glass" role="alert">
                  <b>{active.id}</b> Cause not yet classified
                  {active.status === "open" && <button className="btn primary" onClick={() => run(() => approveResponse(active.id, district))}>Approve containment</button>}
                  {active.status === "recovering" && <span className="muted">Checking recovery…</span>}
                </div>
              )}
            </section>
          </div>
          <div className={`lower ${active ? "alarm" : ""}`}>
            <TwinChart history={s.history} twinHistory={s.twinHistory} />
            <ScoreBars scores={s.scores} />
          </div>
        </main>
      )}

      {tab === "network" && (
        <main className="stack">
          {city.layout && city.state ? (
            <GridGraphPanel layout={city.layout} state={city.state} onOpenSubstation={openSubstation} />
          ) : (
            <p className="empty">Loading the grid graph…</p>
          )}
          <Breadcrumb />
          <h2 className="section-title">{districtName} substation: control network</h2>
          <NetworkGraph t={t} links={s.links} />
          <EventTable events={s.events} />
        </main>
      )}

      {tab === "metrics" && <MetricsView />}

      {tab === "incidents" && (
        <main className="stack">
          {cityIncidents.length > 0 && (
            <>
              <h2 className="section-title">City incidents</h2>
              <IncidentList incidents={cityIncidents} onApprove={(id) => run(() => approveCityResponse(id))} />
            </>
          )}
          <Breadcrumb />
          <h2 className="section-title">{districtName} substation incidents</h2>
          <IncidentList incidents={incidents} onApprove={(id) => run(() => approveResponse(id, district))} />
        </main>
      )}
    </div>
  );
}
