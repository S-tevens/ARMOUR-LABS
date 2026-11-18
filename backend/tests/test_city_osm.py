"""Tests on the real-topology Bengaluru grid (OpenStreetMap substations, simulated electrical model)."""
import time

from fastapi.testclient import TestClient

from api.app import create_app
from api.city_runtime import CityRuntime
from city import config
from city.engine import CityEngine
from city.powerflow import SLACK, solve

CFG = config.load(config.LAYOUTS["osm"])
D = CFG.defaults
BBOX = (12.78, 77.40, 13.20, 77.85)


def run(e, n):
    st = None
    for _ in range(n):
        st = e.step().state
    return st


def engine(scenario=None, pre=40):
    e = CityEngine(CFG, 1)
    run(e, pre)
    if scenario:
        e.start_scenario(scenario)
    return e


def test_osm_config_structure_and_provenance():
    assert len(CFG.districts) >= 30 and CFG.featured in {d.id for d in CFG.districts}
    assert all(d.lat and d.lon and BBOX[0] <= d.lat <= BBOX[2] and BBOX[1] <= d.lon <= BBOX[3] for d in CFG.districts)
    assert sum(1 for d in CFG.districts if d.entry) == 5 and all(d.voltage_kv == 400 for d in CFG.districts if d.entry)
    sources = [m["source"] for m in CFG.line_meta.values()]
    assert set(sources) == {"osm", "inferred", "grid-entry"} and sources.count("grid-entry") == 5
    assert all(CFG.line_meta[l.id].get("path") for l in CFG.lines if CFG.line_meta[l.id]["source"] == "osm")
    assert "OpenStreetMap" in CFG.meta["attribution"] and "Inferred" in CFG.meta["data_note"] and "Simulated" in CFG.meta["data_note"]
    assert len(CFG.meta["feeders"]) > 30


def test_osm_grid_is_connected_and_supplied_and_defaults_are_valid():
    ids = {d.id for d in CFG.districts}
    lines = {l.id: l for l in CFG.lines}
    flows, energised = solve(CFG.node_ids, list(CFG.lines), set(lines), {d.id: d.base_load_mw for d in CFG.districts})
    assert len(energised) == len(CFG.node_ids)
    assert set(D["trip_districts"]) <= ids and len(D["trip_districts"]) == 3 and set(D["stale_districts"]) <= ids
    assert D["fault_line"] in lines and D["maintenance_line"] in lines and D["fault_line"] != D["maintenance_line"]
    assert all(any(f.type == "hospital" for f in CFG.district(t).facilities) for t in D["trip_districts"])
    imported = sum(flows[l.id] for l in CFG.lines if l.a == SLACK)
    assert abs(imported - sum(d.base_load_mw for d in CFG.districts)) < 1e-6


def test_normal_operation_and_benign_scenarios_are_quiet():
    st = run(engine(pre=0), 200)
    assert max(l["loading"] for l in st["lines"]) < 0.8 and st["impact"]["people_unserved"] == 0 and st["failures"] == []
    for sc in ("evening_peak", "planned_maintenance", "line_fault"):
        st = run(engine(sc), 90)
        assert max(l["loading"] for l in st["lines"]) < 0.95, sc
        assert st["impact"]["people_unserved"] == 0, sc
        assert not any(l["status"] == "tripped" for l in st["lines"]), sc


def test_coordinated_trip_darkens_the_configured_central_substations():
    st = run(engine("coordinated_substation_trip"), 4)
    assert {d["id"] for d in st["districts"] if d["status"] == "dark"} == set(D["trip_districts"])
    assert st["impact"]["hospitals_on_backup"] >= 3 and st["impact"]["people_unserved"] > 0


def test_load_altering_attack_cascades_and_records_the_domino_in_order():
    e = engine("load_altering_attack")
    first = None
    for i in range(80):
        st = e.step().state
        if first is None and any(l["status"] == "tripped" for l in st["lines"]):
            first = i
    assert first is not None and first <= 55
    f = st["failures"]
    assert [x["n"] for x in f] == list(range(1, len(f) + 1)) and [x["t"] for x in f] == sorted(x["t"] for x in f)
    assert f[0]["kind"] == "line" and "tripped" in f[0]["text"]  # the first domino is an overloaded line
    assert any(x["kind"] == "district" for x in f)  # and it knocks substations out
    assert 0.05 <= st["impact"]["people_unserved"] / sum(d["population"] for d in st["districts"]) <= 0.7
    e.begin_containment()
    for _ in range(500):
        st = e.step().state
        if not e.containment and not e.dark_districts() and all(l["status"] == "in_service" for l in st["lines"]):
            break
    else:
        raise AssertionError("not restored")


def test_failures_reset_for_a_new_incident():
    e = engine("coordinated_substation_trip")
    run(e, 5)
    assert e.failures and e.failures[0]["kind"] == "district"
    e.start_scenario("evening_peak")
    assert e.failures == [] and e.energy_not_served_mwh == 0.0


def test_osm_city_runtime_detects_classifies_contains_and_stays_fast():
    c = CityRuntime(seed=42, city="osm")
    assert len(c.units) == len(CFG.districts)
    t0 = time.perf_counter()
    for _ in range(25):
        c.step()
    per_step = (time.perf_counter() - t0) / 25
    assert per_step < 0.5, f"{per_step:.3f}s per city tick with {len(c.units)} substations"
    assert c.incidents.incidents == {}
    c.engine.start_scenario("coordinated_substation_trip")
    for _ in range(6):
        c.step()
    inc = next(iter(c.incidents.incidents.values()))
    assert inc.classification == "attack" and inc.campaign_id == "CMP-001" and len(inc.affected_devices) == 3
    c.approve_response(inc.id)
    for _ in range(200):
        c.step()
        if c.last_report.state in ("recovered", "unresolved"):
            break
    assert c.last_report.state == "recovered" and len(c.incidents.incidents) == 1


def test_api_layout_carries_everything_the_real_map_needs():
    app = create_app(autostart=False, city="osm")
    with TestClient(app) as c:
        lay = c.get("/city").json()["layout"]
        assert lay["attribution"] and lay["center"] and lay["zoom"] and lay["data_note"] and len(lay["feeders"]) > 30
        assert all("lat" in d and "lon" in d and "voltage_kv" in d for d in lay["districts"])
        assert any(l.get("path") for l in lay["lines"]) and {l["source"] for l in lay["lines"]} >= {"osm", "inferred"}
        assert any(f.get("name") for d in lay["districts"] for f in d["facilities"])
        # the substation drill-down works for any real substation
        some = lay["districts"][3]["id"]
        assert c.get("/incidents", params={"district": some}).status_code == 200
