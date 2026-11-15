"use client";

import React from "react";
import { resolveCropDisplayName } from "@/lib/analysis/workspaceAnalysis";
import {
  CROP_ROLE_LABELS,
  DATA_SOURCE_LABELS,
  EVIDENCE_PARAM_LABELS,
  localizePlainText,
  MONTH_SHORT,
  RISK_SEVERITY_LABELS,
  SCORE_LABELS,
  SEASON_LABELS,
  UI_DICT,
} from "@/lib/i18n";
import {
  formatSeasonMonthShort,
  localizeEvidenceValue,
  localizeFieldName,
  localizeStrategyDescription,
  localizeStrategyName,
  localizeUnit,
} from "@/lib/i18n/dynamicText";
import type { AnalysisEnvelope, CropItem, FieldPlan, Language, Strategy } from "@/lib/schemas";

// High-contrast light-mode @media print 1-page brief
export function PrintableBrief({
  envelope,
  fieldPlan,
  strategy,
  lang = "en",
  plainMode = false,
  catalogMap,
}: {
  envelope: AnalysisEnvelope;
  fieldPlan: FieldPlan;
  strategy?: Strategy;
  lang?: Language;
  plainMode?: boolean;
  catalogMap?: Map<string, CropItem>;
}) {
  if (!strategy) return null;

  const t = UI_DICT[lang];
  const br = t.brief;
  const sc = SCORE_LABELS[lang];
  const months = MONTH_SHORT[lang];
  const bareDays = strategy.scores.bare_field_days_per_year;

  return (
    <article
      data-testid="printable-brief"
      className="print-only-brief rounded-xl border-2 border-[#00291B] bg-white p-6 text-[#111827]"
    >
      <header className="border-b-2 border-[#137135] pb-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <img
              src="/assets/logo.svg"
              alt="FELLAH TECH"
              width={36}
              height={36}
              className="h-9 w-9 shrink-0 rounded-full object-contain"
            />
            <h1 className="text-xl font-extrabold text-[#00291B]">{br.docHeading}</h1>
          </div>
          <span dir="ltr" className="text-xs font-bold text-[#137135]">
            {envelope.analysis_id} · {envelope.dataset_version}
          </span>
        </div>
        <p className="mt-1 text-xs text-[#374151]">
          {br.metaField} <strong>{localizeFieldName(fieldPlan.field_name, lang)}</strong>{" "}
          <span dir="ltr">({fieldPlan.field_id})</span> · {br.metaEngine}{" "}
          <span dir="ltr">{envelope.result.ml_engine_version}</span>
        </p>
      </header>

      <section className="mt-4">
        <h2 className="text-sm font-bold text-[#137135]">
          {br.strategyPrefix} {localizeStrategyName(strategy.strategy_id, strategy.name, lang)}
        </h2>
        <p className="mt-1 text-xs text-[#374151]">
          {localizePlainText(
            localizeStrategyDescription(strategy.strategy_id, strategy.description, lang),
            lang,
            plainMode
          )}
        </p>
        <div className="mt-2 grid grid-cols-4 gap-2 text-xs">
          <div className="rounded border border-gray-200 bg-gray-50 p-2">
            {plainMode ? sc.priority_fit.plain : sc.priority_fit.tech}:{" "}
            <strong dir="ltr" className="text-[#00291B]">{strategy.scores.priority_fit}/100</strong>
          </div>
          <div className="rounded border border-gray-200 bg-gray-50 p-2">
            {plainMode ? sc.water_efficiency.plain : sc.water_efficiency.tech}:{" "}
            <strong dir="ltr" className="text-[#00291B]">{strategy.scores.water_efficiency}/100</strong>
          </div>
          <div className="rounded border border-gray-200 bg-gray-50 p-2">
            {plainMode ? sc.nitrogen_contribution.plain : sc.nitrogen_contribution.tech}:{" "}
            <strong dir="ltr" className="text-[#00291B]">{strategy.scores.nitrogen_contribution}/100</strong>
          </div>
          <div className="rounded border border-gray-200 bg-gray-50 p-2">
            {plainMode ? t.comparison.bareDaysPlain : t.comparison.bareDaysLabel}:{" "}
            <strong dir="ltr" className="text-[#00291B]">
              {bareDays} {t.common.daysPerYearShort}
            </strong>
          </div>
        </div>
      </section>

      <section className="mt-4">
        <h3 className="text-xs font-bold uppercase text-[#137135]">{br.seasonSeqHeading}</h3>
        <table className="mt-1 w-full border-collapse text-xs">
          <thead>
            <tr className="border-b border-[#00291B] text-start">
              <th className="py-1 text-start">{br.colNumber}</th>
              <th className="py-1 text-start">{br.colSeasonYear}</th>
              <th className="py-1 text-start">{br.colCrop}</th>
              <th className="py-1 text-start">{br.colCategoryRole}</th>
            </tr>
          </thead>
          <tbody>
            {strategy.seasons.map((s) => (
              <tr key={s.order} className="border-b border-gray-300">
                <td className="py-1">{s.order}</td>
                <td className="py-1">
                  {SEASON_LABELS[lang][s.season]} {s.year} (
                  {s.planting_month
                    ? months[s.planting_month - 1] ?? formatSeasonMonthShort(s.planting_month, lang)
                    : "—"})
                </td>
                <td className="py-1 font-bold text-[#00291B]">
                  {resolveCropDisplayName(s.crop_id, s.crop_name, catalogMap, lang)}
                </td>
                <td className="py-1 text-[#374151]">{CROP_ROLE_LABELS[lang][s.role] ?? s.role}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="mt-4 grid grid-cols-2 gap-4 text-xs">
        <div>
          <h3 className="font-bold text-[#137135]">{br.risksHeading}</h3>
          <ul className="mt-1 list-disc space-y-1 ps-4 text-[#374151]">
            {strategy.explanation.risks.map((r) => (
              <li key={r.risk_id}>
                <strong>{localizePlainText(r.title, lang, plainMode)}</strong> (
                {RISK_SEVERITY_LABELS[lang][r.severity] ?? r.severity}):{" "}
                {localizePlainText(r.mitigation, lang, plainMode)}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="font-bold text-[#137135]">{br.citationsHeading}</h3>
          <ul className="mt-1 list-disc space-y-1 ps-4 text-[#374151]">
            {strategy.explanation.evidence.map((ev, i) => {
              const pMeta =
                EVIDENCE_PARAM_LABELS[lang][
                  ev.parameter as keyof (typeof EVIDENCE_PARAM_LABELS)["en"]
                ];
              const pLabel = pMeta ? (plainMode ? pMeta.plain : pMeta.tech) : ev.parameter;
              const srcLabel = DATA_SOURCE_LABELS[lang][ev.data_source] ?? ev.data_source;
              return (
                <li key={i}>
                  [{srcLabel}] {pLabel}:{" "}
                  <span dir={lang === "ar" ? "auto" : "ltr"}>
                    {localizeEvidenceValue(ev.observed_value, lang)} {localizeUnit(ev.unit, lang)}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      </section>

      <footer className="mt-4 border-t border-gray-300 pt-2 text-[10px] text-[#6B7280]">
        <strong>{br.disclaimerPrefix}</strong> {localizePlainText(envelope.result.disclaimer, lang, plainMode)}
      </footer>
    </article>
  );
}
