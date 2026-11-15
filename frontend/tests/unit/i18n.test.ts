import { describe, expect, it } from "vitest";
import { ApiClientError, presentApiError } from "@/lib/api/errors";
import {
  ANALYSIS_JOB_STATUS_LABELS,
  CROP_CATEGORY_LABELS,
  CROP_ROLE_LABELS,
  DATA_SOURCE_LABELS,
  EQUIPMENT_LABELS,
  EVIDENCE_GROUP_LABELS,
  EVIDENCE_PARAM_LABELS,
  IRRIGATION_SYSTEM_LABELS,
  MARKET_PREFERENCE_LABELS,
  MONTH_SHORT,
  PRIORITY_WEIGHT_LABELS,
  REQUESTED_OUTCOME_LABELS,
  RISK_SEVERITY_LABELS,
  SCORE_LABELS,
  SEASON_LABELS,
  SOIL_TYPE_LABELS,
  STRESS_LABELS,
  UI_DICT,
  WATER_AVAILABILITY_LABELS,
  WATER_SOURCE_LABELS,
  WEIGHT_PRESET_LABELS,
} from "@/lib/i18n";
import { GUELMA_WORKSPACE_I18N } from "@/lib/i18n/guelmaWorkspace";
import { INTELLIGENCE_I18N } from "@/lib/i18n/intelligence";
import { I18N as PROTOTYPE_I18N } from "@/lib/prototype/i18n";
import type { ErrorCode, Language } from "@/lib/schemas";

const LANGS: readonly Language[] = ["en", "fr", "ar"];

type LeafEntry = { path: string; type: string; value: unknown };

function collectLeaves(obj: unknown, prefix = ""): LeafEntry[] {
  if (obj === null || obj === undefined) {
    return [{ path: prefix, type: String(obj), value: obj }];
  }
  if (Array.isArray(obj)) {
    const entries: LeafEntry[] = [
      { path: `${prefix}.__length`, type: "arrayLength", value: obj.length },
    ];
    obj.forEach((item, idx) => {
      entries.push(...collectLeaves(item, `${prefix}[${idx}]`));
    });
    return entries;
  }
  if (typeof obj === "object") {
    const entries: LeafEntry[] = [];
    for (const key of Object.keys(obj as Record<string, unknown>)) {
      const next = prefix ? `${prefix}.${key}` : key;
      entries.push(...collectLeaves((obj as Record<string, unknown>)[key], next));
    }
    return entries;
  }
  return [{ path: prefix, type: typeof obj, value: obj }];
}

function assertTrilingualParity(
  name: string,
  dict: Record<Language, unknown>,
  options?: { optionalInEn?: string[] }
) {
  const optionalSet = new Set(options?.optionalInEn ?? []);
  const filterLeaves = (leaves: LeafEntry[], isEn: boolean) =>
    isEn
      ? leaves
      : leaves.filter((e) => !Array.from(optionalSet).some((prefix) => e.path === prefix || e.path.startsWith(`${prefix}.`)));

  const byLang = Object.fromEntries(
    LANGS.map((l) => [l, collectLeaves(dict[l])])
  ) as Record<Language, LeafEntry[]>;

  const enMap = new Map(byLang.en.map((e) => [e.path, e]));
  for (const l of ["fr", "ar"] as const) {
    const comparableTarget = filterLeaves(byLang[l], false);
    const targetMap = new Map(comparableTarget.map((e) => [e.path, e]));
    const missingInTarget = byLang.en
      .filter((e) => !targetMap.has(e.path))
      .map((e) => e.path);
    const extraInTarget = comparableTarget
      .filter((e) => !enMap.has(e.path))
      .map((e) => e.path);

    expect(missingInTarget, `${name}.${l} missing keys vs en`).toEqual([]);
    expect(extraInTarget, `${name}.${l} extra keys vs en`).toEqual([]);

    for (const entry of byLang[l]) {
      const enEntry = enMap.get(entry.path);
      if (enEntry) {
        expect(entry.type, `${name}.${l}.${entry.path} type mismatch`).toBe(enEntry.type);
      }
      if (entry.type === "string") {
        expect(
          String(entry.value).trim().length,
          `${name}.${l}.${entry.path} must be non-empty`
        ).toBeGreaterThan(0);
      }
    }
  }

  // Also ensure fr & ar optional namespaces match each other completely
  for (const prefix of optionalSet) {
    const frOpt = byLang.fr.filter((e) => e.path.startsWith(`${prefix}.`));
    const arOpt = byLang.ar.filter((e) => e.path.startsWith(`${prefix}.`));
    const frMap = new Map(frOpt.map((e) => [e.path, e]));
    const arMap = new Map(arOpt.map((e) => [e.path, e]));
    expect(arOpt.filter((e) => !frMap.has(e.path)).map((e) => e.path), `${name}.ar extra ${prefix}`).toEqual([]);
    expect(frOpt.filter((e) => !arMap.has(e.path)).map((e) => e.path), `${name}.ar missing ${prefix}`).toEqual([]);
  }
}

describe("i18n trilingual dictionary parity & completeness", () => {
  it("checks UI_DICT EN / FR / AR parity", () => {
    assertTrilingualParity("UI_DICT", UI_DICT);
  });

  it("checks GUELMA_WORKSPACE_I18N EN / FR / AR parity", () => {
    assertTrilingualParity("GUELMA_WORKSPACE_I18N", GUELMA_WORKSPACE_I18N);
  });

  it("checks INTELLIGENCE_I18N EN / FR / AR parity", () => {
    assertTrilingualParity("INTELLIGENCE_I18N", INTELLIGENCE_I18N);
  });

  it("checks PROTOTYPE_I18N EN / FR / AR parity", () => {
    assertTrilingualParity("PROTOTYPE_I18N", PROTOTYPE_I18N, {
      optionalInEn: ["presets", "strats"],
    });
  });

  it("verifies EN / FR / AR completeness across all domain enum label maps", () => {
    const labelMaps = {
      SEASON_LABELS,
      SOIL_TYPE_LABELS,
      WATER_AVAILABILITY_LABELS,
      WATER_SOURCE_LABELS,
      IRRIGATION_SYSTEM_LABELS,
      MARKET_PREFERENCE_LABELS,
      CROP_CATEGORY_LABELS,
      CROP_ROLE_LABELS,
      STRESS_LABELS,
      SCORE_LABELS,
      EVIDENCE_PARAM_LABELS,
      RISK_SEVERITY_LABELS,
      EQUIPMENT_LABELS,
      WEIGHT_PRESET_LABELS,
      PRIORITY_WEIGHT_LABELS,
      ANALYSIS_JOB_STATUS_LABELS,
      REQUESTED_OUTCOME_LABELS,
      DATA_SOURCE_LABELS,
      EVIDENCE_GROUP_LABELS,
      MONTH_SHORT,
    };

    for (const [mapName, mapValue] of Object.entries(labelMaps)) {
      assertTrilingualParity(mapName, mapValue as Record<Language, unknown>);
    }

    for (const l of LANGS) {
      expect(MONTH_SHORT[l]).toHaveLength(12);
    }
  });

  it("verifies ERROR_COPY covers all 19 ErrorCodes cleanly in EN / FR / AR", () => {
    const codes: ErrorCode[] = [
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
    ];
    for (const code of codes) {
      for (const l of LANGS) {
        const presented = presentApiError(
          new ApiClientError({
            status: 400,
            code,
            message: "Server message",
            details: [],
            requestId: null,
          }),
          l
        );
        expect(presented.code).toBe(code);
        expect(presented.title.trim().length, `${code}.${l} title`).toBeGreaterThan(0);
        expect(presented.guidance.trim().length, `${code}.${l} guidance`).toBeGreaterThan(0);
      }
    }
  });
});
