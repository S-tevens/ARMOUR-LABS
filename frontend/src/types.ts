// Mirrors backend/core/contracts.py and docs/contracts.md. Change all three together.

export type PlcState = "normal" | "suspicious" | "compromised";

export interface Telemetry {
  t: number;
  tick: number;
  tank1_level: number;
  tank2_level: number;
  pressure: number;
  flow: number;
  temperature: number;
  pump1: boolean; // true = running
  pump2: boolean;
  valve1: boolean; // true = open
  plc_status: { plc01: PlcState; plc02: PlcState; plc03: PlcState };
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
