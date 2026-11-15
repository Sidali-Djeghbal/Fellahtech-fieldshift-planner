import {
  createFarm,
  createField,
  listFarms,
  listFields,
  pollAnalysisRequest,
  replaceField,
  startGuestSession,
  submitAnalysis,
} from "@/lib/api/endpoints";
import type {
  AnalysisEnvelope,
  AnalysisPollEnvelope,
  AnalysisSubmitRequest,
  CropCategory,
  CropItem,
  FarmPublic,
  FieldDetailPublic,
  FieldPlan,
  FieldWriteDraft,
  Language,
  PriorityWeights,
  SelectionStatus,
  SeverityLevel,
  Strategy,
} from "@/lib/schemas";
import { useAppStore } from "@/store/useAppStore";

export const CATEGORY_STYLE_MAP: Record<
  CropCategory,
  { badgeClass: string; borderClass: string; dotClass: string }
> = {
  cereals: {
    badgeClass:
      "bg-amber-50 text-amber-900 ring-1 ring-amber-600/25 dark:bg-amber-500/15 dark:text-amber-200 dark:ring-amber-400/30",
    borderClass: "border-amber-600/25 dark:border-amber-400/25",
    dotClass: "bg-amber-600 dark:bg-amber-400",
  },
  legumes: {
    badgeClass:
      "bg-emerald-50 text-emerald-800 ring-1 ring-emerald-600/25 dark:bg-[#22C55E]/15 dark:text-[#86EFAC] dark:ring-[#4ADE80]/30",
    borderClass: "border-emerald-600/25 dark:border-[#4ADE80]/25",
    dotClass: "bg-[#15803D] dark:bg-[#22C55E]",
  },
  oilseeds: {
    badgeClass:
      "bg-yellow-50 text-yellow-900 ring-1 ring-yellow-600/25 dark:bg-yellow-500/15 dark:text-yellow-200 dark:ring-yellow-400/30",
    borderClass: "border-yellow-600/25 dark:border-yellow-400/25",
    dotClass: "bg-yellow-600 dark:bg-yellow-400",
  },
  vegetables: {
    badgeClass:
      "bg-teal-50 text-teal-900 ring-1 ring-teal-600/25 dark:bg-teal-500/15 dark:text-teal-200 dark:ring-teal-400/30",
    borderClass: "border-teal-600/25 dark:border-teal-400/25",
    dotClass: "bg-teal-600 dark:bg-teal-400",
  },
  forage: {
    badgeClass:
      "bg-lime-50 text-lime-900 ring-1 ring-lime-600/25 dark:bg-lime-500/15 dark:text-lime-200 dark:ring-lime-400/30",
    borderClass: "border-lime-600/25 dark:border-lime-400/25",
    dotClass: "bg-lime-600 dark:bg-lime-400",
  },
  cover_crops: {
    badgeClass:
      "bg-emerald-50 text-emerald-900 ring-1 ring-emerald-700/25 dark:bg-emerald-500/15 dark:text-emerald-200 dark:ring-emerald-400/30",
    borderClass: "border-emerald-700/25 dark:border-emerald-400/25",
    dotClass: "bg-emerald-600 dark:bg-emerald-400",
  },
  fallow: {
    badgeClass:
      "bg-[#111813]/5 text-[#3E4C42] ring-1 ring-[#111813]/15 dark:bg-white/10 dark:text-[#D1DBD3] dark:ring-white/15",
    borderClass: "border-[#111813]/15 dark:border-white/15",
    dotClass: "bg-[#58685C] dark:bg-[#9CA89E]",
  },
};

export const SEVERITY_STYLE_MAP: Record<
  SeverityLevel,
  { pillClass: string; borderClass: string; surfaceClass: string; dotClass: string }
> = {
  low: {
    pillClass:
      "bg-emerald-50 text-emerald-800 ring-1 ring-emerald-600/25 dark:bg-[#22C55E]/15 dark:text-[#86EFAC] dark:ring-[#4ADE80]/30",
    borderClass: "border-emerald-600/25 dark:border-[#4ADE80]/25",
    surfaceClass: "bg-emerald-500/10 ring-1 ring-emerald-600/20 dark:bg-[#22C55E]/10 dark:ring-[#4ADE80]/20",
    dotClass: "bg-[#15803D] dark:bg-[#22C55E]",
  },
  medium: {
    pillClass:
      "bg-amber-50 text-amber-900 ring-1 ring-amber-600/25 dark:bg-[#F59E0B]/15 dark:text-[#FCD34D] dark:ring-[#F59E0B]/30",
    borderClass: "border-amber-600/25 dark:border-[#F59E0B]/25",
    surfaceClass: "bg-amber-500/10 ring-1 ring-amber-600/20 dark:bg-[#F59E0B]/10 dark:ring-[#F59E0B]/20",
    dotClass: "bg-amber-600 dark:bg-[#F59E0B]",
  },
  high: {
    pillClass:
      "bg-red-50 text-red-800 ring-1 ring-red-600/25 dark:bg-red-500/15 dark:text-red-300 dark:ring-red-400/30",
    borderClass: "border-red-600/25 dark:border-red-400/25",
    surfaceClass: "bg-red-500/10 ring-1 ring-red-600/20 dark:bg-red-500/10 dark:ring-red-400/20",
    dotClass: "bg-red-600 dark:bg-red-400",
  },
};

export const STRATEGY_SCORE_KEYS: Array<
  | "priority_fit"
  | "water_efficiency"
  | "erosion_protection"
  | "organic_matter_gain"
  | "nitrogen_contribution"
  | "pest_cycle_disruption"
  | "income_forage_value"
> = [
  "priority_fit",
  "water_efficiency",
  "erosion_protection",
  "organic_matter_gain",
  "nitrogen_contribution",
  "pest_cycle_disruption",
  "income_forage_value",
];

export const WEIGHT_PRESET_MAP: Record<
  "balanced" | "water" | "income",
  PriorityWeights
> = {
  balanced: {
    water_saving: 30,
    soil_improvement: 25,
    income: 20,
    risk_reduction: 15,
    forage_value: 10,
  },
  water: {
    water_saving: 40,
    soil_improvement: 25,
    income: 15,
    risk_reduction: 15,
    forage_value: 5,
  },
  income: {
    water_saving: 15,
    soil_improvement: 15,
    income: 45,
    risk_reduction: 15,
    forage_value: 10,
  },
};

/** Derive effective selection status for a strategy from backend-merged season statuses. */
export function getStrategySelectionStatus(strategy: Strategy): SelectionStatus {
  const explicit = strategy.seasons.find((s) => s.selection_status)?.selection_status;
  if (explicit === "selected" || explicit === "rejected" || explicit === "suggested") {
    return explicit;
  }
  return "suggested";
}

const BUILTIN_CROP_NAMES: Record<string, Record<Language, string>> = {
  durum_wheat: { en: "Durum Wheat", fr: "Blé dur", ar: "قمح صلب" },
  soft_wheat: { en: "Soft Wheat", fr: "Blé tendre", ar: "قمح لين" },
  barley: { en: "Barley", fr: "Orge", ar: "شعير" },
  chickpea: { en: "Winter Chickpea", fr: "Pois chiche d'hiver", ar: "حمص شتوي" },
  chickpea_spring: { en: "Spring Chickpea", fr: "Pois chiche de printemps", ar: "حمص ربيعي" },
  vetch: { en: "Vetch-Oat", fr: "Vesce-Avoine", ar: "بيقية-شوفان" },
  vetch_forage: { en: "Vetch Forage", fr: "Vesce fourragère", ar: "بيقية علفية" },
  sunflower: { en: "Sunflower", fr: "Tournesol", ar: "دوار الشمس" },
  fallow: { en: "Bare Fallow", fr: "Jachère", ar: "أرض بور" },
  fava_bean: { en: "Fava Bean", fr: "Fève", ar: "فول" },
  lentil: { en: "Lentil", fr: "Lentille", ar: "عدس" },
  oats_forage: { en: "Oats Forage", fr: "Avoine fourragère", ar: "شوفان علفي" },
  berseem_clover: { en: "Berseem Clover", fr: "Trèfle d'Alexandrie", ar: "برسيم" },
  tomato: { en: "Processing Tomato", fr: "Tomate industrielle", ar: "طماطم صناعية" },
  potato: { en: "Potato", fr: "Pomme de terre", ar: "بطاطس" },
  olive: { en: "Olive", fr: "Olivier", ar: "زيتون" },
};

/** Resolve localized crop label from catalog (with built-in Guelma crop fallback). */
export function resolveCropDisplayName(
  cropId: string | null | undefined,
  fallbackName: string | null | undefined,
  catalogMap: Map<string, CropItem> | undefined,
  lang: Language
): string {
  const key = (cropId ?? "").trim();
  const item = key && catalogMap ? catalogMap.get(key) : undefined;
  if (item) {
    return item.names[lang] || item.display_name || item.names.en || fallbackName || key;
  }
  const builtin = key ? BUILTIN_CROP_NAMES[key] : undefined;
  if (builtin) {
    return builtin[lang] || builtin.en || fallbackName || key;
  }
  return (fallbackName ?? "").trim() || key || "—";
}

/** Match an active workspace field_id cleanly inside an AnalysisEnvelope's field_plans. */
export function findFieldPlanForField(
  envelope: AnalysisEnvelope | null | undefined,
  activeFieldId: string | null | undefined
): FieldPlan | null {
  if (!envelope || envelope.result.field_plans.length === 0) return null;
  if (activeFieldId) {
    const exact = envelope.result.field_plans.find((fp) => fp.field_id === activeFieldId);
    if (exact) return exact;
  }
  return envelope.result.field_plans[0] ?? null;
}

/**
 * Optimistically apply a selection decision in memory mirroring backend
 * PATCH /analysis/{analysis_id}/selection exclusivity semantics.
 */
export function applySelectionToEnvelope(
  envelope: AnalysisEnvelope,
  fieldId: string,
  strategyId: string,
  nextStatus: "selected" | "rejected"
): AnalysisEnvelope {
  const copy = structuredClone(envelope);
  copy.result.field_plans = copy.result.field_plans.map((fp) => {
    if (fp.field_id !== fieldId) return fp;
    return {
      ...fp,
      strategies: fp.strategies.map((strat) => {
        const curStatus = getStrategySelectionStatus(strat);
        if (strat.strategy_id === strategyId) {
          return {
            ...strat,
            seasons: strat.seasons.map((s) => ({
              ...s,
              selection_status: nextStatus,
            })),
          };
        }
        if (nextStatus === "selected" && curStatus === "selected") {
          return {
            ...strat,
            seasons: strat.seasons.map((s) => ({
              ...s,
              selection_status: "suggested",
            })),
          };
        }
        return strat;
      }),
    };
  });
  return copy;
}

/** Convert a workspace FieldDetailPublic record into API FieldWriteDraft payload. */
export function fieldDetailToWriteDraft(field: FieldDetailPublic): FieldWriteDraft {
  return {
    field_id: field.field_id,
    field_name: field.field_name,
    is_unverified_demo_parcel: Boolean(field.is_unverified_demo_parcel),
    location: {
      latitude: field.location.latitude,
      longitude: field.location.longitude,
      boundary: field.location.boundary ?? null,
    },
    area_hectares: field.area_hectares,
    elevation_m: field.elevation_m ?? "",
    soil: {
      soil_type: field.soil.soil_type,
      soil_ph: field.soil.soil_ph ?? "",
      organic_matter_percent: field.soil.organic_matter_percent ?? "",
      soil_test_date: field.soil.soil_test_date ?? "",
    },
    water: {
      availability: field.water.availability,
      source: field.water.source,
      source_other: field.water.source_other ?? "",
      irrigation_system: field.water.irrigation_system,
    },
    crop_history:
      field.crop_history.length > 0
        ? field.crop_history.map((h) => ({
            season: h.season,
            year: h.year,
            planting_month: h.planting_month ?? null,
            crop_id: h.crop_id ?? null,
            crop_name_raw: h.crop_name_raw ?? null,
            yield_tons_per_hectare: h.yield_tons_per_hectare ?? null,
            notes: h.notes ?? null,
          }))
        : [
            {
              season: "autumn",
              year: new Date().getFullYear() - 1,
              planting_month: 11,
              crop_id: "durum_wheat",
            },
          ],
  };
}

/**
 * Ensures an API caller session exists and reconciles local workspace farm/fields
 * with backend storage before submitting an analysis job.
 */
export async function syncWorkspaceFarmAndFields(params: {
  farm: FarmPublic;
  fields: FieldDetailPublic[];
  onReconcileFarmId: (oldFarmId: string, nextFarm: FarmPublic) => void;
}): Promise<{ farmId: string; syncedFieldIds: string[] }> {
  const store = useAppStore.getState();
  if (store.authMode === "none") {
    const guest = await startGuestSession(1);
    store.setGuestSession({
      guestToken: guest.guest_token,
      expiresAt: guest.expires_at,
    });
  }

  const farmsPage = await listFarms();
  let remoteFarm = farmsPage.items.find(
    (item) =>
      item.farm_id === params.farm.farm_id &&
      item.farm_name.trim().toLowerCase() === params.farm.farm_name.trim().toLowerCase()
  );

  if (!remoteFarm) {
    remoteFarm = await createFarm({
      farm_name: params.farm.farm_name,
      country: params.farm.country || "Algeria",
      region: params.farm.region || "Guelma",
      commune: params.farm.commune ?? null,
    });
    if (remoteFarm.farm_id !== params.farm.farm_id) {
      params.onReconcileFarmId(params.farm.farm_id, remoteFarm);
    }
  }

  const existingFieldsPage = await listFields(remoteFarm.farm_id);
  const existingIds = new Set(existingFieldsPage.items.map((f) => f.field_id));
  const syncedFieldIds: string[] = [];

  for (const field of params.fields) {
    const draft = fieldDetailToWriteDraft(field);
    if (existingIds.has(field.field_id)) {
      await replaceField(remoteFarm.farm_id, field.field_id, draft);
    } else {
      await createField(remoteFarm.farm_id, draft);
    }
    syncedFieldIds.push(field.field_id);
  }

  return {
    farmId: remoteFarm.farm_id,
    syncedFieldIds,
  };
}

/**
 * Submits an analysis job and polls asynchronously until terminal state or abort.
 */
export async function submitAndPollWorkspaceAnalysis(params: {
  request: AnalysisSubmitRequest;
  signal: AbortSignal;
  onQueued: (requestId: string) => void;
  onPollUpdate: (poll: AnalysisPollEnvelope) => void;
}): Promise<AnalysisPollEnvelope> {
  const idempotencyKey =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

  const queued = await submitAnalysis(params.request, idempotencyKey);
  params.onQueued(queued.request_id);

  let delayMs = Math.max(250, queued.poll_interval_ms || 450);

  while (!params.signal.aborted) {
    await new Promise<void>((resolve) => {
      const timer = setTimeout(resolve, delayMs);
      params.signal.addEventListener(
        "abort",
        () => {
          clearTimeout(timer);
          resolve();
        },
        { once: true }
      );
    });

    if (params.signal.aborted) {
      break;
    }

    const poll = await pollAnalysisRequest(queued.request_id);
    params.onPollUpdate(poll);

    if (
      poll.status === "ok" ||
      poll.status === "partial" ||
      poll.status === "failed" ||
      poll.status === "cancelled"
    ) {
      return poll;
    }

    delayMs = Math.max(250, poll.poll_interval_ms || 450);
  }

  return {
    request_id: queued.request_id,
    status: "cancelled",
    poll_interval_ms: null,
    analysis_id: null,
    warnings: queued.warnings,
    degraded_mode: null,
    error: null,
    result: null,
  };
}

/** Computes consistent score progress bar tone using botanical status hierarchy. */
export function getScoreProgressClass(
  score: number,
  isPriorityFit = false,
  theme: "light" | "dark" = "light"
): string {
  if (isPriorityFit) {
    return theme === "dark"
      ? "bg-gradient-to-r from-[#22C55E] to-[#86EFAC]"
      : "bg-gradient-to-r from-[#0B4B2E] to-[#10B981]";
  }
  if (theme === "dark") {
    if (score >= 75) return "bg-[#22C55E]";
    if (score >= 50) return "bg-[#4ADE80]";
    return "bg-amber-500";
  }
  if (score >= 75) return "bg-[#0B4B2E]";
  if (score >= 50) return "bg-emerald-500";
  return "bg-amber-500";
}
