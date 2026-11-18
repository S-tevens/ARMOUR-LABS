import { useEffect, useState } from "react";
import { API_URL } from "../api";
import type { Incident } from "../types";
import { getCity } from "./api";
import type { CityLayout, CityMessage, CityState } from "./types";

const HISTORY = 90;

export interface CityStream {
  connected: boolean;
  layout: CityLayout | null;
  state: CityState | null;
  incidents: Record<string, Incident>;
  unserved: number[]; // people without power per tick, for the sparkline
  energy: number[]; // energy not supplied per tick
}

const EMPTY: CityStream = { connected: false, layout: null, state: null, incidents: {}, unserved: [], energy: [] };
const tail = (a: number[], x: number) => [...a, x].slice(-HISTORY);

/** Loads the city layout, then follows /ws/city. Reconnects automatically. */
export function useCityStream(): CityStream {
  const [s, setS] = useState<CityStream>(EMPTY);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: number | undefined;
    let closed = false;

    const load = () =>
      getCity()
        .then((info) =>
          setS((p) => ({
            ...p,
            layout: info.layout,
            state: p.state ?? info.state,
            incidents: { ...Object.fromEntries(info.incidents.map((i) => [i.id, i])), ...p.incidents },
          })),
        )
        .catch(() => undefined);

    const connect = () => {
      ws = new WebSocket(API_URL.replace(/^http/, "ws") + "/ws/city");
      ws.onopen = () => {
        setS((p) => ({ ...p, connected: true }));
        void load();
      };
      ws.onclose = () => {
        setS((p) => ({ ...p, connected: false }));
        if (!closed) timer = window.setTimeout(connect, 1500);
      };
      ws.onmessage = (ev) => {
        const m = JSON.parse(ev.data) as CityMessage;
        setS((p) => {
          if (m.type === "city") {
            // the state says which incident is live: drop open ones the backend no longer has (after "Stop and reset")
            const live = m.data.incident_id;
            const incidents = Object.fromEntries(
              Object.entries(p.incidents).filter(([id, i]) => !(i.status === "open" || i.status === "recovering") || id === live),
            );
            return { ...p, incidents, state: m.data, unserved: tail(p.unserved, m.data.impact.people_unserved), energy: tail(p.energy, m.data.impact.energy_not_served_mwh) };
          }
          if (m.type === "city_incident") return { ...p, incidents: { ...p.incidents, [m.data.id]: m.data } };
          return p;
        });
      };
    };
    connect();
    return () => {
      closed = true;
      window.clearTimeout(timer);
      ws?.close();
    };
  }, []);

  return s;
}
