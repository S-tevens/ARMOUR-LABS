"""City detector and incident manager (owner: P3). Rule-based v0.

Scores follow the substation baseline: network (unauthorised messages), process (fixed limits: dark districts,
line loading, frequency) and twin (distance from the authorised-topology expectation). Classification is a small
executable rule table, not machine learning yet:

  unauthorised command seen                       -> attack  (higher confidence when impact or residual agrees)
  unexplained line trip, no unauthorised message  -> fault
  anything else                                   -> unknown

Evidence text is built only from real values in the city state and events. Incidents on two or more districts that
share the unauthorised source are grouped into one campaign.
"""
from __future__ import annotations

from collections import deque

from core.contracts import Evidence, Incident, NetworkEvent, Scores, TwinState

ALERT_THRESHOLD = 0.8
RECENT_WINDOW_S = 10.0


class CityDetector:
    def __init__(self) -> None:
        self.recent: deque[NetworkEvent] = deque()  # unauthorised events in the window

    def reset(self) -> None:
        self.recent.clear()

    def score(self, st: dict, twin: TwinState, events: list[NetworkEvent]) -> Scores:
        for e in events:
            if not e.authorised:
                self.recent.append(e)
        while self.recent and st["t"] - self.recent[0].t > RECENT_WINDOW_S:
            self.recent.popleft()
        net = 0.9 if self.recent else 0.0
        worst_load = max((l["loading"] for l in st["lines"]), default=0.0)
        dark = any(d["status"] == "dark" for d in st["districts"])
        process = max(
            1.0 if dark else 0.0,
            1.0 if worst_load > 1.0 else 0.6 if worst_load > 0.9 else worst_load / 1.5,
            min(1.0, abs(st["frequency"] - 50.0) / 0.5),
        )
        twin_score = min(1.0, max(abs(v) for v in twin.norm_residual.values()) / 6.0)
        return Scores(t=st["t"], network=round(net, 3), controller=round(net, 3),
                      process=round(min(1.0, process), 3), twin=round(twin_score, 3))

    @staticmethod
    def is_alert(s: Scores) -> bool:
        return max(s.network, s.controller, s.process, s.twin) >= ALERT_THRESHOLD


def _names(st: dict, ids: list[str]) -> str:
    by = {d["id"]: d["name"] for d in st["districts"]}
    return ", ".join(by.get(i, i) for i in ids)


class CityIncidentManager:
    def __init__(self) -> None:
        self.incidents: dict[str, Incident] = {}
        self._counter = 0
        self._seen: dict[str, dict[int, NetworkEvent]] = {}  # incident id -> unauthorised events it has seen

    def reset(self) -> None:
        """A hard reset starts from a clean slate: no incidents, no remembered evidence."""
        self.incidents.clear()
        self._seen.clear()
        self._counter = 0

    def active(self) -> Incident | None:
        for inc in self.incidents.values():
            if inc.status in ("open", "responding", "recovering"):
                return inc
        return None

    def _build(self, st: dict, twin: TwinState, scores: Scores, recent: list[NetworkEvent],
               expected_open: set[str]) -> tuple[list[Evidence], str, float, list[str], str | None]:
        ev: list[Evidence] = []
        dark = [d["id"] for d in st["districts"] if d["status"] == "dark"]
        unexplained = [l["id"] for l in st["lines"] if l["status"] in ("tripped", "fault") and l["id"] not in expected_open]
        hot = [(l["id"], l["loading"]) for l in st["lines"] if l["loading"] > 1.0 and l["status"] == "in_service"]
        srcs = sorted({e.src for e in recent})
        dsts = sorted({e.dst for e in recent})
        if recent:
            ev.append(Evidence(type="unauthorised_event", tag="observed",
                               text=f"{len(recent)} unauthorised command{'s' if len(recent) != 1 else ''} from {', '.join(srcs)} to {', '.join(dsts)}"))
        if dark:
            ev.append(Evidence(type="district_dark", tag="observed",
                               text=f"{_names(st, dark)} without power ({st['impact']['people_unserved']:,} people)"))
        if unexplained:
            ev.append(Evidence(type="topology_mismatch", tag="observed",
                               text=f"Line{'s' if len(unexplained) != 1 else ''} {', '.join(unexplained)} out of service without an authorised command"))
        for lid, load in hot:
            ev.append(Evidence(type="line_overload", tag="observed", text=f"Line {lid} at {load * 100:.0f}% of its capacity"))
        if st["impact"]["hospitals_on_backup"] or st["impact"]["hospitals_down"]:
            ev.append(Evidence(type="hospital_impact", tag="observed",
                               text=f"{st['impact']['hospitals_on_backup']} hospital(s) on backup power, {st['impact']['hospitals_down']} without power"))
        if recent:
            cls, conf = "attack", 0.8 if (dark or hot or unexplained) else 0.6
        elif unexplained:
            cls, conf = "fault", 0.6
        else:
            cls, conf = "unknown", 0.3
        affected = [f"SUB-{i.upper()}" for i in dark] if dark else dsts or unexplained
        districts_hit = {e.dst for e in recent if e.dst.startswith("SUB-")}
        campaign = "CMP-001" if len(districts_hit) >= 2 else None
        return ev, cls, conf, affected or dsts, campaign

    def update(self, st: dict, twin: TwinState, scores: Scores, alert: bool, detector: CityDetector,
               expected_open: set[str]) -> Incident | None:
        """Creates or refreshes the open incident. Returns it when it is created or its status changes."""
        inc = self.active()
        recent = list(detector.recent)
        if inc is None:
            if not alert:
                return None
            self._counter += 1
            ev, cls, conf, affected, campaign = self._build(st, twin, scores, recent, expected_open)
            inc = Incident(
                id=f"CIT-{self._counter:03d}", t_start=st["t"],
                severity="high" if st["impact"]["people_unserved"] > 0 or max(scores.network, scores.twin) >= 0.9 else "medium",
                confidence=conf, affected_devices=affected, classification=cls,
                scores=scores.model_dump(exclude={"t"}), evidence=ev, status="open", campaign_id=campaign,
            )
            self.incidents[inc.id] = inc
            self._seen[inc.id] = {e.seq: e for e in recent}
            return inc
        if inc.status == "open":  # the impact evolves while the incident is open: refresh from real data
            seen = self._seen.setdefault(inc.id, {})
            seen.update({e.seq: e for e in recent})
            ev, cls, conf, affected, campaign = self._build(st, twin, scores, list(seen.values()), expected_open)
            inc.evidence, inc.classification, inc.confidence = ev, cls, conf
            inc.affected_devices, inc.campaign_id = affected, campaign or inc.campaign_id
            inc.scores = scores.model_dump(exclude={"t"})
        return None
