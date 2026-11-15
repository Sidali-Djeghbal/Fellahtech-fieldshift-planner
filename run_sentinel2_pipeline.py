#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main entry point for the Field Shift Sentinel-2 Guelma (2017-2025) pipeline.

Modes:
  local-prep   Run Phase 1 (local boundary & existing datasets audit) + Phase 13 (integration readiness)
  gee-run      Run Phase 2-9 via authenticated Python Earth Engine API (saves raw summary CSVs)
  gee-batch    Submit GEE GeoTIFF batch exports to Google Drive
  postprocess  Run local QA, charts, maps, metadata & docs on files in data/SENTINEL2/raw/gee_exports/
  all          Run all phases end-to-end
"""

import argparse
import json

from sentinel2_pipeline.config import RAW_METADATA_DIR, SENTINEL2_DIR, ensure_directories
from sentinel2_pipeline.phase1_local_audit import audit_existing_datasets, audit_local_boundary
from sentinel2_pipeline.phase2_gee_client import (
    download_gee_rasters_local,
    inspect_gee_collection_metadata,
    run_gee_summary_exports,
    submit_gee_batch_raster_exports,
)
from sentinel2_pipeline.phase3_postprocess_qa import run_postprocess_and_qa
from sentinel2_pipeline.phase4_visualize_analyze import run_visualization_and_analysis
from sentinel2_pipeline.phase5_docs_integration import write_metadata_and_docs


def main() -> None:
    parser = argparse.ArgumentParser(description="Field Shift Sentinel-2 Guelma Pipeline")
    parser.add_argument(
        "--mode",
        choices=["local-prep", "gee-run", "gee-rasters", "gee-batch", "postprocess", "all"],
        default="all",
        help="Execution mode",
    )
    args = parser.parse_args()

    ensure_directories()

    print("=" * 72)
    print("FIELD SHIFT — SENTINEL-2 PIPELINE (GUELMA 2017-2025)")
    print("=" * 72)

    print("\n[Phase 1] Auditing local boundary and existing datasets...")
    boundary_audit = audit_local_boundary()
    dataset_inventory = audit_existing_datasets()
    print(f"  Local boundary: {boundary_audit['boundary_file']} ({boundary_audit['utm_area_km2']} km2)")
    print(f"  Existing datasets audited: {len(dataset_inventory)}")

    if args.mode == "local-prep":
        write_metadata_and_docs(boundary_audit, dataset_inventory)
        print(f"\nLocal audit & integration-readiness report written -> {SENTINEL2_DIR}")
        return

    gee_meta = None
    if args.mode in ("gee-run", "all"):
        print("\n[Phases 2-8] Inspecting GEE Sentinel-2 collection & exporting summary tables...")
        gee_meta = inspect_gee_collection_metadata()
        m_csv, s_csv, a_csv = run_gee_summary_exports()
        print(f"  Exported: {m_csv}, {s_csv}, {a_csv}")

    if args.mode in ("gee-rasters", "all"):
        print("\n[Phase 8b] Downloading Sentinel-2 composite GeoTIFFs locally at native 10m/20m...")
        rasters = download_gee_rasters_local()
        print(f"  Verified local GeoTIFFs: {len(rasters)}")

    if args.mode == "gee-batch":
        print("\n[Phase 9] Submitting GEE GeoTIFF batch exports to Google Drive...")
        tasks = submit_gee_batch_raster_exports()
        for t in tasks:
            print("  Task started:", t)
        return

    if args.mode in ("postprocess", "all"):
        print("\n[Phases 8-12] Running QA checks, charts, maps, and documentation...")
        if gee_meta is None and (RAW_METADATA_DIR / "gee_collection_metadata.json").exists():
            with open(RAW_METADATA_DIR / "gee_collection_metadata.json", "r", encoding="utf-8") as f:
                gee_meta = json.load(f)
        qa_outputs = run_postprocess_and_qa(boundary_audit, gee_meta=gee_meta)
        analysis_outputs = run_visualization_and_analysis(qa_outputs)
        write_metadata_and_docs(
            boundary_audit=boundary_audit,
            dataset_inventory=dataset_inventory,
            gee_meta=gee_meta,
            qa_outputs=qa_outputs,
            analysis_outputs=analysis_outputs,
        )
        print(qa_outputs["qa"][["check_id", "observed_value", "status"]].to_string(index=False))
        print(f"\nCompleted successfully -> {SENTINEL2_DIR}")


if __name__ == "__main__":
    main()
