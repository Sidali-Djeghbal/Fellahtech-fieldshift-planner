"""Reproducible CLI Runner for Field Shift Phase D: Cross-Dataset Integration & Validation."""

from fieldshift_integration.canonical_layers import build_canonical_layers
from fieldshift_integration.docs_builder import build_all_documentation
from fieldshift_integration.feature_engineering import build_feature_tables
from fieldshift_integration.source_inventory import build_source_inventory
from fieldshift_integration.spatial_harmonization import run_spatial_harmonization
from fieldshift_integration.validation_suite import run_validation_suite


def main() -> None:
    print("[Phase D] 1/6 Inspecting actual workspace datasets...")
    inv_df = build_source_inventory()
    print(f"  -> Inventoried {len(inv_df)} datasets")

    print("[Phase D] 2/6 Building 6 canonical data layers...")
    canon_counts = build_canonical_layers()
    print(f"  -> Canonical layers built: {canon_counts}")

    print("[Phase D] 3/6 Running multi-resolution spatial harmonization & CropFreq 10m grid alignment...")
    spatial_info = run_spatial_harmonization()
    print(f"  -> Spatial harmonization done: {spatial_info}")

    print("[Phase D] 4/6 Generating leakage-controlled feature tables...")
    feat_counts = build_feature_tables()
    print(f"  -> Feature tables built: {feat_counts}")

    print("[Phase D] 5/6 Running automated validation suite...")
    val_df = run_validation_suite()
    print(
        f"  -> Validation results: PASS={(val_df['status']=='PASS').sum()}, "
        f"CHECK={(val_df['status']=='CHECK').sum()}, FAIL={(val_df['status']=='FAIL').sum()}"
    )

    print("[Phase D] 6/6 Writing data dictionary, specs, Phase D report & project README...")
    build_all_documentation(inv_df, canon_counts, spatial_info, feat_counts, val_df)
    print("[Phase D] ALL STAGES COMPLETED CLEANLY.")


if __name__ == "__main__":
    main()
