"use client";

import React, { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Calculator,
  CheckCircle,
  Drop,
  Flask,
  Plant,
  Play,
  Plus,
  SlidersHorizontal,
  Trash,
  Warning,
  XCircle,
} from "@phosphor-icons/react";
import { UsdaTextureModal } from "@/components/profile/UsdaTextureModal";
import { ApiErrorCard, WarningsBanner } from "@/components/shared/ProvenanceBanners";
import {
  cancelAnalysisRequest,
  fetchAllCatalogItems,
  getField,
  listFarms,
  listFields,
  pollAnalysisRequest,
  replaceField,
  submitAnalysis,
} from "@/lib/api/endpoints";
import {
  CROP_CATEGORY_LABELS,
  IRRIGATION_SYSTEM_LABELS,
  MARKET_PREFERENCE_LABELS,
  SEASON_LABELS,
  SOIL_TYPE_LABELS,
  UI_DICT,
  WATER_AVAILABILITY_LABELS,
  WATER_SOURCE_LABELS,
} from "@/lib/i18n";
import type {
  AnalysisSubmitRequest,
  CycleMode,
  FieldWriteDraft,
  IrrigationSystem,
  MarketPreference,
  PriorityWeights,
  Season,
  SoilType,
  WaterAvailability,
  WaterSource,
} from "@/lib/schemas";
import {
  WEIGHT_KEYS,
  balanceRemainingWeights,
  validateAnalysisPreSubmit,
  validateDisjointCrops,
  validateSeasonMonthConsistency,
  validateWeightsSum,
} from "@/lib/validation";
import { useAppStore } from "@/store/useAppStore";

interface CropHistoryRowState {
  season: Season;
  year: number;
  planting_month: number | "";
  crop_id: string;
  crop_name_raw: string;
  useCustomCrop: boolean;
  yield_tons_per_hectare: number | "";
  notes: string;
}

const WEIGHT_PRESETS: Array<{ id: string; label: string; weights: PriorityWeights }> = [
  {
    id: "water_resilient",
    label: "Water Resilient",
    weights: {
      water_saving: 35,
      soil_improvement: 25,
      income: 20,
      risk_reduction: 15,
      forage_value: 5,
    },
  },
  {
    id: "soil_restorer",
    label: "Soil Restorer",
    weights: {
      water_saving: 20,
      soil_improvement: 40,
      income: 15,
      risk_reduction: 15,
      forage_value: 10,
    },
  },
  {
    id: "cash_market",
    label: "Cash Market",
    weights: {
      water_saving: 15,
      soil_improvement: 15,
      income: 45,
      risk_reduction: 15,
      forage_value: 10,
    },
  },
  {
    id: "balanced_livestock",
    label: "Balanced Livestock",
    weights: {
      water_saving: 25,
      soil_improvement: 20,
      income: 20,
      risk_reduction: 15,
      forage_value: 20,
    },
  },
];

const EQUIPMENT_OPTIONS = [
  "standard_tractor",
  "seed_drill",
  "combine_harvester",
  "hay_baler",
  "no_subsoiler",
];

export default function FarmProfilePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const {
    lang,
    authMode,
    activeFarmId,
    activeFieldId,
    setActiveFarmId,
    setActiveFieldId,
    setActiveAnalysisId,
    setActiveRequestId,
  } = useAppStore();

  const t = UI_DICT[lang].farmProfile;
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

  const resolvedFieldId = activeFieldId ?? fieldsQuery.data?.items[0]?.field_id ?? null;

  const fieldDetailQuery = useQuery({
    queryKey: ["field-detail", resolvedFarmId, resolvedFieldId],
    queryFn: () => getField(resolvedFarmId!, resolvedFieldId!),
    enabled: hasSession && Boolean(resolvedFarmId) && Boolean(resolvedFieldId),
  });

  const catalogQuery = useQuery({
    queryKey: ["catalog", lang],
    queryFn: () => fetchAllCatalogItems(lang),
    enabled: hasSession,
  });

  // Form states
  const [cropHistory, setCropHistory] = useState<CropHistoryRowState[]>([
    {
      season: "autumn",
      year: 2025,
      planting_month: 11,
      crop_id: "durum_wheat",
      crop_name_raw: "Durum Wheat",
      useCustomCrop: false,
      yield_tons_per_hectare: "",
      notes: "",
    },
  ]);
  const [soilType, setSoilType] = useState<SoilType>("unknown");
  const [soilPh, setSoilPh] = useState<string>("");
  const [organicMatter, setOrganicMatter] = useState<string>("");
  const [soilTestDate, setSoilTestDate] = useState<string>("");
  const [usdaModalOpen, setUsdaModalOpen] = useState(false);

  const [waterAvailability, setWaterAvailability] = useState<WaterAvailability>("moderate");
  const [waterSource, setWaterSource] = useState<WaterSource>("well");
  const [waterSourceOther, setWaterSourceOther] = useState("");
  const [irrigationSystem, setIrrigationSystem] = useState<IrrigationSystem>("drip");

  const [startSeason, setStartSeason] = useState<Season>("spring");
  const [startYear, setStartYear] = useState(2027);
  const [plantingMonth, setPlantingMonth] = useState<number | "">(3);
  const [horizonSeasons, setHorizonSeasons] = useState(4);
  const [cycleMode, setCycleMode] = useState<CycleMode>("annual_rotation");
  const [tempDeltaC, setTempDeltaC] = useState(0);
  const [precipPctDelta, setPrecipPctDelta] = useState(0);

  const [weights, setWeights] = useState<PriorityWeights>({
    water_saving: 30,
    soil_improvement: 25,
    income: 25,
    risk_reduction: 10,
    forage_value: 10,
  });
  const [marketPreference, setMarketPreference] = useState<MarketPreference>("mixed");
  const [targetCropIds, setTargetCropIds] = useState<string[]>(["chickpea"]);
  const [excludedCropIds, setExcludedCropIds] = useState<string[]>([]);
  const [equipmentConstraints, setEquipmentConstraints] = useState<string[]>([]);

  const [submitError, setSubmitError] = useState<unknown>(null);
  const [clientErrors, setClientErrors] = useState<string[]>([]);

  // Async Polling Modal State
  const [pollingRequestId, setPollingRequestId] = useState<string | null>(null);
  const [pollStatus, setPollStatus] = useState<string>("pending");
  const pollTimerRef = useRef<number | null>(null);

  useEffect(() => {
    const f = fieldDetailQuery.data;
    if (!f) return;
    if (resolvedFarmId) setActiveFarmId(resolvedFarmId);
    setActiveFieldId(f.field_id);

    setSoilType(f.soil.soil_type);
    setSoilPh(f.soil.soil_ph !== null ? String(f.soil.soil_ph) : "");
    setOrganicMatter(
      f.soil.organic_matter_percent !== null ? String(f.soil.organic_matter_percent) : ""
    );
    setSoilTestDate(f.soil.soil_test_date ?? "");
    setWaterAvailability(f.water.availability);
    setWaterSource(f.water.source);
    setWaterSourceOther(f.water.source_other ?? "");
    setIrrigationSystem(f.water.irrigation_system);

    if (f.crop_history.length > 0) {
      setCropHistory(
        f.crop_history.map((row) => ({
          season: row.season,
          year: row.year,
          planting_month: row.planting_month ?? "",
          crop_id: row.crop_id ?? "",
          crop_name_raw: row.crop_name_raw ?? "",
          useCustomCrop: !row.crop_id && Boolean(row.crop_name_raw),
          yield_tons_per_hectare: row.yield_tons_per_hectare ?? "",
          notes: row.notes ?? "",
        }))
      );
    }
  }, [fieldDetailQuery.data, resolvedFarmId, setActiveFarmId, setActiveFieldId]);

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) {
        window.clearTimeout(pollTimerRef.current);
      }
    };
  }, []);

  const fieldLat = fieldDetailQuery.data?.location.latitude ?? 36.52;
  const weightsCheck = validateWeightsSum(weights);
  const cropsCheck = validateDisjointCrops(targetCropIds, excludedCropIds);
  const planningMonthCheck = validateSeasonMonthConsistency(
    startSeason,
    plantingMonth === "" ? null : Number(plantingMonth),
    fieldLat
  );

  function toggleTargetCrop(cropId: string) {
    setTargetCropIds((prev) => {
      if (prev.includes(cropId)) return prev.filter((c) => c !== cropId);
      setExcludedCropIds((ex) => ex.filter((c) => c !== cropId)); // INPUT-02 mutual exclusion
      return [...prev, cropId];
    });
  }

  function toggleExcludedCrop(cropId: string) {
    setExcludedCropIds((prev) => {
      if (prev.includes(cropId)) return prev.filter((c) => c !== cropId);
      setTargetCropIds((tg) => tg.filter((c) => c !== cropId)); // INPUT-02 mutual exclusion
      return [...prev, cropId];
    });
  }

  async function runPollLoop(requestId: string, intervalMs: number) {
    try {
      const env = await pollAnalysisRequest(requestId);
      setPollStatus(env.status);
      if (env.status === "ok" || env.status === "partial") {
        if (env.analysis_id) {
          setActiveAnalysisId(env.analysis_id);
          setPollingRequestId(null);
          await queryClient.invalidateQueries({ queryKey: ["analyses"] });
          await queryClient.invalidateQueries({ queryKey: ["demo", "session"] });
          router.push(`/comparison?analysisId=${env.analysis_id}`);
        }
        return;
      }
      if (env.status === "failed" || env.status === "cancelled") {
        setPollingRequestId(null);
        if (env.error) {
          setSubmitError(new Error(env.error.message));
        }
        return;
      }
      pollTimerRef.current = window.setTimeout(
        () => void runPollLoop(requestId, env.poll_interval_ms ?? intervalMs),
        env.poll_interval_ms ?? intervalMs
      );
    } catch (err) {
      setPollingRequestId(null);
      setSubmitError(err);
    }
  }

  async function handleSubmitAll(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    setClientErrors([]);

    const preValidation = validateAnalysisPreSubmit({
      weights,
      targetCropIds,
      excludedCropIds,
      startSeason,
      plantingMonth: plantingMonth === "" ? null : Number(plantingMonth),
      latitude: fieldLat,
      cropHistory: cropHistory.map((r) => ({
        season: r.season,
        planting_month: r.planting_month === "" ? null : Number(r.planting_month),
      })),
    });

    if (!preValidation.valid) {
      setClientErrors(preValidation.errors);
      return;
    }

    if (!resolvedFarmId || !fieldDetailQuery.data) return;

    try {
      const f = fieldDetailQuery.data;
      // 1. Save pending parcel profile edits cleanly (ADR-5 strips soil.source & catalog_version)
      const draft: FieldWriteDraft = {
        field_id: f.field_id,
        field_name: f.field_name,
        is_unverified_demo_parcel: f.is_unverified_demo_parcel,
        location: f.location,
        area_hectares: f.area_hectares,
        elevation_m: f.elevation_m,
        soil: {
          soil_type: soilType,
          soil_ph: soilType === "unknown" || soilPh === "" ? null : Number(soilPh),
          organic_matter_percent:
            soilType === "unknown" || organicMatter === "" ? null : Number(organicMatter),
          soil_test_date: soilType === "unknown" || !soilTestDate ? null : soilTestDate,
        },
        water: {
          availability: waterAvailability,
          source: waterSource,
          source_other: waterSource === "other" ? waterSourceOther || null : null,
          irrigation_system: irrigationSystem,
        },
        crop_history: cropHistory.map((row) => ({
          season: row.season,
          year: Number(row.year),
          planting_month: row.planting_month === "" ? null : Number(row.planting_month),
          crop_id: row.useCustomCrop ? null : row.crop_id || null,
          crop_name_raw: row.useCustomCrop
            ? row.crop_name_raw || null
            : catalogQuery.data?.items.find((c) => c.crop_id === row.crop_id)?.names.en ??
              row.crop_name_raw ??
              null,
          yield_tons_per_hectare:
            row.yield_tons_per_hectare === "" ? null : Number(row.yield_tons_per_hectare),
          notes: row.notes || null,
        })),
      };

      await replaceField(resolvedFarmId, f.field_id, draft);

      // 2. Submit analysis job (202 Accepted)
      const payload: AnalysisSubmitRequest = {
        farm_id: resolvedFarmId,
        language: lang,
        planning: {
          start_season: startSeason,
          start_year: Number(startYear),
          horizon_seasons: Number(horizonSeasons),
          cycle_mode: cycleMode,
          planting_month: plantingMonth === "" ? null : Number(plantingMonth),
          scenario_overrides: {
            temp_delta_c: Number(tempDeltaC),
            precip_pct_delta: Number(precipPctDelta),
          },
        },
        priorities: {
          weights,
          market_preference: marketPreference,
          target_crop_ids: targetCropIds,
          excluded_crop_ids: excludedCropIds,
          equipment_constraints: equipmentConstraints,
        },
        field_ids: [f.field_id],
      };

      const queued = await submitAnalysis(payload);
      setActiveRequestId(queued.request_id);
      setPollingRequestId(queued.request_id);
      setPollStatus(queued.status);

      pollTimerRef.current = window.setTimeout(
        () => void runPollLoop(queued.request_id, queued.poll_interval_ms),
        queued.poll_interval_ms
      );
    } catch (err) {
      setSubmitError(err);
    }
  }

  async function handleCancelPolling() {
    if (!pollingRequestId) return;
    if (pollTimerRef.current) {
      window.clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    try {
      await cancelAnalysisRequest(pollingRequestId);
    } catch {
      // Ignore if already finished
    } finally {
      setPollingRequestId(null);
      setPollStatus("cancelled");
    }
  }

  const catalogItems = catalogQuery.data?.items ?? [];

  return (
    <div className="space-y-5 pb-8">
      <div>
        <h1 className="font-heading text-2xl font-extrabold text-[#111827]">{t.title}</h1>
        <p className="mt-1 text-xs text-[#6B7280]">{t.subtitle}</p>
      </div>

      {fieldDetailQuery.data && (
        <WarningsBanner warnings={fieldDetailQuery.data.warnings} lang={lang} />
      )}

      {submitError !== null && (
        <ApiErrorCard
          error={submitError}
          lang={lang}
          onOpenClaimAccount={() => {
            document.querySelector<HTMLButtonElement>('[data-testid="auth-modal-trigger"]')?.click();
          }}
        />
      )}

      {clientErrors.length > 0 && (
        <div
          role="alert"
          data-testid="client-validation-errors"
          className="rounded-xl border-2 border-red-300 bg-red-50 p-4 text-xs text-red-800"
        >
          <ul className="list-disc space-y-1 ps-5">
            {clientErrors.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      <form onSubmit={handleSubmitAll} className="space-y-5">
        {/* Section 1: Crop History */}
        <section className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-sm text-[#111827]">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="flex items-center gap-2 font-heading text-base font-bold text-[#111827]">
              <Plant size={18} className="text-[#137135]" />
              {t.secCropHistory}
            </h2>
            <button
              type="button"
              onClick={() =>
                setCropHistory((prev) => [
                  ...prev,
                  {
                    season: "autumn",
                    year: 2024,
                    planting_month: 11,
                    crop_id: "barley",
                    crop_name_raw: "Barley",
                    useCustomCrop: false,
                    yield_tons_per_hectare: "",
                    notes: "",
                  },
                ])
              }
              disabled={cropHistory.length >= 30}
              className="inline-flex items-center gap-1 rounded-lg bg-[#00291B] px-3 py-1.5 text-xs font-bold text-white hover:bg-[#04421B] shadow-sm transition"
            >
              <Plus size={14} weight="bold" />
              {t.addHistoryRow}
            </button>
          </div>

          <div className="space-y-3">
            {cropHistory.map((row, idx) => {
              const rowMonthCheck = validateSeasonMonthConsistency(
                row.season,
                row.planting_month === "" ? null : Number(row.planting_month),
                fieldLat
              );
              return (
                <div
                  key={idx}
                  className="rounded-xl border border-gray-200 bg-gray-50/70 p-3.5"
                >
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
                    <div>
                      <label className="mb-1 block text-[11px] font-semibold text-[#374151]">Season</label>
                      <select
                        value={row.season}
                        onChange={(e) => {
                          const val = e.target.value as Season;
                          setCropHistory((prev) =>
                            prev.map((r, i) => (i === idx ? { ...r, season: val } : r))
                          );
                        }}
                        className="w-full rounded-lg border border-gray-300 bg-white px-2.5 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
                      >
                        {(["spring", "summer", "autumn", "winter"] as Season[]).map((s) => (
                          <option key={s} value={s}>
                            {SEASON_LABELS[lang][s]}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="mb-1 block text-[11px] font-semibold text-[#374151]">Year</label>
                      <input
                        type="number"
                        min={1980}
                        max={2100}
                        value={row.year}
                        onChange={(e) => {
                          const val = Number(e.target.value);
                          setCropHistory((prev) =>
                            prev.map((r, i) => (i === idx ? { ...r, year: val } : r))
                          );
                        }}
                        className="tabular-nums w-full rounded-lg border border-gray-300 bg-white px-2.5 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-[11px] font-semibold text-[#374151]">
                        Planting Month
                      </label>
                      <input
                        type="number"
                        min={1}
                        max={12}
                        value={row.planting_month}
                        onChange={(e) => {
                          const val = e.target.value === "" ? "" : Number(e.target.value);
                          setCropHistory((prev) =>
                            prev.map((r, i) => (i === idx ? { ...r, planting_month: val } : r))
                          );
                        }}
                        placeholder="1..12"
                        className="tabular-nums w-full rounded-lg border border-gray-300 bg-white px-2.5 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
                      />
                    </div>
                    <div className="lg:col-span-2">
                      <div className="mb-1 flex items-center justify-between text-[11px]">
                        <span className="font-semibold text-[#374151]">Crop</span>
                        <label className="inline-flex cursor-pointer items-center gap-1 text-[#137135]">
                          <input
                            type="checkbox"
                            checked={row.useCustomCrop}
                            onChange={(e) =>
                              setCropHistory((prev) =>
                                prev.map((r, i) =>
                                  i === idx ? { ...r, useCustomCrop: e.target.checked } : r
                                )
                              )
                            }
                          />
                          {t.otherLocalCrop}
                        </label>
                      </div>
                      {!row.useCustomCrop ? (
                        <select
                          value={row.crop_id}
                          onChange={(e) => {
                            const cid = e.target.value;
                            const found = catalogItems.find((c) => c.crop_id === cid);
                            setCropHistory((prev) =>
                              prev.map((r, i) =>
                                i === idx
                                  ? {
                                      ...r,
                                      crop_id: cid,
                                      crop_name_raw: found?.names.en ?? cid,
                                    }
                                  : r
                              )
                            );
                          }}
                          className="w-full rounded-lg border border-gray-300 bg-white px-2.5 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
                        >
                          {catalogItems.map((item) => (
                            <option key={item.crop_id} value={item.crop_id}>
                              {item.names[lang]} · {CROP_CATEGORY_LABELS[lang][item.category]}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="text"
                          required
                          value={row.crop_name_raw}
                          onChange={(e) => {
                            const val = e.target.value;
                            setCropHistory((prev) =>
                              prev.map((r, i) =>
                                i === idx ? { ...r, crop_id: "", crop_name_raw: val } : r
                              )
                            );
                          }}
                          placeholder="e.g. Blé dur local"
                          className="w-full rounded-lg border border-gray-300 bg-white px-2.5 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
                        />
                      )}
                    </div>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                    {!rowMonthCheck.valid ? (
                      <span className="text-[11px] font-semibold text-red-600">
                        INPUT-03: {rowMonthCheck.error}
                      </span>
                    ) : (
                      <span className="text-[11px] text-gray-500">
                        Northern Hemisphere season check OK
                      </span>
                    )}
                    {cropHistory.length > 1 && (
                      <button
                        type="button"
                        onClick={() =>
                          setCropHistory((prev) => prev.filter((_, i) => i !== idx))
                        }
                        className="inline-flex items-center gap-1 text-[11px] text-red-600 hover:underline"
                      >
                        <Trash size={13} />
                        Remove
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Section 2: Soil Provenance (ADR-5) */}
        <section className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-sm text-[#111827]">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="flex items-center gap-2 font-heading text-base font-bold text-[#111827]">
              <Flask size={18} className="text-[#137135]" />
              {t.secSoil}
            </h2>
            <button
              type="button"
              onClick={() => setUsdaModalOpen(true)}
              data-testid="usda-converter-btn"
              className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-bold text-[#00291B] hover:bg-gray-50 shadow-xs transition"
            >
              <Calculator size={14} />
              {t.usdaHelperBtn}
            </button>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <button
              type="button"
              onClick={() => {
                setSoilType("unknown");
                setSoilPh("");
                setOrganicMatter("");
                setSoilTestDate("");
              }}
              className={`rounded-xl border p-4 text-start transition ${
                soilType === "unknown"
                  ? "border-[#137135] bg-emerald-50/50"
                  : "border-gray-200 bg-white hover:border-gray-300"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-[#111827]">{t.soilUnknownTitle}</span>
                <span className="rounded bg-gray-100 text-gray-700 px-2 py-0.5 text-[10px] font-bold">
                  soil_source: unknown
                </span>
              </div>
              <p className="mt-1 text-xs text-[#6B7280]">{t.soilUnknownDesc}</p>
            </button>

            <button
              type="button"
              onClick={() => {
                if (soilType === "unknown") setSoilType("loamy");
              }}
              className={`rounded-xl border p-4 text-start transition ${
                soilType !== "unknown"
                  ? "border-[#137135] bg-emerald-50/50"
                  : "border-gray-200 bg-white hover:border-gray-300"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-[#111827]">{t.soilKnownTitle}</span>
                <span className="rounded bg-[#DCFCE7] text-[#15803D] px-2 py-0.5 text-[10px] font-bold">
                  soil_source: farmer
                </span>
              </div>
              <p className="mt-1 text-xs text-[#6B7280]">{t.soilKnownDesc}</p>
            </button>
          </div>

          {soilType !== "unknown" && (
            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-4">
              <div>
                <label className="mb-1 block text-xs font-semibold text-[#374151]">Soil Texture</label>
                <select
                  value={soilType}
                  onChange={(e) => setSoilType(e.target.value as SoilType)}
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
                >
                  {(["clay", "loamy", "silty", "sandy"] as SoilType[]).map((st) => (
                    <option key={st} value={st}>
                      {SOIL_TYPE_LABELS[lang][st]}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-[#374151]">Soil pH (3.0–11.0)</label>
                <input
                  type="number"
                  step="0.1"
                  min={3.0}
                  max={11.0}
                  value={soilPh}
                  onChange={(e) => setSoilPh(e.target.value)}
                  placeholder="7.6"
                  className="tabular-nums w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-[#374151]">Organic Matter %</label>
                <input
                  type="number"
                  step="0.1"
                  min={0}
                  max={100}
                  value={organicMatter}
                  onChange={(e) => setOrganicMatter(e.target.value)}
                  placeholder="1.4"
                  className="tabular-nums w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-[#374151]">Lab Test Date</label>
                <input
                  type="date"
                  value={soilTestDate}
                  onChange={(e) => setSoilTestDate(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
                />
              </div>
            </div>
          )}
        </section>

        {/* Section 3: Water & Irrigation */}
        <section className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-sm text-[#111827]">
          <h2 className="mb-3 flex items-center gap-2 font-heading text-base font-bold text-[#111827]">
            <Drop size={18} className="text-[#137135]" />
            {t.secWater}
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-semibold text-[#374151]">
                {t.waterAvailability}
              </label>
              <select
                value={waterAvailability}
                onChange={(e) => setWaterAvailability(e.target.value as WaterAvailability)}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
              >
                {(Object.keys(WATER_AVAILABILITY_LABELS[lang]) as WaterAvailability[]).map((w) => (
                  <option key={w} value={w}>
                    {WATER_AVAILABILITY_LABELS[lang][w]}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-[#374151]">
                {t.waterSource}
              </label>
              <select
                value={waterSource}
                onChange={(e) => setWaterSource(e.target.value as WaterSource)}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
              >
                {(Object.keys(WATER_SOURCE_LABELS[lang]) as WaterSource[]).map((w) => (
                  <option key={w} value={w}>
                    {WATER_SOURCE_LABELS[lang][w]}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-[#374151]">
                {t.irrigationSystem}
              </label>
              <select
                value={irrigationSystem}
                onChange={(e) => setIrrigationSystem(e.target.value as IrrigationSystem)}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
              >
                {(Object.keys(IRRIGATION_SYSTEM_LABELS[lang]) as IrrigationSystem[]).map((sys) => (
                  <option key={sys} value={sys}>
                    {IRRIGATION_SYSTEM_LABELS[lang][sys]}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {waterSource === "other" && (
            <div className="mt-3">
              <label className="mb-1 block text-xs font-semibold text-[#374151]">
                {t.waterSourceOther}
              </label>
              <input
                type="text"
                value={waterSourceOther}
                onChange={(e) => setWaterSourceOther(e.target.value)}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
              />
            </div>
          )}
        </section>

        {/* Section 4: Planning Window & Climate What-If */}
        <section className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-sm text-[#111827]">
          <h2 className="mb-3 font-heading text-base font-bold text-[#111827]">{t.secPlanning}</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <div>
              <label className="mb-1 block text-xs font-semibold text-[#374151]">{t.startSeason}</label>
              <select
                value={startSeason}
                onChange={(e) => setStartSeason(e.target.value as Season)}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
              >
                {(["spring", "summer", "autumn", "winter"] as Season[]).map((s) => (
                  <option key={s} value={s}>
                    {SEASON_LABELS[lang][s]}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-[#374151]">{t.startYear}</label>
              <input
                type="number"
                min={2020}
                max={2100}
                value={startYear}
                onChange={(e) => setStartYear(Number(e.target.value))}
                className="tabular-nums w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-[#374151]">{t.plantingMonth}</label>
              <input
                type="number"
                min={1}
                max={12}
                data-testid="planning-month-input"
                value={plantingMonth}
                onChange={(e) =>
                  setPlantingMonth(e.target.value === "" ? "" : Number(e.target.value))
                }
                className="tabular-nums w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-[#374151]">{t.horizonSeasons}</label>
              <input
                type="number"
                min={1}
                max={6}
                value={horizonSeasons}
                onChange={(e) => setHorizonSeasons(Number(e.target.value))}
                className="tabular-nums w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-[#374151]">{t.cycleMode}</label>
              <select
                value={cycleMode}
                onChange={(e) => setCycleMode(e.target.value as CycleMode)}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
              >
                <option value="annual_rotation">Annual Rotation</option>
                <option value="consecutive_seasons">Consecutive Seasons</option>
              </select>
            </div>
          </div>

          {!planningMonthCheck.valid && (
            <p className="mt-2 flex items-center gap-1.5 text-xs font-bold text-red-600">
              <Warning size={15} weight="fill" />
              INPUT-03: {planningMonthCheck.error}
            </p>
          )}

          <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50/40 p-4">
            <p className="mb-3 text-xs font-bold text-[#00291B]">{t.whatIfTitle}</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <div className="flex justify-between text-xs text-[#374151]">
                  <span>{t.tempDelta}</span>
                  <span dir="ltr" className="tabular-nums font-bold text-[#111827]">
                    {tempDeltaC >= 0 ? `+${tempDeltaC}` : tempDeltaC} °C
                  </span>
                </div>
                <input
                  type="range"
                  min={-5}
                  max={10}
                  step={0.5}
                  value={tempDeltaC}
                  onChange={(e) => setTempDeltaC(Number(e.target.value))}
                  className="mt-1 w-full accent-[#137135]"
                />
              </div>
              <div>
                <div className="flex justify-between text-xs text-[#374151]">
                  <span>{t.precipDelta}</span>
                  <span dir="ltr" className="tabular-nums font-bold text-[#111827]">
                    {precipPctDelta >= 0 ? `+${precipPctDelta}` : precipPctDelta}%
                  </span>
                </div>
                <input
                  type="range"
                  min={-80}
                  max={100}
                  step={5}
                  value={precipPctDelta}
                  onChange={(e) => setPrecipPctDelta(Number(e.target.value))}
                  className="mt-1 w-full accent-[#137135]"
                />
              </div>
            </div>
          </div>
        </section>

        {/* Section 5: Farmer Priorities (Sum = 100) & Crop Constraints */}
        <section className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-sm text-[#111827]">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="flex items-center gap-2 font-heading text-base font-bold text-[#111827]">
              <SlidersHorizontal size={18} className="text-[#137135]" />
              {t.secPriorities}
            </h2>
            <div className="flex flex-wrap items-center gap-2">
              <span
                data-testid="weights-sum-badge"
                className={`tabular-nums rounded-full px-3 py-1 text-xs font-bold ${
                  weightsCheck.valid
                    ? "bg-[#DCFCE7] text-[#15803D]"
                    : "bg-red-100 text-red-700"
                }`}
              >
                {t.weightsSum}: {weightsCheck.sum} / 100
              </span>
              {!weightsCheck.valid && (
                <button
                  type="button"
                  onClick={() => setWeights((prev) => balanceRemainingWeights(prev))}
                  className="rounded-lg bg-[#00291B] text-white hover:bg-[#04421B] px-3 py-1 text-xs font-bold transition shadow-xs"
                >
                  {t.autoBalanceBtn}
                </button>
              )}
            </div>
          </div>

          {/* 4 Presets */}
          <div className="mb-4 flex flex-wrap gap-2">
            {WEIGHT_PRESETS.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setWeights(p.weights)}
                className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-semibold text-[#374151] hover:bg-gray-50 transition"
              >
                {p.label}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {WEIGHT_KEYS.map((key) => (
              <div key={key} className="rounded-xl border border-gray-200 bg-gray-50/60 p-3">
                <label className="block text-[11px] font-semibold capitalize text-[#374151]">
                  {key.replace("_", " ")}
                </label>
                <input
                  type="number"
                  min={0}
                  max={100}
                  data-testid={`weight-input-${key}`}
                  value={weights[key]}
                  onChange={(e) =>
                    setWeights((prev) => ({
                      ...prev,
                      [key]: Math.max(0, Math.min(100, Math.round(Number(e.target.value)))),
                    }))
                  }
                  className="tabular-nums mt-1.5 w-full rounded-lg border border-gray-300 bg-white px-2.5 py-1.5 text-sm font-bold text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
                />
              </div>
            ))}
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-xs font-bold text-[#374151]">
                {t.targetCrops}
              </label>
              <div className="flex flex-wrap gap-1.5">
                {catalogItems
                  .filter((c) => c.category !== "fallow")
                  .map((item) => {
                    const selected = targetCropIds.includes(item.crop_id);
                    const isExcluded = excludedCropIds.includes(item.crop_id);
                    return (
                      <button
                        key={item.crop_id}
                        type="button"
                        disabled={isExcluded}
                        onClick={() => toggleTargetCrop(item.crop_id)}
                        className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                          selected
                            ? "bg-[#00291B] text-white shadow-xs"
                            : isExcluded
                              ? "cursor-not-allowed bg-gray-100 text-gray-400 line-through"
                              : "border border-gray-200 bg-white text-[#374151] hover:bg-gray-50"
                        }`}
                      >
                        {item.names[lang]}
                      </button>
                    );
                  })}
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-bold text-[#374151]">
                {t.excludedCrops}
              </label>
              <div className="flex flex-wrap gap-1.5">
                {catalogItems
                  .filter((c) => c.category !== "fallow")
                  .map((item) => {
                    const selected = excludedCropIds.includes(item.crop_id);
                    const isTarget = targetCropIds.includes(item.crop_id);
                    return (
                      <button
                        key={item.crop_id}
                        type="button"
                        disabled={isTarget}
                        onClick={() => toggleExcludedCrop(item.crop_id)}
                        className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                          selected
                            ? "bg-red-600 text-white shadow-xs"
                            : isTarget
                              ? "cursor-not-allowed bg-gray-100 text-gray-400 line-through"
                              : "border border-gray-200 bg-white text-[#374151] hover:bg-gray-50"
                        }`}
                      >
                        {item.names[lang]}
                      </button>
                    );
                  })}
              </div>
            </div>
          </div>

          {!cropsCheck.valid && (
            <p className="mt-2 text-xs font-bold text-red-600">{cropsCheck.error}</p>
          )}

          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-semibold text-[#374151]">
                {t.marketPreference}
              </label>
              <select
                value={marketPreference}
                onChange={(e) => setMarketPreference(e.target.value as MarketPreference)}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
              >
                {(Object.keys(MARKET_PREFERENCE_LABELS[lang]) as MarketPreference[]).map((mp) => (
                  <option key={mp} value={mp}>
                    {MARKET_PREFERENCE_LABELS[lang][mp]}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-[#374151]">
                {t.equipmentConstraints}
              </label>
              <div className="flex flex-wrap gap-1.5">
                {EQUIPMENT_OPTIONS.map((eq) => {
                  const active = equipmentConstraints.includes(eq);
                  return (
                    <button
                      key={eq}
                      type="button"
                      onClick={() =>
                        setEquipmentConstraints((prev) =>
                          prev.includes(eq) ? prev.filter((i) => i !== eq) : [...prev, eq]
                        )
                      }
                      className={`rounded-lg px-2.5 py-1 text-[11px] font-semibold transition ${
                        active
                          ? "bg-[#00291B] text-white shadow-xs"
                          : "border border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
                      }`}
                    >
                      {eq.replace(/_/g, " ")}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </section>

        {/* Sticky Submission Bar */}
        <div className="sticky bottom-16 z-20 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#E5E7EB] bg-white p-4 shadow-lg lg:bottom-4">
          <div className="flex items-center gap-2 text-xs">
            {weightsCheck.valid && cropsCheck.valid && planningMonthCheck.valid ? (
              <>
                <CheckCircle size={18} weight="fill" className="text-[#15803D]" />
                <span className="text-[#111827]">
                  Ready to analyze parcel{" "}
                  <strong dir="ltr" className="text-[#00291B]">
                    {resolvedFieldId ?? "—"}
                  </strong>
                </span>
              </>
            ) : (
              <>
                <Warning size={18} weight="fill" className="text-red-600" />
                <span className="text-red-700 font-semibold">Fix validation guards before running.</span>
              </>
            )}
          </div>
          <button
            type="submit"
            disabled={!resolvedFarmId || !resolvedFieldId || Boolean(pollingRequestId)}
            data-testid="run-analysis-submit-btn"
            className="inline-flex items-center gap-2 rounded-xl bg-[#00291B] px-5 py-2.5 text-xs font-bold text-white shadow-md hover:bg-[#04421B] disabled:opacity-50 transition"
          >
            <Play size={16} weight="fill" className="text-[#84E875]" />
            {t.submitBtn}
          </button>
        </div>
      </form>

      {/* Async Job Queue Modal */}
      {pollingRequestId && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
        >
          <div className="flex w-full max-w-md flex-col items-center rounded-2xl border border-[#E5E7EB] bg-white p-6 text-center shadow-xl text-[#111827]">
            <div className="relative h-16 w-16">
              <svg className="animate-spin h-full w-full text-[#137135]" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            </div>
            <h3 className="mt-4 font-heading text-base font-extrabold text-[#111827]">
              {t.pollingTitle}
            </h3>
            <p className="mt-1 text-xs text-[#374151]">
              Status: <span className="font-bold uppercase text-[#137135]">{pollStatus}</span>
            </p>
            <p dir="ltr" className="mt-1 text-[11px] text-gray-500">
              {pollingRequestId}
            </p>
            <button
              type="button"
              onClick={handleCancelPolling}
              data-testid="cancel-job-btn"
              className="mt-5 inline-flex items-center gap-1.5 rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-xs font-bold text-red-700 hover:bg-red-100 transition"
            >
              <XCircle size={15} weight="bold" />
              {t.cancelJobBtn}
            </button>
          </div>
        </div>
      )}

      <UsdaTextureModal
        open={usdaModalOpen}
        lang={lang}
        onClose={() => setUsdaModalOpen(false)}
        onApply={(derived) => setSoilType(derived)}
      />
    </div>
  );
}
