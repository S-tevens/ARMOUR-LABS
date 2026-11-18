import { useEffect, useState } from "react";
import { API_URL, districtQuery, telemetryUrl } from "./api";
import type { Incident, NetworkEvent, Scores, StreamMessage, Telemetry, TwinState } from "./types";

export const HISTORY = 90;

export interface LinkStat {
  total: number;
  bad: number;
}

export interface StreamState {
  connected: boolean;
  telemetry: Telemetry | null;
  twin: TwinState | null;
  scores: Scores | null;
  events: NetworkEvent[]; // newest first
  incidents: Record<string, Incident>;
  history: Telemetry[]; // oldest first, last HISTORY ticks
  twinHistory: TwinState[];
  links: Record<string, LinkStat>; // key "src>dst", counted since page load
}

const EMPTY: StreamState = {
  connected: false,
  telemetry: null,
  twin: null,
  scores: null,
  events: [],
  incidents: {},
  history: [],
  twinHistory: [],
  links: {},
};

const tail = <T,>(a: T[], x: T): T[] => [...a, x].slice(-HISTORY);

/** Subscribes to the backend WebSocket and keeps the latest state. Reconnects automatically. */
export function useStream(district?: string): StreamState {
  const [state, setState] = useState<StreamState>(EMPTY);

  useEffect(() => {
    setState(EMPTY); // switching district starts from a clean slate
    let ws: WebSocket | null = null;
    let timer: number | undefined;
    let closed = false;

    const connect = () => {
      ws = new WebSocket(telemetryUrl(district));
      ws.onopen = () => {
        setState((s) => ({ ...s, connected: true }));
        // Pick up incidents that opened before this page loaded (reload, late join).
        fetch(`${API_URL}/incidents${districtQuery(district)}`)
          .then((r) => r.json() as Promise<Incident[]>)
          .then((list) =>
            setState((s) => ({ ...s, incidents: { ...Object.fromEntries(list.map((i) => [i.id, i])), ...s.incidents } })),
          )
          .catch(() => undefined);
      };
      ws.onclose = () => {
        setState((s) => ({ ...s, connected: false }));
        if (!closed) timer = window.setTimeout(connect, 1500);
      };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data) as StreamMessage;
        setState((s) => {
          switch (msg.type) {
            case "telemetry":
              return { ...s, telemetry: msg.data, history: tail(s.history, msg.data) };
            case "twin":
              return { ...s, twin: msg.data, twinHistory: tail(s.twinHistory, msg.data) };
            case "scores":
              return { ...s, scores: msg.data };
            case "event": {
              const key = `${msg.data.src}>${msg.data.dst}`;
              const prev = s.links[key] ?? { total: 0, bad: 0 };
              return {
                ...s,
                events: [msg.data, ...s.events].slice(0, 40),
                links: { ...s.links, [key]: { total: prev.total + 1, bad: prev.bad + (msg.data.authorised ? 0 : 1) } },
              };
            }
            case "incident":
              return { ...s, incidents: { ...s.incidents, [msg.data.id]: msg.data } };
          }
        });
      };
    };
    connect();
    return () => {
      closed = true;
      window.clearTimeout(timer);
      ws?.close();
    };
  }, [district]);

  return state;
}
