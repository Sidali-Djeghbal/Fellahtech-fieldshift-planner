"use client";

import React from "react";
import {
  Brain,
  Compass,
  Drop,
  GlobeHemisphereEast,
  Leaf,
  PencilSimple,
  Play,
  Plus,
  Trash,
  X,
} from "@phosphor-icons/react";
import { findNearestGuelmaCommune } from "@/lib/geo/guelma";
import {
  IRRIGATION_SYSTEM_LABELS,
  SOIL_TYPE_LABELS,
  WATER_AVAILABILITY_LABELS,
} from "@/lib/i18n";
import { GUELMA_WORKSPACE_I18N } from "@/lib/i18n/guelmaWorkspace";
import { INTELLIGENCE_I18N } from "@/lib/i18n/intelligence";
import type { FarmPublic, FieldDetailPublic, FieldPlan, Language } from "@/lib/schemas";

interface ParcelInspectorPanelProps {
  lang: Language;
  farms: FarmPublic[];
  selectedField: FieldDetailPublic | null;
  fieldPlan: FieldPlan | null | undefined;
  onStartAddFarm: () => void;
  onLoadSamples: () => void;
  onOpenAnalysis: (farmId: string, fieldId: string) => void;
  onScrollToPlan: (fieldId: string) => void;
  onInspect3d: (farmId: string, fieldId: string) => void;
  onEditBorders?: (field: FieldDetailPublic) => void;
  onEditInfo: (field: FieldDetailPublic) => void;
  onDeleteField?: (field: FieldDetailPublic) => void;
  onCloseInspector?: () => void;
}

export function ParcelInspectorPanel({
  lang,
  farms,
  selectedField,
  fieldPlan,
  onStartAddFarm,
  onLoadSamples,
  onOpenAnalysis,
  onScrollToPlan,
  onInspect3d,
  onEditInfo,
  onDeleteField,
  onCloseInspector,
}: ParcelInspectorPanelProps) {
  const dict = GUELMA_WORKSPACE_I18N[lang];
  const intel = INTELLIGENCE_I18N[lang];
  const insp = intel.workstation.inspector;
  const hud = intel.workstation.mapHud;

  if (farms.length === 0) {
    const steps = [dict.emptyStep1, dict.emptyStep2, dict.emptyStep3];
    return (
      <aside
        data-testid="empty-workspace-card"
        className="lg-surface lg-specular flex flex-col justify-between rounded-2xl p-4 text-[#111813] dark:text-[#F5F7F5] sm:p-5"
      >
        <div>
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#111813]/[0.06] text-[#15803D] dark:bg-white/[0.08] dark:text-[#4ADE80]">
              <GlobeHemisphereEast size={20} weight="regular" aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <p className="font-mono text-[10px] font-medium uppercase tracking-wider text-[#15803D] dark:text-[#4ADE80]">
                {dict.provinceBadge}
              </p>
              <h2 className="mt-1 font-heading text-base font-semibold tracking-tight text-[#111813] dark:text-[#F5F7F5]">
                {dict.emptyTitle}
              </h2>
            </div>
          </div>

          <p className="mt-2.5 max-w-[65ch] text-xs leading-relaxed text-[#4A5A4E] dark:text-[#9CA89E]">
            {dict.emptyDesc}
          </p>

          <ol className="mt-3.5 space-y-2">
            {steps.map((stepText, idx) => (
              <li
                key={idx}
                className="flex items-start gap-2.5 rounded-xl bg-[#111813]/[0.04] px-3 py-2 text-xs text-[#243227] dark:bg-white/[0.05] dark:text-[#E5EAE6]"
              >
                <span className="shrink-0 font-mono text-[11px] font-semibold tabular-nums text-[#15803D] dark:text-[#4ADE80]">
                  {String(idx + 1).padStart(2, "0")}
                </span>
                <span className="leading-snug">{stepText}</span>
              </li>
            ))}
          </ol>
        </div>

        <div className="mt-4 flex flex-col gap-2">
          <button
            type="button"
            onClick={onStartAddFarm}
            data-testid="empty-add-farm-btn"
            className="fs-cta-primary inline-flex min-h-10 w-full items-center justify-center gap-1.5 whitespace-nowrap rounded-full ps-4 pe-4 text-xs font-semibold active:not-disabled:scale-[0.96]"
          >
            <Plus size={14} weight="bold" aria-hidden="true" />
            <span>{dict.addFarmBtn.replace(/^\+\s*/, "")}</span>
          </button>

          <button
            type="button"
            onClick={onLoadSamples}
            data-testid="load-samples-btn"
            className="lg-capsule inline-flex min-h-10 w-full items-center justify-center gap-1.5 whitespace-nowrap rounded-full px-4 text-xs font-medium text-[#111813] active:not-disabled:scale-[0.96] dark:text-[#F5F7F5]"
          >
            <Compass size={14} className="text-[#15803D] dark:text-[#4ADE80]" aria-hidden="true" />
            <span>{dict.loadSamplesBtn}</span>
          </button>
        </div>
      </aside>
    );
  }

  if (!selectedField) {
    return (
      <aside
        data-testid="parcel-inspector-panel"
        className="lg-surface lg-specular flex flex-col justify-center rounded-2xl p-5 text-[#111813] dark:text-[#F5F7F5]"
      >
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#111813]/[0.06] text-[#15803D] dark:bg-white/[0.08] dark:text-[#4ADE80]">
            <Compass size={20} aria-hidden="true" />
          </div>
          <div>
            <p className="font-mono text-[10px] font-medium uppercase tracking-wider text-[#4A5A4E] dark:text-[#9CA89E]">
              {insp.headerTitle}
            </p>
            <p className="mt-1.5 max-w-[65ch] text-xs leading-relaxed text-[#4A5A4E] dark:text-[#9CA89E]">
              {insp.noSelection}
            </p>
          </div>
        </div>
      </aside>
    );
  }

  const commune = findNearestGuelmaCommune(
    selectedField.location.latitude,
    selectedField.location.longitude
  );
  const latestCrop = selectedField.crop_history[0];
  const latestCropLabel = latestCrop
    ? `${latestCrop.crop_name_raw || latestCrop.crop_id || "—"} (${latestCrop.year})`
    : "—";

  const readinessScore = (() => {
    if (fieldPlan?.suggested_strategy_id) {
      const strat = fieldPlan.strategies.find(
        (s) => s.strategy_id === fieldPlan.suggested_strategy_id
      );
      if (strat) return Math.round(strat.scores.priority_fit);
    }
    let pts = 35;
    if (selectedField.soil.source === "farmer" && selectedField.soil.soil_type !== "unknown") pts += 25;
    if (selectedField.elevation_m !== null && selectedField.elevation_m !== undefined) pts += 15;
    if (selectedField.crop_history.length > 0) pts += 25;
    return Math.min(pts, 100);
  })();

  const soilSummary =
    selectedField.soil.source === "farmer"
      ? `${SOIL_TYPE_LABELS[lang][selectedField.soil.soil_type]}${
          selectedField.soil.soil_ph !== null && selectedField.soil.soil_ph !== undefined
            ? ` · pH ${selectedField.soil.soil_ph}`
            : ""
        }`
      : dict.soilUnknownTag;

  return (
    <aside
      data-testid="parcel-inspector-panel"
      className="lg-surface lg-specular rounded-2xl p-4 text-[#111813] dark:text-[#F5F7F5]"
    >
      {/* Header: Parcel Name + Crop / Hectares + Dismiss */}
      <div className="flex items-start justify-between gap-2.5">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] font-medium uppercase tracking-wider text-[#4A5A4E] dark:text-[#9CA89E]">
              {insp.headerTitle}
            </span>
            <span className="rounded-md bg-[#15803D]/10 px-1.5 py-0.5 font-mono text-[10px] font-medium text-[#15803D] dark:bg-white/10 dark:text-[#4ADE80]">
              {selectedField.field_id}
            </span>
          </div>
          <h3 className="mt-1 truncate font-heading text-base font-semibold text-[#111813] dark:text-[#F5F7F5]">
            {selectedField.field_name}
          </h3>
          <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
            <span>{commune.name[lang] || commune.name.en}</span>
            <span aria-hidden="true">·</span>
            <span className="font-mono font-semibold tabular-nums text-[#15803D] dark:text-[#4ADE80]">
              {selectedField.area_hectares.toFixed(2)} ha
            </span>
          </p>
        </div>

        {onCloseInspector ? (
          <button
            type="button"
            onClick={onCloseInspector}
            aria-label={hud.closeInspectorLabel}
            className="lg-capsule flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[#4A5A4E] transition-[transform,background-color,color] duration-150 ease-out hover:text-[#111813] active:scale-[0.96] dark:text-[#9CA89E] dark:hover:text-[#F5F7F5]"
          >
            <X size={14} aria-hidden="true" />
          </button>
        ) : null}
      </div>

      {/* Growth / Agronomic Readiness Bar */}
      <div className="mt-3">
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-[#4A5A4E] dark:text-[#9CA89E]">{hud.readinessLabel}</span>
          <span className="font-mono font-semibold tabular-nums text-[#15803D] dark:text-[#4ADE80]">
            {readinessScore}%
          </span>
        </div>
        <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-[#111813]/10 dark:bg-white/10">
          <div
            className="h-full rounded-full bg-gradient-to-r from-[#16A34A] via-[#4ADE80] to-[#EAB34D] transition-[width] duration-300 ease-out"
            style={{ width: `${readinessScore}%` }}
          />
        </div>
      </div>

      {/* Compact Liquid-Glass Key Telemetry Rows */}
      <dl className="mt-3 space-y-1.5 rounded-xl bg-[#111813]/[0.04] px-3 py-2.5 text-xs dark:bg-white/[0.05]">
        <div className="flex items-center justify-between gap-2">
          <dt className="flex items-center gap-1.5 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
            <Leaf size={13} className="text-[#15803D] dark:text-[#4ADE80]" aria-hidden="true" />
            <span>{insp.soil}</span>
          </dt>
          <dd className="truncate font-medium text-[#111813] dark:text-[#F5F7F5]">{soilSummary}</dd>
        </div>

        <div className="flex items-center justify-between gap-2">
          <dt className="flex items-center gap-1.5 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
            <Drop size={13} className="text-sky-600 dark:text-sky-400" aria-hidden="true" />
            <span>{insp.water}</span>
          </dt>
          <dd className="truncate font-medium text-[#111813] dark:text-[#F5F7F5]">
            {WATER_AVAILABILITY_LABELS[lang][selectedField.water.availability]} ·{" "}
            {IRRIGATION_SYSTEM_LABELS[lang][selectedField.water.irrigation_system]}
          </dd>
        </div>

        <div className="flex items-center justify-between gap-2">
          <dt className="text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">{insp.coordinates}</dt>
          <dd className="font-mono text-[11px] tabular-nums text-[#243227] dark:text-[#E5EAE6]" dir="ltr">
            {selectedField.location.latitude.toFixed(4)}°N,{" "}
            {selectedField.location.longitude.toFixed(4)}°E
          </dd>
        </div>

        <div className="flex items-center justify-between gap-2">
          <dt className="text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">{insp.elevation}</dt>
          <dd className="font-mono text-[11px] tabular-nums text-[#243227] dark:text-[#E5EAE6]">
            {selectedField.elevation_m !== null && selectedField.elevation_m !== undefined
              ? `${selectedField.elevation_m} m`
              : dict.elevNotProvided}
          </dd>
        </div>

        <div className="flex items-center justify-between gap-2">
          <dt className="text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">{insp.latestCrop}</dt>
          <dd className="truncate font-medium text-[#111813] dark:text-[#F5F7F5]">{latestCropLabel}</dd>
        </div>

        <div className="flex items-center justify-between gap-2 pt-0.5">
          <dt className="flex items-center gap-1.5 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
            <Brain size={13} className="text-[#15803D] dark:text-[#4ADE80]" aria-hidden="true" />
            <span>{insp.aiStatus}</span>
          </dt>
          <dd>
            {fieldPlan ? (
              <span
                className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                  fieldPlan.status === "ok"
                    ? "bg-[#15803D]/12 text-[#15803D] dark:bg-[#4ADE80]/20 dark:text-[#4ADE80]"
                    : "bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-300"
                }`}
              >
                {fieldPlan.status === "ok"
                  ? intel.fieldStatus.aiAnalyzed
                  : intel.fieldStatus.aiPartial}
              </span>
            ) : (
              <span className="text-[11px] font-medium text-amber-700 dark:text-amber-300">
                {intel.fieldStatus.aiNotAnalyzed}
              </span>
            )}
          </dd>
        </div>
      </dl>

      {/* Action Buttons */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {fieldPlan ? (
          <button
            type="button"
            onClick={() => onScrollToPlan(selectedField.field_id)}
            className="fs-cta-primary inline-flex min-h-9 min-w-full flex-1 items-center justify-center gap-1.5 rounded-xl px-3 text-xs font-semibold active:not-disabled:scale-[0.96]"
          >
            <Brain size={14} weight="fill" aria-hidden="true" />
            <span>{insp.openPlanBtn}</span>
          </button>
        ) : (
          <button
            type="button"
            onClick={() => onOpenAnalysis(selectedField.farm_id, selectedField.field_id)}
            className="fs-cta-primary inline-flex min-h-9 flex-1 items-center justify-center gap-1.5 rounded-xl px-3 text-xs font-semibold active:not-disabled:scale-[0.96]"
          >
            <Brain size={14} aria-hidden="true" />
            <span>{insp.analyzeBtn}</span>
          </button>
        )}

        <button
          type="button"
          onClick={() => onInspect3d(selectedField.farm_id, selectedField.field_id)}
          className="lg-capsule inline-flex min-h-9 items-center justify-center gap-1 rounded-xl px-2.5 text-[11px] font-medium text-[#111813] active:not-disabled:scale-[0.96] dark:text-[#F5F7F5]"
          title={insp.sim3dBtn}
        >
          <Play size={12} weight="fill" className="text-[#15803D] dark:text-[#4ADE80]" aria-hidden="true" />
          <span>{insp.sim3dBtn}</span>
        </button>

        <button
          type="button"
          onClick={() => onEditInfo(selectedField)}
          className="lg-capsule inline-flex min-h-9 items-center justify-center gap-1 rounded-xl px-2.5 text-[11px] font-medium text-[#111813] active:not-disabled:scale-[0.96] dark:text-[#F5F7F5]"
          title={dict.editInfoBtn}
        >
          <PencilSimple size={12} aria-hidden="true" />
          <span>{insp.editInfoBtn}</span>
        </button>

        {onDeleteField ? (
          <button
            type="button"
            onClick={() => onDeleteField(selectedField)}
            aria-label={dict.removeFieldBtn}
            title={dict.removeFieldBtn}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-red-50 text-red-600 transition-[transform,background-color] duration-150 ease-out hover:bg-red-100 active:scale-[0.96] dark:bg-red-500/15 dark:text-red-300 dark:hover:bg-red-500/25"
          >
            <Trash size={13} aria-hidden="true" />
          </button>
        ) : null}
      </div>
    </aside>
  );
}
