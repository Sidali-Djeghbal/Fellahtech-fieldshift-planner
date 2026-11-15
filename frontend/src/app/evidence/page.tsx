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
import { EVIDENCE_PARAM_LABELS, UI_DICT, localizePlainText } from "@/lib/i18n";
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
  const {
    lang,
    plainMode,
    authMode,
    activeFarmId,
    activeAnalysisId,
    simulateDegradedReplay,
  } = useAppStore();

  const t = UI_DICT[lang].evidence;
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
            list.push({ ...ev, contextLabel: `${fp.field_id} · ${strat.name}` });
          }
        }
      }
      for (const rq of fp.requested_crop_results) {
        for (const ev of rq.evidence ?? []) {
          const key = `${ev.data_source}:${ev.source_mission ?? ""}:${ev.parameter}:${String(ev.observed_value)}`;
          if (!seen.has(key)) {
            seen.add(key);
            list.push({ ...ev, contextLabel: `${fp.field_id} · ${rq.requested_crop_id}` });
          }
        }
      }
    }
    return list;
  }, [envelope]);

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
    <div className="space-y-5">
      <div>
        <h1 className="font-heading text-2xl font-extrabold text-[#111827]">{t.title}</h1>
        <p className="mt-1 text-xs text-[#6B7280]">{t.subtitle}</p>
      </div>

      {analysisQuery.error && <ApiErrorCard error={analysisQuery.error} lang={lang} />}

      {envelope && (
        <>
          <DegradedReplayBanner degradedMode={envelope.degraded_mode} lang={lang} />
          <WarningsBanner warnings={envelope.warnings} lang={lang} />

          {/* Multi-Scale Fusion Explainer */}
          <section className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-sm text-[#111827]">
            <div className="flex items-start gap-3">
              <Stack size={24} className="mt-0.5 shrink-0 text-[#137135]" />
              <div>
                <h2 className="font-heading text-base font-bold text-[#111827]">{t.fusionTitle}</h2>
                <p className="mt-1 text-xs leading-relaxed text-[#374151]">{t.fusionBody}</p>
                <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                  <span className="rounded bg-emerald-50 border border-emerald-200 px-2.5 py-1 text-[#00291B]">
                    dataset_version_used:{" "}
                    <strong dir="ltr" className="text-[#00291B]">
                      {envelope.result.dataset_version_used}
                    </strong>
                  </span>
                  <span className="rounded bg-emerald-50 border border-emerald-200 px-2.5 py-1 text-[#00291B]">
                    ml_engine_version:{" "}
                    <strong dir="ltr" className="text-[#00291B]">
                      {envelope.result.ml_engine_version}
                    </strong>
                  </span>
                </div>
              </div>
            </div>
          </section>

          {/* Provenance Filter Bar */}
          <section className="rounded-2xl border border-[#E5E7EB] bg-white p-4 shadow-sm text-[#111827]">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setSourceFilter("all")}
                  className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                    sourceFilter === "all"
                      ? "bg-[#00291B] text-white shadow-xs"
                      : "border border-gray-200 bg-white text-[#374151] hover:bg-gray-50"
                  }`}
                >
                  {t.filterAll} ({collectedEvidence.length})
                </button>
                <button
                  type="button"
                  data-testid="filter-farmer-input"
                  onClick={() => setSourceFilter("farmer_input")}
                  className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                    sourceFilter === "farmer_input"
                      ? "bg-[#00291B] text-white shadow-xs"
                      : "border border-gray-200 bg-white text-[#374151] hover:bg-gray-50"
                  }`}
                >
                  {t.filterFarmer}
                </button>
                <button
                  type="button"
                  data-testid="filter-dataset"
                  onClick={() => setSourceFilter("dataset")}
                  className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                    sourceFilter === "dataset"
                      ? "bg-[#00291B] text-white shadow-xs"
                      : "border border-gray-200 bg-white text-[#374151] hover:bg-gray-50"
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
                      className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize transition ${
                        groupFilter === grp
                          ? "bg-[#137135] text-white"
                          : "border border-gray-200 bg-gray-50 text-gray-600 hover:bg-gray-100"
                      }`}
                    >
                      {grp.replace("_", " & ")}
                    </button>
                  )
                )}
              </div>
            </div>

            {missions.length > 0 && (
              <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-gray-200 pt-3">
                <span className="text-[11px] text-[#6B7280]">Agronomic tag:</span>
                <button
                  type="button"
                  onClick={() => setMissionFilter("all")}
                  className={`rounded px-2 py-0.5 text-[11px] transition ${
                    missionFilter === "all"
                      ? "bg-[#00291B] text-white font-semibold"
                      : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  }`}
                >
                  All
                </button>
                {missions.map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setMissionFilter(m)}
                    className={`rounded px-2 py-0.5 text-[11px] transition ${
                      missionFilter === m
                        ? "bg-[#00291B] text-white font-semibold"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
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
                  className="rounded-2xl border border-[#E5E7EB] bg-white p-4 shadow-sm text-[#111827]"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      {isFarmer ? (
                        <UserCheck size={18} className="text-[#137135]" />
                      ) : (
                        <Database size={18} className="text-[#137135]" />
                      )}
                      <h3 className="font-heading text-sm font-bold text-[#111827]">
                        {plainMode ? pLabel.plain : pLabel.tech}
                      </h3>
                    </div>

                    <div className="flex flex-wrap items-center gap-1.5">
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                          isFarmer ? "bg-[#FEF3C7] text-[#D97706]" : "bg-[#DCFCE7] text-[#15803D]"
                        }`}
                      >
                        {ev.data_source}
                      </span>
                      {ev.source_mission && (
                        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-semibold text-gray-700">
                          {ev.source_mission}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap items-baseline justify-between gap-2 rounded-xl border border-gray-200 bg-gray-50/70 px-3 py-2">
                    <span dir="ltr" className="tabular-nums text-lg font-extrabold text-[#111827]">
                      {String(ev.observed_value)}{" "}
                      <span className="text-xs font-normal text-[#6B7280]">{ev.unit ?? ""}</span>
                    </span>
                    <span className="rounded bg-white border border-gray-200 px-2 py-0.5 text-[10px] font-semibold text-[#137135]">
                      {ev.derived ? t.derivedBadge : t.directBadge}
                    </span>
                  </div>

                  <p className="mt-2.5 text-xs leading-relaxed text-[#374151]">
                    {localizePlainText(ev.interpretation, lang, plainMode)}
                  </p>

                  <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[10px] text-[#6B7280]">
                    <span>{ev.contextLabel}</span>
                    {ev.period && <span dir="ltr">{ev.period}</span>}
                  </div>
                </article>
              );
            })}
          </section>

          {/* Data Quality Ledger & Spatial Context */}
          <section className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            {/* Quality & Gaps */}
            <div className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-sm text-[#111827]">
              <div className="flex items-center justify-between">
                <h2 className="font-heading text-base font-bold text-[#111827]">{t.qualityTitle}</h2>
                <span className="tabular-nums rounded-full bg-[#DCFCE7] text-[#15803D] px-3 py-0.5 text-xs font-bold">
                  {completenessPct}%
                </span>
              </div>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-gray-200">
                <div className="h-full bg-[#137135]" style={{ width: `${completenessPct}%` }} />
              </div>
              {dq?.confidence_note && (
                <p className="mt-3 text-xs text-[#374151]">{dq.confidence_note}</p>
              )}

              <p className="mt-4 text-xs font-bold text-red-700">{t.missingDataTitle}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {(dq?.missing_data ?? []).map((md) => (
                  <span
                    key={md}
                    dir="ltr"
                    className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-50 px-2.5 py-0.5 text-[11px] font-semibold text-red-700"
                  >
                    <Warning size={12} />
                    {md}
                  </span>
                ))}
              </div>

              {(dq?.limitations ?? []).length > 0 && (
                <ul className="mt-3 list-disc space-y-1 ps-4 text-xs text-[#6B7280]">
                  {dq?.limitations.map((lim, i) => (
                    <li key={i}>{lim}</li>
                  ))}
                </ul>
              )}

              <Link
                href="/farm-profile"
                className="mt-4 inline-flex items-center gap-2 rounded-xl bg-[#00291B] text-white px-4 py-2 text-xs font-bold hover:bg-[#04421B] shadow-sm transition"
              >
                {t.fixInProfileBtn}
                <ArrowRight size={14} weight="bold" />
              </Link>
            </div>

            {/* Visual Reference Spatial Map */}
            <div className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-sm text-[#111827]">
              <h2 className="flex items-center gap-2 font-heading text-base font-bold text-[#111827]">
                <GlobeHemisphereEast size={18} className="text-[#137135]" />
                {t.spatialTitle}
              </h2>
              <p className="mt-1 text-xs text-[#6B7280]">{t.spatialNote}</p>

              <svg
                viewBox="0 0 300 170"
                className="mt-3 h-48 w-full rounded-xl border border-[#E5E7EB] bg-[#2D3C21]"
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
