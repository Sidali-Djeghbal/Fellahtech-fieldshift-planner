"use client";

import React, { useState } from "react";
import {
  CheckCircle,
  Code,
  Flask,
  Info,
  ListChecks,
  Plant,
  Question,
  ShieldCheck,
  UserCircle,
  WarningOctagon,
} from "@phosphor-icons/react";
import { SEVERITY_STYLE_MAP } from "@/lib/analysis/workspaceAnalysis";
import { EVIDENCE_PARAM_LABELS, localizePlainText, UI_DICT } from "@/lib/i18n";
import {
  localizeEvidenceValue,
  localizePeriod,
  localizeUnit,
} from "@/lib/i18n/dynamicText";
import { INTELLIGENCE_I18N } from "@/lib/i18n/intelligence";
import type { EvidenceParameter, Explanation, Language } from "@/lib/schemas";

type ExplanationTab =
  | "reasons"
  | "evidence"
  | "benefits"
  | "risks"
  | "assumptions"
  | "gaps"
  | "review";

interface StrategyExplanationTabsProps {
  strategyId: string;
  explanation: Explanation;
  lang: Language;
  plainMode: boolean;
}

export function StrategyExplanationTabs({
  strategyId,
  explanation,
  lang,
  plainMode,
}: StrategyExplanationTabsProps) {
  const dict = INTELLIGENCE_I18N[lang];
  const ex = dict.explanations;
  const [activeTab, setActiveTab] = useState<ExplanationTab>("reasons");
  const [showCodes, setShowCodes] = useState(false);

  const tabs: Array<{ key: ExplanationTab; label: string; count: number }> = [
    { key: "reasons", label: ex.tabs.reasons, count: explanation.reasons.length },
    { key: "evidence", label: ex.tabs.evidence, count: explanation.evidence.length },
    { key: "benefits", label: ex.tabs.benefits, count: explanation.benefits.length },
    { key: "risks", label: ex.tabs.risks, count: explanation.risks.length },
    { key: "assumptions", label: ex.tabs.assumptions, count: explanation.assumptions.length },
    { key: "gaps", label: ex.tabs.gaps, count: explanation.information_gaps.length },
    { key: "review", label: ex.tabs.review, count: explanation.needs_local_review.length },
  ];

  return (
    <div
      className="fs-liquid-well overflow-hidden rounded-2xl"
      data-testid={`explanation-tabs-${strategyId}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 pt-3.5 pb-2">
        <h4 className="flex items-center gap-1.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-[#111813] dark:text-[#F5F7F5]">
          <Flask size={15} weight="duotone" className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
          <span>{ex.heading}</span>
        </h4>

        {activeTab === "reasons" && explanation.reasons.length > 0 ? (
          <button
            type="button"
            onClick={() => setShowCodes((prev) => !prev)}
            className="fs-liquid-pill inline-flex min-h-8 items-center gap-1 rounded-full ps-2.5 pe-3 text-[11px] font-medium text-[#4A5A4E] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:text-[#F5F7F5] active:scale-[0.96]"
          >
            <Code size={12} aria-hidden="true" />
            <span>{showCodes ? ex.codeToggleHide : ex.codeToggleShow}</span>
          </button>
        ) : null}
      </div>

      {/* Underline Tab Strip with keyboard Arrow navigation */}
      <div
        className="flex gap-5 overflow-x-auto border-b border-[#111813]/10 px-4 dark:border-white/10"
        role="tablist"
        aria-label={ex.heading}
        onKeyDown={(e) => {
          const idx = tabs.findIndex((t) => t.key === activeTab);
          if (e.key === "ArrowRight") {
            e.preventDefault();
            setActiveTab(tabs[(idx + 1) % tabs.length].key);
          } else if (e.key === "ArrowLeft") {
            e.preventDefault();
            setActiveTab(tabs[(idx + tabs.length - 1) % tabs.length].key);
          }
        }}
      >
        {tabs.map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => setActiveTab(tab.key)}
              data-testid={`explanation-tab-${tab.key}`}
              className={`inline-flex min-h-10 shrink-0 items-center gap-1.5 border-b-2 py-2.5 text-xs font-medium transition-[color,border-color] duration-150 ease-out ${
                isActive
                  ? "border-[#15803D] font-semibold text-[#111813] dark:border-[#86EFAC] dark:text-[#F5F7F5]"
                  : "border-transparent text-[#4A5A4E] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:text-[#E4EBE5]"
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`rounded-full px-1.5 py-0.5 font-mono text-[10px] tabular-nums ${
                  isActive
                    ? "bg-[#22C55E]/15 text-[#15803D] dark:bg-[#22C55E]/20 dark:text-[#86EFAC]"
                    : "bg-[#111813]/[0.08] text-[#4A5A4E] dark:bg-white/[0.08] dark:text-[#9CA89E]"
                }`}
              >
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Tab Panel Body */}
      <div className="p-4">
        {activeTab === "reasons" ? (
          explanation.reasons.length === 0 ? (
            <p className="text-xs text-[#4A5A4E] dark:text-[#9CA89E]">{ex.emptyList}</p>
          ) : (
            <ul className="divide-y divide-[#111813]/10 rounded-xl bg-[#111813]/[0.03] dark:divide-white/10 dark:bg-white/[0.04]">
              {explanation.reasons.map((r, idx) => (
                <li key={`${r.code}-${idx}`} className="p-3.5 text-xs">
                  <div className="flex items-start gap-2.5">
                    <CheckCircle
                      size={15}
                      weight="fill"
                      className="mt-0.5 shrink-0 text-[#15803D] dark:text-[#4ADE80]"
                      aria-hidden="true"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="leading-relaxed text-[#243227] dark:text-[#E4EBE5]">
                        {localizePlainText(r.text, lang, plainMode)}
                      </p>
                      {showCodes ? (
                        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[10px]">
                          <code
                            dir="ltr"
                            className="fs-liquid-well rounded-full px-2 py-0.5 font-mono font-semibold text-[#15803D] dark:text-[#86EFAC]"
                          >
                            {r.code}
                          </code>
                          {r.params && Object.keys(r.params).length > 0 ? (
                            <code
                              dir="ltr"
                              className="fs-liquid-well rounded-full px-2 py-0.5 font-mono text-[#4A5A4E] dark:text-[#9CA89E]"
                            >
                              {JSON.stringify(r.params)}
                            </code>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )
        ) : null}

        {activeTab === "evidence" ? (
          explanation.evidence.length === 0 ? (
            <p className="text-xs text-[#4A5A4E] dark:text-[#9CA89E]">{ex.emptyList}</p>
          ) : (
            <div className="overflow-x-auto rounded-xl bg-[#111813]/[0.03] dark:bg-white/[0.04]">
              <table className="w-full min-w-[640px] border-collapse text-xs">
                <thead>
                  <tr className="border-b border-[#111813]/10 text-[10px] font-semibold uppercase tracking-wider text-[#4A5A4E] dark:border-white/10 dark:text-[#9CA89E]">
                    <th className="px-3.5 py-2.5 text-start">{ex.tabs.evidence}</th>
                    <th className="px-3.5 py-2.5 text-start">{UI_DICT[lang].comparison.tableSource}</th>
                    <th className="px-3.5 py-2.5 text-start">{UI_DICT[lang].comparison.tableValue}</th>
                    <th className="px-3.5 py-2.5 text-start">{UI_DICT[lang].comparison.tablePeriod}</th>
                    <th className="px-3.5 py-2.5 text-start">{UI_DICT[lang].comparison.tableInterpretation}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#111813]/10 dark:divide-white/10">
                  {explanation.evidence.map((ev, idx) => {
                    const isFarmer = ev.data_source === "farmer_input";
                    const paramMeta =
                      EVIDENCE_PARAM_LABELS[lang][ev.parameter as EvidenceParameter];
                    const paramLabel = paramMeta
                      ? plainMode
                        ? paramMeta.plain
                        : paramMeta.tech
                      : ev.parameter;

                    return (
                      <tr
                        key={`${ev.parameter}-${idx}`}
                        data-testid={`evidence-item-${ev.data_source}`}
                        className="align-top transition-[background-color] duration-150 hover:bg-[#111813]/[0.04] dark:hover:bg-white/[0.06]"
                      >
                        <td className="px-3.5 py-2.5 font-semibold text-[#111813] dark:text-[#F5F7F5]">
                          {paramLabel}
                        </td>
                        <td className="px-3.5 py-2.5">
                          <div className="flex flex-wrap gap-1.5">
                            <span
                              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                                isFarmer
                                  ? "bg-[#22C55E]/15 text-[#15803D] dark:text-[#86EFAC]"
                                  : "bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-300"
                              }`}
                            >
                              {isFarmer ? (
                                <UserCircle size={11} aria-hidden="true" />
                              ) : (
                                <Plant size={11} aria-hidden="true" />
                              )}
                              {isFarmer ? ex.farmerInputBadge : ex.datasetBadge}
                            </span>
                            <span
                              className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                                ev.derived
                                  ? "bg-amber-100 text-amber-800 dark:bg-[#F59E0B]/15 dark:text-[#FCD34D]"
                                  : "bg-[#111813]/[0.07] text-[#4A5A4E] dark:bg-white/[0.08] dark:text-[#9CA89E]"
                              }`}
                            >
                              {ev.derived ? ex.derivedBadge : ex.directBadge}
                            </span>
                          </div>
                        </td>
                        <td className="px-3.5 py-2.5">
                          {ev.observed_value !== undefined && ev.observed_value !== null ? (
                            <span
                              dir={lang === "ar" ? "auto" : "ltr"}
                              className="tabular-nums font-mono font-semibold text-[#15803D] dark:text-[#86EFAC]"
                            >
                              {localizeEvidenceValue(ev.observed_value, lang)}
                              {ev.unit ? ` ${localizeUnit(ev.unit, lang)}` : ""}
                            </span>
                          ) : (
                            <span className="text-[#4A5A4E] dark:text-[#9CA89E]">—</span>
                          )}
                        </td>
                        <td className="px-3.5 py-2.5 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
                          {ev.source_mission ? (
                            <code dir="ltr" className="block font-mono text-[#111813] dark:text-[#F5F7F5]">
                              {ev.source_mission}
                            </code>
                          ) : null}
                          {ev.period ? <span>{localizePeriod(ev.period, lang)}</span> : null}
                        </td>
                        <td className="px-3.5 py-2.5 leading-relaxed text-[#243227] dark:text-[#E4EBE5]">
                          {localizePlainText(ev.interpretation, lang, plainMode)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )
        ) : null}

        {activeTab === "benefits" ? (
          explanation.benefits.length === 0 ? (
            <p className="text-xs text-[#4A5A4E] dark:text-[#9CA89E]">{ex.emptyList}</p>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {explanation.benefits.map((b) => {
                const metric =
                  typeof b.impact_metric === "string" || typeof b.impact_metric === "number"
                    ? String(b.impact_metric)
                    : null;
                return (
                  <article
                    key={b.benefit_id}
                    className="rounded-xl bg-white/75 p-4 text-xs ring-1 ring-[#15803D]/20 dark:bg-white/[0.05] dark:ring-[#4ADE80]/20"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h5 className="font-semibold text-[#111813] dark:text-[#F5F7F5]">
                        {localizePlainText(b.title, lang, plainMode)}
                      </h5>
                      {metric ? (
                        <span
                          dir="ltr"
                          className="tabular-nums rounded-full bg-[#22C55E]/15 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-[#15803D] dark:text-[#86EFAC]"
                        >
                          {metric}
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1.5 leading-relaxed text-[#243227] dark:text-[#E4EBE5]">
                      {localizePlainText(b.description, lang, plainMode)}
                    </p>
                  </article>
                );
              })}
            </div>
          )
        ) : null}

        {activeTab === "risks" ? (
          explanation.risks.length === 0 ? (
            <p className="text-xs text-[#4A5A4E] dark:text-[#9CA89E]">{ex.emptyList}</p>
          ) : (
            <div className="space-y-3">
              {explanation.risks.map((r) => {
                const st = SEVERITY_STYLE_MAP[r.severity];
                return (
                  <article
                    key={r.risk_id}
                    className={`rounded-xl p-4 text-xs ${st.surfaceClass}`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h5 className="flex items-center gap-1.5 font-semibold text-[#111813] dark:text-[#F5F7F5]">
                        <WarningOctagon size={15} weight="fill" className="shrink-0 text-red-600 dark:text-red-400" aria-hidden="true" />
                        <span>{localizePlainText(r.title, lang, plainMode)}</span>
                      </h5>
                      <div className="flex flex-wrap items-center gap-1.5 text-[10px] font-semibold">
                        <span className={`rounded-full px-2.5 py-0.5 ${st.pillClass}`}>
                          {ex.severityLabel}: {dict.severity[r.severity]}
                        </span>
                        {r.likelihood ? (
                          <span className="fs-liquid-pill rounded-full px-2.5 py-0.5 text-[#111813] dark:text-[#F5F7F5]">
                            {ex.likelihoodLabel}: {dict.severity[r.likelihood]}
                          </span>
                        ) : null}
                      </div>
                    </div>

                    <p className="mt-1.5 leading-relaxed text-[#243227] dark:text-[#E4EBE5]">
                      {localizePlainText(r.description, lang, plainMode)}
                    </p>

                    <div className="mt-3 flex items-start gap-2 rounded-lg bg-[#15803D]/[0.08] px-3.5 py-2.5 text-[#15803D] dark:bg-white/[0.06] dark:text-[#86EFAC]">
                      <ShieldCheck size={14} weight="fill" className="mt-0.5 shrink-0 text-[#15803D] dark:text-[#4ADE80]" aria-hidden="true" />
                      <div>
                        <span className="font-semibold">{ex.mitigationLabel}: </span>
                        <span className="text-[#243227] dark:text-[#E4EBE5]">
                          {localizePlainText(r.mitigation, lang, plainMode)}
                        </span>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          )
        ) : null}

        {activeTab === "assumptions" ? (
          <SimpleBulletList
            items={explanation.assumptions}
            icon={<Info size={14} className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />}
            emptyLabel={ex.emptyList}
            lang={lang}
            plainMode={plainMode}
            toneClass="bg-[#111813]/[0.04] dark:bg-white/[0.05]"
          />
        ) : null}

        {activeTab === "gaps" ? (
          <SimpleBulletList
            items={explanation.information_gaps}
            icon={<Question size={14} className="text-amber-600 dark:text-[#FCD34D]" aria-hidden="true" />}
            emptyLabel={ex.emptyList}
            lang={lang}
            plainMode={plainMode}
            toneClass="bg-amber-50/90 ring-1 ring-amber-600/20 dark:bg-[#F59E0B]/10 dark:ring-[#F59E0B]/20"
          />
        ) : null}

        {activeTab === "review" ? (
          <SimpleBulletList
            items={explanation.needs_local_review}
            icon={<ListChecks size={14} className="text-[#0284C7] dark:text-sky-400" aria-hidden="true" />}
            emptyLabel={ex.emptyList}
            lang={lang}
            plainMode={plainMode}
            toneClass="bg-sky-50/90 ring-1 ring-sky-600/20 dark:bg-sky-500/10 dark:ring-sky-400/20"
          />
        ) : null}
      </div>
    </div>
  );
}

function SimpleBulletList({
  items,
  icon,
  emptyLabel,
  lang,
  plainMode,
  toneClass,
}: {
  items: string[];
  icon: React.ReactNode;
  emptyLabel: string;
  lang: Language;
  plainMode: boolean;
  toneClass: string;
}) {
  if (items.length === 0) {
    return <p className="text-xs text-[#4A5A4E] dark:text-[#9CA89E]">{emptyLabel}</p>;
  }
  return (
    <ul className="space-y-2 text-xs text-[#243227] dark:text-[#E4EBE5]">
      {items.map((text, idx) => (
        <li
          key={idx}
          className={`flex items-start gap-2.5 rounded-xl px-4 py-3 leading-relaxed ${toneClass}`}
        >
          <span className="mt-0.5 shrink-0">{icon}</span>
          <span>{localizePlainText(text, lang, plainMode)}</span>
        </li>
      ))}
    </ul>
  );
}
