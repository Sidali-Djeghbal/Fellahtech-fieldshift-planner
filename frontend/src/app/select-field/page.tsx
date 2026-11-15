"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle,
  FloppyDisk,
  MapPin,
  PencilSimple,
  Plus,
  Trash,
  Warning,
} from "@phosphor-icons/react";
import { useResolvedTheme } from "@/app/providers";
import { useWorkspaceShell } from "@/components/guelma/WorkspaceShellContext";
import { OrbitalFieldMap } from "@/components/map/OrbitalFieldMap";
import { ApiErrorCard, WarningsBanner } from "@/components/shared/ProvenanceBanners";
import {
  createFarm,
  createField,
  getDemoLocationBoundary,
  getField,
  listFarms,
  listFields,
  replaceField,
} from "@/lib/api/endpoints";
import {
  GUELMA_FALLBACK_BOUNDARY,
  GUELMA_PARCEL_PRESETS,
  SETIF_OUTSIDE_TEST_COORD,
  computePolygonAreaHectares,
  computePolygonCentroid,
  isInsideGuelmaBoundary,
  ringToGeoJsonPolygon,
} from "@/lib/geo/guelma";
import { UI_DICT } from "@/lib/i18n";
import type { FieldWriteDraft } from "@/lib/schemas";
import { useAppStore } from "@/store/useAppStore";

export default function SelectFieldPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const resolvedTheme = useResolvedTheme();
  const { openAuthModal } = useWorkspaceShell();
  const {
    lang,
    authMode,
    activeFarmId,
    activeFieldId,
    setActiveFarmId,
    setActiveFieldId,
  } = useAppStore();

  const glassInputClass =
    "w-full rounded-xl border border-[#111813]/15 bg-[#111813]/[0.03] px-3 py-2 text-xs text-[#111813] placeholder:text-[#6B7A6F] focus:border-[#15803D] focus:outline-none focus:ring-1 focus:ring-[#15803D] dark:border-white/15 dark:bg-white/[0.06] dark:text-[#F5F7F5] dark:placeholder:text-[#6E7B71] dark:focus:border-[#22C55E] dark:focus:ring-[#22C55E]";

  const t = UI_DICT[lang].selectField;
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

  const boundaryQuery = useQuery({
    queryKey: ["demo", "boundary", 1],
    queryFn: () => getDemoLocationBoundary(1),
  });

  const boundary = boundaryQuery.data ?? GUELMA_FALLBACK_BOUNDARY;

  const [newFarmName, setNewFarmName] = useState("");
  const [drawMode, setDrawMode] = useState(false);
  const [parcelRing, setParcelRing] = useState<[number, number][]>([]);
  const [fieldId, setFieldId] = useState("F1");
  const [fieldName, setFieldName] = useState("Guelma Team Demo Parcel (Unstudied)");
  const [latitude, setLatitude] = useState(36.52);
  const [longitude, setLongitude] = useState(7.52);
  const [areaHectares, setAreaHectares] = useState(12.5);
  const [elevationInput, setElevationInput] = useState<string>("");
  const [isUnverifiedDemo, setIsUnverifiedDemo] = useState(true);
  const [editingExisting, setEditingExisting] = useState(true);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);

  const selectedFieldDetailQuery = useQuery({
    queryKey: ["field-detail", resolvedFarmId, activeFieldId],
    queryFn: () => getField(resolvedFarmId!, activeFieldId!),
    enabled: hasSession && Boolean(resolvedFarmId) && Boolean(activeFieldId),
  });

  useEffect(() => {
    const f = selectedFieldDetailQuery.data;
    if (!f) return;
    setFieldId(f.field_id);
    setFieldName(f.field_name);
    setLatitude(f.location.latitude);
    setLongitude(f.location.longitude);
    setAreaHectares(f.area_hectares);
    setElevationInput(f.elevation_m !== null ? String(f.elevation_m) : "");
    setIsUnverifiedDemo(f.is_unverified_demo_parcel);
    setEditingExisting(true);

    const geom = f.location.boundary as { type?: string; coordinates?: number[][][] } | null;
    if (geom?.type === "Polygon" && Array.isArray(geom.coordinates?.[0])) {
      setParcelRing(geom.coordinates[0].map((c) => [c[0], c[1]] as [number, number]));
    } else {
      setParcelRing([]);
    }
  }, [selectedFieldDetailQuery.data]);

  const insideGuelma = isInsideGuelmaBoundary(
    latitude,
    longitude,
    boundary,
    parcelRing.length >= 3 ? parcelRing : null
  );

  function handleAddVertex(coord: [number, number]) {
    setParcelRing((prev) => {
      const next = [...prev, coord];
      if (next.length >= 3) {
        const calcArea = computePolygonAreaHectares(next);
        const calcCenter = computePolygonCentroid(next);
        setAreaHectares(calcArea);
        if (calcCenter) {
          setLatitude(calcCenter.latitude);
          setLongitude(calcCenter.longitude);
        }
      } else {
        setLatitude(coord[1]);
        setLongitude(coord[0]);
      }
      return next;
    });
  }

  function handleLoadPreset(presetId: string) {
    const preset = GUELMA_PARCEL_PRESETS.find((p) => p.id === presetId);
    if (!preset) return;
    setFieldId(preset.id.toUpperCase());
    setFieldName(preset.zoneName[lang]);
    setParcelRing(preset.ring);
    setLongitude(preset.center[0]);
    setLatitude(preset.center[1]);
    setAreaHectares(preset.areaHectares);
    setElevationInput(""); // ADR-5: NEVER fabricate elevation_m from DEM
    setIsUnverifiedDemo(false);
    setEditingExisting(
      Boolean(fieldsQuery.data?.items.some((item) => item.field_id === preset.id.toUpperCase()))
    );
    setSaveError(null);
  }

  function handleLoadOutsideTest() {
    setFieldId("SETIF_TEST");
    setFieldName(SETIF_OUTSIDE_TEST_COORD.label);
    setParcelRing([]);
    setLatitude(SETIF_OUTSIDE_TEST_COORD.latitude);
    setLongitude(SETIF_OUTSIDE_TEST_COORD.longitude);
    setAreaHectares(18.0);
    setElevationInput("");
    setIsUnverifiedDemo(false);
    setEditingExisting(false);
    setSaveError(null);
  }

  async function handleCreateFarm(e: React.FormEvent) {
    e.preventDefault();
    if (!newFarmName.trim()) return;
    setSaveError(null);
    try {
      const created = await createFarm({
        farm_name: newFarmName.trim(),
        country: "Algeria",
        region: "Guelma",
        commune: "Guelma",
      });
      setNewFarmName("");
      setActiveFarmId(created.farm_id);
      await queryClient.invalidateQueries({ queryKey: ["farms"] });
    } catch (err) {
      setSaveError(err);
    }
  }

  async function handleSaveAndContinue(e: React.FormEvent) {
    e.preventDefault();
    if (!resolvedFarmId) return;
    setSaving(true);
    setSaveError(null);

    try {
      const existingDetail = selectedFieldDetailQuery.data;
      const draft: FieldWriteDraft = {
        field_id: fieldId.trim(),
        field_name: fieldName.trim(),
        is_unverified_demo_parcel: isUnverifiedDemo,
        location: {
          latitude: Number(latitude),
          longitude: Number(longitude),
          boundary: ringToGeoJsonPolygon(parcelRing),
        },
        area_hectares: Number(areaHectares),
        elevation_m: elevationInput.trim() === "" ? null : Number(elevationInput),
        soil: existingDetail && existingDetail.field_id === fieldId.trim()
          ? {
              soil_type: existingDetail.soil.soil_type,
              soil_ph: existingDetail.soil.soil_ph,
              organic_matter_percent: existingDetail.soil.organic_matter_percent,
              soil_test_date: existingDetail.soil.soil_test_date,
            }
          : {
              soil_type: "unknown",
              soil_ph: null,
              organic_matter_percent: null,
              soil_test_date: null,
            },
        water: existingDetail && existingDetail.field_id === fieldId.trim()
          ? existingDetail.water
          : {
              availability: "moderate",
              source: "well",
              source_other: null,
              irrigation_system: "drip",
            },
        crop_history:
          existingDetail &&
          existingDetail.field_id === fieldId.trim() &&
          existingDetail.crop_history.length > 0
            ? existingDetail.crop_history.map((ch) => ({
                season: ch.season,
                year: ch.year,
                planting_month: ch.planting_month ?? null,
                crop_id: ch.crop_id ?? null,
                crop_name_raw: ch.crop_name_raw ?? null,
                yield_tons_per_hectare: ch.yield_tons_per_hectare ?? null,
                notes: ch.notes ?? null,
              }))
            : [
                {
                  season: "autumn",
                  year: 2025,
                  planting_month: 11,
                  crop_id: "durum_wheat",
                  crop_name_raw: "Durum Wheat",
                  yield_tons_per_hectare: null,
                  notes: null,
                },
              ],
      };

      const existsOnFarm = fieldsQuery.data?.items.some(
        (item) => item.field_id === draft.field_id
      );

      if (existsOnFarm && editingExisting) {
        await replaceField(resolvedFarmId, draft.field_id, draft);
      } else {
        await createField(resolvedFarmId, draft);
      }

      setActiveFarmId(resolvedFarmId);
      setActiveFieldId(draft.field_id);
      await queryClient.invalidateQueries({ queryKey: ["fields", resolvedFarmId] });
      await queryClient.invalidateQueries({ queryKey: ["farms"] });
      router.push("/farm-profile");
    } catch (err) {
      setSaveError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fs-view-enter space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-semibold tracking-tight text-[#111813] dark:text-[#F5F7F5]">
            {t.title}
          </h1>
          <p className="mt-1 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">{t.subtitle}</p>
        </div>
        <div
          data-testid="boundary-status-pill"
          className={`inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-xs font-semibold ${
            insideGuelma
              ? "border-[#15803D]/25 bg-[#15803D]/10 text-[#15803D] dark:border-[#22C55E]/30 dark:bg-[#22C55E]/15 dark:text-[#86EFAC]"
              : "border-red-300/80 bg-red-50/90 text-red-700 dark:border-red-500/35 dark:bg-red-500/15 dark:text-red-300"
          }`}
        >
          {insideGuelma ? <CheckCircle size={15} weight="fill" /> : <Warning size={15} weight="fill" />}
          {insideGuelma ? t.insideGuelma : t.outsideGuelma}
        </div>
      </div>

      {selectedFieldDetailQuery.data && (
        <WarningsBanner
          warnings={selectedFieldDetailQuery.data.warnings}
          lang={lang}
          theme={resolvedTheme}
        />
      )}

      {saveError !== null && (
        <ApiErrorCard
          error={saveError}
          lang={lang}
          theme={resolvedTheme}
          onOpenClaimAccount={openAuthModal}
        />
      )}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        {/* Map & Presets Column */}
        <div className="space-y-4 xl:col-span-7">
          <OrbitalFieldMap
            boundaryFeature={boundary}
            targetCenter={[longitude, latitude]}
            parcelRing={parcelRing}
            drawMode={drawMode}
            onAddVertex={handleAddVertex}
            attributionText={t.mapAttribution}
            instantJumpLabel={t.instantJump}
          />

          {/* Drawing Toolbar & 6 Verified Guelma Presets */}
          <div className="fs-liquid-panel lg-surface lg-specular rounded-3xl p-4 sm:p-5 text-[#111813] dark:text-[#F5F7F5]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => setDrawMode((v) => !v)}
                  className={`inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-xs font-semibold transition active:scale-[0.96] ${
                    drawMode
                      ? "bg-[#15803D] text-white shadow-sm dark:bg-[#22C55E] dark:text-[#081A0E]"
                      : "fs-cta-primary"
                  }`}
                >
                  <PencilSimple size={15} weight="bold" />
                  {drawMode ? t.drawModeOn : t.drawModeOff}
                </button>
                <button
                  type="button"
                  onClick={() => setParcelRing([])}
                  className="fs-liquid-pill inline-flex items-center gap-1.5 rounded-full px-3.5 py-2 text-xs font-semibold text-[#3E4C42] dark:text-[#D1DDD3]"
                >
                  <Trash size={14} />
                  {t.clearPolygon}
                </button>
              </div>
              <button
                type="button"
                data-testid="load-setif-outside-btn"
                onClick={handleLoadOutsideTest}
                className="rounded-full border border-red-300/80 bg-red-50/90 px-3.5 py-1.5 text-xs font-semibold text-red-700 transition hover:bg-red-100 dark:border-red-500/35 dark:bg-red-500/15 dark:text-red-300 dark:hover:bg-red-500/25"
              >
                {t.outsideTestBtn}
              </button>
            </div>

            <p className="mt-4 text-xs font-semibold text-[#4A5A4E] dark:text-[#9CA89E]">
              {t.presetsTitle}
            </p>
            <div className="mt-2.5 grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-3">
              {GUELMA_PARCEL_PRESETS.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  data-testid={`preset-${preset.id}`}
                  onClick={() => handleLoadPreset(preset.id)}
                  className="fs-liquid-well-interactive flex flex-col items-start rounded-2xl p-3 text-start"
                >
                  <span className="text-xs font-semibold text-[#111813] dark:text-[#F5F7F5]">
                    {preset.zoneName[lang]}
                  </span>
                  <span className="mt-1 font-mono text-[11px] font-medium tabular-nums text-[#15803D] dark:text-[#86EFAC]">
                    {preset.areaHectares} ha · {preset.ring.length - 1} vertices
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Side Control Drawer */}
        <div className="space-y-4 xl:col-span-5">
          {/* Farm Selector + Quick Create */}
          <div className="fs-liquid-panel rounded-3xl p-4 sm:p-5 text-[#111813] dark:text-[#F5F7F5]">
            <label className="block text-xs font-semibold text-[#4A5A4E] dark:text-[#9CA89E]">
              {t.farmLabel}
            </label>
            <div className="mt-2.5 flex flex-wrap gap-2">
              {(farmsQuery.data?.items ?? []).map((farm) => (
                <button
                  key={farm.farm_id}
                  type="button"
                  onClick={() => {
                    setActiveFarmId(farm.farm_id);
                    setActiveFieldId(null);
                  }}
                  className={`rounded-full px-3.5 py-1.5 text-xs font-semibold transition ${
                    farm.farm_id === resolvedFarmId
                      ? "bg-[#0B3D2E] text-white shadow-sm dark:bg-[#FFFFFF] dark:text-[#111713]"
                      : "fs-liquid-pill text-[#3E4C42] dark:text-[#D1DDD3]"
                  }`}
                >
                  {farm.farm_name} ({farm.field_count})
                </button>
              ))}
            </div>

            <form onSubmit={handleCreateFarm} className="mt-3.5 flex gap-2">
              <input
                type="text"
                value={newFarmName}
                onChange={(e) => setNewFarmName(e.target.value)}
                placeholder={t.newFarmName}
                className={`min-w-0 flex-1 ${glassInputClass}`}
              />
              <button
                type="submit"
                data-testid="create-farm-btn"
                className="fs-cta-primary inline-flex shrink-0 items-center gap-1 rounded-full px-3.5 py-1.5 text-xs font-semibold active:not-disabled:scale-[0.96]"
              >
                <Plus size={14} weight="bold" />
                {t.createFarmBtn}
              </button>
            </form>
          </div>

          {/* Field Switcher & Metadata Form */}
          <form
            onSubmit={handleSaveAndContinue}
            className="fs-liquid-panel space-y-4 rounded-3xl p-5 text-[#111813] dark:text-[#F5F7F5]"
          >
            <div>
              <p className="text-xs font-semibold text-[#4A5A4E] dark:text-[#9CA89E]">
                Farm Parcels
              </p>
              <div className="mt-2.5 flex flex-wrap gap-2">
                {(fieldsQuery.data?.items ?? []).map((f) => (
                  <button
                    key={f.field_id}
                    type="button"
                    onClick={() => setActiveFieldId(f.field_id)}
                    className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition ${
                      f.field_id === activeFieldId
                        ? "bg-[#0B3D2E] text-white shadow-sm dark:bg-[#FFFFFF] dark:text-[#111713]"
                        : "fs-liquid-pill text-[#3E4C42] dark:text-[#D1DDD3]"
                    }`}
                  >
                    <MapPin size={13} />
                    <span dir="ltr">{f.field_id}</span>
                    {f.is_unverified_demo_parcel && (
                      <span className="rounded-full bg-amber-500/20 px-1.5 text-[9px] font-bold text-amber-800 dark:text-[#FCD34D]">
                        DEMO
                      </span>
                    )}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => {
                    const nextNum = (fieldsQuery.data?.items.length ?? 0) + 1;
                    setActiveFieldId(null);
                    setEditingExisting(false);
                    setFieldId(`F${nextNum}`);
                    setFieldName(`Guelma Parcel F${nextNum}`);
                    setIsUnverifiedDemo(false);
                    setParcelRing([]);
                  }}
                  className="inline-flex items-center gap-1 rounded-full border border-dashed border-[#15803D]/50 px-3 py-1.5 text-xs font-semibold text-[#15803D] transition hover:bg-[#15803D]/10 dark:border-[#22C55E]/40 dark:text-[#86EFAC] dark:hover:bg-[#22C55E]/15"
                >
                  <Plus size={13} />
                  New Parcel
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-semibold text-[#3E4C42] dark:text-[#D1DDD3]">
                  {t.fieldIdLabel}
                </label>
                <input
                  type="text"
                  required
                  dir="ltr"
                  value={fieldId}
                  onChange={(e) => setFieldId(e.target.value)}
                  className={glassInputClass}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-[#3E4C42] dark:text-[#D1DDD3]">
                  {t.areaLabel}
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max="10000"
                  required
                  dir="ltr"
                  value={areaHectares}
                  onChange={(e) => setAreaHectares(Number(e.target.value))}
                  className={`tabular-nums ${glassInputClass}`}
                />
              </div>
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold text-[#3E4C42] dark:text-[#D1DDD3]">
                {t.fieldNameLabel}
              </label>
              <input
                type="text"
                required
                value={fieldName}
                onChange={(e) => setFieldName(e.target.value)}
                className={glassInputClass}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs font-semibold text-[#3E4C42] dark:text-[#D1DDD3]">
                  Latitude
                </label>
                <input
                  type="number"
                  step="0.000001"
                  dir="ltr"
                  value={latitude}
                  onChange={(e) => setLatitude(Number(e.target.value))}
                  className={`tabular-nums ${glassInputClass}`}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-[#3E4C42] dark:text-[#D1DDD3]">
                  Longitude
                </label>
                <input
                  type="number"
                  step="0.000001"
                  dir="ltr"
                  value={longitude}
                  onChange={(e) => setLongitude(Number(e.target.value))}
                  className={`tabular-nums ${glassInputClass}`}
                />
              </div>
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold text-[#3E4C42] dark:text-[#D1DDD3]">
                {t.elevationLabel}
              </label>
              <input
                type="number"
                step="1"
                min="-500"
                max="9000"
                dir="ltr"
                value={elevationInput}
                onChange={(e) => setElevationInput(e.target.value)}
                placeholder="null"
                className={`tabular-nums ${glassInputClass}`}
              />
              <p className="mt-1 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
                {t.elevationUnknownHint}
              </p>
            </div>

            <button
              type="submit"
              disabled={saving || !resolvedFarmId}
              data-testid="save-parcel-continue-btn"
              className="fs-cta-primary flex w-full items-center justify-center gap-2 rounded-full px-4 py-3 text-xs font-semibold active:not-disabled:scale-[0.98] disabled:opacity-50"
            >
              <FloppyDisk size={16} weight="bold" />
              {saving ? "Saving..." : t.saveContinueBtn}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
