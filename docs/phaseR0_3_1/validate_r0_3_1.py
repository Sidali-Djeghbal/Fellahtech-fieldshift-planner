#!/usr/bin/env python3
"""Automated invariant validator for Phase R0.3.1 Scientific Evidence Quality Audit."""

from __future__ import annotations

import csv
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R03_DIR = ROOT / "docs" / "phaseR0_3"
R031_DIR = ROOT / "docs" / "phaseR0_3_1"

ALLOWED_VERIFICATION_STATUS = {
    "VERIFIED_PRIMARY_SOURCE",
    "VERIFIED_INSTITUTIONAL_SOURCE",
    "VERIFIED_SECONDARY_SOURCE",
    "PARTIALLY_VERIFIED",
    "UNVERIFIED",
    "INVALID_OR_MISMATCHED",
}

VERIFIED_FOR_IMPLEMENTATION = {
    "VERIFIED_PRIMARY_SOURCE",
    "VERIFIED_INSTITUTIONAL_SOURCE",
}

ALLOWED_EVIDENCE_TIERS = {
    "LOCAL_VALIDATED",
    "ALGERIAN_REGIONAL",
    "MEDITERRANEAN_REGIONAL",
    "INTERNATIONAL_REFERENCE",
    "GENERAL_ESTIMATE",
    "NOT_AVAILABLE",
}

ALLOWED_READINESS = {
    "IMPLEMENTATION_READY",
    "REFERENCE_ONLY",
    "LOCAL_CALIBRATION_REQUIRED",
    "CONFLICTED",
    "NOT_AVAILABLE",
}

ALLOWED_CONFIDENCE = {"HIGH", "MEDIUM", "LOW", "NONE"}

ALLOWED_RECOMMENDATIONS = {
    "APPROVE_FOR_DESIGN",
    "REQUIRES_MORE_EVIDENCE",
    "BLOCKED_BY_LOCAL_DATA",
    "REJECT_OR_REFORMULATE",
}

EXPECTED_SOURCE_COLS = [
    "source_id",
    "original_reference",
    "source_type",
    "verification_status",
    "DOI_or_URL",
    "DOI_resolution_status",
    "title_match",
    "author_year_match",
    "geography_match",
    "claim_support_status",
    "exact_page_table_section",
    "identified_problems",
    "confidence",
    "reviewer_notes",
]

EXPECTED_AUDIT_COLS = [
    "corrected_evidence_tier",
    "implementation_readiness",
    "source_verification_status",
    "measurement_basis",
    "confidence_after_audit",
    "audit_decision",
    "audit_reason",
]

EXPECTED_CANDIDATE_IDS = (
    [f"CAND-0{i}" for i in range(1, 9)]
    + [f"TIER_B_0{i}" for i in range(1, 7)]
    + [f"TIER_C_0{i}" for i in range(1, 5)]
)

EXPECTED_CROPS = {
    "DURUM_WHEAT",
    "SOFT_WHEAT",
    "BARLEY",
    "FABA_BEAN",
    "CHICKPEA_WINTER",
    "CHICKPEA_SPRING",
    "LENTIL",
    "VETCH_OAT",
    "TOMATO_IND",
    "POTATO",
    "SUNFLOWER",
    "OLIVE",
    "BARE_FALLOW",
}

BASELINE_R03_SHA256 = {
    "R0_3_AGRONOMIC_EVIDENCE_MATRIX.csv": ("2a163a84d057a84ffeb34229758880cd5a2bad47c548608f3d006adac83d8878", 148895),
    "R0_3_CROP_REQUIREMENTS_REPORT.md": ("d4f32df27881486e766f9bc27b2fef571b9070a0816ff477acf64eb5335e7770", 30462),
    "R0_3_DATA_TO_REQUIREMENTS_MAPPING.csv": ("ea8cec165aaf817a6aad9f51f7b6e9ed1278c08cec63c78ed67f7ebc77604388", 14446),
    "R0_3_EXECUTIVE_SUMMARY.md": ("478cf19d05eb2fd4378b1499131e009d8aa2bf3ec6c3d1ed5ea3844d2e072e71", 8594),
    "R0_3_LOCAL_VALIDATION_GAPS.md": ("dd91981915a15ef1cbd9446f5fecc50539dd99913f23a31e3bdecf7d178217b6", 11358),
    "R0_3_RULE_CALIBRATION_CANDIDATES.md": ("eccac009fa051340ae12b7b3777a3d1af71bb827f6338060c018e86b8760416e", 14318),
    "R0_3_SOURCE_REGISTER.md": ("4bc1cd1aefcbf35609ed548458bf56725e312817bb210630d27b3723b8934c48", 22554),
}

REQUIRED_DELIVERABLES = [
    "R0_3_1_SOURCE_VERIFICATION.csv",
    "R0_3_1_CORRECTED_EVIDENCE_MATRIX.csv",
    "R0_3_1_ECW_ECE_AUDIT.md",
    "R0_3_1_HIGH_IMPACT_PARAMETERS_AUDIT.md",
    "R0_3_1_DATASET_PROXY_AUDIT.md",
    "R0_3_1_CALIBRATION_CANDIDATES_REVIEW.csv",
    "R0_3_1_REMAINING_EVIDENCE_GAPS.md",
    "R0_3_1_EXECUTIVE_SUMMARY.md",
    "R0_3_1_AUDIT_LOG.md",
    "validate_r0_3_1.py",
]


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def main() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        status = "PASS" if cond else "FAIL"
        print(f"[{status}] {name}" + (f" :: {detail}" if detail else ""))
        if not cond:
            failures.append(f"{name}: {detail}")

    # Load core datasets
    orig_cols, orig_rows = load_csv(R03_DIR / "R0_3_AGRONOMIC_EVIDENCE_MATRIX.csv")
    corr_cols, corr_rows = load_csv(R031_DIR / "R0_3_1_CORRECTED_EVIDENCE_MATRIX.csv")
    src_cols, src_rows = load_csv(R031_DIR / "R0_3_1_SOURCE_VERIFICATION.csv")
    cand_cols, cand_rows = load_csv(R031_DIR / "R0_3_1_CALIBRATION_CANDIDATES_REVIEW.csv")

    # Check 1: Non-destructive matrix preservation (416 rows, zero lost/duplicated, verbatim original columns)
    expected_corr_cols = ["record_id", *orig_cols, *EXPECTED_AUDIT_COLS]
    c1_cols_ok = corr_cols == expected_corr_cols
    c1_count_ok = len(orig_rows) == 416 and len(corr_rows) == 416
    c1_ids = [r["record_id"] for r in corr_rows]
    c1_unique_ids = len(c1_ids) == len(set(c1_ids)) == 416
    c1_verbatim_ok = c1_count_ok and all(
        corr_rows[i]["record_id"] == f"{orig_rows[i]['crop_id']}::{orig_rows[i]['parameter_id']}"
        and all(corr_rows[i][c] == orig_rows[i][c] for c in orig_cols)
        for i in range(416)
    )
    check(
        "Check 1 - Non-destructive matrix preservation",
        c1_cols_ok and c1_count_ok and c1_unique_ids and c1_verbatim_ok,
        f"rows={len(corr_rows)}, cols={len(corr_cols)}/{len(expected_corr_cols)}, verbatim={c1_verbatim_ok}",
    )

    # Check 2: Source register completeness & verification_status enum
    src_map = {r["source_id"]: r for r in src_rows}
    expected_sids = {f"SRC-{i:02d}" for i in range(1, 35)}
    c2_ok = (
        src_cols == EXPECTED_SOURCE_COLS
        and len(src_rows) == 34
        and set(src_map.keys()) == expected_sids
        and all(r["verification_status"] in ALLOWED_VERIFICATION_STATUS for r in src_rows)
        and all(all(r[col].strip() != "" for col in EXPECTED_SOURCE_COLS) for r in src_rows)
    )
    check("Check 2 - Source verification register completeness & enums", c2_ok, f"sources={len(src_rows)}")

    # Check 3: Cross-reference integrity + enum enforcement on corrected matrix
    bad_refs: list[str] = []
    bad_enums: list[str] = []
    for r in corr_rows:
        if r["corrected_evidence_tier"] not in ALLOWED_EVIDENCE_TIERS:
            bad_enums.append(f"{r['record_id']}:tier={r['corrected_evidence_tier']}")
        if r["implementation_readiness"] not in ALLOWED_READINESS:
            bad_enums.append(f"{r['record_id']}:read={r['implementation_readiness']}")
        if r["confidence_after_audit"] not in ALLOWED_CONFIDENCE:
            bad_enums.append(f"{r['record_id']}:conf={r['confidence_after_audit']}")
        for sid in [s.strip() for s in r["source_ids"].split(";") if s.strip() and s.strip() != "NONE"]:
            if sid not in src_map:
                bad_refs.append(f"{r['record_id']}:{sid}")
    check(
        "Check 3 - Matrix enums & source cross-references",
        not bad_refs and not bad_enums,
        f"bad_refs={len(bad_refs)}, bad_enums={len(bad_enums)}",
    )

    # Check 4: Absent/N-A guardrails
    na_violations = []
    for r in corr_rows:
        is_na_val = r["value_min"].strip() in ("NOT_AVAILABLE", "NOT_APPLICABLE", "", "NONE") and r["value_max"].strip() in ("NOT_AVAILABLE", "NOT_APPLICABLE", "", "NONE")
        if is_na_val and (
            r["implementation_readiness"] != "NOT_AVAILABLE"
            or r["corrected_evidence_tier"] != "NOT_AVAILABLE"
            or r["confidence_after_audit"] != "NONE"
        ):
            na_violations.append(r["record_id"])
    check("Check 4 - Absent/N-A cannot be IMPLEMENTATION_READY or non-NONE", not na_violations, f"violations={na_violations}")

    # Check 5: Strict IMPLEMENTATION_READY audit eligibility
    ready_rows = [r for r in corr_rows if r["implementation_readiness"] == "IMPLEMENTATION_READY"]
    ready_violations: list[str] = []
    for r in ready_rows:
        sids = [s.strip() for s in r["source_ids"].split(";") if s.strip() and s.strip() != "NONE"]
        if not sids:
            ready_violations.append(f"{r['record_id']}:no_sources")
            continue
        if not all(src_map[s]["verification_status"] in VERIFIED_FOR_IMPLEMENTATION for s in sids):
            ready_violations.append(f"{r['record_id']}:unverified_or_partial_source({sids})")
        if r["value_min"].strip() != r["value_max"].strip():
            ready_violations.append(f"{r['record_id']}:non_scalar_range({r['value_min']}..{r['value_max']})")
        if r["parameter_id"] in ("nutrient_uptake_npk_kg_t", "fertilizer_rec_algeria_kg_ha", "forage_nutritive_value", "algerian_costs_prices_context", "soil_salinity_ece_threshold_dsm", "soil_salinity_slope_pct"):
            ready_violations.append(f"{r['record_id']}:blocked_parameter_type")
        mb = r["measurement_basis"]
        if any(mb.startswith(p) for p in ("MIXED_", "INVALID_", "UNVERIFIED_", "CONFLICTING_")):
            ready_violations.append(f"{r['record_id']}:ambiguous_basis({mb})")
    check(
        "Check 5 - Strict IMPLEMENTATION_READY gate",
        len(ready_rows) > 0 and not ready_violations,
        f"ready_count={len(ready_rows)}, violations={ready_violations}",
    )

    # Check 6: ECw != ECe & Tomato/Potato/Olive salinity protections + ECw/ECe report coverage
    tomato_sal = [r for r in corr_rows if r["crop_id"] == "TOMATO_IND" and "salinity" in r["parameter_id"]]
    potato_sal = [r for r in corr_rows if r["crop_id"] == "POTATO" and "salinity" in r["parameter_id"]]
    olive_sal = [r for r in corr_rows if r["crop_id"] == "OLIVE" and "salinity" in r["parameter_id"]]
    ec_md = (R031_DIR / "R0_3_1_ECW_ECE_AUDIT.md").read_text(encoding="utf-8")
    c6_matrix_ok = (
        len(tomato_sal) == 2
        and all(r["implementation_readiness"] == "CONFLICTED" and r["corrected_evidence_tier"] != "LOCAL_VALIDATED" for r in tomato_sal)
        and all(r["implementation_readiness"] == "CONFLICTED" for r in potato_sal + olive_sal)
    )
    c6_md_ok = all(crop in ec_md for crop in EXPECTED_CROPS) and all(
        tag in ec_md for tag in ("ECe_THRESHOLD_VERIFIED", "BASIS_UNCLEAR", "CONFLICTING_EVIDENCE", "NOT_AVAILABLE")
    )
    check("Check 6 - ECw != ECe guardrail & ECw/ECe audit coverage", c6_matrix_ok and c6_md_ok)

    # Check 7: LOCAL_VALIDATED strict guardrail (exact 0 local crop-parameter trials)
    local_val_rows = [r["record_id"] for r in corr_rows if r["corrected_evidence_tier"] == "LOCAL_VALIDATED"]
    tomato_orig3 = {
        r["parameter_id"]: r
        for r in corr_rows
        if r["record_id"] in (
            "TOMATO_IND::soil_salinity_ece_threshold_dsm",
            "TOMATO_IND::key_soilborne_pathogens_weeds",
            "TOMATO_IND::operational_machinery_seeding",
        )
    }
    c7_ok = (
        len(local_val_rows) == 0
        and len(tomato_orig3) == 3
        and all(r["implementation_readiness"] != "IMPLEMENTATION_READY" for r in tomato_orig3.values())
    )
    check("Check 7 - Zero unsupported LOCAL_VALIDATED rows remain", c7_ok, f"local_validated={local_val_rows}")

    # Check 8: 13-crop matrix completeness, all deliverables present & 25 domains covered
    crops_in_matrix = {r["crop_id"] for r in corr_rows}
    deliverables_ok = all((R031_DIR / f).is_file() and (R031_DIR / f).stat().st_size > 200 for f in REQUIRED_DELIVERABLES)
    proxy_md = (R031_DIR / "R0_3_1_DATASET_PROXY_AUDIT.md").read_text(encoding="utf-8")
    c8_domains_ok = all(k in proxy_md for k in ("NASA POWER", "GPM IMERG", "SMAP", "SoilGrids", "Sentinel-2", "MODIS", "WS2M", "DEM", "nitrogen_0_30cm"))
    check("Check 8 - 13-crop completeness, 25 domains & all 10 files present", crops_in_matrix == EXPECTED_CROPS and deliverables_ok and c8_domains_ok)

    # Check 9: 18-candidate review + explicit 18-vs-19 matrix discrepancy check
    cand_map = {r["candidate_id"]: r for r in cand_rows}
    hi_md = (R031_DIR / "R0_3_1_HIGH_IMPACT_PARAMETERS_AUDIT.md").read_text(encoding="utf-8")
    exec_md = (R031_DIR / "R0_3_1_EXECUTIVE_SUMMARY.md").read_text(encoding="utf-8")
    sunflower_etc = next(r for r in corr_rows if r["record_id"] == "SUNFLOWER::fao33_seasonal_etc_mm")
    c9_ok = (
        [r["candidate_id"] for r in cand_rows] == EXPECTED_CANDIDATE_IDS
        and all(r["final_recommendation"] in ALLOWED_RECOMMENDATIONS for r in cand_rows)
        and cand_map["CAND-05"]["final_recommendation"] == "REJECT_OR_REFORMULATE"
        and cand_map["CAND-04"]["final_recommendation"] == "REJECT_OR_REFORMULATE"
        and cand_map["CAND-07"]["final_recommendation"] == "REJECT_OR_REFORMULATE"
        and cand_map["TIER_B_05"]["final_recommendation"] == "REJECT_OR_REFORMULATE"
        and sunflower_etc["implementation_readiness"] == "REFERENCE_ONLY"
        and "600" in hi_md and "19" in exec_md and "L341" in hi_md
    )
    check(
        "Check 9 - 18-candidate governance & 18-vs-19 matrix discrepancy",
        c9_ok,
        f"candidates={len(cand_rows)}, CAND-05={cand_map['CAND-05']['final_recommendation']}",
    )

    # Check 10: Immutability of Phase R0.3 files & repo read-only boundary
    hash_ok = True
    for fname, (exp_hash, exp_size) in BASELINE_R03_SHA256.items():
        p = R03_DIR / fname
        data = p.read_bytes()
        h = hashlib.sha256(data).hexdigest()
        if h != exp_hash or len(data) != exp_size:
            hash_ok = False
    git_res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    outside_changes = [
        line for line in git_res.stdout.splitlines() if line.strip() and "docs/phaseR0_3_1" not in line
    ]
    check(
        "Check 10 - Read-only baseline immutability (R0.3 SHA-256 & git boundary)",
        hash_ok and not outside_changes,
        f"r03_hashes_ok={hash_ok}, outside_git_changes={outside_changes}",
    )

    print(f"\nSUMMARY: {10 - len(failures)}/10 checks PASSED, {len(failures)} FAILED")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
