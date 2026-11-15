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
  const {
    lang,
    authMode,
    activeFarmId,
    activeFieldId,
    setActiveFarmId,
    setActiveFieldId,
  } = useAppStore();

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
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-extrabold text-[#111827]">{t.title}</h1>
          <p className="mt-1 text-xs text-[#6B7280]">{t.subtitle}</p>
        </div>
        <div
          data-testid="boundary-status-pill"
          className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-bold ${
            insideGuelma
              ? "bg-[#DCFCE7] text-[#15803D]"
              : "border border-red-300 bg-red-100 text-red-700"
          }`}
        >
          {insideGuelma ? <CheckCircle size={15} weight="fill" /> : <Warning size={15} weight="fill" />}
          {insideGuelma ? t.insideGuelma : t.outsideGuelma}
        </div>
      </div>

      {selectedFieldDetailQuery.data && (
        <WarningsBanner warnings={selectedFieldDetailQuery.data.warnings} lang={lang} />
      )}

      {saveError !== null && (
        <ApiErrorCard
          error={saveError}
          lang={lang}
          onOpenClaimAccount={() => {
            const trigger = document.querySelector<HTMLButtonElement>('[data-testid="auth-modal-trigger"]');
            trigger?.click();
          }}
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
          <div className="rounded-2xl border border-[#E5E7EB] bg-white p-4 shadow-sm text-[#111827]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => setDrawMode((v) => !v)}
                  className={`inline-flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-bold transition ${
                    drawMode ? "bg-[#00291B] text-[#84E875]" : "bg-[#00291B] text-white hover:bg-[#04421B]"
                  }`}
                >
                  <PencilSimple size={15} weight="bold" />
                  {drawMode ? t.drawModeOn : t.drawModeOff}
                </button>
                <button
                  type="button"
                  onClick={() => setParcelRing([])}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-gray-200 px-3 py-2 text-xs font-semibold text-[#374151] hover:bg-gray-100 transition"
                >
                  <Trash size={14} />
                  {t.clearPolygon}
                </button>
              </div>
              <button
                type="button"
                data-testid="load-setif-outside-btn"
                onClick={handleLoadOutsideTest}
                className="rounded-xl border border-red-200 bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-100 transition"
              >
                {t.outsideTestBtn}
              </button>
            </div>

            <p className="mt-4 text-xs font-bold text-[#6B7280]">{t.presetsTitle}</p>
            <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-3">
              {GUELMA_PARCEL_PRESETS.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  data-testid={`preset-${preset.id}`}
                  onClick={() => handleLoadPreset(preset.id)}
                  className="flex flex-col items-start rounded-xl border border-gray-200 bg-gray-50/70 p-2.5 text-start transition hover:border-[#137135] hover:bg-emerald-50/30"
                >
                  <span className="text-xs font-bold text-[#111827]">{preset.zoneName[lang]}</span>
                  <span className="tabular-nums mt-0.5 text-[11px] text-[#137135] font-semibold">
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
          <div className="rounded-2xl border border-[#E5E7EB] bg-white p-4 shadow-sm text-[#111827]">
            <label className="block text-xs font-bold text-[#6B7280]">{t.farmLabel}</label>
            <div className="mt-2 flex flex-wrap gap-2">
              {(farmsQuery.data?.items ?? []).map((farm) => (
                <button
                  key={farm.farm_id}
                  type="button"
                  onClick={() => {
                    setActiveFarmId(farm.farm_id);
                    setActiveFieldId(null);
                  }}
                  className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                    farm.farm_id === resolvedFarmId
                      ? "bg-[#00291B] text-white shadow-xs"
                      : "border border-gray-200 bg-white text-[#374151] hover:bg-gray-50"
                  }`}
                >
                  {farm.farm_name} ({farm.field_count})
                </button>
              ))}
            </div>

            <form onSubmit={handleCreateFarm} className="mt-3 flex gap-2">
              <input
                type="text"
                value={newFarmName}
                onChange={(e) => setNewFarmName(e.target.value)}
                placeholder={t.newFarmName}
                className="min-w-0 flex-1 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
              />
              <button
                type="submit"
                data-testid="create-farm-btn"
                className="inline-flex items-center gap-1 rounded-lg bg-[#00291B] px-3 py-1.5 text-xs font-bold text-white hover:bg-[#04421B] shadow-sm transition"
              >
                <Plus size={14} weight="bold" />
                {t.createFarmBtn}
              </button>
            </form>
          </div>

          {/* Field Switcher & Metadata Form */}
          <form onSubmit={handleSaveAndContinue} className="space-y-4 rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-sm text-[#111827]">
            <div>
              <p className="text-xs font-bold text-[#6B7280]">Farm Parcels</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {(fieldsQuery.data?.items ?? []).map((f) => (
                  <button
                    key={f.field_id}
                    type="button"
                    onClick={() => setActiveFieldId(f.field_id)}
                    className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-bold transition ${
                      f.field_id === activeFieldId
                        ? "bg-[#00291B] text-white shadow-xs"
                        : "border border-gray-200 bg-white text-[#374151] hover:bg-gray-50"
                    }`}
                  >
                    <MapPin size={13} />
                    <span dir="ltr">{f.field_id}</span>
                    {f.is_unverified_demo_parcel && (
                      <span className="rounded bg-[#FEF3C7] text-[#D97706] px-1 text-[9px] font-bold">DEMO</span>
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
                  className="inline-flex items-center gap-1 rounded-lg border border-dashed border-[#137135] px-2.5 py-1.5 text-xs font-semibold text-[#137135] hover:bg-emerald-50 transition"
                >
                  <Plus size={13} />
                  New Parcel
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-semibold text-[#374151]">
                  {t.fieldIdLabel}
                </label>
                <input
                  type="text"
                  required
                  dir="ltr"
                  value={fieldId}
                  onChange={(e) => setFieldId(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-[#374151]">
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
                  className="tabular-nums w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
                />
              </div>
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold text-[#374151]">
                {t.fieldNameLabel}
              </label>
              <input
                type="text"
                required
                value={fieldName}
                onChange={(e) => setFieldName(e.target.value)}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs font-semibold text-[#374151]">Latitude</label>
                <input
                  type="number"
                  step="0.000001"
                  dir="ltr"
                  value={latitude}
                  onChange={(e) => setLatitude(Number(e.target.value))}
                  className="tabular-nums w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-[#374151]">Longitude</label>
                <input
                  type="number"
                  step="0.000001"
                  dir="ltr"
                  value={longitude}
                  onChange={(e) => setLongitude(Number(e.target.value))}
                  className="tabular-nums w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
                />
              </div>
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold text-[#374151]">
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
                className="tabular-nums w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
              />
              <p className="mt-1 text-[11px] text-[#6B7280]">{t.elevationUnknownHint}</p>
            </div>

            <button
              type="submit"
              disabled={saving || !resolvedFarmId}
              data-testid="save-parcel-continue-btn"
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#00291B] px-4 py-3 text-xs font-bold text-white shadow-sm hover:bg-[#04421B] disabled:opacity-50 transition"
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
