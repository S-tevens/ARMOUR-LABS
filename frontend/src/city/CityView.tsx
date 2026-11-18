import { useState } from "react";
import SimulatorCard from "../components/SimulatorCard";
import type { Incident } from "../types";
import CityMap from "./CityMap";
import DistrictCard from "./DistrictCard";
import ImpactStrip from "./ImpactStrip";
import ResponseCard from "./ResponseCard";
import type { CityScenarioInfo } from "./types";
import type { CityStream } from "./useCityStream";
import WhatsHappening from "./WhatsHappening";

const CAUSE: Record<string, string> = { attack: "Likely attack", fault: "Likely equipment fault", unknown: "Cause not yet known" };

export default function CityView({
  stream, scenarios, onStart, onStop, onApprove, onOpenSubstation,
}: {
  stream: CityStream;
  scenarios: CityScenarioInfo[];
  onStart: (name: string) => void;
  onStop: () => void;
  onApprove: (id: string) => void;
  onOpenSubstation: (district: string) => void;
}) {
  const { layout, state } = stream;
  const [selected, setSelected] = useState<string | null>(null);
  if (!layout || !state) {
    return <p className="empty">{stream.connected ? "Loading the city…" : "Waiting for the backend…"}</p>;
  }
  const incidents = Object.values(stream.incidents).sort((a, b) => b.t_start - a.t_start);
  const active: Incident | undefined = incidents.find((i) => i.status === "open" || i.status === "recovering");
  const sel = state.districts.find((d) => d.id === selected);

  return (
    <main className="cityview">
      <section className="pagehead">
        <div className="page-title">
          <h1>{layout.name.replace(" (fictional network)", "")}</h1>
          <span className="muted small">{layout.note.split(".")[0]}. Backup time and energy run accelerated, 1 s is 1 min.</span>
        </div>
        <ImpactStrip layout={layout} state={state} unserved={stream.unserved} energy={stream.energy} />
      </section>

      <div className="citystage">
        <WhatsHappening state={state} incident={active} onSelect={setSelected} />

        <section className={`mapwrap ${state.status === "incident" ? "alarm" : ""}`} aria-label="City map">
          <CityMap layout={layout} state={state} selected={selected} onSelect={setSelected} />
          {active && (
            <div className="alert glass" role="alert">
              <b>{CAUSE[active.classification]}</b>
              {active.campaign_id && <span className="pill neutral">Campaign</span>}
              {active.status === "open" && <button className="btn primary" onClick={() => onApprove(active.id)}>Approve containment</button>}
              {active.status === "recovering" && <span className="muted">Restoring the city…</span>}
            </div>
          )}
          <ul className="legend-map" aria-label="Legend">
            <li><i className="dot green" /> Supplied</li>
            <li><i className="dot amber" /> Needs attention</li>
            <li><i className="dot red" /> Without power</li>
            <li><i className="flowkey" /> Power flow</li>
          </ul>
        </section>

        <div className="cityside">
          <DistrictCard d={sel} onOpen={onOpenSubstation} />
          <ResponseCard s={state} />
          <SimulatorCard title="City simulator" scenarios={scenarios} onStart={onStart} onStop={onStop} />
        </div>
      </div>
    </main>
  );
}
