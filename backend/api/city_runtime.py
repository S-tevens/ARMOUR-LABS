"""City runtime (owner: P3): drives the city engine and one substation unit per district.

Each district's substation is a full `Runtime` (simulator, twin, detector, incidents) with sizes scaled for that
district. The city engine decides whether each district is still connected to the grid and how much demand it has;
the units react to that. City-level detection looks at the whole picture: topology, flows and impact.
"""
from __future__ import annotations

import asyncio
import contextlib

from api.runtime import Runtime
from city import config
from city.containment import STEP_EVERY_TICKS  # noqa: F401  (re-exported for tests)
from city.detect import CityDetector, CityIncidentManager
from city.engine import CityEngine
from city.recovery import CityRecoveryReport, CityRecoveryVerifier
from city.scenarios import ATTACKER_IP, SCENARIO_INFO
from city.twin import CityTwin
from core.contracts import Incident
from db.store import EventStore
from detect.bundle import peek_bundle
from sim.plant import PlantParams

MAX_EVENT_MESSAGES_PER_TICK = 5


def params_for(d: config.District, index: int, featured: str) -> PlantParams:
    s = d.plant_scale
    return PlantParams(
        load_crit_base=400.0 * s, load_crit_amp=30.0 * s, load_nc_base=300.0 * s, load_nc_amp=40.0 * s,
        pv_rated_kw=500.0 * s, bess_pmax_kw=250.0 * s, bess_cap_kwh=200.0 * s, import_target_kw=320.0 * s,
        load_phase=0.0 if d.id == featured else 0.6 * (index + 1),
    )


class CityRuntime:
    def __init__(self, seed: int = 42, tick_seconds: float = 1.0, featured_db: str = ":memory:",
                 city: str | None = None, ml: bool = False) -> None:
        self.cfg = config.load(config.LAYOUTS[city] if city else None)
        self.featured = self.cfg.featured
        self.tick_seconds = tick_seconds
        self.engine = CityEngine(self.cfg, seed)
        self.units: dict[str, Runtime] = {}
        for i, d in enumerate(self.cfg.districts):
            unit = Runtime(
                seed=seed if d.id == self.featured else seed + 1 + i,
                db_path=featured_db if d.id == self.featured else ":memory:",
                tick_seconds=tick_seconds,
                params=params_for(d, i, self.featured),
                bundle=peek_bundle if ml else None,
            )
            unit.district = d.id
            self.units[d.id] = unit
        self.twin = CityTwin(self.cfg)
        self.detector = CityDetector()
        self.incidents = CityIncidentManager()
        self.verifier = CityRecoveryVerifier()
        self.last_report: CityRecoveryReport = CityRecoveryReport("idle")
        self.store = EventStore(":memory:")
        self.subscribers: set[asyncio.Queue] = set()
        self.state: dict | None = None
        self.status = "normal"
        self._task: asyncio.Task | None = None

    @property
    def featured_unit(self) -> Runtime:
        return self.units[self.featured]

    # --- layout for the UI -----------------------------------------------------------
    def layout(self) -> dict:
        return {
            "name": self.cfg.name,
            "note": self.cfg.note,
            "featured": self.featured,
            "attribution": self.cfg.meta.get("attribution"),
            "data_note": self.cfg.meta.get("data_note"),
            "center": self.cfg.meta.get("center"),
            "zoom": self.cfg.meta.get("zoom"),
            "feeders": self.cfg.meta.get("feeders", []),
            "districts": [{"id": d.id, "name": d.name, "x": d.x, "y": d.y, "lat": d.lat, "lon": d.lon,
                           "voltage_kv": d.voltage_kv, "entry": d.entry, "population": d.population,
                           "base_load_mw": d.base_load_mw,
                           "facilities": [{"id": f.id, "type": f.type, "priority": f.priority, "name": f.name, "lat": f.lat, "lon": f.lon}
                                          for f in d.facilities]}
                          for d in self.cfg.districts],
            "lines": [{"id": l.id, "from": l.a, "to": l.b, "capacity_mw": l.capacity_mw,
                       "terminal": self.cfg.terminals.get(l.id), **self.cfg.line_meta.get(l.id, {})}
                      for l in self.cfg.lines],
        }

    def scenarios(self) -> list[dict]:
        return [{"name": k, **v} for k, v in SCENARIO_INFO.items()]

    # --- one city tick ------------------------------------------------------------------
    def step(self) -> list[dict]:
        step = self.engine.step()
        st = step.state
        self._apply_unit_actions()
        energised = {d["id"] for d in st["districts"] if d["status"] != "dark"}
        demand_factor = self.engine.forecast * self.engine.attack_factor
        for did, unit in self.units.items():
            unit.engine.plant.grid_available = did in energised
            unit.engine.plant.load_scale = demand_factor
            unit.twin.demand_factor = self.engine.forecast
            unit.step()

        self.twin.demand_forecast = self.engine.forecast
        self.twin.sync(self.engine.command_log)
        twin = self.twin.compute(st)
        scores = self.detector.score(st, twin, step.events)
        created = self.incidents.update(st, twin, scores, self.detector.is_alert(scores), self.detector,
                                        self.twin.expected_open_lines)

        messages: list[dict] = []
        changed = created
        if created is not None:  # a new incident starts with a clean response card
            self.last_report = CityRecoveryReport("idle")
            self.engine.containment_log = []
        active = self.incidents.active()
        if active is not None and active.status == "recovering":
            self.last_report = self.verifier.update(st, self.twin.expected_open_lines)
            if self.last_report.state in ("recovered", "unresolved"):
                active.status = self.last_report.state
                changed = active
        if changed is not None:
            messages.append({"type": "city_incident", "data": changed.model_dump()})

        self.status = self._status(st)
        st = {**st, "status": self.status, "incident_id": active.id if active else None,
              "accelerated": True, "featured": self.featured, "twin": self._twin_summary(twin), "scores": scores.model_dump(),
              "recovery": self.last_report.to_dict(), "actions": [x["action"] for x in self.engine.containment_log][-6:]}
        self.state = st
        messages.insert(0, {"type": "city", "data": st})
        shown = [e for e in step.events if not e.authorised or e.register != "STATUS"][:MAX_EVENT_MESSAGES_PER_TICK]
        messages += [{"type": "city_event", "data": e.model_dump()} for e in shown]
        for m in messages:
            self.store.append(m["type"], st["t"], m["data"])
            self._broadcast(m)
        return messages

    @staticmethod
    def _twin_summary(twin) -> dict:
        return {"topology_mismatch": twin.residual["topology_mismatch"], "district_mismatch": twin.residual["district_mismatch"],
                "max_norm_residual": max(abs(v) for v in twin.norm_residual.values())}

    def _status(self, st: dict) -> str:
        if self.incidents.active() is not None:
            return "incident"
        if any(d["status"] in ("attention", "stale") for d in st["districts"]) or any(l["status"] in ("tripped", "fault") for l in st["lines"]):
            return "attention"
        return "normal"

    def _apply_unit_actions(self) -> None:
        actions, self.engine.unit_actions = self.engine.unit_actions, []
        for did, action in actions:
            unit = self.units.get(did)
            if unit is not None and action == "unauthorised_grid_loss":
                # the same attacker command also reaches the district's own substation
                unit.engine.emit(ATTACKER_IP, "IED-01", "OPERATE", "CB_MAIN", "OPEN", False)

    # --- responses -------------------------------------------------------------------
    def approve_response(self, incident_id: str) -> Incident:
        inc = self.incidents.incidents[incident_id]  # KeyError if unknown
        inc.status = "recovering"
        self.verifier.start(self.engine.t)
        self.last_report = CityRecoveryReport("recovering")
        self.engine.begin_containment()
        for unit in self.units.values():  # the districts' own substation incidents are contained too
            a = unit.incidents.active()
            if a is not None and a.status == "open":
                unit.approve_response(a.id)
        m = {"type": "city_incident", "data": inc.model_dump()}
        self.store.append("city_incident", self.engine.t, m["data"])
        self._broadcast(m)
        return inc

    def reset(self) -> None:
        """Hard reset to a healthy city, with no incidents or remembered evidence."""
        self.engine.stop_scenario()
        self.incidents.reset()
        self.detector.reset()
        self.last_report = CityRecoveryReport("idle")
        self.engine.containment_log = []

    def recovery(self) -> dict:
        return {"report": self.last_report.to_dict(), "actions": self.engine.containment_log}

    # --- pub/sub and loop ------------------------------------------------------------
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self.subscribers.discard(q)

    def _broadcast(self, message: dict) -> None:
        for q in list(self.subscribers):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                pass

    async def _loop(self) -> None:
        while True:
            self.step()
            await asyncio.sleep(self.tick_seconds)

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
