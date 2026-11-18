# ARMOUR LABS: City Layer Plan (Bengaluru-inspired)

A second layer above the substation we already have. The city shows *where* and *how bad*; clicking a district drops into the substation view we built. It answers "so what?" for judges: not "a breaker opened" but "12 % of the city is dark and 3 hospitals are on backup".

> **Fictional by design.** The city is Bengaluru-*inspired*: district names and facility types are real-sounding, but the network, loads and substations are invented. We never claim real BESCOM / KPTCL topology or real vulnerabilities. Say so in the UI (a small "Simulated, Bengaluru-inspired" label) and in the README.

---

## 1. The frontend must stay clean and easy to read

These are hard requirements, not suggestions. Every frontend task is reviewed against them.

**The 5-second test.** A person seeing the city view for the first time must be able to answer, in five seconds:
1. Is the city OK? (one status pill, same as now)
2. Where is the problem? (the affected district is visibly different)
3. How bad is it? (people without power, critical sites at risk)

**Rules**
- **One screen, one question.** The city view answers *where and how bad*. Detail lives one click deeper (progressive disclosure): `City > District > Substation`, with a breadcrumb.
- **Few colours, fixed meaning.** Reuse the existing tokens only: green healthy, amber needs attention, red incident, blue power flow. Never colour alone: status also has an icon or label.
- **Plain units first.** People, hospitals, minutes. Megawatts and hertz are secondary, shown on click.
- **At most about 8 labels visible at once.** District names only. Everything else on hover or in the side panel. Importance is shown by size and opacity, not by more text.
- **Ranked "what's happening" list**, sorted by impact, one plain sentence each ("Koramangala: hospital feeder lost power, command was not from SCADA").
- **Same visual language as today:** frosted glass panels, Manrope, thin meters, small badges, restrained animation. Reuse `Meter`, `Spark`, the callout and pill styles. No new chart libraries, no new design system.
- **Animation only where it carries information:** power flow direction and speed, a pulsing incident marker. Respect reduced motion.
- **Keyboard and screen-reader friendly:** every district is focusable with a text label for its status.
- **Performance:** the city SVG stays under about 250 elements; only flow lines animate.

---

## 2. What the city layer is

```text
CITY (new)        8 districts, lines between substations, city frequency, impact counters
  |  click a district
  v
SUBSTATION (built)  the isometric microgrid view, twin, detectors, containment
```

- **Districts:** 8 tiles. Proposed (fictional network): Whitefield (tech park), Electronic City (tech park), Hebbal (airport corridor), Yelahanka, Indiranagar, Koramangala (hospital campus), Jayanagar, City Centre (metro hub).
- **Facilities per district, with a priority:** hospitals (P1), water pumping and metro (P2), tech parks and traffic signals (P3), residential (P4).
- **Each district substation is an instance of the existing `Plant`**, with different parameters (load, solar, battery), not a new model. Eight cheap instances at 1 Hz is trivial.
- **City physics (simple on purpose):** substations are nodes joined by lines with a capacity. A linear (DC) power flow gives flows. Total generation minus load gives a city-wide frequency. A line above its limit for N seconds trips, and flows are recomputed (cascade).
- **City attacks:** coordinated breaker trips across districts, a simultaneous load-altering attack (compromised chargers and smart devices), a communications loss.
- **Look-alikes again:** planned maintenance outage (authorised), a hot-evening demand peak (natural), a transformer or line fault (equipment). All must not be flagged as attacks.
- **City containment:** restore by priority (hospitals, then water and metro, then the rest), staged re-energisation, with a dry-run that predicts line loadings before the operator approves.

---

## 3. Contracts to agree first (1 hour, all three people)

New folder `docs/` file: `docs/city-contracts.md`, mirrored in `backend/core/city_contracts.py` and `frontend/src/city/types.ts`. Existing substation contracts do not change except where noted.

```text
CityState (WebSocket /ws/city, 1 Hz)
  t, frequency, status (normal | attention | incident)
  districts[]: id, name, x, y            # map position, fixed
               status, served_pct, people_unserved
               facilities[]: id, type, priority, status (ok | backup | down), backup_minutes_left
  lines[]:     id, from, to, flow_mw, capacity_mw, loading (0..1.2), status (in_service | tripped)
  impact:      people_unserved, hospitals_on_backup, hospitals_down, critical_sites_down,
               energy_not_served_mwh, restoration_pct

Incident (existing) gains:  district: string | null, campaign_id: string | null
REST:   GET /city                      static layout + current CityState
        GET /city/scenarios            city scenarios (same shape as /scenarios)
        POST /city/scenario/start|stop {name, districts?}
        POST /city/incident/{id}/approve-response
        GET /city/recovery             city recovery report
WS:     /ws/telemetry?district=<id>    existing substation stream for one district (default: the featured district)
```

Day-0 deliverables: the contract doc, a sample `CityState` JSON (P2), and a mock server serving it (P1). P1 never waits for the backend.

---

## 4. Tasks by person

Sizes: **S** under half a day, **M** about a day, **L** two days or more. Builds are ordered; each ends with a demo checkpoint.

### P2: city model, scenarios, twin and recovery (`backend/city/`, `backend/sim/`, `backend/twin/`)

| # | Task | Size | Build |
|---|---|---|---|
| P2.1 | City config file `backend/city/data/bengaluru.json`: 8 districts (name, map x/y, population, base load, solar, battery, facilities with priorities) and the lines (capacity, reactance). Fictional. | S | C1 |
| P2.2 | Linear power-flow solver (numpy) with a slack bus, plus tests (conservation, a known 3-node solution, a tripped-line recompute) | M | C1 |
| P2.3 | Parameterise `Plant` (load, PV, battery sizes) so each district is an instance. Keep the existing 30 tests green. | M | C1 |
| P2.4 | `CityEngine`: steps all districts, feeds each district's utility import into the city flow, applies line trips back to district breakers (a lost feeder opens `cb_main`), city frequency from total imbalance, seeded and deterministic | L | C1 |
| P2.5 | Line overload protection with a delay, and cascade recompute | M | C2 |
| P2.6 | Facility model: hospitals run on backup for N minutes then go down; impact metrics (people unserved, energy not served, restoration %) | M | C2 |
| P2.7 | City scenarios: `coordinated_substation_trip`, `load_altering_attack`, `comms_loss` (attacks); `planned_maintenance`, `evening_peak` (benign); `line_fault` (fault). Each with ground-truth labels. | L | C2 |
| P2.8 | City containment: priority restoration order, staged re-energisation, authorised commands logged | M | C2 |
| P2.9 | City twin: expected flows from the authorised topology and commands only (same independence rule as the substation twin, with a leak test) | L | C3 |
| P2.10 | Dry-run of a restoration plan (predicted line loadings, flag any overload before approval) and city recovery verification with a dwell time | L | C3 |
| P2.11 | City dataset generator (labelled runs, run-based split) | S | C3 |

### P3: city runtime, API, detection and correlation (`backend/api/`, `backend/detect/`, `backend/incident/`, `backend/db/`)

| # | Task | Size | Build |
|---|---|---|---|
| P3.1 | `CityRuntime`: one engine, twin and detector per district plus the city engine; tick loop; store tagging by district | L | C1 |
| P3.2 | Endpoints and sockets from the contract: `/city`, `/ws/city`, `/ws/telemetry?district=`, city scenario and approve endpoints; tests with fake clients | M | C1 |
| P3.3 | Incidents carry `district` and `campaign_id`; existing substation incidents keep working per district | S | C1 |
| P3.4 | City-level signals: system frequency, power balance across the city, simultaneous unauthorised commands in several districts | M | C2 |
| P3.5 | Campaign correlation: group district incidents that share a source, command pattern and time window into one campaign incident with a kill-chain timeline | L | C3 |
| P3.6 | City evaluation: detection delay, correct district set, false alarms on the benign city scenarios; `GET /metrics?scope=city` | M | C3 |
| P3.7 | Plain-language incident sentences for the ranked list, built only from real fields (test: every number in the text exists in the data) | M | C3 |
| P3.8 | Continue Tier 1 substation work in parallel when blocked: Isolation Forest, physics checks, fusion (see the build plan) | L | all |

### P1: city view and navigation (`frontend/src/city/`, `frontend/src/App.tsx`)

| # | Task | Size | Build |
|---|---|---|---|
| P1.1 | Mock server serving sample `CityState`, and the `useCityStream` hook (same pattern as `useStream`) | S | C1 |
| P1.2 | Isometric city map: 8 district tiles in the existing SVG projection, lines between them, district status colour plus icon, under 250 elements | L | C1 |
| P1.3 | Navigation and breadcrumb `City > District > Substation`; the existing substation view opens for the chosen district; the tab bar gains "City" | M | C1 |
| P1.4 | Headline impact strip: people without power, critical sites at risk, energy not supplied, city frequency (same style as the sensor strip, with badges) | S | C2 |
| P1.5 | Facility icons on tiles (hospital, metro, water, tech park) with ok / backup / down state and a backup countdown | M | C2 |
| P1.6 | Line animation by flow direction and speed; thickness by loading; amber and red when overloaded or tripped | M | C2 |
| P1.7 | Ranked "What's happening" panel (plain sentence per incident, sorted by impact) and the district detail card with an "Open substation" button | M | C2 |
| P1.8 | City simulator card (grouped dropdown, same pattern as the substation simulator), approve-containment banner | S | C2 |
| P1.9 | Campaign timeline (kill chain) and the dry-run preview showing predicted line loadings before approving | L | C3 |
| P1.10 | City replay scrubber (reuses the replay endpoint pattern) and the city recovery panel | M | C3 |
| P1.11 | Guided demo mode and the 5-second test pass (see section 6) | M | C4 |

---

## 5. Builds and demo checkpoints

| Build | Goal | Demo checkpoint |
|---|---|---|
| **C0** (1 hour) | Contracts, sample JSON, mock server | Everyone builds against the same shapes |
| **C1** | City model, runtime and the map | A live city map with flowing lines; click a district to open its substation |
| **C2** | Impact, city scenarios, containment | Trigger the coordinated trip: districts darken, hospitals go on backup, the impact counters climb, the ranked list explains it |
| **C3** | City twin, correlation, dry-run, replay | The campaign is detected as one incident; the dry-run previews the restoration; recovery is verified at city level |
| **C4** | Polish and guided demo | A rehearsed 3-minute demo and a recorded fallback video |

Each build ends with a joint 30-minute integration run on one machine before it is merged to `main`.

---

## 6. Acceptance checks

**Backend**
- The same seed gives the same city run.
- Power flow conserves energy and matches the known test case; a tripped line is recomputed.
- The existing 30 substation tests still pass.
- The city twin's expectations do not change when observed topology changes (leak test).
- `planned_maintenance`, `evening_peak` and `line_fault` raise no attack classification.
- "Restored" or "Recovered" appears only after the verification checks pass and the dwell time elapses.

**Frontend (the clarity bar)**
- **5-second test:** three people who have never seen it each answer the three questions (city OK? where? how bad?) correctly within 5 seconds during an active incident.
- Never more than about 8 labels visible on the city map at once.
- Every status is readable without colour (icon or text).
- No raw hertz or megawatts in the headline strip; plain units first.
- Works at laptop width and a 1000 px tablet width; keyboard focus visible; reduced motion respected.

---

## 7. Risks and cut order

| Risk | Mitigation |
|---|---|
| The city turns into a pretty map with a placeholder brain | Do the substation detection (Tier 1) in parallel; city detection reuses it per district |
| Physics rabbit hole | Linear power flow only, 8 nodes; no AC model |
| Frontend clutter | The clarity rules above are acceptance criteria; remove before adding |
| Integration slip | Contracts and mock server on day 0; P1 builds against the mock |
| Claims about real infrastructure | Fictional data, labelled as such |

**Cut order if time runs short:** replay scrubber, then the communications-loss scenario, then the campaign timeline, then the dry-run, then the load-altering attack. Never cut: the map, the coordinated trip, the impact strip, the ranked list, containment and verified recovery.

## 8. Out of scope for this layer
Real map tiles or real network data, a full AC power-flow model, thermal and voltage-stability modelling, real-time protocol traffic, and multi-user accounts.
