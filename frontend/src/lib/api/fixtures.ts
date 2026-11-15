import type {
  AnalysisEnvelope,
  AnalysisPollEnvelope,
  AnalysisResult,
  AnalysisSubmitRequest,
  BoundaryFeature,
  CatalogPage,
  CropItem,
  DemoLocationSummary,
  FarmAnalysesPage,
  FarmAnalysisSummary,
  FarmPublic,
  FarmWriteRequest,
  FieldDetailPublic,
  FieldPublic,
  FieldWriteRequest,
  GuestSessionInfo,
  GuestSessionStartResponse,
  HealthResponse,
  Language,
  RegisterResponse,
  SelectionPatchResponse,
  TokenPairResponse,
  UserDataExport,
  UserProfile,
  WarningNotice,
} from "@/lib/schemas";
import {
  GUELMA_FALLBACK_BOUNDARY,
  isInsideGuelmaBoundary,
} from "@/lib/geo/guelma";
import { validateAnalysisPreSubmit } from "@/lib/validation";
import { ApiClientError } from "./errors";

// ---------------------------------------------------------------------------
// Verbatim Visual I/O Fixtures (§9.1 - §9.4)
// ---------------------------------------------------------------------------

export const GUELMA_DEMO_LOCATION: DemoLocationSummary = {
  id: 1,
  code: "guelma",
  name: "Guelma",
  country: "Algeria",
  region: "Guelma",
};

export const DEMO_PARCEL_UNVERIFIED_WARNING: WarningNotice = {
  code: "DEMO_PARCEL_UNVERIFIED",
  message:
    "This demo parcel is pre-designated by the project team; its real field measurements have not yet been studied and will be added later.",
  fields: ["F1"],
};

export const FIXTURE_INPUT_9_1 = {
  schema_version: "5.0",
  request_id: "550e8400-e29b-41d4-a716-446655440000",
  catalog_version: "2026.11",
  dataset_version: "2026.11-guelma-v1",
  language: "en" as Language,
  farm: {
    farm_id: "farm_1",
    farm_name: "Ferme Guelma Demo",
    country: "Algeria",
    region: "Guelma",
    commune: "Guelma",
  },
  planning: {
    start_season: "spring" as const,
    start_year: 2027,
    horizon_seasons: 4,
    cycle_mode: "annual_rotation" as const,
    planting_month: 3,
    scenario_overrides: {
      temp_delta_c: 0.0,
      precip_pct_delta: 0.0,
    },
  },
  priorities: {
    weights: {
      water_saving: 30,
      soil_improvement: 25,
      income: 25,
      risk_reduction: 10,
      forage_value: 10,
    },
    market_preference: "mixed" as const,
    target_crop_ids: ["chickpea"],
    excluded_crop_ids: [],
    equipment_constraints: [],
  },
  fields: [
    {
      field_id: "F1",
      field_name: "Guelma Team Demo Parcel (Unstudied)",
      is_unverified_demo_parcel: true,
      location: {
        latitude: 36.52,
        longitude: 7.52,
        boundary: null,
      },
      area_hectares: 12.5,
      elevation_m: null,
      crop_history: [
        {
          season: "autumn" as const,
          year: 2025,
          planting_month: 11,
          crop_id: "durum_wheat",
          crop_name_raw: "Durum Wheat",
          catalog_version: "2026.11",
          yield_tons_per_hectare: null,
        },
        {
          season: "autumn" as const,
          year: 2024,
          planting_month: 11,
          crop_id: "barley",
          crop_name_raw: "Barley",
          catalog_version: "2026.11",
          yield_tons_per_hectare: null,
        },
      ],
      soil: {
        soil_type: "unknown" as const,
        source: "unknown" as const,
        soil_ph: null,
        organic_matter_percent: null,
        soil_test_date: null,
      },
      water: {
        availability: "moderate" as const,
        source: "well" as const,
        source_other: null,
        irrigation_system: "drip" as const,
      },
    },
  ],
};

// Verbatim §9.3 output.json
export const FIXTURE_OUTPUT_9_3: AnalysisResult = {
  schema_version: "5.0",
  request_id: "550e8400-e29b-41d4-a716-446655440000",
  dataset_version_used: "2026.11-guelma-v1",
  generated_at: "2026-11-14T10:06:12Z",
  status: "ok",
  language: "en",
  ml_engine_version: "agro-ml-2.1.0",
  overall_summary:
    "Rotating spring chickpea and forage vetch into cereal-dominated parcel F1 reduces multi-year moisture depletion and breaks cereal disease cycles.",
  disclaimer:
    "Recommendations depend on the unverified demo parcel inputs supplied and dataset_version 2026.11-guelma-v1; verify soil chemistry locally prior to planting.",
  field_plans: [
    {
      field_id: "F1",
      field_name: "Guelma Team Demo Parcel (Unstudied)",
      status: "ok",
      partial_reason: null,
      field_insights: {
        bare_field_periods: [
          {
            start_month: 7,
            end_month: 10,
            evidence: "Summer fallow gap observed between cereal harvests.",
          },
        ],
        stress_periods: [
          {
            type: "drought",
            months: [6, 7, 8],
            severity: "medium",
            evidence: "Seasonal water deficit pattern in local dataset for zone F1.",
          },
        ],
        climate_trend_summary:
          "Dataset zone 2026.11-guelma-v1 indicates recurring dry summer months with moderate spring variability.",
      },
      strategies: [
        {
          strategy_id: "S1_baseline_cereal",
          name: "Existing Cereal Baseline",
          is_existing_rotation: true,
          description:
            "Continues historical autumn cereal dominance as the comparison baseline.",
          seasons: [
            {
              order: 1,
              season: "spring",
              year: 2027,
              planting_month: 3,
              crop_id: "fallow",
              crop_name: "Bare Fallow",
              category: "fallow",
              role: "fallow",
              selection_status: "suggested",
              notes: null,
            },
            {
              order: 2,
              season: "autumn",
              year: 2027,
              planting_month: 11,
              crop_id: "durum_wheat",
              crop_name: "Durum Wheat",
              category: "cereals",
              role: "main_crop",
              selection_status: "suggested",
              notes: null,
            },
            {
              order: 3,
              season: "spring",
              year: 2028,
              planting_month: 3,
              crop_id: "fallow",
              crop_name: "Bare Fallow",
              category: "fallow",
              role: "fallow",
              selection_status: "suggested",
              notes: null,
            },
            {
              order: 4,
              season: "autumn",
              year: 2028,
              planting_month: 11,
              crop_id: "barley",
              crop_name: "Barley",
              category: "cereals",
              role: "main_crop",
              selection_status: "suggested",
              notes: null,
            },
          ],
          scores: {
            water_efficiency: 52,
            erosion_protection: 48,
            organic_matter_gain: 35,
            nitrogen_contribution: 25,
            pest_cycle_disruption: 30,
            income_forage_value: 58,
            priority_fit: 49,
            bare_field_days_per_year: 140,
          },
          confidence: "medium",
          explanation: {
            reasons: [
              {
                code: "BASELINE_CONTINUITY",
                text: "Reflects prior autumn wheat/barley cropping history.",
                params: { prior_crops: 2 },
              },
            ],
            evidence: [
              {
                data_source: "farmer_input",
                parameter: "water_availability",
                observed_value: "moderate",
                unit: null,
                period: null,
                derived: false,
                interpretation:
                  "Farmer-reported moderate well availability with drip irrigation.",
              },
            ],
            benefits: [
              {
                benefit_id: "B0",
                title: "Familiar machinery workflow",
                description: "Requires no immediate equipment change.",
              },
            ],
            risks: [
              {
                risk_id: "R0",
                title: "Cereal monoculture pathogen carryover",
                description: "Consecutive cereals increase root disease pressure.",
                severity: "high",
                likelihood: "medium",
                mitigation: "Introduce a legume break crop.",
              },
            ],
            assumptions: [
              "Parcel F1 field parameters remain unstudied until surveyed.",
            ],
            information_gaps: [
              "Missing laboratory soil pH and organic matter measurements.",
            ],
            needs_local_review: [
              "Verify soil texture and organic matter on parcel F1.",
            ],
          },
        },
        {
          strategy_id: "S2_water_resilient",
          name: "Chickpea & Drip Forage Balanced Rotation",
          is_existing_rotation: false,
          description:
            "Introduces nitrogen-fixing chickpea and conserved forage vetch alongside durum wheat.",
          seasons: [
            {
              order: 1,
              season: "spring",
              year: 2027,
              planting_month: 3,
              crop_id: "chickpea",
              crop_name: "Chickpea",
              category: "legumes",
              role: "nitrogen_fixer",
              selection_status: "suggested",
              notes: null,
            },
            {
              order: 2,
              season: "autumn",
              year: 2027,
              planting_month: 11,
              crop_id: "durum_wheat",
              crop_name: "Durum Wheat",
              category: "cereals",
              role: "cash_crop",
              selection_status: "suggested",
              notes: null,
            },
            {
              order: 3,
              season: "spring",
              year: 2028,
              planting_month: 3,
              crop_id: "vetch_forage",
              crop_name: "Vetch Forage",
              category: "forage",
              role: "forage",
              selection_status: "suggested",
              notes: null,
            },
            {
              order: 4,
              season: "autumn",
              year: 2028,
              planting_month: 11,
              crop_id: "barley",
              crop_name: "Barley",
              category: "cereals",
              role: "break_crop",
              selection_status: "suggested",
              notes: null,
            },
          ],
          scores: {
            water_efficiency: 82,
            erosion_protection: 76,
            organic_matter_gain: 74,
            nitrogen_contribution: 80,
            pest_cycle_disruption: 85,
            income_forage_value: 78,
            priority_fit: 84,
            bare_field_days_per_year: 55,
          },
          confidence: "medium",
          explanation: {
            reasons: [
              {
                code: "TARGET_CROP_MATCH",
                text: "Includes farmer requested crop chickpea in season 1.",
                params: { crop_id: "chickpea" },
              },
            ],
            evidence: [
              {
                data_source: "dataset",
                parameter: "precipitation",
                observed_value: 312,
                unit: "mm/year",
                period: "dataset-zone-baseline",
                derived: true,
                interpretation:
                  "Mean annual dataset precipitation aligns with spring chickpea establishment.",
              },
              {
                data_source: "dataset",
                parameter: "precipitation_anomaly",
                observed_value: -18,
                unit: "% vs historical mean",
                period: "dataset-dry-quantile",
                derived: true,
                interpretation:
                  "Drier years favor drought-tolerant legumes over fallow cereals.",
              },
            ],
            benefits: [
              {
                benefit_id: "B1",
                title: "Biological nitrogen fixation",
                description:
                  "Spring chickpea lowers synthetic nitrogen demand for autumn wheat.",
              },
            ],
            risks: [
              {
                risk_id: "R1",
                title: "Soil chemistry uncertainty",
                description:
                  "Unstudied parcel soil pH could affect legume nodulation.",
                severity: "medium",
                likelihood: "medium",
                mitigation: "Collect topsoil lab sample before spring sowing.",
              },
            ],
            assumptions: [
              "Drip irrigation system remains operational for supplemental spring moisture.",
            ],
            information_gaps: [
              "Parcel F1 awaits physical soil sampling (`is_unverified_demo_parcel: true`).",
            ],
            needs_local_review: [
              "Confirm chickpea seed variety suitability with local extension service.",
            ],
          },
        },
        {
          strategy_id: "S3_income_diversified",
          name: "Market Cereal & Legume Cash Focus",
          is_existing_rotation: false,
          description:
            "Prioritizes market revenue with alternating durum wheat and chickpea cycles.",
          seasons: [
            {
              order: 1,
              season: "spring",
              year: 2027,
              planting_month: 3,
              crop_id: "chickpea",
              crop_name: "Chickpea",
              category: "legumes",
              role: "cash_crop",
              selection_status: "suggested",
              notes: null,
            },
            {
              order: 2,
              season: "autumn",
              year: 2027,
              planting_month: 11,
              crop_id: "durum_wheat",
              crop_name: "Durum Wheat",
              category: "cereals",
              role: "cash_crop",
              selection_status: "suggested",
              notes: null,
            },
            {
              order: 3,
              season: "spring",
              year: 2028,
              planting_month: 3,
              crop_id: "sunflower",
              crop_name: "Sunflower",
              category: "oilseeds",
              role: "break_crop",
              selection_status: "suggested",
              notes: null,
            },
            {
              order: 4,
              season: "autumn",
              year: 2028,
              planting_month: 11,
              crop_id: "durum_wheat",
              crop_name: "Durum Wheat",
              category: "cereals",
              role: "cash_crop",
              selection_status: "suggested",
              notes: null,
            },
          ],
          scores: {
            water_efficiency: 70,
            erosion_protection: 72,
            organic_matter_gain: 64,
            nitrogen_contribution: 68,
            pest_cycle_disruption: 79,
            income_forage_value: 88,
            priority_fit: 77,
            bare_field_days_per_year: 75,
          },
          confidence: "medium",
          explanation: {
            reasons: [
              {
                code: "MIXED_MARKET_REVENUE",
                text: "Balances pulse and oilseed break crops around cash wheat.",
                params: { cash_seasons: 4 },
              },
            ],
            evidence: [
              {
                data_source: "farmer_input",
                parameter: "water_availability",
                observed_value: "moderate",
                unit: null,
                period: null,
                derived: false,
                interpretation:
                  "Moderate well irrigation supports spring oilseed establishment.",
              },
            ],
            benefits: [
              {
                benefit_id: "B2",
                title: "High gross revenue potential",
                description: "Maximize marketed crop share across 4 seasons.",
              },
            ],
            risks: [
              {
                risk_id: "R2",
                title: "Higher irrigation demand in summer",
                description: "Oilseed phase demands reliable mid-season watering.",
                severity: "medium",
                likelihood: "low",
                mitigation: "Schedule drip irrigation during flowering.",
              },
            ],
            assumptions: ["No soil salinity issues on unstudied parcel F1."],
            information_gaps: ["Exact well summer yield rate not measured."],
            needs_local_review: [
              "Verify local buyer uptake for spring oilseed.",
            ],
          },
        },
      ],
      suggested_strategy_id: "S2_water_resilient",
      requested_crop_results: [
        {
          requested_crop_id: "chickpea",
          outcome: "included",
          included_in_strategy_ids: [
            "S2_water_resilient",
            "S3_income_diversified",
          ],
          replaced_by_crop_id: null,
          explanation:
            "Chickpea fits spring 2027 well as a nitrogen-fixing legume breaking historical autumn cereal dominance.",
          comparison: [],
          evidence: [],
        },
      ],
      data_quality: {
        completeness_score: 0.45,
        confidence_note:
          "Reduced completeness because parcel F1 is an unverified demo parcel with unknown soil chemistry.",
        missing_data: ["soil_ph", "organic_matter_percent", "elevation_m"],
        warnings: [
          "DEMO_PARCEL_UNVERIFIED: Parcel measurements have not yet been studied.",
        ],
        limitations: [
          "Predictions rely on dataset_version 2026.11-guelma-v1 regional signals rather than verified soil sampling on F1.",
        ],
      },
    },
  ],
  data_quality: {
    completeness_score: 0.45,
    confidence_note: "Farm-level confidence reflects 1 unverified demo parcel.",
    missing_data: ["F1.soil_ph", "F1.organic_matter_percent"],
    warnings: ["DEMO_PARCEL_UNVERIFIED"],
    limitations: ["Awaiting field survey data for pre-designated parcel F1."],
  },
};

// Verbatim §9.4 crops + Guelma supplementary catalog crops
export const FIXTURE_CATALOG_ITEMS: CropItem[] = [
  {
    crop_id: "durum_wheat",
    display_name: "Durum Wheat",
    names: { en: "Durum Wheat", fr: "Blé dur", ar: "قمح صلب" },
    category: "cereals",
    roles: ["main_crop", "cash_crop"],
    family: "Poaceae",
  },
  {
    crop_id: "barley",
    display_name: "Barley",
    names: { en: "Barley", fr: "Orge", ar: "شعير" },
    category: "cereals",
    roles: ["main_crop", "break_crop"],
    family: "Poaceae",
  },
  {
    crop_id: "chickpea",
    display_name: "Chickpea",
    names: { en: "Chickpea", fr: "Pois chiche", ar: "حمص" },
    category: "legumes",
    roles: ["nitrogen_fixer", "cash_crop"],
    family: "Fabaceae",
  },
  {
    crop_id: "vetch_forage",
    display_name: "Vetch Forage",
    names: { en: "Vetch Forage", fr: "Vesce fourragère", ar: "بيقية علفية" },
    category: "forage",
    roles: ["forage", "nitrogen_fixer"],
    family: "Fabaceae",
  },
  {
    crop_id: "sunflower",
    display_name: "Sunflower",
    names: { en: "Sunflower", fr: "Tournesol", ar: "دوار الشمس" },
    category: "oilseeds",
    roles: ["cash_crop", "break_crop"],
    family: "Asteraceae",
  },
  {
    crop_id: "fallow",
    display_name: "Bare Fallow",
    names: { en: "Bare Fallow", fr: "Jachère", ar: "أرض بور" },
    category: "fallow",
    roles: ["fallow"],
    family: "None",
  },
  {
    crop_id: "fava_bean",
    display_name: "Fava Bean",
    names: { en: "Fava Bean", fr: "Fève", ar: "فول" },
    category: "legumes",
    roles: ["nitrogen_fixer", "cash_crop"],
    family: "Fabaceae",
  },
  {
    crop_id: "lentil",
    display_name: "Lentil",
    names: { en: "Lentil", fr: "Lentille", ar: "عدس" },
    category: "legumes",
    roles: ["nitrogen_fixer", "cash_crop"],
    family: "Fabaceae",
  },
  {
    crop_id: "oats_forage",
    display_name: "Oats Forage",
    names: { en: "Oats Forage", fr: "Avoine fourragère", ar: "شوفان علفي" },
    category: "forage",
    roles: ["forage", "cover_crop"],
    family: "Poaceae",
  },
  {
    crop_id: "berseem_clover",
    display_name: "Berseem Clover",
    names: { en: "Berseem Clover", fr: "Trèfle d'Alexandrie", ar: "برسيم" },
    category: "cover_crops",
    roles: ["cover_crop", "nitrogen_fixer", "forage"],
    family: "Fabaceae",
  },
];

// ---------------------------------------------------------------------------
// Stateful Fixture Transport Store (ONLY used when NEXT_PUBLIC_API_MODE=fixture)
// ---------------------------------------------------------------------------

interface FixtureAnalysisRecord {
  analysis_id: string;
  request_id: string;
  farm_id: string;
  status: "pending" | "running" | "ok" | "partial" | "failed" | "cancelled";
  pollCount: number;
  created_at: string;
  duration_ms: number | null;
  language: Language;
  catalog_version: string;
  dataset_version: string;
  ml_engine_version: string;
  warnings: WarningNotice[];
  degraded_mode: AnalysisEnvelope["degraded_mode"];
  result: AnalysisResult;
  selections: Record<string, Record<string, "suggested" | "selected" | "rejected">>;
  input_hash: string;
}

class FixtureBackendState {
  guestToken: string | null = null;
  guestRevoked = false;
  guestCreatedAt: string | null = null;
  guestExpiresAt: string | null = null;
  user: UserProfile | null = null;
  accessToken: string | null = null;
  refreshToken: string | null = null;
  farms: Map<string, FarmPublic> = new Map();
  fieldsByFarm: Map<string, Map<string, FieldDetailPublic>> = new Map();
  analysesById: Map<string, FixtureAnalysisRecord> = new Map();
  analysesByRequestId: Map<string, FixtureAnalysisRecord> = new Map();
  analysisQuartersUsed = 5;
  farmSeq = 1;
  analysisSeq = 1;
  simulateDegraded = false;
  simulateGuestLimit = false;

  reset() {
    this.guestToken = null;
    this.guestRevoked = false;
    this.guestCreatedAt = null;
    this.guestExpiresAt = null;
    this.user = null;
    this.accessToken = null;
    this.refreshToken = null;
    this.farms.clear();
    this.fieldsByFarm.clear();
    this.analysesById.clear();
    this.analysesByRequestId.clear();
    this.analysisQuartersUsed = 5;
    this.farmSeq = 1;
    this.analysisSeq = 1;
    this.simulateDegraded = false;
    this.simulateGuestLimit = false;
  }

  seedDemoWorkspace() {
    const farmId = "farm_1";
    const f1: FieldDetailPublic = {
      farm_id: farmId,
      field_id: "F1",
      field_name: "Guelma Team Demo Parcel (Unstudied)",
      is_unverified_demo_parcel: true,
      location: {
        latitude: 36.52,
        longitude: 7.52,
        boundary: null,
      },
      area_hectares: 12.5,
      elevation_m: null,
      soil: {
        soil_type: "unknown",
        source: "unknown",
        soil_ph: null,
        organic_matter_percent: null,
        soil_test_date: null,
      },
      water: {
        availability: "moderate",
        source: "well",
        source_other: null,
        irrigation_system: "drip",
      },
      crop_history: [
        {
          season: "autumn",
          year: 2025,
          planting_month: 11,
          crop_id: "durum_wheat",
          crop_name_raw: "Durum Wheat",
          yield_tons_per_hectare: null,
          notes: null,
        },
        {
          season: "autumn",
          year: 2024,
          planting_month: 11,
          crop_id: "barley",
          crop_name_raw: "Barley",
          yield_tons_per_hectare: null,
          notes: null,
        },
      ],
      warnings: [DEMO_PARCEL_UNVERIFIED_WARNING],
    };

    this.farms.set(farmId, {
      farm_id: farmId,
      farm_name: "Ferme Guelma Demo",
      country: "Algeria",
      region: "Guelma",
      commune: "Guelma",
      field_count: 1,
      created_at: "2026-11-14T10:00:00Z",
    });

    const fMap = new Map<string, FieldDetailPublic>();
    fMap.set("F1", f1);
    this.fieldsByFarm.set(farmId, fMap);

    const clonedResult = structuredClone(FIXTURE_OUTPUT_9_3);
    const record: FixtureAnalysisRecord = {
      analysis_id: "analysis_4f9a8c120e3b",
      request_id: FIXTURE_INPUT_9_1.request_id,
      farm_id: farmId,
      status: "ok",
      pollCount: 2,
      created_at: "2026-11-14T10:06:12Z",
      duration_ms: 1420,
      language: "en",
      catalog_version: "2026.11",
      dataset_version: "2026.11-guelma-v1",
      ml_engine_version: "agro-ml-2.1.0",
      warnings: [DEMO_PARCEL_UNVERIFIED_WARNING],
      degraded_mode: null,
      result: clonedResult,
      selections: {},
      input_hash: "base-f1",
    };

    this.analysesById.set(record.analysis_id, record);
    this.analysesByRequestId.set(record.request_id, record);
    this.analysisQuartersUsed = 5;
    this.farmSeq = 2;
  }
}

export const fixtureState = new FixtureBackendState();

function makeRequestId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "550e8400-e29b-41d4-a716-446655440000";
}

function formatResultWithSelections(record: FixtureAnalysisRecord): AnalysisResult {
  const copy = structuredClone(record.result);
  copy.field_plans = copy.field_plans.map((fp) => {
    const fieldSel = record.selections[fp.field_id] || {};
    return {
      ...fp,
      strategies: fp.strategies.map((strat) => {
        const status = fieldSel[strat.strategy_id];
        if (!status) return strat;
        return {
          ...strat,
          seasons: strat.seasons.map((s) => ({
            ...s,
            selection_status: status,
          })),
        };
      }),
    };
  });
  return copy;
}

function computeFieldWarnings(
  field: Pick<FieldWriteRequest, "field_id" | "is_unverified_demo_parcel" | "location">,
  isGuest: boolean
): WarningNotice[] {
  const warnings: WarningNotice[] = [];
  if (field.is_unverified_demo_parcel) {
    warnings.push({
      ...DEMO_PARCEL_UNVERIFIED_WARNING,
      fields: [field.field_id],
    });
  }
  const inside = isInsideGuelmaBoundary(
    field.location.latitude,
    field.location.longitude,
    GUELMA_FALLBACK_BOUNDARY
  );
  if (!inside) {
    if (isGuest) {
      throw new ApiClientError({
        status: 422,
        code: "OUTSIDE_DEMO_BOUNDARY",
        message:
          "Guest parcels must sit inside the Wilaya of Guelma MVP boundary (PostGIS ST_Covers = false).",
        details: [{ field_id: field.field_id, latitude: field.location.latitude, longitude: field.location.longitude }],
        requestId: makeRequestId(),
      });
    }
    warnings.push({
      code: "MVP_OUTSIDE_COVERAGE",
      message:
        "Field lies outside the Wilaya of Guelma MVP boundary; regional dataset extrapolation is limited.",
      fields: [field.field_id],
    });
  }
  return warnings;
}

function buildScenarioResult(
  req: AnalysisSubmitRequest,
  requestId: string,
  fields: FieldDetailPublic[]
): AnalysisResult {
  const base = structuredClone(FIXTURE_OUTPUT_9_3);
  base.request_id = requestId;
  base.language = req.language;
  base.generated_at = new Date().toISOString();

  const tempDelta = req.planning.scenario_overrides?.temp_delta_c ?? 0;
  const precipDelta = req.planning.scenario_overrides?.precip_pct_delta ?? 0;
  const primaryField = fields[0];
  const isUnstudied = fields.some((f) => f.is_unverified_demo_parcel);

  const summaryPrefix =
    req.language === "fr"
      ? "Rotation recommandée pour optimiser la rétention d'eau et rompre le cycle céréalier"
      : req.language === "ar"
        ? "توصية بدورة زراعية متوازنة لحفظ الرطوبة وكسر دورة أمراض الحبوب"
        : `Scenario (${tempDelta >= 0 ? "+" : ""}${tempDelta}°C, ${precipDelta >= 0 ? "+" : ""}${precipDelta}%) rotation analysis`;

  base.overall_summary =
    tempDelta === 0 && precipDelta === 0 && primaryField.field_id === "F1" && req.language === "en"
      ? FIXTURE_OUTPUT_9_3.overall_summary
      : `${summaryPrefix} — ${primaryField.field_name} (${fields.length} parcel${fields.length > 1 ? "s" : ""}).`;

  base.field_plans = fields.map((field) => {
    const templatePlan = structuredClone(FIXTURE_OUTPUT_9_3.field_plans[0]);
    templatePlan.field_id = field.field_id;
    templatePlan.field_name = field.field_name;
    const missing: string[] = [];
    if (field.soil.soil_ph === null) missing.push("soil_ph");
    if (field.soil.organic_matter_percent === null) missing.push("organic_matter_percent");
    if (field.elevation_m === null) missing.push("elevation_m");

    const completeness =
      field.soil.soil_type === "unknown"
        ? 0.45
        : Number((1 - missing.length * 0.1).toFixed(2));

    templatePlan.data_quality = {
      completeness_score: completeness,
      confidence_note:
        missing.length === 0
          ? "Complete farmer soil chemistry, elevation, water, and crop history provided."
          : `Completeness ${(completeness * 100).toFixed(0)}%: missing ${missing.join(", ")}.`,
      missing_data: missing,
      warnings: field.warnings.map((w) => `${w.code}: ${w.message}`),
      limitations: [
        isUnstudied
          ? "Relies on regional dataset_version 2026.11-guelma-v1 while unstudied parcel awaits soil lab measurements."
          : "Combined farmer soil/water records with pinned 2026.11-guelma-v1 regional climate signals.",
      ],
    };

    if (tempDelta > 0 || precipDelta < 0) {
      templatePlan.field_insights.climate_trend_summary = `Adjusted scenario (+${tempDelta}°C, ${precipDelta}% rain) increases summer evaporative deficit across ${field.field_name}; legume-forage cover cuts bare-soil loss.`;
    }

    // Add farmer soil & elevation evidence items if provided
    const farmerEvidence = [...templatePlan.strategies[1].explanation.evidence];
    if (field.soil.soil_type !== "unknown") {
      farmerEvidence.push({
        data_source: "farmer_input",
        parameter: "soil_type",
        observed_value: field.soil.soil_type,
        unit: null,
        period: field.soil.soil_test_date,
        derived: false,
        interpretation: `Farmer-verified ${field.soil.soil_type} soil texture.`,
      });
    }
    if (field.soil.soil_ph !== null) {
      farmerEvidence.push({
        data_source: "farmer_input",
        parameter: "soil_ph",
        observed_value: field.soil.soil_ph,
        unit: null,
        period: field.soil.soil_test_date,
        derived: false,
        interpretation: "Farmer lab soil pH measurement guides legume nodulation fit.",
      });
    }
    if (field.elevation_m !== null) {
      farmerEvidence.push({
        data_source: "farmer_input",
        parameter: "elevation_m",
        observed_value: field.elevation_m,
        unit: "m",
        period: null,
        derived: false,
        interpretation: "Farmer-provided parcel elevation.",
      });
    }
    templatePlan.strategies[1].explanation.evidence = farmerEvidence;

    // Update requested crop results based on target_crop_ids
    if (req.priorities.target_crop_ids.length > 0) {
      templatePlan.requested_crop_results = req.priorities.target_crop_ids.map((cid) => ({
        requested_crop_id: cid,
        outcome: req.priorities.excluded_crop_ids.includes(cid) ? "excluded" : "included",
        included_in_strategy_ids: ["S2_water_resilient", "S3_income_diversified"],
        replaced_by_crop_id: null,
        explanation: `Requested crop ${cid} evaluated against water (${field.water.availability}) and seasonal window.`,
        comparison: [],
        evidence: [],
      }));
    }

    return templatePlan;
  });

  base.data_quality = {
    completeness_score: base.field_plans[0].data_quality.completeness_score,
    confidence_note: base.field_plans[0].data_quality.confidence_note,
    missing_data: base.field_plans.flatMap((fp) =>
      fp.data_quality.missing_data.map((m) => `${fp.field_id}.${m}`)
    ),
    warnings: Array.from(new Set(fields.flatMap((f) => f.warnings.map((w) => w.code)))),
    limitations: base.field_plans[0].data_quality.limitations,
  };

  return base;
}

export async function handleFixtureRequest(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    headers?: Record<string, string>;
  }
): Promise<{ status: number; data: unknown; headers: Record<string, string> }> {
  const method = (options.method || "GET").toUpperCase();
  const headers = options.headers || {};
  const [pathname, rawQuery] = path.split("?");
  const query = new URLSearchParams(rawQuery || "");
  const reqId = headers["X-Request-Id"] || makeRequestId();

  const authHeader = headers["Authorization"] || "";
  const guestHeader = headers["X-Guest-Token"] || "";
  const isAuthenticated = authHeader.startsWith("Bearer ") && Boolean(fixtureState.accessToken);
  if (
    !isAuthenticated &&
    !fixtureState.guestToken &&
    !fixtureState.guestRevoked &&
    guestHeader === "gst_9b44f7c10a8e2130d5c89e4b"
  ) {
    fixtureState.guestToken = guestHeader;
    fixtureState.guestCreatedAt = "2026-11-14T10:00:00Z";
    fixtureState.guestExpiresAt = "2026-11-21T10:00:00Z";
    if (fixtureState.farms.size === 0) {
      fixtureState.seedDemoWorkspace();
    }
  }
  const isGuest = !isAuthenticated && Boolean(guestHeader) && Boolean(fixtureState.guestToken);

  const requireCaller = () => {
    if (!isAuthenticated && !isGuest) {
      throw new ApiClientError({
        status: 401,
        code: "UNAUTHORIZED",
        message: "Authentication or guest session token required.",
        details: [],
        requestId: reqId,
      });
    }
  };

  // System Health
  if (pathname === "/health" && method === "GET") {
    const res: HealthResponse = {
      status: fixtureState.simulateDegraded ? "degraded" : "ok",
      db: { connected: true, postgis_version: "3.4 USE_GEOS=1 USE_PROJ=1" },
      dataset: { active_version: "2026.11-guelma-v1", loaded_at: "2026-11-14T07:30:00Z" },
      catalog: { version: "2026.11", synced_at: "2026-11-14T08:00:00Z" },
      worker_queue: { active_workers: 2, pending_jobs: 0, stale_leases: 0 },
      ml_service: {
        reachable: !fixtureState.simulateDegraded,
        circuit_breaker: fixtureState.simulateDegraded ? "open" : "closed",
        consecutive_failures: fixtureState.simulateDegraded ? 3 : 0,
        ml_engine_version: "agro-ml-2.1.0",
      },
    };
    return { status: 200, data: res, headers: { "X-Request-Id": reqId } };
  }

  // Demo Locations & Boundary
  if (pathname === "/demo/locations" && method === "GET") {
    return {
      status: 200,
      data: { items: [GUELMA_DEMO_LOCATION], next_cursor: null, has_more: false },
      headers: { "X-Request-Id": reqId },
    };
  }

  if (pathname === "/demo/locations/1/boundary" && method === "GET") {
    const feature: BoundaryFeature = GUELMA_FALLBACK_BOUNDARY;
    return { status: 200, data: feature, headers: { "X-Request-Id": reqId } };
  }

  // Auth: Guest Start
  if (pathname === "/auth/guest" && method === "POST") {
    fixtureState.reset();
    fixtureState.guestToken = "gst_9b44f7c10a8e2130d5c89e4b";
    fixtureState.guestCreatedAt = "2026-11-14T10:00:00Z";
    fixtureState.guestExpiresAt = "2026-11-21T10:00:00Z";
    fixtureState.seedDemoWorkspace();

    const payload: GuestSessionStartResponse = {
      guest_token: fixtureState.guestToken,
      expires_at: fixtureState.guestExpiresAt,
      demo_location: GUELMA_DEMO_LOCATION,
      demo_parcel: {
        field_id: "F1",
        field_name: "Guelma Team Demo Parcel (Unstudied)",
        location: { latitude: 36.52, longitude: 7.52 },
        area_hectares: 12.5,
        is_unverified_demo_parcel: true,
        warnings: [DEMO_PARCEL_UNVERIFIED_WARNING],
      },
    };
    return { status: 201, data: payload, headers: { "X-Request-Id": reqId } };
  }

  if (pathname === "/demo/session") {
    if (!isGuest && !fixtureState.guestToken) {
      throw new ApiClientError({
        status: 401,
        code: "UNAUTHORIZED",
        message: "Guest token missing or expired.",
        details: [],
        requestId: reqId,
      });
    }
    if (method === "GET") {
      const firstFarm = fixtureState.farms.get("farm_1");
      const info: GuestSessionInfo = {
        demo_location: GUELMA_DEMO_LOCATION,
        demo_parcel: {
          field_id: "F1",
          field_name: "Guelma Team Demo Parcel (Unstudied)",
          location: { latitude: 36.52, longitude: 7.52 },
          area_hectares: 12.5,
          is_unverified_demo_parcel: true,
          warnings: [DEMO_PARCEL_UNVERIFIED_WARNING],
        },
        created_at: fixtureState.guestCreatedAt || "2026-11-14T10:00:00Z",
        expires_at: fixtureState.guestExpiresAt || "2026-11-21T10:00:00Z",
        limits: {
          max_farms: 3,
          max_fields_per_farm: 5,
          max_analyses: 10,
          max_analysis_quarters: 40,
        },
        usage: {
          farms: fixtureState.farms.size,
          fields: firstFarm ? firstFarm.field_count : 0,
          analysis_quarters: fixtureState.analysisQuartersUsed,
          analyses: Number((fixtureState.analysisQuartersUsed / 4).toFixed(2)),
        },
      };
      return { status: 200, data: info, headers: { "X-Request-Id": reqId } };
    }
    if (method === "DELETE") {
      fixtureState.reset();
      fixtureState.guestRevoked = true;
      return { status: 204, data: null, headers: { "X-Request-Id": reqId } };
    }
  }

  // Auth: Register / Login / Refresh / Logout / Me / Claim Guest
  if (pathname === "/auth/register" && method === "POST") {
    const body = options.body as { email: string; full_name: string; preferred_lang?: Language };
    const profile: UserProfile = {
      id: 101,
      email: body.email,
      full_name: body.full_name,
      preferred_lang: body.preferred_lang || "en",
      created_at: new Date().toISOString(),
    };
    fixtureState.user = profile;
    fixtureState.accessToken = "jwt_access_fixture_v1";
    fixtureState.refreshToken = "jwt_refresh_fixture_v1";
    if (fixtureState.farms.size === 0) {
      fixtureState.seedDemoWorkspace();
    }
    const res: RegisterResponse = {
      user: profile,
      access_token: fixtureState.accessToken,
      refresh_token: fixtureState.refreshToken,
      token_type: "bearer",
      expires_in: 900,
    };
    return { status: 201, data: res, headers: { "X-Request-Id": reqId } };
  }

  if (pathname === "/auth/login" && method === "POST") {
    const body = options.body as { email: string };
    if (!fixtureState.user) {
      fixtureState.user = {
        id: 101,
        email: body.email,
        full_name: "Guelma Agronomist",
        preferred_lang: "en",
        created_at: "2026-11-14T10:00:00Z",
      };
      if (fixtureState.farms.size === 0) {
        fixtureState.seedDemoWorkspace();
      }
    }
    fixtureState.accessToken = "jwt_access_fixture_v1";
    fixtureState.refreshToken = "jwt_refresh_fixture_v1";
    const pair: TokenPairResponse = {
      access_token: fixtureState.accessToken,
      refresh_token: fixtureState.refreshToken,
      token_type: "bearer",
      expires_in: 900,
    };
    return { status: 200, data: pair, headers: { "X-Request-Id": reqId } };
  }

  if (pathname === "/auth/refresh" && method === "POST") {
    fixtureState.accessToken = `jwt_access_rotated_${Date.now()}`;
    fixtureState.refreshToken = `jwt_refresh_rotated_${Date.now()}`;
    const pair: TokenPairResponse = {
      access_token: fixtureState.accessToken,
      refresh_token: fixtureState.refreshToken,
      token_type: "bearer",
      expires_in: 900,
    };
    return { status: 200, data: pair, headers: { "X-Request-Id": reqId } };
  }

  if (pathname === "/auth/logout" && method === "POST") {
    fixtureState.accessToken = null;
    fixtureState.refreshToken = null;
    return { status: 204, data: null, headers: { "X-Request-Id": reqId } };
  }

  if (pathname === "/auth/me") {
    if (!isAuthenticated || !fixtureState.user) {
      throw new ApiClientError({
        status: 401,
        code: "UNAUTHORIZED",
        message: "Bearer JWT required.",
        details: [],
        requestId: reqId,
      });
    }
    if (method === "GET") {
      return { status: 200, data: fixtureState.user, headers: { "X-Request-Id": reqId } };
    }
    if (method === "DELETE") {
      fixtureState.reset();
      fixtureState.guestRevoked = true;
      return { status: 204, data: null, headers: { "X-Request-Id": reqId } };
    }
  }

  if (pathname === "/auth/me/export" && method === "GET") {
    if (!isAuthenticated || !fixtureState.user) {
      throw new ApiClientError({
        status: 401,
        code: "UNAUTHORIZED",
        message: "Bearer JWT required.",
        details: [],
        requestId: reqId,
      });
    }
    const farms = Array.from(fixtureState.farms.values());
    const fields: FieldDetailPublic[] = [];
    for (const fMap of fixtureState.fieldsByFarm.values()) {
      fields.push(...fMap.values());
    }
    const exp: UserDataExport = {
      exported_at: new Date().toISOString(),
      user: fixtureState.user,
      farms,
      fields,
      analysis_requests: Array.from(fixtureState.analysesById.values()).map((a) => ({
        request_id: a.request_id,
        status: a.status,
      })),
      analysis_results: Array.from(fixtureState.analysesById.values()).map((a) => ({
        analysis_id: a.analysis_id,
        dataset_version: a.dataset_version,
      })),
      analysis_selections: Array.from(fixtureState.analysesById.values()).map((a) => ({
        analysis_id: a.analysis_id,
        selections: a.selections,
      })),
    };
    return { status: 200, data: exp, headers: { "X-Request-Id": reqId } };
  }

  if (pathname === "/auth/claim-guest" && method === "POST") {
    if (!authHeader.startsWith("Bearer ") || !guestHeader) {
      throw new ApiClientError({
        status: 401,
        code: "UNAUTHORIZED",
        message: "Both Authorization Bearer and X-Guest-Token headers are required to claim guest data.",
        details: [],
        requestId: reqId,
      });
    }
    const count = fixtureState.farms.size;
    fixtureState.guestToken = null;
    fixtureState.guestRevoked = true;
    return { status: 200, data: { claimed_farms_count: count }, headers: { "X-Request-Id": reqId } };
  }

  // Catalog
  if (pathname === "/catalog" && method === "GET") {
    requireCaller();
    const category = query.get("category");
    const role = query.get("role");
    let items = [...FIXTURE_CATALOG_ITEMS];
    if (category) items = items.filter((c) => c.category === category);
    if (role) items = items.filter((c) => c.roles.includes(role as CropItem["roles"][number]));

    const page: CatalogPage = {
      catalog_version: "2026.11",
      synced_at: "2026-11-14T08:00:00Z",
      items,
      next_cursor: null,
      has_more: false,
    };
    return { status: 200, data: page, headers: { "X-Request-Id": reqId } };
  }

  // Farms
  if (pathname === "/farms") {
    requireCaller();
    if (method === "GET") {
      return {
        status: 200,
        data: {
          items: Array.from(fixtureState.farms.values()),
          next_cursor: null,
          has_more: false,
        },
        headers: { "X-Request-Id": reqId },
      };
    }
    if (method === "POST") {
      if (isGuest && (fixtureState.farms.size >= 3 || fixtureState.simulateGuestLimit)) {
        throw new ApiClientError({
          status: 403,
          code: "GUEST_LIMIT_REACHED",
          message: "Guest limit reached: maximum 3 farms allowed in Guest Sandbox.",
          details: [{ limit: 3, current: fixtureState.farms.size }],
          requestId: reqId,
        });
      }
      const body = options.body as FarmWriteRequest;
      const farmId = `farm_${fixtureState.farmSeq++}`;
      const created: FarmPublic = {
        farm_id: farmId,
        farm_name: body.farm_name,
        country: body.country,
        region: body.region,
        commune: body.commune ?? null,
        field_count: 0,
        created_at: new Date().toISOString(),
      };
      fixtureState.farms.set(farmId, created);
      fixtureState.fieldsByFarm.set(farmId, new Map());
      return { status: 201, data: created, headers: { "X-Request-Id": reqId } };
    }
  }

  const farmMatch = pathname.match(/^\/farms\/(farm_[0-9]+)$/);
  if (farmMatch) {
    requireCaller();
    const farmId = farmMatch[1];
    const farm = fixtureState.farms.get(farmId);
    if (!farm) {
      throw new ApiClientError({
        status: 404,
        code: "NOT_FOUND",
        message: `Farm ${farmId} not found.`,
        details: [],
        requestId: reqId,
      });
    }
    if (method === "GET") return { status: 200, data: farm, headers: { "X-Request-Id": reqId } };
    if (method === "PUT" || method === "PATCH") {
      const patch = options.body as Partial<FarmWriteRequest>;
      const updated: FarmPublic = { ...farm, ...patch };
      fixtureState.farms.set(farmId, updated);
      return { status: 200, data: updated, headers: { "X-Request-Id": reqId } };
    }
    if (method === "DELETE") {
      fixtureState.farms.delete(farmId);
      fixtureState.fieldsByFarm.delete(farmId);
      return { status: 204, data: null, headers: { "X-Request-Id": reqId } };
    }
  }

  // Fields collection
  const fieldsMatch = pathname.match(/^\/farms\/(farm_[0-9]+)\/fields$/);
  if (fieldsMatch) {
    requireCaller();
    const farmId = fieldsMatch[1];
    const farm = fixtureState.farms.get(farmId);
    const fMap = fixtureState.fieldsByFarm.get(farmId);
    if (!farm || !fMap) {
      throw new ApiClientError({
        status: 404,
        code: "NOT_FOUND",
        message: `Farm ${farmId} not found.`,
        details: [],
        requestId: reqId,
      });
    }
    if (method === "GET") {
      const items: FieldPublic[] = Array.from(fMap.values()).map((f) => {
        const rest = { ...f };
        delete (rest as Partial<FieldDetailPublic>).crop_history;
        return rest;
      });
      return {
        status: 200,
        data: { items, next_cursor: null, has_more: false },
        headers: { "X-Request-Id": reqId },
      };
    }
    if (method === "POST") {
      if (isGuest && (fMap.size >= 5 || fixtureState.simulateGuestLimit)) {
        throw new ApiClientError({
          status: 403,
          code: "GUEST_LIMIT_REACHED",
          message: "Guest limit reached: maximum 5 fields per farm allowed.",
          details: [{ limit: 5, current: fMap.size }],
          requestId: reqId,
        });
      }
      const body = options.body as FieldWriteRequest;
      if (fMap.has(body.field_id)) {
        throw new ApiClientError({
          status: 409,
          code: "CONFLICT",
          message: `Field ID '${body.field_id}' already exists on farm ${farmId}.`,
          details: [{ field_id: body.field_id }],
          requestId: reqId,
        });
      }
      const warnings = computeFieldWarnings(body, isGuest);
      const detail: FieldDetailPublic = {
        farm_id: farmId,
        field_id: body.field_id,
        field_name: body.field_name,
        is_unverified_demo_parcel: Boolean(body.is_unverified_demo_parcel),
        location: {
          latitude: body.location.latitude,
          longitude: body.location.longitude,
          boundary: body.location.boundary ?? null,
        },
        area_hectares: body.area_hectares,
        elevation_m: body.elevation_m ?? null,
        soil: {
          soil_type: body.soil.soil_type,
          source: body.soil.soil_type === "unknown" ? "unknown" : "farmer",
          soil_ph: body.soil.soil_ph ?? null,
          organic_matter_percent: body.soil.organic_matter_percent ?? null,
          soil_test_date: body.soil.soil_test_date ?? null,
        },
        water: {
          availability: body.water.availability,
          source: body.water.source,
          source_other: body.water.source_other ?? null,
          irrigation_system: body.water.irrigation_system,
        },
        crop_history: body.crop_history,
        warnings,
      };
      fMap.set(body.field_id, detail);
      farm.field_count = fMap.size;
      const pub: FieldPublic = { ...detail };
      delete (pub as Partial<FieldDetailPublic>).crop_history;
      return { status: 201, data: pub, headers: { "X-Request-Id": reqId } };
    }
  }

  // Single Field
  const singleFieldMatch = pathname.match(/^\/farms\/(farm_[0-9]+)\/fields\/([^/]+)$/);
  if (singleFieldMatch) {
    requireCaller();
    const [, farmId, fieldId] = singleFieldMatch;
    const farm = fixtureState.farms.get(farmId);
    const fMap = fixtureState.fieldsByFarm.get(farmId);
    const existing = fMap?.get(fieldId);
    if (!farm || !fMap || !existing) {
      throw new ApiClientError({
        status: 404,
        code: "NOT_FOUND",
        message: `Field ${fieldId} not found on ${farmId}.`,
        details: [],
        requestId: reqId,
      });
    }
    if (method === "GET") {
      return { status: 200, data: existing, headers: { "X-Request-Id": reqId } };
    }
    if (method === "PUT" || method === "PATCH") {
      const body = options.body as FieldWriteRequest;
      const merged: FieldWriteRequest = {
        field_id: body.field_id || existing.field_id,
        field_name: body.field_name ?? existing.field_name,
        is_unverified_demo_parcel:
          body.is_unverified_demo_parcel ?? existing.is_unverified_demo_parcel,
        location: body.location ?? existing.location,
        area_hectares: body.area_hectares ?? existing.area_hectares,
        elevation_m: body.elevation_m !== undefined ? body.elevation_m : existing.elevation_m,
        soil: body.soil ?? existing.soil,
        water: body.water ?? existing.water,
        crop_history: body.crop_history ?? existing.crop_history,
      };
      const warnings = computeFieldWarnings(merged, isGuest);
      const updated: FieldDetailPublic = {
        farm_id: farmId,
        field_id: existing.field_id,
        field_name: merged.field_name,
        is_unverified_demo_parcel: Boolean(merged.is_unverified_demo_parcel),
        location: {
          latitude: merged.location.latitude,
          longitude: merged.location.longitude,
          boundary: merged.location.boundary ?? null,
        },
        area_hectares: merged.area_hectares,
        elevation_m: merged.elevation_m ?? null,
        soil: {
          soil_type: merged.soil.soil_type,
          source: merged.soil.soil_type === "unknown" ? "unknown" : "farmer",
          soil_ph: merged.soil.soil_ph ?? null,
          organic_matter_percent: merged.soil.organic_matter_percent ?? null,
          soil_test_date: merged.soil.soil_test_date ?? null,
        },
        water: {
          availability: merged.water.availability,
          source: merged.water.source,
          source_other: merged.water.source_other ?? null,
          irrigation_system: merged.water.irrigation_system,
        },
        crop_history: merged.crop_history,
        warnings,
      };
      fMap.set(existing.field_id, updated);
      return { status: 200, data: updated, headers: { "X-Request-Id": reqId } };
    }
    if (method === "DELETE") {
      fMap.delete(fieldId);
      farm.field_count = fMap.size;
      return { status: 204, data: null, headers: { "X-Request-Id": reqId } };
    }
  }

  // Farm Analyses History
  const farmAnalysesMatch = pathname.match(/^\/farms\/(farm_[0-9]+)\/analyses$/);
  if (farmAnalysesMatch && method === "GET") {
    requireCaller();
    const farmId = farmAnalysesMatch[1];
    const statusFilter = query.get("status");
    const items: FarmAnalysisSummary[] = Array.from(fixtureState.analysesById.values())
      .filter((a) => a.farm_id === farmId)
      .filter((a) => !statusFilter || a.status === statusFilter)
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
      .map((a) => ({
        request_id: a.request_id,
        analysis_id: a.analysis_id,
        status: a.status,
        language: a.language,
        catalog_version: a.catalog_version,
        dataset_version: a.dataset_version,
        ml_engine_version: a.ml_engine_version,
        warnings: a.warnings,
        created_at: a.created_at,
        duration_ms: a.duration_ms,
      }));
    const page: FarmAnalysesPage = { items, next_cursor: null, has_more: false };
    return { status: 200, data: page, headers: { "X-Request-Id": reqId } };
  }

  // Submit Analysis
  if (pathname === "/analysis" && method === "POST") {
    requireCaller();
    const body = options.body as AnalysisSubmitRequest;
    const fMap = fixtureState.fieldsByFarm.get(body.farm_id);
    if (!fMap) {
      throw new ApiClientError({
        status: 404,
        code: "NOT_FOUND",
        message: `Farm ${body.farm_id} not found.`,
        details: [],
        requestId: reqId,
      });
    }
    const targetFields = body.field_ids
      .map((fid) => fMap.get(fid))
      .filter((f): f is FieldDetailPublic => Boolean(f));
    if (targetFields.length !== body.field_ids.length) {
      throw new ApiClientError({
        status: 404,
        code: "NOT_FOUND",
        message: "One or more requested field_ids do not exist.",
        details: [],
        requestId: reqId,
      });
    }

    const validation = validateAnalysisPreSubmit({
      weights: body.priorities.weights,
      targetCropIds: body.priorities.target_crop_ids,
      excludedCropIds: body.priorities.excluded_crop_ids,
      startSeason: body.planning.start_season,
      plantingMonth: body.planning.planting_month,
      latitude: targetFields[0].location.latitude,
      cropHistory: targetFields[0].crop_history,
    });
    if (!validation.valid) {
      throw new ApiClientError({
        status: 400,
        code: "INVALID_INPUT",
        message: validation.errors[0],
        details: validation.errors.map((e) => ({ message: e })),
        requestId: reqId,
      });
    }

    const baseHash = `${body.farm_id}:${body.field_ids.join(",")}`;
    const hasMatchingBase = Array.from(fixtureState.analysesById.values()).some(
      (a) => a.input_hash === baseHash
    );
    const quarterCost = hasMatchingBase ? 1 : 4;
    if (isGuest && (fixtureState.analysisQuartersUsed + quarterCost > 40 || fixtureState.simulateGuestLimit)) {
      throw new ApiClientError({
        status: 403,
        code: "GUEST_LIMIT_REACHED",
        message:
          "Guest analysis quota reached (40 canonical quarters = 10 full analyses). Claim your session with a free account.",
        details: [{ used: fixtureState.analysisQuartersUsed, max: 40 }],
        requestId: reqId,
      });
    }

    const requestId = makeRequestId();
    const hexSuffix = (fixtureState.analysisSeq++).toString(16).padStart(12, "0");
    const analysisId = `analysis_${hexSuffix}`;
    const warnings = targetFields.flatMap((f) => f.warnings);
    const result = buildScenarioResult(body, requestId, targetFields);

    const record: FixtureAnalysisRecord = {
      analysis_id: analysisId,
      request_id: requestId,
      farm_id: body.farm_id,
      status: "pending",
      pollCount: 0,
      created_at: new Date().toISOString(),
      duration_ms: 950,
      language: body.language,
      catalog_version: "2026.11",
      dataset_version: "2026.11-guelma-v1",
      ml_engine_version: "agro-ml-2.1.0",
      warnings,
      degraded_mode: fixtureState.simulateDegraded
        ? {
            kind: "last_good_replay",
            stale: true,
            source_analysis_id: "analysis_4f9a8c120e3b",
            created_at: "2026-11-14T10:06:12Z",
            dataset_version: "2026.11-guelma-v1",
            age_seconds: 18420,
          }
        : null,
      result,
      selections: {},
      input_hash: baseHash,
    };

    if (isGuest) {
      fixtureState.analysisQuartersUsed += quarterCost;
    }

    fixtureState.analysesById.set(analysisId, record);
    fixtureState.analysesByRequestId.set(requestId, record);

    return {
      status: 202,
      data: {
        request_id: requestId,
        status: "pending",
        poll_url: `/api/v1/analysis/requests/${requestId}`,
        poll_interval_ms: 450,
        warnings,
      },
      headers: { "X-Request-Id": reqId },
    };
  }

  // Poll Analysis Request
  const pollMatch = pathname.match(/^\/analysis\/requests\/([^/]+)$/);
  if (pollMatch && method === "GET") {
    requireCaller();
    const requestId = pollMatch[1];
    const record = fixtureState.analysesByRequestId.get(requestId);
    if (!record) {
      throw new ApiClientError({
        status: 404,
        code: "NOT_FOUND",
        message: `Analysis request ${requestId} not found.`,
        details: [],
        requestId: reqId,
      });
    }
    if (record.status === "pending") {
      record.status = "running";
      record.pollCount = 1;
      const env: AnalysisPollEnvelope = {
        request_id: record.request_id,
        status: "running",
        poll_interval_ms: 450,
        analysis_id: null,
        warnings: record.warnings,
        degraded_mode: null,
        error: null,
        result: null,
      };
      return { status: 200, data: env, headers: { "X-Request-Id": reqId, "Retry-After": "1" } };
    }
    if (record.status === "running") {
      record.status = "ok";
      record.pollCount = 2;
    }
    const env: AnalysisPollEnvelope = {
      request_id: record.request_id,
      status: record.status,
      poll_interval_ms: null,
      analysis_id: record.status === "ok" || record.status === "partial" ? record.analysis_id : null,
      warnings: record.warnings,
      degraded_mode: record.degraded_mode,
      error: null,
      result: record.status === "ok" || record.status === "partial" ? formatResultWithSelections(record) : null,
    };
    return { status: 200, data: env, headers: { "X-Request-Id": reqId } };
  }

  // Cancel Analysis Request
  const cancelMatch = pathname.match(/^\/analysis\/requests\/([^/]+)\/cancel$/);
  if (cancelMatch && method === "POST") {
    requireCaller();
    const requestId = cancelMatch[1];
    const record = fixtureState.analysesByRequestId.get(requestId);
    if (!record) {
      throw new ApiClientError({
        status: 404,
        code: "NOT_FOUND",
        message: `Analysis request ${requestId} not found.`,
        details: [],
        requestId: reqId,
      });
    }
    if (record.status !== "pending" && record.status !== "running") {
      throw new ApiClientError({
        status: 409,
        code: "CONFLICT",
        message: `Cannot cancel request in status ${record.status}.`,
        details: [],
        requestId: reqId,
      });
    }
    record.status = "cancelled";
    return {
      status: 200,
      data: { request_id: record.request_id, status: "cancelled" },
      headers: { "X-Request-Id": reqId },
    };
  }

  // Selection Patch
  const selMatch = pathname.match(/^\/analysis\/(analysis_[0-9a-f]{12})\/selection$/);
  if (selMatch && method === "PATCH") {
    requireCaller();
    const analysisId = selMatch[1];
    const record = fixtureState.analysesById.get(analysisId);
    if (!record) {
      throw new ApiClientError({
        status: 404,
        code: "NOT_FOUND",
        message: `Analysis ${analysisId} not found.`,
        details: [],
        requestId: reqId,
      });
    }
    const body = options.body as {
      field_id: string;
      strategy_id: string;
      selection_status: "selected" | "rejected";
    };
    const fieldSel = (record.selections[body.field_id] = record.selections[body.field_id] || {});
    if (body.selection_status === "selected") {
      for (const sid of Object.keys(fieldSel)) {
        if (fieldSel[sid] === "selected") {
          fieldSel[sid] = "suggested";
        }
      }
    }
    fieldSel[body.strategy_id] = body.selection_status;
    const resp: SelectionPatchResponse = {
      analysis_id: analysisId,
      field_id: body.field_id,
      strategy_id: body.strategy_id,
      selection_status: body.selection_status,
    };
    return { status: 200, data: resp, headers: { "X-Request-Id": reqId } };
  }

  // Get Analysis Envelope
  const analysisMatch = pathname.match(/^\/analysis\/(analysis_[0-9a-f]{12})$/);
  if (analysisMatch && method === "GET") {
    requireCaller();
    const analysisId = analysisMatch[1];
    const record = fixtureState.analysesById.get(analysisId);
    if (!record) {
      throw new ApiClientError({
        status: 404,
        code: "NOT_FOUND",
        message: `Analysis ${analysisId} not found.`,
        details: [],
        requestId: reqId,
      });
    }
    const env: AnalysisEnvelope = {
      analysis_id: record.analysis_id,
      request_id: record.request_id,
      status: record.status === "partial" ? "partial" : "ok",
      dataset_version: record.dataset_version,
      warnings: record.warnings,
      degraded_mode:
        record.degraded_mode ??
        (fixtureState.simulateDegraded
          ? {
              kind: "last_good_replay",
              stale: true,
              source_analysis_id: "analysis_4f9a8c120e3b",
              created_at: "2026-11-14T10:06:12Z",
              dataset_version: "2026.11-guelma-v1",
              age_seconds: 18420,
            }
          : null),
      result: formatResultWithSelections(record),
    };
    return { status: 200, data: env, headers: { "X-Request-Id": reqId } };
  }

  throw new ApiClientError({
    status: 404,
    code: "NOT_FOUND",
    message: `Route ${method} ${pathname} not mocked in fixture transport.`,
    details: [],
    requestId: reqId,
  });
}
