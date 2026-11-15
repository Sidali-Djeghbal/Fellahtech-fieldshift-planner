import { describe, expect, it } from "vitest";
import {
  applySelectionToEnvelope,
  CATEGORY_STYLE_MAP,
  findFieldPlanForField,
  getScoreProgressClass,
  getStrategySelectionStatus,
  resolveCropDisplayName,
  SEVERITY_STYLE_MAP,
  STRATEGY_SCORE_KEYS,
} from "@/lib/analysis/workspaceAnalysis";
import { FIXTURE_OUTPUT_9_3 } from "@/lib/api/fixtures";
import { INTELLIGENCE_I18N } from "@/lib/i18n/intelligence";
import type { AnalysisEnvelope, CropCategory, CropItem, SeverityLevel } from "@/lib/schemas";

const MOCK_ENVELOPE: AnalysisEnvelope = {
  analysis_id: "analysis_4f9a8c120e3b",
  request_id: FIXTURE_OUTPUT_9_3.request_id,
  status: "ok",
  dataset_version: "2026.11-guelma-v1",
  warnings: [],
  degraded_mode: null,
  result: FIXTURE_OUTPUT_9_3,
};

describe("AI Intelligence domain helpers & UI state mapping", () => {
  it("defines distinct styles for all 7 CropCategory and 3 SeverityLevel enum values", () => {
    const categories: CropCategory[] = [
      "cereals",
      "legumes",
      "oilseeds",
      "vegetables",
      "forage",
      "cover_crops",
      "fallow",
    ];
    for (const c of categories) {
      expect(CATEGORY_STYLE_MAP[c].badgeClass.length).toBeGreaterThan(0);
      expect(INTELLIGENCE_I18N.en.categories[c].length).toBeGreaterThan(0);
      expect(INTELLIGENCE_I18N.fr.categories[c].length).toBeGreaterThan(0);
      expect(INTELLIGENCE_I18N.ar.categories[c].length).toBeGreaterThan(0);
    }

    const severities: SeverityLevel[] = ["low", "medium", "high"];
    for (const sev of severities) {
      expect(SEVERITY_STYLE_MAP[sev].pillClass.length).toBeGreaterThan(0);
      expect(INTELLIGENCE_I18N.en.severity[sev].length).toBeGreaterThan(0);
      expect(INTELLIGENCE_I18N.fr.severity[sev].length).toBeGreaterThan(0);
      expect(INTELLIGENCE_I18N.ar.severity[sev].length).toBeGreaterThan(0);
    }

    expect(STRATEGY_SCORE_KEYS).toHaveLength(7);
  });

  it("reads strategy selection_status accurately and maintains single-selected exclusivity per field", () => {
    const fp = MOCK_ENVELOPE.result.field_plans[0];
    const s1 = fp.strategies[0];
    const s2 = fp.strategies[1];
    expect(getStrategySelectionStatus(s1)).toBe("suggested");

    const withS1Selected = applySelectionToEnvelope(
      MOCK_ENVELOPE,
      fp.field_id,
      s1.strategy_id,
      "selected"
    );
    const fpAfter1 = findFieldPlanForField(withS1Selected, fp.field_id)!;
    expect(getStrategySelectionStatus(fpAfter1.strategies[0])).toBe("selected");
    expect(getStrategySelectionStatus(fpAfter1.strategies[1])).toBe("suggested");

    const withS2Selected = applySelectionToEnvelope(
      withS1Selected,
      fp.field_id,
      s2.strategy_id,
      "selected"
    );
    const fpAfter2 = findFieldPlanForField(withS2Selected, fp.field_id)!;
    expect(getStrategySelectionStatus(fpAfter2.strategies[0])).toBe("suggested");
    expect(getStrategySelectionStatus(fpAfter2.strategies[1])).toBe("selected");

    const withS2Rejected = applySelectionToEnvelope(
      withS2Selected,
      fp.field_id,
      s2.strategy_id,
      "rejected"
    );
    const fpAfter3 = findFieldPlanForField(withS2Rejected, fp.field_id)!;
    expect(getStrategySelectionStatus(fpAfter3.strategies[1])).toBe("rejected");
  });

  it("matches exact field_id in findFieldPlanForField and resolves multilingual crop labels", () => {
    expect(findFieldPlanForField(null, "F1")).toBeNull();
    const matched = findFieldPlanForField(MOCK_ENVELOPE, FIXTURE_OUTPUT_9_3.field_plans[0].field_id);
    expect(matched?.field_id).toBe(FIXTURE_OUTPUT_9_3.field_plans[0].field_id);

    const catalogItem: CropItem = {
      crop_id: "durum_wheat",
      display_name: "Durum Wheat",
      names: { en: "Durum Wheat", fr: "Blé dur", ar: "قمح صلب" },
      category: "cereals",
      roles: ["main_crop", "cash_crop"],
      family: "Poaceae",
    };
    const map = new Map<string, CropItem>([["durum_wheat", catalogItem]]);

    expect(resolveCropDisplayName("durum_wheat", "Fallback", map, "ar")).toBe("قمح صلب");
    expect(resolveCropDisplayName("unknown_crop", "Local Chickpea", map, "fr")).toBe(
      "Local Chickpea"
    );
    expect(resolveCropDisplayName("bare_id", undefined, map, "en")).toBe("bare_id");

    expect(getScoreProgressClass(82, true)).toContain("from-[#0B4B2E]");
    expect(getScoreProgressClass(40)).toBe("bg-amber-500");
  });
});

