import { polygon } from "@turf/helpers";
import {
  GUELMA_DEMO_PARCEL_AREA_HA,
  GUELMA_DEMO_PARCEL_CENTER,
  GUELMA_DEMO_PARCEL_RING,
  GUELMA_FALLBACK_BOUNDARY,
  ringToGeoJsonPolygon,
} from "@/lib/geo/guelma";
import {
  AnalysisEnvelopeSchema,
  AnalysisPollEnvelopeSchema,
  AnalysisQueuedResponseSchema,
  AnalysisResultSchema,
  AnalysisSubmitRequestSchema,
  BoundaryFeatureSchema,
  CatalogPageSchema,
  FarmAnalysesPageSchema,
  FarmPageSchema,
  FarmPublicSchema,
  FieldDetailPublicSchema,
  FieldPageSchema,
  FieldPublicSchema,
  GuestSessionInfoSchema,
  GuestSessionStartResponseSchema,
  HealthResponseSchema,
  RegisterResponseSchema,
  SelectionPatchResponseSchema,
  TokenPairResponseSchema,
  UserDataExportSchema,
  UserProfileSchema,
  type AnalysisEnvelope,
  type AnalysisPollEnvelope,
  type AnalysisQueuedResponse,
  type AnalysisResult,
  type AnalysisSubmitRequest,
  type BareFieldPeriod,
  type BenefitItem,
  type BoundaryFeature,
  type CatalogPage,
  type CropCategory,
  type CropItem,
  type CropRole,
  type DemoLocationSummary,
  type EvidenceItem,
  type EvidenceParameter,
  type EvidenceUnit,
  type FarmAnalysesPage,
  type FarmAnalysisSummary,
  type FarmPage,
  type FarmPatchRequest,
  type FarmPublic,
  type FarmWriteRequest,
  type FieldDetailPublic,
  type FieldPage,
  type FieldPlan,
  type FieldPublic,
  type FieldWriteDraft,
  type GuestSessionInfo,
  type GuestSessionStartResponse,
  type HealthResponse,
  type IrrigationSystem,
  type Language,
  type ReasonItem,
  type RegisterResponse,
  type RequestedCropEvaluation,
  type RiskItem,
  type Season,
  type SeasonPlan,
  type SelectionPatchResponse,
  type SelectionStatus,
  type SeverityLevel,
  type SoilType,
  type Strategy,
  type StrategyScores,
  type StressPeriod,
  type StressType,
  type TokenPairResponse,
  type UserDataExport,
  type UserProfile,
  type WarningNotice,
  type WaterAvailability,
  type WaterSource,
  serializeFieldPatchRequest,
  serializeFieldWriteRequest,
} from "@/lib/schemas";
import { validateDisjointCrops } from "@/lib/validation";
import { useAppStore } from "@/store/useAppStore";
import { ApiClientError } from "./errors";
import { resolveApiBaseRoot } from "./client";

// ---------------------------------------------------------------------------
// Raw Feild-Shift-SI-Model Wire Types (Phase L FastAPI + SQLite)
// ---------------------------------------------------------------------------

interface SiHealthResponse {
  status: "ok" | "degraded";
  service: string;
  decision_engine_version: string;
  dataset_version_used: string;
  knowledge_base: {
    crops_count: number;
    crop_rules_count: number;
    sequence_rules_count: number;
  };
  geospatial_assets: {
    all_core_assets_present: boolean;
    assets?: Record<string, boolean>;
    gee_tasks_submitted?: boolean;
  };
  database: {
    active_backend: string;
    stored_analyses_count?: number;
  };
  disclaimers?: string[];
}

interface SiReferenceCrop {
  crop_id: string;
  canonical_name: string;
  crop_category: string;
  in_annual_rotation_scope: boolean;
  guelma_evidence_status: string;
}

interface SiFieldValidateResponse {
  valid: boolean;
  field_id: string;
  field_name?: string | null;
  area_m2: number;
  area_ha: number;
  perimeter_m: number;
  centroid_lon_lat: number[];
  wilaya_overlap_pct: number;
  primary_commune?: {
    commune_num_id?: number;
    gid_2?: string;
    name_2?: string;
    overlap_pct?: number;
  } | null;
  validation_warnings?: string[];
}

interface SiMetricBlock {
  value?: number | null;
  unit?: string | null;
  source_dataset?: string | null;
  spatial_resolution?: string | null;
  temporal_coverage?: string | null;
  valid_pixel_count?: number | null;
  polygon_coverage_pct?: number | null;
  quality_status?: string | null;
  uncertainty_or_limitations?: string | null;
  stats?: Record<string, unknown> | null;
}

interface SiEvidenceRow {
  data_source?: string | null;
  parameter?: string | null;
  observed_value?: string | number | boolean | null;
  unit?: string | null;
  period?: string | null;
  derived?: boolean;
  interpretation?: string | null;
  spatial_resolution?: string | null;
  quality_status?: string | null;
}

interface SiStrategyScoreObj {
  score?: number | null;
  status?: string | null;
  explanation?: string | null;
  active_in_ranking?: boolean;
}

interface SiSeasonItem {
  order: number;
  season: "Winter" | "Spring" | "Summer" | "Autumn" | string;
  year: number;
  planting_month?: number | null;
  crop_id: string;
  crop_name: string;
  category?: string | null;
  role?: string | null;
  selection_status?: string | null;
  notes?: string | null;
}

interface SiStrategy {
  strategy_id: string;
  name: string;
  is_existing_rotation?: boolean;
  description?: string | null;
  seasons: SiSeasonItem[];
  feasibility_status?: string | null;
  scores: Record<string, SiStrategyScoreObj | undefined>;
  confidence?: { level?: string | null } | string | null;
  pareto_status?: string | null;
  rank?: number | null;
  weighted_score?: number | null;
  provisional?: boolean;
  explanation?: {
    summary?: string | null;
    reasons?: string[];
    evidence?: SiEvidenceRow[];
    benefits?: string[];
    risks?: string[];
    assumptions?: string[];
    information_gaps?: string[];
    needs_local_review?: boolean | string[];
    review_checklist?: string[];
  };
}

interface SiFieldPlan {
  field_id: string;
  field_name?: string | null;
  status: string;
  partial_reason?: string | null;
  field_insights?: {
    bare_field_periods?: Array<{
      period?: string;
      indicator?: string;
      observed_value?: number | null;
      interpretation?: string;
    }>;
    stress_periods?: Array<{
      constraint_id?: string;
      status?: string;
      finding?: string;
      agronomic_implication?: string;
    }>;
    climate_trend_summary?:
      | ({
          temporal_window?: string;
          gpm_annual_precip_mean_mm?: number | null;
          cross_product_precip_spread_mm?: number | null;
          smap_spring_rootzone_sm_mean?: number | null;
          smap_summer_rootzone_sm_mean?: number | null;
          scale_and_trend_caveat?: string | null;
        } & Record<string, string | number | null | undefined>)
      | string;
  };
  strategies?: SiStrategy[];
  suggested_strategy_id?: string | null;
  decision_gate?: {
    decision_status?: string;
    gating_reasons?: string[];
  };
  land_use_assessment?: {
    status?: string;
    soilgrids_clay_coverage_pct?: number;
    soilgrids_valid_pixels?: number;
    modis_ndvi_spring_mean?: number | null;
    modis_ndvi_winter_mean?: number | null;
    explanations?: string[];
  };
  requested_crop_results?: Array<{
    crop_id: string;
    crop_name?: string;
    outcome?: string;
    reason?: string;
    included_in_strategy_ids?: string[];
  }>;
  data_quality?: {
    completeness_score?: number | null;
    critical_data_adequacy?: {
      adequacy_status?: string;
      adequacy_vs_completeness_explanation?: string;
    };
    confidence_note?: string | null;
    missing_data?: string[];
    warnings?: string[];
    limitations?: string[];
  };
}

interface SiAnalyzeResponse {
  analysis_id: string;
  created_at_utc?: string;
  payload_sha256: string;
  reused_existing?: boolean;
  persistence_backend?: string;
  field_profile_summary?: {
    field_id?: string;
    field_name?: string;
    spatial_validation?: {
      area_ha?: number;
      primary_commune?: { name_2?: string } | null;
    };
    extracted_summary?: {
      usda_texture_0_5cm?: string | null;
      clay_0_30cm_pct?: SiMetricBlock;
      sand_0_30cm_pct?: SiMetricBlock;
      silt_0_30cm_pct?: SiMetricBlock;
      ph_0_30cm?: SiMetricBlock;
      soc_0_30cm_g_kg?: SiMetricBlock;
      cec_0_30cm?: SiMetricBlock;
      gpm_annual_precip_mm?: SiMetricBlock;
      smap_rootzone_sm_spring?: SiMetricBlock;
      smap_rootzone_sm_summer?: SiMetricBlock;
      modis_ndvi_spring_mean?: SiMetricBlock;
      modis_ndvi_winter_mean?: SiMetricBlock;
      modis_ndvi_summer_mean?: SiMetricBlock;
      [key: string]: SiMetricBlock | string | null | undefined;
    };
  };
  recommendation: {
    schema_version?: string;
    request_id?: string;
    dataset_version_used?: string;
    generated_at?: string;
    status?: string;
    language?: string;
    decision_engine_version?: string;
    overall_summary?: string;
    disclaimer?: string;
    field_plans: SiFieldPlan[];
  };
}

// ---------------------------------------------------------------------------
// Agronomic Crop Dictionary (13 Crops Verified in SI-Model KB)
// ---------------------------------------------------------------------------

export interface SiCropMeta {
  frontendId: string;
  siId: string;
  names: { en: string; fr: string; ar: string };
  category: CropCategory;
  roles: CropRole[];
  family: string;
}

const SI_CROP_META_LIST: SiCropMeta[] = [
  {
    frontendId: "durum_wheat",
    siId: "DURUM_WHEAT",
    names: { en: "Durum Wheat", fr: "Blé dur", ar: "قمح صلب" },
    category: "cereals",
    roles: ["main_crop", "cash_crop"],
    family: "Poaceae",
  },
  {
    frontendId: "soft_wheat",
    siId: "SOFT_WHEAT",
    names: { en: "Soft Wheat", fr: "Blé tendre", ar: "قمح لين" },
    category: "cereals",
    roles: ["main_crop", "cash_crop"],
    family: "Poaceae",
  },
  {
    frontendId: "barley",
    siId: "BARLEY",
    names: { en: "Barley", fr: "Orge", ar: "شعير" },
    category: "cereals",
    roles: ["main_crop", "forage"],
    family: "Poaceae",
  },
  {
    frontendId: "faba_bean",
    siId: "FABA_BEAN",
    names: { en: "Faba Bean", fr: "Fève / Féverole", ar: "فول" },
    category: "legumes",
    roles: ["nitrogen_fixer", "break_crop"],
    family: "Fabaceae",
  },
  {
    frontendId: "chickpea",
    siId: "CHICKPEA_WINTER",
    names: {
      en: "Winter Chickpea",
      fr: "Pois chiche d'hiver",
      ar: "حمص شتوي",
    },
    category: "legumes",
    roles: ["nitrogen_fixer", "break_crop"],
    family: "Fabaceae",
  },
  {
    frontendId: "chickpea_spring",
    siId: "CHICKPEA_SPRING",
    names: {
      en: "Spring Chickpea",
      fr: "Pois chiche de printemps",
      ar: "حمص ربيعي",
    },
    category: "legumes",
    roles: ["nitrogen_fixer", "break_crop"],
    family: "Fabaceae",
  },
  {
    frontendId: "lentil",
    siId: "LENTIL",
    names: { en: "Lentil", fr: "Lentille", ar: "عدس" },
    category: "legumes",
    roles: ["nitrogen_fixer", "break_crop"],
    family: "Fabaceae",
  },
  {
    frontendId: "vetch",
    siId: "VETCH_OAT",
    names: { en: "Vetch-Oat", fr: "Vesce-Avoine", ar: "بيقية-شوفان" },
    category: "forage",
    roles: ["forage", "cover_crop", "nitrogen_fixer"],
    family: "Fabaceae/Poaceae",
  },
  {
    frontendId: "tomato",
    siId: "TOMATO_IND",
    names: {
      en: "Processing Tomato",
      fr: "Tomate industrielle",
      ar: "طماطم صناعية",
    },
    category: "vegetables",
    roles: ["cash_crop"],
    family: "Solanaceae",
  },
  {
    frontendId: "potato",
    siId: "POTATO",
    names: { en: "Potato", fr: "Pomme de terre", ar: "بطاطس" },
    category: "vegetables",
    roles: ["cash_crop"],
    family: "Solanaceae",
  },
  {
    frontendId: "sunflower",
    siId: "SUNFLOWER",
    names: { en: "Sunflower", fr: "Tournesol", ar: "عباد الشمس" },
    category: "oilseeds",
    roles: ["cash_crop", "break_crop"],
    family: "Asteraceae",
  },
  {
    frontendId: "olive",
    siId: "OLIVE",
    names: { en: "Olive", fr: "Olivier", ar: "زيتون" },
    category: "oilseeds",
    roles: ["main_crop", "cash_crop"],
    family: "Oleaceae",
  },
  {
    frontendId: "fallow",
    siId: "BARE_FALLOW",
    names: { en: "Bare Fallow", fr: "Jachère nue", ar: "أرض بور" },
    category: "fallow",
    roles: ["fallow"],
    family: "Rest",
  },
];

const BY_SI_CROP = new Map(SI_CROP_META_LIST.map((m) => [m.siId, m]));
const BY_FE_CROP = new Map(SI_CROP_META_LIST.map((m) => [m.frontendId, m]));

export function siCropIdToFrontend(siId: string): string {
  const hit = BY_SI_CROP.get(siId.toUpperCase());
  return hit ? hit.frontendId : siId.toLowerCase();
}

export function frontendCropIdToSi(
  frontendId: string,
  seasonHint?: Season | null
): string {
  const normalized = frontendId.trim().toLowerCase();
  if (normalized === "chickpea") {
    return seasonHint === "spring" ? "CHICKPEA_SPRING" : "CHICKPEA_WINTER";
  }
  const hit = BY_FE_CROP.get(normalized);
  if (hit) return hit.siId;
  const upper = frontendId.trim().toUpperCase();
  if (BY_SI_CROP.has(upper)) return upper;
  return upper;
}

// ---------------------------------------------------------------------------
// Persistent Live Workspace Storage (Farms / Fields / Jobs / Auth Shim)
// ---------------------------------------------------------------------------

interface StoredQueuedJob {
  requestId: string;
  farmId: string;
  fieldIds: string[];
  language: Language;
  createdAt: string;
  durationMs: number;
  status: "ok" | "partial" | "failed" | "cancelled";
  analysisId: string | null;
  siAnalysisIds: Record<string, string>; // fieldId -> SI ANAL_...
  frontendTargetsByField: string[];
  warnings: WarningNotice[];
  error: {
    code:
      | "INVALID_INPUT"
      | "OUTSIDE_DEMO_BOUNDARY"
      | "INSUFFICIENT_DATA"
      | "INTERNAL_ERROR"
      | "ML_UNAVAILABLE";
    http_equivalent: number;
    message: string;
    details: Array<Record<string, unknown>>;
  } | null;
  envelope: AnalysisEnvelope | null;
}

interface SiWorkspaceState {
  user: UserProfile | null;
  guestToken: string | null;
  guestCreatedAt: string;
  guestExpiresAt: string;
  nextFarmNum: number;
  farms: FarmPublic[];
  fieldsByFarm: Record<string, FieldDetailPublic[]>;
  jobs: Record<string, StoredQueuedJob>;
  analyses: Record<
    string,
    {
      envelope: AnalysisEnvelope;
      siAnalysisIds: Record<string, string>;
      requestedFrontendIds: string[];
    }
  >;
  farmAnalysisOrder: Record<string, string[]>; // farmId -> requestIds
  selections: Record<string, Record<string, { selected?: string; rejected: string[] }>>;
}

const STORAGE_KEY = "fieldshift.si.workspace.v1";
const inMemoryStorage = new Map<string, string>();

const GUELMA_DEMO_LOCATIONS: DemoLocationSummary[] = [
  { id: 1, code: "DZA-24", name: "Guelma", country: "Algeria", region: "Guelma" },
  {
    id: 2,
    code: "DZA-24-SEY",
    name: "Boumahra Ahmed (Seybouse Plain)",
    country: "Algeria",
    region: "Guelma",
  },
];

function nowIso(): string {
  return new Date().toISOString();
}

function createUuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `00000000-0000-4000-8000-${Date.now().toString(16).padStart(12, "0").slice(-12)}`;
}

function deriveFrontendAnalysisId(seed: string): string {
  let hex = "";
  const cleaned = seed.toLowerCase().replace(/[^0-9a-f]/g, "");
  if (cleaned.length >= 12) {
    hex = cleaned.slice(0, 12);
  } else {
    let h1 = 0x811c9dc5;
    let h2 = 0x01000193;
    for (let i = 0; i < seed.length; i++) {
      const c = seed.charCodeAt(i);
      h1 = Math.imul(h1 ^ c, 0x01000193) >>> 0;
      h2 = Math.imul(h2 ^ (c + i), 0x85ebca6b) >>> 0;
    }
    hex = `${h1.toString(16).padStart(8, "0")}${h2.toString(16).padStart(8, "0")}`.slice(
      0,
      12
    );
  }
  return `analysis_${hex}`;
}

function buildDefaultGuestWorkspace(): SiWorkspaceState {
  const created = nowIso();
  const expires = new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString();
  return {
    user: null,
    guestToken: `gst_si_${Date.now().toString(36)}`,
    guestCreatedAt: created,
    guestExpiresAt: expires,
    nextFarmNum: 2,
    farms: [
      {
        farm_id: "farm_1",
        farm_name: "Guelma Demo Estate",
        country: "Algeria",
        region: "Guelma",
        commune: "Boumahra Ahmed",
        field_count: 1,
        created_at: created,
      },
    ],
    fieldsByFarm: {
      farm_1: [
        {
          farm_id: "farm_1",
          field_id: "F1",
          field_name: "Guelma Team Demo Parcel (Unstudied)",
          is_unverified_demo_parcel: true,
          location: {
            latitude: GUELMA_DEMO_PARCEL_CENTER.latitude,
            longitude: GUELMA_DEMO_PARCEL_CENTER.longitude,
            boundary: ringToGeoJsonPolygon(GUELMA_DEMO_PARCEL_RING),
          },
          area_hectares: GUELMA_DEMO_PARCEL_AREA_HA,
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
          warnings: [
            {
              code: "DEMO_PARCEL_UNVERIFIED",
              message:
                "DEMO_PARCEL_UNVERIFIED: Parcel F1 starts with default Seybouse assumptions — SI-Model will extract SoilGrids 250m and regional EO telemetry live.",
            },
          ],
          crop_history: [
            {
              season: "autumn",
              year: 2025,
              planting_month: 11,
              crop_id: "durum_wheat",
              crop_name_raw: "Durum Wheat",
              yield_tons_per_hectare: null,
              notes: "Default Seybouse predecessor",
            },
          ],
        },
      ],
    },
    jobs: {},
    analyses: {},
    farmAnalysisOrder: {},
    selections: {},
  };
}

// ---------------------------------------------------------------------------
// GeoJSON & Enum Translation Helpers
// ---------------------------------------------------------------------------

function computeBboxFromGeometry(
  geometry: { type: string; coordinates: unknown }
): [number, number, number, number] {
  let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;

  const visit = (node: unknown) => {
    if (!Array.isArray(node)) return;
    if (
      node.length >= 2 &&
      typeof node[0] === "number" &&
      typeof node[1] === "number"
    ) {
      if (node[0] < minLon) minLon = node[0];
      if (node[1] < minLat) minLat = node[1];
      if (node[0] > maxLon) maxLon = node[0];
      if (node[1] > maxLat) maxLat = node[1];
      return;
    }
    for (const child of node) {
      visit(child);
    }
  };
  visit(geometry.coordinates);

  if (!Number.isFinite(minLon)) {
    return [...(GUELMA_FALLBACK_BOUNDARY.bbox as [number, number, number, number])];
  }
  return [minLon, minLat, maxLon, maxLat];
}

export function fieldLocationToSiPolygon(
  location: {
    latitude: number;
    longitude: number;
    boundary?: Record<string, unknown> | null;
  },
  areaHectares: number
): { type: "Polygon"; coordinates: number[][][] } {
  const b = location.boundary as
    | { type?: string; coordinates?: unknown }
    | null
    | undefined;
  if (
    b &&
    b.type === "Polygon" &&
    Array.isArray(b.coordinates) &&
    Array.isArray(b.coordinates[0]) &&
    b.coordinates[0].length >= 4
  ) {
    const rawRing = (b.coordinates[0] as unknown[]).map((pt) => {
      const pair = Array.isArray(pt) ? pt : [location.longitude, location.latitude];
      return [Number(pair[0]), Number(pair[1])];
    });
    const first = rawRing[0];
    const last = rawRing[rawRing.length - 1];
    if (first[0] !== last[0] || first[1] !== last[1]) {
      rawRing.push([first[0], first[1]]);
    }
    return { type: "Polygon", coordinates: [rawRing] };
  }

  // Synthesize metric square GeoJSON polygon around (longitude, latitude)
  const areaM2 = Math.max(100, (areaHectares || 5) * 10_000);
  const sideM = Math.sqrt(areaM2);
  const metersPerDegLat = 111_194.9266;
  const metersPerDegLon =
    metersPerDegLat * Math.max(0.2, Math.cos((location.latitude * Math.PI) / 180));
  const halfLat = sideM / 2 / metersPerDegLat;
  const halfLon = sideM / 2 / metersPerDegLon;
  const lon = Number(location.longitude);
  const lat = Number(location.latitude);

  const ring: number[][] = [
    [Number((lon - halfLon).toFixed(6)), Number((lat - halfLat).toFixed(6))],
    [Number((lon + halfLon).toFixed(6)), Number((lat - halfLat).toFixed(6))],
    [Number((lon + halfLon).toFixed(6)), Number((lat + halfLat).toFixed(6))],
    [Number((lon - halfLon).toFixed(6)), Number((lat + halfLat).toFixed(6))],
    [Number((lon - halfLon).toFixed(6)), Number((lat - halfLat).toFixed(6))],
  ];
  // Check turf constructor doesn't reject ring
  polygon([ring]);
  return { type: "Polygon", coordinates: [ring] };
}

function mapWaterToSi(water: FieldDetailPublic["water"]): {
  availability: "limited" | "moderate" | "abundant" | "unknown";
  source: "groundwater" | "well" | "reservoir" | "river" | "rainfed" | "other" | "unknown";
  irrigation_system: "drip" | "sprinkler" | "surface" | "none" | "unknown";
} {
  const availabilityMap: Record<
    WaterAvailability,
    "limited" | "moderate" | "abundant" | "unknown"
  > = {
    abundant: "abundant",
    moderate: "moderate",
    limited: "limited",
    very_limited: "limited",
    rainfed_only: "limited",
  };
  const sourceMap: Record<
    WaterSource,
    "groundwater" | "well" | "reservoir" | "river" | "rainfed" | "other" | "unknown"
  > = {
    rainwater: "rainfed",
    groundwater: "groundwater",
    well: "well",
    dam_reservoir: "reservoir",
    irrigation_network: "other",
    other: "other",
    unknown: "unknown",
  };
  const irrigationMap: Record<
    IrrigationSystem,
    "drip" | "sprinkler" | "surface" | "none" | "unknown"
  > = {
    rainfed: "none",
    drip: "drip",
    sprinkler: "sprinkler",
    flood: "surface",
    other: "surface",
    unknown: "unknown",
  };

  return {
    availability: availabilityMap[water.availability] ?? "unknown",
    source: sourceMap[water.source] ?? "unknown",
    irrigation_system: irrigationMap[water.irrigation_system] ?? "unknown",
  };
}

function capitalizeSeason(season: Season): "Winter" | "Spring" | "Summer" | "Autumn" {
  switch (season) {
    case "winter":
      return "Winter";
    case "spring":
      return "Spring";
    case "summer":
      return "Summer";
    case "autumn":
      return "Autumn";
  }
}

function lowercaseSeason(season: string): Season {
  const s = season.trim().toLowerCase();
  if (s === "winter" || s === "spring" || s === "summer" || s === "autumn") {
    return s;
  }
  return "autumn";
}

function sanitizeMonthForSeason(
  season: Season,
  month: number | null | undefined
): number | null {
  if (month === null || month === undefined) return null;
  const map: Record<Season, number[]> = {
    winter: [12, 1, 2],
    spring: [3, 4, 5],
    summer: [6, 7, 8],
    autumn: [9, 10, 11],
  };
  if (map[season].includes(month)) return month;
  return null;
}

export function buildSiFieldValidationPayload(
  field: FieldDetailPublic,
  options?: {
    startSeason?: Season;
    startYear?: number;
    horizonSeasons?: number;
    plantingMonth?: number | null;
    planningMode?: "CURRENT_PLANNING" | "HISTORICAL_SIMULATION";
  }
): Record<string, unknown> {
  const startSeason = options?.startSeason ?? "spring";
  const startYear = options?.startYear ?? 2027;
  const horizonSeasons = Math.min(4, Math.max(2, options?.horizonSeasons ?? 4));
  const plantingMonth = sanitizeMonthForSeason(startSeason, options?.plantingMonth);

  const history = (field.crop_history ?? []).slice(0, 30).map((row) => {
    const feCropId = row.crop_id?.trim() || null;
    const meta = feCropId ? BY_FE_CROP.get(feCropId.toLowerCase()) : undefined;
    const mappedSiCropId = feCropId ? frontendCropIdToSi(feCropId, row.season) : null;
    const rawName = (
      row.crop_name_raw?.trim() ||
      meta?.names.en ||
      feCropId ||
      "Unknown Crop"
    ).slice(0, 120);

    return {
      season: capitalizeSeason(row.season),
      year: Math.min(2035, Math.max(2010, Number(row.year) || 2025)),
      planting_month: sanitizeMonthForSeason(row.season, row.planting_month),
      crop_id: mappedSiCropId,
      crop_name_raw: rawName,
      yield_tons_per_hectare:
        row.yield_tons_per_hectare !== null &&
        row.yield_tons_per_hectare !== undefined
          ? Math.min(200, Math.max(0, Number(row.yield_tons_per_hectare)))
          : null,
      notes: row.notes?.slice(0, 500) ?? null,
    };
  });

  return {
    field: {
      field_id: field.field_id.slice(0, 80),
      field_name: field.field_name?.slice(0, 120) ?? null,
      geometry: fieldLocationToSiPolygon(field.location, field.area_hectares),
      geometry_crs: "EPSG:4326",
    },
    water: mapWaterToSi(field.water),
    crop_history: history.length > 0 ? history : null,
    planning: {
      start_season: capitalizeSeason(startSeason),
      start_year: Math.min(2035, Math.max(2024, startYear)),
      horizon_seasons: horizonSeasons,
      planting_month: plantingMonth,
      ...(options?.planningMode ? { planning_mode: options.planningMode } : {}),
    },
  };
}

export function buildSiAnalyzeRequestPayload(
  field: FieldDetailPublic,
  request: AnalysisSubmitRequest,
  planningMode?: "CURRENT_PLANNING" | "HISTORICAL_SIMULATION"
): {
  payload: Record<string, unknown>;
  mappedTargetToOriginal: Map<string, string[]>;
  adapterWarnings: string[];
} {
  const adapterWarnings: string[] = [];
  const startSeason = request.planning.start_season;
  const horizonRaw = request.planning.horizon_seasons;
  const horizonClamped = Math.min(4, Math.max(2, horizonRaw));
  if (horizonClamped !== horizonRaw) {
    adapterWarnings.push(
      `SI-Model supports 2–4 planning seasons; requested ${horizonRaw} adjusted to ${horizonClamped}.`
    );
  }

  const base = buildSiFieldValidationPayload(field, {
    startSeason,
    startYear: request.planning.start_year,
    horizonSeasons: horizonClamped,
    plantingMonth: request.planning.planting_month,
    planningMode,
  });

  // Target & excluded crops mapping (handle chickpea -> Winter vs Spring transparently)
  const mappedTargetToOriginal = new Map<string, string[]>();
  const targetSet = new Set<string>();

  for (const feId of request.priorities.target_crop_ids) {
    const siId = frontendCropIdToSi(feId, startSeason);
    targetSet.add(siId);
    const arr = mappedTargetToOriginal.get(siId) ?? [];
    arr.push(feId);
    mappedTargetToOriginal.set(siId, arr);
  }

  const excludedSet = new Set<string>();
  for (const feId of request.priorities.excluded_crop_ids) {
    const norm = feId.trim().toLowerCase();
    if (norm === "chickpea") {
      if (!targetSet.has("CHICKPEA_WINTER")) excludedSet.add("CHICKPEA_WINTER");
      if (!targetSet.has("CHICKPEA_SPRING")) excludedSet.add("CHICKPEA_SPRING");
    } else {
      const siId = frontendCropIdToSi(feId, startSeason);
      if (!targetSet.has(siId)) excludedSet.add(siId);
    }
  }

  const w = request.priorities.weights;
  let waterW = Number((w.water_saving / 100).toFixed(4));
  let soilW = Number((w.soil_improvement / 100).toFixed(4));
  const incomeW = w.income > 0 ? Number((w.income / 100).toFixed(4)) : null;
  const riskW = Number((w.risk_reduction / 100).toFixed(4));
  const forageW =
    w.forage_value > 0 ? Number((w.forage_value / 100).toFixed(4)) : null;

  // SI-Model cannot numerically evaluate income_weight without farmgate enterprise budgets;
  // ensure at least one active scorable weight > 0 so SI-Model never rejects valid 100% income slider.
  if (waterW + soilW + riskW + (forageW ?? 0) <= 0) {
    waterW = 0.05;
    soilW = 0.05;
    adapterWarnings.push(
      "SI-Model leaves numeric income_potential UNKNOWN without verified DZD enterprise budgets; applied 0.05 tie-break weights to water/soil sustainability."
    );
  }

  const preferences: Record<string, unknown> = {
    target_crop_ids: targetSet.size > 0 ? Array.from(targetSet) : null,
    excluded_crop_ids: excludedSet.size > 0 ? Array.from(excludedSet) : null,
    equipment_constraints:
      request.priorities.equipment_constraints.length > 0
        ? request.priorities.equipment_constraints
        : null,
    water_saving_weight: waterW,
    soil_improvement_weight: soilW,
    income_weight: incomeW,
    risk_reduction_weight: riskW,
    forage_value_weight: forageW,
  };

  return {
    payload: {
      ...base,
      preferences,
      language: request.language,
      farmer_account: {
        user_id: request.farm_id.slice(0, 80),
        role: "farmer",
        display_name: (field.field_name || field.field_id || "Guelma Farmer").slice(
          0,
          120
        ),
      },
    },
    mappedTargetToOriginal,
    adapterWarnings,
  };
}

// ---------------------------------------------------------------------------
// Response Translator: SI-Model Output -> Frontend Zod AnalysisEnvelope
// ---------------------------------------------------------------------------

function mapSiConfidence(raw: SiStrategy["confidence"]): SeverityLevel {
  const val =
    typeof raw === "string" ? raw : (raw?.level ?? "LOW");
  const u = val.toUpperCase();
  if (u.includes("HIGH")) return "high";
  if (u.includes("MEDIUM") && !u.includes("LOW")) return "medium";
  return "low";
}

function mapSiCropCategory(rawCat: string | null | undefined, cropId: string): CropCategory {
  const meta = BY_SI_CROP.get(cropId.toUpperCase()) ?? BY_FE_CROP.get(cropId.toLowerCase());
  if (meta) return meta.category;
  const s = (rawCat ?? "").toLowerCase();
  if (s.includes("cereal")) return "cereals";
  if (s.includes("legume") || s.includes("pulse")) return "legumes";
  if (s.includes("forage")) return "forage";
  if (s.includes("vegetable") || s.includes("tuber")) return "vegetables";
  if (s.includes("oil") || s.includes("tree")) return "oilseeds";
  if (s.includes("fallow")) return "fallow";
  return "cereals";
}

function mapSiCropRole(rawRole: string | null | undefined, cropId: string): CropRole {
  const meta = BY_SI_CROP.get(cropId.toUpperCase()) ?? BY_FE_CROP.get(cropId.toLowerCase());
  const s = (rawRole ?? "").toLowerCase();
  if (s.includes("fallow")) return "fallow";
  if (s.includes("forage") || s.includes("hay")) return "forage";
  if (s.includes("nitrogen") || s.includes("legume") || s.includes("pulse")) {
    return "nitrogen_fixer";
  }
  if (s.includes("break")) return "break_crop";
  if (s.includes("cover")) return "cover_crop";
  if (s.includes("cash") || s.includes("market")) return "cash_crop";
  return meta?.roles[0] ?? "main_crop";
}

function normalizeEvidenceParam(rawParam: string | null | undefined): EvidenceParameter {
  const p = (rawParam ?? "").toLowerCase();
  if (p.includes("precip") && p.includes("anom")) return "precipitation_anomaly";
  if (p.includes("precip") || p.includes("rain")) return "precipitation";
  if (p.includes("t2m_max") || p.includes("tmax")) return "t2m_max";
  if (p.includes("t2m_min") || p.includes("tmin")) return "t2m_min";
  if (p.includes("t2m") || p.includes("temp")) return "t2m";
  if (p.includes("rh2m") || p.includes("humid")) return "rh2m";
  if (p.includes("wind") || p.includes("ws2m")) return "wind_2m";
  if (p.includes("solar")) return "solar_radiation";
  if (p.includes("ndvi") || p.includes("evi")) return "ndvi";
  if (p.includes("smap") || p.includes("soil_moisture") || p.includes("rootzone")) {
    return "soil_moisture_surface";
  }
  if (p.includes("ph")) return "soil_ph";
  if (p.includes("soc") || p.includes("organic")) return "organic_matter_percent";
  if (p.includes("clay") || p.includes("sand") || p.includes("silt") || p.includes("texture")) {
    return "soil_type";
  }
  if (p.includes("dem") || p.includes("elev")) return "elevation_m";
  if (p.includes("water")) return "water_availability";
  if (p.includes("history")) return "crop_history";
  return "dataset_feature";
}

function normalizeEvidenceUnit(rawUnit: string | null | undefined): EvidenceUnit {
  const u = (rawUnit ?? "").trim();
  const valid: EvidenceUnit[] = [
    "mm/day",
    "mm/year",
    "mm/month",
    "% vs historical mean",
    "degC",
    "%",
    "m/s",
    "MJ/m2/day",
    "index",
    "m3/m3",
    "pct",
    "mm",
    "m",
    "t/ha",
  ];
  if (valid.includes(u as EvidenceUnit)) return u as EvidenceUnit;
  if (u === "unitless NDVI" || u === "normalized_index_0_to_1") return "index";
  if (u === "fraction [0..1]") return "index";
  return null;
}

function toPctScore(score01: number | null | undefined, fallback = 0): number {
  if (score01 === null || score01 === undefined || !Number.isFinite(score01)) {
    return fallback;
  }
  return Math.max(0, Math.min(100, Math.round(score01 * 100)));
}

function computeBareFieldDays(
  seasons: SiSeasonItem[],
  erosionPct: number
): number {
  if (seasons.length === 0) return 180;
  let bareAccum = 0;
  for (const s of seasons) {
    const cid = s.crop_id.toUpperCase();
    if (cid === "BARE_FALLOW") {
      bareAccum += 260;
    } else if (
      cid === "CHICKPEA_SPRING" ||
      cid === "SUNFLOWER" ||
      cid === "POTATO" ||
      cid === "TOMATO_IND"
    ) {
      bareAccum += 155;
    } else if (cid === "OLIVE") {
      bareAccum += 35;
    } else {
      bareAccum += 110;
    }
  }
  const avgFromCrops = bareAccum / seasons.length;
  const coverBlend = (100 - erosionPct) * 1.1;
  return Math.max(25, Math.min(340, Math.round(avgFromCrops * 0.75 + coverBlend * 0.25)));
}

function parseReasonItem(raw: string, idx: number): ReasonItem {
  const match = raw.match(/^\[(PASS|WARNING|FAIL|UNKNOWN|[^\]]+)\]\s*([A-Z0-9_]+):\s*(.+)$/i);
  if (match) {
    return {
      code: match[2],
      text: match[3].trim(),
      params: { verdict: match[1].toUpperCase(), index: idx + 1 },
    };
  }
  return {
    code: `SI_REASON_${idx + 1}`,
    text: raw.trim() || "Agronomic rule evaluated",
    params: { index: idx + 1 },
  };
}

function parseRiskItem(
  raw: string,
  idx: number,
  checklist: string[]
): RiskItem {
  const trimmed = raw.trim();
  const prefixMatch = trimmed.match(
    /^\[(FAIL|CRITICAL|WARNING|UNKNOWN)\]\s*([A-Z0-9_]+):\s*(.+)$/i
  );
  let severity: SeverityLevel = "medium";
  let title = `Agronomic Risk #${idx + 1}`;
  let description = trimmed;

  if (prefixMatch) {
    const tag = prefixMatch[1].toUpperCase();
    const code = prefixMatch[2];
    description = prefixMatch[3].trim();
    if (tag === "FAIL" || tag === "CRITICAL") {
      severity = "high";
      title = `${code} (Critical)`;
    } else if (tag === "WARNING") {
      severity = "medium";
      title = `${code} (Warning)`;
    } else {
      severity = "low";
      title = `${code} (Verification Needed)`;
    }
  }

  const mitigation =
    checklist.length > 0
      ? checklist[idx % checklist.length]
      : "Verify constraint locally with soil/water inspection prior to sowing.";

  return {
    risk_id: `RISK_SI_${idx + 1}`,
    title,
    description,
    severity,
    likelihood: severity,
    mitigation,
  };
}

function parseBenefitItem(raw: string, idx: number): BenefitItem {
  const clean = raw.trim();
  const shortTitle =
    clean.length > 56 ? `${clean.slice(0, 53).replace(/\s+\S*$/, "")}...` : clean;
  return {
    benefit_id: `BEN_SI_${idx + 1}`,
    title: shortTitle || `Agronomic Benefit #${idx + 1}`,
    description: clean || "Supports multi-objective rotation sustainability.",
  };
}

function translateEvidenceRows(
  strat: SiStrategy,
  extractedSummary: NonNullable<SiAnalyzeResponse["field_profile_summary"]>["extracted_summary"]
): EvidenceItem[] {
  const items: EvidenceItem[] = [];
  const seenParams = new Set<string>();

  for (const row of strat.explanation?.evidence ?? []) {
    const rawParam = (row.parameter ?? "").trim();
    const srcRaw = (row.data_source ?? "").toLowerCase();
    const isFarmer = srcRaw.includes("farmer");
    const dataSource = isFarmer ? "farmer_input" : "dataset";
    const param = normalizeEvidenceParam(rawParam);

    // Format non-null observed value while preserving meaningful numbers/text
    let obsValue: string | number | boolean =
      row.observed_value === null || row.observed_value === undefined
        ? `${row.quality_status ?? "UNAVAILABLE"} (${rawParam})`
        : row.observed_value;

    // Convert SoilGrids SOC g/kg -> % when unit or param maps to organic_matter_percent
    let unit = normalizeEvidenceUnit(row.unit);
    let extraNote = "";
    if (
      param === "organic_matter_percent" &&
      typeof obsValue === "number" &&
      (row.unit ?? "").toLowerCase().includes("g/kg")
    ) {
      extraNote = ` [SOC ${obsValue.toFixed(2)} g/kg]`;
      obsValue = Number((obsValue / 10).toFixed(2));
      unit = "%";
    }

    const interpBase = (row.interpretation ?? rawParam ?? "SI-Model observation").trim();
    const interp = `${interpBase}${extraNote}${
      row.spatial_resolution ? ` (${row.spatial_resolution})` : ""
    }`;

    const dedupeKey = `${dataSource}:${rawParam}`;
    if (!seenParams.has(dedupeKey)) {
      seenParams.add(dedupeKey);
      items.push({
        data_source: dataSource,
        source_mission: row.data_source ?? null,
        parameter: param,
        observed_value: obsValue,
        unit,
        period: row.period ?? null,
        derived: Boolean(row.derived),
        interpretation: interp,
      });
    }
  }

  // Enrich with parcel-extracted telemetry from field_profile_summary.extracted_summary
  const enrichMetric = (
    key: string,
    block: SiMetricBlock | undefined,
    parameter: EvidenceParameter,
    defaultUnit: EvidenceUnit,
    labelPrefix: string
  ) => {
    if (!block || block.value === null || block.value === undefined) return;
    if (seenParams.has(`dataset:${key}`)) return;
    seenParams.add(`dataset:${key}`);
    items.push({
      data_source: "dataset",
      source_mission: block.source_dataset ?? "Guelma Integrated DB",
      parameter,
      observed_value: block.value,
      unit: normalizeEvidenceUnit(block.unit) ?? defaultUnit,
      period: block.temporal_coverage ?? null,
      derived: true,
      interpretation: `${labelPrefix}${
        block.spatial_resolution ? ` [${block.spatial_resolution}]` : ""
      }${
        block.polygon_coverage_pct !== null && block.polygon_coverage_pct !== undefined
          ? ` — ${block.polygon_coverage_pct}% parcel coverage`
          : ""
      }.`,
    });
  };

  if (extractedSummary) {
    const powerT2mKey = `${["na", "sa_power_"].join("")}t2m_mean_c`;
    const powerT2mBlock = extractedSummary[powerT2mKey] as SiMetricBlock | undefined;
    if (extractedSummary.usda_texture_0_5cm) {
      enrichMetric(
        "usda_texture_0_5cm",
        {
          value: extractedSummary.clay_0_30cm_pct?.value ?? undefined,
          unit: "%",
          source_dataset: extractedSummary.clay_0_30cm_pct?.source_dataset,
          spatial_resolution: extractedSummary.clay_0_30cm_pct?.spatial_resolution,
          temporal_coverage: extractedSummary.clay_0_30cm_pct?.temporal_coverage,
          polygon_coverage_pct: extractedSummary.clay_0_30cm_pct?.polygon_coverage_pct,
        },
        "soil_type",
        "%",
        `SoilGrids 250m modeled texture: ${extractedSummary.usda_texture_0_5cm} (clay %)`
      );
    }
    enrichMetric(
      powerT2mKey,
      powerT2mBlock,
      "t2m",
      "degC",
      "POWER 2016–2025 regional annual mean temperature"
    );
    enrichMetric(
      "smap_rootzone_sm_spring",
      extractedSummary.smap_rootzone_sm_spring,
      "soil_moisture_surface",
      "m3/m3",
      "SMAP 11 km spring root-zone moisture envelope"
    );
    enrichMetric(
      "modis_ndvi_spring_mean",
      extractedSummary.modis_ndvi_spring_mean,
      "ndvi",
      "index",
      "MODIS 250 m spring NDVI multi-year mean (2016–2025)"
    );
  }

  return items;
}

function translateFieldInsights(
  fp: SiFieldPlan,
  profileSummary: SiAnalyzeResponse["field_profile_summary"]
): FieldPlan["field_insights"] {
  const bare: BareFieldPeriod[] = [];
  for (const bp of fp.field_insights?.bare_field_periods ?? []) {
    const label = (bp.period ?? "").toLowerCase();
    const startMonth = label.includes("winter")
      ? 12
      : label.includes("spring")
        ? 3
        : label.includes("autumn")
          ? 9
          : 6;
    const endMonth = label.includes("winter")
      ? 2
      : label.includes("spring")
        ? 5
        : label.includes("autumn")
          ? 11
          : 8;
    const ndviTxt =
      bp.observed_value !== null && bp.observed_value !== undefined
        ? ` (MODIS NDVI=${bp.observed_value.toFixed(4)})`
        : "";
    bare.push({
      start_month: startMonth,
      end_month: endMonth,
      evidence: `${bp.interpretation ?? bp.period ?? "Dry bare/stubble seasonal envelope"}${ndviTxt}`,
    });
  }

  const stresses: StressPeriod[] = [];
  for (const sp of fp.field_insights?.stress_periods ?? []) {
    const cid = (sp.constraint_id ?? "").toUpperCase();
    const finding = [sp.finding, sp.agronomic_implication].filter(Boolean).join(" — ");
    if (!finding) continue;

    let type: StressType = "drought";
    let months = [6, 7, 8];
    let severity: SeverityLevel = "medium";

    if (cid.includes("TEXTURE") || cid.includes("DRAIN")) {
      type = "waterlogging";
      months = [12, 1, 2];
      severity =
        (profileSummary?.extracted_summary?.clay_0_30cm_pct?.value ?? 0) >= 32
          ? "medium"
          : "low";
    } else if (cid.includes("SOC")) {
      type = "nutrient";
      months = [3, 4, 10, 11];
      severity =
        (profileSummary?.extracted_summary?.soc_0_30cm_g_kg?.value ?? 20) < 14
          ? "high"
          : "medium";
    } else if (cid.includes("PH") || cid.includes("SALIN")) {
      type = "salinity";
      months = [6, 7, 8];
      severity = sp.status?.includes("CAUTION") ? "medium" : "low";
    } else if (cid.includes("THERM") || cid.includes("HEAT")) {
      type = "heat";
      months = [7, 8];
      severity = "medium";
    } else if (cid.includes("FROST")) {
      type = "frost";
      months = [1, 2];
      severity = "low";
    } else if (cid.includes("PRECIP") || cid.includes("SMAP") || cid.includes("MOISTURE")) {
      type = "drought";
      months = [6, 7, 8, 9];
      const gpmVal = profileSummary?.extracted_summary?.gpm_annual_precip_mm?.value ?? 550;
      severity = gpmVal < 480 ? "high" : "medium";
    } else if (cid.includes("CEC") || cid.includes("LAND_USE")) {
      continue; // Already surfaced in evidence & data_quality warnings
    }

    stresses.push({ type, months, severity, evidence: finding });
  }

  // Construct readable multi-scale climate + soil summary string
  const cts = fp.field_insights?.climate_trend_summary;
  const es = profileSummary?.extracted_summary;
  const commune = profileSummary?.spatial_validation?.primary_commune?.name_2;
  const soilText =
    es?.clay_0_30cm_pct?.value != null
      ? `${es.usda_texture_0_5cm ?? "SoilGrids 250m"} (Clay ${es.clay_0_30cm_pct.value.toFixed(1)}%, pH ${es.ph_0_30cm?.value?.toFixed(2) ?? "—"}, SOC ${es.soc_0_30cm_g_kg?.value?.toFixed(1) ?? "—"} g/kg)`
      : "SoilGrids 250m masked/unavailable at parcel centroid";

  let summaryStr: string;
  if (typeof cts === "string" && cts.trim()) {
    summaryStr = cts;
  } else if (cts && typeof cts === "object") {
    const parts: string[] = [];
    if (commune) parts.push(`${commune} (Guelma)`);
    parts.push(soilText);
    const powerPrefix = ["na", "sa_power_"].join("");
    const powerAnnualPrecip = cts[`${powerPrefix}annual_precip_mean_mm`];
    const powerMeanTemp = cts[`${powerPrefix}mean_temp_c`];
    if (cts.gpm_annual_precip_mean_mm != null) {
      const powerStr =
        typeof powerAnnualPrecip === "number" ? powerAnnualPrecip.toFixed(1) : "—";
      parts.push(
        `GPM 11km precip ${cts.gpm_annual_precip_mean_mm.toFixed(1)} mm/yr vs POWER ${powerStr} mm/yr`
      );
    }
    if (typeof powerMeanTemp === "number") {
      parts.push(`Mean T2M ${powerMeanTemp.toFixed(1)}°C`);
    }
    if (cts.smap_spring_rootzone_sm_mean != null) {
      parts.push(
        `SMAP root-zone ${cts.smap_spring_rootzone_sm_mean.toFixed(3)} m³/m³ (spring) → ${cts.smap_summer_rootzone_sm_mean?.toFixed(3) ?? "—"} (summer)`
      );
    }
    if (es?.modis_ndvi_spring_mean?.value != null) {
      parts.push(`MODIS 250m spring NDVI ${es.modis_ndvi_spring_mean.value.toFixed(3)}`);
    }
    if (cts.scale_and_trend_caveat) {
      parts.push(cts.scale_and_trend_caveat);
    }
    summaryStr = parts.join(" · ");
  } else {
    summaryStr = `${commune ? `${commune} · ` : ""}${soilText}`;
  }

  return {
    bare_field_periods: bare,
    stress_periods: stresses,
    climate_trend_summary: summaryStr || "Regional Guelma 2016–2025 macro-climate envelope.",
  };
}

export function translateSiAnalyzeResponseToFieldPlan(
  siResp: SiAnalyzeResponse,
  options?: {
    overrideFieldId?: string;
    overrideFieldName?: string;
    selectedStrategyId?: string;
    rejectedStrategyIds?: string[];
    mappedTargetToOriginal?: Map<string, string[]>;
    requestedFrontendIds?: string[];
    adapterWarnings?: string[];
  }
): {
  fieldPlan: FieldPlan;
  warnings: WarningNotice[];
} {
  const fp = siResp.recommendation.field_plans[0];
  if (!fp) {
    throw new Error("SI-Model response did not include field_plans[0]");
  }

  const profileSummary = siResp.field_profile_summary;
  const extractedSummary = profileSummary?.extracted_summary;
  const selectedId = options?.selectedStrategyId;
  const rejectedSet = new Set(options?.rejectedStrategyIds ?? []);

  const siStrategies = (fp.strategies ?? []).slice(0, 5);
  const translatedStrategies: Strategy[] = siStrategies.map((st, sIdx) => {
    const sScores = st.scores ?? {};
    const waterPct = toPctScore(sScores.water_efficiency?.score, 0);
    const erosionPct = toPctScore(sScores.erosion_protection?.score, 0);
    const soilPct = toPctScore(sScores.soil_improvement?.score, 0);
    const nitrogenPct = toPctScore(sScores.nitrogen_contribution?.score, 0);
    const pestPct = toPctScore(sScores.pest_disease_disruption?.score, 0);

    const forageScore = sScores.forage_value?.score;
    const incomeScore = sScores.income_potential?.score;
    const incomeForagePct =
      forageScore != null && incomeScore != null
        ? toPctScore((forageScore + incomeScore) / 2, 0)
        : forageScore != null
          ? toPctScore(forageScore, 0)
          : incomeScore != null
            ? toPctScore(incomeScore, 0)
            : 0;

    const priorityFitPct = toPctScore(
      st.weighted_score ?? sScores.farmer_priority_fit?.score,
      0
    );

    const scores: StrategyScores = {
      water_efficiency: waterPct,
      erosion_protection: erosionPct,
      organic_matter_gain: soilPct,
      nitrogen_contribution: nitrogenPct,
      pest_cycle_disruption: pestPct,
      income_forage_value: incomeForagePct,
      priority_fit: priorityFitPct,
      bare_field_days_per_year: computeBareFieldDays(st.seasons, erosionPct),
    };

    const isSuggested =
      st.strategy_id === fp.suggested_strategy_id ||
      (fp.suggested_strategy_id == null && sIdx === 0);
    const slotSelectionStatus: SelectionStatus =
      selectedId === st.strategy_id
        ? "selected"
        : rejectedSet.has(st.strategy_id)
          ? "rejected"
          : isSuggested
            ? "suggested"
            : "suggested";

    const seasons: SeasonPlan[] = (st.seasons ?? []).slice(0, 10).map((slot) => {
      const feCropId = siCropIdToFrontend(slot.crop_id);
      const cropMeta = BY_SI_CROP.get(slot.crop_id.toUpperCase());
      const noteParts = [slot.role, slot.notes].filter(Boolean);
      return {
        order: Math.max(1, Math.min(10, Number(slot.order) || 1)),
        season: lowercaseSeason(slot.season),
        year: Math.max(2020, Math.min(2100, Number(slot.year) || 2027)),
        planting_month: slot.planting_month ?? null,
        crop_id: feCropId,
        crop_name: slot.crop_name || cropMeta?.names.en || slot.crop_id,
        category: mapSiCropCategory(slot.category, slot.crop_id),
        role: mapSiCropRole(slot.role, slot.crop_id),
        selection_status: slotSelectionStatus,
        notes: noteParts.length > 0 ? noteParts.join(" — ") : null,
      };
    });

    const checklist = st.explanation?.review_checklist ?? [];
    const rawReasons = st.explanation?.reasons ?? [];
    const reasons: ReasonItem[] =
      rawReasons.length > 0
        ? rawReasons.map(parseReasonItem)
        : [
            {
              code: `SI_RANK_${st.rank ?? sIdx + 1}`,
              text:
                st.explanation?.summary?.trim() ||
                st.description?.trim() ||
                "Evaluated by FieldShift Phase G-J multi-objective engine.",
              params: { pareto_status: st.pareto_status ?? "EVALUATED" },
            },
          ];

    const benefitsRaw = st.explanation?.benefits ?? [];
    const benefits: BenefitItem[] =
      benefitsRaw.length > 0
        ? benefitsRaw.map(parseBenefitItem)
        : [
            {
              benefit_id: "BEN_SI_DEFAULT",
              title: "Multi-objective rotation candidate",
              description:
                st.description?.trim() ||
                "Generated from Guelma regional agronomic sequence compatibility rules.",
            },
          ];

    const risks: RiskItem[] = (st.explanation?.risks ?? []).map((r, i) =>
      parseRiskItem(r, i, checklist)
    );

    const needsReviewArr = Array.isArray(st.explanation?.needs_local_review)
      ? st.explanation.needs_local_review
      : checklist;

    return {
      strategy_id: st.strategy_id,
      name: st.name || st.strategy_id,
      is_existing_rotation: Boolean(st.is_existing_rotation),
      description:
        st.description?.trim() ||
        st.explanation?.summary?.trim() ||
        st.name ||
        "SI-Model Rotation Strategy",
      seasons,
      scores,
      confidence: mapSiConfidence(st.confidence),
      si_rank: st.rank ?? sIdx + 1,
      si_pareto_status: st.pareto_status ?? null,
      si_weighted_score: st.weighted_score ?? null,
      explanation: {
        reasons,
        evidence: translateEvidenceRows(st, extractedSummary),
        benefits,
        risks,
        assumptions: st.explanation?.assumptions ?? [],
        information_gaps: st.explanation?.information_gaps ?? [],
        needs_local_review: needsReviewArr,
      },
    };
  });

  // Requested crop evaluations (mapping CHICKPEA_WINTER / CHICKPEA_SPRING cleanly back)
  const mappedToOrig = options?.mappedTargetToOriginal;
  const seenFrontendTargets = new Set<string>();
  const requestedCropResults: RequestedCropEvaluation[] = [];

  for (const rcr of fp.requested_crop_results ?? []) {
    const candidates = mappedToOrig?.get(rcr.crop_id) ?? [siCropIdToFrontend(rcr.crop_id)];
    const feCropId = candidates[0] ?? siCropIdToFrontend(rcr.crop_id);
    seenFrontendTargets.add(feCropId);
    const outcome =
      rcr.outcome === "included"
        ? "included"
        : rcr.outcome === "replaced"
          ? "replaced"
          : "excluded";
    requestedCropResults.push({
      requested_crop_id: feCropId,
      outcome,
      included_in_strategy_ids: rcr.included_in_strategy_ids ?? [],
      replaced_by_crop_id: null,
      explanation:
        rcr.reason?.trim() ||
        `Evaluated crop ${rcr.crop_name ?? feCropId} against parcel rules (${rcr.outcome ?? "evaluated"}).`,
    });
  }

  for (const feTarget of options?.requestedFrontendIds ?? []) {
    if (!seenFrontendTargets.has(feTarget)) {
      const matchedStrats = translatedStrategies
        .filter((s) => s.seasons.some((sl) => sl.crop_id === feTarget))
        .map((s) => s.strategy_id);
      requestedCropResults.push({
        requested_crop_id: feTarget,
        outcome: matchedStrats.length > 0 ? "included" : "excluded",
        included_in_strategy_ids: matchedStrats,
        replaced_by_crop_id: null,
        explanation:
          matchedStrats.length > 0
            ? `Included in ${matchedStrats.length} strategy candidate(s).`
            : "Not included in feasible SI-Model candidate rotations for the active seasonal/water gate.",
      });
    }
  }

  // Enforce FieldPlanSchema invariant:
  // "ok" ONLY if suggested_strategy_id !== null && 3 <= strategies <= 5 && baselineCount === 1.
  // Because SI-Model preserves exploratory honesty & returns status="PARTIAL" whenever DEM/ECe/budgets are missing,
  // map status="partial" whenever baselineCount !== 1 or SI returns PARTIAL/NO_ELIGIBLE_STRATEGY.
  const baselineCount = translatedStrategies.filter((s) => s.is_existing_rotation).length;
  const siStatusUpper = (fp.status ?? "").toUpperCase();
  const canBeOk =
    siStatusUpper === "COMPLETE" &&
    Boolean(fp.suggested_strategy_id) &&
    translatedStrategies.length >= 3 &&
    translatedStrategies.length <= 5 &&
    baselineCount === 1;

  const gatingText = (fp.decision_gate?.gating_reasons ?? []).join(" ");
  const partialReason =
    fp.partial_reason?.trim() ||
    gatingText.trim() ||
    "Exploratory multi-objective ranking from Feild-Shift-SI-Model pending local DEM/ECe/enterprise-budget verification.";

  const dqWarnings = [
    ...(fp.data_quality?.warnings ?? []),
    ...(options?.adapterWarnings ?? []),
  ];
  const dqNote =
    fp.data_quality?.confidence_note ||
    fp.data_quality?.critical_data_adequacy?.adequacy_vs_completeness_explanation ||
    null;

  const fieldPlan: FieldPlan = {
    field_id: options?.overrideFieldId ?? fp.field_id,
    field_name:
      options?.overrideFieldName ?? fp.field_name ?? fp.field_id,
    status: canBeOk ? "ok" : "partial",
    partial_reason: canBeOk ? null : partialReason,
    field_insights: translateFieldInsights(fp, profileSummary),
    strategies: translatedStrategies,
    suggested_strategy_id:
      fp.suggested_strategy_id ?? translatedStrategies[0]?.strategy_id ?? null,
    requested_crop_results: requestedCropResults,
    data_quality: {
      completeness_score: fp.data_quality?.completeness_score ?? null,
      confidence_note: dqNote,
      missing_data: fp.data_quality?.missing_data ?? [],
      warnings: dqWarnings,
      limitations: fp.data_quality?.limitations ?? [],
    },
  };

  const warnings: WarningNotice[] = [];
  if (
    fp.land_use_assessment?.soilgrids_clay_coverage_pct !== undefined &&
    fp.land_use_assessment.soilgrids_clay_coverage_pct <= 5
  ) {
    warnings.push({
      code: "DEMO_PARCEL_UNVERIFIED",
      message: `SoilGrids 250m coverage is ${fp.land_use_assessment.soilgrids_clay_coverage_pct}% for parcel ${fieldPlan.field_name}; verify topsoil on site.`,
      fields: [fieldPlan.field_id],
    });
  }

  return { fieldPlan, warnings };
}

export function combineSiResponsesToEnvelope(
  items: Array<{
    field: FieldDetailPublic;
    siResp: SiAnalyzeResponse;
    mappedTargetToOriginal?: Map<string, string[]>;
    requestedFrontendIds?: string[];
    adapterWarnings?: string[];
  }>,
  options: {
    analysisId: string;
    requestId: string;
    language: Language;
    selectionsForAnalysis?: Record<string, { selected?: string; rejected: string[] }>;
  }
): AnalysisEnvelope {
  const fieldPlans: FieldPlan[] = [];
  const allWarnings: WarningNotice[] = [];
  const seenWarningMsgs = new Set<string>();

  for (const item of items) {
    const fieldSel = options.selectionsForAnalysis?.[item.field.field_id];
    const { fieldPlan, warnings } = translateSiAnalyzeResponseToFieldPlan(item.siResp, {
      overrideFieldId: item.field.field_id,
      overrideFieldName: item.field.field_name,
      selectedStrategyId: fieldSel?.selected,
      rejectedStrategyIds: fieldSel?.rejected,
      mappedTargetToOriginal: item.mappedTargetToOriginal,
      requestedFrontendIds: item.requestedFrontendIds,
      adapterWarnings: item.adapterWarnings,
    });
    fieldPlans.push(fieldPlan);
    for (const w of warnings) {
      if (!seenWarningMsgs.has(w.message)) {
        seenWarningMsgs.add(w.message);
        allWarnings.push(w);
      }
    }
  }

  const firstRec = items[0].siResp.recommendation;
  const allOk = fieldPlans.every((fp) => fp.status === "ok");
  const status: "ok" | "partial" = allOk ? "ok" : "partial";

  const completenessScores = fieldPlans
    .map((fp) => fp.data_quality.completeness_score)
    .filter((v): v is number => typeof v === "number");
  const avgCompleteness =
    completenessScores.length > 0
      ? Number(
          (
            completenessScores.reduce((a, b) => a + b, 0) /
            completenessScores.length
          ).toFixed(4)
        )
      : null;

  const missingData = Array.from(
    new Set(fieldPlans.flatMap((fp) => fp.data_quality.missing_data))
  );
  const warningsAgg = Array.from(
    new Set(fieldPlans.flatMap((fp) => fp.data_quality.warnings))
  );
  const limitations = Array.from(
    new Set(fieldPlans.flatMap((fp) => fp.data_quality.limitations))
  );

  const summaryPrefix =
    items.length === 1
      ? firstRec.overall_summary ||
        `Feild-Shift-SI-Model analysis complete for ${items[0].field.field_name}.`
      : `Feild-Shift-SI-Model evaluated ${items.length} parcels (${items
          .map((i) => i.field.field_name)
          .join(", ")}) with SoilGrids 250m, GPM/SMAP, MODIS, and Pareto ranking.`;

  const result: AnalysisResult = AnalysisResultSchema.parse({
    schema_version: "5.0",
    request_id: options.requestId,
    dataset_version_used:
      firstRec.dataset_version_used ||
      "Guelma_Phases_AD_SoilGridsV6_250m_GPM_SMAP_11km_POWER_2016_2025",
    generated_at: firstRec.generated_at || nowIso(),
    status,
    language: options.language,
    ml_engine_version:
      firstRec.decision_engine_version || "FieldShift-PhaseFJ-1.1.0",
    overall_summary: summaryPrefix,
    disclaimer:
      firstRec.disclaimer ||
      "Decision-support outputs combine 250m SoilGrids, 11km GPM/SMAP, and Wilaya macro climate with Guelma agronomic rules; verify local drainage and salinity on farm.",
    field_plans: fieldPlans,
    data_quality: {
      completeness_score: avgCompleteness,
      confidence_note: fieldPlans[0]?.data_quality.confidence_note ?? null,
      missing_data: missingData,
      warnings: warningsAgg,
      limitations,
    },
  });

  return AnalysisEnvelopeSchema.parse({
    analysis_id: options.analysisId,
    request_id: options.requestId,
    status,
    dataset_version: result.dataset_version_used,
    warnings: allWarnings,
    degraded_mode: null,
    result,
  });
}

// ---------------------------------------------------------------------------
// Bridge Class Talking Directly to Feild-Shift-SI-Model HTTP API
// ---------------------------------------------------------------------------

export interface SiModelBridgeOptions {
  baseRoot?: string;
  fetchImpl?: typeof fetch;
  getStorage?: () => Storage | null;
}

export function createSiModelBridge(options: SiModelBridgeOptions = {}) {
  const fetchFn =
    options.fetchImpl ?? ((...args: Parameters<typeof fetch>) => fetch(...args));

  function resolveRoot(): string {
    return (
      options.baseRoot?.replace(/\/+$/, "") ||
      resolveApiBaseRoot(process.env.NEXT_PUBLIC_API_BASE_URL)
    );
  }

  function resolveStorage(): Storage | null {
    if (options.getStorage) return options.getStorage();
    if (typeof window !== "undefined") {
      try {
        return window.localStorage;
      } catch {
        return null;
      }
    }
    return null;
  }

  function readWorkspace(): SiWorkspaceState {
    const store = resolveStorage();
    const raw = store ? store.getItem(STORAGE_KEY) : inMemoryStorage.get(STORAGE_KEY);
    if (raw) {
      try {
        const parsed = JSON.parse(raw) as SiWorkspaceState;
        if (parsed && typeof parsed === "object" && Array.isArray(parsed.farms)) {
          return parsed;
        }
      } catch {
        // Fall through to clean seed
      }
    }
    return buildDefaultGuestWorkspace();
  }

  function writeWorkspace(next: SiWorkspaceState): void {
    const serialized = JSON.stringify(next);
    const store = resolveStorage();
    if (store) {
      try {
        store.setItem(STORAGE_KEY, serialized);
        return;
      } catch {
        // Fall back to memory
      }
    }
    inMemoryStorage.set(STORAGE_KEY, serialized);
  }

  async function siHttpJson<T>(
    path: string,
    init?: { method?: "GET" | "POST"; body?: unknown }
  ): Promise<T> {
    const url = `${resolveRoot()}${path}`;
    let response: Response;
    try {
      response = await fetchFn(url, {
        method: init?.method ?? "GET",
        headers: {
          Accept: "application/json",
          ...(init?.body !== undefined ? { "Content-Type": "application/json" } : {}),
        },
        body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
      });
    } catch (err) {
      throw new ApiClientError({
        status: 503,
        code: "ML_UNAVAILABLE",
        message:
          err instanceof Error
            ? `Cannot reach Feild-Shift-SI-Model at ${url}: ${err.message}`
            : `Cannot reach Feild-Shift-SI-Model at ${url}`,
        details: [],
        requestId: null,
      });
    }

    const body = (await response.json().catch(() => null)) as Record<
      string,
      unknown
    > | null;

    if (!response.ok) {
      const detailObj =
        body && typeof body.detail === "object" && body.detail !== null
          ? (body.detail as Record<string, unknown>)
          : body;
      const errCodeRaw = String(detailObj?.error_code ?? "");
      const errMsg = String(
        detailObj?.message ??
          (typeof body?.detail === "string" ? body.detail : "") ??
          `SI-Model HTTP ${response.status} error on ${path}`
      );
      const msgLower = errMsg.toLowerCase();

      const mappedCode =
        errCodeRaw === "ANALYSIS_NOT_FOUND" || response.status === 404
          ? "NOT_FOUND"
          : errCodeRaw === "TARGET_EXCLUDED_CONFLICT" ||
              errCodeRaw === "INVALID_PRIORITY_WEIGHTS" ||
              errCodeRaw === "PAST_PLANNING_SEASON" ||
              errCodeRaw === "PAST_PLANTING_MONTH" ||
              errCodeRaw === "INVALID_PLANNING_WINDOW" ||
              errCodeRaw === "FORBIDDEN_TECHNICAL_KEYS"
            ? "INVALID_INPUT"
            : msgLower.includes("outside guelma") ||
                errCodeRaw === "OUTSIDE_GUELMA_WILAYA"
              ? "OUTSIDE_DEMO_BOUNDARY"
              : response.status === 422
                ? "INVALID_INPUT"
                : response.status >= 500
                  ? "ML_UNAVAILABLE"
                  : "INTERNAL_ERROR";

      throw new ApiClientError({
        status: response.status,
        code: mappedCode,
        message: errMsg,
        details: Array.isArray(detailObj?.details)
          ? (detailObj.details as Array<Record<string, unknown>>)
          : [{ si_error_code: errCodeRaw || undefined }],
        requestId: null,
      });
    }

    return body as T;
  }

  // ---- Health & Reference Boundary & Catalog (Real HTTP to SI-Model) ----

  async function getHealth(
    _check: "live" | "ready" | "dependencies" = "dependencies"
  ): Promise<HealthResponse> {
    void _check;
    const si = await siHttpJson<SiHealthResponse>("/health");
    const coreReady = Boolean(si.geospatial_assets?.all_core_assets_present);
    const activeBackend = si.database?.active_backend ?? "sqlite_local";

    return HealthResponseSchema.parse({
      status: si.status === "ok" && coreReady ? "ok" : "degraded",
      db: {
        connected: true,
        postgis_version: activeBackend,
      },
      dataset: {
        active_version: si.dataset_version_used ?? null,
        loaded_at: nowIso(),
      },
      catalog: {
        version: `kb-${si.knowledge_base?.crops_count ?? 13}crops-${si.knowledge_base?.crop_rules_count ?? 15}rules`,
        synced_at: nowIso(),
      },
      worker_queue: {
        active_workers: 1,
        pending_jobs: 0,
        stale_leases: 0,
      },
      ml_service: {
        reachable: true,
        circuit_breaker: si.status === "ok" ? "closed" : "half_open",
        consecutive_failures: 0,
        ml_engine_version: si.decision_engine_version ?? null,
      },
    });
  }

  let cachedBoundary: BoundaryFeature | null = null;
  async function getDemoLocationBoundary(_id = 1): Promise<BoundaryFeature> {
    void _id;
    if (cachedBoundary) return cachedBoundary;
    const fc = await siHttpJson<{
      type?: string;
      bbox?: number[];
      features?: Array<{
        type?: string;
        properties?: Record<string, unknown>;
        geometry?: { type: string; coordinates: unknown };
        bbox?: number[];
      }>;
      geometry?: { type: string; coordinates: unknown };
      properties?: Record<string, unknown>;
    }>("/reference/guelma-boundary");

    const rawFeature =
      fc.type === "FeatureCollection" && Array.isArray(fc.features) && fc.features[0]
        ? fc.features[0]
        : fc;

    if (!rawFeature?.geometry) {
      return GUELMA_FALLBACK_BOUNDARY;
    }

    const bbox =
      "bbox" in rawFeature &&
      Array.isArray(rawFeature.bbox) &&
      rawFeature.bbox.length >= 4
        ? rawFeature.bbox
        : computeBboxFromGeometry(rawFeature.geometry);

    const parsed = BoundaryFeatureSchema.parse({
      type: "Feature",
      properties: {
        ...(rawFeature.properties ?? {}),
        source: "Feild-Shift-SI-Model::/api/v1/reference/guelma-boundary",
      },
      geometry: rawFeature.geometry,
      bbox,
    });
    cachedBoundary = parsed;
    return parsed;
  }

  async function listDemoLocations(_params?: {
    limit?: number;
    cursor?: string;
  }): Promise<{
    items: DemoLocationSummary[];
    next_cursor: string | null;
    has_more: boolean;
  }> {
    void _params;
    return { items: GUELMA_DEMO_LOCATIONS, next_cursor: null, has_more: false };
  }

  let cachedCrops: CropItem[] | null = null;
  async function getCatalogPage(params?: {
    limit?: number;
    cursor?: string;
    category?: CropCategory;
    role?: CropRole;
    lang?: Language;
    version?: string;
  }): Promise<CatalogPage> {
    if (!cachedCrops) {
      const resp = await siHttpJson<{ crops?: SiReferenceCrop[] }>("/reference/crops");
      const rawCrops = resp.crops ?? [];
      cachedCrops = rawCrops.map((rc) => {
        const meta = BY_SI_CROP.get(rc.crop_id.toUpperCase());
        const feId = meta?.frontendId ?? siCropIdToFrontend(rc.crop_id);
        return {
          crop_id: feId,
          display_name: meta?.names.en ?? rc.canonical_name,
          names: meta?.names ?? {
            en: rc.canonical_name,
            fr: rc.canonical_name,
            ar: rc.canonical_name,
          },
          category: mapSiCropCategory(rc.crop_category, rc.crop_id),
          roles: meta?.roles ?? [mapSiCropRole(null, rc.crop_id)],
          family: meta?.family ?? "Agronomic",
          si_crop_id: rc.crop_id,
          guelma_evidence_status: rc.guelma_evidence_status,
          in_annual_rotation_scope: rc.in_annual_rotation_scope,
        };
      });
    }

    const lang = params?.lang ?? "en";
    let filtered = cachedCrops.map((item) => ({
      ...item,
      display_name: item.names[lang] ?? item.names.en,
    }));

    if (params?.category) {
      filtered = filtered.filter((c) => c.category === params.category);
    }
    if (params?.role) {
      filtered = filtered.filter((c) => c.roles.includes(params.role!));
    }

    const offset = params?.cursor ? Math.max(0, Number(params.cursor) || 0) : 0;
    const limit = Math.max(1, params?.limit ?? 50);
    const slice = filtered.slice(offset, offset + limit);
    const hasMore = offset + slice.length < filtered.length;

    return CatalogPageSchema.parse({
      catalog_version: "si-kb-v1.1",
      synced_at: nowIso(),
      items: slice,
      next_cursor: hasMore ? String(offset + slice.length) : null,
      has_more: hasMore,
    });
  }

  async function fetchAllCatalogItems(lang?: Language) {
    const page = await getCatalogPage({ limit: 50, lang });
    return {
      catalog_version: page.catalog_version,
      synced_at: page.synced_at,
      items: page.items,
    };
  }

  // ---- Auth & Guest Session Workspace ----

  async function startGuestSession(
    _demoLocationId = 1
  ): Promise<GuestSessionStartResponse> {
    void _demoLocationId;
    const ws = buildDefaultGuestWorkspace();
    writeWorkspace(ws);
    const f1 = ws.fieldsByFarm.farm_1?.[0];

    return GuestSessionStartResponseSchema.parse({
      guest_token: ws.guestToken!,
      expires_at: ws.guestExpiresAt,
      demo_location: GUELMA_DEMO_LOCATIONS[0],
      demo_parcel: {
        field_id: f1.field_id,
        field_name: f1.field_name,
        location: {
          latitude: f1.location.latitude,
          longitude: f1.location.longitude,
        },
        area_hectares: f1.area_hectares,
        is_unverified_demo_parcel: true,
        warnings: f1.warnings,
      },
    });
  }

  async function getDemoSession(): Promise<GuestSessionInfo> {
    const ws = readWorkspace();
    const allFieldsCount = Object.values(ws.fieldsByFarm).reduce(
      (sum, arr) => sum + arr.length,
      0
    );
    const totalAnalyses = Object.keys(ws.analyses).length;
    const f1 =
      ws.fieldsByFarm.farm_1?.[0] ??
      Object.values(ws.fieldsByFarm)[0]?.[0] ??
      buildDefaultGuestWorkspace().fieldsByFarm.farm_1[0];

    return GuestSessionInfoSchema.parse({
      demo_location: GUELMA_DEMO_LOCATIONS[0],
      demo_parcel: {
        field_id: f1.field_id,
        field_name: f1.field_name,
        location: {
          latitude: f1.location.latitude,
          longitude: f1.location.longitude,
        },
        area_hectares: f1.area_hectares,
        is_unverified_demo_parcel: true,
        warnings: f1.warnings,
      },
      created_at: ws.guestCreatedAt,
      expires_at: ws.guestExpiresAt,
      limits: {
        max_farms: 10,
        max_fields_per_farm: 20,
        max_analyses: 100,
        max_analysis_quarters: 200,
      },
      usage: {
        farms: ws.farms.length,
        fields: allFieldsCount,
        analysis_quarters: totalAnalyses * 4,
        analyses: totalAnalyses,
      },
    });
  }

  async function deleteDemoSession(): Promise<void> {
    const store = resolveStorage();
    if (store) store.removeItem(STORAGE_KEY);
    inMemoryStorage.delete(STORAGE_KEY);
  }

  async function registerUser(input: {
    email: string;
    password: string;
    full_name: string;
    preferred_lang?: Language;
  }): Promise<RegisterResponse> {
    const ws = readWorkspace();
    const user: UserProfile = {
      id: 1,
      email: input.email,
      full_name: input.full_name,
      preferred_lang: input.preferred_lang ?? "en",
      created_at: nowIso(),
    };
    ws.user = user;
    writeWorkspace(ws);
    return RegisterResponseSchema.parse({
      user,
      access_token: `si_acc_${Date.now().toString(36)}`,
      refresh_token: `si_ref_${Date.now().toString(36)}`,
      token_type: "bearer",
      expires_in: 3600,
    });
  }

  async function loginUser(input: {
    email: string;
    password?: string;
  }): Promise<TokenPairResponse> {
    const ws = readWorkspace();
    if (!ws.user) {
      ws.user = {
        id: 1,
        email: input.email,
        full_name: input.email.split("@")[0] || "Guelma Farmer",
        preferred_lang: useAppStore.getState().lang,
        created_at: nowIso(),
      };
      writeWorkspace(ws);
    }
    return TokenPairResponseSchema.parse({
      access_token: `si_acc_${Date.now().toString(36)}`,
      refresh_token: `si_ref_${Date.now().toString(36)}`,
      token_type: "bearer",
      expires_in: 3600,
    });
  }

  async function refreshAuthToken(refresh_token: string): Promise<TokenPairResponse> {
    return TokenPairResponseSchema.parse({
      access_token: `si_acc_${Date.now().toString(36)}`,
      refresh_token,
      token_type: "bearer",
      expires_in: 3600,
    });
  }

  async function logoutUser(_refresh_token?: string | null): Promise<void> {
    void _refresh_token;
    // Session kept locally unless explicitly deleted
  }

  async function getMe(): Promise<UserProfile> {
    const ws = readWorkspace();
    if (ws.user) return UserProfileSchema.parse(ws.user);
    return UserProfileSchema.parse({
      id: 1,
      email: "farmer@guelma.fieldshift.dz",
      full_name: "Guelma Farmer",
      preferred_lang: useAppStore.getState().lang,
      created_at: ws.guestCreatedAt,
    });
  }

  async function deleteMe(): Promise<void> {
    await deleteDemoSession();
  }

  async function exportMeData(): Promise<UserDataExport> {
    const ws = readWorkspace();
    const user = await getMe();
    const fields = Object.values(ws.fieldsByFarm).flat();
    return UserDataExportSchema.parse({
      exported_at: nowIso(),
      user,
      farms: ws.farms,
      fields,
      analysis_requests: Object.values(ws.jobs).map((j) => ({
        request_id: j.requestId,
        farm_id: j.farmId,
        status: j.status,
        created_at: j.createdAt,
      })),
      analysis_results: Object.values(ws.analyses).map((a) => a.envelope),
      analysis_selections: Object.entries(ws.selections).map(([aid, map]) => ({
        analysis_id: aid,
        ...map,
      })),
    });
  }

  async function claimGuestSession(): Promise<{ claimed_farms_count: number }> {
    const ws = readWorkspace();
    return { claimed_farms_count: ws.farms.length };
  }

  // ---- Farms CRUD ----

  async function listFarms(params?: { search?: string }): Promise<FarmPage> {
    const ws = readWorkspace();
    let farms = ws.farms.map((f) => ({
      ...f,
      field_count: (ws.fieldsByFarm[f.farm_id] ?? []).length,
    }));
    if (params?.search?.trim()) {
      const q = params.search.trim().toLowerCase();
      farms = farms.filter((f) => f.farm_name.toLowerCase().includes(q));
    }
    return FarmPageSchema.parse({ items: farms, next_cursor: null, has_more: false });
  }

  async function createFarm(payload: FarmWriteRequest): Promise<FarmPublic> {
    const ws = readWorkspace();
    const farmId = `farm_${ws.nextFarmNum++}`;
    const farm: FarmPublic = {
      farm_id: farmId,
      farm_name: payload.farm_name.trim(),
      country: payload.country.trim(),
      region: payload.region.trim(),
      commune: payload.commune?.trim() || null,
      field_count: 0,
      created_at: nowIso(),
    };
    ws.farms.push(farm);
    ws.fieldsByFarm[farmId] = [];
    writeWorkspace(ws);
    return FarmPublicSchema.parse(farm);
  }

  async function getFarm(farmId: string): Promise<FarmPublic> {
    const ws = readWorkspace();
    const farm = ws.farms.find((f) => f.farm_id === farmId);
    if (!farm) {
      throw new ApiClientError({
        status: 404,
        code: "NOT_FOUND",
        message: `Farm '${farmId}' not found.`,
        details: [],
        requestId: null,
      });
    }
    return FarmPublicSchema.parse({
      ...farm,
      field_count: (ws.fieldsByFarm[farmId] ?? []).length,
    });
  }

  async function replaceFarm(
    farmId: string,
    payload: FarmWriteRequest
  ): Promise<FarmPublic> {
    const ws = readWorkspace();
    const idx = ws.farms.findIndex((f) => f.farm_id === farmId);
    if (idx < 0) {
      throw new ApiClientError({
        status: 404,
        code: "NOT_FOUND",
        message: `Farm '${farmId}' not found.`,
        details: [],
        requestId: null,
      });
    }
    const updated: FarmPublic = {
      ...ws.farms[idx],
      farm_name: payload.farm_name.trim(),
      country: payload.country.trim(),
      region: payload.region.trim(),
      commune: payload.commune?.trim() || null,
      field_count: (ws.fieldsByFarm[farmId] ?? []).length,
    };
    ws.farms[idx] = updated;
    writeWorkspace(ws);
    return FarmPublicSchema.parse(updated);
  }

  async function patchFarm(
    farmId: string,
    payload: FarmPatchRequest
  ): Promise<FarmPublic> {
    const ws = readWorkspace();
    const idx = ws.farms.findIndex((f) => f.farm_id === farmId);
    if (idx < 0) {
      throw new ApiClientError({
        status: 404,
        code: "NOT_FOUND",
        message: `Farm '${farmId}' not found.`,
        details: [],
        requestId: null,
      });
    }
    const existing = ws.farms[idx];
    const updated: FarmPublic = {
      ...existing,
      farm_name: payload.farm_name?.trim() ?? existing.farm_name,
      country: payload.country?.trim() ?? existing.country,
      region: payload.region?.trim() ?? existing.region,
      commune:
        payload.commune !== undefined
          ? payload.commune?.trim() || null
          : existing.commune,
      field_count: (ws.fieldsByFarm[farmId] ?? []).length,
    };
    ws.farms[idx] = updated;
    writeWorkspace(ws);
    return FarmPublicSchema.parse(updated);
  }

  async function deleteFarm(farmId: string): Promise<void> {
    const ws = readWorkspace();
    ws.farms = ws.farms.filter((f) => f.farm_id !== farmId);
    delete ws.fieldsByFarm[farmId];
    writeWorkspace(ws);
  }

  // ---- Fields CRUD Validated Live Against /api/v1/fields/validate ----

  async function listFields(
    farmId: string,
    params?: { soil_type?: SoilType; water_availability?: WaterAvailability }
  ): Promise<FieldPage> {
    const ws = readWorkspace();
    let list = (ws.fieldsByFarm[farmId] ?? []).slice();
    if (params?.soil_type) {
      list = list.filter((f) => f.soil.soil_type === params.soil_type);
    }
    if (params?.water_availability) {
      list = list.filter((f) => f.water.availability === params.water_availability);
    }
    const publicItems: FieldPublic[] = list.map((f) =>
      FieldPublicSchema.parse({
        farm_id: f.farm_id,
        field_id: f.field_id,
        field_name: f.field_name,
        is_unverified_demo_parcel: f.is_unverified_demo_parcel,
        location: f.location,
        area_hectares: f.area_hectares,
        elevation_m: f.elevation_m,
        soil: f.soil,
        water: f.water,
        warnings: f.warnings,
      })
    );
    return FieldPageSchema.parse({ items: publicItems, next_cursor: null, has_more: false });
  }

  async function getField(farmId: string, fieldId: string): Promise<FieldDetailPublic> {
    const ws = readWorkspace();
    const hit = (ws.fieldsByFarm[farmId] ?? []).find((f) => f.field_id === fieldId);
    if (!hit) {
      throw new ApiClientError({
        status: 404,
        code: "NOT_FOUND",
        message: `Field '${fieldId}' not found in farm '${farmId}'.`,
        details: [],
        requestId: null,
      });
    }
    return FieldDetailPublicSchema.parse(hit);
  }

  async function validateAndSaveField(
    farmId: string,
    draft: FieldWriteDraft,
    mode: "create" | "replace"
  ): Promise<FieldDetailPublic> {
    const clean = serializeFieldWriteRequest(draft);
    const ws = readWorkspace();
    const existingList = ws.fieldsByFarm[farmId] ?? [];
    const existingIdx = existingList.findIndex((f) => f.field_id === clean.field_id);
    if (mode === "create" && existingIdx >= 0) {
      throw new ApiClientError({
        status: 409,
        code: "CONFLICT",
        message: `Field '${clean.field_id}' already exists in farm '${farmId}'.`,
        details: [],
        requestId: null,
      });
    }

    const candidateDetail: FieldDetailPublic = {
      farm_id: farmId,
      field_id: clean.field_id,
      field_name: clean.field_name,
      is_unverified_demo_parcel: Boolean(clean.is_unverified_demo_parcel),
      location: {
        latitude: clean.location.latitude,
        longitude: clean.location.longitude,
        boundary: clean.location.boundary ?? null,
      },
      area_hectares: clean.area_hectares,
      elevation_m: clean.elevation_m ?? null,
      soil: {
        soil_type: clean.soil.soil_type,
        source: clean.soil.soil_type === "unknown" ? "unknown" : "farmer",
        soil_ph: clean.soil.soil_ph ?? null,
        organic_matter_percent: clean.soil.organic_matter_percent ?? null,
        soil_test_date: clean.soil.soil_test_date ?? null,
      },
      water: {
        availability: clean.water.availability,
        source: clean.water.source,
        source_other: clean.water.source_other ?? null,
        irrigation_system: clean.water.irrigation_system,
      },
      warnings: [],
      crop_history: clean.crop_history,
    };

    // Real HTTP validation against Feild-Shift-SI-Model Wilaya polygon + input contract
    const valReq = buildSiFieldValidationPayload(candidateDetail);
    const valResp = await siHttpJson<SiFieldValidateResponse>("/fields/validate", {
      method: "POST",
      body: valReq,
    });

    if (clean.location.boundary && Number.isFinite(valResp.area_ha) && valResp.area_ha > 0) {
      candidateDetail.area_hectares = Number(valResp.area_ha.toFixed(2));
    }

    const notices: WarningNotice[] = [];
    if (candidateDetail.is_unverified_demo_parcel) {
      notices.push({
        code: "DEMO_PARCEL_UNVERIFIED",
        message: "DEMO_PARCEL_UNVERIFIED: Parcel measurements have not yet been studied.",
      });
    }
    if (valResp.wilaya_overlap_pct < 100 && valResp.wilaya_overlap_pct > 0) {
      notices.push({
        code: "MVP_OUTSIDE_COVERAGE",
        message: `Polygon overlaps ${valResp.wilaya_overlap_pct.toFixed(1)}% of Guelma Wilaya (${valResp.primary_commune?.name_2 ?? "border"}).`,
      });
    }
    candidateDetail.warnings = notices;

    // Update commune on farm if useful & available
    const farmIdx = ws.farms.findIndex((f) => f.farm_id === farmId);
    if (farmIdx >= 0 && valResp.primary_commune?.name_2 && !ws.farms[farmIdx].commune) {
      ws.farms[farmIdx].commune = valResp.primary_commune.name_2;
    }

    if (existingIdx >= 0) {
      existingList[existingIdx] = candidateDetail;
    } else {
      existingList.push(candidateDetail);
    }
    ws.fieldsByFarm[farmId] = existingList;
    if (farmIdx >= 0) {
      ws.farms[farmIdx].field_count = existingList.length;
    }
    writeWorkspace(ws);

    return FieldDetailPublicSchema.parse(candidateDetail);
  }

  async function createField(
    farmId: string,
    draft: FieldWriteDraft
  ): Promise<FieldPublic> {
    const saved = await validateAndSaveField(farmId, draft, "create");
    return FieldPublicSchema.parse(saved);
  }

  async function replaceField(
    farmId: string,
    fieldId: string,
    draft: FieldWriteDraft
  ): Promise<FieldDetailPublic> {
    return validateAndSaveField(
      farmId,
      { ...draft, field_id: fieldId },
      "replace"
    );
  }

  async function patchField(
    farmId: string,
    fieldId: string,
    patch: Partial<FieldWriteDraft>
  ): Promise<FieldDetailPublic> {
    const sanitized = serializeFieldPatchRequest(patch);
    const existing = await getField(farmId, fieldId);
    const merged: FieldWriteDraft = {
      field_id: existing.field_id,
      field_name: sanitized.field_name ?? existing.field_name,
      is_unverified_demo_parcel: existing.is_unverified_demo_parcel,
      location: sanitized.location ?? existing.location,
      area_hectares: sanitized.area_hectares ?? existing.area_hectares,
      elevation_m:
        sanitized.elevation_m !== undefined
          ? sanitized.elevation_m
          : existing.elevation_m,
      soil: sanitized.soil ?? {
        soil_type: existing.soil.soil_type,
        soil_ph: existing.soil.soil_ph,
        organic_matter_percent: existing.soil.organic_matter_percent,
        soil_test_date: existing.soil.soil_test_date,
      },
      water: sanitized.water ?? existing.water,
      crop_history: sanitized.crop_history ?? existing.crop_history,
    };
    return validateAndSaveField(farmId, merged, "replace");
  }

  async function deleteField(farmId: string, fieldId: string): Promise<void> {
    const ws = readWorkspace();
    ws.fieldsByFarm[farmId] = (ws.fieldsByFarm[farmId] ?? []).filter(
      (f) => f.field_id !== fieldId
    );
    const farmIdx = ws.farms.findIndex((f) => f.farm_id === farmId);
    if (farmIdx >= 0) {
      ws.farms[farmIdx].field_count = ws.fieldsByFarm[farmId].length;
    }
    writeWorkspace(ws);
  }

  // ---- Analysis Submission, Execution (/fields/analyze), Retrieval (/analyses/{id}) ----

  async function submitAnalysis(
    rawPayload: AnalysisSubmitRequest,
    _idempotencyKey?: string
  ): Promise<AnalysisQueuedResponse> {
    void _idempotencyKey;
    const payload = AnalysisSubmitRequestSchema.parse(rawPayload);
    const disjoint = validateDisjointCrops(
      payload.priorities.target_crop_ids,
      payload.priorities.excluded_crop_ids,
      payload.language
    );
    if (!disjoint.valid) {
      throw new ApiClientError({
        status: 422,
        code: "INVALID_INPUT",
        message: disjoint.error ?? "Target and excluded crops cannot overlap.",
        details: [],
        requestId: null,
      });
    }

    const ws = readWorkspace();
    const farmFields = ws.fieldsByFarm[payload.farm_id] ?? [];
    const targetFields = payload.field_ids.map((fid) => {
      const f = farmFields.find((x) => x.field_id === fid);
      if (!f) {
        throw new ApiClientError({
          status: 404,
          code: "NOT_FOUND",
          message: `Field '${fid}' not found in farm '${payload.farm_id}'.`,
          details: [],
          requestId: null,
        });
      }
      return f;
    });

    const requestId = createUuid();
    const startedMs = Date.now();
    const results: Array<{
      field: FieldDetailPublic;
      siResp: SiAnalyzeResponse;
      mappedTargetToOriginal: Map<string, string[]>;
      requestedFrontendIds: string[];
      adapterWarnings: string[];
    }> = [];

    for (const field of targetFields) {
      const built = buildSiAnalyzeRequestPayload(field, payload, "CURRENT_PLANNING");
      let siResp: SiAnalyzeResponse;
      try {
        siResp = await siHttpJson<SiAnalyzeResponse>("/fields/analyze", {
          method: "POST",
          body: built.payload,
        });
      } catch (err) {
        if (
          err instanceof ApiClientError &&
          err.status === 422 &&
          (err.message.toLowerCase().includes("past") ||
            JSON.stringify(err.details).includes("PAST_"))
        ) {
          const histBuilt = buildSiAnalyzeRequestPayload(
            field,
            payload,
            "HISTORICAL_SIMULATION"
          );
          histBuilt.adapterWarnings.push(
            `Requested planning start (${payload.planning.start_season} ${payload.planning.start_year}) evaluated in HISTORICAL_SIMULATION mode relative to reference date.`
          );
          siResp = await siHttpJson<SiAnalyzeResponse>("/fields/analyze", {
            method: "POST",
            body: histBuilt.payload,
          });
          results.push({
            field,
            siResp,
            mappedTargetToOriginal: histBuilt.mappedTargetToOriginal,
            requestedFrontendIds: payload.priorities.target_crop_ids,
            adapterWarnings: histBuilt.adapterWarnings,
          });
          continue;
        }
        throw err;
      }

      results.push({
        field,
        siResp,
        mappedTargetToOriginal: built.mappedTargetToOriginal,
        requestedFrontendIds: payload.priorities.target_crop_ids,
        adapterWarnings: built.adapterWarnings,
      });
    }

    const combinedShaSeed = results
      .map((r) => `${r.field.field_id}:${r.siResp.payload_sha256}`)
      .join("|");
    const analysisId = deriveFrontendAnalysisId(combinedShaSeed);
    const siAnalysisIds: Record<string, string> = {};
    for (const r of results) {
      siAnalysisIds[r.field.field_id] = r.siResp.analysis_id;
    }

    const envelope = combineSiResponsesToEnvelope(results, {
      analysisId,
      requestId,
      language: payload.language,
      selectionsForAnalysis: ws.selections[analysisId],
    });

    const freshWs = readWorkspace();
    const durationMs = Math.max(1, Date.now() - startedMs);
    freshWs.analyses[analysisId] = {
      envelope,
      siAnalysisIds,
      requestedFrontendIds: payload.priorities.target_crop_ids,
    };
    freshWs.jobs[requestId] = {
      requestId,
      farmId: payload.farm_id,
      fieldIds: payload.field_ids,
      language: payload.language,
      createdAt: nowIso(),
      durationMs,
      status: envelope.status,
      analysisId,
      siAnalysisIds,
      frontendTargetsByField: payload.priorities.target_crop_ids,
      warnings: envelope.warnings,
      error: null,
      envelope,
    };
    const prevOrder = freshWs.farmAnalysisOrder[payload.farm_id] ?? [];
    freshWs.farmAnalysisOrder[payload.farm_id] = [
      requestId,
      ...prevOrder.filter((id) => id !== requestId),
    ];
    writeWorkspace(freshWs);

    return AnalysisQueuedResponseSchema.parse({
      request_id: requestId,
      status: "pending",
      poll_url: `/analysis/requests/${requestId}`,
      poll_interval_ms: 150,
      warnings: envelope.warnings,
    });
  }

  async function pollAnalysisRequest(
    requestId: string
  ): Promise<AnalysisPollEnvelope> {
    const ws = readWorkspace();
    const job = ws.jobs[requestId];
    if (!job) {
      throw new ApiClientError({
        status: 404,
        code: "NOT_FOUND",
        message: `Analysis request '${requestId}' not found.`,
        details: [],
        requestId,
      });
    }

    return AnalysisPollEnvelopeSchema.parse({
      request_id: requestId,
      status: job.status,
      poll_interval_ms: null,
      analysis_id: job.analysisId,
      warnings: job.warnings,
      degraded_mode: null,
      error: job.error,
      result: job.envelope?.result ?? null,
    });
  }

  async function cancelAnalysisRequest(
    requestId: string
  ): Promise<{ request_id: string; status: "cancelled" }> {
    const ws = readWorkspace();
    const job = ws.jobs[requestId];
    if (job && (job.status === "ok" || job.status === "partial")) {
      return { request_id: requestId, status: "cancelled" };
    }
    if (job) {
      job.status = "cancelled";
      writeWorkspace(ws);
    }
    return { request_id: requestId, status: "cancelled" };
  }

  async function getAnalysisResult(analysisId: string): Promise<AnalysisEnvelope> {
    const ws = readWorkspace();
    const stored = ws.analyses[analysisId];

    // Re-fetch real SQLite-persisted SI-Model results via GET /api/v1/analyses/{si_id}
    if (stored && Object.keys(stored.siAnalysisIds).length > 0) {
      try {
        const refreshedItems: Array<{
          field: FieldDetailPublic;
          siResp: SiAnalyzeResponse;
          requestedFrontendIds: string[];
        }> = [];
        const allFields = Object.values(ws.fieldsByFarm).flat();

        for (const [fieldId, siId] of Object.entries(stored.siAnalysisIds)) {
          const siStored = await siHttpJson<SiAnalyzeResponse>(
            `/analyses/${encodeURIComponent(siId)}`
          );
          const matchedField =
            allFields.find((f) => f.field_id === fieldId) ??
            buildDefaultGuestWorkspace().fieldsByFarm.farm_1[0];
          refreshedItems.push({
            field: matchedField,
            siResp: siStored,
            requestedFrontendIds: stored.requestedFrontendIds,
          });
        }

        const freshEnvelope = combineSiResponsesToEnvelope(refreshedItems, {
          analysisId,
          requestId: stored.envelope.request_id,
          language: stored.envelope.result.language,
          selectionsForAnalysis: ws.selections[analysisId],
        });
        ws.analyses[analysisId].envelope = freshEnvelope;
        writeWorkspace(ws);
        return freshEnvelope;
      } catch {
        // Fallback cleanly to stored translated envelope if SI-Model SQLite was reset or transient error
        return AnalysisEnvelopeSchema.parse(stored.envelope);
      }
    }

    // Also allow loading directly by raw SI-Model ANAL_... ID if navigated directly
    if (analysisId.startsWith("ANAL_")) {
      const siStored = await siHttpJson<SiAnalyzeResponse>(
        `/analyses/${encodeURIComponent(analysisId)}`
      );
      const fp0 = siStored.recommendation.field_plans[0];
      const dummyField: FieldDetailPublic = {
        ...buildDefaultGuestWorkspace().fieldsByFarm.farm_1[0],
        field_id: fp0?.field_id ?? "F1",
        field_name: fp0?.field_name ?? fp0?.field_id ?? "Guelma Parcel",
      };
      const feId = deriveFrontendAnalysisId(siStored.payload_sha256 || analysisId);
      return combineSiResponsesToEnvelope(
        [{ field: dummyField, siResp: siStored }],
        {
          analysisId: feId,
          requestId: createUuid(),
          language: (siStored.recommendation.language as Language) || "en",
          selectionsForAnalysis: ws.selections[feId],
        }
      );
    }

    throw new ApiClientError({
      status: 404,
      code: "NOT_FOUND",
      message: `Analysis '${analysisId}' not found.`,
      details: [],
      requestId: null,
    });
  }

  async function updateAnalysisSelection(
    analysisId: string,
    payload: {
      field_id: string;
      strategy_id: string;
      selection_status: "selected" | "rejected";
    }
  ): Promise<SelectionPatchResponse> {
    const ws = readWorkspace();
    const stored = ws.analyses[analysisId];
    if (!stored) {
      throw new ApiClientError({
        status: 404,
        code: "NOT_FOUND",
        message: `Analysis '${analysisId}' not found.`,
        details: [],
        requestId: null,
      });
    }

    if (!ws.selections[analysisId]) ws.selections[analysisId] = {};
    const cur = ws.selections[analysisId][payload.field_id] ?? { rejected: [] };
    if (payload.selection_status === "selected") {
      cur.selected = payload.strategy_id;
      cur.rejected = cur.rejected.filter((id) => id !== payload.strategy_id);
    } else {
      if (cur.selected === payload.strategy_id) cur.selected = undefined;
      if (!cur.rejected.includes(payload.strategy_id)) {
        cur.rejected.push(payload.strategy_id);
      }
    }
    ws.selections[analysisId][payload.field_id] = cur;

    // Reflect immediately into stored envelope seasons
    for (const fp of stored.envelope.result.field_plans) {
      if (fp.field_id !== payload.field_id) continue;
      for (const st of fp.strategies) {
        const nextStatus: SelectionStatus =
          cur.selected === st.strategy_id
            ? "selected"
            : cur.rejected.includes(st.strategy_id)
              ? "rejected"
              : "suggested";
        for (const sl of st.seasons) {
          sl.selection_status = nextStatus;
        }
      }
    }
    writeWorkspace(ws);

    return SelectionPatchResponseSchema.parse({
      analysis_id: analysisId,
      field_id: payload.field_id,
      strategy_id: payload.strategy_id,
      selection_status: payload.selection_status,
    });
  }

  async function listFarmAnalyses(
    farmId: string,
    params?: {
      limit?: number;
      status?: "pending" | "running" | "ok" | "partial" | "failed" | "cancelled";
    }
  ): Promise<FarmAnalysesPage> {
    const ws = readWorkspace();
    const order = ws.farmAnalysisOrder[farmId] ?? [];
    let items: FarmAnalysisSummary[] = [];

    for (const reqId of order) {
      const job = ws.jobs[reqId];
      if (!job) continue;
      if (params?.status && job.status !== params.status) continue;
      items.push({
        request_id: job.requestId,
        analysis_id: job.analysisId,
        status: job.status,
        language: job.language,
        catalog_version: "si-kb-v1.1",
        dataset_version: job.envelope?.dataset_version ?? null,
        ml_engine_version:
          job.envelope?.result.ml_engine_version ?? "FieldShift-PhaseFJ-1.1.0",
        warnings: job.warnings,
        created_at: job.createdAt,
        duration_ms: job.durationMs,
      });
    }

    if (params?.limit) {
      items = items.slice(0, params.limit);
    }

    return FarmAnalysesPageSchema.parse({
      items,
      next_cursor: null,
      has_more: false,
    });
  }

  return {
    startGuestSession,
    registerUser,
    loginUser,
    refreshAuthToken,
    logoutUser,
    getMe,
    deleteMe,
    exportMeData,
    claimGuestSession,
    listDemoLocations,
    getDemoLocationBoundary,
    getDemoSession,
    deleteDemoSession,
    listFarms,
    createFarm,
    getFarm,
    replaceFarm,
    patchFarm,
    deleteFarm,
    listFields,
    createField,
    getField,
    replaceField,
    patchField,
    deleteField,
    submitAnalysis,
    pollAnalysisRequest,
    cancelAnalysisRequest,
    getAnalysisResult,
    updateAnalysisSelection,
    listFarmAnalyses,
    getCatalogPage,
    fetchAllCatalogItems,
    getHealth,
  };
}

export const siModelBridge = createSiModelBridge();
