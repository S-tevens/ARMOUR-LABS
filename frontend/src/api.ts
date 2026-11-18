import type { Incident, ScenarioInfo } from "./types";

export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
export const WS_URL: string = API_URL.replace(/^http/, "ws") + "/ws/telemetry";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_URL + path, init);
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

const post = (path: string, body?: unknown) =>
  call(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });

export const getScenarios = () => call<ScenarioInfo[]>("/scenarios");
export const startScenario = (name: string) => post("/scenario/start", { name });
export const stopScenario = () => post("/scenario/stop");
export const approveResponse = (id: string) => post(`/incident/${id}/approve-response`) as Promise<Incident>;
