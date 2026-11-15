# Phase M — Operational Pilot Execution Checklist (`PLANNED`)

> **Important Epistemic Label:** **ALL STEPS BELOW ARE PLANNED PRE-PILOT AND FIELD ACTIVITIES.** Zero farmer sessions, expert field reviews, soil lab samples, or harvest weigh-ins have been conducted as of `2026-11-15`.

---

## Stage 1 — Institutional & Technical Preparation (`PLANNED — Must Finish Before Day 1`)
- [ ] **1.1** Formalize pilot coordination with **DSA Guelma**, **ITGC**, **ONID**, and **Chamber of Agriculture** (designate 1 lead coordinator + >= 2 accredited agronomists per institution).
- [ ] **1.2** Assign bilingual (`Arabic` / `French`) enumerators to translate English Phase J rule reasons live during supervised farmer sessions.
- [ ] **1.3** Secure deployment machine: run [`src/api/app.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/api/app.py) locally or on secure VPN (`GET /api/v1/health` verified `status = "ok"`, `sqlite_local` backup cron enabled, `GEE` disabled).
- [ ] **1.4** Pre-test offline GeoJSON map canvas (`GET /api/v1/reference/guelma-boundary`) on pilot tablets with zero cellular connectivity.
- [ ] **1.5** Print backup offline copies of [`expert_evaluation_form.md`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseM/expert_evaluation_form.md) and informed farmer consent notice (explicit advisory-only disclaimer).

## Stage 2 — Field Selection & Stratified Intake (`PLANNED — N = 36 Target Fields`)
- [ ] **2.1** Recruit `12` parcels each across `NORTHERN_HUMID`, `CENTRAL_VALLEY`, and `SOUTHERN_SEMI_ARID` communes per [`field_sampling_strategy.md`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseM/field_sampling_strategy.md) (`22` rainfed, `14` irrigated).
- [ ] **2.2** Conduct Section A intake with farmer: draw single GeoJSON `Polygon`, enter ONLY farmer-known water access, crop history (`null` vs `[]` carefully distinguished), and preferences; log `FarmerPilotObservation` + `PilotExecutionSession` timing/usability telemetry.
- [ ] **2.3** Run `POST /api/v1/fields/validate` and confirm mapped `area_ha` and commune name with farmer before running `/analyze`.
- [ ] **2.4** Save immutable `analysis_id` (`GET /api/v1/analyses/{analysis_id}`). **Hold output internally**—do not issue unreviewed planting advice on the spot if agronomist sign-off is pending.

## Stage 3 — Independent Agronomic Review (`PLANNED — Mandatory Safety Gate`)
- [ ] **3.1** Present each saved `analysis_id` (`Field Profile + Candidate Strategies + Uncertainty`) to an accredited `ITGC` / `DSA` / `ONID` reviewer.
- [ ] **3.2** Record [`ExpertReviewRecord`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/pilot/models.py#L99): disposition (`ACCEPTED`, `ACCEPTED_WITH_MODIFICATIONS`, `REJECTED`, `REQUIRES_ADDITIONAL_INFO`), rationale, investigation code, ratings, and `approved_for_farmer_briefing`.
- [ ] **3.3** Double-review a random subset (`>= 20%`, `>= 8` fields) across two independent experts to measure inter-expert concordance.

## Stage 4 — Supervised Farmer Briefing & Optional Lab / Harvest Follow-Up (`PLANNED`)
- [ ] **4.1** Conduct farmer briefing **only** for `approved_for_farmer_briefing = true` records (and present expert-modified sequence where `ACCEPTED_WITH_MODIFICATIONS`).
- [ ] **4.2** Collect Section C physical samples where lab budget allows (`ECe`, `pH`, texture, `SOM`, `CaCO3`, `Olsen-P`, irrigation `ECw`, single-season yield `t/ha`) under [`MeasuredFieldObservation`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/pilot/models.py#L168)—keep all unsampled variables strictly `null` (`NOT_MEASURED`).

## Stage 5 — Post-Pilot Audit & Go/No-Go Decision (`PLANNED`)
- [ ] **5.1** Compute separated metrics via [`compute_pilot_metrics`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/pilot/models.py#L277) covering usability, polygon reliability, expert agreement, constraint safety, latency, and SoilGrids-vs-lab error (only where real lab cores exist).
- [ ] **5.2** Investigate every `MODIFIED`/`REJECTED` root cause (`disagreement_investigation_code`) before adjusting any Phase G/H/I rule or scheduling Phase N (`DEM` integration, `ECe` gating, native `fr`/`ar` localization, PostGIS rollout).
