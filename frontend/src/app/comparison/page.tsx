"use client";

import React, { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CaretDown,
  CaretUp,
  CheckCircle,
  Crown,
  Printer,
  ShieldWarning,
  Thermometer,
  XCircle,
} from "@phosphor-icons/react";
import { AgronomicRiskCalendar } from "@/components/comparison/AgronomicRiskCalendar";
import { PrintableBrief } from "@/components/comparison/PrintableBrief";
import { ScoreRadarChart } from "@/components/comparison/ScoreRadarChart";
import {
  ApiErrorCard,
  DegradedReplayBanner,
  WarningsBanner,
} from "@/components/shared/ProvenanceBanners";
import {
  fetchAllCatalogItems,
  getAnalysisResult,
  listFarmAnalyses,
  listFarms,
  pollAnalysisRequest,
  submitAnalysis,
  updateAnalysisSelection,
} from "@/lib/api/endpoints";
import {
  CROP_CATEGORY_LABELS,
  CROP_ROLE_LABELS,
  SCORE_LABELS,
  SEASON_LABELS,
  UI_DICT,
  localizePlainText,
} from "@/lib/i18n";
import type { Strategy } from "@/lib/schemas";
import { useAppStore } from "@/store/useAppStore";

function ComparisonContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const {
    lang,
    plainMode,
    authMode,
    activeFarmId,
    activeAnalysisId,
    simulateDegradedReplay,
    setActiveAnalysisId,
  } = useAppStore();

  const t = UI_DICT[lang].comparison;
  const hasSession = authMode !== "none";
  const urlAnalysisId = searchParams.get("analysisId");

  const farmsQuery = useQuery({
    queryKey: ["farms", authMode],
    queryFn: () => listFarms(),
    enabled: hasSession,
  });

  const resolvedFarmId = activeFarmId ?? farmsQuery.data?.items[0]?.farm_id ?? null;

  const analysesQuery = useQuery({
    queryKey: ["analyses", resolvedFarmId],
    queryFn: () => listFarmAnalyses(resolvedFarmId!),
    enabled: hasSession && Boolean(resolvedFarmId),
  });

  const resolvedAnalysisId =
    urlAnalysisId ??
    activeAnalysisId ??
    analysesQuery.data?.items.find((a) => a.analysis_id)?.analysis_id ??
    null;

  const analysisQuery = useQuery({
    queryKey: ["analysis", resolvedAnalysisId, simulateDegradedReplay],
    queryFn: () => getAnalysisResult(resolvedAnalysisId!),
    enabled: hasSession && Boolean(resolvedAnalysisId),
  });

  const catalogQuery = useQuery({
    queryKey: ["catalog", lang],
    queryFn: () => fetchAllCatalogItems(lang),
    enabled: hasSession,
  });

  const [selectedFieldIdx, setSelectedFieldIdx] = useState(0);
  const [expandedStrategyId, setExpandedStrategyId] = useState<string | null>(null);
  const [whatIfTemp, setWhatIfTemp] = useState(1.5);
  const [whatIfPrecip, setWhatIfPrecip] = useState(-15);
  const [runningWhatIf, setRunningWhatIf] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);

  const envelope = analysisQuery.data;
  const fieldPlans = envelope?.result.field_plans ?? [];
  const activeFieldPlan = fieldPlans[selectedFieldIdx] ?? fieldPlans[0];
  const catalogItems = catalogQuery.data?.items ?? [];

  const getLocalizedCropName = (cropId: string, fallback: string) => {
    const found = catalogItems.find((c) => c.crop_id === cropId);
    return found ? found.names[lang] : fallback;
  };

  async function handleSelectAction(
    strategyId: string,
    selectionStatus: "selected" | "rejected"
  ) {
    if (!envelope || !activeFieldPlan) return;
    setActionError(null);
    try {
      await updateAnalysisSelection(envelope.analysis_id, {
        field_id: activeFieldPlan.field_id,
        strategy_id: strategyId,
        selection_status: selectionStatus,
      });
      await queryClient.invalidateQueries({ queryKey: ["analysis", envelope.analysis_id] });
    } catch (err) {
      setActionError(err);
    }
  }

  async function handleQuickWhatIf() {
    if (!resolvedFarmId || !activeFieldPlan) return;
    setRunningWhatIf(true);
    setActionError(null);
    try {
      const queued = await submitAnalysis({
        farm_id: resolvedFarmId,
        language: lang,
        planning: {
          start_season: "spring",
          start_year: 2027,
          horizon_seasons: 4,
          cycle_mode: "annual_rotation",
          planting_month: 3,
          scenario_overrides: {
            temp_delta_c: whatIfTemp,
            precip_pct_delta: whatIfPrecip,
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
          market_preference: "mixed",
          target_crop_ids: ["chickpea"],
          excluded_crop_ids: [],
          equipment_constraints: [],
        },
        field_ids: [activeFieldPlan.field_id],
      });

      // Poll cleanly until complete
      for (let i = 0; i < 20; i++) {
        await new Promise((r) => setTimeout(r, 450));
        const polled = await pollAnalysisRequest(queued.request_id);
        if ((polled.status === "ok" || polled.status === "partial") && polled.analysis_id) {
          setActiveAnalysisId(polled.analysis_id);
          await queryClient.invalidateQueries({ queryKey: ["analyses"] });
          await queryClient.invalidateQueries({ queryKey: ["demo", "session"] });
          router.push(`/comparison?analysisId=${polled.analysis_id}`);
          return;
        }
        if (polled.status === "failed" || polled.status === "cancelled") {
          break;
        }
      }
    } catch (err) {
      setActionError(err);
    } finally {
      setRunningWhatIf(false);
    }
  }

  const baselineStrategy = activeFieldPlan?.strategies.find((s) => s.is_existing_rotation);
  const chosenOrSuggestedStrategy =
    activeFieldPlan?.strategies.find((s) =>
      s.seasons.some((sn) => sn.selection_status === "selected")
    ) ??
    activeFieldPlan?.strategies.find(
      (s) => s.strategy_id === activeFieldPlan.suggested_strategy_id
    );

  const getStrategySelectionState = (strat: Strategy) => {
    if (strat.seasons.some((s) => s.selection_status === "selected")) return "selected";
    if (strat.seasons.some((s) => s.selection_status === "rejected")) return "rejected";
    return "suggested";
  };

  return (
    <div className="space-y-5">
      {/* Screen Header */}
      <div className="no-print flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-extrabold text-[#111827]">{t.title}</h1>
          <p className="mt-1 text-xs text-[#6B7280]">{t.subtitle}</p>
        </div>
        <button
          type="button"
          onClick={() => window.print()}
          data-testid="print-brief-btn"
          className="inline-flex items-center gap-2 rounded-xl border border-[#E5E7EB] bg-white px-4 py-2 text-xs font-bold text-[#111827] hover:bg-gray-50 shadow-xs transition"
        >
          <Printer size={16} />
          {t.printBriefBtn}
        </button>
      </div>

      {analysisQuery.error && <ApiErrorCard error={analysisQuery.error} lang={lang} />}
      {actionError !== null && (
        <ApiErrorCard
          error={actionError}
          lang={lang}
          onOpenClaimAccount={() => {
            document.querySelector<HTMLButtonElement>('[data-testid="auth-modal-trigger"]')?.click();
          }}
        />
      )}

      {envelope && activeFieldPlan && (
        <>
          <DegradedReplayBanner degradedMode={envelope.degraded_mode} lang={lang} />
          <WarningsBanner warnings={envelope.warnings} lang={lang} />

          {/* Summary & Provenance Banner */}
          <section className="no-print rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-sm text-[#111827]">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <div className="flex flex-wrap items-center gap-2">
                <code dir="ltr" className="rounded bg-emerald-50 border border-emerald-200 px-2 py-0.5 font-bold text-[#00291B]">
                  {envelope.analysis_id}
                </code>
                <span className="rounded bg-gray-100 px-2 py-0.5 text-[#374151]">
                  Dataset: <strong dir="ltr">{envelope.result.dataset_version_used}</strong>
                </span>
                <span className="rounded bg-gray-100 px-2 py-0.5 text-[#374151]">
                  Engine: <strong dir="ltr">{envelope.result.ml_engine_version}</strong>
                </span>
              </div>
              <span className="tabular-nums rounded-full bg-[#DCFCE7] text-[#15803D] px-3 py-0.5 font-bold">
                Completeness:{" "}
                {Math.round((envelope.result.data_quality.completeness_score ?? 0) * 100)}%
              </span>
            </div>
            <p className="mt-3 text-sm font-medium leading-relaxed text-[#111827]">
              {localizePlainText(envelope.result.overall_summary, lang, plainMode)}
            </p>
            <p className="mt-2 flex items-start gap-1.5 text-xs text-[#6B7280]">
              <ShieldWarning size={15} className="mt-0.5 shrink-0 text-[#137135]" />
              {envelope.result.disclaimer}
            </p>
          </section>

          {/* Multi-Field Tabs */}
          {fieldPlans.length > 1 && (
            <div className="no-print flex flex-wrap gap-2">
              {fieldPlans.map((fp, idx) => (
                <button
                  key={fp.field_id}
                  type="button"
                  onClick={() => setSelectedFieldIdx(idx)}
                  className={`rounded-xl px-4 py-2 text-xs font-bold transition ${
                    idx === selectedFieldIdx
                      ? "bg-[#00291B] text-white shadow-xs"
                      : "border border-gray-200 bg-white text-[#374151] hover:bg-gray-50"
                  }`}
                >
                  {fp.field_id} · {fp.field_name} ({fp.status})
                </button>
              ))}
            </div>
          )}

          {activeFieldPlan.status === "partial" && activeFieldPlan.partial_reason && (
            <div className="no-print rounded-xl border border-red-300 bg-red-50 p-3 text-xs text-red-800">
              Partial field result: {activeFieldPlan.partial_reason}
            </div>
          )}

          {/* 12-Month Agronomic Risk Calendar */}
          <div className="no-print">
            <AgronomicRiskCalendar
              insights={activeFieldPlan.field_insights}
              baselineBareDays={baselineStrategy?.scores.bare_field_days_per_year}
              recommendedBareDays={chosenOrSuggestedStrategy?.scores.bare_field_days_per_year}
              lang={lang}
              plainMode={plainMode}
            />
          </div>

          {/* Radar Chart & Strategy Comparison Cards */}
          <section className="no-print grid grid-cols-1 gap-5 xl:grid-cols-12">
            <div className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-sm text-[#111827] xl:col-span-4">
              <h2 className="mb-3 font-heading text-sm font-bold text-[#111827]">
                Multi-Axis Agronomic Balance
              </h2>
              <ScoreRadarChart
                baseline={baselineStrategy}
                focused={chosenOrSuggestedStrategy}
                lang={lang}
                plainMode={plainMode}
              />

              {/* Requested Crop Outcomes */}
              <div className="mt-5 border-t border-gray-200 pt-4">
                <h3 className="text-xs font-bold text-[#6B7280]">{t.requestedCropsTitle}</h3>
                <div className="mt-2 space-y-2">
                  {activeFieldPlan.requested_crop_results.map((reqCrop) => (
                    <div
                      key={reqCrop.requested_crop_id}
                      className="rounded-xl border border-gray-200 bg-gray-50/70 p-3 text-xs"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <strong className="text-[#111827]">
                          {getLocalizedCropName(
                            reqCrop.requested_crop_id,
                            reqCrop.requested_crop_id
                          )}
                        </strong>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                            reqCrop.outcome === "included"
                              ? "bg-[#DCFCE7] text-[#15803D]"
                              : reqCrop.outcome === "replaced"
                                ? "bg-[#FEF3C7] text-[#D97706]"
                                : "bg-red-100 text-red-700"
                          }`}
                        >
                          {reqCrop.outcome}
                        </span>
                      </div>
                      {reqCrop.replaced_by_crop_id && (
                        <p className="mt-1 text-[11px] text-[#137135] font-semibold">
                          Replaced by: {reqCrop.replaced_by_crop_id}
                        </p>
                      )}
                      <p className="mt-1 text-[11px] text-[#6B7280]">{reqCrop.explanation}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Strategy Cards Column */}
            <div className="space-y-4 xl:col-span-8">
              {activeFieldPlan.strategies.map((strat) => {
                const isSuggested = strat.strategy_id === activeFieldPlan.suggested_strategy_id;
                const selState = getStrategySelectionState(strat);
                const expanded = expandedStrategyId === strat.strategy_id;

                return (
                  <article
                    key={strat.strategy_id}
                    data-testid={`strategy-card-${strat.strategy_id}`}
                    className={`rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-sm text-[#111827] transition ${
                      selState === "selected"
                        ? "ring-2 ring-[#00291B]"
                        : isSuggested
                          ? "ring-1 ring-[#137135]"
                          : ""
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="font-heading text-base font-extrabold text-[#111827]">
                            {strat.name}
                          </h3>
                          {isSuggested && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-[#DCFCE7] text-[#15803D] px-2.5 py-0.5 text-[11px] font-bold">
                              <Crown size={12} weight="fill" />
                              {t.recommendedBadge}
                            </span>
                          )}
                          {strat.is_existing_rotation && (
                            <span className="rounded-full border border-gray-300 bg-gray-100 px-2.5 py-0.5 text-[11px] font-semibold text-gray-700">
                              {t.baselineBadge}
                            </span>
                          )}
                          {selState === "selected" && (
                            <span
                              data-testid={`selected-badge-${strat.strategy_id}`}
                              className="inline-flex items-center gap-1 rounded-full bg-[#00291B] px-2.5 py-0.5 text-[11px] font-bold text-white shadow-xs"
                            >
                              <CheckCircle size={12} weight="fill" className="text-[#84E875]" />
                              {t.selectedBadge}
                            </span>
                          )}
                          {selState === "rejected" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-red-600 px-2.5 py-0.5 text-[11px] font-bold text-white">
                              <XCircle size={12} weight="fill" />
                              {t.rejectedBadge}
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-xs text-[#6B7280]">{strat.description}</p>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          data-testid={`select-strategy-${strat.strategy_id}`}
                          onClick={() => handleSelectAction(strat.strategy_id, "selected")}
                          className="rounded-lg bg-[#00291B] px-3 py-1.5 text-xs font-bold text-white hover:bg-[#04421B] shadow-xs transition"
                        >
                          {t.selectStrategyBtn}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleSelectAction(strat.strategy_id, "rejected")}
                          className="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-100 transition"
                        >
                          {t.rejectStrategyBtn}
                        </button>
                      </div>
                    </div>

                    {/* Season-by-season Strip */}
                    <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
                      {strat.seasons.map((sn) => (
                        <div
                          key={sn.order}
                          className="rounded-xl border border-gray-200 bg-gray-50/70 p-2.5"
                        >
                          <div className="flex items-center justify-between text-[10px] text-[#6B7280]">
                            <span>
                              #{sn.order} · {SEASON_LABELS[lang][sn.season]} {sn.year}
                            </span>
                            {sn.planting_month && <span dir="ltr">M{sn.planting_month}</span>}
                          </div>
                          <p className="mt-1 text-xs font-bold text-[#111827]">
                            {getLocalizedCropName(sn.crop_id, sn.crop_name)}
                          </p>
                          <div className="mt-1.5 flex flex-wrap gap-1 text-[10px]">
                            <span className="rounded bg-white border border-gray-200 px-1.5 py-0.5 text-[#374151]">
                              {CROP_CATEGORY_LABELS[lang][sn.category]}
                            </span>
                            <span className="rounded bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 text-[#137135] font-medium">
                              {CROP_ROLE_LABELS[lang][sn.role]}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* 7-Score Horizontal Matrix + Bare Days */}
                    <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
                      {(Object.keys(SCORE_LABELS[lang]) as Array<keyof (typeof SCORE_LABELS)["en"]>).map(
                        (scoreKey) => {
                          const val = strat.scores[scoreKey];
                          const label = plainMode
                            ? SCORE_LABELS[lang][scoreKey].plain
                            : SCORE_LABELS[lang][scoreKey].tech;
                          return (
                            <div
                              key={scoreKey}
                              className="rounded-lg border border-gray-200 bg-gray-50/50 p-2"
                            >
                              <div className="flex items-center justify-between text-[10px] text-[#374151]">
                                <span className="truncate">{label}</span>
                                <strong className="tabular-nums text-[#111827]">{val}</strong>
                              </div>
                              <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
                                <div
                                  className="h-full bg-[#137135]"
                                  style={{ width: `${val}%` }}
                                />
                              </div>
                            </div>
                          );
                        }
                      )}
                      <div className="rounded-lg border border-gray-200 bg-gray-50/50 p-2">
                        <span className="block truncate text-[10px] text-[#6B7280]">
                          {plainMode ? t.bareDaysPlain : t.bareDaysLabel}
                        </span>
                        <strong className="tabular-nums mt-0.5 block text-sm text-[#00291B] font-bold">
                          {strat.scores.bare_field_days_per_year} d/yr
                        </strong>
                      </div>
                    </div>

                    {/* Expandable Details */}
                    <button
                      type="button"
                      onClick={() =>
                        setExpandedStrategyId(expanded ? null : strat.strategy_id)
                      }
                      className="mt-3 inline-flex items-center gap-1 text-xs font-bold text-[#137135] hover:underline"
                    >
                      {expanded ? <CaretUp size={14} /> : <CaretDown size={14} />}
                      {expanded ? "Hide Agronomic Breakdown" : "Inspect Benefits, Risks & Gaps"}
                    </button>

                    {expanded && (
                      <div className="mt-3 grid grid-cols-1 gap-3 border-t border-gray-200 pt-3 md:grid-cols-3 text-xs">
                        <div>
                          <p className="font-bold text-[#137135]">{t.benefitsTitle}</p>
                          <ul className="mt-1.5 space-y-1.5 text-[#374151]">
                            {strat.explanation.benefits.map((b) => (
                              <li key={b.benefit_id}>
                                <strong className="text-[#111827]">{b.title}:</strong>{" "}
                                {localizePlainText(b.description, lang, plainMode)}
                              </li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <p className="font-bold text-red-700">{t.risksTitle}</p>
                          <ul className="mt-1.5 space-y-1.5 text-[#374151]">
                            {strat.explanation.risks.map((r) => (
                              <li key={r.risk_id}>
                                <strong className="text-[#111827]">{r.title}</strong> ({r.severity}):{" "}
                                {localizePlainText(r.description, lang, plainMode)}
                                <span className="mt-0.5 block text-[#137135] font-medium">
                                  Mitigation: {r.mitigation}
                                </span>
                              </li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <p className="font-bold text-[#6B7280]">{t.gapsTitle}</p>
                          <ul className="mt-1.5 list-disc space-y-1 ps-4 text-[#6B7280]">
                            {strat.explanation.information_gaps.map((g, gi) => (
                              <li key={gi}>{g}</li>
                            ))}
                            {strat.explanation.needs_local_review.map((nr, ni) => (
                              <li key={`nr-${ni}`}>{nr}</li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          </section>

          {/* Inline Climate What-If Scenario Tweak */}
          <section className="no-print rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-sm text-[#111827]">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="flex items-center gap-2 font-heading text-base font-bold text-[#111827]">
                  <Thermometer size={18} className="text-[#137135]" />
                  {t.whatIfTitle}
                </h2>
                <p className="mt-1 text-xs text-[#6B7280]">
                  Test hotter/drier seasons against the same parcel baseline (uses 1 guest quarter).
                </p>
              </div>
              <button
                type="button"
                disabled={runningWhatIf}
                onClick={handleQuickWhatIf}
                className="rounded-xl bg-[#00291B] px-4 py-2 text-xs font-bold text-white hover:bg-[#04421B] shadow-xs disabled:opacity-50 transition"
              >
                {runningWhatIf ? "Running..." : t.whatIfRunBtn}
              </button>
            </div>
            <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <div className="flex justify-between text-xs text-[#374151]">
                  <span>Temperature Shift</span>
                  <span dir="ltr" className="tabular-nums font-bold text-[#111827]">
                    {whatIfTemp >= 0 ? `+${whatIfTemp}` : whatIfTemp} °C
                  </span>
                </div>
                <input
                  type="range"
                  min={-5}
                  max={10}
                  step={0.5}
                  value={whatIfTemp}
                  onChange={(e) => setWhatIfTemp(Number(e.target.value))}
                  className="mt-1 w-full accent-[#137135]"
                />
              </div>
              <div>
                <div className="flex justify-between text-xs text-[#374151]">
                  <span>Precipitation Change</span>
                  <span dir="ltr" className="tabular-nums font-bold text-[#111827]">
                    {whatIfPrecip >= 0 ? `+${whatIfPrecip}` : whatIfPrecip}%
                  </span>
                </div>
                <input
                  type="range"
                  min={-80}
                  max={100}
                  step={5}
                  value={whatIfPrecip}
                  onChange={(e) => setWhatIfPrecip(Number(e.target.value))}
                  className="mt-1 w-full accent-[#137135]"
                />
              </div>
            </div>
          </section>

          {/* 1-Page Light-Mode @media print Brief */}
          <PrintableBrief
            envelope={envelope}
            fieldPlan={activeFieldPlan}
            strategy={chosenOrSuggestedStrategy}
          />
        </>
      )}
    </div>
  );
}

export default function ComparisonPage() {
  return (
    <Suspense
      fallback={
        <div className="rounded-2xl border border-[#E5E7EB] bg-white p-6 text-xs text-[#6B7280] shadow-sm">
          Loading rotation comparison...
        </div>
      }
    >
      <ComparisonContent />
    </Suspense>
  );
}
