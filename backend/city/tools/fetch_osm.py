"""Fetches the raw OpenStreetMap data for the Bengaluru grid from the Overpass API (owner: P2).

Usage (from backend/):  python -m city.tools.fetch_osm

Writes substations.json, lines.json, hospitals.json and metro.json into city/tools/raw/ (git-ignored). Then run
`python -m city.tools.build_osm_city` to build city/data/bengaluru_osm.json. The result is committed, so the app
never needs the network for data.

Data: (c) OpenStreetMap contributors, ODbL. Be polite to the public Overpass servers: the script identifies itself,
retries with backoff and does not hammer. No personal information is sent.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

RAW = Path(__file__).parent / "raw"
BBOX = "12.80,77.42,13.17,77.82"  # south, west, north, east: Bengaluru
URL = "https://overpass-api.de/api/interpreter"
UA = "armour-labs-hackathon/0.1 (educational power-grid security simulation)"
VOLT = '["voltage"~"^(66|110|220|400)"]'

QUERIES = {
    "substations": f'[out:json][timeout:120];(node["power"="substation"]{VOLT}({BBOX});way["power"="substation"]{VOLT}({BBOX}););out geom tags;',
    "lines": f'[out:json][timeout:120];(way["power"~"^(line|cable)$"]{VOLT}({BBOX}););out geom tags;',
    "hospitals": f'[out:json][timeout:90];(node["amenity"="hospital"]["name"]({BBOX});way["amenity"="hospital"]["name"]({BBOX}););out center tags;',
    "metro": f'[out:json][timeout:90];(node["railway"="station"]["station"="subway"]({BBOX}););out body;',
}


def fetch(name: str, query: str, attempts: int = 6) -> None:
    wait = 20
    for i in range(1, attempts + 1):
        req = urllib.request.Request(URL, data=urllib.parse.urlencode({"data": query}).encode(), headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=150) as r:
                data = json.loads(r.read().decode("utf-8"))
            RAW.mkdir(parents=True, exist_ok=True)
            (RAW / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
            print(f"{name}: {len(data['elements'])} elements")
            return
        except Exception as e:  # the public servers are often busy: back off and retry
            print(f"{name}: attempt {i} failed ({e}); waiting {wait}s", file=sys.stderr)
            time.sleep(wait)
            wait = min(wait * 2, 120)
    raise SystemExit(f"could not fetch {name}")


if __name__ == "__main__":
    for key, q in QUERIES.items():
        fetch(key, q)
