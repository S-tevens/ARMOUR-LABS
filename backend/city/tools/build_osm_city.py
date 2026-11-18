"""Builds city/data/bengaluru_osm.json from raw OpenStreetMap data (owner: P2).

Usage (from backend/):  python -m city.tools.fetch_osm && python -m city.tools.build_osm_city

WHAT IS REAL (from OpenStreetMap, (c) OpenStreetMap contributors, ODbL):
  - substation locations, names and voltage levels (the 220 kV and 400 kV substations are the simulated nodes;
    the 66 kV substations are kept as small context dots)
  - the routes of mapped 220/400 kV lines between those substations
  - hospitals (the larger ones) and Namma Metro stations
WHAT IS INFERRED (marked "inferred" and drawn dashed): OpenStreetMap's line mapping is incomplete, so many real ties
  are missing from the data. Where a substation has fewer than two mapped connections, ties to its nearest neighbours
  are added, and separate pieces are joined. The real grid topology is not public, so these are assumptions.
WHAT IS SIMULATED: loads (from the number of mapped 66 kV substations each node would feed), populations, line
  ratings (calibrated so normal operation sits at about 45-68 % loading) and every attack. The facility-to-substation
  assignment is by proximity, not real supply records.

The line ratings are tuned by running the city engine itself until the demo scenarios behave sensibly.
"""
from __future__ import annotations

import datetime
import json
import math
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from city import config  # noqa: E402
from city.engine import CityEngine  # noqa: E402
from city.powerflow import SLACK, Line, solve  # noqa: E402

RAW = Path(__file__).parent / "raw"
OUT = Path(__file__).resolve().parents[1] / "data" / "bengaluru_osm.json"
CENTER = (12.9716, 77.5946)
NORTH = (13.10, 77.60)
KIAL = ("Kempegowda International Airport", 13.1986, 77.7066)  # added by hand, not from the fetched data
PEOPLE_PER_MW = 3500
SNAP_M = 400
FLOOR_MW = {400: 600.0, 220: 150.0}
EXCLUDE = re.compile(r"ccpp|traction", re.I)
BAD_HOSPITAL = ("clinic", "dental", "eye", "diagnostic", "nursing", "maternity", "physio", "ayurved", "homeo", "veterinary", "pet ", "lab")


def load(name):
    return json.loads((RAW / f"{name}.json").read_text(encoding="utf-8"))["elements"]


def volt(tags):
    try:
        return max(int(x) for x in str(tags.get("voltage", "0")).replace(" ", "").split(";"))
    except ValueError:
        return 0


def hav(a, b):
    R = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(d))


def slug(text, taken):
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "substation"
    s, i = base, 2
    while s in taken:
        s, i = f"{base}-{i}", i + 1
    taken.add(s)
    return s


def clean(name):
    n = re.sub(r"\b(sub[- ]?station|kptcl|ss)\b", "", name, flags=re.I)
    n = re.sub(r"\s+", " ", n).strip(" -,")
    return n or "Substation"


def thin(path, keep=28):
    if len(path) <= keep:
        return path
    step = (len(path) - 1) / (keep - 1)
    return [path[round(i * step)] for i in range(keep)]


def build_substations():
    subs = []
    for e in load("substations"):
        tags = e.get("tags", {})
        if e["type"] == "way" and e.get("geometry"):
            pts = [(g["lat"], g["lon"]) for g in e["geometry"]]
            c = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        elif e["type"] == "node":
            pts, c = [(e["lat"], e["lon"])], (e["lat"], e["lon"])
        else:
            continue
        subs.append({"osm": f"{e['type'][0]}{e['id']}", "name": tags.get("name", ""), "v": volt(tags), "pts": pts, "c": c})
    merged = []
    for s in sorted(subs, key=lambda s: -s["v"]):
        if not any(hav(s["c"], m["c"]) < 250 for m in merged):
            merged.append(s)
    return [s for s in merged if not EXCLUDE.search(s["name"])]


def build_graph(nodes):
    """Edges from mapped lines (real) plus inferred ties. Returns {(a, b): {source, voltage_kv, path}} by node index."""
    lines = [l for l in load("lines") if volt(l.get("tags", {})) >= 220000]

    def snap(pt):
        best, bd = None, 1e9
        for i, n in enumerate(nodes):
            if hav(pt, n["c"]) > 2000:
                continue
            d = min(hav(pt, p) for p in n["pts"])
            if d < bd:
                best, bd = i, d
        return best if bd <= SNAP_M else None

    edges: dict[tuple[int, int], dict] = {}
    for l in lines:
        geo = [(g["lat"], g["lon"]) for g in l.get("geometry", [])]
        last = None
        for idx, pt in enumerate(geo):
            i = snap(pt)
            if i is None:
                continue
            if last is not None and last[0] != i:
                a, b = last[0], i
                path = [list(map(lambda x: round(x, 5), p)) for p in geo[last[1]: idx + 1]]
                key = (min(a, b), max(a, b))
                if key not in edges or len(path) > len(edges[key]["path"]):
                    edges[key] = {"source": "osm", "voltage_kv": volt(l["tags"]) // 1000,
                                  "path": path if a < b else path[::-1]}
            last = (i, idx)
    adj = defaultdict(set)
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)

    def add(a, b):
        key = (min(a, b), max(a, b))
        if key in edges:
            return
        edges[key] = {"source": "inferred", "voltage_kv": 220, "path": None}
        adj[a].add(b)
        adj[b].add(a)

    n = len(nodes)
    dist = lambda a, b: hav(nodes[a]["c"], nodes[b]["c"])
    for i in range(n):  # every node gets at least two ties
        order = sorted((j for j in range(n) if j != i and j not in adj[i]), key=lambda j: dist(i, j))
        while len(adj[i]) < 2 and order:
            j = order.pop(0)
            if dist(i, j) <= 18000:
                add(i, j)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        parent[find(a)] = find(b)
    while len({find(i) for i in range(n)}) > 1:  # join separate pieces by their closest pair
        best = min(((dist(i, j), i, j) for i in range(n) for j in range(i + 1, n) if find(i) != find(j)))
        add(best[1], best[2])
        parent[find(best[1])] = find(best[2])
    return edges


def facilities(nodes, node_ids):
    out: dict[int, list] = defaultdict(list)
    hosp = []
    for e in load("hospitals"):
        t = e.get("tags", {})
        name = t.get("name", "")
        low = name.lower()
        score = 3 * (t.get("emergency") == "yes") + 2 * (t.get("healthcare") == "hospital") + 2 * ("wikidata" in t) \
            + ("hospital" in low and not any(b in low for b in BAD_HOSPITAL)) + ("beds" in t)
        c = e.get("center") or {"lat": e.get("lat"), "lon": e.get("lon")}
        if score >= 5 and c["lat"] is not None and not any(b in low for b in BAD_HOSPITAL):
            hosp.append((score, name, (c["lat"], c["lon"])))
    hosp.sort(key=lambda h: (-h[0], h[1]))
    per_node = defaultdict(int)
    taken = 0
    for score, name, pt in hosp:
        i = min(range(len(nodes)), key=lambda k: hav(pt, nodes[k]["c"]))
        if hav(pt, nodes[i]["c"]) > 12000 or per_node[i] >= 2 or taken >= 40:
            continue
        per_node[i] += 1
        taken += 1
        out[i].append({"id": f"{node_ids[i]}-hosp-{per_node[i]}", "type": "hospital", "priority": 1, "name": name,
                       "lat": round(pt[0], 5), "lon": round(pt[1], 5)})
    metro: dict[int, list] = defaultdict(list)
    for e in load("metro"):
        if "lat" not in e:  # metro is optional: skip entries without coordinates
            continue
        pt = (e["lat"], e["lon"])
        metro[min(range(len(nodes)), key=lambda k: hav(pt, nodes[k]["c"]))].append(pt)
    for i, pts in metro.items():
        lat, lon = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        out[i].append({"id": f"{node_ids[i]}-metro", "type": "metro", "priority": 2, "name": f"Namma Metro ({len(pts)} stations)",
                       "lat": round(lat, 5), "lon": round(lon, 5)})
    k = min(range(len(nodes)), key=lambda k: hav(KIAL[1:], nodes[k]["c"]))
    out[k].append({"id": f"{node_ids[k]}-airport", "type": "airport", "priority": 2, "name": KIAL[0], "lat": KIAL[1], "lon": KIAL[2]})
    return out, sum(per_node.values())


def calibrate(nodes, ids, edges, loads, rng_seed):
    """Line ratings from the flows, so normal operation sits at 45-68 % loading. Returns (lines, caps by id)."""
    rng = random.Random(rng_seed)
    entries = [i for i, n in enumerate(nodes) if n["v"] >= 400000]
    pairs = [(f"L{k + 1}", ids[a], ids[b], key) for k, (key, (a, b)) in enumerate((k, k) for k in sorted(edges))]
    pairs += [(f"L{len(pairs) + k + 1}", SLACK, ids[i], None) for k, i in enumerate(entries)]
    target = {lid: rng.uniform(0.45, 0.68) for lid, *_ in pairs}
    volts = {}
    for lid, a, b, key in pairs:
        volts[lid] = 400 if key is None else edges[key]["voltage_kv"]
    caps = {lid: FLOOR_MW.get(volts[lid], 150.0) for lid, *_ in pairs}
    load_by_id = {ids[i]: loads[i] for i in range(len(nodes))}
    for _ in range(5):
        lines = [Line(lid, a, b, caps[lid]) for lid, a, b, _ in pairs]
        flows, _ = solve([SLACK] + ids, lines, {l.id for l in lines}, load_by_id)
        for lid, a, b, _key in pairs:
            floor = FLOOR_MW.get(volts[lid], 150.0)
            caps[lid] = round(max(floor, abs(flows[lid]) / target[lid]), 0)
    return pairs, caps, volts


def n_minus_one(ids, pairs, caps, loads):
    nodes = [SLACK] + ids
    lines = [Line(lid, a, b, caps[lid]) for lid, a, b, _ in pairs]
    load_by_id = dict(zip(ids, loads))
    res = {}
    for lid, a, b, _ in pairs:
        if a == SLACK:
            continue
        flows, en = solve(nodes, lines, {l.id for l in lines} - {lid}, load_by_id)
        if len(en) != len(nodes):
            continue  # a bridge: removing it isolates a node
        res[lid] = max(abs(flows[l.id]) / l.capacity_mw for l in lines if l.id != lid)
    return res


def assemble(seed):
    nodes_all = build_substations()
    nodes = [s for s in nodes_all if s["v"] >= 220000]
    feeders = [s for s in nodes_all if 11000 < s["v"] < 220000]
    taken: set[str] = set()
    ids = []
    for s in nodes:
        s["name"] = clean(s["name"]) if s["name"] else "Unnamed substation"
        ids.append(slug(s["name"], taken))
    edges = build_graph(nodes)

    node_load = [0.0] * len(nodes)
    feeder_out = []
    for f in feeders:
        i = min(range(len(nodes)), key=lambda k: hav(f["c"], nodes[k]["c"]))
        node_load[i] += random.Random(f["osm"]).uniform(8, 20)
        feeder_out.append({"name": clean(f["name"]) if f["name"] else "Substation", "lat": round(f["c"][0], 5),
                           "lon": round(f["c"][1], 5), "voltage_kv": f["v"] // 1000, "parent": ids[i]})
    for i, s in enumerate(nodes):
        node_load[i] += random.Random(s["osm"] + "own").uniform(10, 18) if s["v"] < 400000 else 6.0
    facs, n_hosp = facilities(nodes, ids)
    for i, fl in facs.items():
        node_load[i] += sum({"hospital": 1.5, "metro": 0.8, "airport": 25.0}[f["type"]] * (int(re.findall(r"\d+", f["name"])[0]) if f["type"] == "metro" else 1) for f in fl)
    node_load = [round(x, 1) for x in node_load]
    pairs, caps, volts = calibrate(nodes, ids, edges, node_load, seed)
    return nodes, ids, edges, node_load, facs, feeder_out, pairs, caps, volts, n_hosp


def write(seed, defaults, featured, parts):
    nodes, ids, edges, node_load, facs, feeder_out, pairs, caps, volts, n_hosp = parts
    districts = []
    for i, s in enumerate(nodes):
        districts.append({
            "id": ids[i], "name": s["name"], "lat": round(s["c"][0], 5), "lon": round(s["c"][1], 5),
            "voltage_kv": s["v"] // 1000, "entry": s["v"] >= 400000, "osm_id": s["osm"],
            "population": int(round(node_load[i] * PEOPLE_PER_MW, -3)), "base_load_mw": node_load[i],
            "plant_scale": 1.0 if ids[i] == featured else round(min(3.0, max(0.6, node_load[i] / 30.0)), 2),
            "facilities": facs.get(i, []),
        })
    lines = []
    for lid, a, b, key in pairs:
        item = {"id": lid, "from": a, "to": b, "capacity_mw": caps[lid], "voltage_kv": volts[lid]}
        if key is None:
            item["source"] = "grid-entry"
        else:
            e = edges[key]
            item["source"] = e["source"]
            if e["path"]:
                p = thin(e["path"])
                p[0] = [round(nodes[key[0]]["c"][0], 5), round(nodes[key[0]]["c"][1], 5)]
                p[-1] = [round(nodes[key[1]]["c"][0], 5), round(nodes[key[1]]["c"][1], 5)]
                item["path"] = p
        lines.append(item)
    doc = {
        "name": "Bengaluru power grid",
        "note": "Substations, mapped line routes, hospitals and metro stations are from OpenStreetMap. Ties that OpenStreetMap does not map are inferred (dashed). Loads, line ratings, populations and every attack are simulated; this is not utility data.",
        "attribution": "Map data © OpenStreetMap contributors (ODbL).",
        "data_note": "Real: substation locations, names and voltages; mapped line routes; hospitals; metro stations. Inferred: ties missing from OpenStreetMap. Simulated: loads, ratings, populations, attacks.",
        "source": {"fetched": datetime.date.today().isoformat(), "bbox": "12.80,77.42,13.17,77.82", "calibration_seed": seed},
        "center": [CENTER[0], CENTER[1]], "zoom": 11,
        "featured": featured, "scenario_defaults": defaults,
        "districts": districts, "lines": lines, "feeders": feeder_out,
    }
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")


def evaluate(path):
    """Runs the demo scenarios on the candidate config. Returns (ok, notes)."""
    cfg = config.load(path)
    notes, ok = [], True

    def engine(scenario=None, pre=40):
        e = CityEngine(cfg, 1)
        for _ in range(pre):
            e.step()
        if scenario:
            e.start_scenario(scenario)
        return e

    def run(e, n):
        worst, st = 0.0, None
        for _ in range(n):
            st = e.step().state
            worst = max(worst, max(l["loading"] for l in st["lines"]))
        return st, worst

    st, w = run(engine(pre=0), 160)
    if w > 0.8 or st["impact"]["people_unserved"]:
        return False, [f"normal max loading {w:.2f}"]
    st, w = run(engine("evening_peak"), 90)
    if w > 0.93 or any(l["status"] != "in_service" for l in st["lines"]):
        return False, [f"evening peak max loading {w:.2f}"]
    for sc in ("planned_maintenance", "line_fault"):
        st, w = run(engine(sc), 60)
        if w > 0.95 or st["impact"]["people_unserved"]:
            return False, [f"{sc}: max loading {w:.2f}, unserved {st['impact']['people_unserved']}"]
    e = engine("coordinated_substation_trip")
    st, _ = run(e, 4)
    dark = {d["id"] for d in st["districts"] if d["status"] == "dark"}
    if dark != set(cfg.defaults["trip_districts"]):
        return False, [f"trip darkens {sorted(dark)}"]
    total = sum(d["population"] for d in st["districts"])
    e = engine("load_altering_attack")
    first = None
    for i in range(80):
        st = e.step().state
        if first is None and any(l["status"] == "tripped" for l in st["lines"]):
            first = i
    frac = st["impact"]["people_unserved"] / total
    if first is None or first > 55 or not 0.05 <= frac <= 0.7:
        return False, [f"load-altering: first trip {first}, unserved fraction {frac:.2f}"]
    e.begin_containment()
    for i in range(500):
        st = e.step().state
        if not e.containment and not e.dark_districts() and all(l["status"] == "in_service" for l in st["lines"]):
            break
    else:
        return False, ["load-altering containment did not restore the city"]
    notes.append(f"load-altering: first trip at +{first}s, {frac:.0%} of people dark, restored in {i + 1}s")
    return ok, notes


def main():
    nodes_all = build_substations()
    nodes = [s for s in nodes_all if s["v"] >= 220000]
    print(f"{len(nodes)} simulated substations (220/400 kV); {sum(1 for s in nodes_all if 11000 < s['v'] < 220000)} 66 kV context substations")
    ids_preview = sorted(range(len(nodes)), key=lambda k: hav(CENTER, nodes[k]["c"]))
    best = None
    for seed in range(1, 120):
        parts = assemble(seed)
        _, ids, edges, node_load, facs, *_rest = parts
        pairs, caps, volts = parts[6], parts[7], parts[8]
        if len(parts[0]) != len(nodes):
            continue
        # scenario defaults
        central = [i for i in ids_preview if nodes[i]["v"] < 400000 and any(f["type"] == "hospital" for f in facs.get(i, []))][:3]
        if len(central) < 3:
            raise SystemExit("not enough central substations with hospitals")
        north = min((i for i in range(len(nodes)) if nodes[i]["v"] < 400000 and i not in central), key=lambda k: hav(NORTH, nodes[k]["c"]))
        nm1 = n_minus_one(ids, pairs, caps, node_load)
        good = sorted(((v, lid) for lid, v in nm1.items() if 0.55 <= v <= 0.88), reverse=True)
        if len(good) < 2:
            continue
        featured = next((ids[i] for i in central if "nimhans" in ids[i]), ids[central[0]])  # a real hospital institute's substation
        defaults = {"trip_districts": [ids[i] for i in central], "stale_districts": [ids[north]],
                    "fault_line": good[0][1], "maintenance_line": good[1][1]}
        write(seed, defaults, featured, parts)
        ok, notes = evaluate(OUT)
        print(f"seed {seed:3d}: {'OK ' if ok else 'no '} {'; '.join(notes)}")
        if ok:
            best = seed
            break
    if best is None:
        raise SystemExit("no calibration seed passed the scenario checks")
    d = json.loads(OUT.read_text(encoding="utf-8"))
    n_osm = sum(1 for l in d["lines"] if l["source"] == "osm")
    n_inf = sum(1 for l in d["lines"] if l["source"] == "inferred")
    print(f"wrote {OUT.name}: {len(d['districts'])} substations, {n_osm} mapped lines + {n_inf} inferred ties + "
          f"{sum(1 for l in d['lines'] if l['source'] == 'grid-entry')} grid entries, "
          f"{sum(len(x['facilities']) for x in d['districts'])} facilities, {len(d['feeders'])} 66 kV context substations")
    print("featured:", d["featured"], "| defaults:", d["scenario_defaults"])


if __name__ == "__main__":
    main()
