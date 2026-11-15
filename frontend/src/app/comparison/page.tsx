"use client";

import React, { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CaretDown,
  CaretUp,
  CheckCircle,
  Crown,
  Printer,
  ShieldWarning,
  Thermometer,
  XCircle,
} from "@phosphor-icons/react";
import { useResolvedTheme } from "@/app/providers";
import { AgronomicRiskCalendar } from "@/components/comparison/AgronomicRiskCalendar";
import { PrintableBrief } from "@/components/comparison/PrintableBrief";
import { ScoreRadarChart } from "@/components/comparison/ScoreRadarChart";
import { useWorkspaceShell } from "@/components/guelma/WorkspaceShellContext";
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
  ANALYSIS_JOB_STATUS_LABELS,
  CROP_CATEGORY_LABELS,
  CROP_ROLE_LABELS,
  REQUESTED_OUTCOME_LABELS,
  RISK_SEVERITY_LABELS,
  SCORE_LABELS,
  SEASON_LABELS,
  UI_DICT,
  localizePlainText,
} from "@/lib/i18n";
import { resolveCropDisplayName } from "@/lib/analysis/workspaceAnalysis";
import type { Strategy } from "@/lib/schemas";
import { useAppStore } from "@/store/useAppStore";

function ComparisonContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const resolvedTheme = useResolvedTheme();
  const { openAuthModal } = useWorkspaceShell();

  const {
    lang,
    plainMode,
    authMode,
    activeFarmId,
    activeAnalysisId,
    simulateDegradedReplay,
    setSimulateDegradedReplay,
    setActiveAnalysisId,
  } = useAppStore();

  const t = UI_DICT[lang].comparison;
  const c = UI_DICT[lang].common;
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
  const catalogMap = new Map(catalogItems.map((c) => [c.crop_id, c]));

  const getLocalizedCropName = (cropId: string, fallback: string) =>
    resolveCropDisplayName(cropId, fallback, catalogMap, lang);

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
    <div className="fs-view-enter space-y-5">
      {/* Screen Header */}
      <div className="no-print flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-semibold tracking-tight text-[#111813] dark:text-[#F5F7F5]">
            {t.title}
          </h1>
          <p className="mt-1 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">{t.subtitle}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <label className="fs-liquid-pill inline-flex cursor-pointer items-center gap-1.5 rounded-full px-3.5 py-2 text-[11px] font-medium text-[#3E4C42] dark:text-[#D1DDD3]">
            <input
              type="checkbox"
              data-testid="toggle-degraded-preview"
              checked={simulateDegradedReplay}
              onChange={(e) => setSimulateDegradedReplay(e.target.checked)}
              className="rounded accent-[#15803D] dark:accent-[#22C55E]"
            />
            <span>{UI_DICT[lang].dashboard.simulateDegradedLabel}</span>
          </label>
          <Link
            href="/"
            className="fs-liquid-pill inline-flex items-center gap-1.5 rounded-full px-3.5 py-2 text-xs font-semibold text-[#111813] dark:text-[#F5F7F5]"
          >
            <ArrowLeft size={14} className="rtl:-scale-x-100" />
            <span>{c.backToCommandCenter}</span>
          </Link>
          <button
            type="button"
            onClick={() => window.print()}
            data-testid="print-brief-btn"
            className="fs-cta-primary inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold active:not-disabled:scale-[0.96]"
          >
            <Printer size={16} />
            {t.printBriefBtn}
          </button>
        </div>
      </div>

      {(analysisQuery.error || analysesQuery.error || farmsQuery.error) && (
        <ApiErrorCard
          error={analysisQuery.error ?? analysesQuery.error ?? farmsQuery.error}
          lang={lang}
          theme={resolvedTheme}
          onOpenClaimAccount={openAuthModal}
        />
      )}
      {actionError !== null && (
        <ApiErrorCard
          error={actionError}
          lang={lang}
          theme={resolvedTheme}
          onOpenClaimAccount={openAuthModal}
        />
      )}

      {!envelope && !analysisQuery.error && (
        <section className="no-print fs-liquid-panel rounded-3xl p-6 text-[#111813] dark:text-[#F5F7F5]">
          {hasSession && resolvedAnalysisId && analysisQuery.isLoading ? (
            <p className="text-xs text-[#4A5A4E] dark:text-[#9CA89E]">
              {t.loadingText}
            </p>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="font-heading text-base font-bold text-[#111813] dark:text-[#F5F7F5]">
                  {t.emptyTitle}
                </h2>
                <p className="mt-1 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">
                  {t.emptyBody}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link
                  href="/farm-profile"
                  className="fs-cta-primary rounded-full px-4 py-2 text-xs font-semibold"
                >
                  {t.openProfileBtn}
                </Link>
                <Link
                  href="/"
                  className="fs-liquid-pill rounded-full px-4 py-2 text-xs font-semibold text-[#111813] dark:text-[#F5F7F5]"
                >
                  {c.backToCommandCenter}
                </Link>
              </div>
            </div>
          )}
        </section>
      )}

      {envelope && activeFieldPlan && (
        <>
          <DegradedReplayBanner
            degradedMode={envelope.degraded_mode}
            lang={lang}
            theme={resolvedTheme}
          />
          <WarningsBanner warnings={envelope.warnings} lang={lang} theme={resolvedTheme} />

          {/* Summary & Provenance Banner */}
          <section className="no-print fs-liquid-microclimate rounded-3xl p-5 text-[#111813] dark:text-[#F5F7F5]">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <div className="flex flex-wrap items-center gap-2">
                <code
                  dir="ltr"
                  className="rounded-full border border-[#15803D]/25 bg-[#15803D]/10 px-3 py-0.5 font-mono font-semibold text-[#15803D] dark:border-[#22C55E]/30 dark:bg-[#22C55E]/15 dark:text-[#86EFAC]"
                >
                  {envelope.analysis_id}
                </code>
                <span className="rounded-full border border-[#111813]/12 bg-[#111813]/[0.04] px-2.5 py-0.5 text-[#3E4C42] dark:border-white/12 dark:bg-white/[0.06] dark:text-[#D1DDD3]">
                  {c.datasetLabel}: <strong dir="ltr">{envelope.result.dataset_version_used}</strong>
                </span>
                <span className="rounded-full border border-[#111813]/12 bg-[#111813]/[0.04] px-2.5 py-0.5 text-[#3E4C42] dark:border-white/12 dark:bg-white/[0.06] dark:text-[#D1DDD3]">
                  {c.engineLabel}: <strong dir="ltr">{envelope.result.ml_engine_version}</strong>
                </span>
              </div>
              <span className="tabular-nums rounded-full border border-[#15803D]/25 bg-[#15803D]/10 px-3 py-0.5 font-semibold text-[#15803D] dark:border-[#22C55E]/30 dark:bg-[#22C55E]/15 dark:text-[#86EFAC]">
                {c.completenessLabel}:{" "}
                {Math.round((envelope.result.data_quality.completeness_score ?? 0) * 100)}%
              </span>
            </div>
            <p className="mt-3 text-sm font-medium leading-relaxed text-[#111813] dark:text-[#F5F7F5]">
              {localizePlainText(envelope.result.overall_summary, lang, plainMode)}
            </p>
            <p className="mt-2 flex items-start gap-1.5 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">
              <ShieldWarning size={15} className="mt-0.5 shrink-0 text-[#15803D] dark:text-[#86EFAC]" />
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
                  className={`rounded-full px-4 py-2 text-xs font-semibold transition ${
                    idx === selectedFieldIdx
                      ? "bg-[#0B3D2E] text-white shadow-sm dark:bg-[#FFFFFF] dark:text-[#111713]"
                      : "fs-liquid-pill text-[#3E4C42] dark:text-[#D1DDD3]"
                  }`}
                >
                  {fp.field_id} · {fp.field_name} (
                  {ANALYSIS_JOB_STATUS_LABELS[lang][fp.status] ?? fp.status}
                  )
                </button>
              ))}
            </div>
          )}

          {activeFieldPlan.status === "partial" && activeFieldPlan.partial_reason && (
            <div className="no-print rounded-2xl border border-red-300/80 bg-red-50/90 p-3.5 text-xs text-red-800 dark:border-red-500/35 dark:bg-red-500/15 dark:text-red-200">
              {t.partialFieldBanner} {activeFieldPlan.partial_reason}
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
            <div className="fs-liquid-panel rounded-3xl p-5 text-[#111813] dark:text-[#F5F7F5] xl:col-span-4">
              <h2 className="mb-3 font-heading text-sm font-bold text-[#111813] dark:text-[#F5F7F5]">
                {t.radarHeading}
              </h2>
              <ScoreRadarChart
                baseline={baselineStrategy}
                focused={chosenOrSuggestedStrategy}
                lang={lang}
                plainMode={plainMode}
                variant={resolvedTheme}
              />

              {/* Requested Crop Outcomes */}
              <div className="mt-5 border-t border-[#111813]/10 pt-4 dark:border-white/10">
                <h3 className="text-xs font-semibold text-[#4A5A4E] dark:text-[#9CA89E]">
                  {t.requestedCropsTitle}
                </h3>
                <div className="mt-2.5 space-y-2">
                  {activeFieldPlan.requested_crop_results.map((reqCrop) => (
                    <div key={reqCrop.requested_crop_id} className="fs-liquid-well rounded-2xl p-3 text-xs">
                      <div className="flex items-center justify-between gap-2">
                        <strong className="text-[#111813] dark:text-[#F5F7F5]">
                          {getLocalizedCropName(
                            reqCrop.requested_crop_id,
                            reqCrop.requested_crop_id
                          )}
                        </strong>
                        <span
                          className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase ${
                            reqCrop.outcome === "included"
                              ? "bg-[#15803D]/15 text-[#15803D] dark:bg-[#22C55E]/20 dark:text-[#86EFAC]"
                              : reqCrop.outcome === "replaced"
                                ? "bg-amber-500/15 text-amber-800 dark:bg-amber-500/20 dark:text-[#FCD34D]"
                                : "bg-red-500/15 text-red-700 dark:bg-red-500/20 dark:text-red-300"
                          }`}
                        >
                          {REQUESTED_OUTCOME_LABELS[lang][reqCrop.outcome] ?? reqCrop.outcome}
                        </span>
                      </div>
                      {reqCrop.replaced_by_crop_id && (
                        <p className="mt-1 text-[11px] font-semibold text-[#15803D] dark:text-[#86EFAC]">
                          {t.replacedByLabel}{" "}
                          {resolveCropDisplayName(reqCrop.replaced_by_crop_id, null, catalogMap, lang)}
                        </p>
                      )}
                      <p className="mt-1 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
                        {localizePlainText(reqCrop.explanation, lang, plainMode)}
                      </p>
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
                    className={`fs-liquid-panel rounded-3xl p-5 text-[#111813] transition dark:text-[#F5F7F5] ${
                      selState === "selected"
                        ? "ring-2 ring-[#0B3D2E] dark:ring-[#22C55E]"
                        : isSuggested
                          ? "ring-1 ring-[#15803D]/50 dark:ring-[#22C55E]/45"
                          : ""
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="font-heading text-base font-bold text-[#111813] dark:text-[#F5F7F5]">
                            {strat.name}
                          </h3>
                          {isSuggested && (
                            <span className="inline-flex items-center gap-1 rounded-full border border-[#15803D]/25 bg-[#15803D]/10 px-2.5 py-0.5 text-[11px] font-semibold text-[#15803D] dark:border-[#22C55E]/30 dark:bg-[#22C55E]/15 dark:text-[#86EFAC]">
                              <Crown size={12} weight="fill" />
                              {t.recommendedBadge}
                            </span>
                          )}
                          {strat.is_existing_rotation && (
                            <span className="rounded-full border border-[#111813]/12 bg-[#111813]/[0.05] px-2.5 py-0.5 text-[11px] font-semibold text-[#3E4C42] dark:border-white/15 dark:bg-white/[0.08] dark:text-[#D1DDD3]">
                              {t.baselineBadge}
                            </span>
                          )}
                          {selState === "selected" && (
                            <span
                              data-testid={`selected-badge-${strat.strategy_id}`}
                              className="inline-flex items-center gap-1 rounded-full bg-[#0B3D2E] px-2.5 py-0.5 text-[11px] font-semibold text-white shadow-xs dark:bg-[#FFFFFF] dark:text-[#111713]"
                            >
                              <CheckCircle
                                size={12}
                                weight="fill"
                                className="text-[#84E875] dark:text-[#15803D]"
                              />
                              {t.selectedBadge}
                            </span>
                          )}
                          {selState === "rejected" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-red-600 px-2.5 py-0.5 text-[11px] font-semibold text-white dark:bg-red-500">
                              <XCircle size={12} weight="fill" />
                              {t.rejectedBadge}
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">
                          {strat.description}
                        </p>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          data-testid={`select-strategy-${strat.strategy_id}`}
                          onClick={() => handleSelectAction(strat.strategy_id, "selected")}
                          className="fs-cta-primary rounded-full px-3.5 py-1.5 text-xs font-semibold active:not-disabled:scale-[0.96]"
                        >
                          {t.selectStrategyBtn}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleSelectAction(strat.strategy_id, "rejected")}
                          className="rounded-full border border-red-300/80 bg-red-50/90 px-3.5 py-1.5 text-xs font-semibold text-red-700 transition hover:bg-red-100 dark:border-red-500/35 dark:bg-red-500/15 dark:text-red-300 dark:hover:bg-red-500/25"
                        >
                          {t.rejectStrategyBtn}
                        </button>
                      </div>
                    </div>

                    {/* Season-by-season Strip */}
                    <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
                      {strat.seasons.map((sn) => (
                        <div key={sn.order} className="fs-liquid-well rounded-2xl p-3">
                          <div className="flex items-center justify-between text-[10px] text-[#4A5A4E] dark:text-[#9CA89E]">
                            <span>
                              #{sn.order} · {SEASON_LABELS[lang][sn.season]} {sn.year}
                            </span>
                            {sn.planting_month && <span dir="ltr">M{sn.planting_month}</span>}
                          </div>
                          <p className="mt-1 text-xs font-bold text-[#111813] dark:text-[#F5F7F5]">
                            {getLocalizedCropName(sn.crop_id, sn.crop_name)}
                          </p>
                          <div className="mt-1.5 flex flex-wrap gap-1 text-[10px]">
                            <span className="rounded-full border border-[#111813]/12 bg-white/70 px-2 py-0.5 text-[#3E4C42] dark:border-white/12 dark:bg-white/[0.06] dark:text-[#D1DDD3]">
                              {CROP_CATEGORY_LABELS[lang][sn.category]}
                            </span>
                            <span className="rounded-full border border-[#15803D]/25 bg-[#15803D]/10 px-2 py-0.5 font-medium text-[#15803D] dark:border-[#22C55E]/25 dark:bg-[#22C55E]/15 dark:text-[#86EFAC]">
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
                            <div key={scoreKey} className="fs-liquid-well rounded-xl p-2.5">
                              <div className="flex items-center justify-between text-[10px] text-[#3E4C42] dark:text-[#D1DDD3]">
                                <span className="truncate">{label}</span>
                                <strong className="font-mono tabular-nums text-[#111813] dark:text-[#F5F7F5]">
                                  {val}
                                </strong>
                              </div>
                              <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-[#111813]/10 dark:bg-white/10">
                                <div
                                  className="h-full rounded-full bg-[#15803D] dark:bg-[#22C55E]"
                                  style={{ width: `${val}%` }}
                                />
                              </div>
                            </div>
                          );
                        }
                      )}
                      <div className="fs-liquid-well rounded-xl p-2.5">
                        <span className="block truncate text-[10px] text-[#4A5A4E] dark:text-[#9CA89E]">
                          {plainMode ? t.bareDaysPlain : t.bareDaysLabel}
                        </span>
                        <strong className="mt-0.5 block font-mono text-sm font-bold tabular-nums text-[#15803D] dark:text-[#86EFAC]">
                          {strat.scores.bare_field_days_per_year} {c.daysPerYearShort}
                        </strong>
                      </div>
                    </div>

                    {/* Expandable Details */}
                    <button
                      type="button"
                      onClick={() =>
                        setExpandedStrategyId(expanded ? null : strat.strategy_id)
                      }
                      className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-[#15803D] hover:underline dark:text-[#86EFAC]"
                    >
                      {expanded ? <CaretUp size={14} /> : <CaretDown size={14} />}
                      {expanded ? t.hideDetailsBtn : t.inspectDetailsBtn}
                    </button>

                    {expanded && (
                      <div className="mt-3 grid grid-cols-1 gap-3 border-t border-[#111813]/10 pt-3 text-xs dark:border-white/10 md:grid-cols-3">
                        <div>
                          <p className="font-bold text-[#15803D] dark:text-[#86EFAC]">
                            {t.benefitsTitle}
                          </p>
                          <ul className="mt-1.5 space-y-1.5 text-[#3E4C42] dark:text-[#D1DDD3]">
                            {strat.explanation.benefits.map((b) => (
                              <li key={b.benefit_id}>
                                <strong className="text-[#111813] dark:text-[#F5F7F5]">
                                  {b.title}:
                                </strong>{" "}
                                {localizePlainText(b.description, lang, plainMode)}
                              </li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <p className="font-bold text-red-700 dark:text-red-300">
                            {t.risksTitle}
                          </p>
                          <ul className="mt-1.5 space-y-1.5 text-[#3E4C42] dark:text-[#D1DDD3]">
                            {strat.explanation.risks.map((r) => (
                              <li key={r.risk_id}>
                                <strong className="text-[#111813] dark:text-[#F5F7F5]">
                                  {r.title}
                                </strong>{" "}
                                ({RISK_SEVERITY_LABELS[lang][r.severity] ?? r.severity}):{" "}
                                {localizePlainText(r.description, lang, plainMode)}
                                <span className="mt-0.5 block font-medium text-[#15803D] dark:text-[#86EFAC]">
                                  {t.mitigationLabel} {localizePlainText(r.mitigation, lang, plainMode)}
                                </span>
                              </li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <p className="font-bold text-[#4A5A4E] dark:text-[#9CA89E]">
                            {t.gapsTitle}
                          </p>
                          <ul className="mt-1.5 list-disc space-y-1 ps-4 text-[#4A5A4E] dark:text-[#9CA89E]">
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
          <section className="no-print fs-liquid-panel rounded-3xl p-5 text-[#111813] dark:text-[#F5F7F5]">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="flex items-center gap-2 font-heading text-base font-bold text-[#111813] dark:text-[#F5F7F5]">
                  <Thermometer size={18} className="text-[#15803D] dark:text-[#86EFAC]" />
                  {t.whatIfTitle}
                </h2>
                <p className="mt-1 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">
                  {t.whatIfHint}
                </p>
              </div>
              <button
                type="button"
                disabled={runningWhatIf}
                onClick={handleQuickWhatIf}
                className="fs-cta-primary rounded-full px-4 py-2 text-xs font-semibold active:not-disabled:scale-[0.96] disabled:opacity-50"
              >
                {runningWhatIf ? t.runningBtn : t.whatIfRunBtn}
              </button>
            </div>
            <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <div className="flex justify-between text-xs text-[#3E4C42] dark:text-[#D1DDD3]">
                  <span>{t.tempShiftLabel}</span>
                  <span dir="ltr" className="tabular-nums font-bold text-[#111813] dark:text-[#F5F7F5]">
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
                  className="mt-1.5 w-full accent-[#15803D] dark:accent-[#22C55E]"
                />
              </div>
              <div>
                <div className="flex justify-between text-xs text-[#3E4C42] dark:text-[#D1DDD3]">
                  <span>{t.precipChangeLabel}</span>
                  <span dir="ltr" className="tabular-nums font-bold text-[#111813] dark:text-[#F5F7F5]">
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
                  className="mt-1.5 w-full accent-[#15803D] dark:accent-[#22C55E]"
                />
              </div>
            </div>
          </section>

          {/* 1-Page Light-Mode @media print Brief */}
          <PrintableBrief
            envelope={envelope}
            fieldPlan={activeFieldPlan}
            strategy={chosenOrSuggestedStrategy}
            lang={lang}
            plainMode={plainMode}
            catalogMap={catalogMap}
          />
        </>
      )}
    </div>
  );
}

function ComparisonSuspenseFallback() {
  const lang = useAppStore((s) => s.lang);
  return (
    <div className="fs-liquid-panel rounded-3xl p-6 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">
      {UI_DICT[lang].comparison.loadingText}
    </div>
  );
}

export default function ComparisonPage() {
  return (
    <Suspense fallback={<ComparisonSuspenseFallback />}>
      <ComparisonContent />
    </Suspense>
  );
}
