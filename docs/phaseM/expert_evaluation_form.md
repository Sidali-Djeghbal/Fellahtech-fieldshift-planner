# Phase M — Standardized Expert Evaluation Form (Section B)

> **Validated Contract:** [`ExpertReviewRecord`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/pilot/models.py#L99) in `src/pilot/models.py`  
> **Mandatory Safety Rule:** Farmer briefing is **BLOCKED** (`approved_for_farmer_briefing` cannot be `true`) whenever `review_outcome` is `REJECTED` or `REQUIRES_ADDITIONAL_INFO`, or when `agronomic_safety_pass = false`.

---

## Part 1 — Identification & Institutional Traceability
- **Review ID:** `____________________` | **Pilot Field Code:** `____________________`
- **Field Shift `analysis_id`:** `ANAL____________________` *(links verbatim to persisted Phase L input, Field Profile & JSON output)*
- **Reviewer Code (`expert_id`):** `____________________` | **Date (`UTC`):** `____________________`
- **Institution (`select one`):** `[ ] DSA_GUELMA` `[ ] ITGC` `[ ] ONID` `[ ] INRA` `[ ] CHAMBER_OF_AGRICULTURE` `[ ] UNIVERSITY_AGRONOMY` `[ ] OTHER_EXTENSION`

---

## Part 2 — Independent Agronomic & Field Profile Inspection
*Review BEFORE sharing output with farmer (`GET /api/v1/analyses/{analysis_id}`).*

1. **Field Profile Plausibility (`Section B` Geospatial Snapshot):**
   - Do polygon commune (`overlap %`), area (`ha`), SoilGrids `250 m` texture/SOC/pH (`MODELED_SPATIAL_ESTIMATE`), and macro rainfall (`GPM` vs `NASA POWER`) match your knowledge of this site?
   - Are missing local elements (`DEM` unavailable, SoilGrids `null` mask, unmeasured `ECe`/`CaCO3`/`Olsen-P`) accurately noted?
2. **Sequence Compatibility Verdict (`select one`):**
   - `[ ] ACCEPTABLE` — All break intervals, season windows, and pest guards (`SEQ_01`–`SEQ_10`) fit site conditions.
   - `[ ] ACCEPTABLE_WITH_CAVEATS` — Sequence valid only if documented local conditions (e.g. `ECe` test, surface drain) are checked.
   - `[ ] UNACCEPTABLE` — Agronomic incompatibility or biological hazard (e.g., *Orobanche* / waterlogging / sowing mismatch).
   - `[ ] UNCERTAIN` — Insufficient local evidence to verify sequence fit.
3. **Agronomic Assessment Narrative (`required`):**  
   `____________________________________________________________________________________`
4. **Local Constraints Observed by Expert That System Could Not See (`optional array; null = not assessed, [] = none`):**  
   *(e.g., perched winter waterlogging hollow, heavy `Orobanche crenata` seedbank, fractured tenancy contract, stony shallow horizon)*  
   `____________________________________________________________________________________`

---

## Part 3 — Recommendation Disposition & Mandatory Disagreement Investigation

5. **Formal Disposition (`select one`):**
   - `[ ] ACCEPTED` — Top strategy and caveats are suitable for supervised farmer briefing as generated.
   - `[ ] ACCEPTED_WITH_MODIFICATIONS` — Core recommendation useful, but crop choice/order/practice must be modified.
   - `[ ] REJECTED` — Top recommendation is unsuitable or unsafe for this farm context.
   - `[ ] REQUIRES_ADDITIONAL_INFO` — Cannot judge responsibly until missing lab soil/water data, tenancy, or field inspection arrives.
6. **Decision Rationale (`required even on ACCEPTED`, min 10 chars):**  
   `____________________________________________________________________________________`
7. **Recommended Modifications (`MANDATORY if ACCEPTED_WITH_MODIFICATIONS`):**  
   `____________________________________________________________________________________`
8. **Root-Cause Investigation Code When Modified or Rejected (`NEVER skip`):**  
   *Note: Expert disagreement does NOT automatically mean an engine bug—record exact evidence context:*
   - `[ ] LOCAL_DISEASE_PRESSURE_UNOBSERVED` (e.g., farm-specific *Orobanche* / root-rot unknown to satellite/history)
   - `[ ] MISSING_DEM_DRAINAGE_CONTEXT` (model flagged `UNKNOWN`, expert knows depression floods / hillside erodes)
   - `[ ] MISSING_SALINITY_ECE_ECW` (local well/Seybouse salinity too high for recommended crop)
   - `[ ] MICROCLIMATE_OR_RAINFALL_BIAS` (macro `11–69 km` rain/frost diverges from local valley conditions)
   - `[ ] SOCIOECONOMIC_MARKET_LABOR_BARRIER` (missing regional contract, seed shortage, or harvest labor gap)
   - `[ ] KNOWLEDGE_BASE_RULE_REFINEMENT_NEEDED` (verified gap in `crop_profiles.json` or Phase G/H rule thresholds)
   - `[ ] INPUT_MISUNDERSTANDING_OR_BOUNDARY_ERROR` (polygon misplaced or water access misclassified during intake)
   - `[ ] NOT_APPLICABLE` *(ONLY when outcome is `ACCEPTED`)*

---

## Part 4 — Quality Scores & Mandatory Farmer Briefing Gate

9. **Constraint Detection Rating (`1 = Missed Critical Blocker` .. `5 = Caught All Key Constraints`):** `[ 1 ] [ 2 ] [ 3 ] [ 4 ] [ 5 ]`
10. **Explanation & Trade-Off Quality (`1 = Unclear/Misleading` .. `5 = Clear & Actionable`):** `[ 1 ] [ 2 ] [ 3 ] [ 4 ] [ 5 ]`
11. **Were Uncertainty, Missing Data & Non-Yield Scope Communicated Clearly?** `[ ] YES` `[ ] NO`
12. **Agronomic Safety Pass (`0` unsafe sequence/salinity/waterlogging recommendations)?** `[ ] PASS (true)` `[ ] FAIL (false)`
13. **Authorization Gate:** **Approve Recommendation for Supervised Farmer Briefing?** `[ ] APPROVED (true)` `[ ] BLOCKED (false)`
    - *System Validator Enforcement (`ExpertReviewRecord`): Setting `APPROVED = true` while outcome is `REJECTED` / `REQUIRES_ADDITIONAL_INFO` or `Safety = FAIL` raises `PilotSafetyViolationError`.*
