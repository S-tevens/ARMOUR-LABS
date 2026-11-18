"""FastAPI app: REST control endpoints plus the /ws/telemetry and /ws/city streams (owner: P3).

The substation endpoints accept an optional `district` (default: the featured district), so the original
single-substation API keeps working. City endpoints live under /city.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.city_runtime import CityRuntime
from api.runtime import Runtime
from sim.scenarios import SCENARIO_INFO


class ScenarioRequest(BaseModel):
    name: str
    districts: list[str] | None = None  # city scenarios only


def create_app(autostart: bool | None = None, db_path: str | None = None) -> FastAPI:
    if autostart is None:
        autostart = os.getenv("ARMOUR_AUTOSTART", "1") == "1"
    city = CityRuntime(
        seed=int(os.getenv("ARMOUR_SEED", "42")),
        tick_seconds=float(os.getenv("ARMOUR_TICK_SECONDS", "1.0")),
        featured_db=db_path or os.getenv("ARMOUR_DB", ":memory:"),
    )
    runtime = city.featured_unit  # the original single-substation API works on this unit

    def unit(district: str | None) -> Runtime:
        if district is None:
            return runtime
        if district not in city.units:
            raise HTTPException(404, f"unknown district {district}")
        return city.units[district]

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if autostart:
            city.start()  # steps the city and every district substation
        yield
        await city.stop()

    app = FastAPI(title="ARMOUR LABS", version="0.2.0", lifespan=lifespan)
    app.state.runtime = runtime
    app.state.city = city
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # development only
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------------- substation API (optionally per district) ----------------
    @app.get("/health")
    def health():
        return {"status": "ok", "tick": runtime.engine.plant.tick, "active_scenario": runtime.engine.active,
                "city_tick": city.engine.tick, "city_scenario": city.engine.active}

    @app.get("/scenarios")
    def scenarios():
        return [{"name": k, **v} for k, v in SCENARIO_INFO.items()]

    @app.post("/scenario/start")
    def scenario_start(req: ScenarioRequest, district: str | None = None):
        u = unit(district)
        try:
            u.engine.start_scenario(req.name)
        except KeyError:
            raise HTTPException(404, f"unknown scenario {req.name}")
        return {"active": u.engine.active}

    @app.post("/scenario/stop")
    def scenario_stop(district: str | None = None):
        unit(district).engine.stop_scenario()
        return {"active": None}

    @app.get("/incidents")
    def incidents(district: str | None = None):
        return [i.model_dump() for i in unit(district).incidents.incidents.values()]

    @app.post("/incident/{incident_id}/approve-response")
    def approve_response(incident_id: str, district: str | None = None):
        try:
            return unit(district).approve_response(incident_id).model_dump()
        except KeyError:
            raise HTTPException(404, "unknown incident")

    @app.get("/incidents/{incident_id}/replay")
    def replay(incident_id: str, district: str | None = None):
        u = unit(district)
        inc = u.incidents.incidents.get(incident_id)
        if inc is None:
            raise HTTPException(404, "unknown incident")
        return u.store.query(t_from=max(0.0, inc.t_start - 10.0))

    @app.get("/recovery")
    def recovery(district: str | None = None):
        return unit(district).recovery()

    @app.get("/metrics")
    def metrics():
        # TODO (P3): precision/recall/F1/FPR/latency from the evaluation script.
        return {"status": "not_implemented", "note": "no measured results yet"}

    @app.websocket("/ws/telemetry")
    async def ws_telemetry(ws: WebSocket, district: str | None = None):
        if district is not None and district not in city.units:
            await ws.close(code=4404)
            return
        await ws.accept()
        u = unit(district)
        q = u.subscribe()
        try:
            while True:
                await ws.send_json(await q.get())
        except WebSocketDisconnect:
            pass
        finally:
            u.unsubscribe(q)

    # ---------------- city API ----------------
    @app.get("/city")
    def city_info():
        return {"layout": city.layout(), "state": city.state,
                "incidents": [i.model_dump() for i in city.incidents.incidents.values()]}

    @app.get("/city/scenarios")
    def city_scenarios():
        return city.scenarios()

    @app.post("/city/scenario/start")
    def city_scenario_start(req: ScenarioRequest):
        try:
            city.engine.start_scenario(req.name, req.districts)
        except KeyError:
            raise HTTPException(404, f"unknown scenario {req.name}")
        except ValueError as e:
            raise HTTPException(422, str(e))
        return {"active": city.engine.active}

    @app.post("/city/scenario/stop")
    def city_scenario_stop():
        city.engine.stop_scenario()
        return {"active": None}

    @app.get("/city/incidents")
    def city_incidents():
        return [i.model_dump() for i in city.incidents.incidents.values()]

    @app.post("/city/incident/{incident_id}/approve-response")
    def city_approve(incident_id: str):
        try:
            return city.approve_response(incident_id).model_dump()
        except KeyError:
            raise HTTPException(404, "unknown incident")

    @app.get("/city/recovery")
    def city_recovery():
        return city.recovery()

    @app.websocket("/ws/city")
    async def ws_city(ws: WebSocket):
        await ws.accept()
        q = city.subscribe()
        try:
            while True:
                await ws.send_json(await q.get())
        except WebSocketDisconnect:
            pass
        finally:
            city.unsubscribe(q)

    return app
