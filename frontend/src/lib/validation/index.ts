import type { PriorityWeights, Season, SoilType } from "@/lib/schemas";

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

export function validateWeightsSum(weights: PriorityWeights): WeightsValidationResult {
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
      error: "All priority weights must be integers between 0 and 100.",
    };
  }
  if (sum !== 100) {
    return {
      valid: false,
      sum,
      remaining,
      error: `Priority weights must sum strictly to 100 (currently ${sum}).`,
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
  excludedCropIds: string[]
): DisjointCropsValidationResult {
  const excludedSet = new Set(excludedCropIds.map((id) => id.trim()).filter(Boolean));
  const overlappingIds = Array.from(
    new Set(targetCropIds.map((id) => id.trim()).filter((id) => excludedSet.has(id)))
  );

  if (overlappingIds.length > 0) {
    return {
      valid: false,
      overlappingIds,
      error: `Target and excluded crops cannot overlap: ${overlappingIds.join(", ")}.`,
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
  latitude: number = 36.52
): SeasonMonthValidationResult {
  const allowedMonths = NORTHERN_HEMISPHERE_SEASON_MONTHS[season];
  if (plantingMonth === null || plantingMonth === undefined) {
    return { valid: true, allowedMonths };
  }
  if (!Number.isInteger(plantingMonth) || plantingMonth < 1 || plantingMonth > 12) {
    return {
      valid: false,
      allowedMonths,
      error: `Planting month must be between 1 and 12 (received ${plantingMonth}).`,
    };
  }
  if (latitude >= 0 && !allowedMonths.includes(plantingMonth)) {
    return {
      valid: false,
      allowedMonths,
      error: `Month ${plantingMonth} does not match ${season} in Northern Hemisphere (expected: ${allowedMonths.join(", ")}).`,
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
}): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  const wCheck = validateWeightsSum(params.weights);
  if (!wCheck.valid && wCheck.error) errors.push(wCheck.error);

  const cCheck = validateDisjointCrops(params.targetCropIds, params.excludedCropIds);
  if (!cCheck.valid && cCheck.error) errors.push(cCheck.error);

  const pCheck = validateSeasonMonthConsistency(
    params.startSeason,
    params.plantingMonth,
    params.latitude
  );
  if (!pCheck.valid && pCheck.error) errors.push(`Planning: ${pCheck.error}`);

  params.cropHistory.forEach((row, index) => {
    const hCheck = validateSeasonMonthConsistency(
      row.season,
      row.planting_month,
      params.latitude
    );
    if (!hCheck.valid && hCheck.error) {
      errors.push(`Crop history row #${index + 1}: ${hCheck.error}`);
    }
  });

  return { valid: errors.length === 0, errors };
}
