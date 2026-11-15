"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Database,
  GlobeHemisphereEast,
  Stack,
  UserCheck,
  Warning,
} from "@phosphor-icons/react";
import { useResolvedTheme } from "@/app/providers";
import {
  ApiErrorCard,
  DegradedReplayBanner,
  WarningsBanner,
} from "@/components/shared/ProvenanceBanners";
import {
  getAnalysisResult,
  getDemoLocationBoundary,
  listFarmAnalyses,
  listFarms,
  listFields,
} from "@/lib/api/endpoints";
import { GUELMA_FALLBACK_BOUNDARY } from "@/lib/geo/guelma";
import {
  DATA_SOURCE_LABELS,
  EVIDENCE_GROUP_LABELS,
  EVIDENCE_PARAM_LABELS,
  UI_DICT,
  localizePlainText,
} from "@/lib/i18n";
import {
  localizeCropIdBadge,
  localizeDynamicPhrase,
  localizeEvidenceValue,
  localizeMissingField,
  localizePeriod,
  localizeStrategyName,
  localizeUnit,
} from "@/lib/i18n/dynamicText";
import type { DataSource, EvidenceItem, EvidenceParameter } from "@/lib/schemas";
import { useAppStore } from "@/store/useAppStore";

type ParamGroup = "all" | "climate" | "water" | "vegetation" | "soil_history";

function classifyParamGroup(p: EvidenceParameter): Exclude<ParamGroup, "all"> {
  if (
    [
      "precipitation",
      "t2m",
      "t2m_max",
      "t2m_min",
      "rh2m",
      "wind_2m",
      "solar_radiation",
      "precipitation_anomaly",
    ].includes(p)
  ) {
    return "climate";
  }
  if (
    [
      "soil_moisture_surface",
      "evaporative_stress_index",
      "groundwater_anomaly",
      "water_availability",
    ].includes(p)
  ) {
    return "water";
  }
  if (p === "ndvi") return "vegetation";
  return "soil_history";
}

export default function EvidencePage() {
  const resolvedTheme = useResolvedTheme();
  const {
    lang,
    plainMode,
    authMode,
    activeFarmId,
    activeAnalysisId,
    simulateDegradedReplay,
  } = useAppStore();

  const t = UI_DICT[lang].evidence;
  const c = UI_DICT[lang].common;
  const compDict = UI_DICT[lang].comparison;
  const hasSession = authMode !== "none";

  const farmsQuery = useQuery({
    queryKey: ["farms", authMode],
    queryFn: () => listFarms(),
    enabled: hasSession,
  });
  const resolvedFarmId = activeFarmId ?? farmsQuery.data?.items[0]?.farm_id ?? null;

  const fieldsQuery = useQuery({
    queryKey: ["fields", resolvedFarmId],
    queryFn: () => listFields(resolvedFarmId!),
    enabled: hasSession && Boolean(resolvedFarmId),
  });

  const analysesQuery = useQuery({
    queryKey: ["analyses", resolvedFarmId],
    queryFn: () => listFarmAnalyses(resolvedFarmId!),
    enabled: hasSession && Boolean(resolvedFarmId),
  });

  const resolvedAnalysisId =
    activeAnalysisId ??
    analysesQuery.data?.items.find((a) => a.analysis_id)?.analysis_id ??
    null;

  const analysisQuery = useQuery({
    queryKey: ["analysis", resolvedAnalysisId, simulateDegradedReplay],
    queryFn: () => getAnalysisResult(resolvedAnalysisId!),
    enabled: hasSession && Boolean(resolvedAnalysisId),
  });

  const boundaryQuery = useQuery({
    queryKey: ["demo", "boundary", 1],
    queryFn: () => getDemoLocationBoundary(1),
  });

  const [sourceFilter, setSourceFilter] = useState<"all" | DataSource>("all");
  const [groupFilter, setGroupFilter] = useState<ParamGroup>("all");
  const [missionFilter, setMissionFilter] = useState<string>("all");

  const envelope = analysisQuery.data;

  const collectedEvidence = useMemo(() => {
    if (!envelope) return [];
    const seen = new Set<string>();
    const list: Array<EvidenceItem & { contextLabel: string }> = [];

    for (const fp of envelope.result.field_plans) {
      for (const strat of fp.strategies) {
        for (const ev of strat.explanation.evidence) {
          const key = `${ev.data_source}:${ev.source_mission ?? ""}:${ev.parameter}:${String(ev.observed_value)}:${ev.period ?? ""}`;
          if (!seen.has(key)) {
            seen.add(key);
            list.push({
              ...ev,
              contextLabel: `${fp.field_id} · ${localizeStrategyName(strat.strategy_id, strat.name, lang)}`,
            });
          }
        }
      }
      for (const rq of fp.requested_crop_results) {
        for (const ev of rq.evidence ?? []) {
          const key = `${ev.data_source}:${ev.source_mission ?? ""}:${ev.parameter}:${String(ev.observed_value)}`;
          if (!seen.has(key)) {
            seen.add(key);
            list.push({
              ...ev,
              contextLabel: `${fp.field_id} · ${localizeCropIdBadge(rq.requested_crop_id, lang)}`,
            });
          }
        }
      }
    }
    return list;
  }, [envelope, lang]);

  const missions = useMemo(() => {
    const set = new Set<string>();
    for (const ev of collectedEvidence) {
      if (ev.source_mission) set.add(ev.source_mission);
    }
    return Array.from(set);
  }, [collectedEvidence]);

  const filteredEvidence = collectedEvidence.filter((ev) => {
    if (sourceFilter !== "all" && ev.data_source !== sourceFilter) return false;
    if (groupFilter !== "all" && classifyParamGroup(ev.parameter) !== groupFilter) return false;
    if (missionFilter !== "all" && ev.source_mission !== missionFilter) return false;
    return true;
  });

  const boundaryRing =
    ((boundaryQuery.data ?? GUELMA_FALLBACK_BOUNDARY).geometry.coordinates as number[][][][])?.[0]?.[0] ?? [];
  const fields = fieldsQuery.data?.items ?? [];
  const dq = envelope?.result.data_quality;
  const completenessPct = Math.round((dq?.completeness_score ?? 0) * 100);

  return (
    <div className="fs-view-enter space-y-5">
      <div>
        <h1 className="font-heading text-2xl font-semibold tracking-tight text-[#111813] dark:text-[#F5F7F5]">
          {t.title}
        </h1>
        <p className="mt-1 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">{t.subtitle}</p>
      </div>

      {(analysisQuery.error || farmsQuery.error || fieldsQuery.error || analysesQuery.error) && (
        <ApiErrorCard
          error={analysisQuery.error ?? farmsQuery.error ?? fieldsQuery.error ?? analysesQuery.error}
          lang={lang}
          theme={resolvedTheme}
        />
      )}

      {!envelope && !analysisQuery.error && (
        <section className="fs-liquid-panel rounded-3xl p-6 text-[#111813] dark:text-[#F5F7F5]">
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
                  {compDict.openProfileBtn}
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

      {envelope && (
        <>
          <DegradedReplayBanner
            degradedMode={envelope.degraded_mode}
            lang={lang}
            theme={resolvedTheme}
          />
          <WarningsBanner warnings={envelope.warnings} lang={lang} theme={resolvedTheme} />

          {/* Multi-Scale Fusion Explainer */}
          <section className="fs-liquid-microclimate rounded-3xl p-5 text-[#111813] dark:text-[#F5F7F5]">
            <div className="flex items-start gap-3">
              <Stack size={24} className="mt-0.5 shrink-0 text-[#15803D] dark:text-[#86EFAC]" />
              <div>
                <h2 className="font-heading text-base font-bold text-[#111813] dark:text-[#F5F7F5]">
                  {t.fusionTitle}
                </h2>
                <p className="mt-1 text-xs leading-relaxed text-[#3E4C42] dark:text-[#D1DDD3]">
                  {t.fusionBody}
                </p>
                <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                  <span className="rounded-full border border-[#15803D]/25 bg-[#15803D]/10 px-3 py-1 text-[#0B3D2E] dark:border-[#22C55E]/30 dark:bg-[#22C55E]/15 dark:text-[#86EFAC]">
                    {c.datasetLabel}:{" "}
                    <strong dir="ltr" className="font-mono">
                      {envelope.result.dataset_version_used}
                    </strong>
                  </span>
                  <span className="rounded-full border border-[#15803D]/25 bg-[#15803D]/10 px-3 py-1 text-[#0B3D2E] dark:border-[#22C55E]/30 dark:bg-[#22C55E]/15 dark:text-[#86EFAC]">
                    {c.engineLabel}:{" "}
                    <strong dir="ltr" className="font-mono">
                      {envelope.result.ml_engine_version}
                    </strong>
                  </span>
                </div>
              </div>
            </div>
          </section>

          {/* Provenance Filter Bar */}
          <section className="fs-liquid-panel rounded-3xl p-4 sm:p-5 text-[#111813] dark:text-[#F5F7F5]">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setSourceFilter("all")}
                  className={`rounded-full px-3.5 py-1.5 text-xs font-semibold transition ${
                    sourceFilter === "all"
                      ? "bg-[#0B3D2E] text-white shadow-sm dark:bg-[#FFFFFF] dark:text-[#111713]"
                      : "fs-liquid-pill text-[#3E4C42] dark:text-[#D1DDD3]"
                  }`}
                >
                  {t.filterAll} ({collectedEvidence.length})
                </button>
                <button
                  type="button"
                  data-testid="filter-farmer-input"
                  onClick={() => setSourceFilter("farmer_input")}
                  className={`rounded-full px-3.5 py-1.5 text-xs font-semibold transition ${
                    sourceFilter === "farmer_input"
                      ? "bg-[#0B3D2E] text-white shadow-sm dark:bg-[#FFFFFF] dark:text-[#111713]"
                      : "fs-liquid-pill text-[#3E4C42] dark:text-[#D1DDD3]"
                  }`}
                >
                  {t.filterFarmer}
                </button>
                <button
                  type="button"
                  data-testid="filter-dataset"
                  onClick={() => setSourceFilter("dataset")}
                  className={`rounded-full px-3.5 py-1.5 text-xs font-semibold transition ${
                    sourceFilter === "dataset"
                      ? "bg-[#0B3D2E] text-white shadow-sm dark:bg-[#FFFFFF] dark:text-[#111713]"
                      : "fs-liquid-pill text-[#3E4C42] dark:text-[#D1DDD3]"
                  }`}
                >
                  {t.filterDataset}
                </button>
              </div>

              <div className="flex flex-wrap gap-1.5">
                {(["all", "climate", "water", "vegetation", "soil_history"] as ParamGroup[]).map(
                  (grp) => (
                    <button
                      key={grp}
                      type="button"
                      onClick={() => setGroupFilter(grp)}
                      className={`rounded-full px-3 py-1 text-[11px] font-semibold transition ${
                        groupFilter === grp
                          ? "bg-[#15803D] text-white shadow-xs dark:bg-[#22C55E] dark:text-[#081A0E]"
                          : "fs-liquid-pill text-[#4A5A4E] dark:text-[#9CA89E]"
                      }`}
                    >
                      {EVIDENCE_GROUP_LABELS[lang][grp]}
                    </button>
                  )
                )}
              </div>
            </div>

            {missions.length > 0 && (
              <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-[#111813]/10 pt-3 dark:border-white/10">
                <span className="text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
                  {t.tagFilterLabel}
                </span>
                <button
                  type="button"
                  onClick={() => setMissionFilter("all")}
                  className={`rounded-full px-2.5 py-0.5 text-[11px] transition ${
                    missionFilter === "all"
                      ? "bg-[#0B3D2E] font-semibold text-white dark:bg-[#FFFFFF] dark:text-[#111713]"
                      : "fs-liquid-pill text-[#3E4C42] dark:text-[#D1DDD3]"
                  }`}
                >
                  {t.tagAll}
                </button>
                {missions.map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setMissionFilter(m)}
                    className={`rounded-full px-2.5 py-0.5 text-[11px] transition ${
                      missionFilter === m
                        ? "bg-[#0B3D2E] font-semibold text-white dark:bg-[#FFFFFF] dark:text-[#111713]"
                        : "fs-liquid-pill text-[#3E4C42] dark:text-[#D1DDD3]"
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
            )}
          </section>

          {/* Evidence Cards */}
          <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {filteredEvidence.map((ev, idx) => {
              const pLabel = EVIDENCE_PARAM_LABELS[lang][ev.parameter];
              const isFarmer = ev.data_source === "farmer_input";
              return (
                <article
                  key={idx}
                  data-testid={`evidence-card-${ev.data_source}`}
                  className="fs-liquid-panel rounded-3xl p-4 sm:p-5 text-[#111813] dark:text-[#F5F7F5]"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      {isFarmer ? (
                        <UserCheck size={18} className="text-[#15803D] dark:text-[#86EFAC]" />
                      ) : (
                        <Database size={18} className="text-[#15803D] dark:text-[#86EFAC]" />
                      )}
                      <h3 className="font-heading text-sm font-bold text-[#111813] dark:text-[#F5F7F5]">
                        {plainMode ? pLabel.plain : pLabel.tech}
                      </h3>
                    </div>

                    <div className="flex flex-wrap items-center gap-1.5">
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                          isFarmer
                            ? "bg-amber-500/15 text-amber-800 dark:bg-amber-500/20 dark:text-[#FCD34D]"
                            : "bg-[#15803D]/15 text-[#15803D] dark:bg-[#22C55E]/20 dark:text-[#86EFAC]"
                        }`}
                      >
                        {DATA_SOURCE_LABELS[lang][ev.data_source] ?? ev.data_source}
                      </span>
                      {ev.source_mission && (
                        <span className="rounded-full border border-[#111813]/12 bg-[#111813]/[0.05] px-2 py-0.5 text-[10px] font-semibold text-[#3E4C42] dark:border-white/15 dark:bg-white/[0.08] dark:text-[#D1DDD3]">
                          {ev.source_mission}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="fs-liquid-well mt-3 flex flex-wrap items-baseline justify-between gap-2 rounded-2xl px-3.5 py-2.5">
                    <span
                      dir={lang === "ar" ? "auto" : "ltr"}
                      className="font-mono text-lg font-bold tabular-nums text-[#111813] dark:text-[#F5F7F5]"
                    >
                      {localizeEvidenceValue(ev.observed_value, lang)}{" "}
                      <span className="font-sans text-xs font-normal text-[#4A5A4E] dark:text-[#9CA89E]">
                        {localizeUnit(ev.unit, lang)}
                      </span>
                    </span>
                    <span className="rounded-full border border-[#15803D]/25 bg-[#15803D]/10 px-2.5 py-0.5 text-[10px] font-semibold text-[#15803D] dark:border-[#22C55E]/25 dark:bg-[#22C55E]/15 dark:text-[#86EFAC]">
                      {ev.derived ? t.derivedBadge : t.directBadge}
                    </span>
                  </div>

                  <p className="mt-2.5 text-xs leading-relaxed text-[#3E4C42] dark:text-[#D1DDD3]">
                    {localizePlainText(ev.interpretation, lang, plainMode)}
                  </p>

                  <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[10px] text-[#4A5A4E] dark:text-[#9CA89E]">
                    <span>{ev.contextLabel}</span>
                    {ev.period && (
                      <span dir={lang === "ar" ? "auto" : "ltr"}>
                        {localizePeriod(ev.period, lang)}
                      </span>
                    )}
                  </div>
                </article>
              );
            })}
          </section>

          {/* Data Quality Ledger & Spatial Context */}
          <section className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            {/* Quality & Gaps */}
            <div className="fs-liquid-panel rounded-3xl p-5 text-[#111813] dark:text-[#F5F7F5]">
              <div className="flex items-center justify-between">
                <h2 className="font-heading text-base font-bold text-[#111813] dark:text-[#F5F7F5]">
                  {t.qualityTitle}
                </h2>
                <span className="tabular-nums rounded-full border border-[#15803D]/25 bg-[#15803D]/10 px-3 py-0.5 text-xs font-semibold text-[#15803D] dark:border-[#22C55E]/30 dark:bg-[#22C55E]/15 dark:text-[#86EFAC]">
                  {completenessPct}%
                </span>
              </div>
              <div className="mt-2.5 h-2 w-full overflow-hidden rounded-full bg-[#111813]/10 dark:bg-white/10">
                <div
                  className="h-full rounded-full bg-[#15803D] dark:bg-[#22C55E]"
                  style={{ width: `${completenessPct}%` }}
                />
              </div>
              {dq?.confidence_note && (
                <p className="mt-3 text-xs text-[#3E4C42] dark:text-[#D1DDD3]">
                  {localizeDynamicPhrase(dq.confidence_note, lang)}
                </p>
              )}

              <p className="mt-4 text-xs font-bold text-red-700 dark:text-red-300">
                {t.missingDataTitle}
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {(dq?.missing_data ?? []).map((md) => (
                  <span
                    key={md}
                    dir={lang === "ar" ? "auto" : "ltr"}
                    className="inline-flex items-center gap-1 rounded-full border border-red-300/80 bg-red-50/90 px-2.5 py-0.5 text-[11px] font-semibold text-red-700 dark:border-red-500/35 dark:bg-red-500/15 dark:text-red-300"
                  >
                    <Warning size={12} />
                    {localizeMissingField(md, lang, plainMode)}
                  </span>
                ))}
              </div>

              {(dq?.limitations ?? []).length > 0 && (
                <ul className="mt-3 list-disc space-y-1 ps-4 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">
                  {dq?.limitations.map((lim, i) => (
                    <li key={i}>{localizeDynamicPhrase(lim, lang)}</li>
                  ))}
                </ul>
              )}

              <Link
                href="/farm-profile"
                className="fs-cta-primary mt-4 inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold active:not-disabled:scale-[0.96]"
              >
                {t.fixInProfileBtn}
                <ArrowRight size={14} weight="bold" className="rtl:-scale-x-100" />
              </Link>
            </div>

            {/* Visual Reference Spatial Map */}
            <div className="fs-liquid-panel rounded-3xl p-5 text-[#111813] dark:text-[#F5F7F5]">
              <h2 className="flex items-center gap-2 font-heading text-base font-bold text-[#111813] dark:text-[#F5F7F5]">
                <GlobeHemisphereEast size={18} className="text-[#15803D] dark:text-[#86EFAC]" />
                {t.spatialTitle}
              </h2>
              <p className="mt-1 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">{t.spatialNote}</p>

              <svg
                viewBox="0 0 300 170"
                className="mt-3 h-48 w-full rounded-2xl bg-[#1A2619] ring-1 ring-[#111813]/12 dark:ring-white/12"
              >
                <polygon
                  points={boundaryRing
                    .map(([lon, lat]) => {
                      const x = ((lon - 6.95) / 1.0) * 280 + 10;
                      const y = ((36.7 - lat) / 0.7) * 150 + 10;
                      return `${x},${y}`;
                    })
                    .join(" ")}
                  fill="rgba(95, 168, 125, 0.14)"
                  stroke="#5FA87D"
                  strokeWidth="2"
                  strokeDasharray="5 3"
                />
                {fields.map((f) => {
                  const x = Math.max(12, Math.min(288, ((f.location.longitude - 6.95) / 1.0) * 280 + 10));
                  const y = Math.max(12, Math.min(158, ((36.7 - f.location.latitude) / 0.7) * 150 + 10));
                  return (
                    <g key={f.field_id}>
                      <circle cx={x} cy={y} r="7" fill="#84E875" stroke="#00291B" strokeWidth="1.5" />
                      <text x={x + 10} y={y + 4} fill="#FFFFFF" fontSize="10" fontWeight="700">
                        {f.field_id} ({f.location.latitude.toFixed(2)}°N, {f.location.longitude.toFixed(2)}°E)
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
