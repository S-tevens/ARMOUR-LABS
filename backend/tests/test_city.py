import copy

from fastapi.testclient import TestClient

from api.app import create_app
from api.city_runtime import CityRuntime
from city import config
from city.engine import CityEngine
from city.powerflow import SLACK, Line, solve
from city.twin import CityTwin

CFG = config.load()


def run(e, n):
    last = None
    for _ in range(n):
        last = e.step().state
    return last


def city_warm(pre=40, seed=42):
    c = CityRuntime(seed=seed)
    for _ in range(pre):
        c.step()
    return c


def run_until(c, pred, n):
    for i in range(n):
        c.step()
        if pred():
            return i + 1
    return None


# ---------------- power flow ----------------
def test_power_flow_known_cases():
    lines = [Line("a", SLACK, "A", 100), Line("b", "A", "B", 100)]
    flows, en = solve([SLACK, "A", "B"], lines, {"a", "b"}, {"A": 0.0, "B": 30.0})
    assert abs(flows["a"] - 30) < 1e-6 and abs(flows["b"] - 30) < 1e-6 and en == {SLACK, "A", "B"}
    # two parallel paths of equal capacity share the load equally
    lines = [Line("a", SLACK, "A", 100), Line("b", SLACK, "B", 100), Line("c", "A", "B", 100)]
    flows, _ = solve([SLACK, "A", "B"], lines, {"a", "b", "c"}, {"A": 20.0, "B": 20.0})
    assert abs(flows["a"] - 20) < 1e-6 and abs(flows["b"] - 20) < 1e-6 and abs(flows["c"]) < 1e-6


def test_power_flow_conserves_energy_and_detects_islands():
    nodes, lines = CFG.node_ids, list(CFG.lines)
    load = {d.id: d.base_load_mw for d in CFG.districts}
    flows, en = solve(nodes, lines, {l.id for l in lines}, load)
    imported = sum(flows[l.id] for l in lines if l.a == SLACK)
    assert abs(imported - sum(load.values())) < 1e-6 and len(en) == len(nodes)
    # cutting the only feed to Yelahanka (L4) leaves it dark; the others stay lit
    flows, en = solve(nodes, lines, {l.id for l in lines} - {"L4"}, load)
    assert "yl" not in en and "hb" in en and flows["L4"] == 0.0


def test_city_config_is_consistent():
    assert len(CFG.districts) == 8 and len(CFG.lines) == 13 and CFG.featured in {d.id for d in CFG.districts}
    ids = set(CFG.node_ids)
    assert all(l.a in ids and l.b in ids for l in CFG.lines)
    assert all(any(f.type == "hospital" for f in d.facilities) or d.id in ("yl",) for d in CFG.districts)


# ---------------- city engine ----------------
def test_normal_city_is_stable_and_deterministic():
    a, b = CityEngine(CFG, 1), CityEngine(CFG, 1)
    worst = 0.0
    for _ in range(700):
        sa, sb = a.step().state, b.step().state
        assert sa == sb
        worst = max(worst, max(l["loading"] for l in sa["lines"]))
    assert worst < 0.8 and sa["frequency"] == 50.0
    assert all(d["status"] == "ok" for d in sa["districts"]) and sa["impact"]["people_unserved"] == 0


def test_coordinated_trip_darkens_districts_and_hospitals_run_down_their_backup():
    e = CityEngine(CFG, 1)
    run(e, 30)
    e.start_scenario("coordinated_substation_trip")
    st = run(e, 3)
    assert [d["id"] for d in st["districts"] if d["status"] == "dark"] == ["in", "jy", "kr"]
    assert st["impact"]["people_unserved"] == 2_450_000 and st["impact"]["hospitals_on_backup"] == 3
    assert st["frequency"] > 50.2  # load rejection
    ens = st["impact"]["energy_not_served_mwh"]
    st = run(e, 100)  # 90 minutes of accelerated time: backup is exhausted
    assert st["impact"]["hospitals_down"] == 3 and st["impact"]["critical_sites_down"] >= 3
    assert st["impact"]["energy_not_served_mwh"] > ens


def test_load_altering_attack_overloads_lines_and_cascades():
    e = CityEngine(CFG, 1)
    run(e, 30)
    e.start_scenario("load_altering_attack")
    st = run(e, 40)
    tripped = [l["id"] for l in st["lines"] if l["status"] == "tripped"]
    assert tripped and st["impact"]["people_unserved"] > 0


def test_benign_scenarios_stay_inside_limits():
    e = CityEngine(CFG, 1)
    run(e, 30)
    e.start_scenario("evening_peak")
    st = run(e, 90)
    assert max(l["loading"] for l in st["lines"]) < 0.95 and st["impact"]["people_unserved"] == 0
    e = CityEngine(CFG, 1)
    run(e, 30)
    e.start_scenario("planned_maintenance")
    st = run(e, 60)
    assert [l["id"] for l in st["lines"] if l["status"] == "open"] == ["L5"]
    assert max(l["loading"] for l in st["lines"]) < 0.95 and st["impact"]["people_unserved"] == 0


def test_line_fault_reroutes_without_blackout():
    e = CityEngine(CFG, 1)
    run(e, 30)
    e.start_scenario("line_fault")
    st = run(e, 30)
    assert [l["id"] for l in st["lines"] if l["status"] == "fault"] == ["L6"]
    assert st["impact"]["people_unserved"] == 0


# ---------------- city twin ----------------
def test_city_twin_ignores_observed_topology_when_forming_expectations():
    c = city_warm()
    st = c.state
    tw1, tw2 = CityTwin(CFG), CityTwin(CFG)
    a = tw1.compute(st)
    broken = copy.deepcopy(st)
    broken["districts"][0]["status"] = "dark"
    broken["lines"][3]["status"] = "tripped"
    b = tw2.compute(broken)
    assert a.expected == b.expected  # expectations come only from authorised commands and the forecast
    assert a.residual["district_mismatch"] == 0 and b.residual["district_mismatch"] == 1
    assert b.residual["topology_mismatch"] == 1


# ---------------- city runtime: detection, classification, containment ----------------
def test_quiet_normal_operation_and_benign_scenarios_raise_no_city_incident():
    for scenario in (None, "planned_maintenance", "evening_peak"):
        c = city_warm(30)
        if scenario:
            c.engine.start_scenario(scenario)
        for _ in range(120):
            c.step()
        assert c.incidents.incidents == {}, scenario


def test_coordinated_trip_is_an_attack_campaign_with_evidence_that_persists():
    c = city_warm()
    c.engine.start_scenario("coordinated_substation_trip")
    assert run_until(c, lambda: bool(c.incidents.incidents), 5) is not None
    for _ in range(30):  # the 10 s network window passes; the evidence must not vanish
        c.step()
    inc = next(iter(c.incidents.incidents.values()))
    assert inc.classification == "attack" and inc.campaign_id == "CMP-001" and inc.severity == "high"
    assert inc.affected_devices == ["SUB-IN", "SUB-JY", "SUB-KR"]
    texts = " ".join(e.text for e in inc.evidence)
    assert "3 unauthorised commands from 10.0.0.66" in texts and "2,450,000 people" in texts


def test_city_containment_restores_in_priority_order_and_verifies_recovery():
    c = city_warm()
    c.engine.start_scenario("coordinated_substation_trip")
    run_until(c, lambda: bool(c.incidents.incidents), 5)
    inc = next(iter(c.incidents.incidents.values()))
    c.approve_response(inc.id)
    assert inc.status == "recovering"
    assert run_until(c, lambda: c.last_report.state in ("recovered", "unresolved"), 200) is not None
    assert c.last_report.state == "recovered" and inc.status == "recovered"
    actions = [a["action"] for a in c.engine.containment_log]
    assert actions[0].startswith("Blocked source") and any("Restored Koramangala" in a for a in actions)
    assert len(c.incidents.incidents) == 1  # no second incident after recovery
    assert all(d["status"] == "ok" for d in c.state["districts"])


def test_cascade_is_restored_by_isolating_reclosing_then_energising():
    c = city_warm()
    c.engine.start_scenario("load_altering_attack")
    run_until(c, lambda: c.state["impact"]["people_unserved"] > 0, 60)
    inc = next(iter(c.incidents.incidents.values()))
    assert inc.classification == "attack"
    c.approve_response(inc.id)
    assert run_until(c, lambda: c.last_report.state in ("recovered", "unresolved"), 300) is not None
    assert c.last_report.state == "recovered"
    actions = [a["action"] for a in c.engine.containment_log]
    first_isolate = next(i for i, a in enumerate(actions) if a.startswith("Isolated"))
    first_line = next(i for i, a in enumerate(actions) if a.startswith("Reclosed line"))
    first_restore = next(i for i, a in enumerate(actions) if a.startswith("Restored"))
    assert first_isolate < first_line < first_restore  # staged: no load on a line while it is reclosed


def test_line_fault_is_a_fault_and_comms_loss_an_attack():
    c = city_warm()
    c.engine.start_scenario("line_fault")
    run_until(c, lambda: bool(c.incidents.incidents), 5)
    inc = next(iter(c.incidents.incidents.values()))
    assert inc.classification == "fault" and inc.affected_devices == ["L6"]
    c2 = city_warm()
    c2.engine.start_scenario("comms_loss")
    run_until(c2, lambda: bool(c2.incidents.incidents), 5)
    assert next(iter(c2.incidents.incidents.values())).classification == "attack"
    assert any(d["status"] == "stale" for d in c2.state["districts"])


def test_districts_react_to_the_city_and_carry_their_own_incidents():
    c = city_warm()
    c.engine.start_scenario("coordinated_substation_trip")
    for _ in range(15):
        c.step()
    kr = c.units["kr"]
    assert kr.engine.plant.grid_available is False
    assert c.units["ec"].engine.plant.grid_available is True
    assert any(i.district == "kr" for i in kr.incidents.incidents.values())
    # the substation of an untouched district is unaffected
    assert not c.units["wf"].incidents.incidents


# ---------------- API ----------------
def test_city_api_end_to_end():
    app = create_app(autostart=False)
    city = app.state.city
    with TestClient(app) as c:
        lay = c.get("/city").json()["layout"]
        assert len(lay["districts"]) == 8 and len(lay["lines"]) == 13 and "fictional" in lay["note"].lower()
        assert {s["name"] for s in c.get("/city/scenarios").json()} >= {"coordinated_substation_trip", "load_altering_attack"}
        for _ in range(30):
            city.step()
        with c.websocket_connect("/ws/city") as ws:
            assert c.post("/city/scenario/start", json={"name": "coordinated_substation_trip"}).status_code == 200
            for _ in range(3):
                city.step()
            msgs = [ws.receive_json() for _ in range(3)]
            assert msgs[0]["type"] == "city" and "impact" in msgs[0]["data"] and msgs[0]["data"]["status"]
        incs = c.get("/city/incidents").json()
        assert len(incs) == 1 and incs[0]["classification"] == "attack"
        assert c.post(f"/city/incident/{incs[0]['id']}/approve-response").json()["status"] == "recovering"
        for _ in range(60):
            city.step()
        assert c.get("/city/recovery").json()["report"]["state"] == "recovered"
        # per-district substation API
        assert c.get("/incidents", params={"district": "kr"}).status_code == 200
        assert c.get("/incidents", params={"district": "nope"}).status_code == 404
        assert c.post("/city/scenario/start", json={"name": "nope"}).status_code == 404
        assert c.post("/city/scenario/start", json={"name": "comms_loss", "districts": ["zz"]}).status_code == 422


def test_stop_and_reset_gives_a_clean_slate_for_the_next_incident():
    c = city_warm()
    c.engine.start_scenario("load_altering_attack")
    run_until(c, lambda: bool(c.incidents.incidents), 5)
    for _ in range(8):
        c.step()
    assert any("EV-GATEWAY" in e.text for e in next(iter(c.incidents.incidents.values())).evidence)
    c.reset()
    assert c.incidents.incidents == {} and c.last_report.state == "idle" and c.engine.containment_log == []
    for _ in range(15):
        c.step()
    c.engine.start_scenario("coordinated_substation_trip")
    run_until(c, lambda: bool(c.incidents.incidents), 5)
    for _ in range(5):
        c.step()
    inc = next(iter(c.incidents.incidents.values()))
    assert inc.id == "CIT-001"
    assert not any("EV-GATEWAY" in e.text for e in inc.evidence)  # nothing left over from the previous incident
    assert inc.classification == "attack" and inc.campaign_id == "CMP-001"
