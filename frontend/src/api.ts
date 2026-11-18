import type { Incident, ScenarioInfo } from "./types";

export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
export const WS_URL: string = API_URL.replace(/^http/, "ws") + "/ws/telemetry";

/** `?district=<id>` selects a district's substation; omitted means the featured district. */
export const districtQuery = (district?: string) => (district ? `?district=${district}` : "");
export const telemetryUrl = (district?: string) => WS_URL + districtQuery(district);

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
export const getIncidents = (district?: string) => call<Incident[]>(`/incidents${districtQuery(district)}`);
export const startScenario = (name: string, district?: string) => post(`/scenario/start${districtQuery(district)}`, { name });
export const stopScenario = (district?: string) => post(`/scenario/stop${districtQuery(district)}`);
export const approveResponse = (id: string, district?: string) =>
  post(`/incident/${id}/approve-response${districtQuery(district)}`) as Promise<Incident>;

export const getMetrics = () => call<import("./metrics/types").Metrics>("/metrics");
export const runMetrics = () => post("/metrics/run") as Promise<{ started: boolean }>;

export interface Explanation { text: string; source: "template" | "gemini"; model: string | null; pending: boolean; gemini_configured: boolean; note?: string }
export const getExplanation = (id: string, district?: string) => call<Explanation>(`/incidents/${id}/explanation${districtQuery(district)}`);
