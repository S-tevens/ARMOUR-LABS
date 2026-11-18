export interface TickCounts { tp: number; fp: number; fn: number; tn: number; precision: number; recall: number; f1: number; fpr: number }
export interface Detector {
  key: string;
  label: string;
  family: string;
  description: string;
  tick: TickCounts;
  runs: { detected: number; total: number; rate: number; median_delay_s: number | null; mean_delay_s: number | null };
  false_alarms: { events: number; per_hour: number; benign_runs_alarmed: number; benign_runs: number };
}
export interface ScenarioRow {
  name: string;
  label: string;
  kind: "attack" | "fault" | "benign";
  runs: number;
  per_detector: Record<string, { detected: number; runs: number; median_delay_s: number | null }>;
}
export interface Block {
  detectors: Detector[];
  scenarios: ScenarioRow[];
  protocol: { test_runs: number; negative_hours: number; attack_or_fault_runs: number; benign_runs: number; alert_rule: string };
  note?: string;
}
export interface Metrics extends Partial<Block> {
  status: "ok" | "running" | "error" | "not_computed";
  error?: string;
  progress?: string | null;
  elapsed_s?: number;
  generated_at?: string;
  duration_s?: number;
  source?: string;
  limitations?: string[];
  fresh_check?: Block;
  training?: {
    train_rows: number;
    seconds_to_train: number;
    selected_model: string;
    selection: Record<string, { label: string; detected: number; of: number; false_alarm_runs: number }>;
    tolerances: Record<string, number>;
  };
}
