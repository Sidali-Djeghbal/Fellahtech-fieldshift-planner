"use client";

import React from "react";
import { CalendarBlank, SunHorizon, Warning } from "@phosphor-icons/react";
import { localizePlainText, MONTH_SHORT, STRESS_LABELS, UI_DICT } from "@/lib/i18n";
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
    <section className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-sm select-none">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 font-heading text-base font-bold text-[#111827]">
          <CalendarBlank size={18} className="text-[#137135]" />
          {t.riskCalendarTitle}
        </h2>
        {baselineBareDays !== undefined && recommendedBareDays !== undefined && (
          <span className="tabular-nums rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-bold text-[#137135]">
            {plainMode ? t.bareDaysPlain : t.bareDaysLabel}: {baselineBareDays} &rarr;{" "}
            {recommendedBareDays} d/yr
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
                  ? "border-red-300 bg-red-50 text-red-900"
                  : stresses.length > 0
                    ? "border-orange-300 bg-orange-50 text-orange-900"
                    : bare
                      ? "border-amber-300 bg-amber-50 text-amber-900"
                      : "border-gray-200 bg-gray-50 text-[#111827]"
              }`}
            >
              <p className="text-xs font-bold">{label}</p>
              <div className="mt-1.5 flex min-h-[22px] flex-col items-center justify-center gap-1">
                {bare && (
                  <span className="rounded bg-[#FEF3C7] text-[#D97706] px-1.5 py-0.5 text-[9px] font-bold">
                    BARE
                  </span>
                )}
                {stresses.map((s, sIdx) => (
                  <span
                    key={sIdx}
                    className="rounded bg-red-100 text-red-700 px-1.5 py-0.5 text-[9px] font-bold"
                  >
                    {s.type.toUpperCase()}
                  </span>
                ))}
                {!bare && stresses.length === 0 && (
                  <span className="text-[10px] text-gray-400">OK</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Plain-language Explanations */}
      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-3.5">
          <p className="flex items-center gap-1.5 text-xs font-bold text-amber-900">
            <SunHorizon size={15} />
            {plainMode ? t.bareWindowPlain : t.bareWindowTitle}
          </p>
          {insights.bare_field_periods.length === 0 ? (
            <p className="mt-1 text-xs text-gray-500">No bare-soil gaps flagged.</p>
          ) : (
            <ul className="mt-2 space-y-1.5 text-xs text-[#374151]">
              {insights.bare_field_periods.map((bp, i) => (
                <li key={i}>
                  <strong dir="ltr" className="text-[#111827]">
                    {months[bp.start_month - 1]}–{months[bp.end_month - 1]}:
                  </strong>{" "}
                  {localizePlainText(bp.evidence, lang, plainMode)}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded-xl border border-red-200 bg-red-50/50 p-3.5">
          <p className="flex items-center gap-1.5 text-xs font-bold text-red-900">
            <Warning size={15} weight="fill" className="text-red-600" />
            {t.stressWindowTitle}
          </p>
          {insights.stress_periods.length === 0 ? (
            <p className="mt-1 text-xs text-gray-500">No major stress windows detected.</p>
          ) : (
            <ul className="mt-2 space-y-1.5 text-xs text-[#374151]">
              {insights.stress_periods.map((sp, i) => (
                <li key={i}>
                  <strong className="text-[#111827]">
                    {STRESS_LABELS[lang][sp.type]} ({sp.severity}):
                  </strong>{" "}
                  {localizePlainText(sp.evidence, lang, plainMode)}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <p className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50/60 px-3.5 py-2 text-xs text-[#00291B]">
        {localizePlainText(insights.climate_trend_summary, lang, plainMode)}
      </p>
    </section>
  );
}
