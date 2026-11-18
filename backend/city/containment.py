"""City containment (owner: P2): staged, priority-ordered restoration.

Stage 0: block the malicious source (attacks), stop the load-altering effect, restore the control-centre view.
Then, once demand is back to normal:
  1. isolate: open the breakers of districts that were cut off by a cascade, so reclosing lines carries no load
  2. reclose and repair out-of-service lines (with no load on them, so nothing re-trips)
  3. re-energise districts one at a time, hospitals first, and only if doing so would not overload any line;
     otherwise hold the district back and retry later
Every change is an authorised SCADA command and is logged.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from city.scenarios import ATTACKER_IP, SCENARIO_INFO

if TYPE_CHECKING:
    from city.engine import CityEngine

STEP_EVERY_TICKS = 2
SAFE_LOADING = 1.0
DEMAND_SETTLED = 0.06  # how close the demand factor must be to its schedule before restoring


class CityContainment:
    def __init__(self, scenario: str | None, start_tick: int) -> None:
        self.scenario = scenario
        self.start_tick = start_tick
        self.done = False
        self.queue: list[tuple[str, str]] | None = None
        self._last_step = -999

    def on_tick(self, eng: "CityEngine") -> None:
        n = eng.tick - self.start_tick
        if n == 0:
            self._block(eng)
            return
        settled = abs(eng.attack_factor - 1.0) < DEMAND_SETTLED and abs(eng.forecast - eng.forecast_target) < DEMAND_SETTLED
        if not settled:
            return
        if self.queue is None:
            self.queue = self._plan(eng)
        if self.queue and eng.tick - self._last_step >= STEP_EVERY_TICKS:
            self._last_step = eng.tick
            self._restore_next(eng)
        if not self.queue:
            eng.log_action("City restored; monitoring for stability")
            self.done = True

    def _block(self, eng: "CityEngine") -> None:
        kind = SCENARIO_INFO.get(self.scenario or "", {}).get("kind")
        if kind == "attack":
            eng.emit("FIREWALL", ATTACKER_IP, "BLOCK", "SOURCE", ATTACKER_IP, True)
            eng.log_action(f"Blocked source {ATTACKER_IP} at the firewall; unauthorised commands now rejected")
            eng.attack_target = 1.0
            eng.stale.clear()
            eng.log_action("Control centre sees every district again; charger load released")
        else:
            eng.log_action("No malicious source to block")
        eng.active = None

    def _plan(self, eng: "CityEngine") -> list[tuple[str, str]]:
        queue: list[tuple[str, str]] = []
        # 1. isolate districts left dark by a cascade, so lines can be reclosed with no load on them
        for did in eng.dark_districts():
            if eng.main_closed[did]:
                eng.command(f"DIST_MAIN_{did.upper()}", "OPEN")
                eng.log_action(f"Isolated {eng.cfg.district(did).name} so lines can be reclosed without load")
        # 2. lines
        for lid, reason in sorted(eng.out_reason.items()):
            if reason in ("protection", "fault"):
                queue.append(("line", lid))
        # 3. districts, hospitals first
        dark = [d for d in eng.cfg.districts if not eng.main_closed[d.id]]
        dark.sort(key=lambda d: (d.top_priority, -d.population))
        queue += [("district", d.id) for d in dark]
        return queue

    def _restore_next(self, eng: "CityEngine") -> None:
        kind, ident = self.queue[0]
        if kind == "line":
            if eng.out_reason.get(ident) == "fault":
                eng.out_reason[ident] = "command"
                eng.log_action(f"Repaired line {ident}")
            eng.command(f"LINE_{ident}", "CLOSE")
            eng.log_action(f"Reclosed line {ident}")
            self.queue.pop(0)
            return
        d = eng.cfg.district(ident)
        eng.main_closed[ident] = True  # trial: would this district overload a line?
        flows, _ = eng._solve(eng.demand_mw)
        worst = max((abs(flows[l.id]) / l.capacity_mw for l in eng.cfg.lines if l.id in eng.service), default=0.0)
        eng.main_closed[ident] = False
        if worst > SAFE_LOADING and len(self.queue) > 1:
            self.queue.append(self.queue.pop(0))
            eng.log_action(f"Holding {d.name}: restoring it now would overload a line")
            return
        eng.command(f"DIST_MAIN_{ident.upper()}", "CLOSE")
        has_hosp = any(f.type == "hospital" for f in d.facilities)
        eng.log_action(f"Restored {d.name}" + (" (hospital first)" if has_hosp else ""))
        eng.unit_actions.append((ident, "grid_restored"))
        self.queue.pop(0)
