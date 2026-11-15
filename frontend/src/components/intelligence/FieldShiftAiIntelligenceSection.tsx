"use client";

import React from "react";
import Link from "next/link";
import {
  ArrowRight,
  Brain,
  CheckCircle,
  Compass,
  Play,
  Printer,
  Prohibit,
  SpinnerGap,
  Translate,
  WarningOctagon,
} from "@phosphor-icons/react";
import { useResolvedTheme } from "@/app/providers";
import { PrintableBrief } from "@/components/comparison/PrintableBrief";
import { AnalysisOverviewCard } from "@/components/intelligence/AnalysisOverviewCard";
import { FieldInsightsPanel } from "@/components/intelligence/FieldInsightsPanel";
import { RequestedCropsAndQualitySection } from "@/components/intelligence/RequestedCropsAndQualitySection";
import { StrategyComparisonSection } from "@/components/intelligence/StrategyComparisonSection";
import { ApiErrorCard } from "@/components/shared/ProvenanceBanners";
import { findFieldPlanForField } from "@/lib/analysis/workspaceAnalysis";
import { localizeFieldName } from "@/lib/i18n/dynamicText";
import { INTELLIGENCE_I18N } from "@/lib/i18n/intelligence";
import type {
  AnalysisEnvelope,
  CropItem,
  FarmAnalysisSummary,
  FarmPublic,
  FieldDetailPublic,
  Language,
} from "@/lib/schemas";

export type AnalysisRunLifecycle =
  | "idle"
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

interface FieldShiftAiIntelligenceSectionProps {
  lang: Language;
  plainMode: boolean;
  hasFields: boolean;
  activeFarm: FarmPublic | null;
  activeField: FieldDetailPublic | null;
  lifecycle: AnalysisRunLifecycle;
  cancelling: boolean;
  error: unknown;
  envelope: AnalysisEnvelope | null;
  farmAnalyses: FarmAnalysisSummary[];
  focusedFieldPlanId: string | null;
  focusedStrategyId: string | null;
  savingStrategyId: string | null;
  toast: { kind: "success" | "error"; message: string } | null;
  catalogItems: CropItem[];
  onTogglePlainMode: () => void;
  onOpenRunner: (preselectFieldId?: string) => void;
  onPreviewDemo: () => void;
  onCancelRun: () => void;
  onRetry: () => void;
  onOpenAuthModal: () => void;
  onSwitchAnalysis: (analysisId: string) => void;
  onSelectFieldPlan: (fieldId: string) => void;
  onFocusStrategy: (strategyId: string) => void;
  onUpdateSelection: (
    fieldId: string,
    strategyId: string,
    selectionStatus: "selected" | "rejected"
  ) => void;
}

export function FieldShiftAiIntelligenceSection({
  lang,
  plainMode,
  hasFields,
  activeField,
  lifecycle,
  cancelling,
  error,
  envelope,
  farmAnalyses,
  focusedFieldPlanId,
  focusedStrategyId,
  savingStrategyId,
  toast,
  catalogItems,
  onTogglePlainMode,
  onOpenRunner,
  onPreviewDemo,
  onCancelRun,
  onRetry,
  onOpenAuthModal,
  onSwitchAnalysis,
  onSelectFieldPlan,
  onFocusStrategy,
  onUpdateSelection,
}: FieldShiftAiIntelligenceSectionProps) {
  const resolvedTheme = useResolvedTheme();
  const dict = INTELLIGENCE_I18N[lang];
  const sec = dict.section;
  const st = dict.states;

  const catalogMap = React.useMemo(
    () => new Map<string, CropItem>(catalogItems.map((c) => [c.crop_id, c])),
    [catalogItems]
  );

  const activeFieldPlan = React.useMemo(
    () =>
      findFieldPlanForField(
        envelope,
        focusedFieldPlanId ?? activeField?.field_id ?? null
      ),
    [envelope, focusedFieldPlanId, activeField?.field_id]
  );

  const printableStrategy = React.useMemo(() => {
    if (!activeFieldPlan) return undefined;
    return (
      activeFieldPlan.strategies.find((s) => s.strategy_id === focusedStrategyId) ??
      activeFieldPlan.strategies.find(
        (s) => s.strategy_id === activeFieldPlan.suggested_strategy_id
      ) ??
      activeFieldPlan.strategies[0]
    );
  }, [activeFieldPlan, focusedStrategyId]);

  const activeFieldMissingFromEnvelope = Boolean(
    envelope &&
      activeField &&
      !envelope.result.field_plans.some((fp) => fp.field_id === activeField.field_id)
  );

  return (
    <section
      id="ai-intelligence"
      data-testid="ai-intelligence-section"
      className="space-y-4 pt-1"
    >
      {/* Workstation Section Header & Controls */}
      <div className="fs-liquid-panel rounded-3xl px-5 py-4 sm:px-6 no-print">
        <div className="flex flex-col gap-3.5 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Brain size={16} weight="duotone" className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
              <span className="font-mono text-[11px] font-medium uppercase tracking-wider text-[#4A5A4E] dark:text-[#9CA89E]">
                {sec.badge}
              </span>
            </div>
            <h2 className="mt-0.5 font-heading text-base font-semibold tracking-tight text-[#111813] dark:text-[#F5F7F5] sm:text-lg">
              {sec.title}
            </h2>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={onTogglePlainMode}
              data-testid="toggle-plain-mode-btn"
              aria-pressed={plainMode}
              className={`inline-flex min-h-10 items-center gap-1.5 rounded-full ps-3 pe-3.5 text-xs font-medium transition-[transform,background-color,box-shadow,color] active:not-disabled:scale-[0.96] ${
                plainMode
                  ? "bg-[#22C55E]/20 text-[#15803D] ring-1 ring-[#15803D]/35 dark:text-[#86EFAC] dark:ring-[#4ADE80]/35"
                  : "fs-liquid-pill text-[#111813] dark:text-[#F5F7F5]"
              }`}
            >
              <Translate size={15} aria-hidden="true" />
              <span>{plainMode ? sec.plainModeOn : sec.plainModeOff}</span>
            </button>

            {envelope && activeFieldPlan ? (
              <button
                type="button"
                onClick={() => window.print()}
                className="fs-liquid-pill inline-flex min-h-10 items-center gap-1.5 rounded-full ps-3 pe-3.5 text-xs font-medium text-[#111813] dark:text-[#F5F7F5] active:not-disabled:scale-[0.96]"
              >
                <Printer size={15} aria-hidden="true" />
                <span>{sec.printBriefBtn}</span>
              </button>
            ) : null}

            <Link
              href={
                envelope
                  ? `/comparison?analysisId=${encodeURIComponent(envelope.analysis_id)}`
                  : "/comparison"
              }
              className="fs-liquid-pill inline-flex min-h-10 items-center gap-1.5 rounded-full ps-3.5 pe-3 text-xs font-medium text-[#243227] hover:text-[#111813] dark:text-[#D1DBD3] dark:hover:text-[#FFFFFF] active:not-disabled:scale-[0.96]"
            >
              <span>{sec.openComparisonPage}</span>
              <ArrowRight
                size={13}
                className={lang === "ar" ? "-scale-x-100" : "rtl:-scale-x-100"}
                aria-hidden="true"
              />
            </Link>

            {!envelope ? (
              <button
                type="button"
                onClick={onPreviewDemo}
                data-testid="preview-demo-intelligence-btn"
                className="fs-liquid-pill inline-flex min-h-10 items-center gap-1.5 rounded-full ps-3 pe-3.5 text-xs font-medium text-[#15803D] dark:text-[#86EFAC] active:not-disabled:scale-[0.96]"
              >
                <Compass size={15} weight="duotone" aria-hidden="true" />
                <span>{sec.previewDemoBtn}</span>
              </button>
            ) : null}

            {hasFields ? (
              <button
                type="button"
                onClick={() => onOpenRunner(activeField?.field_id)}
                data-testid="run-ai-analysis-btn"
                className="fs-cta-primary inline-flex min-h-10 items-center gap-1.5 rounded-full ps-3.5 pe-4 text-xs font-semibold active:not-disabled:scale-[0.96]"
              >
                <Play size={13} weight="fill" aria-hidden="true" />
                <span>{envelope ? sec.runNewBtn : dict.header.runAiBtn}</span>
              </button>
            ) : null}
          </div>
        </div>

        {/* State A compact status strip (single container, no repeated CTAs) */}
        {lifecycle !== "pending" && lifecycle !== "running" && !envelope ? (
          <div
            data-testid="analysis-empty-state"
            className="fs-liquid-well mt-4 flex flex-wrap items-center justify-between gap-2 rounded-2xl px-4 py-3 text-xs"
          >
            <div className="flex flex-wrap items-center gap-2 text-[#4A5A4E] dark:text-[#9CA89E]">
              <span className="font-semibold text-[#111813] dark:text-[#F5F7F5]">
                {hasFields ? st.unanalyzedTitle : st.noFieldsTitle}
              </span>
              <span aria-hidden="true">·</span>
              <span className="max-w-[65ch]">{hasFields ? st.unanalyzedDesc : st.noFieldsDesc}</span>
            </div>
          </div>
        ) : null}
      </div>

      {/* Feedback Toast */}
      {toast ? (
        <div
          role="status"
          aria-live="polite"
          data-testid="intelligence-toast"
          className={`no-print flex items-center gap-2 rounded-2xl border px-4 py-3 text-xs font-medium shadow-xs backdrop-blur-md ${
            toast.kind === "success"
              ? "border-[#15803D]/30 bg-[#22C55E]/15 text-[#14532D] dark:border-[#4ADE80]/30 dark:text-[#86EFAC]"
              : "border-red-600/35 bg-red-50/95 text-red-900 dark:border-red-400/35 dark:bg-red-950/60 dark:text-red-200"
          }`}
        >
          {toast.kind === "success" ? (
            <CheckCircle size={15} weight="fill" className="shrink-0 text-[#15803D] dark:text-[#4ADE80]" aria-hidden="true" />
          ) : (
            <WarningOctagon size={15} weight="fill" className="shrink-0 text-red-600 dark:text-red-400" aria-hidden="true" />
          )}
          <span>{toast.message}</span>
        </div>
      ) : null}

      {/* API Error Card */}
      {error !== null ? (
        <ApiErrorCard
          error={error}
          lang={lang}
          theme={resolvedTheme}
          onRetry={onRetry}
          onOpenClaimAccount={onOpenAuthModal}
        />
      ) : null}

      {/* Running / Pending State */}
      {lifecycle === "pending" || lifecycle === "running" ? (
        <div
          data-testid="analysis-running-card"
          className="fs-liquid-panel flex flex-wrap items-center justify-between gap-4 rounded-3xl px-5 py-4"
        >
          <div className="flex items-center gap-3.5">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#22C55E]/15 text-[#15803D] ring-1 ring-[#15803D]/25 dark:text-[#86EFAC] dark:ring-[#4ADE80]/25">
              <SpinnerGap size={20} className="animate-spin" aria-hidden="true" />
            </span>
            <div>
              <h3 className="font-heading text-sm font-semibold text-[#111813] dark:text-[#F5F7F5]">
                {lifecycle === "pending" ? st.pendingTitle : st.runningTitle}
              </h3>
              <p className="mt-0.5 max-w-[65ch] text-xs text-[#4A5A4E] dark:text-[#9CA89E]">
                {lifecycle === "pending" ? st.pendingDesc : st.runningDesc}
              </p>
            </div>
          </div>
          <button
            type="button"
            disabled={cancelling}
            onClick={onCancelRun}
            data-testid="cancel-ai-analysis-btn"
            className="inline-flex min-h-10 items-center gap-1.5 rounded-full border border-red-600/30 bg-red-50/90 px-3.5 text-xs font-medium text-red-700 transition-[transform,background-color] hover:bg-red-100 active:not-disabled:scale-[0.96] disabled:opacity-50 dark:border-red-400/30 dark:bg-red-500/15 dark:text-red-200 dark:hover:bg-red-500/25"
          >
            <Prohibit size={15} aria-hidden="true" />
            <span>{cancelling ? st.cancelling : st.cancelBtn}</span>
          </button>
        </div>
      ) : null}

      {/* Cancelled State */}
      {lifecycle === "cancelled" && !envelope ? (
        <div className="fs-liquid-well rounded-2xl px-5 py-3.5 text-xs">
          <span className="font-semibold text-[#111813] dark:text-[#F5F7F5]">{st.cancelledTitle}</span>
          <span className="ms-2 text-[#4A5A4E] dark:text-[#9CA89E]">{st.cancelledDesc}</span>
        </div>
      ) : null}

      {/* Active Completed / Partial Analysis Experience (State B) */}
      {envelope ? (
        <div className="space-y-4 no-print">
          <AnalysisOverviewCard
            lang={lang}
            plainMode={plainMode}
            envelope={envelope}
            farmAnalyses={farmAnalyses}
            activeFieldPlan={activeFieldPlan}
            selectedWorkspaceFieldId={activeField?.field_id ?? null}
            onSelectFieldPlan={onSelectFieldPlan}
            onSwitchAnalysis={onSwitchAnalysis}
          />

          {activeFieldMissingFromEnvelope && activeField ? (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-600/30 bg-amber-50/90 px-5 py-3.5 text-xs text-amber-900 backdrop-blur-md dark:border-[#F59E0B]/30 dark:bg-[#F59E0B]/12 dark:text-[#FDE68A]">
              <div>
                <p className="font-semibold">
                  {localizeFieldName(activeField.field_name, lang)} ({activeField.field_id}) — {st.unlinkedFieldTitle}
                </p>
                <p className="mt-0.5 max-w-[65ch] text-amber-800/90 dark:text-[#D1DBD3]">{st.unlinkedFieldDesc}</p>
              </div>
              <button
                type="button"
                onClick={() => onOpenRunner(activeField.field_id)}
                className="fs-cta-primary inline-flex min-h-10 items-center gap-1.5 rounded-full ps-3.5 pe-4 text-xs font-semibold active:not-disabled:scale-[0.96]"
              >
                <Brain size={14} weight="duotone" aria-hidden="true" />
                <span>{st.unlinkedFieldCta}</span>
              </button>
            </div>
          ) : null}

          {activeFieldPlan ? (
            <>
              <FieldInsightsPanel
                insights={activeFieldPlan.field_insights}
                lang={lang}
                plainMode={plainMode}
              />

              <StrategyComparisonSection
                fieldPlan={activeFieldPlan}
                focusedStrategyId={focusedStrategyId}
                savingStrategyId={savingStrategyId}
                catalogMap={catalogMap}
                lang={lang}
                plainMode={plainMode}
                onFocusStrategy={onFocusStrategy}
                onUpdateSelection={onUpdateSelection}
              />

              <RequestedCropsAndQualitySection
                requestedCrops={activeFieldPlan.requested_crop_results}
                farmDataQuality={envelope.result.data_quality}
                fieldPlan={activeFieldPlan}
                catalogMap={catalogMap}
                lang={lang}
                plainMode={plainMode}
              />
            </>
          ) : null}
        </div>
      ) : null}

      {/* Preserved 1-page Print Brief */}
      {envelope && activeFieldPlan ? (
        <PrintableBrief
          envelope={envelope}
          fieldPlan={activeFieldPlan}
          strategy={printableStrategy}
        />
      ) : null}
    </section>
  );
}
