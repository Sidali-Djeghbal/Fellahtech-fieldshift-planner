"use client";

import React from "react";
import {
  CheckCircle,
  GitBranch,
  Medal,
  Prohibit,
  SlidersHorizontal,
  SpinnerGap,
  WarningCircle,
} from "@phosphor-icons/react";
import { useResolvedTheme } from "@/app/providers";
import { ScoreRadarChart } from "@/components/comparison/ScoreRadarChart";
import { CropRotationTimeline } from "@/components/intelligence/CropRotationTimeline";
import { StrategyExplanationTabs } from "@/components/intelligence/StrategyExplanationTabs";
import {
  getScoreProgressClass,
  getStrategySelectionStatus,
  SEVERITY_STYLE_MAP,
  STRATEGY_SCORE_KEYS,
} from "@/lib/analysis/workspaceAnalysis";
import { SCORE_LABELS, UI_DICT } from "@/lib/i18n";
import { INTELLIGENCE_I18N } from "@/lib/i18n/intelligence";
import type { CropItem, FieldPlan, Language, Strategy } from "@/lib/schemas";

interface StrategyComparisonSectionProps {
  fieldPlan: FieldPlan;
  focusedStrategyId: string | null;
  savingStrategyId: string | null;
  catalogMap: Map<string, CropItem>;
  lang: Language;
  plainMode: boolean;
  onFocusStrategy: (strategyId: string) => void;
  onUpdateSelection: (
    fieldId: string,
    strategyId: string,
    selectionStatus: "selected" | "rejected"
  ) => void;
}

export function StrategyComparisonSection({
  fieldPlan,
  focusedStrategyId,
  savingStrategyId,
  catalogMap,
  lang,
  plainMode,
  onFocusStrategy,
  onUpdateSelection,
}: StrategyComparisonSectionProps) {
  const resolvedTheme = useResolvedTheme();
  const dict = INTELLIGENCE_I18N[lang];
  const st = dict.strategies;

  const strategies = fieldPlan.strategies;
  const baseline = strategies.find((s) => s.is_existing_rotation);
  const focusedStrategy: Strategy | undefined =
    strategies.find((s) => s.strategy_id === focusedStrategyId) ??
    strategies.find((s) => s.strategy_id === fieldPlan.suggested_strategy_id) ??
    strategies[0];

  return (
    <section className="space-y-6">
      {/* Partial Field Plan Banner if present */}
      {fieldPlan.status === "partial" ? (
        <div
          className="rounded-2xl bg-amber-50/90 px-5 py-4 text-xs text-amber-900 backdrop-blur-md ring-1 ring-amber-600/25 dark:bg-[#F59E0B]/12 dark:text-[#FDE68A] dark:ring-[#F59E0B]/30"
          data-testid="partial-field-plan-banner"
        >
          <p className="flex items-center gap-1.5 font-semibold">
            <WarningCircle size={15} weight="fill" className="text-amber-700 dark:text-[#FCD34D]" aria-hidden="true" />
            <span>{dict.overview.partialBannerTitle}</span>
          </p>
          {fieldPlan.partial_reason ? (
            <p className="mt-1 leading-relaxed text-amber-900/90 dark:text-[#D1DBD3]">{fieldPlan.partial_reason}</p>
          ) : null}
        </div>
      ) : null}

      {/* Comparison Header + Trade-off Radar */}
      <div className="fs-liquid-panel overflow-hidden rounded-3xl p-5 sm:p-6">
        <div className="grid gap-6 lg:grid-cols-3 lg:items-center">
          <div className="lg:col-span-2">
            <h3 className="flex items-center gap-2 font-heading text-sm font-semibold leading-[1.15] text-[#111813] dark:text-[#F5F7F5] sm:text-base">
              <GitBranch size={17} weight="duotone" className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
              <span>{st.heading}</span>
            </h3>
            <p className="mt-1.5 max-w-[65ch] text-xs leading-relaxed text-[#4A5A4E] dark:text-[#9CA89E]">
              {st.subtitle}
            </p>

            {/* Concentric Strategy Tabs */}
            {strategies.length > 0 ? (
              <div className="mt-5 flex flex-wrap gap-2.5">
                {strategies.map((strat) => {
                  const isFocused = focusedStrategy?.strategy_id === strat.strategy_id;
                  const isSuggested = strat.strategy_id === fieldPlan.suggested_strategy_id;
                  const selStatus = getStrategySelectionStatus(strat);

                  return (
                    <button
                      key={strat.strategy_id}
                      type="button"
                      onClick={() => onFocusStrategy(strat.strategy_id)}
                      className={`inline-flex min-h-10 items-center gap-1.5 rounded-full ps-3 pe-3.5 text-xs font-medium transition-[transform,background-color,box-shadow,color] duration-150 ease-out active:not-disabled:scale-[0.96] ${
                        isFocused
                          ? "bg-[#0B3D2E] font-semibold text-white shadow-[0_4px_14px_rgba(11,61,46,0.22)] dark:bg-[#FFFFFF] dark:text-[#111713] dark:shadow-[0_4px_14px_rgba(0,0,0,0.35)]"
                          : "fs-liquid-well fs-liquid-well-interactive text-[#111813] dark:text-[#F5F7F5]"
                      }`}
                    >
                      {isSuggested ? (
                        <Medal
                          size={14}
                          weight="fill"
                          className={isFocused ? "text-[#86EFAC] dark:text-[#15803D]" : "text-[#15803D] dark:text-[#86EFAC]"}
                          aria-hidden="true"
                        />
                      ) : null}
                      <span>{strat.name}</span>
                      {selStatus === "selected" ? (
                        <span className="font-mono text-[10px] opacity-90" aria-hidden="true">✓</span>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            ) : (
              <p className="mt-3 rounded-xl bg-amber-50/90 px-4 py-2.5 text-xs text-amber-900 ring-1 ring-amber-600/20 dark:bg-[#F59E0B]/12 dark:text-[#FDE68A] dark:ring-0">
                {st.noStrategiesPartial}
              </p>
            )}
          </div>

          {strategies.length > 0 && focusedStrategy ? (
            <div className="fs-liquid-well rounded-2xl p-4 text-center">
              <p className="mb-1 font-mono text-[10px] font-semibold uppercase tracking-wider text-[#4A5A4E] dark:text-[#9CA89E]">
                {st.radarTitle}
              </p>
              <ScoreRadarChart
                baseline={baseline}
                focused={focusedStrategy}
                lang={lang}
                plainMode={plainMode}
                variant={resolvedTheme}
              />
            </div>
          ) : null}
        </div>
      </div>

      {/* Strategy Comparison Cards Grid */}
      {strategies.length > 0 ? (
        <div
          className="grid gap-5 md:grid-cols-2 xl:grid-cols-3"
          data-testid="strategy-comparison-grid"
        >
          {strategies.map((strat) => {
            const isSuggested = strat.strategy_id === fieldPlan.suggested_strategy_id;
            const isFocused = focusedStrategy?.strategy_id === strat.strategy_id;
            const selStatus = getStrategySelectionStatus(strat);
            const isSaving = savingStrategyId === strat.strategy_id;
            const confStyle = SEVERITY_STYLE_MAP[strat.confidence];

            return (
              <article
                key={strat.strategy_id}
                data-testid={`strategy-card-${strat.strategy_id}`}
                className={`fs-liquid-panel relative flex flex-col justify-between overflow-hidden rounded-3xl transition-[box-shadow,background-color] duration-150 ease-out ${
                  selStatus === "selected"
                    ? "ring-2 ring-[#15803D]/65 dark:ring-[#22C55E]/60"
                    : isFocused
                      ? "ring-2 ring-[#111813]/25 dark:ring-white/35"
                      : ""
                }`}
              >
                <div className="p-5">
                  {/* Status / Provenance Tags */}
                  <div className="flex flex-wrap items-center gap-2">
                    {isSuggested ? (
                      <span
                        data-testid={`recommended-badge-${strat.strategy_id}`}
                        className="inline-flex items-center gap-1 rounded-full bg-[#22C55E]/15 px-2.5 py-0.5 text-[10px] font-semibold text-[#15803D] ring-1 ring-[#15803D]/25 dark:bg-[#22C55E]/20 dark:text-[#86EFAC] dark:ring-[#4ADE80]/30"
                      >
                        <Medal size={11} weight="fill" aria-hidden="true" />
                        {st.recommendedBadge}
                      </span>
                    ) : null}

                    {strat.is_existing_rotation ? (
                      <span
                        data-testid={`baseline-badge-${strat.strategy_id}`}
                        className="fs-liquid-well rounded-full px-2.5 py-0.5 text-[10px] font-medium text-[#243227] dark:text-[#E4EBE5]"
                      >
                        {st.baselineBadge}
                      </span>
                    ) : null}

                    <span
                      data-testid={`selection-status-${strat.strategy_id}`}
                      className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold ${
                        selStatus === "selected"
                          ? "bg-[#0B3D2E] text-white dark:bg-[#FFFFFF] dark:text-[#111713]"
                          : selStatus === "rejected"
                            ? "bg-red-100 text-red-800 dark:bg-red-500/18 dark:text-red-300"
                            : "fs-liquid-well text-[#4A5A4E] dark:text-[#9CA89E]"
                      }`}
                    >
                      {st.statusBadge[selStatus]}
                    </span>

                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${confStyle.pillClass}`}
                      title={st.confidenceLabel}
                    >
                      {st.confidenceLabel}: {dict.severity[strat.confidence]}
                    </span>
                  </div>

                  {/* Clickable Strategy Heading — keyboard accessible & stretched over card surface */}
                  <button
                    type="button"
                    onClick={() => onFocusStrategy(strat.strategy_id)}
                    className="mt-3 block w-full rounded-lg text-start after:absolute after:inset-0 after:z-[1] after:rounded-3xl after:content-['']"
                  >
                    <h4 className="font-heading text-sm font-semibold leading-[1.2] text-[#111813] hover:text-[#15803D] dark:text-[#F5F7F5] dark:hover:text-[#86EFAC]">
                      {strat.name}
                    </h4>
                  </button>
                  <p className="pointer-events-none mt-1.5 text-xs leading-relaxed text-[#4A5A4E] dark:text-[#9CA89E]">
                    {strat.description}
                  </p>

                  {/* Liquid Well Metrics: Priority Fit & Bare Soil Days */}
                  <div className="fs-liquid-well mt-4 grid grid-cols-2 gap-4 rounded-2xl px-4 py-3">
                    <div>
                      <span className="block text-[10px] font-medium uppercase tracking-wider text-[#4A5A4E] dark:text-[#9CA89E]">
                        {st.priorityFitLabel}
                      </span>
                      <span
                        dir="ltr"
                        className="mt-0.5 block font-mono text-lg font-semibold tabular-nums text-[#15803D] dark:text-[#86EFAC]"
                      >
                        {strat.scores.priority_fit}%
                      </span>
                    </div>

                    <div>
                      <span className="block text-[10px] font-medium uppercase tracking-wider text-[#4A5A4E] dark:text-[#9CA89E]">
                        {st.bareDaysLabel}
                      </span>
                      <span
                        dir="ltr"
                        className="mt-0.5 block font-mono text-lg font-semibold tabular-nums text-amber-700 dark:text-[#FCD34D]"
                      >
                        {strat.scores.bare_field_days_per_year}{" "}
                        <span className="font-sans text-[11px] font-medium text-[#4A5A4E] dark:text-[#9CA89E]">
                          {st.bareDaysUnit}
                        </span>
                      </span>
                    </div>
                  </div>

                  {/* Normalized 0..100 Score Progress Bars */}
                  <div className="mt-4 space-y-2.5">
                    <p className="font-mono text-[10px] font-semibold uppercase tracking-wider text-[#4A5A4E] dark:text-[#9CA89E]">
                      {st.scoreSectionTitle}
                    </p>
                    {STRATEGY_SCORE_KEYS.filter((k) => k !== "priority_fit").map((key) => {
                      const val = strat.scores[key];
                      const lbl = plainMode
                        ? SCORE_LABELS[lang][key].plain
                        : SCORE_LABELS[lang][key].tech;

                      return (
                        <div key={key} className="space-y-1">
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="truncate font-medium text-[#243227] dark:text-[#E4EBE5]">{lbl}</span>
                            <span
                              dir="ltr"
                              className="font-mono font-semibold tabular-nums text-[#15803D] dark:text-[#86EFAC]"
                            >
                              {val}/100
                            </span>
                          </div>
                          <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#111813]/[0.08] dark:bg-white/[0.08]">
                            <div
                              className={`h-full rounded-full transition-[width] duration-300 ease-out ${getScoreProgressClass(val, false, resolvedTheme)}`}
                              style={{ width: `${Math.max(0, Math.min(100, val))}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Tactile Glass Footer Operations */}
                <div className="relative z-10 flex flex-wrap items-center justify-between gap-2 border-t border-[#111813]/10 bg-[#111813]/[0.03] px-4 py-3 dark:border-white/10 dark:bg-white/[0.03]">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={isSaving || selStatus === "selected"}
                      onClick={() =>
                        onUpdateSelection(fieldPlan.field_id, strat.strategy_id, "selected")
                      }
                      data-testid={`select-strategy-${strat.strategy_id}`}
                      className={`inline-flex min-h-10 items-center gap-1.5 rounded-full ps-3 pe-3.5 text-xs font-semibold transition-[transform,background-color,color] duration-150 ease-out active:not-disabled:scale-[0.96] ${
                        selStatus === "selected"
                          ? "bg-[#15803D] text-white dark:bg-[#22C55E] dark:text-[#111713]"
                          : "fs-cta-primary disabled:opacity-60"
                      }`}
                    >
                      {isSaving ? (
                        <SpinnerGap size={13} className="animate-spin" aria-hidden="true" />
                      ) : (
                        <CheckCircle size={13} weight="bold" aria-hidden="true" />
                      )}
                      <span>
                        {isSaving
                          ? st.savingBtn
                          : selStatus === "selected"
                            ? st.selectedBtn
                            : st.selectBtn}
                      </span>
                    </button>

                    <button
                      type="button"
                      disabled={isSaving || selStatus === "rejected"}
                      onClick={() =>
                        onUpdateSelection(fieldPlan.field_id, strat.strategy_id, "rejected")
                      }
                      data-testid={`reject-strategy-${strat.strategy_id}`}
                      className={`inline-flex min-h-10 items-center gap-1 rounded-full ps-2.5 pe-3 text-xs font-medium transition-[transform,background-color,color] duration-150 ease-out active:not-disabled:scale-[0.96] ${
                        selStatus === "rejected"
                          ? "bg-red-100 text-red-800 ring-1 ring-red-600/30 dark:bg-red-500/20 dark:text-red-200 dark:ring-red-400/30"
                          : "fs-liquid-pill text-[#4A5A4E] hover:text-red-700 disabled:opacity-60 dark:text-[#9CA89E] dark:hover:text-red-300"
                      }`}
                    >
                      <Prohibit size={13} aria-hidden="true" />
                      <span>{selStatus === "rejected" ? st.rejectedBtn : st.rejectBtn}</span>
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={() => onFocusStrategy(strat.strategy_id)}
                    aria-label={`${strat.name} (${strat.seasons.length} ${UI_DICT[lang].comparison.seasonsUnitAria})`}
                    className={`inline-flex min-h-10 items-center gap-1 rounded-full px-2.5 text-[11px] font-medium transition-[transform,background-color,color] duration-150 ease-out active:not-disabled:scale-[0.96] ${
                      isFocused
                        ? "bg-[#22C55E]/15 text-[#15803D] dark:bg-[#22C55E]/20 dark:text-[#86EFAC]"
                        : "text-[#4A5A4E] hover:bg-[#111813]/[0.08] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:bg-white/[0.08] dark:hover:text-[#F5F7F5]"
                    }`}
                  >
                    <SlidersHorizontal size={13} aria-hidden="true" />
                    <span className="font-mono tabular-nums">{strat.seasons.length}</span>
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      ) : null}

      {/* Focused Strategy Deep-Dive Inspector */}
      {focusedStrategy ? (
        <div
          className="fs-liquid-panel space-y-6 overflow-hidden rounded-3xl p-5 sm:p-6"
          data-testid="focused-strategy-inspector"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <span className="font-mono text-[10px] font-medium uppercase tracking-wider text-[#4A5A4E] dark:text-[#9CA89E]">
                {focusedStrategy.strategy_id}
              </span>
              <h4 className="mt-0.5 font-heading text-base font-semibold leading-[1.15] text-[#111813] dark:text-[#F5F7F5]">
                {focusedStrategy.name}
              </h4>
            </div>
            <span className="fs-liquid-well rounded-full px-3 py-1 font-mono text-xs font-semibold tabular-nums text-[#15803D] dark:text-[#86EFAC]">
              {st.priorityFitLabel}: {focusedStrategy.scores.priority_fit}%
            </span>
          </div>

          <CropRotationTimeline
            strategyId={focusedStrategy.strategy_id}
            seasons={focusedStrategy.seasons}
            catalogMap={catalogMap}
            lang={lang}
          />

          <StrategyExplanationTabs
            strategyId={focusedStrategy.strategy_id}
            explanation={focusedStrategy.explanation}
            lang={lang}
            plainMode={plainMode}
          />
        </div>
      ) : null}
    </section>
  );
}
