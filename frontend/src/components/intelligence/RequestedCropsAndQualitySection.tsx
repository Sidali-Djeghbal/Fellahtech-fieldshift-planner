"use client";

import React from "react";
import {
  ArrowsLeftRight,
  CheckCircle,
  ClipboardText,
  Database,
  Info,
  Prohibit,
  ShieldCheck,
  Warning,
} from "@phosphor-icons/react";
import { resolveCropDisplayName } from "@/lib/analysis/workspaceAnalysis";
import { INTELLIGENCE_I18N } from "@/lib/i18n/intelligence";
import type {
  CropItem,
  DataQuality,
  FieldPlan,
  Language,
  RequestedCropEvaluation,
} from "@/lib/schemas";

interface RequestedCropsAndQualitySectionProps {
  requestedCrops: RequestedCropEvaluation[];
  farmDataQuality: DataQuality;
  fieldPlan: FieldPlan;
  catalogMap: Map<string, CropItem>;
  lang: Language;
}

export function RequestedCropsAndQualitySection({
  requestedCrops,
  farmDataQuality,
  fieldPlan,
  catalogMap,
  lang,
}: RequestedCropsAndQualitySectionProps) {
  const dict = INTELLIGENCE_I18N[lang];
  const rc = dict.requestedCrops;
  const dq = dict.quality;

  return (
    <div className="space-y-6">
      {/* Requested Crop Disposition Ledger */}
      <section
        className="fs-liquid-panel space-y-5 overflow-hidden rounded-3xl p-5 sm:p-6"
        data-testid="requested-crops-section"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="flex items-center gap-2 font-heading text-sm font-semibold leading-[1.15] text-[#111813] sm:text-base dark:text-[#F5F7F5]">
              <ArrowsLeftRight size={17} weight="duotone" className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
              <span>{rc.heading}</span>
            </h3>
            <p className="mt-1 max-w-[65ch] text-xs text-[#4A5A4E] dark:text-[#9CA89E]">{rc.subtitle}</p>
          </div>
          <span className="fs-liquid-well rounded-full px-3 py-0.5 font-mono text-xs font-semibold tabular-nums text-[#15803D] dark:text-[#86EFAC]">
            {requestedCrops.length}
          </span>
        </div>

        <div>
          {requestedCrops.length === 0 ? (
            <p className="fs-liquid-well rounded-2xl px-4 py-3 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">
              {rc.emptyNotice}
            </p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {requestedCrops.map((item) => {
                const cropName = resolveCropDisplayName(
                  item.requested_crop_id,
                  null,
                  catalogMap,
                  lang
                );
                const replacementName = item.replaced_by_crop_id
                  ? resolveCropDisplayName(item.replaced_by_crop_id, null, catalogMap, lang)
                  : null;

                const badgeClass =
                  item.outcome === "included"
                    ? "bg-emerald-100 text-emerald-800 dark:bg-[#22C55E]/15 dark:text-[#86EFAC]"
                    : item.outcome === "replaced"
                      ? "bg-amber-100 text-amber-800 dark:bg-[#F59E0B]/15 dark:text-[#FCD34D]"
                      : "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300";

                return (
                  <article
                    key={item.requested_crop_id}
                    data-testid={`requested-crop-${item.requested_crop_id}`}
                    className="fs-liquid-well rounded-2xl p-4 text-xs"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <h4 className="text-sm font-semibold text-[#111813] dark:text-[#F5F7F5]">{cropName}</h4>
                        <code dir="ltr" className="font-mono text-[10px] text-[#4A5A4E] dark:text-[#9CA89E]">
                          {item.requested_crop_id}
                        </code>
                      </div>

                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${badgeClass}`}
                      >
                        {item.outcome === "included" ? (
                          <CheckCircle size={12} weight="fill" aria-hidden="true" />
                        ) : item.outcome === "excluded" ? (
                          <Prohibit size={12} weight="fill" aria-hidden="true" />
                        ) : (
                          <ArrowsLeftRight size={12} weight="bold" aria-hidden="true" />
                        )}
                        {rc.outcomes[item.outcome]}
                      </span>
                    </div>

                    {replacementName ? (
                      <p className="mt-2.5 rounded-xl bg-amber-50/90 px-3 py-1.5 text-[11px] font-medium text-amber-900 ring-1 ring-amber-600/20 dark:bg-[#F59E0B]/12 dark:text-[#FDE68A] dark:ring-0">
                        {rc.replacedBy}: <strong>{replacementName}</strong>{" "}
                        <code dir="ltr" className="font-mono text-[10px]">
                          ({item.replaced_by_crop_id})
                        </code>
                      </p>
                    ) : null}

                    <p className="mt-2.5 leading-relaxed text-[#243227] dark:text-[#E4EBE5]">{item.explanation}</p>

                    <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-[#111813]/10 pt-2.5 text-[10px] dark:border-white/10">
                      <span className="font-medium text-[#4A5A4E] dark:text-[#9CA89E]">{rc.includedIn}:</span>
                      {item.included_in_strategy_ids.length === 0 ? (
                        <span className="text-[#4A5A4E] dark:text-[#9CA89E]">{rc.noStrategies}</span>
                      ) : (
                        item.included_in_strategy_ids.map((sid) => (
                          <span
                            key={sid}
                            dir="ltr"
                            className="rounded-full bg-emerald-100 px-2 py-0.5 font-mono font-medium text-emerald-800 dark:bg-[#22C55E]/15 dark:text-[#86EFAC]"
                          >
                            {sid}
                          </span>
                        ))
                      )}
                      {item.evidence && item.evidence.length > 0 ? (
                        <span className="rounded-full bg-sky-100 px-2 py-0.5 font-medium text-sky-800 dark:bg-sky-500/15 dark:text-sky-300">
                          {rc.evidenceCount(item.evidence.length)}
                        </span>
                      ) : null}
                      {item.comparison && item.comparison.length > 0 ? (
                        <span className="fs-liquid-pill rounded-full px-2 py-0.5 font-medium text-[#111813] dark:text-[#F5F7F5]">
                          {rc.comparisonCount(item.comparison.length)}
                        </span>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </div>
      </section>

      {/* Farm & Field Data Quality & Limitations */}
      <section className="fs-liquid-panel space-y-5 overflow-hidden rounded-3xl p-5 sm:p-6">
        <div>
          <h3 className="flex items-center gap-2 font-heading text-sm font-semibold leading-[1.15] text-[#111813] sm:text-base dark:text-[#F5F7F5]">
            <Database size={17} weight="duotone" className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
            <span>{dq.heading}</span>
          </h3>
          <p className="mt-1.5 flex items-center gap-1.5 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">
            <Info size={13} className="shrink-0 text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
            <span>{dq.completenessVsConfidenceNote}</span>
          </p>
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          <QualityColumn
            testId="data-quality-farm"
            title={dq.farmTitle}
            quality={farmDataQuality}
            lang={lang}
          />
          <QualityColumn
            testId="data-quality-field"
            title={`${dq.fieldTitle} (${fieldPlan.field_id})`}
            quality={fieldPlan.data_quality}
            lang={lang}
          />
        </div>
      </section>
    </div>
  );
}

function QualityColumn({
  testId,
  title,
  quality,
  lang,
}: {
  testId: string;
  title: string;
  quality: DataQuality;
  lang: Language;
}) {
  const dq = INTELLIGENCE_I18N[lang].quality;
  const pct =
    typeof quality.completeness_score === "number"
      ? Math.round(quality.completeness_score * 100)
      : null;

  return (
    <article
      data-testid={testId}
      className="fs-liquid-well flex flex-col justify-between rounded-2xl p-4 text-xs sm:p-5"
    >
      <div>
        <div className="flex items-center justify-between gap-2">
          <h4 className="font-semibold text-[#111813] dark:text-[#F5F7F5]">{title}</h4>
          <span
            dir="ltr"
            className="tabular-nums rounded-full bg-emerald-100 px-2.5 py-0.5 font-mono text-xs font-semibold text-emerald-800 dark:bg-[#22C55E]/15 dark:text-[#86EFAC]"
          >
            {pct !== null ? `${pct}%` : dq.completenessUnavailable}
          </span>
        </div>

        <div className="mt-3">
          <div className="flex justify-between text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
            <span>{dq.completenessLabel}</span>
            <span dir="ltr" className="tabular-nums font-mono">
              {pct !== null ? `${pct}%` : "—"}
            </span>
          </div>
          <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-[#111813]/[0.08] dark:bg-white/[0.08]">
            <div
              className="h-full rounded-full bg-[#15803D] transition-[width] duration-300 ease-out dark:bg-[#22C55E]"
              style={{ width: `${pct ?? 0}%` }}
            />
          </div>
        </div>

        {quality.confidence_note ? (
          <p className="mt-3 rounded-xl bg-[#111813]/[0.04] px-3.5 py-2.5 text-[11px] leading-relaxed text-[#243227] dark:bg-white/[0.05] dark:text-[#E4EBE5]">
            {quality.confidence_note}
          </p>
        ) : null}

        <div className="mt-4">
          <p className="flex items-center gap-1.5 font-mono text-[10px] font-semibold uppercase tracking-wider text-[#4A5A4E] dark:text-[#9CA89E]">
            <ClipboardText size={13} className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
            <span>{dq.missingDataTitle}</span>
          </p>
          {quality.missing_data.length === 0 ? (
            <p className="mt-1 flex items-center gap-1 text-[11px] text-[#15803D] dark:text-[#86EFAC]">
              <ShieldCheck size={13} weight="fill" aria-hidden="true" />
              <span>{dq.missingDataEmpty}</span>
            </p>
          ) : (
            <ul className="mt-1.5 flex flex-wrap gap-1.5">
              {quality.missing_data.map((m, i) => (
                <li
                  key={i}
                  dir="ltr"
                  className="rounded-full bg-amber-100 px-2.5 py-0.5 font-mono text-[10px] font-medium text-amber-800 dark:bg-[#F59E0B]/15 dark:text-[#FCD34D]"
                >
                  {m}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="mt-4">
          <p className="flex items-center gap-1.5 font-mono text-[10px] font-semibold uppercase tracking-wider text-[#4A5A4E] dark:text-[#9CA89E]">
            <Warning size={13} className="text-amber-700 dark:text-[#FCD34D]" aria-hidden="true" />
            <span>{dq.modelWarningsTitle}</span>
          </p>
          {quality.warnings.length === 0 ? (
            <p className="mt-1 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">{dq.modelWarningsEmpty}</p>
          ) : (
            <ul className="mt-1 list-disc space-y-1 ps-4 text-[11px] text-amber-900 dark:text-[#FDE68A]">
              {quality.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          )}
        </div>

        <div className="mt-4">
          <p className="font-mono text-[10px] font-semibold uppercase tracking-wider text-[#4A5A4E] dark:text-[#9CA89E]">
            {dq.limitationsTitle}
          </p>
          {quality.limitations.length === 0 ? (
            <p className="mt-1 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">{dq.limitationsEmpty}</p>
          ) : (
            <ul className="mt-1 list-disc space-y-1 ps-4 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
              {quality.limitations.map((lim, i) => (
                <li key={i}>{lim}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </article>
  );
}
