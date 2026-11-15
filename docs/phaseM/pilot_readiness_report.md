# Phase M — Supervised Field Pilot Readiness Report

> **Executive Verdict:** **`CONDITIONAL — READY FOR SUPERVISED ADVISOR-LED FIELD PILOT IN GUELMA`** *(Strictly Blocked for Autonomous / Unsupervised Farmer Deployment)*  
> **Completed vs. Planned Separation:** Software integration (`71/71` tests passing) and Phase M pilot data/validation contracts (`src/pilot/`) are **COMPLETE**; actual farmer recruitment, expert review scoring, and soil/yield measurements remain **100% PLANNED (Zero Field Execution Yet)**.

---

## 1. Technical & Scientific Audit Foundation

- **Verified Technical Readiness (`COMPLETE`):**
  - Phases D–J scientific models, Phase K `17`-scenario backtest/stress audit (`CONDITIONAL` scientific verdict; `NOT_VALIDATABLE` empirical yield benchmark), and Phase L FastAPI application (`src/api/app.py`, `SQLiteAnalysisRepository`, `frontend/index.html`, `db/schema_postgis.sql`) pass `71/71` automated tests cleanly.
  - All Phase L contracts strictly forbid technical farmer inputs, distinguish `null` (`NOT_PROVIDED`) from `[]` (`EXPLICITLY_CONFIRMED_EMPTY`), validate Draft 2020-12 output on every response, and never force an ineligible winner (`NO_ELIGIBLE_STRATEGY`).
- **Pilot Governance Layer Built in Phase M (`COMPLETE`):**
  - Python contracts & anti-fabrication validators in [`src/pilot/models.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/pilot/models.py) enforce Section A (`FarmerPilotObservation`), Section B (`ExpertReviewRecord` briefing safety gate), Section C (`MeasuredFieldObservation` explicit `NOT_MEASURED` / texture sum / no-zero-coercion), stratified `36`-field quota validation (`validate_sampling_plan`), and strictly separated evaluation metrics (`compute_pilot_metrics`).
  - Complete ground-truth dictionary ([`ground_truth_data_dictionary.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseM/ground_truth_data_dictionary.csv)), sampling plan, standardized expert rubric, metrics specification, risk register, and execution checklist.

---

## 2. Pilot Readiness Matrix

| Readiness Dimension | Status | Evidence Basis |
|---|---|---|
| **Backend API, UI & Local SQLite Persistence** | **READY (Supervised Pilot)** | `/api/v1/health`, `/validate`, `/analyze`, `/analyses/{id}`, offline Wilaya map UI, `7/7` Phase L integration tests passing |
| **Pilot Data Collection & Safety Validators** | **READY** | `src/pilot/models.py` enforces non-fabrication (`NOT_MEASURED`), farmer/expert/lab separation, and briefing gate (`tests/test_phaseM_pilot.py`) |
| **Institutional Participation & MoUs (`DSA/ITGC/ONID`)** | **PENDING (Planned)** | No participating farms, advisors, or ethics/data-sharing sign-offs recorded yet |
| **Bilingual Farmer Delivery (`fr` / `ar` Explanations)** | **GAP / WORKAROUND READY** | Engine prose is English; supervised pilot requires bilingual enumerator/advisor mediation |
| **Production Multi-User Persistence (`PostGIS` + Auth)** | **DISCONNECTED** | Local pilot uses password-protected advisor workstation (`SQLite`); host `postgis` + `psycopg` + OAuth2 remain unprovisioned |
| **Empirical Predictive Yield Validation (`t/ha`)** | **`NOT_VALIDATABLE` (Blocked)** | Zero labeled yield plots on disk; `compute_pilot_metrics` blocks yield accuracy claims until `>= 15` paired harvest measurements exist |

---

## 3. Exact Prerequisites Remaining Before Pilot Kickoff Day 1

1. Obtain formal collaboration approval and designate reviewers from **DSA Guelma**, **ITGC**, **ONID**, and the **Chamber of Agriculture**.
2. Appoint bilingual (`Arabic` / `French`) enumerators trained on `null` vs `[]` history entry, map polygon verification, and verbal non-yield/non-profit disclosures.
3. Configure workstation/server security (`SQLite` daily encrypted backup, local LAN access control—never exposed raw on public internet without auth).
4. Execute Stage 2 stratified intake (`N = 36` parcels across Northern Humid, Central Valley, and Southern Semi-Arid communes), enforce Stage 3 mandatory expert sign-off on 100% of analyses prior to farmer briefing, and log Section C lab cores (`ECe`, `pH`, texture, `SOM`, `CaCO3`, `Olsen-P`) wherever laboratory partners participate.
