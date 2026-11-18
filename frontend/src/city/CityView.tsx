import { useState } from "react";
import SimulatorCard from "../components/SimulatorCard";
import type { Incident } from "../types";
import CityRealMap from "./CityRealMap";
import City3DMap from "./City3DMap";
import DistrictCard from "./DistrictCard";
import ImpactStrip from "./ImpactStrip";
import LocalGrid from "./LocalGrid";
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
  const [mapMode, setMapMode] = useState<"3d" | "2d">("3d");
  if (!layout || !state) {
    return <p className="empty">{stream.connected ? "Loading the grid…" : "Waiting for the backend…"}</p>;
  }
  const incidents = Object.values(stream.incidents).sort((a, b) => b.t_start - a.t_start);
  const active: Incident | undefined = incidents.find((i) => i.status === "open" || i.status === "recovering");
  const sel = state.districts.find((d) => d.id === selected);
  const selLayout = layout.districts.find((d) => d.id === selected);

  return (
    <main className="cityview">
      <section className="pagehead">
        <div className="page-title">
          <h1>{layout.name}</h1>
          <span className="muted small" title={layout.data_note ?? undefined}>
            Real substations and line routes from OpenStreetMap. Loads and attacks are simulated. Backup time and energy run accelerated, 1 s is 1 min.
          </span>
        </div>
        <ImpactStrip layout={layout} state={state} unserved={stream.unserved} energy={stream.energy} />
      </section>

      <div className="citystage">
        <WhatsHappening state={state} incident={active} onSelect={setSelected} />

        <section className={`mapwrap real ${mapMode === "3d" ? "spatial" : ""} ${state.status === "incident" ? "alarm" : ""}`} aria-label="City map">
          <div className="map-mode" aria-label="Map view"><button aria-pressed={mapMode === "3d"} onClick={() => setMapMode("3d")}>3D city</button><button aria-pressed={mapMode === "2d"} onClick={() => setMapMode("2d")}>2D map</button></div>
          {mapMode === "3d" ? <City3DMap layout={layout} state={state} selected={selected} onSelect={setSelected} onFallback={() => setMapMode("2d")} /> : <CityRealMap layout={layout} state={state} selected={selected} onSelect={setSelected} />}
          {active && (
            <div className="alert glass" role="alert">
              <b>{CAUSE[active.classification]}</b>
              {active.campaign_id && <span className="pill neutral">Campaign</span>}
              {active.status === "open" && <button className="btn primary" onClick={() => onApprove(active.id)}>Approve containment</button>}
              {active.status === "recovering" && <span className="muted">Restoring the grid…</span>}
            </div>
          )}
          <ul className="legend-map" aria-label="Legend">
            <li><i className={`dot ${mapMode === "3d" ? "cyan" : "green"}`} /> Supplied</li>
            <li><i className="dot amber" /> Needs attention</li>
            <li><i className="dot red" /> Without power</li>
            {mapMode === "2d" && <><li><i className="ln solid" /> Mapped line</li><li><i className="ln dashed" /> Inferred tie</li></>}
          </ul>
          {selected && <LocalGrid layout={layout} state={state} id={selected} onClose={() => setSelected(null)} onOpen={onOpenSubstation} />}
        </section>

        <div className="cityside">
          <DistrictCard d={sel} lay={selLayout} onOpen={onOpenSubstation} />
          <ResponseCard s={state} />
          <SimulatorCard title="City simulator" scenarios={scenarios} onStart={onStart} onStop={onStop} />
        </div>
      </div>
    </main>
  );
}
