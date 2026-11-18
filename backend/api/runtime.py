"""Wires simulator -> twin -> detector -> incidents -> store -> WebSocket subscribers."""
from __future__ import annotations

import asyncio
import contextlib
from typing import Callable

from core.contracts import Evidence, Incident, Scores
from db.store import EventStore
from detect.bundle import Bundle
from detect.features import FeatureExtractor
from detect.threshold import ThresholdDetector
from incident.manager import IncidentManager
from sim.engine import SimulationEngine
from sim.plant import PlantParams
from twin.twin import GridTwin


class Runtime:
    def __init__(self, seed: int = 42, db_path: str = ":memory:", tick_seconds: float = 1.0,
                 params: PlantParams | None = None, bundle: Callable[[], Bundle | None] | None = None) -> None:
        self.engine = SimulationEngine(seed, params)
        self.twin = GridTwin(params)
        self.detector = ThresholdDetector()
        self.features = FeatureExtractor((params or PlantParams()).scale)
        self._bundle = bundle  # returns the trained detectors once they are ready, else None
        self._prev = (0.0, 0.0)  # previous ML and physics scores, for the two-consecutive-ticks alert rule
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
        x = self.features.update(r.telemetry, r.events)  # keep the feature window running every tick
        extra: list[Evidence] = []
        bundle = self._bundle() if self._bundle else None
        if bundle is not None and self.features.ready:
            ratios = bundle.invariants.ratios(r.telemetry, x)
            inv, ml = bundle.invariants.score(ratios), float(bundle.ml.score01(x)[0])
            # an alert needs two consecutive ticks, so a single noisy tick never opens an incident
            scores = scores.model_copy(update={"invariants": round(min(inv, self._prev[0]), 3), "ml": round(min(ml, self._prev[1]), 3)})
            self._prev = (inv, ml)
            extra = self._detector_evidence(bundle, r.telemetry, x, ratios, scores)
        alert = self.detector.is_alert(scores)
        inc = self.incidents.update(r.telemetry, twin, scores, alert, r.events, extra)

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

    @staticmethod
    def _detector_evidence(bundle: Bundle, obs, x, ratios, scores: Scores) -> list[Evidence]:
        """Plain sentences from the physics checks and the autoencoder, only when they are actually raised."""
        out = [Evidence(type="physics_check", tag="observed", text=t) for t in bundle.invariants.explain(ratios, obs, x)]
        if scores.ml >= 0.8:
            top = bundle.ml.explain(x)
            if top:
                names = ", ".join(label for label, _ in top)
                out.append(Evidence(type="ml_anomaly", tag="observed",
                                    text=f"The readings break the relationships learned from normal operation, mostly {names}"))
        return out

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
