"use client";

import React from "react";
import {
  Brain,
  CheckCircle,
  ClockCounterClockwise,
  Info,
  MapPin,
  ShieldWarning,
  WarningCircle,
} from "@phosphor-icons/react";
import { useResolvedTheme } from "@/app/providers";
import { DegradedReplayBanner, WarningsBanner } from "@/components/shared/ProvenanceBanners";
import { ANALYSIS_JOB_STATUS_LABELS, localizePlainText, UI_DICT } from "@/lib/i18n";
import { localizeFieldName } from "@/lib/i18n/dynamicText";
import { INTELLIGENCE_I18N } from "@/lib/i18n/intelligence";
import type {
  AnalysisEnvelope,
  FarmAnalysisSummary,
  FieldPlan,
  Language,
} from "@/lib/schemas";

interface AnalysisOverviewCardProps {
  lang: Language;
  plainMode?: boolean;
  envelope: AnalysisEnvelope;
  farmAnalyses: FarmAnalysisSummary[];
  activeFieldPlan: FieldPlan | null;
  selectedWorkspaceFieldId?: string | null;
  onSelectFieldPlan: (fieldId: string) => void;
  onSwitchAnalysis: (analysisId: string) => void;
}

export function AnalysisOverviewCard({
  lang,
  plainMode = false,
  envelope,
  farmAnalyses,
  activeFieldPlan,
  selectedWorkspaceFieldId,
  onSelectFieldPlan,
  onSwitchAnalysis,
}: AnalysisOverviewCardProps) {
  const resolvedTheme = useResolvedTheme();
  const dict = INTELLIGENCE_I18N[lang];
  const ov = dict.overview;
  const res = envelope.result;
  const completedRuns = farmAnalyses.filter((a) => a.analysis_id);

  const selectedFieldMissingFromPlan =
    Boolean(selectedWorkspaceFieldId) &&
    !res.field_plans.some((fp) => fp.field_id === selectedWorkspaceFieldId);

  return (
    <div className="space-y-3">
      {/* Degraded Replay Banner (ADR-8) */}
      <DegradedReplayBanner degradedMode={envelope.degraded_mode} lang={lang} theme={resolvedTheme} />

      {/* Envelope Warnings (clearly separate from result.data_quality.warnings) */}
      {envelope.warnings.length > 0 ? (
        <div
          className="rounded-3xl bg-amber-50/90 p-4 backdrop-blur-md ring-1 ring-amber-600/25 dark:bg-[#F59E0B]/12 dark:ring-[#F59E0B]/30"
          data-testid="envelope-warnings-section"
        >
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-amber-800 dark:text-[#FCD34D]">
            {ov.envelopeWarningsTitle}
          </p>
          <WarningsBanner warnings={envelope.warnings} lang={lang} theme={resolvedTheme} />
        </div>
      ) : null}

      {/* Executive Summary & Provenance Ledger */}
      <section
        className="fs-liquid-panel space-y-6 overflow-hidden rounded-3xl p-5 sm:p-6"
        data-testid="analysis-summary-card"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2.5">
            <span
              data-testid="analysis-status-pill"
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
                res.status === "ok"
                  ? "bg-[#22C55E]/15 text-[#15803D] dark:text-[#86EFAC]"
                  : "bg-amber-100 text-amber-800 dark:bg-[#F59E0B]/15 dark:text-[#FCD34D]"
              }`}
            >
              {res.status === "ok" ? (
                <CheckCircle size={14} weight="fill" className="text-[#15803D] dark:text-[#4ADE80]" aria-hidden="true" />
              ) : (
                <WarningCircle size={14} weight="fill" className="text-amber-700 dark:text-[#FCD34D]" aria-hidden="true" />
              )}
              {res.status === "ok" ? ov.statusOk : ov.statusPartial}
            </span>

            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
                envelope.degraded_mode
                  ? "bg-amber-100 text-amber-900 dark:bg-[#F59E0B]/15 dark:text-[#FDE68A]"
                  : "fs-liquid-well text-[#111813] dark:text-[#F5F7F5]"
              }`}
            >
              <Brain size={13} weight="duotone" className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
              {envelope.degraded_mode ? ov.staleBadge : ov.freshBadge}
            </span>
          </div>

          {completedRuns.length > 1 ? (
            <label className="inline-flex items-center gap-2 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">
              <ClockCounterClockwise size={14} className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
              <span className="font-medium">{dict.section.historyLabel}:</span>
              <select
                value={envelope.analysis_id}
                onChange={(e) => onSwitchAnalysis(e.target.value)}
                data-testid="analysis-history-select"
                className="fs-liquid-pill min-h-10 rounded-xl bg-white/90 px-3 font-mono text-base font-medium text-[#111813] dark:bg-[#141A16] dark:text-[#F5F7F5] sm:text-xs"
              >
                {completedRuns.map((run) => (
                  <option key={run.analysis_id} value={run.analysis_id!}>
                    {run.analysis_id} ·{" "}
                    {run.status === "ok"
                      ? UI_DICT[lang].common.okShort
                      : run.status === "partial"
                      ? ov.statusPartial
                      : ANALYSIS_JOB_STATUS_LABELS[lang][run.status] ?? run.status.toUpperCase()}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
        </div>

        {/* Summary + Disclaimer */}
        <div className="grid gap-5 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <h3 className="font-mono text-[11px] font-medium uppercase tracking-wider text-[#4A5A4E] dark:text-[#9CA89E]">
              {ov.summaryHeading}
            </h3>
            <p className="mt-2 max-w-[68ch] text-sm leading-relaxed text-[#111813] dark:text-[#F5F7F5]">
              {localizePlainText(res.overall_summary, lang, plainMode)}
            </p>
          </div>

          <div className="rounded-2xl bg-amber-50/90 p-4 text-xs text-amber-950 ring-1 ring-amber-600/25 dark:bg-[#F59E0B]/10 dark:text-[#E4EBE5] dark:ring-[#F59E0B]/25">
            <p className="flex items-center gap-1.5 font-semibold text-amber-900 dark:text-[#FDE68A]">
              <ShieldWarning size={14} weight="fill" className="shrink-0 text-amber-600 dark:text-[#FCD34D]" aria-hidden="true" />
              {ov.disclaimerHeading}
            </p>
            <p className="mt-1.5 text-[11px] leading-relaxed text-amber-900/85 dark:text-[#D1DBD3]">
              {localizePlainText(res.disclaimer, lang, plainMode)}
            </p>
          </div>
        </div>

        {/* Floating Well Provenance Ledger (no border-box grid) */}
        <div className="fs-liquid-well grid grid-cols-2 gap-4 rounded-2xl px-4 py-3.5 sm:grid-cols-5">
          <div>
            <span className="block text-[10px] font-medium text-[#4A5A4E] dark:text-[#9CA89E]">
              {ov.analysisIdLabel}
            </span>
            <code
              dir="ltr"
              className="mt-0.5 block truncate font-mono text-[11px] font-semibold text-[#15803D] dark:text-[#86EFAC]"
            >
              {envelope.analysis_id}
            </code>
          </div>
          <div>
            <span className="block text-[10px] font-medium text-[#4A5A4E] dark:text-[#9CA89E]">
              {ov.generatedAtLabel}
            </span>
            <span
              dir="ltr"
              className="mt-0.5 block truncate font-mono text-[11px] font-medium tabular-nums text-[#111813] dark:text-[#F5F7F5]"
            >
              {res.generated_at.slice(0, 19).replace("T", " ")}
            </span>
          </div>
          <div>
            <span className="block text-[10px] font-medium text-[#4A5A4E] dark:text-[#9CA89E]">
              {ov.datasetVersionLabel}
            </span>
            <code
              dir="ltr"
              className="mt-0.5 block truncate font-mono text-[11px] font-medium text-[#111813] dark:text-[#F5F7F5]"
            >
              {res.dataset_version_used}
            </code>
          </div>
          <div>
            <span className="block text-[10px] font-medium text-[#4A5A4E] dark:text-[#9CA89E]">
              {ov.engineVersionLabel}
            </span>
            <code
              dir="ltr"
              className="mt-0.5 block truncate font-mono text-[11px] font-medium text-[#111813] dark:text-[#F5F7F5]"
            >
              {res.ml_engine_version}
            </code>
          </div>
          <div>
            <span className="block text-[10px] font-medium text-[#4A5A4E] dark:text-[#9CA89E]">
              {ov.schemaVersionLabel}
            </span>
            <code
              dir="ltr"
              className="mt-0.5 block truncate font-mono text-[11px] font-medium text-[#111813] dark:text-[#F5F7F5]"
            >
              v{res.schema_version}
            </code>
          </div>
        </div>

        {/* Multi-Field Selector Tabs */}
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs font-semibold text-[#111813] dark:text-[#F5F7F5]">
              {ov.fieldSelectorHeading} ({res.field_plans.length})
            </span>
            {selectedFieldMissingFromPlan ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-1 text-[11px] font-medium text-amber-800 dark:bg-[#F59E0B]/15 dark:text-[#FCD34D]">
                <Info size={12} aria-hidden="true" />
                {dict.states.unlinkedFieldTitle}
              </span>
            ) : null}
          </div>

          <div className="flex flex-wrap gap-2.5">
            {res.field_plans.map((fp) => {
              const active = activeFieldPlan?.field_id === fp.field_id;
              return (
                <button
                  key={fp.field_id}
                  type="button"
                  onClick={() => onSelectFieldPlan(fp.field_id)}
                  data-testid={`field-plan-tab-${fp.field_id}`}
                  aria-pressed={active}
                  className={`inline-flex min-h-10 items-center gap-2 rounded-full ps-3 pe-3.5 text-xs font-medium transition-[transform,background-color,box-shadow,color] duration-150 ease-out active:not-disabled:scale-[0.96] ${
                    active
                      ? "bg-[#0B3D2E] font-semibold text-white shadow-[0_4px_14px_rgba(11,61,46,0.22)] dark:bg-[#FFFFFF] dark:text-[#111713] dark:shadow-[0_4px_14px_rgba(0,0,0,0.35)]"
                      : "fs-liquid-well fs-liquid-well-interactive text-[#111813] dark:text-[#F5F7F5]"
                  }`}
                >
                  <MapPin size={13} weight="fill" aria-hidden="true" />
                  <span>{localizeFieldName(fp.field_name, lang)}</span>
                  <span
                    className={`rounded-full px-2 py-0.5 font-mono text-[10px] ${
                      fp.status === "ok"
                        ? active
                          ? "bg-white/20 text-white dark:bg-[#111713]/12 dark:text-[#111713]"
                          : "bg-[#22C55E]/15 text-[#15803D] dark:text-[#86EFAC]"
                        : "bg-amber-100 text-amber-800 dark:bg-[#F59E0B]/18 dark:text-[#FCD34D]"
                    }`}
                  >
                    {fp.field_id} · {fp.status === "ok" ? UI_DICT[lang].common.okShort : ov.statusPartial}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </section>
    </div>
  );
}
