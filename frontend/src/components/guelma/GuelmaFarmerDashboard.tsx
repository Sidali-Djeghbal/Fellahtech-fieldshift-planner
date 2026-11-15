"use client";

import React from "react";
import {
  Compass,
  Drop,
  GlobeHemisphereEast,
  Leaf,
  MapPin,
  MapTrifold,
  PencilSimple,
  Play,
  Plus,
  Polygon,
  Sparkle,
  Stack,
  Trash,
} from "@phosphor-icons/react";
import { FieldShiftLogo } from "@/components/brand/FieldShiftLogo";
import { FieldPolygonThumbnail } from "@/components/guelma/FieldPolygonThumbnail";
import { GuelmaOverviewMap } from "@/components/guelma/GuelmaOverviewMap";
import {
  findNearestGuelmaCommune,
  isInsideGuelmaBoundary,
  GUELMA_FALLBACK_BOUNDARY,
  extractRingFromBoundary,
} from "@/lib/geo/guelma";
import {
  IRRIGATION_SYSTEM_LABELS,
  SOIL_TYPE_LABELS,
  WATER_AVAILABILITY_LABELS,
} from "@/lib/i18n";
import { GUELMA_WORKSPACE_I18N } from "@/lib/i18n/guelmaWorkspace";
import type { FarmPublic, FieldDetailPublic, Language } from "@/lib/schemas";
import { fieldKey } from "@/store/useGuelmaWorkspace";

interface GuelmaFarmerDashboardProps {
  lang: Language;
  farms: FarmPublic[];
  fields: FieldDetailPublic[];
  selectedFieldKey: string | null;
  onChangeLang: (lang: Language) => void;
  onSelectField: (farmId: string, fieldId: string) => void;
  onStartAddFarm: () => void;
  onStartAddFieldToFarm: (farmId: string) => void;
  onLoadSamples: () => void;
  onResetWorkspace: () => void;
  onInspectField: (farmId: string, fieldId: string) => void;
  onEditFieldBorders: (field: FieldDetailPublic) => void;
  onEditFieldInfo: (field: FieldDetailPublic) => void;
  onRequestRemoveField: (field: FieldDetailPublic) => void;
  onEditFarm: (farm: FarmPublic) => void;
  onRequestRemoveFarm: (farm: FarmPublic) => void;
}

export function GuelmaFarmerDashboard({
  lang,
  farms,
  fields,
  selectedFieldKey,
  onChangeLang,
  onSelectField,
  onStartAddFarm,
  onStartAddFieldToFarm,
  onLoadSamples,
  onResetWorkspace,
  onInspectField,
  onEditFieldBorders,
  onEditFieldInfo,
  onRequestRemoveField,
  onEditFarm,
  onRequestRemoveFarm,
}: GuelmaFarmerDashboardProps) {
  const dict = GUELMA_WORKSPACE_I18N[lang];
  const totalHa = fields.reduce((sum, f) => sum + (Number(f.area_hectares) || 0), 0);
  const coveredCommunes = new Set<string>();
  farms.forEach((fm) => {
    if (fm.commune) coveredCommunes.add(fm.commune);
  });
  fields.forEach((fl) => {
    const c = findNearestGuelmaCommune(fl.location.latitude, fl.location.longitude);
    coveredCommunes.add(c.name.en);
  });

  return (
    <div
      className="min-h-screen bg-[#EAECEB] text-[#111827]"
      data-testid="guelma-farmer-dashboard"
    >
      {/* Clean Botanical Light Top Navigation Bar */}
      <header className="sticky top-0 z-30 border-b border-[#D5E0D9] bg-white/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <FieldShiftLogo size={32} />
            <div>
              <div className="flex items-center gap-2">
                <span className="font-heading text-sm font-extrabold tracking-tight text-[#0B4B2E]">
                  FIELD SHIFT
                </span>
                <span className="rounded-full bg-[#ECFDF5] px-2.5 py-0.5 text-[11px] font-semibold text-[#065F46] ring-1 ring-[#A7F3D0]">
                  {dict.brandTag}
                </span>
              </div>
              <p className="hidden text-[11px] text-[#6B7280] sm:block">
                {dict.dashboardSubtitle}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            {/* Trilingual Switcher */}
            <div
              className="inline-flex rounded-full border border-[#D5E0D9] bg-[#F4F7F5] p-0.5 text-xs font-bold"
              role="group"
              aria-label="Language switcher"
            >
              {(["en", "fr", "ar"] as const).map((l) => (
                <button
                  key={l}
                  type="button"
                  onClick={() => onChangeLang(l)}
                  data-testid={`dash-lang-${l}`}
                  aria-pressed={lang === l}
                  className={`rounded-full px-2.5 py-1 uppercase transition ${
                    lang === l
                      ? "bg-[#0B4B2E] text-white shadow-xs"
                      : "text-[#4B5563] hover:text-[#111827]"
                  }`}
                >
                  {l}
                </button>
              ))}
            </div>

            {farms.length > 0 ? (
              <button
                type="button"
                onClick={onResetWorkspace}
                data-testid="reset-workspace-btn"
                className="rounded-full border border-[#D1D5DB] bg-white px-3 py-1.5 text-xs font-semibold text-[#4B5563] transition hover:bg-gray-50"
              >
                {dict.clearWorkspaceBtn}
              </button>
            ) : null}

            <button
              type="button"
              onClick={onStartAddFarm}
              data-testid="header-add-farm-btn"
              className="inline-flex items-center gap-1.5 rounded-full bg-[#0B4B2E] px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-[#137135]"
            >
              <Plus size={15} weight="bold" />
              <span>{dict.addFarmBtn.replace(/^\+\s*/, "")}</span>
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-5 px-4 py-6 sm:px-6">
        {/* Dashboard Headline & KPI Strip */}
        <section className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#137135]">
              <Compass size={15} weight="duotone" />
              <span>{dict.provinceBadge}</span>
            </span>
            <h1 className="mt-1 font-heading text-2xl font-extrabold tracking-tight text-[#0B4B2E] sm:text-3xl">
              {dict.dashboardTitle}
            </h1>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-2xl border border-[#DCE3DF] bg-white px-4 py-3 shadow-xs">
              <div className="text-[11px] font-medium text-[#6B7280]">{dict.kpiFarms}</div>
              <div className="mt-0.5 font-mono text-xl font-bold text-[#0B4B2E]" data-testid="kpi-farms">
                {farms.length}
              </div>
            </div>
            <div className="rounded-2xl border border-[#DCE3DF] bg-white px-4 py-3 shadow-xs">
              <div className="text-[11px] font-medium text-[#6B7280]">{dict.kpiFields}</div>
              <div className="mt-0.5 font-mono text-xl font-bold text-[#0B4B2E]" data-testid="kpi-fields">
                {fields.length}
              </div>
            </div>
            <div className="rounded-2xl border border-[#DCE3DF] bg-white px-4 py-3 shadow-xs">
              <div className="text-[11px] font-medium text-[#6B7280]">{dict.kpiArea}</div>
              <div className="mt-0.5 font-mono text-xl font-bold text-[#137135]" data-testid="kpi-area">
                {totalHa.toFixed(1)} ha
              </div>
            </div>
            <div className="rounded-2xl border border-[#DCE3DF] bg-white px-4 py-3 shadow-xs">
              <div className="text-[11px] font-medium text-[#6B7280]">{dict.kpiCommunes}</div>
              <div className="mt-0.5 font-mono text-xl font-bold text-[#0B4B2E]" data-testid="kpi-communes">
                {coveredCommunes.size} / 34
              </div>
            </div>
          </div>
        </section>

        {/* Empty State or Populated Workspace */}
        {farms.length === 0 ? (
          <section className="grid gap-5 lg:grid-cols-5">
            <div
              className="flex flex-col justify-between rounded-2xl border border-[#DCE3DF] bg-white p-6 shadow-sm lg:col-span-3"
              data-testid="empty-workspace-card"
            >
              <div>
                <div className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-[#ECFDF5] text-[#137135]">
                  <MapTrifold size={24} weight="duotone" />
                </div>
                <h2 className="mt-4 font-heading text-xl font-bold text-[#0B4B2E]">
                  {dict.emptyTitle}
                </h2>
                <p className="mt-2 max-w-xl text-sm leading-relaxed text-[#4B5563]">
                  {dict.emptyDesc}
                </p>

                <ul className="mt-5 space-y-2.5 text-xs font-medium text-[#374151]">
                  <li className="flex items-center gap-2.5 rounded-xl bg-[#F6FAF7] px-3.5 py-2.5">
                    <Polygon size={17} className="shrink-0 text-[#137135]" weight="duotone" />
                    <span>{dict.emptyStep1}</span>
                  </li>
                  <li className="flex items-center gap-2.5 rounded-xl bg-[#F6FAF7] px-3.5 py-2.5">
                    <Stack size={17} className="shrink-0 text-[#137135]" weight="duotone" />
                    <span>{dict.emptyStep2}</span>
                  </li>
                  <li className="flex items-center gap-2.5 rounded-xl bg-[#F6FAF7] px-3.5 py-2.5">
                    <Sparkle size={17} className="shrink-0 text-[#137135]" weight="duotone" />
                    <span>{dict.emptyStep3}</span>
                  </li>
                </ul>
              </div>

              <div className="mt-6 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={onStartAddFarm}
                  data-testid="empty-add-farm-btn"
                  className="inline-flex items-center gap-2 rounded-xl bg-[#0B4B2E] px-5 py-3 text-sm font-bold text-white shadow-md transition hover:bg-[#137135]"
                >
                  <Plus size={18} weight="bold" />
                  <span>{dict.addFarmBtn.replace(/^\+\s*/, "")}</span>
                </button>
                <button
                  type="button"
                  onClick={onLoadSamples}
                  data-testid="load-samples-btn"
                  className="inline-flex items-center gap-2 rounded-xl border border-[#CBD7CF] bg-[#F8FAF9] px-4 py-3 text-xs font-bold text-[#0B4B2E] transition hover:bg-[#ECFDF5]"
                >
                  <GlobeHemisphereEast size={16} weight="duotone" />
                  <span>{dict.loadSamplesBtn}</span>
                </button>
              </div>
            </div>

            <div className="lg:col-span-2">
              <GuelmaOverviewMap
                fields={[]}
                selectedFieldKey={null}
                onSelectField={() => {}}
                title={dict.overviewMapTitle}
                subtitle={dict.overviewMapSub}
              />
            </div>
          </section>
        ) : (
          <div className="space-y-6">
            {/* Province Overview Map showing all saved farm/field polygons */}
            <GuelmaOverviewMap
              fields={fields}
              selectedFieldKey={selectedFieldKey}
              onSelectField={onSelectField}
              onOpenInspect={onInspectField}
              title={dict.overviewMapTitle}
              subtitle={dict.overviewMapSub}
            />

            {/* Farms & Parcels Section */}
            <section className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-heading text-lg font-bold text-[#0B4B2E]">
                  {dict.farmsListTitle}
                </h2>
                <button
                  type="button"
                  onClick={onStartAddFarm}
                  data-testid="list-add-farm-btn"
                  className="inline-flex items-center gap-1.5 rounded-xl border border-[#0B4B2E]/25 bg-white px-3.5 py-2 text-xs font-bold text-[#0B4B2E] shadow-xs transition hover:bg-[#ECFDF5]"
                >
                  <Plus size={14} weight="bold" />
                  <span>{dict.addFarmBtn.replace(/^\+\s*/, "")}</span>
                </button>
              </div>

              {farms.map((farm) => {
                const farmFields = fields.filter((f) => f.farm_id === farm.farm_id);
                return (
                  <div
                    key={farm.farm_id}
                    data-testid={`farm-card-${farm.farm_id}`}
                    className="overflow-hidden rounded-2xl border border-[#DCE3DF] bg-white shadow-sm"
                  >
                    {/* Farm Header Bar */}
                    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#E5EAE7] bg-[#F7FAF8] px-5 py-3.5">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-base font-bold text-[#0B4B2E]">
                            {farm.farm_name}
                          </h3>
                          <span className="rounded-full bg-white px-2.5 py-0.5 text-[11px] font-semibold text-[#374151] ring-1 ring-[#D5E0D9]">
                            {dict.communeBadge}: {farm.commune || farm.region}
                          </span>
                          <span className="rounded-full bg-[#ECFDF5] px-2.5 py-0.5 font-mono text-[11px] font-semibold text-[#065F46]">
                            {farmFields.length} {dict.fieldsSuffix}
                          </span>
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          onClick={() => onStartAddFieldToFarm(farm.farm_id)}
                          data-testid={`add-field-farm-${farm.farm_id}`}
                          className="inline-flex items-center gap-1 rounded-lg bg-[#0B4B2E] px-3 py-1.5 text-xs font-bold text-white transition hover:bg-[#137135]"
                        >
                          <Plus size={13} weight="bold" />
                          <span>{dict.addFieldBtn.replace(/^\+\s*/, "")}</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => onEditFarm(farm)}
                          data-testid={`edit-farm-${farm.farm_id}`}
                          className="inline-flex items-center gap-1 rounded-lg border border-[#D1D5DB] bg-white px-2.5 py-1.5 text-xs font-semibold text-[#374151] hover:bg-gray-50"
                        >
                          <PencilSimple size={13} />
                          <span>{dict.editFarmBtn}</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => onRequestRemoveFarm(farm)}
                          data-testid={`remove-farm-${farm.farm_id}`}
                          className="inline-flex items-center gap-1 rounded-lg border border-red-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50"
                        >
                          <Trash size={13} />
                          <span>{dict.removeFarmBtn}</span>
                        </button>
                      </div>
                    </div>

                    {/* Mapped Field Cards Grid */}
                    <div className="grid gap-3 p-4 md:grid-cols-2">
                      {farmFields.map((field) => {
                        const key = fieldKey(field.farm_id, field.field_id);
                        const isSelected = key === selectedFieldKey;
                        const ring = extractRingFromBoundary(field.location.boundary);
                        const inside = isInsideGuelmaBoundary(
                          field.location.latitude,
                          field.location.longitude,
                          GUELMA_FALLBACK_BOUNDARY,
                          ring.length >= 3 ? ring : null
                        );
                        const communeObj = findNearestGuelmaCommune(
                          field.location.latitude,
                          field.location.longitude
                        );
                        const latestHist = field.crop_history[0];

                        return (
                          <article
                            key={key}
                            onClick={() => onSelectField(field.farm_id, field.field_id)}
                            data-testid={`field-card-${field.field_id}`}
                            className={`flex flex-col justify-between gap-3 rounded-xl border p-3.5 transition cursor-pointer ${
                              isSelected
                                ? "border-[#137135] bg-[#F7FCF9] ring-2 ring-[#137135]/20"
                                : "border-[#E5EAE7] bg-white hover:border-[#B6C8BD]"
                            }`}
                          >
                            <div className="flex items-start gap-3.5">
                              <FieldPolygonThumbnail
                                boundary={field.location.boundary}
                                latitude={field.location.latitude}
                                longitude={field.location.longitude}
                                active={isSelected}
                                insideGuelma={inside}
                                areaHectares={field.area_hectares}
                                className="h-20 w-28 shrink-0"
                              />

                              <div className="min-w-0 flex-1">
                                <div className="flex flex-wrap items-center gap-1.5">
                                  <h4 className="truncate text-sm font-bold text-[#111827]">
                                    {field.field_name}
                                  </h4>
                                  <span className="rounded bg-[#F3F4F6] px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[#4B5563]">
                                    {field.field_id}
                                  </span>
                                </div>

                                <div
                                  className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-[#6B7280]"
                                  dir="ltr"
                                >
                                  <span className="inline-flex items-center gap-1 font-sans text-[#065F46] font-medium">
                                    <MapPin size={12} weight="fill" />
                                    {communeObj.name[lang] || communeObj.name.en}
                                  </span>
                                  <span className="font-mono">
                                    {field.location.latitude.toFixed(4)}°N,{" "}
                                    {field.location.longitude.toFixed(4)}°E
                                  </span>
                                </div>

                                <div className="mt-2 flex flex-wrap gap-1.5 text-[10px] font-semibold">
                                  <span
                                    className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${
                                      field.soil.source === "farmer"
                                        ? "bg-[#ECFDF5] text-[#065F46]"
                                        : "bg-[#F3F4F6] text-[#4B5563]"
                                    }`}
                                  >
                                    <Leaf size={11} />
                                    {field.soil.source === "farmer"
                                      ? `${SOIL_TYPE_LABELS[lang][field.soil.soil_type]}${
                                          field.soil.soil_ph ? ` · pH ${field.soil.soil_ph}` : ""
                                        }`
                                      : dict.soilUnknownTag}
                                  </span>

                                  <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 px-2 py-0.5 text-sky-800">
                                    <Drop size={11} />
                                    {WATER_AVAILABILITY_LABELS[lang][field.water.availability]} ·{" "}
                                    {IRRIGATION_SYSTEM_LABELS[lang][field.water.irrigation_system]}
                                  </span>

                                  <span className="rounded-full bg-amber-50 px-2 py-0.5 text-amber-800">
                                    {dict.cropHistoryCount(field.crop_history.length)}
                                    {latestHist
                                      ? ` (${latestHist.crop_name_raw || latestHist.crop_id || ""} ${latestHist.year})`
                                      : ""}
                                  </span>
                                </div>
                              </div>
                            </div>

                            {/* Field Action Strip */}
                            <div
                              className="flex flex-wrap items-center justify-between gap-2 border-t border-[#EDF1EE] pt-2.5"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <span className="font-mono text-[10px] text-[#6B7280]">
                                {field.elevation_m !== null && field.elevation_m !== undefined
                                  ? `${field.elevation_m} m`
                                  : dict.elevNotProvided}
                              </span>

                              <div className="flex flex-wrap items-center gap-1.5">
                                <button
                                  type="button"
                                  onClick={() => onEditFieldBorders(field)}
                                  data-testid={`edit-borders-${field.field_id}`}
                                  className="inline-flex items-center gap-1 rounded-lg border border-[#D1D5DB] bg-white px-2 py-1 text-[11px] font-semibold text-[#374151] hover:bg-gray-50"
                                >
                                  <Polygon size={12} />
                                  <span>{dict.editBordersBtn}</span>
                                </button>
                                <button
                                  type="button"
                                  onClick={() => onEditFieldInfo(field)}
                                  data-testid={`edit-info-${field.field_id}`}
                                  className="inline-flex items-center gap-1 rounded-lg border border-[#D1D5DB] bg-white px-2 py-1 text-[11px] font-semibold text-[#374151] hover:bg-gray-50"
                                >
                                  <PencilSimple size={12} />
                                  <span>{dict.editInfoBtn}</span>
                                </button>
                                <button
                                  type="button"
                                  onClick={() => onRequestRemoveField(field)}
                                  data-testid={`remove-field-${field.field_id}`}
                                  className="inline-flex items-center gap-1 rounded-lg border border-red-200 bg-white px-2 py-1 text-[11px] font-semibold text-red-600 hover:bg-red-50"
                                >
                                  <Trash size={12} />
                                  <span>{dict.removeFieldBtn}</span>
                                </button>
                                <button
                                  type="button"
                                  onClick={() => onInspectField(field.farm_id, field.field_id)}
                                  data-testid={`inspect-field-${field.field_id}`}
                                  className="inline-flex items-center gap-1 rounded-lg bg-[#0B4B2E] px-2.5 py-1 text-[11px] font-bold text-white shadow-xs transition hover:bg-[#137135]"
                                >
                                  <Play size={11} weight="fill" />
                                  <span>{dict.inspectBtn}</span>
                                </button>
                              </div>
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

