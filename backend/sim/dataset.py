"""Labelled dataset generator (owner: P2).

Usage (from backend/):  python -m sim.dataset --out ../data/generated

Each run is one CSV (one row per second) plus a JSONL file of network events:
  normal_seed<N>.csv / .events.jsonl
  <scenario>_seed<N>.csv / .events.jsonl
and a manifest.json describing the columns, scenarios, timeline and seeds.

Timeline per run: normal for `start` s, scenario active until `stop` s, then `ticks` total
(the tail shows the substation after a hard reset). Splits are by RUN, never by random rows, so
adjacent time windows never leak between train and test.

Label columns: scenario, kind (normal|attack|fault|benign), active, is_attack, is_anomaly.
  is_attack  : malicious activity is happening
  is_anomaly : attack or physical fault (legitimate or natural changes are NOT anomalies)
Ground-truth columns (true_*) are for evaluation only and must not be detector inputs.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from sim.engine import SimulationEngine
from sim.scenarios import SCENARIO_INFO

TICKS = 420
START = 120
STOP = 300
NORMAL_SEEDS = (1, 2, 3, 4)
SCENARIO_SEEDS = (11, 12)

TELEMETRY_COLS = ["t", "tick", "frequency", "bus_voltage", "grid_import_kw", "pv_kw", "bess_kw", "bess_soc",
                  "load_critical_kw", "load_noncritical_kw", "irradiance",
                  "cb_main", "cb_pv", "cb_bess", "cb_crit", "cb_nc", "ied01", "ied02", "ied03"]
TRUTH_COLS = ["true_frequency", "true_bus_voltage", "true_grid_import_kw", "true_pv_kw", "true_load_critical_kw"]
LABEL_COLS = ["scenario", "kind", "active", "is_attack", "is_anomaly"]
COLUMNS = TELEMETRY_COLS + TRUTH_COLS + LABEL_COLS
BOOL_COLS = ("cb_main", "cb_pv", "cb_bess", "cb_crit", "cb_nc")


def generate_run(scenario: str | None, seed: int, ticks: int = TICKS, start: int = START, stop: int = STOP):
    """Returns (rows, events). rows are dicts keyed by COLUMNS; events are NetworkEvent dicts."""
    eng = SimulationEngine(seed)
    rows: list[dict] = []
    events: list[dict] = []
    for i in range(ticks):
        if scenario and i == start:
            eng.start_scenario(scenario)
        if scenario and i == stop:
            eng.stop_scenario()
        gt = eng.ground_truth()  # label for the tick about to be simulated
        r = eng.step()
        t = r.telemetry
        truth = eng.plant.true_state()
        row = t.model_dump(exclude={"ied_status"})
        row.update(t.ied_status.model_dump())
        row.update(
            true_frequency=round(truth["frequency"], 4),
            true_bus_voltage=round(truth["bus_voltage"], 5),
            true_grid_import_kw=round(truth["grid_import_kw"], 3),
            true_pv_kw=round(truth["pv_kw"], 3),
            true_load_critical_kw=round(truth["load_critical_kw"], 3),
        )
        row.update(
            scenario=gt["scenario"], kind=gt["kind"], active=int(gt["active"]),
            is_attack=int(gt["is_attack"]), is_anomaly=int(gt["is_anomaly"]),
        )
        for k in BOOL_COLS:
            row[k] = int(row[k])
        rows.append(row)
        events.extend(e.model_dump() for e in r.events)
    return rows, events


def write_run(out: Path, name: str, rows: list[dict], events: list[dict]) -> None:
    with open(out / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    with open(out / f"{name}.events.jsonl", "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


def write_dataset(out_dir: str | Path, normal_seeds=NORMAL_SEEDS, scenario_seeds=SCENARIO_SEEDS) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    runs: list[dict] = []
    for seed in normal_seeds:
        name = f"normal_seed{seed}"
        rows, events = generate_run(None, seed)
        write_run(out, name, rows, events)
        runs.append({"name": name, "scenario": "normal", "seed": seed, "rows": len(rows), "events": len(events)})
    for scenario in SCENARIO_INFO:
        for seed in scenario_seeds:
            name = f"{scenario}_seed{seed}"
            rows, events = generate_run(scenario, seed)
            write_run(out, name, rows, events)
            runs.append({"name": name, "scenario": scenario, "seed": seed, "rows": len(rows), "events": len(events)})
    manifest = {
        "source": "custom simulator (not a public dataset)",
        "domain": "campus microgrid substation",
        "ticks": TICKS, "scenario_start": START, "scenario_stop": STOP,
        "columns": COLUMNS, "truth_columns_not_for_detectors": TRUTH_COLS,
        "scenarios": SCENARIO_INFO, "runs": runs,
        "suggested_split": {
            "train": [f"normal_seed{s}" for s in normal_seeds[:2]],
            "validation": [f"normal_seed{s}" for s in normal_seeds[2:3]],
            "test": [f"normal_seed{s}" for s in normal_seeds[3:]] + [r["name"] for r in runs if r["scenario"] != "normal"],
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate labelled ARMOUR LABS simulator datasets")
    ap.add_argument("--out", default="../data/generated")
    args = ap.parse_args()
    m = write_dataset(args.out)
    print(f"Wrote {len(m['runs'])} runs to {args.out}")
