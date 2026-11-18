import Spark from "../components/Spark";
import type { CityLayout, CityState } from "./types";

/** 2,450,000 -> "2.45 M", 18,000 -> "18 k". Plain units first. */
export function people(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)} M`;
  if (n >= 1_000) return `${Math.round(n / 1_000)} k`;
  return String(n);
}

function Badge({ bad }: { bad: boolean }) {
  return (
    <span className={`kpi-badge ${bad ? "bad" : "ok"}`} title={bad ? "Needs attention" : "All clear"}>
      <svg viewBox="0 0 10 10" width="9" height="9" aria-hidden="true">
        {bad ? <path d="M5 2v4M5 8v.2" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" /> : <path d="M2 5.2 4.2 7.4 8 3" fill="none" stroke="#fff" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />}
      </svg>
    </span>
  );
}

export default function ImpactStrip({
  layout, state, unserved, energy,
}: { layout: CityLayout; state: CityState; unserved: number[]; energy: number[] }) {
  const im = state.impact;
  const totalPeople = layout.districts.reduce((a, d) => a + d.population, 0);
  const hospitals = layout.districts.reduce((a, d) => a + d.facilities.filter((f) => f.type === "hospital").length, 0);
  const atRisk = im.hospitals_on_backup + im.hospitals_down;
  const supplied = Math.round(100 * (1 - im.people_unserved / totalPeople));
  return (
    <section className="kpis" aria-label="City impact">
      <div className="kpi">
        <div className="kpi-text">
          <span className="numeral">{people(im.people_unserved)}<Badge bad={im.people_unserved > 0} /></span>
          <span className="label">People without power</span>
        </div>
        <Spark values={unserved} domain={[0, totalPeople / 2]} color={im.people_unserved > 0 ? "#E5484D" : "#2DB56A"} bars={22} />
      </div>
      <div className="kpi">
        <div className="kpi-text">
          <span className="numeral">{atRisk}<small>of {hospitals}</small><Badge bad={atRisk > 0} /></span>
          <span className="label">{im.hospitals_down > 0 ? `Hospitals: ${im.hospitals_down} without power` : im.hospitals_on_backup > 0 ? "Hospitals on backup power" : "Hospitals at risk"}</span>
        </div>
      </div>
      <div className="kpi">
        <div className="kpi-text">
          <span className="numeral">{Math.round(im.energy_not_served_mwh)}<small>MWh</small><Badge bad={im.energy_not_served_mwh > 0.5} /></span>
          <span className="label" title="Backup time and energy run in accelerated time: 1 second is 1 minute">Energy not supplied</span>
        </div>
        <Spark values={energy} domain={[0, Math.max(20, ...energy)]} color={im.energy_not_served_mwh > 0.5 ? "#E5484D" : "#2DB56A"} bars={22} />
      </div>
      <div className="kpi">
        <div className="kpi-text">
          <span className="numeral">{supplied}<small>%</small><Badge bad={supplied < 100} /></span>
          <span className="label">People supplied</span>
        </div>
      </div>
    </section>
  );
}
