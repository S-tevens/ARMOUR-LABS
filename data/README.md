# Data

Generated datasets live in `data/generated/` and are **not committed** (they are reproducible). Create them with:

```bash
cd backend
python -m sim.dataset --out ../data/generated
```

This writes one CSV (one row per second) and one `.events.jsonl` per run, plus `manifest.json`.
The source is the **custom simulator**, not a public dataset: label every result that uses it as such.

- Runs: 4 normal seeds, and every scenario with 2 seeds. Each run is normal for 120 s, the scenario is active until 300 s, then the plant is hard reset until 420 s.
- Labels: `scenario`, `kind` (normal, attack, fault, benign), `active`, `is_attack`, `is_anomaly`. A legitimate operator change is `benign`: it is **not** an anomaly.
- `true_*` columns are ground truth for evaluation only. Detectors must not use them as inputs.
- Split by run, never by random rows (see `suggested_split` in the manifest), so adjacent time windows do not leak between train and test.
- Add a public dataset (BATADAL or HAI) alongside this for model credibility, and keep results labelled by source.

## City grid data

The Bengaluru grid lives in `backend/city/data/bengaluru_osm.json` and is built from OpenStreetMap (see the README, "Data sources and licence"). It is committed; the raw downloads (`backend/city/tools/raw/`) are not. Map data (c) OpenStreetMap contributors, ODbL.
