import { useCallback, useEffect, useRef, useState } from "react";
import type { Incident } from "../types";
import { approveCityResponse, startCityScenario, stopCityScenario } from "../city/api";
import type { CityStream } from "../city/useCityStream";

export type Phase = "idle" | "normal" | "attack" | "detect" | "explain" | "contain" | "recover" | "done";
export const STEPS: { id: Exclude<Phase, "idle" | "done">; label: string }[] = [
  { id: "normal", label: "Normal" },
  { id: "attack", label: "Attack" },
  { id: "detect", label: "Detect" },
  { id: "explain", label: "Explain" },
  { id: "contain", label: "Contain" },
  { id: "recover", label: "Recover" },
];

/** The scenario the demo plays: three central substations are tripped at once (the pattern of the 2015 Ukraine attack). */
export const DEMO_SCENARIO = "coordinated_substation_trip";
const MIN_SECONDS: Record<string, number> = { normal: 6, attack: 7, detect: 8, explain: 16, contain: 8, recover: 7 };
const TIMEOUT_S = 75; // give up waiting for the system to reach the next step

export interface DemoStats {
  startT: number | null; // simulated clock when the attack began
  approveT: number | null; // simulated clock when containment was approved
  detectS: number | null;
  restoreS: number | null;
  peakUnserved: number;
  peakBackup: number;
  peakDown: number;
}
const NO_STATS: DemoStats = { startT: null, approveT: null, detectS: null, restoreS: null, peakUnserved: 0, peakBackup: 0, peakDown: 0 };

export interface Demo {
  phase: Phase;
  paused: boolean;
  error: string | null;
  stats: DemoStats;
  incident: Incident | null;
  secondsLeft: number;
  start: () => void;
  stop: () => void;
  next: () => void;
  togglePause: () => void;
}

/** Runs the guided story on the city layer: normal, attack, detect, explain, contain, recover. It only uses the normal API. */
export function useDemo(stream: CityStream): Demo {
  const [phase, setPhase] = useState<Phase>("idle");
  const [paused, setPaused] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<DemoStats>(NO_STATS);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const latest = useRef(stream);
  latest.current = stream;
  const run = useRef({ phase: "idle" as Phase, since: 0, paused: false, skip: false, stats: NO_STATS, incidentId: null as string | null });

  const enter = useCallback((p: Phase) => {
    const r = run.current;
    r.phase = p;
    r.since = Date.now();
    r.skip = false;
    setPhase(p);
    const fail = (e: unknown) => { setError(`The demo could not continue: ${e instanceof Error ? e.message : String(e)}`); r.phase = "done"; setPhase("done"); };
    if (p === "normal") void stopCityScenario().catch(fail); // reset to a clean, normal city
    if (p === "attack") {
      r.stats = { ...NO_STATS, startT: latest.current.state?.t ?? 0 };
      void startCityScenario(DEMO_SCENARIO).catch(fail);
    }
    if (p === "contain" && r.incidentId) {
      r.stats.approveT = latest.current.state?.t ?? null;
      void approveCityResponse(r.incidentId).catch(fail);
    }
  }, []);

  useEffect(() => {
    if (phase === "idle" || phase === "done") return;
    const id = window.setInterval(() => {
      const r = run.current;
      if (r.paused) { r.since += 500; return; }
      const st = latest.current.state;
      const inc = st?.incident_id ? latest.current.incidents[st.incident_id] ?? null : null;
      if (inc) r.incidentId = inc.id;
      if (st) {
        const s = r.stats;
        s.peakUnserved = Math.max(s.peakUnserved, st.impact.people_unserved);
        s.peakBackup = Math.max(s.peakBackup, st.impact.hospitals_on_backup);
        s.peakDown = Math.max(s.peakDown, st.impact.hospitals_down);
        if (inc && s.detectS == null && s.startT != null) s.detectS = Math.max(0, Math.round(inc.t_start - s.startT));
        setStats({ ...s });
      }
      const waited = (Date.now() - r.since) / 1000;
      const min = MIN_SECONDS[r.phase] ?? 0;
      setSecondsLeft(Math.max(0, Math.ceil(min - waited)));
      const dwellDone = r.skip || waited >= min;
      const fresh = latest.current.incidents[r.incidentId ?? ""] ?? inc;

      let ready = false;
      switch (r.phase) {
        case "normal": ready = !!st && st.status === "normal" && !st.scenario; break;
        case "attack": ready = true; break;
        case "detect": ready = !!inc; break;
        case "explain": ready = !!fresh; break;
        case "contain": ready = !!fresh && (fresh.status === "recovering" || fresh.status === "recovered"); break;
        case "recover": ready = !!fresh && fresh.status === "recovered"; break;
      }
      if (ready && dwellDone) {
        const order: Phase[] = ["normal", "attack", "detect", "explain", "contain", "recover", "done"];
        const to = order[order.indexOf(r.phase) + 1];
        if (to === "done" && st && r.stats.approveT != null) { r.stats.restoreS = Math.max(0, Math.round(st.t - r.stats.approveT)); setStats({ ...r.stats }); }
        enter(to);
      } else if (!ready && waited > TIMEOUT_S) {
        setError("Timed out waiting for the next step. Is the backend running?");
        r.phase = "done";
        setPhase("done");
      }
    }, 500);
    return () => window.clearInterval(id);
  }, [phase, enter]);

  const start = useCallback(() => {
    setError(null);
    setPaused(false);
    run.current = { phase: "idle", since: 0, paused: false, skip: false, stats: NO_STATS, incidentId: null };
    setStats(NO_STATS);
    enter("normal");
  }, [enter]);
  const stop = useCallback(() => { run.current.phase = "idle"; setPhase("idle"); setPaused(false); run.current.paused = false; }, []);
  const next = useCallback(() => { run.current.skip = true; }, []);
  const togglePause = useCallback(() => { run.current.paused = !run.current.paused; setPaused(run.current.paused); }, []);

  const st = stream.state;
  const incident = (run.current.incidentId && stream.incidents[run.current.incidentId]) || (st?.incident_id ? stream.incidents[st.incident_id] ?? null : null);
  return { phase, paused, error, stats, incident: incident || null, secondsLeft, start, stop, next, togglePause };
}
