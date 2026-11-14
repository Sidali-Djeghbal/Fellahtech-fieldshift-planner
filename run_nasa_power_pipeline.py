#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main entry point for the NASA POWER Guelma spatial audit, processing,
QA validation, climate analysis, and documentation pipeline.
"""

from nasa_power_pipeline.analysis import run_climate_analysis
from nasa_power_pipeline.audit import run_spatial_audit
from nasa_power_pipeline.config import PROCESSED_DIR, ensure_output_dirs
from nasa_power_pipeline.documentation import run_documentation
from nasa_power_pipeline.processing import run_processing
from nasa_power_pipeline.qa import run_quality_assurance


def main() -> None:
    """Execute Phases 1 through 7 in order."""
    print("=" * 72)
    print("FIELD SHIFT — NASA POWER REGIONAL PROCESSING PIPELINE (GUELMA)")
    print("=" * 72)

    ensure_output_dirs()

    print("\n[Phase 2] Running spatial audit, GeoPackage export, and maps...")
    intersections_by_comm, audit_summary = run_spatial_audit()
    guelma_area_km2 = audit_summary["boundary"]["utm_area_km2"]
    print(f"  Boundary area (EPSG:32632): {guelma_area_km2:.4f} km2")
    for comm, info in audit_summary["grids"]["communities"].items():
        print(
            f"  {comm}: {info['intersecting_cells']}/{info['cell_count']} intersecting cells | "
            f"coverage={info['coverage_pct']:.4f}% | max_overlap={info['max_pairwise_overlap_m2']:.2e} m2"
        )

    print("\n[Phases 3-4] Generating daily, monthly, seasonal, and annual datasets...")
    datasets = run_processing(intersections_by_comm, guelma_area_km2)
    print(f"  daily_cell_values: {len(datasets['daily_cell']):,} rows")
    print(f"  daily_guelma:      {len(datasets['daily_guelma']):,} rows")
    print(f"  monthly_guelma:    {len(datasets['monthly']):,} rows")
    print(f"  seasonal_guelma:   {len(datasets['seasonal']):,} rows")
    print(f"  annual_guelma:     {len(datasets['annual']):,} rows")

    print("\n[Phase 5] Running comprehensive data quality & consistency checks...")
    qa_results = run_quality_assurance(datasets, audit_summary)
    print(qa_results["data_quality"][["check_id", "observed_value", "status"]].to_string(index=False))

    print("\n[Phase 6] Running exploratory climate analysis & generating figures...")
    analysis_results = run_climate_analysis(datasets)
    print(f"  climate_trends:    {len(analysis_results['trends'])} indicators")
    print(f"  climate_anomalies: {len(analysis_results['anomalies'])} annual rows")

    print("\n[Phase 7] Saving processing metadata, data dictionary, and README...")
    run_documentation(audit_summary, datasets, qa_results, analysis_results)

    print("\n" + "=" * 72)
    print(f"PIPELINE COMPLETED SUCCESSFULLY -> {PROCESSED_DIR}")
    print("=" * 72)


if __name__ == "__main__":
    main()
