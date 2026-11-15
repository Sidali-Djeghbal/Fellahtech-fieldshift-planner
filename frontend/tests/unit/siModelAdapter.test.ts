import { describe, expect, it, vi } from "vitest";
import { ApiClientError } from "@/lib/api/errors";
import {
  buildSiAnalyzeRequestPayload,
  buildSiFieldValidationPayload,
  createSiModelBridge,
  fieldLocationToSiPolygon,
  frontendCropIdToSi,
  siCropIdToFrontend,
  translateSiAnalyzeResponseToFieldPlan,
} from "@/lib/api/siModelAdapter";
import {
  AnalysisEnvelopeSchema,
  AnalysisResultSchema,
  type AnalysisSubmitRequest,
  type FieldDetailPublic,
} from "@/lib/schemas";

function makeMemoryStorage(): Storage {
  const map = new Map<string, string>();
  return {
    get length() {
      return map.size;
    },
    clear: () => map.clear(),
    getItem: (key) => map.get(key) ?? null,
    key: (idx) => Array.from(map.keys())[idx] ?? null,
    removeItem: (key) => {
      map.delete(key);
    },
    setItem: (key, value) => {
      map.set(key, value);
    },
  };
}

const SAMPLE_FIELD_BOUMAHRA: FieldDetailPublic = {
  farm_id: "farm_1",
  field_id: "F1",
  field_name: "Boumahra Seybouse Parcel",
  is_unverified_demo_parcel: false,
  location: {
    latitude: 36.472,
    longitude: 7.483,
    boundary: {
      type: "Polygon",
      coordinates: [
        [
          [7.48, 36.47],
          [7.486, 36.47],
          [7.486, 36.474],
          [7.48, 36.474],
          [7.48, 36.47],
        ],
      ],
    },
  },
  area_hectares: 23.85,
  elevation_m: 140,
  soil: {
    soil_type: "clay",
    source: "farmer",
    soil_ph: 7.2,
    organic_matter_percent: 2.1,
    soil_test_date: "2025-10-12",
  },
  water: {
    availability: "moderate",
    source: "rainwater",
    source_other: null,
    irrigation_system: "rainfed",
  },
  warnings: [],
  crop_history: [
    {
      season: "autumn",
      year: 2025,
      planting_month: 11,
      crop_id: "durum_wheat",
      crop_name_raw: null,
      yield_tons_per_hectare: 3.1,
      notes: "Seybouse baseline",
    },
  ],
};

const REALISTIC_SI_ANALYZE_RESPONSE = {
  analysis_id: "ANAL_a1b2c3d4e5f6",
  created_at_utc: "2026-11-15T21:45:00Z",
  payload_sha256: "deadbeef1234567890abcdef1234567890abcdef1234567890abcdef12345678",
  reused_existing: false,
  persistence_backend: "sqlite_local",
  field_profile_summary: {
    field_id: "F1",
    field_name: "Boumahra Seybouse Parcel",
    spatial_validation: {
      area_ha: 23.85,
      primary_commune: { name_2: "Boumahra Ahmed" },
    },
    extracted_summary: {
      usda_texture_0_5cm: "Clay loam",
      clay_0_30cm_pct: {
        value: 32.253,
        unit: "%",
        source_dataset: "SoilGrids 2.0 V6 (250m)",
        spatial_resolution: "250 m",
        temporal_coverage: "static baseline",
        polygon_coverage_pct: 100.0,
      },
      ph_0_30cm: {
        value: 7.1958,
        unit: "pH",
        source_dataset: "SoilGrids 2.0 V6 (250m)",
        spatial_resolution: "250 m",
      },
      soc_0_30cm_g_kg: {
        value: 12.7296,
        unit: "g/kg",
        source_dataset: "SoilGrids 2.0 V6 (250m)",
        spatial_resolution: "250 m",
      },
      gpm_annual_precip_mm: {
        value: 587.56,
        unit: "mm/year",
        source_dataset: "GPM IMERG V07",
        spatial_resolution: "11 km",
        temporal_coverage: "2016-2025",
      },
      nasa_power_annual_precip_mm: {
        value: 562.1,
        unit: "mm/year",
        source_dataset: "POWER",
        spatial_resolution: "55 km",
        temporal_coverage: "2016-2025",
      },
      nasa_power_t2m_mean_c: {
        value: 18.4,
        unit: "degC",
        source_dataset: "POWER",
        spatial_resolution: "55 km",
        temporal_coverage: "2016-2025",
      },
      smap_rootzone_sm_spring: {
        value: 0.241,
        unit: "m3/m3",
        source_dataset: "SMAP L4",
        spatial_resolution: "11 km",
        temporal_coverage: "2016-2025 Spring",
      },
      modis_ndvi_spring_mean: {
        value: 0.5702,
        unit: "unitless NDVI",
        source_dataset: "MODIS MOD13Q1",
        spatial_resolution: "250 m",
        temporal_coverage: "2016-2025 Spring",
      },
    },
  },
  recommendation: {
    schema_version: "phaseJ-1.0",
    request_id: "ANAL_a1b2c3d4e5f6",
    dataset_version_used: "Guelma_Phases_AD_SoilGridsV6_250m_GPM_SMAP_11km_POWER_2016_2025",
    generated_at: "2026-11-15T21:45:00Z",
    status: "PARTIAL",
    language: "en",
    decision_engine_version: "FieldShift-PhaseFJ-1.1.0",
    overall_summary: "4 ranked crop-rotation strategies generated for Boumahra Ahmed.",
    disclaimer: "Verify drainage and ECe locally prior to spring planting.",
    field_plans: [
      {
        field_id: "F1",
        field_name: "Boumahra Seybouse Parcel",
        status: "PARTIAL",
        partial_reason: null,
        decision_gate: {
          decision_status: "PROVISIONAL_EXPLORATORY",
          gating_reasons: ["Local DEM slope and ECe salinity unverified."],
        },
        land_use_assessment: {
          status: "ARABLE_CANDIDATE",
          soilgrids_clay_coverage_pct: 100.0,
          soilgrids_valid_pixels: 7,
        },
        field_insights: {
          bare_field_periods: [
            {
              period: "Summer (Jun-Aug)",
              indicator: "modis_ndvi_summer_mean",
              observed_value: 0.231,
              interpretation: "Low summer vegetation cover between cereal harvests",
            },
          ],
          stress_periods: [
            {
              constraint_id: "WATER_PRECIP_SEASONAL",
              status: "CAUTION",
              finding: "587.6 mm/yr rainfall requires drought-resilient summer break.",
              agronomic_implication: "Favor early-maturing winter cereals and spring legumes.",
            },
            {
              constraint_id: "SOIL_SOC_LOW",
              status: "CAUTION",
              finding: "Topsoil SOC 12.73 g/kg benefits from legume residue incorporation.",
              agronomic_implication: "Include Faba Bean or Chickpea every 2-3 seasons.",
            },
          ],
          climate_trend_summary: {
            temporal_window: "2016-2025",
            gpm_annual_precip_mean_mm: 587.56,
            nasa_power_annual_precip_mean_mm: 562.1,
            nasa_power_mean_temp_c: 18.4,
            smap_spring_rootzone_sm_mean: 0.241,
            smap_summer_rootzone_sm_mean: 0.145,
            scale_and_trend_caveat: "Coarse 11km/55km macro climate envelope.",
          },
        },
        suggested_strategy_id: "STRAT_WATER_CONSCIOUS",
        strategies: [
          {
            strategy_id: "STRAT_WATER_CONSCIOUS",
            name: "Water-Conscious Legume & Durum Sequence",
            is_existing_rotation: false,
            description: "Balances spring chickpea and durum wheat for Boumahra alluvial soils.",
            rank: 1,
            pareto_status: "PARETO_OPTIMAL",
            weighted_score: 0.812,
            confidence: { level: "MEDIUM_CONDITIONAL" },
            seasons: [
              {
                order: 1,
                season: "Spring",
                year: 2027,
                planting_month: 3,
                crop_id: "CHICKPEA_SPRING",
                crop_name: "Spring Chickpea",
                category: "legumes",
                role: "nitrogen_fixer",
                notes: "Low water footprint pulse",
              },
              {
                order: 2,
                season: "Autumn",
                year: 2027,
                planting_month: 11,
                crop_id: "DURUM_WHEAT",
                crop_name: "Durum Wheat",
                category: "cereals",
                role: "main_crop",
                notes: "Captures winter-spring rainfall",
              },
            ],
            scores: {
              water_efficiency: { score: 0.84, status: "SCORED" },
              erosion_protection: { score: 0.72, status: "SCORED" },
              soil_improvement: { score: 0.78, status: "SCORED" },
              nitrogen_contribution: { score: 0.81, status: "SCORED" },
              pest_disease_disruption: { score: 0.85, status: "SCORED" },
              forage_value: { score: 0.42, status: "SCORED" },
              income_potential: { score: null, status: "UNKNOWN_MISSING_BUDGETS" },
            },
            explanation: {
              summary: "Top Pareto strategy prioritizing rainfall efficiency and disease break.",
              reasons: [
                "[PASS] CEREAL_BREAK: Alternates Fabaceae before Durum Wheat.",
              ],
              evidence: [
                {
                  data_source: "SoilGrids 250m",
                  parameter: "soc_0_30cm",
                  observed_value: 12.73,
                  unit: "g/kg",
                  period: "static baseline",
                  derived: true,
                  interpretation: "Moderate organic carbon in Seybouse topsoil",
                },
                {
                  data_source: "Farmer Input",
                  parameter: "elevation_dem",
                  observed_value: null,
                  unit: null,
                  period: "static",
                  derived: false,
                  interpretation: "Micro-slope requires on-site verification",
                  quality_status: "MISSING_DEM",
                },
              ],
              benefits: ["Reduces cereal root-rot carryover across autumn sowings."],
              risks: ["[WARNING] SPRING_DRY_SPELL: March rainfall variability reduces pod set."],
              assumptions: ["Rainfed seeding at 110 kg/ha chickpea rate."],
              information_gaps: ["Field-scale ECe salinity measurement missing."],
              needs_local_review: true,
              review_checklist: ["Check surface drainage before November wheat sowing."],
            },
          },
          {
            strategy_id: "STRAT_CEREAL_FORAGE",
            name: "Cereal & Vetch-Oat Conservation",
            is_existing_rotation: false,
            description: "High soil cover and forage biomass.",
            rank: 2,
            pareto_status: "PARETO_OPTIMAL",
            weighted_score: 0.76,
            confidence: "LOW",
            seasons: [
              {
                order: 1,
                season: "Spring",
                year: 2027,
                planting_month: 3,
                crop_id: "VETCH_OAT",
                crop_name: "Vetch-Oat",
                category: "forage",
                role: "forage",
              },
              {
                order: 2,
                season: "Autumn",
                year: 2027,
                planting_month: 11,
                crop_id: "BARLEY",
                crop_name: "Barley",
                category: "cereals",
                role: "main_crop",
              },
            ],
            scores: {
              water_efficiency: { score: 0.77 },
              erosion_protection: { score: 0.86 },
              soil_improvement: { score: 0.8 },
              nitrogen_contribution: { score: 0.71 },
              pest_disease_disruption: { score: 0.75 },
              forage_value: { score: 0.9 },
            },
            explanation: {
              reasons: [],
              evidence: [],
              benefits: [],
              risks: [],
              assumptions: [],
              information_gaps: [],
              needs_local_review: false,
            },
          },
          {
            strategy_id: "STRAT_CEREAL_LEGUME",
            name: "Durum & Faba Bean Sequence",
            is_existing_rotation: false,
            description: "Balanced cereal-legume succession.",
            rank: 3,
            weighted_score: 0.73,
            confidence: "MEDIUM",
            seasons: [
              {
                order: 1,
                season: "Spring",
                year: 2027,
                planting_month: 3,
                crop_id: "CHICKPEA_SPRING",
                crop_name: "Spring Chickpea",
              },
            ],
            scores: {
              water_efficiency: { score: 0.72 },
              erosion_protection: { score: 0.69 },
              soil_improvement: { score: 0.74 },
              nitrogen_contribution: { score: 0.79 },
              pest_disease_disruption: { score: 0.76 },
            },
            explanation: {
              reasons: [],
              evidence: [],
              benefits: [],
              risks: [],
              assumptions: [],
              information_gaps: [],
              needs_local_review: [],
            },
          },
        ],
        requested_crop_results: [
          {
            crop_id: "CHICKPEA_SPRING",
            crop_name: "Spring Chickpea",
            outcome: "included",
            reason: "Compatible with Spring 2027 rainfed envelope on Clay loam.",
            included_in_strategy_ids: ["STRAT_WATER_CONSCIOUS", "STRAT_CEREAL_LEGUME"],
          },
        ],
        data_quality: {
          completeness_score: 0.78,
          critical_data_adequacy: {
            adequacy_status: "ADEQUATE_EXPLORATORY",
            adequacy_vs_completeness_explanation: "250m SoilGrids and 11km climate loaded.",
          },
          missing_data: ["DEM_10M_SLOPE"],
          warnings: [],
          limitations: ["Regional 11km GPM smoothing."],
        },
      },
    ],
  },
};

describe("Feild-Shift-SI-Model Integration Bridge & Adapter", () => {
  it("maps crop IDs bidirectionally including season-aware chickpea and generates closed GeoJSON polygons", () => {
    expect(frontendCropIdToSi("chickpea", "spring")).toBe("CHICKPEA_SPRING");
    expect(frontendCropIdToSi("chickpea", "autumn")).toBe("CHICKPEA_WINTER");
    expect(frontendCropIdToSi("vetch", "autumn")).toBe("VETCH_OAT");
    expect(frontendCropIdToSi("tomato", "spring")).toBe("TOMATO_IND");
    expect(siCropIdToFrontend("CHICKPEA_SPRING")).toBe("chickpea_spring");
    expect(siCropIdToFrontend("BARE_FALLOW")).toBe("fallow");

    const syntheticPoly = fieldLocationToSiPolygon(
      { latitude: 36.135, longitude: 7.125, boundary: null },
      10
    );
    expect(syntheticPoly.type).toBe("Polygon");
    expect(syntheticPoly.coordinates[0]).toHaveLength(5);
    expect(syntheticPoly.coordinates[0][0]).toEqual(syntheticPoly.coordinates[0][4]);
  });

  it("enforces strict FieldAnalyzeRequest contract with zero forbidden keys, rainfed mapping, and income=100 tie-breaker", () => {
    const valPayload = buildSiFieldValidationPayload(SAMPLE_FIELD_BOUMAHRA, {
      startSeason: "spring",
      startYear: 2027,
      horizonSeasons: 6,
      plantingMonth: 11, // mismatched with spring -> sanitized to null
    });

    const fieldObj = valPayload.field as Record<string, unknown>;
    expect(fieldObj.soil).toBeUndefined();
    expect(fieldObj.elevation_m).toBeUndefined();
    expect(fieldObj.ndvi).toBeUndefined();
    expect((valPayload.water as Record<string, unknown>).source).toBe("rainfed");
    expect((valPayload.water as Record<string, unknown>).irrigation_system).toBe("none");
    expect((valPayload.planning as Record<string, unknown>).horizon_seasons).toBe(4);
    expect((valPayload.planning as Record<string, unknown>).planting_month).toBeNull();
    const hist0 = (valPayload.crop_history as Array<Record<string, unknown>>)[0];
    expect(hist0.crop_name_raw).toBe("Durum Wheat");

    const submitReq: AnalysisSubmitRequest = {
      language: "en",
      farm_id: "farm_1",
      field_ids: ["F1"],
      planning: {
        start_season: "spring",
        start_year: 2027,
        horizon_seasons: 6,
        cycle_mode: "annual_rotation",
        planting_month: null,
        scenario_overrides: { temp_delta_c: 0, precip_pct_delta: 0 },
      },
      priorities: {
        weights: {
          water_saving: 0,
          soil_improvement: 0,
          income: 100,
          risk_reduction: 0,
          forage_value: 0,
        },
        market_preference: "local_market",
        target_crop_ids: ["chickpea"],
        excluded_crop_ids: ["barley"],
        equipment_constraints: [],
      },
    };

    const built = buildSiAnalyzeRequestPayload(SAMPLE_FIELD_BOUMAHRA, submitReq);
    const prefs = built.payload.preferences as Record<string, unknown>;
    const farmerAcc = built.payload.farmer_account as Record<string, unknown>;
    expect(prefs.target_crop_ids).toEqual(["CHICKPEA_SPRING"]);
    expect(prefs.excluded_crop_ids).toEqual(["BARLEY"]);
    expect(prefs.water_saving_weight).toBe(0.05);
    expect(prefs.soil_improvement_weight).toBe(0.05);
    expect(prefs.income_weight).toBe(1);
    expect(farmerAcc.farm_id).toBeUndefined();
    expect(farmerAcc.field_count_in_submission).toBeUndefined();
    expect(farmerAcc.user_id).toBe("farm_1");
    expect(farmerAcc.role).toBe("farmer");
    expect(farmerAcc.display_name).toBe("Boumahra Seybouse Parcel");
    expect(built.adapterWarnings.length).toBeGreaterThanOrEqual(2);
  });

  it("translates real SI-Model response strictly into valid Zod FieldPlan even with nullable evidence, boolean needs_local_review, and 0 baselines", () => {
    const mapped = new Map<string, string[]>([["CHICKPEA_SPRING", ["chickpea"]]]);
    const { fieldPlan } = translateSiAnalyzeResponseToFieldPlan(
      REALISTIC_SI_ANALYZE_RESPONSE,
      {
        overrideFieldId: "F1",
        overrideFieldName: "Boumahra Seybouse Parcel",
        mappedTargetToOriginal: mapped,
        requestedFrontendIds: ["chickpea"],
      }
    );

    expect(fieldPlan.status).toBe("partial");
    expect(fieldPlan.strategies).toHaveLength(3);
    expect(fieldPlan.strategies[0].scores.water_efficiency).toBe(84);
    expect(fieldPlan.strategies[0].scores.priority_fit).toBe(81);
    expect(fieldPlan.strategies[0].explanation.needs_local_review).toEqual([
      "Check surface drainage before November wheat sowing.",
    ]);
    // SOC g/kg -> % conversion and non-null observed_value invariant
    const socEv = fieldPlan.strategies[0].explanation.evidence.find(
      (e) => e.parameter === "organic_matter_percent"
    );
    expect(socEv?.observed_value).toBe(1.27);
    expect(socEv?.unit).toBe("%");
    const demEv = fieldPlan.strategies[0].explanation.evidence.find(
      (e) => e.parameter === "elevation_m"
    );
    expect(typeof demEv?.observed_value).toBe("string");
    expect(fieldPlan.requested_crop_results[0].requested_crop_id).toBe("chickpea");
    expect(fieldPlan.requested_crop_results[0].outcome).toBe("included");
  });

  it("communicates with SI-Model endpoints, rejects outside-Guelma 422, auto-retries PAST_PLANNING_SEASON, re-fetches /analyses/{id}, and persists selections", async () => {
    const analyzeModes: Array<string | undefined> = [];
    let fetchAnalysesHit = 0;

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const parsedBody = init?.body ? JSON.parse(String(init.body)) : null;

      if (url.endsWith("/api/v1/health")) {
        return new Response(
          JSON.stringify({
            status: "ok",
            service: "FieldShift-API",
            decision_engine_version: "FieldShift-PhaseFJ-1.1.0",
            dataset_version_used:
              "Guelma_Phases_AD_SoilGridsV6_250m_GPM_SMAP_11km_POWER_2016_2025",
            knowledge_base: { crops_count: 13, crop_rules_count: 15, sequence_rules_count: 10 },
            geospatial_assets: { all_core_assets_present: true },
            database: { active_backend: "sqlite_local" },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      if (url.endsWith("/api/v1/reference/crops")) {
        return new Response(
          JSON.stringify({
            crops: [
              {
                crop_id: "DURUM_WHEAT",
                canonical_name: "Durum Wheat",
                crop_category: "cereals",
                in_annual_rotation_scope: true,
                guelma_evidence_status: "VALIDATED",
              },
              {
                crop_id: "CHICKPEA_SPRING",
                canonical_name: "Spring Chickpea",
                crop_category: "legumes",
                in_annual_rotation_scope: true,
                guelma_evidence_status: "VALIDATED",
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      if (url.endsWith("/api/v1/reference/guelma-boundary")) {
        return new Response(
          JSON.stringify({
            type: "FeatureCollection",
            features: [
              {
                type: "Feature",
                properties: { wilaya: "Guelma" },
                geometry: {
                  type: "Polygon",
                  coordinates: [
                    [
                      [7.0, 36.02],
                      [7.85, 36.02],
                      [7.85, 36.68],
                      [7.0, 36.68],
                      [7.0, 36.02],
                    ],
                  ],
                },
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      if (url.endsWith("/api/v1/fields/validate")) {
        const ring = parsedBody.field.geometry.coordinates[0] as number[][];
        const lon = ring[0][0];
        if (lon < 6.0) {
          return new Response(
            JSON.stringify({
              detail: {
                error_code: "INVALID_FIELD_POLYGON",
                message: "Field polygon lies outside Guelma Wilaya boundary (overlap 0.0%).",
              },
            }),
            { status: 422, headers: { "Content-Type": "application/json" } }
          );
        }
        return new Response(
          JSON.stringify({
            valid: true,
            field_id: parsedBody.field.field_id,
            area_m2: 238500,
            area_ha: 23.85,
            perimeter_m: 1960,
            centroid_lon_lat: [7.483, 36.472],
            wilaya_overlap_pct: 100.0,
            primary_commune: { name_2: "Boumahra Ahmed" },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      if (url.endsWith("/api/v1/fields/analyze")) {
        const planningMode = parsedBody.planning.planning_mode;
        analyzeModes.push(planningMode);
        if (planningMode === "CURRENT_PLANNING") {
          return new Response(
            JSON.stringify({
              detail: {
                error_code: "PAST_PLANNING_SEASON",
                message: "Spring 2026 lies in the past; use HISTORICAL_SIMULATION.",
              },
            }),
            { status: 422, headers: { "Content-Type": "application/json" } }
          );
        }
        return new Response(JSON.stringify(REALISTIC_SI_ANALYZE_RESPONSE), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      if (url.includes("/api/v1/analyses/ANAL_a1b2c3d4e5f6")) {
        fetchAnalysesHit += 1;
        return new Response(JSON.stringify(REALISTIC_SI_ANALYZE_RESPONSE), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      return new Response(JSON.stringify({ detail: "Unexpected route" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    });

    const storage = makeMemoryStorage();
    const bridge = createSiModelBridge({
      baseRoot: "http://127.0.0.1:8000/api/v1",
      fetchImpl: fetchMock as unknown as typeof fetch,
      getStorage: () => storage,
    });

    const health = await bridge.getHealth("dependencies");
    expect(health.status).toBe("ok");
    expect(health.ml_service.reachable).toBe(true);
    expect(health.ml_service.ml_engine_version).toBe("FieldShift-PhaseFJ-1.1.0");

    const catalog = await bridge.fetchAllCatalogItems("fr");
    expect(catalog.items).toHaveLength(2);
    expect(catalog.items.find((c) => c.crop_id === "chickpea_spring")?.display_name).toBe(
      "Pois chiche de printemps"
    );

    const boundary = await bridge.getDemoLocationBoundary(1);
    expect(boundary.bbox).toEqual([7, 36.02, 7.85, 36.68]);

    await bridge.startGuestSession(1);

    // Outside Guelma (Setif) rejected with OUTSIDE_DEMO_BOUNDARY
    await expect(
      bridge.createField("farm_1", {
        field_id: "SETIF_1",
        field_name: "Setif Test",
        is_unverified_demo_parcel: false,
        location: { latitude: 36.19, longitude: 5.41, boundary: null },
        area_hectares: 5,
        elevation_m: "",
        soil: { soil_type: "unknown", soil_ph: "", organic_matter_percent: "", soil_test_date: "" },
        water: {
          availability: "moderate",
          source: "well",
          source_other: "",
          irrigation_system: "drip",
        },
        crop_history: [
          { season: "autumn", year: 2025, planting_month: 11, crop_id: "durum_wheat" },
        ],
      })
    ).rejects.toMatchObject({
      code: "OUTSIDE_DEMO_BOUNDARY",
      status: 422,
    } satisfies Partial<ApiClientError>);

    // Valid Boumahra field saved after live /fields/validate
    const created = await bridge.createField("farm_1", {
      field_id: "BOUMAHRA_1",
      field_name: "Boumahra Seybouse",
      is_unverified_demo_parcel: false,
      location: { latitude: 36.472, longitude: 7.483, boundary: null },
      area_hectares: 23.85,
      elevation_m: 140,
      soil: {
        soil_type: "clay",
        soil_ph: 7.2,
        organic_matter_percent: 2.1,
        soil_test_date: "2025-10-12",
      },
      water: {
        availability: "moderate",
        source: "rainwater",
        source_other: "",
        irrigation_system: "rainfed",
      },
      crop_history: [
        { season: "autumn", year: 2025, planting_month: 11, crop_id: "durum_wheat" },
      ],
    });
    expect(created.field_id).toBe("BOUMAHRA_1");

    // Submit analysis -> triggers CURRENT_PLANNING 422 then automatic HISTORICAL_SIMULATION retry
    const queued = await bridge.submitAnalysis({
      language: "en",
      farm_id: "farm_1",
      field_ids: ["BOUMAHRA_1"],
      planning: {
        start_season: "spring",
        start_year: 2026,
        horizon_seasons: 4,
        cycle_mode: "annual_rotation",
        planting_month: null,
        scenario_overrides: { temp_delta_c: 0, precip_pct_delta: 0 },
      },
      priorities: {
        weights: {
          water_saving: 35,
          soil_improvement: 25,
          income: 15,
          risk_reduction: 15,
          forage_value: 10,
        },
        market_preference: "local_market",
        target_crop_ids: ["chickpea"],
        excluded_crop_ids: [],
        equipment_constraints: [],
      },
    });
    expect(analyzeModes).toEqual(["CURRENT_PLANNING", "HISTORICAL_SIMULATION"]);

    const poll = await bridge.pollAnalysisRequest(queued.request_id);
    expect(poll.status).toBe("partial");
    expect(poll.analysis_id).toMatch(/^analysis_[0-9a-f]{12}$/);

    // Persist strategy selection & verify re-fetch via GET /api/v1/analyses/{ANAL_...}
    await bridge.updateAnalysisSelection(poll.analysis_id!, {
      field_id: "BOUMAHRA_1",
      strategy_id: "STRAT_CEREAL_FORAGE",
      selection_status: "selected",
    });

    const refreshed = await bridge.getAnalysisResult(poll.analysis_id!);
    expect(fetchAnalysesHit).toBe(1);
    AnalysisResultSchema.parse(refreshed.result);
    AnalysisEnvelopeSchema.parse(refreshed);
    const forageStrat = refreshed.result.field_plans[0].strategies.find(
      (s) => s.strategy_id === "STRAT_CEREAL_FORAGE"
    );
    expect(forageStrat?.seasons[0].selection_status).toBe("selected");
  });
});
