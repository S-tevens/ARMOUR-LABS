// Mirrors backend/core/contracts.py and docs/contracts.md. Change all three together.

export type IedState = "normal" | "suspicious" | "compromised";

/** Campus microgrid substation snapshot, 1 Hz. grid_import_kw: + import, - export. bess_kw: + discharge, - charge. Breakers: true = closed. */
export interface Telemetry {
  t: number;
  tick: number;
  frequency: number; // Hz
  bus_voltage: number; // per unit
  grid_import_kw: number;
  pv_kw: number;
  bess_kw: number;
  bess_soc: number; // percent
  load_critical_kw: number; // hospital feeder
  load_noncritical_kw: number; // campus feeder
  irradiance: number; // W/m2
  cb_main: boolean;
  cb_pv: boolean;
  cb_bess: boolean;
  cb_crit: boolean;
  cb_nc: boolean;
  ied_status: { ied01: IedState; ied02: IedState; ied03: IedState };
}

export interface NetworkEvent {
  seq: number;
  t: number;
  src: string;
  dst: string;
  function_code: string;
  register: string;
  value: string | number | boolean | null;
  authorised: boolean;
}

export interface TwinState {
  t: number;
  expected: Record<string, number>;
  residual: Record<string, number>;
  norm_residual: Record<string, number>;
}

export interface Scores {
  t: number;
  network: number;
  controller: number;
  process: number;
  twin: number;
}

export interface Evidence {
  type: string;
  text: string;
  tag: "observed" | "correlated" | "inferred";
}

export interface Incident {
  id: string;
  t_start: number;
  severity: "low" | "medium" | "high";
  confidence: number;
  affected_devices: string[];
  classification: "attack" | "fault" | "unknown";
  scores: Record<string, number>;
  evidence: Evidence[];
  status: "open" | "responding" | "recovering" | "recovered" | "unresolved";
  district?: string | null; // substation incidents: which district
  campaign_id?: string | null; // city incidents spanning several districts
}

export interface ScenarioInfo {
  name: string;
  label: string;
  kind: "attack" | "fault" | "benign";
  group: "core" | "extra";
  mitre: string | null;
  description: string;
}

export type StreamMessage =
  | { type: "telemetry"; data: Telemetry }
  | { type: "event"; data: NetworkEvent }
  | { type: "twin"; data: TwinState }
  | { type: "scores"; data: Scores }
  | { type: "incident"; data: Incident };
