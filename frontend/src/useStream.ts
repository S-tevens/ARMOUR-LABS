import { useEffect, useState } from "react";
import { WS_URL } from "./api";
import type { Incident, NetworkEvent, Scores, StreamMessage, Telemetry, TwinState } from "./types";

export interface StreamState {
  connected: boolean;
  telemetry: Telemetry | null;
  twin: TwinState | null;
  scores: Scores | null;
  events: NetworkEvent[]; // newest first
  incidents: Record<string, Incident>;
}

const EMPTY: StreamState = { connected: false, telemetry: null, twin: null, scores: null, events: [], incidents: {} };

/** Subscribes to the backend WebSocket and keeps the latest state. Reconnects automatically. */
export function useStream(): StreamState {
  const [state, setState] = useState<StreamState>(EMPTY);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: number | undefined;
    let closed = false;

    const connect = () => {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => setState((s) => ({ ...s, connected: true }));
      ws.onclose = () => {
        setState((s) => ({ ...s, connected: false }));
        if (!closed) timer = window.setTimeout(connect, 1500);
      };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data) as StreamMessage;
        setState((s) => {
          switch (msg.type) {
            case "telemetry":
              return { ...s, telemetry: msg.data };
            case "twin":
              return { ...s, twin: msg.data };
            case "scores":
              return { ...s, scores: msg.data };
            case "event":
              return { ...s, events: [msg.data, ...s.events].slice(0, 40) };
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
  }, []);

  return state;
}
