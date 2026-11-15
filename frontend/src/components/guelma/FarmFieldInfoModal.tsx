"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  Calculator,
  Check,
  Drop,
  Leaf,
  MapPin,
  Plus,
  Ruler,
  Trash,
  Warning,
  X,
} from "@phosphor-icons/react";
import { useResolvedTheme } from "@/app/providers";
import { UsdaTextureModal } from "@/components/profile/UsdaTextureModal";
import { FieldPolygonThumbnail } from "@/components/guelma/FieldPolygonThumbnail";
import type { BorderDraftResult } from "@/components/guelma/GuelmaBorderEditorMap";
import { fetchAllCatalogItems } from "@/lib/api/endpoints";
import { presentApiError } from "@/lib/api/errors";
import { FIXTURE_CATALOG_ITEMS } from "@/lib/api/fixtures";
import { GUELMA_COMMUNES, localizeCommuneName } from "@/lib/geo/guelma";
import { localizeFarmName } from "@/lib/i18n/dynamicText";
import {
  IRRIGATION_SYSTEM_LABELS,
  SEASON_LABELS,
  SOIL_TYPE_LABELS,
  WATER_AVAILABILITY_LABELS,
  WATER_SOURCE_LABELS,
} from "@/lib/i18n";
import { GUELMA_WORKSPACE_I18N } from "@/lib/i18n/guelmaWorkspace";
import {
  type CropItem,
  type FarmPublic,
  type FarmWriteRequest,
  type FieldDetailPublic,
  type FieldWriteDraft,
  type IrrigationSystem,
  type Language,
  type Season,
  type SoilType,
  type WaterAvailability,
  type WaterSource,
} from "@/lib/schemas";
import { validateSeasonMonthConsistency } from "@/lib/validation";
import { useAppStore } from "@/store/useAppStore";

interface CropRowDraft {
  season: Season;
  year: number;
  planting_month: string;
  crop_id: string;
  crop_name_raw: string;
  yield_tons_per_hectare: string;
  notes: string;
}

export interface FarmFieldFormSubmitPayload {
  mode: "create" | "edit_field";
  targetFarmMode: "new" | "existing";
  existingFarmId?: string;
  editingFieldId?: string;
  farmPayload: FarmWriteRequest;
  fieldDraft: FieldWriteDraft;
}

interface FarmFieldInfoModalProps {
  open: boolean;
  lang: Language;
  existingFarms: FarmPublic[];
  existingFields: FieldDetailPublic[];
  borderDraft: BorderDraftResult | null;
  editingField: FieldDetailPublic | null;
  defaultFarmId?: string | null;
  onClose: () => void;
  onEditBorders?: () => void;
  onSubmit: (payload: FarmFieldFormSubmitPayload) => Promise<void> | void;
}

const KNOWN_SOIL_TYPES: Exclude<SoilType, "unknown">[] = [
  "clay",
  "loamy",
  "silty",
  "sandy",
];
const WATER_AVAIL_OPTIONS: WaterAvailability[] = [
  "abundant",
  "moderate",
  "limited",
  "very_limited",
  "rainfed_only",
];
const WATER_SOURCE_OPTIONS: WaterSource[] = [
  "rainwater",
  "groundwater",
  "well",
  "dam_reservoir",
  "irrigation_network",
  "other",
  "unknown",
];
const IRRIGATION_OPTIONS: IrrigationSystem[] = [
  "rainfed",
  "drip",
  "sprinkler",
  "flood",
  "other",
  "unknown",
];
const SEASON_OPTIONS: Season[] = ["autumn", "winter", "spring", "summer"];

function nextFieldCode(fields: FieldDetailPublic[]): string {
  const nums = fields.map((f) => {
    const m = /F-(\d+)/i.exec(f.field_id);
    return m ? Number(m[1]) : 0;
  });
  return `F-${Math.max(0, ...nums) + 1}`;
}

export function FarmFieldInfoModal({
  open,
  lang,
  existingFarms,
  existingFields,
  borderDraft,
  editingField,
  defaultFarmId,
  onClose,
  onEditBorders,
  onSubmit,
}: FarmFieldInfoModalProps) {
  const dict = GUELMA_WORKSPACE_I18N[lang];
  const t = dict.form;
  const authMode = useAppStore((s) => s.authMode);
  const resolvedTheme = useResolvedTheme();

  const isEditField = Boolean(editingField);

  const [targetFarmMode, setTargetFarmMode] = useState<"new" | "existing">("new");
  const [selectedFarmId, setSelectedFarmId] = useState<string>(
    defaultFarmId || existingFarms[0]?.farm_id || ""
  );
  const [farmName, setFarmName] = useState("");
  const [country, setCountry] = useState("Algeria");
  const [region, setRegion] = useState("Guelma");
  const [commune, setCommune] = useState("Guelma");

  const [fieldId, setFieldId] = useState("F-1");
  const [fieldName, setFieldName] = useState("");
  const [areaHectares, setAreaHectares] = useState("2.4");
  const [elevationM, setElevationM] = useState("");

  const [soilKnown, setSoilKnown] = useState(false);
  const [soilType, setSoilType] = useState<Exclude<SoilType, "unknown">>("loamy");
  const [soilPh, setSoilPh] = useState("");
  const [soilOm, setSoilOm] = useState("");
  const [soilTestDate, setSoilTestDate] = useState("");
  const [usdaModalOpen, setUsdaModalOpen] = useState(false);

  const [waterAvail, setWaterAvail] = useState<WaterAvailability>("moderate");
  const [waterSource, setWaterSource] = useState<WaterSource>("rainwater");
  const [waterSourceOther, setWaterSourceOther] = useState("");
  const [irrigationSystem, setIrrigationSystem] = useState<IrrigationSystem>("rainfed");

  const [cropRows, setCropRows] = useState<CropRowDraft[]>([
    {
      season: "autumn",
      year: 2024,
      planting_month: "11",
      crop_id: "durum_wheat",
      crop_name_raw: "",
      yield_tons_per_hectare: "",
      notes: "",
    },
  ]);

  const [catalogItems, setCatalogItems] = useState<CropItem[]>(FIXTURE_CATALOG_ITEMS);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previousFocusRef.current = document.activeElement as HTMLElement | null;
    return () => {
      previousFocusRef.current?.focus?.();
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !usdaModalOpen && !submitting) {
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open, usdaModalOpen, submitting, onClose]);

  useEffect(() => {
    if (authMode === "none") return;
    let active = true;
    fetchAllCatalogItems(lang)
      .then((res) => {
        if (active && res.items.length > 0) setCatalogItems(res.items);
      })
      .catch(() => {
        /* fallback to FIXTURE_CATALOG_ITEMS */
      });
    return () => {
      active = false;
    };
  }, [lang, authMode]);

  useEffect(() => {
    if (!open) return;
    setFormError(null);

    if (editingField) {
      const parentFarm = existingFarms.find((f) => f.farm_id === editingField.farm_id);
      setTargetFarmMode("existing");
      setSelectedFarmId(editingField.farm_id);
      setFarmName(parentFarm?.farm_name || "");
      setCountry(parentFarm?.country || "Algeria");
      setRegion(parentFarm?.region || "Guelma");
      setCommune(parentFarm?.commune || "Guelma");

      setFieldId(editingField.field_id);
      setFieldName(editingField.field_name);
      setAreaHectares(String(borderDraft?.areaHectares ?? editingField.area_hectares));
      setElevationM(
        editingField.elevation_m !== null && editingField.elevation_m !== undefined
          ? String(editingField.elevation_m)
          : ""
      );

      const hasKnownSoil = editingField.soil.source === "farmer" && editingField.soil.soil_type !== "unknown";
      setSoilKnown(hasKnownSoil || editingField.soil.soil_ph !== null || editingField.soil.organic_matter_percent !== null);
      setSoilType(
        editingField.soil.soil_type !== "unknown" ? editingField.soil.soil_type : "loamy"
      );
      setSoilPh(editingField.soil.soil_ph !== null ? String(editingField.soil.soil_ph) : "");
      setSoilOm(
        editingField.soil.organic_matter_percent !== null
          ? String(editingField.soil.organic_matter_percent)
          : ""
      );
      setSoilTestDate(editingField.soil.soil_test_date || "");

      setWaterAvail(editingField.water.availability);
      setWaterSource(editingField.water.source);
      setWaterSourceOther(editingField.water.source_other || "");
      setIrrigationSystem(editingField.water.irrigation_system);

      if (editingField.crop_history.length > 0) {
        setCropRows(
          editingField.crop_history.map((h) => ({
            season: h.season,
            year: h.year,
            planting_month: h.planting_month ? String(h.planting_month) : "",
            crop_id: h.crop_id || "",
            crop_name_raw: h.crop_name_raw || "",
            yield_tons_per_hectare:
              h.yield_tons_per_hectare !== null && h.yield_tons_per_hectare !== undefined
                ? String(h.yield_tons_per_hectare)
                : "",
            notes: h.notes || "",
          }))
        );
      }
      return;
    }

    // Create new field from drawn border draft
    if (defaultFarmId && existingFarms.some((f) => f.farm_id === defaultFarmId)) {
      setTargetFarmMode("existing");
      setSelectedFarmId(defaultFarmId);
      const fam = existingFarms.find((f) => f.farm_id === defaultFarmId);
      setCommune(fam?.commune || borderDraft?.nearestCommune.name.en || "Guelma");
    } else {
      setTargetFarmMode("new");
      setSelectedFarmId(existingFarms[0]?.farm_id || "");
      setFarmName("");
      setCountry("Algeria");
      setRegion("Guelma");
      setCommune(borderDraft?.nearestCommune.name.en || "Guelma");
    }

    setFieldId(nextFieldCode(existingFields));
    setFieldName(
      borderDraft
        ? `${borderDraft.nearestCommune.name[lang] || borderDraft.nearestCommune.name.en} ${dict.parcelDefaultSuffix}`
        : ""
    );
    setAreaHectares(borderDraft ? borderDraft.areaHectares.toFixed(2) : "2.0");
    // ADR-5: NEVER fabricate non-null elevation_m automatically from DEM
    setElevationM("");
    setSoilKnown(false);
    setSoilType("loamy");
    setSoilPh("");
    setSoilOm("");
    setSoilTestDate("");
    setWaterAvail("moderate");
    setWaterSource("rainwater");
    setWaterSourceOther("");
    setIrrigationSystem("rainfed");
    setCropRows([
      {
        season: "autumn",
        year: 2024,
        planting_month: "11",
        crop_id: "durum_wheat",
        crop_name_raw: "",
        yield_tons_per_hectare: "",
        notes: "",
      },
    ]);
  }, [
    open,
    editingField,
    borderDraft,
    defaultFarmId,
    existingFarms,
    existingFields,
    lang,
    dict.parcelDefaultSuffix,
  ]);

  if (!open) return null;

  const activeLat = borderDraft?.centroid.latitude ?? editingField?.location.latitude ?? 36.4667;
  const activeLon = borderDraft?.centroid.longitude ?? editingField?.location.longitude ?? 7.4333;
  const activeBoundary = borderDraft?.boundary ?? editingField?.location.boundary ?? null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const existingFarm = existingFarms.find((f) => f.farm_id === selectedFarmId);
    if (!isEditField && targetFarmMode === "new" && !farmName.trim()) {
      setFormError(t.errFarmName);
      return;
    }
    if (!fieldId.trim()) {
      setFormError(t.errFieldId);
      return;
    }
    if (!fieldName.trim()) {
      setFormError(t.errFieldName);
      return;
    }

    const parsedArea = Number(areaHectares);
    if (!Number.isFinite(parsedArea) || parsedArea <= 0 || parsedArea > 10000) {
      setFormError(t.errAreaPositive);
      return;
    }

    if (waterSource === "other" && !waterSourceOther.trim()) {
      setFormError(t.errWaterOtherRequired);
      return;
    }

    const sanitizedHistory: FieldWriteDraft["crop_history"] = [];
    for (let i = 0; i < cropRows.length; i++) {
      const r = cropRows[i];
      if (!r.crop_id.trim() && !r.crop_name_raw.trim()) {
        setFormError(t.errCropMissing(i + 1));
        return;
      }
      const pMonth = r.planting_month.trim() === "" ? null : Number(r.planting_month);
      const check = validateSeasonMonthConsistency(r.season, pMonth, activeLat, lang);
      if (!check.valid) {
        setFormError(check.error ?? "");
        return;
      }
      sanitizedHistory.push({
        season: r.season,
        year: Number(r.year) || 2024,
        planting_month: pMonth,
        crop_id: r.crop_id.trim() || null,
        crop_name_raw: r.crop_name_raw.trim() || null,
        yield_tons_per_hectare:
          r.yield_tons_per_hectare.trim() === "" ? null : Number(r.yield_tons_per_hectare),
        notes: r.notes.trim() || null,
      });
    }

    const farmPayload: FarmWriteRequest =
      targetFarmMode === "existing" && existingFarm
        ? {
            farm_name: existingFarm.farm_name,
            country: existingFarm.country,
            region: existingFarm.region,
            commune: existingFarm.commune ?? commune,
          }
        : {
            farm_name: farmName.trim(),
            country: country.trim() || "Algeria",
            region: region.trim() || "Guelma",
            commune: commune || null,
          };

    const fieldDraft: FieldWriteDraft = {
      field_id: fieldId.trim(),
      field_name: fieldName.trim(),
      is_unverified_demo_parcel: false,
      location: {
        latitude: Number(activeLat.toFixed(6)),
        longitude: Number(activeLon.toFixed(6)),
        boundary: activeBoundary,
      },
      area_hectares: Number(parsedArea.toFixed(2)),
      elevation_m: elevationM.trim() === "" ? "" : Number(elevationM),
      soil: soilKnown
        ? {
            soil_type: soilType,
            soil_ph: soilPh.trim() === "" ? "" : Number(soilPh),
            organic_matter_percent: soilOm.trim() === "" ? "" : Number(soilOm),
            soil_test_date: soilTestDate.trim() || "",
          }
        : {
            soil_type: "unknown",
            soil_ph: "",
            organic_matter_percent: "",
            soil_test_date: "",
          },
      water: {
        availability: waterAvail,
        source: waterSource,
        source_other: waterSource === "other" ? waterSourceOther.trim() : "",
        irrigation_system: irrigationSystem,
      },
      crop_history: sanitizedHistory,
    };

    setSubmitting(true);
    try {
      await onSubmit({
        mode: isEditField ? "edit_field" : "create",
        targetFarmMode: isEditField ? "existing" : targetFarmMode,
        existingFarmId:
          targetFarmMode === "existing" || isEditField ? selectedFarmId : undefined,
        editingFieldId: editingField?.field_id,
        farmPayload,
        fieldDraft,
      });
    } catch (err) {
      const p = presentApiError(err, lang);
      setFormError(`${p.title}: ${p.guidance}`);
    } finally {
      setSubmitting(false);
    }
  };

  const inputClassName =
    "mt-1 min-h-10 w-full rounded-xl border border-[#111813]/15 bg-white/90 px-3 py-2 text-base text-[#111813] placeholder:text-[#6B7A6F] transition-[border-color,background-color] focus:border-[#15803D] focus:outline-none dark:border-white/12 dark:bg-[#141A16] dark:text-[#F5F7F5] dark:placeholder:text-[#78847B] dark:focus:border-[#86EFAC]/60 sm:text-xs";
  const compactInputClassName =
    "mt-1 min-h-10 w-full rounded-xl border border-[#111813]/15 bg-white/90 px-2.5 py-1.5 text-base text-[#111813] placeholder:text-[#6B7A6F] transition-[border-color,background-color] focus:border-[#15803D] focus:outline-none dark:border-white/12 dark:bg-[#141A16] dark:text-[#F5F7F5] dark:placeholder:text-[#78847B] dark:focus:border-[#86EFAC]/60 sm:text-xs";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 overscroll-contain"
      role="dialog"
      aria-modal="true"
      aria-label={isEditField ? t.editFieldTitle : t.createTitle}
      data-testid="farm-field-info-modal"
    >
      <button
        type="button"
        onClick={onClose}
        aria-label={t.cancelBtn}
        className="fixed inset-0 bg-[#0F1711]/35 backdrop-blur-sm dark:bg-black/65"
      />
      <div className="fs-hud-glass relative z-10 flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-3xl text-[#111813] shadow-[0_32px_90px_rgba(17,24,19,0.22)] dark:text-[#F5F7F5] dark:shadow-[0_32px_90px_rgba(0,0,0,0.65)]">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 border-b border-[#111813]/10 bg-[#111813]/[0.03] px-5 py-4 dark:border-white/10 dark:bg-white/[0.04]">
          <div className="flex items-center gap-3">
            <FieldPolygonThumbnail
              boundary={activeBoundary}
              latitude={activeLat}
              longitude={activeLon}
              areaHectares={Number(areaHectares) || 0}
              active
              className="h-14 w-24 shrink-0"
            />
            <div>
              <h2 className="font-heading text-base font-semibold text-[#111813] dark:text-[#F5F7F5]">
                {isEditField ? t.editFieldTitle : t.createTitle}
              </h2>
              <p className="mt-0.5 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">{t.subtitle}</p>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] font-mono tabular-nums text-[#243227] dark:text-[#D1DBD3]">
                <span className="inline-flex items-center gap-1" dir="ltr">
                  <MapPin size={12} className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
                  {activeLat.toFixed(4)}° N, {activeLon.toFixed(4)}° E
                </span>
                {onEditBorders ? (
                  <button
                    type="button"
                    onClick={onEditBorders}
                    className="min-h-8 font-sans font-semibold text-[#15803D] underline decoration-[#15803D]/50 underline-offset-4 transition-colors hover:text-[#0B3D2E] dark:text-[#86EFAC] dark:decoration-[#86EFAC]/50 dark:hover:text-white"
                  >
                    {dict.editBordersBtn}
                  </button>
                ) : null}
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t.cancelBtn}
            className="fs-liquid-pill flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[#4A5A4E] hover:text-[#111813] active:not-disabled:scale-[0.96] dark:text-[#9CA89E] dark:hover:text-white"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        {/* Scrollable Body */}
        <form onSubmit={handleSubmit} className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
          {formError ? (
            <div
              className="flex items-start gap-2 rounded-xl border border-red-600/25 bg-red-50 px-3.5 py-2.5 text-xs font-medium text-red-800 dark:border-red-400/30 dark:bg-red-500/15 dark:text-red-200"
              role="alert"
            >
              <Warning size={16} weight="fill" className="mt-0.5 shrink-0 text-red-600 dark:text-red-300" aria-hidden="true" />
              <span>{formError}</span>
            </div>
          ) : null}

          {/* 1. Farm Section */}
          {!isEditField ? (
            <section className="fs-liquid-well rounded-2xl p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-[#15803D] dark:text-[#86EFAC]">
                  {t.farmSection}
                </h3>
                {existingFarms.length > 0 ? (
                  <div className="inline-flex rounded-full border border-[#111813]/12 bg-[#111813]/[0.05] p-0.5 text-xs font-semibold dark:border-white/12 dark:bg-black/30">
                    <button
                      type="button"
                      onClick={() => setTargetFarmMode("new")}
                      className={`min-h-8 rounded-full px-3 py-1 transition-[background-color,color] ${
                        targetFarmMode === "new"
                          ? "bg-[#0B3D2E] text-white shadow-xs dark:bg-[#FFFFFF] dark:text-[#111713]"
                          : "text-[#4A5A4E] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:text-white"
                      }`}
                    >
                      {t.targetModeNew}
                    </button>
                    <button
                      type="button"
                      onClick={() => setTargetFarmMode("existing")}
                      className={`min-h-8 rounded-full px-3 py-1 transition-[background-color,color] ${
                        targetFarmMode === "existing"
                          ? "bg-[#0B3D2E] text-white shadow-xs dark:bg-[#FFFFFF] dark:text-[#111713]"
                          : "text-[#4A5A4E] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:text-white"
                      }`}
                    >
                      {t.targetModeExisting}
                    </button>
                  </div>
                ) : null}
              </div>

              {targetFarmMode === "existing" && existingFarms.length > 0 ? (
                <div className="mt-3">
                  <label className="block text-xs font-semibold text-[#243227] dark:text-[#D1DBD3]">
                    {t.chooseFarmLabel}
                  </label>
                  <select
                    value={selectedFarmId}
                    onChange={(e) => setSelectedFarmId(e.target.value)}
                    className={inputClassName}
                  >
                    {existingFarms.map((fm) => (
                      <option key={fm.farm_id} value={fm.farm_id}>
                        {localizeFarmName(fm.farm_name, lang)} ({localizeCommuneName(fm.commune || fm.region, lang)})
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <div className="sm:col-span-2">
                    <label className="block text-xs font-semibold text-[#243227] dark:text-[#D1DBD3]">
                      {t.farmNameLabel} *
                    </label>
                    <input
                      type="text"
                      required
                      maxLength={120}
                      value={farmName}
                      onChange={(e) => setFarmName(e.target.value)}
                      placeholder={t.farmNamePlaceholder}
                      data-testid="input-farm-name"
                      className={inputClassName}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-[#243227] dark:text-[#D1DBD3]">
                      {t.communeLabel}
                    </label>
                    <select
                      value={commune}
                      onChange={(e) => setCommune(e.target.value)}
                      data-testid="select-farm-commune"
                      className={inputClassName}
                    >
                      {GUELMA_COMMUNES.map((c) => (
                        <option key={c.id} value={c.name.en}>
                          {c.name[lang] || c.name.en} ({c.daira[lang] || c.daira.en})
                        </option>
                      ))}
                    </select>
                    <p className="mt-1 text-[11px] font-medium text-[#15803D] dark:text-[#86EFAC]">
                      {t.communeAutoHint}
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs font-semibold text-[#243227] dark:text-[#D1DBD3]">
                        {t.regionLabel}
                      </label>
                      <input
                        type="text"
                        value={region}
                        onChange={(e) => setRegion(e.target.value)}
                        className="mt-1 min-h-10 w-full rounded-xl border border-[#111813]/12 bg-[#111813]/[0.03] px-3 py-2 text-base text-[#243227] transition-[border-color] focus:border-[#15803D]/60 focus:outline-none dark:border-white/10 dark:bg-white/[0.04] dark:text-[#D1DBD3] dark:focus:border-[#86EFAC]/60 sm:text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-[#243227] dark:text-[#D1DBD3]">
                        {t.countryLabel}
                      </label>
                      <input
                        type="text"
                        value={country}
                        onChange={(e) => setCountry(e.target.value)}
                        className="mt-1 min-h-10 w-full rounded-xl border border-[#111813]/12 bg-[#111813]/[0.03] px-3 py-2 text-base text-[#243227] transition-[border-color] focus:border-[#15803D]/60 focus:outline-none dark:border-white/10 dark:bg-white/[0.04] dark:text-[#D1DBD3] dark:focus:border-[#86EFAC]/60 sm:text-xs"
                      />
                    </div>
                  </div>
                </div>
              )}
            </section>
          ) : null}

          {/* 2. Field Section */}
          <section className="fs-liquid-well rounded-2xl p-4">
            <div className="flex items-center gap-2">
              <Ruler size={15} className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
              <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-[#15803D] dark:text-[#86EFAC]">
                {t.fieldSection}
              </h3>
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <div>
                <label className="block text-xs font-semibold text-[#243227] dark:text-[#D1DBD3]">
                  {t.fieldNameLabel} *
                </label>
                <input
                  type="text"
                  required
                  maxLength={120}
                  value={fieldName}
                  onChange={(e) => setFieldName(e.target.value)}
                  placeholder={t.fieldNamePlaceholder}
                  data-testid="input-field-name"
                  className={inputClassName}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-[#243227] dark:text-[#D1DBD3]">
                  {t.fieldIdLabel} *
                </label>
                <input
                  type="text"
                  required
                  disabled={isEditField}
                  maxLength={64}
                  value={fieldId}
                  onChange={(e) => setFieldId(e.target.value)}
                  data-testid="input-field-id"
                  className={`${inputClassName} font-mono disabled:bg-[#111813]/[0.04] disabled:text-[#6B7A6F] dark:disabled:bg-white/[0.04] dark:disabled:text-[#78847B]`}
                />
              </div>
              <div>
                <div className="flex items-center justify-between gap-2">
                  <label className="text-xs font-semibold text-[#243227] dark:text-[#D1DBD3]">
                    {t.areaLabel} *
                  </label>
                  <span className="text-[11px] font-semibold text-[#15803D] dark:text-[#86EFAC]">
                    {t.areaAutoTag}
                  </span>
                </div>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max="10000"
                  required
                  value={areaHectares}
                  onChange={(e) => setAreaHectares(e.target.value)}
                  data-testid="input-area-hectares"
                  className={`${inputClassName} font-mono tabular-nums`}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-[#243227] dark:text-[#D1DBD3]">
                  {t.elevLabel}
                </label>
                <input
                  type="number"
                  step="1"
                  min="-500"
                  max="9000"
                  value={elevationM}
                  onChange={(e) => setElevationM(e.target.value)}
                  placeholder={t.elevOptionalPlaceholder}
                  data-testid="input-elevation-m"
                  className={`${inputClassName} font-mono tabular-nums`}
                />
                <p className="mt-1 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">{t.elevAdrNote}</p>
              </div>
            </div>
          </section>

          {/* 3. Soil Section (ADR-5) */}
          <section className="fs-liquid-well rounded-2xl p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Leaf size={15} className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
                <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-[#15803D] dark:text-[#86EFAC]">
                  {t.soilSection}
                </h3>
              </div>
              <div className="inline-flex rounded-full border border-[#111813]/12 bg-[#111813]/[0.05] p-0.5 text-xs font-semibold dark:border-white/12 dark:bg-black/30">
                <button
                  type="button"
                  onClick={() => setSoilKnown(false)}
                  data-testid="soil-mode-unknown"
                  className={`min-h-8 rounded-full px-3 py-1 transition-[background-color,color] ${
                    !soilKnown
                      ? "bg-[#0B3D2E] text-white shadow-xs dark:bg-[#FFFFFF] dark:text-[#111713]"
                      : "text-[#4A5A4E] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:text-white"
                  }`}
                >
                  {t.soilModeUnknown}
                </button>
                <button
                  type="button"
                  onClick={() => setSoilKnown(true)}
                  data-testid="soil-mode-known"
                  className={`min-h-8 rounded-full px-3 py-1 transition-[background-color,color] ${
                    soilKnown
                      ? "bg-[#0B3D2E] text-white shadow-xs dark:bg-[#FFFFFF] dark:text-[#111713]"
                      : "text-[#4A5A4E] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:text-white"
                  }`}
                >
                  {t.soilModeKnown}
                </button>
              </div>
            </div>

            {soilKnown ? (
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <label className="text-xs font-semibold text-[#243227] dark:text-[#D1DBD3]">
                      {t.soilTypeLabel}
                    </label>
                    <button
                      type="button"
                      onClick={() => setUsdaModalOpen(true)}
                      className="inline-flex min-h-7 items-center gap-1 rounded-full bg-[#15803D]/10 px-2.5 text-[11px] font-semibold text-[#15803D] ring-1 ring-[#15803D]/25 transition-[background-color,color] hover:bg-[#15803D]/20 hover:text-[#0B3D2E] dark:bg-white/[0.06] dark:text-[#86EFAC] dark:ring-white/12 dark:hover:bg-white/[0.12] dark:hover:text-white"
                    >
                      <Calculator size={13} aria-hidden="true" />
                      <span>{t.usdaCalcBtn}</span>
                    </button>
                  </div>
                  <select
                    value={soilType}
                    onChange={(e) => setSoilType(e.target.value as Exclude<SoilType, "unknown">)}
                    className={inputClassName}
                  >
                    {KNOWN_SOIL_TYPES.map((st) => (
                      <option key={st} value={st}>
                        {SOIL_TYPE_LABELS[lang][st]}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#243227] dark:text-[#D1DBD3]">
                    {t.soilPhLabel}
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="3"
                    max="11"
                    value={soilPh}
                    onChange={(e) => setSoilPh(e.target.value)}
                    placeholder="7.3"
                    className={`${inputClassName} font-mono tabular-nums`}
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#243227] dark:text-[#D1DBD3]">
                    {t.soilOmLabel}
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="100"
                    value={soilOm}
                    onChange={(e) => setSoilOm(e.target.value)}
                    placeholder="1.4"
                    className={`${inputClassName} font-mono tabular-nums`}
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#243227] dark:text-[#D1DBD3]">
                    {t.soilDateLabel}
                  </label>
                  <input
                    type="date"
                    value={soilTestDate}
                    onChange={(e) => setSoilTestDate(e.target.value)}
                    className={`${inputClassName} font-mono tabular-nums [color-scheme:light] dark:[color-scheme:dark]`}
                  />
                </div>
              </div>
            ) : null}
          </section>

          {/* 4. Water & Irrigation Section */}
          <section className="fs-liquid-well rounded-2xl p-4">
            <div className="flex items-center gap-2">
              <Drop size={15} className="text-[#0284C7] dark:text-[#38BDF8]" aria-hidden="true" />
              <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-[#15803D] dark:text-[#86EFAC]">
                {t.waterSection}
              </h3>
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <div>
                <label className="block text-xs font-semibold text-[#243227] dark:text-[#D1DBD3]">
                  {t.waterAvailLabel}
                </label>
                <select
                  value={waterAvail}
                  onChange={(e) => setWaterAvail(e.target.value as WaterAvailability)}
                  className={inputClassName}
                >
                  {WATER_AVAIL_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {WATER_AVAILABILITY_LABELS[lang][opt]}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-[#243227] dark:text-[#D1DBD3]">
                  {t.waterSourceLabel}
                </label>
                <select
                  value={waterSource}
                  onChange={(e) => setWaterSource(e.target.value as WaterSource)}
                  className={inputClassName}
                >
                  {WATER_SOURCE_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {WATER_SOURCE_LABELS[lang][opt]}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-[#243227] dark:text-[#D1DBD3]">
                  {t.irrigationLabel}
                </label>
                <select
                  value={irrigationSystem}
                  onChange={(e) => setIrrigationSystem(e.target.value as IrrigationSystem)}
                  className={inputClassName}
                >
                  {IRRIGATION_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {IRRIGATION_SYSTEM_LABELS[lang][opt]}
                    </option>
                  ))}
                </select>
              </div>
              {waterSource === "other" ? (
                <div className="sm:col-span-3">
                  <label className="block text-xs font-semibold text-[#243227] dark:text-[#D1DBD3]">
                    {t.waterSourceOtherLabel} *
                  </label>
                  <input
                    type="text"
                    required
                    maxLength={200}
                    value={waterSourceOther}
                    onChange={(e) => setWaterSourceOther(e.target.value)}
                    className={inputClassName}
                  />
                </div>
              ) : null}
            </div>
          </section>

          {/* 5. Crop History Section (1..30) */}
          <section className="fs-liquid-well rounded-2xl p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-[#15803D] dark:text-[#86EFAC]">
                  {t.historySection}
                </h3>
                <p className="mt-0.5 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">{t.historySubtitle}</p>
              </div>
              <button
                type="button"
                disabled={cropRows.length >= 30}
                onClick={() =>
                  setCropRows((prev) => [
                    ...prev,
                    {
                      season: "spring",
                      year: 2023,
                      planting_month: "3",
                      crop_id: "chickpea",
                      crop_name_raw: "",
                      yield_tons_per_hectare: "",
                      notes: "",
                    },
                  ])
                }
                className="fs-liquid-pill inline-flex min-h-9 items-center gap-1.5 rounded-full px-3 text-xs font-semibold text-[#111813] dark:text-[#F5F7F5] disabled:opacity-40"
              >
                <Plus size={13} aria-hidden="true" />
                <span>{t.addHistoryBtn}</span>
              </button>
            </div>

            <div className="mt-3 space-y-2.5">
              {cropRows.map((row, idx) => {
                const pMonth = row.planting_month === "" ? null : Number(row.planting_month);
                const monthCheck = validateSeasonMonthConsistency(row.season, pMonth, activeLat);

                return (
                  <div
                    key={idx}
                    className="rounded-2xl border border-[#111813]/10 bg-[#111813]/[0.03] p-3.5 dark:border-white/10 dark:bg-black/25"
                  >
                    <div className="grid gap-2.5 sm:grid-cols-4">
                      <div>
                        <label className="block text-[11px] font-semibold text-[#4A5A4E] dark:text-[#9CA89E]">
                          {t.seasonLabel}
                        </label>
                        <select
                          value={row.season}
                          onChange={(e) => {
                            const s = e.target.value as Season;
                            setCropRows((prev) =>
                              prev.map((it, i) => (i === idx ? { ...it, season: s } : it))
                            );
                          }}
                          className={compactInputClassName}
                        >
                          {SEASON_OPTIONS.map((s) => (
                            <option key={s} value={s}>
                              {SEASON_LABELS[lang][s]}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-[11px] font-semibold text-[#4A5A4E] dark:text-[#9CA89E]">
                          {t.yearLabel}
                        </label>
                        <input
                          type="number"
                          min="1980"
                          max="2100"
                          value={row.year}
                          onChange={(e) => {
                            const y = Number(e.target.value);
                            setCropRows((prev) =>
                              prev.map((it, i) => (i === idx ? { ...it, year: y } : it))
                            );
                          }}
                          className={`${compactInputClassName} font-mono tabular-nums`}
                        />
                      </div>

                      <div>
                        <label className="block text-[11px] font-semibold text-[#4A5A4E] dark:text-[#9CA89E]">
                          {t.monthLabel}
                        </label>
                        <select
                          value={row.planting_month}
                          onChange={(e) => {
                            const m = e.target.value;
                            setCropRows((prev) =>
                              prev.map((it, i) =>
                                i === idx ? { ...it, planting_month: m } : it
                              )
                            );
                          }}
                          className={`${compactInputClassName} font-mono tabular-nums ${
                            !monthCheck.valid
                              ? "border-red-600/70 text-red-700 dark:border-red-400/70 dark:text-red-300"
                              : "border-[#111813]/15 dark:border-white/12"
                          }`}
                        >
                          <option value="">{t.monthAutoOption}</option>
                          {Array.from({ length: 12 }, (_, m) => m + 1).map((m) => (
                            <option key={m} value={String(m)}>
                              {String(m).padStart(2, "0")}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-[11px] font-semibold text-[#4A5A4E] dark:text-[#9CA89E]">
                          {t.yieldLabel}
                        </label>
                        <input
                          type="number"
                          step="0.1"
                          min="0"
                          max="200"
                          value={row.yield_tons_per_hectare}
                          onChange={(e) => {
                            const v = e.target.value;
                            setCropRows((prev) =>
                              prev.map((it, i) =>
                                i === idx ? { ...it, yield_tons_per_hectare: v } : it
                              )
                            );
                          }}
                          placeholder="3.2"
                          className={`${compactInputClassName} font-mono tabular-nums`}
                        />
                      </div>

                      <div className="sm:col-span-2">
                        <label className="block text-[11px] font-semibold text-[#4A5A4E] dark:text-[#9CA89E]">
                          {t.catalogCropLabel}
                        </label>
                        <select
                          value={row.crop_id}
                          onChange={(e) => {
                            const cid = e.target.value;
                            setCropRows((prev) =>
                              prev.map((it, i) => (i === idx ? { ...it, crop_id: cid } : it))
                            );
                          }}
                          className={compactInputClassName}
                        >
                          <option value="">{dict.customCropOption}</option>
                          {catalogItems.map((c) => (
                            <option key={c.crop_id} value={c.crop_id}>
                              {c.names?.[lang] || c.display_name}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="sm:col-span-2">
                        <label className="block text-[11px] font-semibold text-[#4A5A4E] dark:text-[#9CA89E]">
                          {t.customCropLabel}
                        </label>
                        <input
                          type="text"
                          maxLength={120}
                          value={row.crop_name_raw}
                          onChange={(e) => {
                            const raw = e.target.value;
                            setCropRows((prev) =>
                              prev.map((it, i) =>
                                i === idx ? { ...it, crop_name_raw: raw } : it
                              )
                            );
                          }}
                          placeholder={t.customCropPlaceholder}
                          className={compactInputClassName}
                        />
                      </div>
                    </div>

                    {!monthCheck.valid ? (
                      <p className="mt-1.5 text-[11px] font-semibold text-red-700 dark:text-red-300">
                        {monthCheck.error}
                      </p>
                    ) : null}

                    <div className="mt-2.5 flex items-center gap-2">
                      <input
                        type="text"
                        maxLength={500}
                        value={row.notes}
                        onChange={(e) => {
                          const notes = e.target.value;
                          setCropRows((prev) =>
                            prev.map((it, i) => (i === idx ? { ...it, notes } : it))
                          );
                        }}
                        placeholder={`${t.notesLabel} (${t.notesPrivateTag})`}
                        className="min-h-9 flex-1 rounded-xl border border-[#111813]/15 bg-white/90 px-3 py-1 text-base text-[#111813] placeholder:text-[#6B7A6F] transition-[border-color] focus:border-[#15803D] focus:outline-none dark:border-white/10 dark:bg-[#141A16] dark:text-[#D1DBD3] dark:placeholder:text-[#78847B] dark:focus:border-[#86EFAC]/60 sm:text-[11px]"
                      />
                      {cropRows.length > 1 ? (
                        <button
                          type="button"
                          onClick={() =>
                            setCropRows((prev) => prev.filter((_, i) => i !== idx))
                          }
                          aria-label={t.removeRowLabel}
                          className="flex min-h-9 min-w-9 items-center justify-center rounded-xl text-red-600 transition-[background-color,color] hover:bg-red-500/12 hover:text-red-800 dark:text-red-300 dark:hover:bg-red-500/15 dark:hover:text-red-200"
                        >
                          <Trash size={14} aria-hidden="true" />
                        </button>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Footer Submit Controls */}
          <div className="flex flex-wrap items-center justify-end gap-2.5 border-t border-[#111813]/10 pt-3.5 dark:border-white/10">
            <button
              type="button"
              onClick={onClose}
              className="fs-liquid-pill min-h-10 rounded-full px-4 text-xs font-semibold text-[#243227] hover:text-[#111813] dark:text-[#D1DBD3] dark:hover:text-white active:not-disabled:scale-[0.96]"
            >
              {t.cancelBtn}
            </button>
            <button
              type="submit"
              disabled={submitting}
              data-testid="submit-farm-field-form"
              className="fs-cta-primary inline-flex min-h-10 items-center gap-1.5 rounded-full ps-4 pe-5 text-xs font-semibold active:not-disabled:scale-[0.96] disabled:opacity-50"
            >
              <Check size={15} weight="bold" aria-hidden="true" />
              <span>{isEditField ? t.updateFieldBtn : t.saveFarmFieldBtn}</span>
            </button>
          </div>
        </form>
      </div>

      <UsdaTextureModal
        open={usdaModalOpen}
        lang={lang}
        theme={resolvedTheme}
        onClose={() => setUsdaModalOpen(false)}
        onApply={(derived) => {
          setSoilType(derived);
          setSoilKnown(true);
          setUsdaModalOpen(false);
        }}
      />
    </div>
  );
}

