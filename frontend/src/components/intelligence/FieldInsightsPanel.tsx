"use client";

import React from "react";
import { CalendarBlank, CloudSun, Warning } from "@phosphor-icons/react";
import { SEVERITY_STYLE_MAP } from "@/lib/analysis/workspaceAnalysis";
import { localizePlainText, MONTH_SHORT, STRESS_LABELS } from "@/lib/i18n";
import { INTELLIGENCE_I18N } from "@/lib/i18n/intelligence";
import type { FieldInsights, Language, StressType } from "@/lib/schemas";

const ALL_STRESS_TYPES: StressType[] = [
  "drought",
  "heat",
  "frost",
  "waterlogging",
  "salinity",
  "nutrient",
];

interface FieldInsightsPanelProps {
  insights: FieldInsights;
  lang: Language;
  plainMode: boolean;
}

export function FieldInsightsPanel({
  insights,
  lang,
  plainMode,
}: FieldInsightsPanelProps) {
  const dict = INTELLIGENCE_I18N[lang];
  const ins = dict.insights;
  const months = MONTH_SHORT[lang];

  const isBareMonth = (monthNum: number) =>
    insights.bare_field_periods.some((p) =>
      p.start_month <= p.end_month
        ? monthNum >= p.start_month && monthNum <= p.end_month
        : monthNum >= p.start_month || monthNum <= p.end_month
    );

  const matrixCell = (stressType: StressType, monthNum: number) =>
    insights.stress_periods.find(
      (sp) => sp.type === stressType && sp.months.includes(monthNum)
    );

  const activeStressTypes = ALL_STRESS_TYPES.filter((type) =>
    insights.stress_periods.some((sp) => sp.type === type)
  );
  const matrixRows = activeStressTypes.length > 0 ? activeStressTypes : ALL_STRESS_TYPES.slice(0, 4);

  return (
    <section
      className="fs-liquid-panel space-y-5 overflow-hidden rounded-3xl p-5 sm:p-6"
      data-testid="field-insights-timeline"
    >
      {/* Panel Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 font-heading text-sm font-semibold leading-[1.15] text-[#111813] dark:text-[#F5F7F5] sm:text-base">
          <CalendarBlank size={17} weight="duotone" className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
          <span>{ins.heading}</span>
        </h3>

        <div className="flex flex-wrap items-center gap-4 text-[11px] font-medium text-[#4A5A4E] dark:text-[#9CA89E]">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-[#22C55E]" aria-hidden="true" />
            {ins.activeLegend}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-[#F59E0B]" aria-hidden="true" />
            {ins.bareLegend}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-red-500 dark:bg-red-400" aria-hidden="true" />
            {ins.stressLegend}
          </span>
        </div>
      </div>

      {/* Regional Climate Callout inside soft Emerald Glass Well */}
      <div className="rounded-2xl bg-[#22C55E]/10 px-4 py-3.5 ring-1 ring-[#15803D]/25 dark:ring-[#4ADE80]/20">
        <p className="flex items-center gap-1.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-[#15803D] dark:text-[#86EFAC]">
          <CloudSun size={14} weight="duotone" aria-hidden="true" />
          <span>{ins.climateTrendTitle}</span>
        </p>
        <p className="mt-1.5 max-w-[68ch] text-xs leading-relaxed text-[#243227] dark:text-[#E4EBE5]">
          {localizePlainText(insights.climate_trend_summary, lang, plainMode)}
        </p>
      </div>

      {/* Unified 12-Month Bare-Soil & Stress Indicator Matrix */}
      <div className="space-y-3" data-testid="stress-matrix">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="font-mono text-[11px] font-semibold uppercase tracking-wider text-[#4A5A4E] dark:text-[#9CA89E]">
            {ins.bareCalendarTitle} &amp; {ins.stressMatrixTitle}
          </h4>
        </div>

        <div className="fs-liquid-well overflow-x-auto rounded-2xl">
          <table className="w-full min-w-[600px] border-collapse text-xs">
            <thead>
              <tr className="border-b border-[#111813]/10 text-[10px] font-semibold uppercase tracking-wider text-[#4A5A4E] dark:border-white/10 dark:text-[#9CA89E]">
                <th className="px-3.5 py-2.5 text-start">{ins.stressLegend}</th>
                {months.map((m, idx) => (
                  <th key={idx} className="px-1.5 py-2.5 text-center font-mono tabular-nums">
                    {m}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#111813]/10 dark:divide-white/10">
              {/* Row 1: Bare Soil vs Active Canopy Exposure */}
              <tr className="bg-[#111813]/[0.03] dark:bg-white/[0.03]">
                <td className="px-3.5 py-2.5 text-xs font-semibold text-[#15803D] dark:text-[#86EFAC]">
                  {ins.bareCalendarTitle}
                </td>
                {months.map((_, mIdx) => {
                  const bare = isBareMonth(mIdx + 1);
                  return (
                    <td key={mIdx} className="px-1 py-2 text-center">
                      {bare ? (
                        <span className="inline-block rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-800 dark:bg-[#F59E0B]/18 dark:text-[#FCD34D]">
                          {ins.bareLegend.split(" ")[0]}
                        </span>
                      ) : (
                        <span className="inline-block rounded-full bg-[#22C55E]/15 px-2 py-0.5 text-[10px] font-medium text-[#15803D] dark:text-[#86EFAC]">
                          {ins.statusOkLabel}
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>

              {/* Stress Signal Rows */}
              {matrixRows.map((sType) => (
                <tr key={sType}>
                  <td className="px-3.5 py-2.5 font-medium text-[#111813] dark:text-[#F5F7F5]">
                    {STRESS_LABELS[lang][sType]}
                  </td>
                  {months.map((_, mIdx) => {
                    const hit = matrixCell(sType, mIdx + 1);
                    if (!hit) {
                      return (
                        <td key={mIdx} className="px-1 py-2 text-center text-[#111813]/25 dark:text-white/25">
                          ·
                        </td>
                      );
                    }
                    const style = SEVERITY_STYLE_MAP[hit.severity];
                    return (
                      <td key={mIdx} className="px-1 py-2 text-center">
                        <span
                          title={`${STRESS_LABELS[lang][sType]} · ${dict.severity[hit.severity]}`}
                          className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ${style.pillClass}`}
                        >
                          {dict.severity[hit.severity]}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Bare-Soil & Stress Evidence Details */}
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {insights.bare_field_periods.length === 0 ? (
            <p className="fs-liquid-well rounded-2xl px-4 py-3 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">
              {ins.noBarePeriods}
            </p>
          ) : (
            insights.bare_field_periods.map((bp, i) => (
              <div
                key={`bare-${i}`}
                className="rounded-2xl bg-amber-50/90 p-3.5 text-xs ring-1 ring-amber-600/25 dark:bg-[#F59E0B]/10 dark:ring-[#F59E0B]/25"
              >
                <div className="flex items-center justify-between gap-2">
                  <span dir="ltr" className="font-mono font-semibold text-amber-900 dark:text-[#FDE68A]">
                    {months[bp.start_month - 1]} – {months[bp.end_month - 1]}
                  </span>
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800 dark:bg-[#F59E0B]/18 dark:text-[#FCD34D]">
                    {ins.bareLegend}
                  </span>
                </div>
                <p className="mt-1.5 leading-relaxed text-[#243227] dark:text-[#E4EBE5]">
                  {localizePlainText(bp.evidence, lang, plainMode)}
                </p>
              </div>
            ))
          )}

          {insights.stress_periods.length === 0 ? (
            <p className="fs-liquid-well rounded-2xl px-4 py-3 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">
              {ins.noStressPeriods}
            </p>
          ) : (
            insights.stress_periods.map((sp, i) => {
              const st = SEVERITY_STYLE_MAP[sp.severity];
              return (
                <div
                  key={`stress-${i}`}
                  className={`rounded-2xl p-3.5 text-xs ${st.surfaceClass}`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-1.5">
                    <span className="inline-flex items-center gap-1.5 font-semibold text-[#111813] dark:text-[#F5F7F5]">
                      <Warning size={13} weight="fill" className="shrink-0 text-red-600 dark:text-red-400" aria-hidden="true" />
                      {STRESS_LABELS[lang][sp.type]}
                    </span>
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${st.pillClass}`}
                      >
                        {dict.severity[sp.severity]}
                      </span>
                      <span dir="ltr" className="font-mono text-[10px] text-[#4A5A4E] dark:text-[#9CA89E]">
                        {sp.months.map((m) => months[m - 1]).join(", ")}
                      </span>
                    </div>
                  </div>
                  <p className="mt-1.5 leading-relaxed text-[#243227] dark:text-[#E4EBE5]">
                    {localizePlainText(sp.evidence, lang, plainMode)}
                  </p>
                </div>
              );
            })
          )}
        </div>
      </div>
    </section>
  );
}
