"""FastAPI app: REST control endpoints plus the /ws/telemetry stream (owner: P3)."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.runtime import Runtime
from sim.scenarios import SCENARIO_INFO


class ScenarioRequest(BaseModel):
    name: str


def create_app(autostart: bool | None = None, db_path: str | None = None) -> FastAPI:
    if autostart is None:
        autostart = os.getenv("ARMOUR_AUTOSTART", "1") == "1"
    runtime = Runtime(
        seed=int(os.getenv("ARMOUR_SEED", "42")),
        db_path=db_path or os.getenv("ARMOUR_DB", ":memory:"),
        tick_seconds=float(os.getenv("ARMOUR_TICK_SECONDS", "1.0")),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if autostart:
            runtime.start()
        yield
        await runtime.stop()

    app = FastAPI(title="ARMOUR LABS", version="0.1.0", lifespan=lifespan)
    app.state.runtime = runtime
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # development only
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"status": "ok", "tick": runtime.engine.plant.tick, "active_scenario": runtime.engine.active}

    @app.get("/scenarios")
    def scenarios():
        return [{"name": k, **v} for k, v in SCENARIO_INFO.items()]

    @app.post("/scenario/start")
    def scenario_start(req: ScenarioRequest):
        try:
            runtime.engine.start_scenario(req.name)
        except KeyError:
            raise HTTPException(404, f"unknown scenario {req.name}")
        return {"active": runtime.engine.active}

    @app.post("/scenario/stop")
    def scenario_stop():
        runtime.engine.stop_scenario()
        return {"active": None}

    @app.get("/incidents")
    def incidents():
        return [i.model_dump() for i in runtime.incidents.incidents.values()]

    @app.post("/incident/{incident_id}/approve-response")
    def approve_response(incident_id: str):
        try:
            return runtime.approve_response(incident_id).model_dump()
        except KeyError:
            raise HTTPException(404, "unknown incident")

    @app.get("/incidents/{incident_id}/replay")
    def replay(incident_id: str):
        inc = runtime.incidents.incidents.get(incident_id)
        if inc is None:
            raise HTTPException(404, "unknown incident")
        return runtime.store.query(t_from=max(0.0, inc.t_start - 10.0))

    @app.get("/metrics")
    def metrics():
        # TODO (P3): precision/recall/F1/FPR/latency from the evaluation script.
        return {"status": "not_implemented", "note": "no measured results yet"}

    @app.websocket("/ws/telemetry")
    async def ws_telemetry(ws: WebSocket):
        await ws.accept()
        q = runtime.subscribe()
        try:
            while True:
                await ws.send_json(await q.get())
        except WebSocketDisconnect:
            pass
        finally:
            runtime.unsubscribe(q)

    return app
