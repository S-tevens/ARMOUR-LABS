"""Loads the city layout (owner: P2).

Two layouts exist:
  bengaluru_osm.json  the real default: substations, mapped lines, hospitals and metro stations from OpenStreetMap,
                      with SIMULATED loads, line ratings and attacks (built by city/tools/build_osm_city.py)
  synthetic.json      a small fictional network used by the automated tests

Choose with the ARMOUR_CITY environment variable ("osm", the default, or "synthetic") or by passing a path.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from city.powerflow import SLACK, Line

DATA_DIR = Path(__file__).parent / "data"
LAYOUTS = {"osm": DATA_DIR / "bengaluru_osm.json", "synthetic": DATA_DIR / "synthetic.json"}
FACILITY_PRIORITY = {"hospital": 1, "water": 2, "metro": 2, "airport": 2, "tech": 3}


@dataclass(frozen=True)
class Facility:
    id: str
    type: str
    priority: int
    name: str = ""
    lat: float | None = None
    lon: float | None = None


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
    lat: float | None = None
    lon: float | None = None
    voltage_kv: int | None = None
    entry: bool = False  # a grid entry point (400 kV): fed from the state grid

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
    terminals: dict[str, tuple[float, float]] = field(default_factory=dict)  # synthetic layout: map position of a grid end
    defaults: dict = field(default_factory=dict)  # scenario defaults: trip_districts, stale_districts, fault_line, maintenance_line
    meta: dict = field(default_factory=dict)  # attribution, centre, zoom, data provenance, feeders
    line_meta: dict = field(default_factory=dict)  # line id -> {voltage_kv, source, path}

    def district(self, did: str) -> District:
        return next(d for d in self.districts if d.id == did)

    @property
    def node_ids(self) -> list[str]:
        return [SLACK] + [d.id for d in self.districts]


def resolve(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    return LAYOUTS.get(os.getenv("ARMOUR_CITY", "osm"), LAYOUTS["osm"])


def load(path: str | Path | None = None) -> CityConfig:
    raw = json.loads(resolve(path).read_text(encoding="utf-8"))
    districts = tuple(
        District(
            id=d["id"], name=d["name"], x=d.get("x", 0.0), y=d.get("y", 0.0), population=d["population"],
            base_load_mw=d["base_load_mw"], plant_scale=d["plant_scale"],
            facilities=tuple(Facility(f["id"], f["type"], f["priority"], f.get("name", ""), f.get("lat"), f.get("lon")) for f in d["facilities"]),
            lat=d.get("lat"), lon=d.get("lon"), voltage_kv=d.get("voltage_kv"), entry=d.get("entry", False),
        )
        for d in raw["districts"]
    )
    lines = tuple(Line(l["id"], l["from"], l["to"], float(l["capacity_mw"])) for l in raw["lines"])
    terminals = {l["id"]: tuple(l["terminal"]) for l in raw["lines"] if "terminal" in l}
    line_meta = {l["id"]: {k: l[k] for k in ("voltage_kv", "source", "path") if k in l} for l in raw["lines"]}
    meta = {k: raw[k] for k in ("attribution", "center", "zoom", "source", "feeders", "data_note") if k in raw}
    return CityConfig(raw["name"], raw["note"], raw["featured_district"] if "featured_district" in raw else raw["featured"],
                      districts, lines, terminals, raw.get("scenario_defaults", {}), meta, line_meta)
