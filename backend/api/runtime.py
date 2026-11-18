"""Wires simulator -> twin -> detector -> incidents -> store -> WebSocket subscribers."""
from __future__ import annotations

import asyncio
import contextlib

from core.contracts import Incident
from db.store import EventStore
from detect.threshold import ThresholdDetector
from incident.manager import IncidentManager
from sim.engine import SimulationEngine
from sim.plant import PlantParams
from twin.twin import GridTwin


class Runtime:
    def __init__(self, seed: int = 42, db_path: str = ":memory:", tick_seconds: float = 1.0,
                 params: PlantParams | None = None) -> None:
        self.engine = SimulationEngine(seed, params)
        self.twin = GridTwin(params)
        self.detector = ThresholdDetector()
        self.incidents = IncidentManager()
        self.store = EventStore(db_path)
        self.tick_seconds = tick_seconds
        self.district: str | None = None  # set when this unit is one district of the city
        self.subscribers: set[asyncio.Queue] = set()
        self._task: asyncio.Task | None = None

    # --- one simulation tick ---------------------------------------------------------
    def step(self) -> list[dict]:
        r = self.engine.step()
        self.twin.sync(self.engine.command_log)  # the twin's only command input
        twin = self.twin.compute(r.telemetry)
        scores = self.detector.score(r.telemetry, twin, r.events)
        alert = self.detector.is_alert(scores)
        inc = self.incidents.update(r.telemetry, twin, scores, alert, r.events)

        messages: list[dict] = [{"type": "telemetry", "data": r.telemetry.model_dump()}]
        messages += [{"type": "event", "data": e.model_dump()} for e in r.events]
        messages.append({"type": "twin", "data": twin.model_dump()})
        messages.append({"type": "scores", "data": scores.model_dump()})
        if inc is not None:
            inc.district = self.district
            messages.append({"type": "incident", "data": inc.model_dump()})
        for m in messages:
            self.store.append(m["type"], r.telemetry.t, m["data"])
            self._broadcast(m)
        return messages

    def approve_response(self, incident_id: str) -> Incident:
        """Simulated containment: staged response, then recovery verification."""
        inc = self.incidents.begin_recovery(incident_id, self.engine.plant.t)  # raises KeyError if unknown
        self.engine.begin_containment()
        m = {"type": "incident", "data": inc.model_dump()}
        self.store.append("incident", self.engine.plant.t, m["data"])
        self._broadcast(m)
        return inc

    def recovery(self) -> dict:
        """Latest recovery verification report plus the containment actions taken so far."""
        return {"report": self.incidents.last_report.to_dict(), "actions": self.engine.containment_log}

    # --- pub/sub ---------------------------------------------------------------------
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
                pass  # slow client: drop

    # --- background loop -------------------------------------------------------------
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
