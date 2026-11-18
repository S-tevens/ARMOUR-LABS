"""City engine (owner: P2): districts, lines, protection, cascades, facilities and impact.

Each district sits behind a distribution main breaker. Substations are joined by lines with capacities; a linear
power flow gives the flows. A line that stays above 110 % for a few seconds trips, flows are recomputed, and the
overload can cascade. Districts cut off from the state grid go dark.

City impact accounting runs at MINUTES_PER_TICK simulated minutes per second so a demo shows hours of consequence
in a minute or two (hospital backup power, energy not served). The UI labels this as accelerated.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

from city import scenarios
from city.config import CityConfig
from city.containment import CityContainment
from city.powerflow import SLACK, solve
from core.contracts import NetworkEvent

MINUTES_PER_TICK = 1.0
BACKUP_MINUTES = {"hospital": 90.0}
OVERLOAD_LEVEL = 1.10
OVERLOAD_TRIP_TICKS = 6
HARD_OVERLOAD = 1.40
HEARTBEAT_EVERY_TICKS = 5
DEMAND_RIPPLE = 0.07
DEMAND_PERIOD_S = 600.0
EVENT_LOG_CAP = 5000


@dataclass
class FacilityState:
    id: str
    type: str
    priority: int
    status: str = "ok"  # ok | backup | down
    backup_minutes_left: float = 0.0


@dataclass
class CityStep:
    state: dict
    events: list[NetworkEvent] = field(default_factory=list)


class CityEngine:
    def __init__(self, cfg: CityConfig, seed: int = 42) -> None:
        self.cfg = cfg
        self.seed = seed
        self.t = 0.0
        self.tick = 0
        self.seq = 0
        self.phase = {d.id: 0.7 * i for i, d in enumerate(cfg.districts)}
        self.nodes = cfg.node_ids
        # topology
        self.main_closed: dict[str, bool] = {d.id: True for d in cfg.districts}
        self.service: set[str] = {l.id for l in cfg.lines}
        self.out_reason: dict[str, str] = {}  # line id -> "protection" | "fault" | "command"
        self.overload_ticks: dict[str, int] = {l.id: 0 for l in cfg.lines}
        # demand
        self.forecast = 1.0  # scheduled demand factor (known to the twin)
        self.forecast_target = 1.0
        self.attack_factor = 1.0  # unscheduled demand factor (load-altering attacks)
        self.attack_target = 1.0
        self.stale: set[str] = set()
        # state
        self.frequency = 50.0
        self.energised: set[str] = set(self.nodes)
        self.flows: dict[str, float] = {l.id: 0.0 for l in cfg.lines}
        self.demand_mw: dict[str, float] = {d.id: d.base_load_mw for d in cfg.districts}
        self.facilities: dict[str, FacilityState] = {
            f.id: FacilityState(f.id, f.type, f.priority, "ok", BACKUP_MINUTES.get(f.type, 0.0))
            for d in cfg.districts for f in d.facilities
        }
        self.energy_not_served_mwh = 0.0
        self.peak_unserved = 0
        self.failures: list[dict] = []  # the order things failed in this incident (the domino effect)
        self._dark_prev: set[str] = set()
        self._fac_prev: dict[str, str] = {}
        # scenarios, events, containment
        self.active: str | None = None
        self._active_since = 0
        self.event_log: list[NetworkEvent] = []
        self.command_log: list[NetworkEvent] = []  # AUTHORISED commands only (input for the city twin)
        self._pending: list[NetworkEvent] = []
        self.unit_actions: list[tuple[str, str]] = []  # (district id, action) for the substation units
        self.containment: CityContainment | None = None
        self.containment_log: list[dict] = []

    # --- events and commands ---------------------------------------------------------
    def emit(self, src, dst, function_code, register, value, authorised, *, seq=None, t=None) -> NetworkEvent:
        if seq is None:
            self.seq += 1
            seq = self.seq
        e = NetworkEvent(seq=seq, t=self.t if t is None else t, src=src, dst=dst, function_code=function_code,
                         register=register, value=value, authorised=authorised)
        self._pending.append(e)
        self.event_log.append(e)
        del self.event_log[:-EVENT_LOG_CAP]
        return e

    def command(self, register: str, value: str) -> None:
        """An AUTHORISED SCADA command: DIST_MAIN_<ID> or LINE_<Lx>, value OPEN or CLOSE."""
        closed = value == "CLOSE"
        if register.startswith("DIST_MAIN_"):
            did = register[len("DIST_MAIN_"):].lower()
            if did not in self.main_closed:
                raise ValueError(f"unknown district {did}")
            dst = f"SUB-{did.upper()}"
            self.main_closed[did] = closed
        elif register.startswith("LINE_"):
            lid = register[len("LINE_"):]
            if lid not in self.overload_ticks:
                raise ValueError(f"unknown line {lid}")
            dst = "CITY-SCADA"
            if closed and self.out_reason.get(lid) == "fault":
                pass  # a faulted line cannot be closed until repaired
            elif closed:
                self.service.add(lid)
                self.out_reason.pop(lid, None)
            else:
                self.service.discard(lid)
                self.out_reason[lid] = "command"
        else:
            raise ValueError(f"unknown register {register}")
        e = self.emit("SCADA", dst, "OPERATE", register, value, True)
        self.command_log.append(e)

    # --- scenarios and containment ----------------------------------------------------
    def start_scenario(self, name: str, districts: list[str] | None = None) -> None:
        if name not in scenarios.SCENARIO_INFO:
            raise KeyError(name)
        if self.active:
            self.stop_scenario()
        self._reset_incident_accounting()
        self.active = name
        self._active_since = self.tick
        try:
            scenarios.start(name, self, districts)
        except Exception:
            self.active = None  # do not leave a half-started scenario behind
            raise

    def stop_scenario(self) -> None:
        """Hard reset to a healthy city."""
        self.active = None
        self.containment = None
        self.main_closed = {d: True for d in self.main_closed}
        self.service = {l.id for l in self.cfg.lines}
        self.out_reason.clear()
        self.overload_ticks = {k: 0 for k in self.overload_ticks}
        self.forecast_target = 1.0
        self.attack_target = 1.0
        self.stale.clear()
        self._reset_incident_accounting()
        self.unit_actions.append(("*", "reset"))

    def _reset_incident_accounting(self) -> None:
        self.energy_not_served_mwh, self.peak_unserved = 0.0, 0
        self.failures = []
        self._dark_prev = set()
        self._fac_prev = {}

    def _fail(self, kind: str, ident: str, text: str) -> None:
        self.failures.append({"n": len(self.failures) + 1, "t": self.t, "kind": kind, "id": ident, "text": text})
        del self.failures[:-60]

    def ground_truth(self) -> dict:
        info = scenarios.SCENARIO_INFO.get(self.active) if self.active else None
        kind = info["kind"] if info else "normal"
        return {"scenario": self.active or "normal", "kind": kind, "active": bool(self.active),
                "is_attack": kind == "attack", "is_anomaly": kind in ("attack", "fault")}

    def begin_containment(self) -> None:
        self.containment_log = []
        self.containment = CityContainment(self.active, self.tick)

    def log_action(self, text: str) -> None:
        self.containment_log.append({"t": self.t, "action": text})

    def unauthorised_trips(self) -> list[str]:
        """Lines that are out of service although no authorised command opened them."""
        return sorted(l for l, r in self.out_reason.items() if r in ("protection", "fault"))

    # --- physics ---------------------------------------------------------------------
    def _demand(self) -> dict[str, float]:
        factor = self.forecast * self.attack_factor
        return {
            d.id: d.base_load_mw * (1.0 + DEMAND_RIPPLE * math.sin(2 * math.pi * self.t / DEMAND_PERIOD_S + self.phase[d.id])) * factor
            for d in self.cfg.districts
        }

    def _solve(self, demand: dict[str, float]):
        load = {d: (demand[d] if self.main_closed[d] else 0.0) for d in demand}
        return solve(self.nodes, list(self.cfg.lines), self.service, load)

    def step(self) -> CityStep:
        if self.active:
            scenarios.on_tick(self.active, self, self.tick - self._active_since)
        if self.containment:
            self.containment.on_tick(self)
            if self.containment.done:
                self.containment = None
        if self.tick % HEARTBEAT_EVERY_TICKS == 0:
            for d in self.cfg.districts:
                if d.id not in self.stale:
                    self.emit("SCADA", f"SUB-{d.id.upper()}", "READ", "STATUS", "ok", True)

        self.forecast += (self.forecast_target - self.forecast) * 0.15
        self.attack_factor += (self.attack_target - self.attack_factor) * 0.12
        self.demand_mw = self._demand()
        flows, energised = self._solve(self.demand_mw)

        # protection: trip at most one line per tick, so cascades unfold visibly
        worst, worst_load = None, 0.0
        for ln in self.cfg.lines:
            if ln.id not in self.service:
                self.overload_ticks[ln.id] = 0
                continue
            loading = abs(flows[ln.id]) / ln.capacity_mw
            self.overload_ticks[ln.id] = self.overload_ticks[ln.id] + 1 if loading > OVERLOAD_LEVEL else 0
            trips = self.overload_ticks[ln.id] >= OVERLOAD_TRIP_TICKS or loading > HARD_OVERLOAD
            if trips and loading > worst_load:
                worst, worst_load = ln.id, loading
        if worst:
            self.service.discard(worst)
            self.out_reason[worst] = "protection"
            self.overload_ticks[worst] = 0
            self.emit(f"RELAY-{worst}", "CITY-SCADA", "TRIP", worst, f"{worst_load * 100:.0f}%", True)
            ln = next(l for l in self.cfg.lines if l.id == worst)
            self._fail("line", worst, f"{self._label(ln.a)} to {self._label(ln.b)} line tripped at {worst_load * 100:.0f}% of its rating")
            flows, energised = self._solve(self.demand_mw)
        self.flows, self.energised = flows, energised

        dark = self.dark_districts()
        total_demand = sum(self.demand_mw.values())
        unserved_mw = sum(self.demand_mw[d] for d in dark)
        lost_frac = unserved_mw / total_demand if total_demand else 0.0
        self.frequency += ((50.0 + 2.0 * lost_frac) - self.frequency) * 0.2
        self._update_facilities(dark)
        self._record_failures(dark)
        self.energy_not_served_mwh += unserved_mw * MINUTES_PER_TICK / 60.0
        people = sum(self.cfg.district(d).population for d in dark)
        self.peak_unserved = max(self.peak_unserved, people)

        self.t += 1.0
        self.tick += 1
        events, self._pending = self._pending, []
        return CityStep(state=self.snapshot(), events=events)

    def _label(self, node: str) -> str:
        return "the state grid" if node == SLACK else self.cfg.district(node).name

    def _record_failures(self, dark: list[str]) -> None:
        now = set(dark)
        for did in dark:
            if did not in self._dark_prev:
                self._fail("district", did, f"{self.cfg.district(did).name} lost power")
        self._dark_prev = now
        for d in self.cfg.districts:
            for f in d.facilities:
                status = self.facilities[f.id].status
                prev = self._fac_prev.get(f.id, "ok")
                if f.type == "hospital" and status != prev and status in ("backup", "down"):
                    self._fail("facility", f.id, f"Hospital in {d.name} " + ("switched to backup power" if status == "backup" else "ran out of backup power"))
                self._fac_prev[f.id] = status

    def dark_districts(self) -> list[str]:
        return [d.id for d in self.cfg.districts if not (d.id in self.energised and self.main_closed[d.id])]

    def _update_facilities(self, dark: list[str]) -> None:
        for d in self.cfg.districts:
            for f in d.facilities:
                fs = self.facilities[f.id]
                full = BACKUP_MINUTES.get(f.type, 0.0)
                if d.id not in dark:
                    fs.status, fs.backup_minutes_left = "ok", full
                elif fs.backup_minutes_left > 0:
                    fs.status = "backup"
                    fs.backup_minutes_left = max(0.0, fs.backup_minutes_left - MINUTES_PER_TICK)
                else:
                    fs.status = "down"

    # --- state for the UI -------------------------------------------------------------
    def line_status(self, line_id: str) -> str:
        if line_id in self.service:
            return "in_service"
        return {"protection": "tripped", "fault": "fault", "command": "open"}.get(self.out_reason.get(line_id, ""), "open")

    def snapshot(self) -> dict:
        dark = set(self.dark_districts())
        loading = {l.id: (abs(self.flows[l.id]) / l.capacity_mw if l.id in self.service else 0.0) for l in self.cfg.lines}
        districts = []
        for d in self.cfg.districts:
            adj = [loading[l.id] for l in self.cfg.lines if d.id in (l.a, l.b)]
            status = "dark" if d.id in dark else "stale" if d.id in self.stale else "attention" if adj and max(adj) > 0.9 else "ok"
            districts.append({
                "id": d.id, "name": d.name, "x": d.x, "y": d.y, "population": d.population, "status": status,
                "served_pct": 0 if d.id in dark else 100, "people_unserved": d.population if d.id in dark else 0,
                "load_mw": round(self.demand_mw[d.id] if d.id not in dark else 0.0, 1),
                "facilities": [
                    {"id": f.id, "type": f.type, "priority": f.priority, "status": self.facilities[f.id].status,
                     "backup_minutes_left": round(self.facilities[f.id].backup_minutes_left)}
                    for f in d.facilities
                ],
            })
        lines = [
            {"id": l.id, "from": l.a, "to": l.b, "flow_mw": round(self.flows[l.id], 1), "capacity_mw": l.capacity_mw,
             "loading": round(loading[l.id], 3), "status": self.line_status(l.id)}
            for l in self.cfg.lines
        ]
        facs = list(self.facilities.values())
        people = sum(d["people_unserved"] for d in districts)
        impact = {
            "people_unserved": people,
            "hospitals_on_backup": sum(1 for f in facs if f.type == "hospital" and f.status == "backup"),
            "hospitals_down": sum(1 for f in facs if f.type == "hospital" and f.status == "down"),
            "critical_sites_down": sum(1 for f in facs if f.priority <= 2 and f.status == "down"),
            "energy_not_served_mwh": round(self.energy_not_served_mwh, 1),
            "restoration_pct": 100 if self.peak_unserved == 0 else round(100 * (1 - people / self.peak_unserved)),
        }
        return {"t": self.t, "tick": self.tick, "frequency": round(self.frequency, 3), "districts": districts,
                "lines": lines, "impact": impact, "scenario": self.active, "failures": list(self.failures)}
