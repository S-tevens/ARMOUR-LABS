"""Loads the fictional city layout (owner: P2)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from city.powerflow import SLACK, Line

DATA = Path(__file__).parent / "data" / "bengaluru.json"
FACILITY_PRIORITY = {"hospital": 1, "water": 2, "metro": 2, "airport": 2, "tech": 3}


@dataclass(frozen=True)
class Facility:
    id: str
    type: str
    priority: int


@dataclass(frozen=True)
class District:
    id: str
    name: str
    x: float
    y: float
    population: int
    base_load_mw: float
    plant_scale: float
    facilities: tuple[Facility, ...]

    @property
    def top_priority(self) -> int:
        return min((f.priority for f in self.facilities), default=9)


@dataclass(frozen=True)
class CityConfig:
    name: str
    note: str
    featured: str
    districts: tuple[District, ...]
    lines: tuple[Line, ...]
    terminals: dict[str, tuple[float, float]] = field(default_factory=dict)  # line id -> map position of its grid end

    def district(self, did: str) -> District:
        return next(d for d in self.districts if d.id == did)

    @property
    def node_ids(self) -> list[str]:
        return [SLACK] + [d.id for d in self.districts]


def load(path: Path = DATA) -> CityConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    districts = tuple(
        District(
            id=d["id"], name=d["name"], x=d["x"], y=d["y"], population=d["population"],
            base_load_mw=d["base_load_mw"], plant_scale=d["plant_scale"],
            facilities=tuple(Facility(f["id"], f["type"], f["priority"]) for f in d["facilities"]),
        )
        for d in raw["districts"]
    )
    lines = tuple(Line(l["id"], l["from"], l["to"], float(l["capacity_mw"])) for l in raw["lines"])
    terminals = {l["id"]: tuple(l["terminal"]) for l in raw["lines"] if "terminal" in l}
    return CityConfig(raw["name"], raw["note"], raw["featured_district"], districts, lines, terminals)
