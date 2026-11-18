// City layer contracts. Mirror docs/city-contracts.md and backend/city + backend/api/city_runtime.py.
import type { Incident, NetworkEvent, ScenarioInfo } from "../types";

export type FacilityType = "hospital" | "water" | "metro" | "airport" | "tech";
export type FacilityStatus = "ok" | "backup" | "down";
export type DistrictStatus = "ok" | "attention" | "dark" | "stale";
export type LineStatus = "in_service" | "tripped" | "fault" | "open";

export interface LayoutFacility { id: string; type: FacilityType; priority: number; name?: string; lat?: number | null; lon?: number | null }
export interface LayoutDistrict {
  id: string; name: string; x: number; y: number; lat?: number | null; lon?: number | null; voltage_kv?: number | null;
  entry?: boolean; population: number; base_load_mw?: number; facilities: LayoutFacility[];
}
export type LineSource = "osm" | "inferred" | "grid-entry";
export interface LayoutLine {
  id: string; from: string; to: string; capacity_mw: number; terminal: [number, number] | null;
  voltage_kv?: number; source?: LineSource; path?: [number, number][];
}
export interface Feeder { name: string; lat: number; lon: number; voltage_kv: number; parent: string }
export interface CityLayout {
  name: string; note: string; featured: string; attribution?: string | null; data_note?: string | null;
  center?: [number, number] | null; zoom?: number | null; feeders: Feeder[]; districts: LayoutDistrict[]; lines: LayoutLine[];
}
/** One step of the domino: the order in which things failed during an incident. */
export interface Failure { n: number; t: number; kind: "line" | "district" | "facility"; id: string; text: string }

export interface FacilityState { id: string; type: FacilityType; priority: number; status: FacilityStatus; backup_minutes_left: number }
export interface DistrictState {
  id: string; name: string; x: number; y: number; population: number; status: DistrictStatus;
  served_pct: number; people_unserved: number; load_mw: number; facilities: FacilityState[];
}
export interface LineState {
  id: string; from: string; to: string; flow_mw: number; capacity_mw: number; loading: number; status: LineStatus;
}
export interface Impact {
  people_unserved: number; hospitals_on_backup: number; hospitals_down: number; critical_sites_down: number;
  energy_not_served_mwh: number; restoration_pct: number;
}
export interface RecoveryCheck { name: string; ok: boolean; detail: string }
export interface CityRecovery { state: "idle" | "recovering" | "recovered" | "unresolved"; elapsed: number; seconds_in_range: number; dwell: number; checks: RecoveryCheck[] }

export interface CityState {
  t: number; tick: number; frequency: number; scenario: string | null;
  status: "normal" | "attention" | "incident";
  incident_id: string | null; accelerated: boolean; featured: string;
  districts: DistrictState[]; lines: LineState[]; impact: Impact;
  recovery: CityRecovery; actions: string[]; failures: Failure[];
}

export type CityMessage =
  | { type: "city"; data: CityState }
  | { type: "city_incident"; data: Incident }
  | { type: "city_event"; data: NetworkEvent };

export interface CityInfo { layout: CityLayout; state: CityState | null; incidents: Incident[] }
export type CityScenarioInfo = ScenarioInfo;
