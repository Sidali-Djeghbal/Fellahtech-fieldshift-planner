import { z } from "zod";

// ---------------------------------------------------------------------------
// Controlled Enums (verbatim from schema-v5.0.json & openapi.yaml)
// ---------------------------------------------------------------------------

export const LanguageSchema = z.enum(["en", "fr", "ar"]);
export type Language = z.infer<typeof LanguageSchema>;

export const SeasonSchema = z.enum(["spring", "summer", "autumn", "winter"]);
export type Season = z.infer<typeof SeasonSchema>;

export const CycleModeSchema = z.enum(["annual_rotation", "consecutive_seasons"]);
export type CycleMode = z.infer<typeof CycleModeSchema>;

export const DataSourceSchema = z.enum(["farmer_input", "dataset"]);
export type DataSource = z.infer<typeof DataSourceSchema>;

export const CropCategorySchema = z.enum([
  "cereals",
  "legumes",
  "oilseeds",
  "vegetables",
  "forage",
  "cover_crops",
  "fallow",
]);
export type CropCategory = z.infer<typeof CropCategorySchema>;

export const CropRoleSchema = z.enum([
  "cash_crop",
  "nitrogen_fixer",
  "forage",
  "cover_crop",
  "break_crop",
  "main_crop",
  "fallow",
]);
export type CropRole = z.infer<typeof CropRoleSchema>;

export const SelectionStatusSchema = z.enum(["suggested", "selected", "rejected"]);
export type SelectionStatus = z.infer<typeof SelectionStatusSchema>;

export const SeverityLevelSchema = z.enum(["low", "medium", "high"]);
export type SeverityLevel = z.infer<typeof SeverityLevelSchema>;

export const SoilTypeSchema = z.enum(["sandy", "clay", "loamy", "silty", "unknown"]);
export type SoilType = z.infer<typeof SoilTypeSchema>;

export const SoilSourceSchema = z.enum(["farmer", "unknown"]);
export type SoilSource = z.infer<typeof SoilSourceSchema>;

export const MarketPreferenceSchema = z.enum([
  "local_market",
  "export",
  "subsistence",
  "mixed",
]);
export type MarketPreference = z.infer<typeof MarketPreferenceSchema>;

export const WaterAvailabilitySchema = z.enum([
  "abundant",
  "moderate",
  "limited",
  "very_limited",
  "rainfed_only",
]);
export type WaterAvailability = z.infer<typeof WaterAvailabilitySchema>;

export const WaterSourceSchema = z.enum([
  "rainwater",
  "groundwater",
  "well",
  "dam_reservoir",
  "irrigation_network",
  "other",
  "unknown",
]);
export type WaterSource = z.infer<typeof WaterSourceSchema>;

export const IrrigationSystemSchema = z.enum([
  "rainfed",
  "drip",
  "sprinkler",
  "flood",
  "other",
  "unknown",
]);
export type IrrigationSystem = z.infer<typeof IrrigationSystemSchema>;

export const StressTypeSchema = z.enum([
  "drought",
  "heat",
  "frost",
  "waterlogging",
  "salinity",
  "nutrient",
]);
export type StressType = z.infer<typeof StressTypeSchema>;

export const EvidenceUnitSchema = z
  .enum([
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
  ])
  .nullable();
export type EvidenceUnit = z.infer<typeof EvidenceUnitSchema>;

export const EvidenceParameterSchema = z.enum([
  "precipitation",
  "t2m",
  "t2m_max",
  "t2m_min",
  "rh2m",
  "wind_2m",
  "solar_radiation",
  "ndvi",
  "soil_moisture_surface",
  "precipitation_anomaly",
  "evaporative_stress_index",
  "groundwater_anomaly",
  "crop_history",
  "soil_type",
  "soil_ph",
  "organic_matter_percent",
  "elevation_m",
  "water_availability",
  "dataset_feature",
]);
export type EvidenceParameter = z.infer<typeof EvidenceParameterSchema>;

export const SchemaVersionSchema = z.string().regex(/^5\.[0-9]+$/);

export const WarningCodeSchema = z.enum([
  "MVP_OUTSIDE_COVERAGE",
  "DEMO_PARCEL_UNVERIFIED",
]);
export type WarningCode = z.infer<typeof WarningCodeSchema>;

export const ErrorCodeSchema = z.enum([
  "INVALID_INPUT",
  "UNAUTHORIZED",
  "GUEST_LIMIT_REACHED",
  "NOT_FOUND",
  "CONFLICT",
  "CATALOG_VERSION_MISMATCH",
  "OUTSIDE_DEMO_BOUNDARY",
  "INSUFFICIENT_DATA",
  "RATE_LIMIT_EXCEEDED",
  "INTERNAL_ERROR",
  "ML_UNAVAILABLE",
  "ML_INVALID_RESPONSE",
  "ML_CONTRACT_ERROR",
  "DATASET_VERSION_UNAVAILABLE",
  "ML_DATASET_ERROR",
  "SERVICE_UNAVAILABLE",
  "DATASET_UNAVAILABLE",
  "ML_TIMEOUT",
  "JOB_TIMEOUT",
]);
export type ErrorCode = z.infer<typeof ErrorCodeSchema>;

// ---------------------------------------------------------------------------
// Warnings, Errors, Auth & Demo DTOs (openapi.yaml)
// ---------------------------------------------------------------------------

export const WarningNoticeSchema = z.object({
  code: WarningCodeSchema,
  message: z.string(),
  fields: z.array(z.string()).optional(),
});
export type WarningNotice = z.infer<typeof WarningNoticeSchema>;

export const ErrorEnvelopeSchema = z.object({
  error: z.object({
    code: ErrorCodeSchema,
    message: z.string(),
    details: z.array(z.record(z.unknown())),
    request_id: z.string().nullable().optional(),
  }),
});
export type ErrorEnvelope = z.infer<typeof ErrorEnvelopeSchema>;

export const DemoLocationSummarySchema = z.object({
  id: z.number().int(),
  code: z.string(),
  name: z.string(),
  country: z.string(),
  region: z.string(),
});
export type DemoLocationSummary = z.infer<typeof DemoLocationSummarySchema>;

export const DemoParcelPreviewSchema = z.object({
  field_id: z.string(),
  field_name: z.string(),
  location: z.object({
    latitude: z.number(),
    longitude: z.number(),
  }),
  area_hectares: z.number(),
  is_unverified_demo_parcel: z.literal(true),
  warnings: z.array(WarningNoticeSchema),
});
export type DemoParcelPreview = z.infer<typeof DemoParcelPreviewSchema>;

export const GuestSessionStartResponseSchema = z.object({
  guest_token: z.string(),
  expires_at: z.string(),
  demo_location: DemoLocationSummarySchema,
  demo_parcel: DemoParcelPreviewSchema,
});
export type GuestSessionStartResponse = z.infer<typeof GuestSessionStartResponseSchema>;

export const GuestSessionInfoSchema = z.object({
  demo_location: DemoLocationSummarySchema,
  demo_parcel: DemoParcelPreviewSchema,
  created_at: z.string(),
  expires_at: z.string(),
  limits: z.object({
    max_farms: z.number().int(),
    max_fields_per_farm: z.number().int(),
    max_analyses: z.number().int(),
    max_analysis_quarters: z.number().int(),
  }),
  usage: z.object({
    farms: z.number().int(),
    fields: z.number().int(),
    analysis_quarters: z.number().int(),
    analyses: z.number(),
  }),
});
export type GuestSessionInfo = z.infer<typeof GuestSessionInfoSchema>;

export const UserProfileSchema = z.object({
  id: z.number().int(),
  email: z.string().email(),
  full_name: z.string(),
  preferred_lang: LanguageSchema,
  created_at: z.string(),
});
export type UserProfile = z.infer<typeof UserProfileSchema>;

export const TokenPairResponseSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string(),
  token_type: z.literal("bearer"),
  expires_in: z.number().int(),
});
export type TokenPairResponse = z.infer<typeof TokenPairResponseSchema>;

export const RegisterResponseSchema = z.object({
  user: UserProfileSchema,
  access_token: z.string(),
  refresh_token: z.string(),
  token_type: z.literal("bearer"),
  expires_in: z.number().int(),
});
export type RegisterResponse = z.infer<typeof RegisterResponseSchema>;

export const BoundaryFeatureSchema = z
  .object({
    type: z.literal("Feature"),
    properties: z.record(z.unknown()),
    geometry: z.object({
      type: z.string(),
      coordinates: z.unknown(),
    }),
    bbox: z.array(z.number()),
  })
  .passthrough();
export type BoundaryFeature = z.infer<typeof BoundaryFeatureSchema>;

// ---------------------------------------------------------------------------
// Farms & Fields DTOs (Write & Read)
// ---------------------------------------------------------------------------

export const FarmWriteRequestSchema = z
  .object({
    farm_name: z.string().min(1).max(120),
    country: z.string().min(1).max(80),
    region: z.string().min(1).max(80),
    commune: z.string().max(120).nullable().optional(),
  })
  .strict();
export type FarmWriteRequest = z.infer<typeof FarmWriteRequestSchema>;

export const FarmPatchRequestSchema = FarmWriteRequestSchema.partial().strict();
export type FarmPatchRequest = z.infer<typeof FarmPatchRequestSchema>;

export const FarmPublicSchema = z.object({
  farm_id: z.string().regex(/^farm_[0-9]+$/),
  farm_name: z.string(),
  country: z.string(),
  region: z.string(),
  commune: z.string().nullable(),
  field_count: z.number().int().min(0),
  created_at: z.string(),
});
export type FarmPublic = z.infer<typeof FarmPublicSchema>;

export const FarmPageSchema = z.object({
  items: z.array(FarmPublicSchema),
  next_cursor: z.string().nullable(),
  has_more: z.boolean(),
});
export type FarmPage = z.infer<typeof FarmPageSchema>;

export const CropHistoryWriteItemSchema = z
  .object({
    season: SeasonSchema,
    year: z.number().int().min(1980).max(2100),
    planting_month: z.number().int().min(1).max(12).nullable().optional(),
    crop_id: z.string().max(64).nullable().optional(),
    crop_name_raw: z.string().max(120).nullable().optional(),
    yield_tons_per_hectare: z.number().min(0).nullable().optional(),
    notes: z.string().max(500).nullable().optional(),
  })
  .strict()
  .refine(
    (item) =>
      (typeof item.crop_id === "string" && item.crop_id.trim().length > 0) ||
      (typeof item.crop_name_raw === "string" && item.crop_name_raw.trim().length > 0),
    {
      message: "Either crop_id or crop_name_raw is required on crop history items.",
    }
  );
export type CropHistoryWriteItem = z.infer<typeof CropHistoryWriteItemSchema>;

export const FieldSoilWriteSchema = z
  .object({
    soil_type: SoilTypeSchema,
    soil_ph: z.number().min(3.0).max(11.0).nullable().optional(),
    organic_matter_percent: z.number().min(0.0).max(100.0).nullable().optional(),
    soil_test_date: z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}$/)
      .nullable()
      .optional(),
  })
  .strict();

export const FieldWaterSchema = z
  .object({
    availability: WaterAvailabilitySchema,
    source: WaterSourceSchema,
    source_other: z.string().max(200).nullable().optional(),
    irrigation_system: IrrigationSystemSchema,
  })
  .strict();

export const FieldLocationWriteSchema = z
  .object({
    latitude: z.number().min(-90).max(90),
    longitude: z.number().min(-180).max(180),
    boundary: z.record(z.unknown()).nullable().optional(),
  })
  .strict();

export const FieldWriteRequestSchema = z
  .object({
    field_id: z.string().min(1).max(64),
    field_name: z.string().min(1).max(120),
    is_unverified_demo_parcel: z.boolean().optional(),
    location: FieldLocationWriteSchema,
    area_hectares: z.number().gt(0).max(10000),
    elevation_m: z.number().min(-500).max(9000).nullable().optional(),
    soil: FieldSoilWriteSchema,
    water: FieldWaterSchema,
    crop_history: z.array(CropHistoryWriteItemSchema).min(1).max(30),
  })
  .strict();
export type FieldWriteRequest = z.infer<typeof FieldWriteRequestSchema>;

export const FieldPublicSchema = z.object({
  farm_id: z.string().regex(/^farm_[0-9]+$/),
  field_id: z.string(),
  field_name: z.string(),
  is_unverified_demo_parcel: z.boolean(),
  location: z.object({
    latitude: z.number(),
    longitude: z.number(),
    boundary: z.record(z.unknown()).nullable(),
  }),
  area_hectares: z.number(),
  elevation_m: z.number().nullable(),
  soil: z.object({
    soil_type: SoilTypeSchema,
    source: SoilSourceSchema,
    soil_ph: z.number().nullable(),
    organic_matter_percent: z.number().nullable(),
    soil_test_date: z.string().nullable(),
  }),
  water: z.object({
    availability: WaterAvailabilitySchema,
    source: WaterSourceSchema,
    source_other: z.string().nullable(),
    irrigation_system: IrrigationSystemSchema,
  }),
  warnings: z.array(WarningNoticeSchema),
});
export type FieldPublic = z.infer<typeof FieldPublicSchema>;

export const FieldDetailPublicSchema = FieldPublicSchema.extend({
  crop_history: z.array(
    z
      .object({
        season: SeasonSchema,
        year: z.number().int(),
        planting_month: z.number().int().min(1).max(12).nullable().optional(),
        crop_id: z.string().nullable().optional(),
        crop_name_raw: z.string().nullable().optional(),
        yield_tons_per_hectare: z.number().nullable().optional(),
        notes: z.string().nullable().optional(),
      })
      .passthrough()
  ),
});
export type FieldDetailPublic = z.infer<typeof FieldDetailPublicSchema>;

export const FieldPageSchema = z.object({
  items: z.array(FieldPublicSchema),
  next_cursor: z.string().nullable(),
  has_more: z.boolean(),
});
export type FieldPage = z.infer<typeof FieldPageSchema>;

// ---------------------------------------------------------------------------
// ADR-5 Write Serializer: NEVER emit soil.source or crop_history[].catalog_version,
// and NEVER fabricate non-null elevation_m when blank.
// ---------------------------------------------------------------------------

export interface FieldWriteDraft {
  field_id: string;
  field_name: string;
  is_unverified_demo_parcel?: boolean;
  location: {
    latitude: number;
    longitude: number;
    boundary?: Record<string, unknown> | null;
  };
  area_hectares: number;
  elevation_m?: number | string | null;
  soil: {
    soil_type: z.infer<typeof SoilTypeSchema>;
    source?: unknown;
    soil_ph?: number | string | null;
    organic_matter_percent?: number | string | null;
    soil_test_date?: string | null;
  };
  water: {
    availability: z.infer<typeof WaterAvailabilitySchema>;
    source: z.infer<typeof WaterSourceSchema>;
    source_other?: string | null;
    irrigation_system: z.infer<typeof IrrigationSystemSchema>;
  };
  crop_history: Array<{
    season: z.infer<typeof SeasonSchema>;
    year: number;
    planting_month?: number | null;
    crop_id?: string | null;
    crop_name_raw?: string | null;
    catalog_version?: unknown;
    yield_tons_per_hectare?: number | null;
    notes?: string | null;
  }>;
}

function toNullableNumber(val: number | string | null | undefined): number | null {
  if (val === null || val === undefined || val === "") {
    return null;
  }
  const num = typeof val === "number" ? val : Number(val);
  return Number.isFinite(num) ? num : null;
}

export function serializeFieldWriteRequest(draft: FieldWriteDraft): FieldWriteRequest {
  const isUnknownSoil = draft.soil.soil_type === "unknown";
  const payload: FieldWriteRequest = {
    field_id: draft.field_id.trim(),
    field_name: draft.field_name.trim(),
    is_unverified_demo_parcel: Boolean(draft.is_unverified_demo_parcel),
    location: {
      latitude: Number(draft.location.latitude),
      longitude: Number(draft.location.longitude),
      boundary: draft.location.boundary ?? null,
    },
    area_hectares: Number(draft.area_hectares),
    elevation_m: toNullableNumber(draft.elevation_m),
    soil: {
      soil_type: draft.soil.soil_type,
      soil_ph: isUnknownSoil ? null : toNullableNumber(draft.soil.soil_ph),
      organic_matter_percent: isUnknownSoil
        ? null
        : toNullableNumber(draft.soil.organic_matter_percent),
      soil_test_date:
        isUnknownSoil || !draft.soil.soil_test_date?.trim()
          ? null
          : draft.soil.soil_test_date.trim(),
    },
    water: {
      availability: draft.water.availability,
      source: draft.water.source,
      source_other:
        draft.water.source === "other" && draft.water.source_other?.trim()
          ? draft.water.source_other.trim()
          : null,
      irrigation_system: draft.water.irrigation_system,
    },
    crop_history: draft.crop_history.map((row) => {
      const cleanCropId = row.crop_id?.trim() ? row.crop_id.trim() : null;
      const cleanRaw = row.crop_name_raw?.trim() ? row.crop_name_raw.trim() : null;
      return {
        season: row.season,
        year: Number(row.year),
        planting_month:
          row.planting_month === null || row.planting_month === undefined
            ? null
            : Number(row.planting_month),
        crop_id: cleanCropId,
        crop_name_raw: cleanRaw,
        yield_tons_per_hectare:
          row.yield_tons_per_hectare === null || row.yield_tons_per_hectare === undefined
            ? null
            : Number(row.yield_tons_per_hectare),
        notes: row.notes?.trim() ? row.notes.trim() : null,
      };
    }),
  };

  return FieldWriteRequestSchema.parse(payload);
}

// ---------------------------------------------------------------------------
// Analysis Submit, Poll & Tolerant Reader (5.x) Result Schemas
// ---------------------------------------------------------------------------

export const PriorityWeightsSchema = z
  .object({
    water_saving: z.number().int().min(0).max(100),
    soil_improvement: z.number().int().min(0).max(100),
    income: z.number().int().min(0).max(100),
    risk_reduction: z.number().int().min(0).max(100),
    forage_value: z.number().int().min(0).max(100),
  })
  .strict();
export type PriorityWeights = z.infer<typeof PriorityWeightsSchema>;

export const PlanningSchema = z
  .object({
    start_season: SeasonSchema,
    start_year: z.number().int().min(2020).max(2100),
    horizon_seasons: z.number().int().min(1).max(6),
    cycle_mode: CycleModeSchema.default("annual_rotation"),
    planting_month: z.number().int().min(1).max(12).nullable().optional(),
    scenario_overrides: z
      .object({
        temp_delta_c: z.number().min(-5).max(10).default(0),
        precip_pct_delta: z.number().min(-80).max(100).default(0),
      })
      .strict()
      .optional(),
  })
  .strict();
export type Planning = z.infer<typeof PlanningSchema>;

export const AnalysisSubmitRequestSchema = z
  .object({
    farm_id: z.string().regex(/^farm_[0-9]+$/),
    language: LanguageSchema,
    planning: PlanningSchema,
    priorities: z
      .object({
        weights: PriorityWeightsSchema,
        market_preference: MarketPreferenceSchema,
        target_crop_ids: z.array(z.string().min(1).max(64)).max(20),
        excluded_crop_ids: z.array(z.string().min(1).max(64)).max(20),
        equipment_constraints: z.array(z.string().min(1).max(160)).max(20),
      })
      .strict(),
    field_ids: z.array(z.string().min(1).max(64)).min(1).max(10),
  })
  .strict();
export type AnalysisSubmitRequest = z.infer<typeof AnalysisSubmitRequestSchema>;

export const StrategyScoresSchema = z
  .object({
    water_efficiency: z.number().min(0).max(100),
    erosion_protection: z.number().min(0).max(100),
    organic_matter_gain: z.number().min(0).max(100),
    nitrogen_contribution: z.number().min(0).max(100),
    pest_cycle_disruption: z.number().min(0).max(100),
    income_forage_value: z.number().min(0).max(100),
    priority_fit: z.number().min(0).max(100),
    bare_field_days_per_year: z.number().int().min(0).max(365),
  })
  .passthrough();
export type StrategyScores = z.infer<typeof StrategyScoresSchema>;

export const SeasonPlanSchema = z
  .object({
    order: z.number().int().min(1).max(10),
    season: SeasonSchema,
    year: z.number().int().min(2020).max(2100),
    planting_month: z.number().int().min(1).max(12).nullable().optional(),
    crop_id: z.string().min(1),
    crop_name: z.string().min(1),
    category: CropCategorySchema,
    role: CropRoleSchema,
    selection_status: SelectionStatusSchema,
    notes: z.string().nullable().optional(),
  })
  .passthrough();
export type SeasonPlan = z.infer<typeof SeasonPlanSchema>;

export const BareFieldPeriodSchema = z
  .object({
    start_month: z.number().int().min(1).max(12),
    end_month: z.number().int().min(1).max(12),
    evidence: z.string().min(1),
  })
  .passthrough();
export type BareFieldPeriod = z.infer<typeof BareFieldPeriodSchema>;

export const StressPeriodSchema = z
  .object({
    type: StressTypeSchema,
    months: z.array(z.number().int().min(1).max(12)).min(1),
    severity: SeverityLevelSchema,
    evidence: z.string().min(1),
  })
  .passthrough();
export type StressPeriod = z.infer<typeof StressPeriodSchema>;

export const FieldInsightsSchema = z
  .object({
    bare_field_periods: z.array(BareFieldPeriodSchema),
    stress_periods: z.array(StressPeriodSchema),
    climate_trend_summary: z.string().min(1),
  })
  .passthrough();
export type FieldInsights = z.infer<typeof FieldInsightsSchema>;

export const ReasonItemSchema = z
  .object({
    code: z.string().min(1),
    text: z.string().min(1),
    params: z.record(z.unknown()),
  })
  .passthrough();
export type ReasonItem = z.infer<typeof ReasonItemSchema>;

export const EvidenceItemSchema = z
  .object({
    data_source: DataSourceSchema,
    source_mission: z.string().nullable().optional(),
    parameter: EvidenceParameterSchema,
    observed_value: z.union([z.number(), z.string(), z.boolean()]),
    unit: EvidenceUnitSchema.optional(),
    period: z.string().nullable().optional(),
    derived: z.boolean().default(false),
    interpretation: z.string().min(1),
  })
  .passthrough();
export type EvidenceItem = z.infer<typeof EvidenceItemSchema>;

export const BenefitItemSchema = z
  .object({
    benefit_id: z.string().min(1),
    title: z.string().min(1),
    description: z.string().min(1),
  })
  .passthrough();
export type BenefitItem = z.infer<typeof BenefitItemSchema>;

export const RiskItemSchema = z
  .object({
    risk_id: z.string().min(1),
    title: z.string().min(1),
    description: z.string().min(1),
    severity: SeverityLevelSchema,
    likelihood: SeverityLevelSchema.optional(),
    mitigation: z.string().min(1),
  })
  .passthrough();
export type RiskItem = z.infer<typeof RiskItemSchema>;

export const ExplanationSchema = z
  .object({
    reasons: z.array(ReasonItemSchema),
    evidence: z.array(EvidenceItemSchema),
    benefits: z.array(BenefitItemSchema),
    risks: z.array(RiskItemSchema),
    assumptions: z.array(z.string()),
    information_gaps: z.array(z.string()),
    needs_local_review: z.array(z.string()),
  })
  .passthrough();
export type Explanation = z.infer<typeof ExplanationSchema>;

export const StrategySchema = z
  .object({
    strategy_id: z.string().min(1),
    name: z.string().min(1),
    is_existing_rotation: z.boolean(),
    description: z.string().min(1),
    seasons: z.array(SeasonPlanSchema).min(1).max(10),
    scores: StrategyScoresSchema,
    confidence: SeverityLevelSchema,
    explanation: ExplanationSchema,
  })
  .passthrough();
export type Strategy = z.infer<typeof StrategySchema>;

export const RequestedCropEvaluationSchema = z
  .object({
    requested_crop_id: z.string().min(1),
    outcome: z.enum(["included", "replaced", "excluded"]),
    included_in_strategy_ids: z.array(z.string()),
    replaced_by_crop_id: z.string().nullable().optional(),
    explanation: z.string().min(1),
    comparison: z.array(z.record(z.unknown())).optional(),
    evidence: z.array(EvidenceItemSchema).optional(),
  })
  .passthrough();
export type RequestedCropEvaluation = z.infer<typeof RequestedCropEvaluationSchema>;

export const DataQualitySchema = z
  .object({
    completeness_score: z.number().min(0).max(1).nullable().optional(),
    confidence_note: z.string().nullable().optional(),
    missing_data: z.array(z.string()),
    warnings: z.array(z.string()),
    limitations: z.array(z.string()),
  })
  .passthrough();
export type DataQuality = z.infer<typeof DataQualitySchema>;

export const FieldPlanSchema = z
  .object({
    field_id: z.string().min(1),
    field_name: z.string().min(1),
    status: z.enum(["ok", "partial"]),
    partial_reason: z.string().nullable().optional(),
    field_insights: FieldInsightsSchema,
    strategies: z.array(StrategySchema).max(5),
    suggested_strategy_id: z.string().min(1).nullable(),
    requested_crop_results: z.array(RequestedCropEvaluationSchema),
    data_quality: DataQualitySchema,
  })
  .passthrough()
  .superRefine((plan, ctx) => {
    if (plan.status === "ok") {
      if (!plan.suggested_strategy_id) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "suggested_strategy_id is required when FieldPlan status is ok",
          path: ["suggested_strategy_id"],
        });
      }
      if (plan.strategies.length < 3 || plan.strategies.length > 5) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "ok FieldPlan must contain 3 to 5 strategies",
          path: ["strategies"],
        });
      }
      const baselineCount = plan.strategies.filter((s) => s.is_existing_rotation).length;
      if (baselineCount !== 1) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "ok FieldPlan must contain exactly 1 baseline strategy",
          path: ["strategies"],
        });
      }
    } else if (!plan.partial_reason || plan.partial_reason.trim().length === 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "partial_reason is required when FieldPlan status is partial",
        path: ["partial_reason"],
      });
    }
  });
export type FieldPlan = z.infer<typeof FieldPlanSchema>;

export const AnalysisResultSchema = z
  .object({
    schema_version: SchemaVersionSchema,
    request_id: z.string().uuid(),
    dataset_version_used: z.string().min(1),
    generated_at: z.string(),
    status: z.enum(["ok", "partial"]),
    language: LanguageSchema,
    ml_engine_version: z.string().min(1),
    overall_summary: z.string().min(1),
    disclaimer: z.string().min(1),
    field_plans: z.array(FieldPlanSchema).min(1),
    data_quality: DataQualitySchema,
  })
  .passthrough()
  .superRefine((res, ctx) => {
    if ("fields" in res || "crops" in res) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "AnalysisResult must not contain root input/catalog keys",
      });
    }
    if (res.status === "ok") {
      res.field_plans.forEach((fp, idx) => {
        if (fp.status !== "ok") {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: "All field_plans must be ok when AnalysisResult status is ok",
            path: ["field_plans", idx, "status"],
          });
        }
      });
    }
  });
export type AnalysisResult = z.infer<typeof AnalysisResultSchema>;

export const DegradedModeMetadataSchema = z.object({
  kind: z.literal("last_good_replay"),
  stale: z.literal(true),
  source_analysis_id: z.string().regex(/^analysis_[0-9a-f]{12}$/),
  created_at: z.string(),
  dataset_version: z.string(),
  age_seconds: z.number().int().min(0),
});
export type DegradedModeMetadata = z.infer<typeof DegradedModeMetadataSchema>;

export const AnalysisQueuedResponseSchema = z.object({
  request_id: z.string().uuid(),
  status: z.literal("pending"),
  poll_url: z.string(),
  poll_interval_ms: z.number().int(),
  warnings: z.array(WarningNoticeSchema),
});
export type AnalysisQueuedResponse = z.infer<typeof AnalysisQueuedResponseSchema>;

export const AnalysisEnvelopeSchema = z.object({
  analysis_id: z.string().regex(/^analysis_[0-9a-f]{12}$/),
  request_id: z.string().uuid(),
  status: z.enum(["ok", "partial"]),
  dataset_version: z.string(),
  warnings: z.array(WarningNoticeSchema),
  degraded_mode: DegradedModeMetadataSchema.nullable(),
  result: AnalysisResultSchema,
});
export type AnalysisEnvelope = z.infer<typeof AnalysisEnvelopeSchema>;

export const PollErrorObjectSchema = z.object({
  code: ErrorCodeSchema,
  http_equivalent: z.number().int(),
  message: z.string(),
  details: z.array(z.record(z.unknown())),
});
export type PollErrorObject = z.infer<typeof PollErrorObjectSchema>;

export const AnalysisPollEnvelopeSchema = z.object({
  request_id: z.string().uuid(),
  status: z.enum(["pending", "running", "ok", "partial", "failed", "cancelled"]),
  poll_interval_ms: z.number().int().nullable(),
  analysis_id: z
    .string()
    .regex(/^analysis_[0-9a-f]{12}$/)
    .nullable(),
  warnings: z.array(WarningNoticeSchema),
  degraded_mode: DegradedModeMetadataSchema.nullable(),
  error: PollErrorObjectSchema.nullable(),
  result: AnalysisResultSchema.nullable(),
});
export type AnalysisPollEnvelope = z.infer<typeof AnalysisPollEnvelopeSchema>;

export const FarmAnalysisSummarySchema = z.object({
  request_id: z.string().uuid(),
  analysis_id: z.string().nullable(),
  status: z.enum(["pending", "running", "ok", "partial", "failed", "cancelled"]),
  language: LanguageSchema,
  catalog_version: z.string(),
  dataset_version: z.string().nullable(),
  ml_engine_version: z.string().nullable(),
  warnings: z.array(WarningNoticeSchema),
  created_at: z.string(),
  duration_ms: z.number().int().nullable(),
});
export type FarmAnalysisSummary = z.infer<typeof FarmAnalysisSummarySchema>;

export const FarmAnalysesPageSchema = z.object({
  items: z.array(FarmAnalysisSummarySchema),
  next_cursor: z.string().nullable(),
  has_more: z.boolean(),
});
export type FarmAnalysesPage = z.infer<typeof FarmAnalysesPageSchema>;

// ---------------------------------------------------------------------------
// Catalog, Health & Export DTOs
// ---------------------------------------------------------------------------

export const CropItemSchema = z
  .object({
    crop_id: z.string().min(1),
    display_name: z.string().min(1).optional(),
    names: z
      .object({
        en: z.string().min(1),
        fr: z.string().min(1),
        ar: z.string().min(1),
      })
      .passthrough(),
    category: CropCategorySchema,
    roles: z.array(CropRoleSchema).min(1),
    family: z.string().min(1),
  })
  .passthrough();
export type CropItem = z.infer<typeof CropItemSchema>;

export const CatalogPageSchema = z
  .object({
    catalog_version: z.string(),
    synced_at: z.string(),
    items: z.array(CropItemSchema),
    next_cursor: z.string().nullable(),
    has_more: z.boolean(),
  })
  .passthrough();
export type CatalogPage = z.infer<typeof CatalogPageSchema>;

export const HealthResponseSchema = z.object({
  status: z.enum(["ok", "degraded"]),
  db: z.object({
    connected: z.boolean(),
    postgis_version: z.string(),
  }),
  dataset: z.object({
    active_version: z.string().nullable(),
    loaded_at: z.string().nullable(),
  }),
  catalog: z.object({
    version: z.string().nullable(),
    synced_at: z.string().nullable(),
  }),
  worker_queue: z.object({
    active_workers: z.number().int(),
    pending_jobs: z.number().int(),
    stale_leases: z.number().int(),
  }),
  ml_service: z.object({
    reachable: z.boolean(),
    circuit_breaker: z.enum(["closed", "open", "half_open"]),
    consecutive_failures: z.number().int(),
    ml_engine_version: z.string().nullable(),
  }),
});
export type HealthResponse = z.infer<typeof HealthResponseSchema>;

export const UserDataExportSchema = z.object({
  exported_at: z.string(),
  user: UserProfileSchema,
  farms: z.array(FarmPublicSchema),
  fields: z.array(FieldDetailPublicSchema),
  analysis_requests: z.array(z.record(z.unknown())),
  analysis_results: z.array(z.record(z.unknown())),
  analysis_selections: z.array(z.record(z.unknown())),
});
export type UserDataExport = z.infer<typeof UserDataExportSchema>;

export const SelectionPatchResponseSchema = z.object({
  analysis_id: z.string().regex(/^analysis_[0-9a-f]{12}$/),
  field_id: z.string(),
  strategy_id: z.string(),
  selection_status: z.enum(["selected", "rejected"]),
});
export type SelectionPatchResponse = z.infer<typeof SelectionPatchResponseSchema>;
