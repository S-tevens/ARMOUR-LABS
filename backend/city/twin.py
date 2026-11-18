"""City digital twin (owner: P2).

Expected city behaviour given only the AUTHORISED topology commands and the scheduled demand forecast. It has its
own (slightly different) demand model. It never reads the observed line or breaker states when forming
expectations, so the residuals show where reality differs from what was commanded:

  - a district that is dark although no authorised command opened its breaker  -> district_mismatch
  - a line out of service although no authorised command opened it             -> topology_mismatch
  - flows that differ from the expected flows (unscheduled demand, rerouting)  -> per-line residuals
"""
from __future__ import annotations

import math

from city.config import CityConfig
from city.powerflow import solve
from core.contracts import NetworkEvent, TwinState

TWIN_RIPPLE = 0.065  # the real city uses 0.07
FLOW_SCALE_PU = 0.06  # residual scale: 6 % of line capacity
MISMATCH_SCALE = 0.15


class CityTwin:
    def __init__(self, cfg: CityConfig) -> None:
        self.cfg = cfg
        self.expected_main = {d.id: True for d in cfg.districts}
        self.expected_open_lines: set[str] = set()
        self.demand_forecast = 1.0  # the schedule, like the clock; attacks do not change it
        self._synced = 0
        self.phase = {d.id: 0.7 * i for i, d in enumerate(cfg.districts)}

    def sync(self, command_log: list[NetworkEvent]) -> None:
        for c in command_log[self._synced:]:
            if not c.authorised:
                continue
            closed = c.value == "CLOSE"
            if c.register.startswith("DIST_MAIN_"):
                self.expected_main[c.register[len("DIST_MAIN_"):].lower()] = closed
            elif c.register.startswith("LINE_"):
                lid = c.register[len("LINE_"):]
                (self.expected_open_lines.discard if closed else self.expected_open_lines.add)(lid)
        self._synced = len(command_log)

    def expected(self, t: float):
        demand = {
            d.id: d.base_load_mw * (1.0 + TWIN_RIPPLE * math.sin(2 * math.pi * t / 600.0 + self.phase[d.id])) * self.demand_forecast
            for d in self.cfg.districts
        }
        load = {d: (demand[d] if self.expected_main[d] else 0.0) for d in demand}
        in_service = {l.id for l in self.cfg.lines} - self.expected_open_lines
        flows, energised = solve(self.cfg.node_ids, list(self.cfg.lines), in_service, load)
        dark = {d.id for d in self.cfg.districts if not (d.id in energised and self.expected_main[d.id])}
        return flows, dark

    def compute(self, state: dict) -> TwinState:
        flows, exp_dark = self.expected(state["t"] - 1.0)
        exp: dict[str, float] = {}
        res: dict[str, float] = {}
        norm: dict[str, float] = {}
        for ln in self.cfg.lines:
            obs = next(l for l in state["lines"] if l["id"] == ln.id)
            e, r = flows[ln.id], obs["flow_mw"] - flows[ln.id]
            exp[ln.id], res[ln.id], norm[ln.id] = round(e, 2), round(r, 2), round(r / (FLOW_SCALE_PU * ln.capacity_mw), 2)
        obs_dark = {d["id"] for d in state["districts"] if d["status"] == "dark"}
        obs_out = {l["id"] for l in state["lines"] if l["status"] != "in_service"}
        topo = len(obs_out ^ self.expected_open_lines)
        dist = len(obs_dark ^ exp_dark)
        for name, val in (("topology_mismatch", float(topo)), ("district_mismatch", float(dist))):
            exp[name], res[name], norm[name] = 0.0, val, round(val / MISMATCH_SCALE, 2)
        return TwinState(t=state["t"], expected=exp, residual=res, norm_residual=norm)
