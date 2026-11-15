import { SEASON_LABELS } from "@/lib/i18n";
import type { Language, PriorityWeights, Season, SoilType } from "@/lib/schemas";

export type WeightKey = keyof PriorityWeights;

export const WEIGHT_KEYS: WeightKey[] = [
  "water_saving",
  "soil_improvement",
  "income",
  "risk_reduction",
  "forage_value",
];

export const NORTHERN_HEMISPHERE_SEASON_MONTHS: Record<Season, readonly number[]> = {
  winter: [12, 1, 2],
  spring: [3, 4, 5],
  summer: [6, 7, 8],
  autumn: [9, 10, 11],
};

// ---------------------------------------------------------------------------
// INPUT-01: Priority Weights Sum Strictly to 100
// ---------------------------------------------------------------------------

export interface WeightsValidationResult {
  valid: boolean;
  sum: number;
  remaining: number;
  error?: string;
}

export function validateWeightsSum(
  weights: PriorityWeights,
  lang: Language = "en"
): WeightsValidationResult {
  const values = WEIGHT_KEYS.map((k) => weights[k]);
  const allIntegers = values.every(
    (v) => Number.isInteger(v) && v >= 0 && v <= 100
  );
  const sum = values.reduce((acc, v) => acc + v, 0);
  const remaining = 100 - sum;

  if (!allIntegers) {
    return {
      valid: false,
      sum,
      remaining,
      error:
        lang === "fr"
          ? "Tous les poids de priorité doivent être des entiers entre 0 et 100."
          : lang === "ar"
            ? "يجب أن تكون جميع أوزان الأولوية أعداداً صحيحة بين 0 و100."
            : "All priority weights must be integers between 0 and 100.",
    };
  }
  if (sum !== 100) {
    return {
      valid: false,
      sum,
      remaining,
      error:
        lang === "fr"
          ? `La somme des poids doit être exactement égale à 100 (actuellement ${sum}).`
          : lang === "ar"
            ? `يجب أن يكون مجموع أوزان الأولوية مساوياً لـ 100 تماماً (المجموع الحالي ${sum}).`
            : `Priority weights must sum strictly to 100 (currently ${sum}).`,
    };
  }
  return { valid: true, sum: 100, remaining: 0 };
}

export function balanceRemainingWeights(
  weights: PriorityWeights,
  anchorKey: WeightKey = "income"
): PriorityWeights {
  const sum = WEIGHT_KEYS.reduce((acc, k) => acc + Math.round(weights[k]), 0);
  const diff = 100 - sum;
  if (diff === 0) return { ...weights };

  const next = { ...weights };
  const targetVal = next[anchorKey] + diff;
  if (targetVal >= 0 && targetVal <= 100) {
    next[anchorKey] = targetVal;
    return next;
  }

  // Spread remaining delta proportionally across keys within [0, 100]
  let left = diff;
  for (const key of WEIGHT_KEYS) {
    if (left === 0) break;
    const room = left > 0 ? 100 - next[key] : next[key];
    const step = Math.min(Math.abs(left), room);
    next[key] += left > 0 ? step : -step;
    left += left > 0 ? -step : step;
  }
  return next;
}

export function autoBalanceWeights(
  weights: PriorityWeights,
  changedKey: WeightKey,
  newValue: number
): PriorityWeights {
  const clamped = Math.max(0, Math.min(100, Math.round(newValue)));
  const others = WEIGHT_KEYS.filter((k) => k !== changedKey);
  const remainingTarget = 100 - clamped;
  const currentOthersSum = others.reduce((acc, k) => acc + weights[k], 0);

  const next: PriorityWeights = { ...weights, [changedKey]: clamped };

  if (currentOthersSum === 0) {
    const base = Math.floor(remainingTarget / others.length);
    let rem = remainingTarget - base * others.length;
    for (const k of others) {
      next[k] = base + (rem > 0 ? 1 : 0);
      if (rem > 0) rem--;
    }
    return next;
  }

  let allocated = 0;
  others.forEach((k, idx) => {
    if (idx === others.length - 1) {
      next[k] = Math.max(0, remainingTarget - allocated);
    } else {
      const proportional = Math.round((weights[k] / currentOthersSum) * remainingTarget);
      next[k] = Math.max(0, Math.min(remainingTarget - allocated, proportional));
      allocated += next[k];
    }
  });
  return next;
}

// ---------------------------------------------------------------------------
// INPUT-02: Target & Excluded Crops Must Be Disjoint
// ---------------------------------------------------------------------------

export interface DisjointCropsValidationResult {
  valid: boolean;
  overlappingIds: string[];
  error?: string;
}

export function validateDisjointCrops(
  targetCropIds: string[],
  excludedCropIds: string[],
  lang: Language = "en"
): DisjointCropsValidationResult {
  const excludedSet = new Set(excludedCropIds.map((id) => id.trim()).filter(Boolean));
  const overlappingIds = Array.from(
    new Set(targetCropIds.map((id) => id.trim()).filter((id) => excludedSet.has(id)))
  );

  if (overlappingIds.length > 0) {
    const joined = overlappingIds.join(", ");
    return {
      valid: false,
      overlappingIds,
      error:
        lang === "fr"
          ? `Les cultures cibles et exclues ne peuvent pas se chevaucher : ${joined}.`
          : lang === "ar"
            ? `لا يمكن أن تتداخل المحاصيل المستهدفة والمستبعدة: ${joined}.`
            : `Target and excluded crops cannot overlap: ${joined}.`,
    };
  }
  return { valid: true, overlappingIds: [] };
}

// ---------------------------------------------------------------------------
// INPUT-03: Northern Hemisphere Season <-> Planting Month Consistency
// ---------------------------------------------------------------------------

export interface SeasonMonthValidationResult {
  valid: boolean;
  allowedMonths: readonly number[];
  error?: string;
}

export function validateSeasonMonthConsistency(
  season: Season,
  plantingMonth: number | null | undefined,
  latitude: number = 36.52,
  lang: Language = "en"
): SeasonMonthValidationResult {
  const allowedMonths = NORTHERN_HEMISPHERE_SEASON_MONTHS[season];
  if (plantingMonth === null || plantingMonth === undefined) {
    return { valid: true, allowedMonths };
  }
  if (!Number.isInteger(plantingMonth) || plantingMonth < 1 || plantingMonth > 12) {
    return {
      valid: false,
      allowedMonths,
      error:
        lang === "fr"
          ? `Le mois de semis doit être compris entre 1 et 12 (reçu ${plantingMonth}).`
          : lang === "ar"
            ? `يجب أن يكون شهر البذر بين 1 و12 (تم إدخال ${plantingMonth}).`
            : `Planting month must be between 1 and 12 (received ${plantingMonth}).`,
    };
  }
  if (latitude >= 0 && !allowedMonths.includes(plantingMonth)) {
    const sLabel = SEASON_LABELS[lang]?.[season] ?? season;
    const monthsText = allowedMonths.join(", ");
    return {
      valid: false,
      allowedMonths,
      error:
        lang === "fr"
          ? `Le mois ${plantingMonth} ne correspond pas à la saison ${sLabel} dans l'hémisphère Nord (attendu : ${monthsText}).`
          : lang === "ar"
            ? `الشهر ${plantingMonth} لا يطابق فصل ${sLabel} في نصف الكرة الشمالي (الأشهر المتوقعة: ${monthsText}).`
            : `Month ${plantingMonth} does not match ${sLabel} in Northern Hemisphere (expected: ${monthsText}).`,
    };
  }
  return { valid: true, allowedMonths };
}

// ---------------------------------------------------------------------------
// ADR-5: USDA Soil Texture Classifier Helper (Exact Precedence)
// Supports g/kg (0..1000) or % (0..100)
//   clay >= 400 -> "clay"
//   else silt >= 500 -> "silty"
//   else sand >= 700 -> "sandy"
//   else -> "loamy"
// ---------------------------------------------------------------------------

export interface UsdaTextureInput {
  clay: number;
  silt: number;
  sand: number;
  unit?: "g_per_kg" | "percent";
}

export function classifyUsdaSoilTexture(
  input: UsdaTextureInput
): Exclude<SoilType, "unknown"> {
  const unit =
    input.unit ??
    (input.clay + input.silt + input.sand <= 105 ? "percent" : "g_per_kg");
  const factor = unit === "percent" ? 10 : 1;

  const clayGkg = input.clay * factor;
  const siltGkg = input.silt * factor;
  const sandGkg = input.sand * factor;

  if (clayGkg >= 400) return "clay";
  if (siltGkg >= 500) return "silty";
  if (sandGkg >= 700) return "sandy";
  return "loamy";
}

// ---------------------------------------------------------------------------
// Aggregate Pre-Submission Guard for AnalysisSubmitRequest
// ---------------------------------------------------------------------------

export function validateAnalysisPreSubmit(params: {
  weights: PriorityWeights;
  targetCropIds: string[];
  excludedCropIds: string[];
  startSeason: Season;
  plantingMonth: number | null | undefined;
  latitude: number;
  cropHistory: Array<{ season: Season; planting_month?: number | null }>;
  lang?: Language;
}): { valid: boolean; errors: string[] } {
  const lang = params.lang ?? "en";
  const errors: string[] = [];

  const wCheck = validateWeightsSum(params.weights, lang);
  if (!wCheck.valid && wCheck.error) errors.push(wCheck.error);

  const cCheck = validateDisjointCrops(params.targetCropIds, params.excludedCropIds, lang);
  if (!cCheck.valid && cCheck.error) errors.push(cCheck.error);

  const pCheck = validateSeasonMonthConsistency(
    params.startSeason,
    params.plantingMonth,
    params.latitude,
    lang
  );
  if (!pCheck.valid && pCheck.error) {
    const planningPrefix =
      lang === "fr" ? "Planification :" : lang === "ar" ? "التخطيط:" : "Planning:";
    errors.push(`${planningPrefix} ${pCheck.error}`);
  }

  params.cropHistory.forEach((row, index) => {
    const hCheck = validateSeasonMonthConsistency(
      row.season,
      row.planting_month,
      params.latitude,
      lang
    );
    if (!hCheck.valid && hCheck.error) {
      const rowPrefix =
        lang === "fr"
          ? `Historique cultural ligne n°${index + 1} :`
          : lang === "ar"
            ? `سجل المحاصيل صف رقم ${index + 1}:`
            : `Crop history row #${index + 1}:`;
      errors.push(`${rowPrefix} ${hCheck.error}`);
    }
  });

  return { valid: errors.length === 0, errors };
}
