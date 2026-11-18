import { API_URL } from "../api";
import type { Incident } from "../types";
import type { CityInfo, CityScenarioInfo } from "./types";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_URL + path, init);
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

const post = (path: string, body?: unknown) =>
  call(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });

export const getCity = () => call<CityInfo>("/city");
export const getCityScenarios = () => call<CityScenarioInfo[]>("/city/scenarios");
export const startCityScenario = (name: string) => post("/city/scenario/start", { name });
export const stopCityScenario = () => post("/city/scenario/stop");
export const approveCityResponse = (id: string) => post(`/city/incident/${id}/approve-response`) as Promise<Incident>;
