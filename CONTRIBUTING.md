# Contributing to ARMOUR LABS

## Ownership
Stay inside your own folders. Ask before editing someone else's.

| Area | Folders | Owner |
|---|---|---|
| Frontend | `frontend/` | P1 |
| Simulation, attacks, twin | `backend/sim/`, `backend/twin/`, `data/` | P2 |
| Detection, incidents, API, storage | `backend/detect/`, `backend/incident/`, `backend/api/`, `backend/db/` | P3 |
| Contracts | `backend/core/contracts.py`, `frontend/src/types.ts`, `docs/contracts.md` | all (everyone must agree) |

## Workflow
```bash
git clone https://github.com/S-tevens/ARMOUR-LABS.git
cd ARMOUR-LABS
git checkout -b <role>/<topic>        # e.g. p2/twin-fit
# work, run the checks below, then:
git add <your files>
git commit -m "Short description"
git push -u origin <role>/<topic>     # then open a pull request
```
- Never push straight to `main`. Open a pull request and wait for the CI checks to pass.
- Run `git pull origin main` before you start work each day.
- Keep pull requests small and focused.
- Do not commit secrets, `.env` files, virtual environments, `node_modules` or databases.

## Checks before opening a PR
```bash
cd backend && python -m pytest        # backend tests
cd frontend && npm run build          # type-check + build
```

## Project rules
- Everything stays inside the simulation. Never connect to real equipment or networks.
- An anomaly is evidence, not proof of an attack.
- Never hard-code metrics. Every reported number must be computed. Label illustrative values.
- Show "Recovered" only when the verification checks pass.
- Use fixed random seeds so runs are repeatable.
- Placeholders in the base project are marked `PLACEHOLDER` or `TODO`. Replace them in your area.
