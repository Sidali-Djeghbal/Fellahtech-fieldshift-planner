import { describe, expect, it } from "vitest";
import {
  computeEdgeMidpoints,
  computePerimeterMeters,
  computePolygonAreaHectares,
  computePolygonCentroid,
  findNearestGuelmaCommune,
  GUELMA_COMMUNES,
  GUELMA_FALLBACK_BOUNDARY,
  GUELMA_PARCEL_PRESETS,
  isInsideGuelmaBoundary,
  ringSegmentsSelfIntersect,
  ringToGeoJsonPolygon,
  SETIF_OUTSIDE_TEST_COORD,
  stripClosingPoint,
} from "@/lib/geo/guelma";
import { INITIAL_PRESETS, STRATS } from "@/lib/prototype/data";
import { evaluate, fieldToPreset } from "@/lib/prototype/engine";
import { deriveSoilSource } from "@/store/useGuelmaWorkspace";
import type { FarmPublic, FieldDetailPublic } from "@/lib/schemas";

describe("Wilaya of Guelma geography & CAD boundary helpers", () => {
  it("contains all 34 communes of Wilaya 24 inside the Guelma boundary", () => {
    expect(GUELMA_COMMUNES).toHaveLength(34);
    for (const commune of GUELMA_COMMUNES) {
      const [lon, lat] = commune.center;
      expect(
        isInsideGuelmaBoundary(lat, lon, GUELMA_FALLBACK_BOUNDARY),
        `Commune ${commune.name.en} (${lat}, ${lon}) should be inside Guelma`
      ).toBe(true);
    }
  });

  it("rejects out-of-province coordinates such as Setif", () => {
    expect(
      isInsideGuelmaBoundary(
        SETIF_OUTSIDE_TEST_COORD.latitude,
        SETIF_OUTSIDE_TEST_COORD.longitude,
        GUELMA_FALLBACK_BOUNDARY
      )
    ).toBe(false);
  });

  it("computes positive geodesic area, perimeter, midpoints, and centroid for all Guelma presets", () => {
    for (const preset of GUELMA_PARCEL_PRESETS) {
      const pts = stripClosingPoint(preset.ring);
      expect(pts.length).toBeGreaterThanOrEqual(3);

      const ha = computePolygonAreaHectares(pts);
      expect(ha).toBeGreaterThan(0.5);
      expect(ha).toBeLessThan(200);

      const perim = computePerimeterMeters(pts, true);
      expect(perim).toBeGreaterThan(100);

      const midpoints = computeEdgeMidpoints(pts, true);
      expect(midpoints).toHaveLength(pts.length);

      const centroid = computePolygonCentroid(pts);
      expect(centroid).not.toBeNull();
      expect(
        isInsideGuelmaBoundary(
          centroid!.latitude,
          centroid!.longitude,
          GUELMA_FALLBACK_BOUNDARY,
          pts
        )
      ).toBe(true);

      const matched = findNearestGuelmaCommune(
        centroid!.latitude,
        centroid!.longitude
      );
      expect(matched.name.en.length).toBeGreaterThan(0);

      const geojson = ringToGeoJsonPolygon(pts);
      expect(geojson).toMatchObject({ type: "Polygon" });
    }
  });

  it("detects bowtie self-intersecting rings and allows valid non-crossing rings", () => {
    const validSquare: [number, number][] = [
      [7.46, 36.47],
      [7.465, 36.47],
      [7.465, 36.475],
      [7.46, 36.475],
    ];
    expect(ringSegmentsSelfIntersect(validSquare)).toBe(false);

    const bowtie: [number, number][] = [
      [7.46, 36.47],
      [7.465, 36.475],
      [7.465, 36.47],
      [7.46, 36.475],
    ];
    expect(ringSegmentsSelfIntersect(bowtie)).toBe(true);
  });
});

describe("Farmer workspace domain conversions & ADR-5 soil derivation", () => {
  it("derives soil.source strictly as 'unknown' unless farmer supplies soil measurements", () => {
    expect(
      deriveSoilSource({
        soil_type: "unknown",
        soil_ph: "",
        organic_matter_percent: "",
        soil_test_date: "",
      })
    ).toBe("unknown");

    expect(
      deriveSoilSource({
        soil_type: "clay",
        soil_ph: "",
        organic_matter_percent: "",
        soil_test_date: "",
      })
    ).toBe("farmer");

    expect(
      deriveSoilSource({
        soil_type: "unknown",
        soil_ph: "7.2",
        organic_matter_percent: "",
        soil_test_date: "",
      })
    ).toBe("farmer");
  });

  it("converts a saved Guelma Farm + FieldDetailPublic into a simulatable Preset and evaluates rotations", () => {
    const farm: FarmPublic = {
      farm_id: "farm_1",
      farm_name: "Ferme Bouchegouf Test",
      country: "Algeria",
      region: "Guelma",
      commune: "Bouchegouf",
      field_count: 1,
      created_at: "2026-11-15T00:00:00Z",
    };

    const field: FieldDetailPublic = {
      farm_id: "farm_1",
      field_id: "F-1",
      field_name: "Parcelle Est",
      is_unverified_demo_parcel: false,
      location: {
        latitude: 36.4615,
        longitude: 7.728,
        boundary: {
          type: "Polygon",
          coordinates: [
            [
              [7.727, 36.463],
              [7.7295, 36.463],
              [7.7295, 36.4602],
              [7.727, 36.4602],
              [7.727, 36.463],
            ],
          ],
        },
      },
      area_hectares: 6.8,
      elevation_m: null,
      soil: {
        soil_type: "clay",
        source: "farmer",
        soil_ph: 7.4,
        organic_matter_percent: 1.5,
        soil_test_date: "2026-10-12",
      },
      water: {
        availability: "moderate",
        source: "dam_reservoir",
        source_other: null,
        irrigation_system: "sprinkler",
      },
      warnings: [],
      crop_history: [
        {
          season: "autumn",
          year: 2024,
          planting_month: 11,
          crop_id: "durum_wheat",
          crop_name_raw: null,
          yield_tons_per_hectare: 3.1,
          notes: null,
        },
      ],
    };

    const preset = fieldToPreset(farm, field);
    expect(preset.id).toBe("farm_1::F-1");
    expect(preset.climate).toBe("bouchegouf_basin");
    expect(preset.soilType).toBe("clay");
    expect(preset.areaHa).toBe(6.8);

    const res = evaluate(
      STRATS[1],
      { rain: 0, temp: 0, irrigated: false, lowInput: false },
      "balanced",
      preset
    );
    expect(res.total).toBeGreaterThan(0);
    expect(res.total).toBeLessThanOrEqual(100);
    expect(INITIAL_PRESETS).toHaveLength(5);
  });
});
