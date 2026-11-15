"use client";

import React from "react";
import { CalendarBlank, SunHorizon, Warning } from "@phosphor-icons/react";
import { localizePlainText, MONTH_SHORT, RISK_SEVERITY_LABELS, STRESS_LABELS, UI_DICT } from "@/lib/i18n";
import type { FieldInsights, Language } from "@/lib/schemas";

export function AgronomicRiskCalendar({
  insights,
  baselineBareDays,
  recommendedBareDays,
  lang,
  plainMode,
}: {
  insights: FieldInsights;
  baselineBareDays?: number;
  recommendedBareDays?: number;
  lang: Language;
  plainMode: boolean;
}) {
  const t = UI_DICT[lang].comparison;
  const c = UI_DICT[lang].common;
  const months = MONTH_SHORT[lang];

  const isBareMonth = (monthNum: number) =>
    insights.bare_field_periods.some((p) =>
      p.start_month <= p.end_month
        ? monthNum >= p.start_month && monthNum <= p.end_month
        : monthNum >= p.start_month || monthNum <= p.end_month
    );

  const monthStresses = (monthNum: number) =>
    insights.stress_periods.filter((sp) => sp.months.includes(monthNum));

  return (
    <section className="fs-liquid-panel rounded-3xl p-5 select-none">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 font-heading text-base font-bold text-[#111813] dark:text-[#F5F7F5]">
          <CalendarBlank size={18} className="text-[#15803D] dark:text-[#86EFAC]" />
          {t.riskCalendarTitle}
        </h2>
        {baselineBareDays !== undefined && recommendedBareDays !== undefined && (
          <span className="tabular-nums rounded-full border border-[#15803D]/25 bg-[#15803D]/10 px-3 py-1 text-xs font-semibold text-[#15803D] dark:border-[#22C55E]/30 dark:bg-[#22C55E]/15 dark:text-[#86EFAC]">
            {plainMode ? t.bareDaysPlain : t.bareDaysLabel}: {baselineBareDays} &rarr;{" "}
            {recommendedBareDays} {c.daysPerYearShort}
          </span>
        )}
      </div>

      {/* 12-Month Strip */}
      <div className="grid grid-cols-4 gap-2 sm:grid-cols-6 lg:grid-cols-12">
        {months.map((label, idx) => {
          const m = idx + 1;
          const bare = isBareMonth(m);
          const stresses = monthStresses(m);
          const highStress = stresses.some((s) => s.severity === "high");

          return (
            <div
              key={m}
              className={`rounded-xl border p-2 text-center transition ${
                highStress
                  ? "border-red-300/80 bg-red-50/90 text-red-900 dark:border-red-500/35 dark:bg-red-500/15 dark:text-red-200"
                  : stresses.length > 0
                    ? "border-orange-300/80 bg-orange-50/90 text-orange-900 dark:border-amber-500/35 dark:bg-amber-500/15 dark:text-[#FDE68A]"
                    : bare
                      ? "border-amber-300/80 bg-amber-50/90 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/12 dark:text-[#FCD34D]"
                      : "border-[#111813]/10 bg-[#111813]/[0.03] text-[#111813] dark:border-white/10 dark:bg-white/[0.04] dark:text-[#F5F7F5]"
              }`}
            >
              <p className="text-xs font-bold">{label}</p>
              <div className="mt-1.5 flex min-h-[22px] flex-col items-center justify-center gap-1">
                {bare && (
                  <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[9px] font-bold text-amber-800 dark:bg-amber-500/20 dark:text-[#FCD34D]">
                    {c.bareShort}
                  </span>
                )}
                {stresses.map((s, sIdx) => (
                  <span
                    key={sIdx}
                    className="rounded bg-red-500/15 px-1.5 py-0.5 text-[9px] font-bold text-red-700 dark:bg-red-500/25 dark:text-red-200"
                  >
                    {STRESS_LABELS[lang][s.type]}
                  </span>
                ))}
                {!bare && stresses.length === 0 && (
                  <span className="text-[10px] text-[#6B7A6F] dark:text-[#6E7B71]">
                    {c.okShort}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Plain-language Explanations */}
      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="rounded-2xl border border-amber-300/70 bg-amber-50/70 p-3.5 dark:border-amber-500/25 dark:bg-amber-500/10">
          <p className="flex items-center gap-1.5 text-xs font-bold text-amber-900 dark:text-[#FCD34D]">
            <SunHorizon size={15} />
            {plainMode ? t.bareWindowPlain : t.bareWindowTitle}
          </p>
          {insights.bare_field_periods.length === 0 ? (
            <p className="mt-1 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">{t.noBareGaps}</p>
          ) : (
            <ul className="mt-2 space-y-1.5 text-xs text-[#3E4C42] dark:text-[#D1DDD3]">
              {insights.bare_field_periods.map((bp, i) => (
                <li key={i}>
                  <strong dir={lang === "ar" ? "auto" : "ltr"} className="text-[#111813] dark:text-[#F5F7F5]">
                    {months[bp.start_month - 1]}–{months[bp.end_month - 1]}:
                  </strong>{" "}
                  {localizePlainText(bp.evidence, lang, plainMode)}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded-2xl border border-red-300/70 bg-red-50/70 p-3.5 dark:border-red-500/25 dark:bg-red-500/10">
          <p className="flex items-center gap-1.5 text-xs font-bold text-red-800 dark:text-red-300">
            <Warning size={15} weight="fill" className="text-red-600 dark:text-red-400" />
            {t.stressWindowTitle}
          </p>
          {insights.stress_periods.length === 0 ? (
            <p className="mt-1 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">
              {t.noStressWindows}
            </p>
          ) : (
            <ul className="mt-2 space-y-1.5 text-xs text-[#3E4C42] dark:text-[#D1DDD3]">
              {insights.stress_periods.map((sp, i) => (
                <li key={i}>
                  <strong className="text-[#111813] dark:text-[#F5F7F5]">
                    {STRESS_LABELS[lang][sp.type]} ({RISK_SEVERITY_LABELS[lang][sp.severity] ?? sp.severity}):
                  </strong>{" "}
                  {localizePlainText(sp.evidence, lang, plainMode)}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <p className="mt-3 rounded-2xl border border-[#15803D]/25 bg-[#15803D]/10 px-3.5 py-2 text-xs text-[#0B3D2E] dark:border-[#22C55E]/25 dark:bg-[#22C55E]/10 dark:text-[#86EFAC]">
        {localizePlainText(insights.climate_trend_summary, lang, plainMode)}
      </p>
    </section>
  );
}
