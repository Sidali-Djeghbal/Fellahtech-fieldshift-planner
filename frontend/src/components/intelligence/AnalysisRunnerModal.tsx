"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  Brain,
  CheckSquare,
  Sliders,
  Thermometer,
  X,
} from "@phosphor-icons/react";
import { WEIGHT_PRESET_MAP } from "@/lib/analysis/workspaceAnalysis";
import {
  MARKET_PREFERENCE_LABELS,
  MONTH_SHORT,
  SEASON_LABELS,
} from "@/lib/i18n";
import { INTELLIGENCE_I18N } from "@/lib/i18n/intelligence";
import type {
  AnalysisSubmitRequest,
  CropItem,
  CycleMode,
  FarmPublic,
  FieldDetailPublic,
  Language,
  MarketPreference,
  PriorityWeights,
  Season,
} from "@/lib/schemas";
import { validateAnalysisPreSubmit } from "@/lib/validation";

const WEIGHT_KEYS: Array<keyof PriorityWeights> = [
  "water_saving",
  "soil_improvement",
  "income",
  "risk_reduction",
  "forage_value",
];

const MARKET_OPTIONS: MarketPreference[] = [
  "local_market",
  "mixed",
  "subsistence",
  "export",
];

const SEASON_OPTIONS: Season[] = ["autumn", "winter", "spring", "summer"];

interface AnalysisRunnerModalProps {
  open: boolean;
  lang: Language;
  farm: FarmPublic | null;
  farmFields: FieldDetailPublic[];
  initialFieldIds: string[];
  catalogItems: CropItem[];
  submitting: boolean;
  onClose: () => void;
  onSubmit: (payload: {
    farm: FarmPublic;
    targetFields: FieldDetailPublic[];
    submitRequest: Omit<AnalysisSubmitRequest, "farm_id">;
  }) => void;
}

export function AnalysisRunnerModal({
  open,
  lang,
  farm,
  farmFields,
  initialFieldIds,
  catalogItems,
  submitting,
  onClose,
  onSubmit,
}: AnalysisRunnerModalProps) {
  const dict = INTELLIGENCE_I18N[lang];
  const r = dict.runner;
  const months = MONTH_SHORT[lang];

  const [selectedFieldIds, setSelectedFieldIds] = useState<string[]>(initialFieldIds);
  const [startSeason, setStartSeason] = useState<Season>("autumn");
  const [startYear, setStartYear] = useState<number>(2026);
  const [horizonSeasons, setHorizonSeasons] = useState<number>(4);
  const [cycleMode, setCycleMode] = useState<CycleMode>("annual_rotation");
  const [plantingMonth, setPlantingMonth] = useState<number | "">("");
  const [weights, setWeights] = useState<PriorityWeights>(WEIGHT_PRESET_MAP.balanced);
  const [marketPreference, setMarketPreference] =
    useState<MarketPreference>("local_market");
  const [targetCropIds, setTargetCropIds] = useState<string[]>([]);
  const [excludedCropIds, setExcludedCropIds] = useState<string[]>([]);
  const [tempDeltaC, setTempDeltaC] = useState<number>(0);
  const [precipPctDelta, setPrecipPctDelta] = useState<number>(0);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  const closeBtnRef = useRef<HTMLButtonElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previousFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const raf = window.requestAnimationFrame(() => closeBtnRef.current?.focus());

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);

    const validInit = initialFieldIds.filter((id) =>
      farmFields.some((f) => f.field_id === id)
    );
    setSelectedFieldIds(
      validInit.length > 0
        ? validInit
        : farmFields.slice(0, 1).map((f) => f.field_id)
    );
    setValidationErrors([]);

    return () => {
      window.cancelAnimationFrame(raf);
      window.removeEventListener("keydown", handleKeyDown);
      previousFocusRef.current?.focus?.();
    };
  }, [open, initialFieldIds, farmFields, onClose]);

  if (!open || !farm) return null;

  const weightSum = WEIGHT_KEYS.reduce((sum, key) => sum + weights[key], 0);

  const toggleField = (fid: string) => {
    setSelectedFieldIds((prev) =>
      prev.includes(fid) ? prev.filter((id) => id !== fid) : [...prev, fid].slice(0, 10)
    );
  };

  const toggleTargetCrop = (cropId: string) => {
    setExcludedCropIds((prev) => prev.filter((id) => id !== cropId));
    setTargetCropIds((prev) =>
      prev.includes(cropId) ? prev.filter((id) => id !== cropId) : [...prev, cropId].slice(0, 10)
    );
  };

  const toggleExcludedCrop = (cropId: string) => {
    setTargetCropIds((prev) => prev.filter((id) => id !== cropId));
    setExcludedCropIds((prev) =>
      prev.includes(cropId) ? prev.filter((id) => id !== cropId) : [...prev, cropId].slice(0, 10)
    );
  };

  const handleAutoBalance = () => {
    if (weightSum === 100) return;
    if (weightSum === 0) {
      setWeights({ ...WEIGHT_PRESET_MAP.balanced });
      return;
    }
    const scaled: PriorityWeights = {
      water_saving: Math.round((weights.water_saving / weightSum) * 100),
      soil_improvement: Math.round((weights.soil_improvement / weightSum) * 100),
      income: Math.round((weights.income / weightSum) * 100),
      risk_reduction: Math.round((weights.risk_reduction / weightSum) * 100),
      forage_value: Math.round((weights.forage_value / weightSum) * 100),
    };
    const nextSum = WEIGHT_KEYS.reduce((s, k) => s + scaled[k], 0);
    scaled.water_saving = Math.max(0, scaled.water_saving + (100 - nextSum));
    setWeights(scaled);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const targetFields = farmFields.filter((f) => selectedFieldIds.includes(f.field_id));
    if (targetFields.length === 0) {
      setValidationErrors([r.selectAtLeastOneField]);
      return;
    }

    const pre = validateAnalysisPreSubmit({
      weights,
      targetCropIds,
      excludedCropIds,
      startSeason,
      plantingMonth: plantingMonth === "" ? null : Number(plantingMonth),
      latitude: targetFields[0].location.latitude,
      cropHistory: targetFields[0].crop_history,
    });

    if (!pre.valid) {
      setValidationErrors(pre.errors);
      return;
    }

    setValidationErrors([]);
    onSubmit({
      farm,
      targetFields,
      submitRequest: {
        language: lang,
        planning: {
          start_season: startSeason,
          start_year: startYear,
          horizon_seasons: horizonSeasons,
          cycle_mode: cycleMode,
          planting_month: plantingMonth === "" ? null : Number(plantingMonth),
          scenario_overrides: {
            temp_delta_c: tempDeltaC,
            precip_pct_delta: precipPctDelta,
          },
        },
        priorities: {
          weights,
          market_preference: marketPreference,
          target_crop_ids: targetCropIds,
          excluded_crop_ids: excludedCropIds,
          equipment_constraints: [],
        },
        field_ids: targetFields.map((f) => f.field_id),
      },
    });
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 overscroll-contain"
      role="dialog"
      aria-modal="true"
      aria-labelledby="runner-modal-title"
      data-testid="analysis-runner-modal"
    >
      <button
        type="button"
        tabIndex={-1}
        aria-label={r.closeBtn}
        onClick={onClose}
        className="fixed inset-0 bg-black/40 backdrop-blur-sm dark:bg-black/60"
      />

      <div className="fs-hud-glass relative z-10 flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-3xl overscroll-contain text-[#111813] dark:text-[#F5F7F5]">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 border-b border-[#111813]/10 px-6 pt-5 pb-4 dark:border-white/10">
          <div>
            <h2
              id="runner-modal-title"
              className="flex items-center gap-2 font-heading text-base font-semibold leading-[1.15] text-[#111813] dark:text-[#F5F7F5]"
            >
              <Brain size={18} weight="duotone" className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
              <span>{r.modalTitle}</span>
            </h2>
            <p className="mt-1 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">
              {farm.farm_name} — {r.modalSubtitle}
            </p>
          </div>
          <button
            ref={closeBtnRef}
            type="button"
            onClick={onClose}
            aria-label={r.closeBtn}
            className="fs-liquid-pill flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[#4A5A4E] hover:text-[#111813] active:scale-[0.96] dark:text-[#9CA89E] dark:hover:text-[#FFFFFF]"
          >
            <X size={16} aria-hidden="true" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="overflow-y-auto overscroll-contain px-6 py-5 space-y-5">
          {validationErrors.length > 0 ? (
            <div
              role="alert"
              className="rounded-2xl bg-red-50/95 p-4 text-xs text-red-800 ring-1 ring-red-600/30 dark:bg-red-500/15 dark:text-red-200 dark:ring-red-400/30"
            >
              <ul className="list-disc space-y-1 ps-4 font-medium">
                {validationErrors.map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {/* 1. Target Parcels */}
          <section className="fs-liquid-well rounded-2xl p-4">
            <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-[#15803D] dark:text-[#86EFAC]">
              <CheckSquare size={15} className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
              <span>{r.fieldsTitle}</span>
            </h3>
            <div className="mt-3 flex flex-wrap gap-2.5">
              {farmFields.map((fld) => {
                const checked = selectedFieldIds.includes(fld.field_id);
                return (
                  <button
                    key={fld.field_id}
                    type="button"
                    onClick={() => toggleField(fld.field_id)}
                    data-testid={`runner-field-${fld.field_id}`}
                    aria-pressed={checked}
                    className={`inline-flex min-h-10 items-center gap-2 rounded-full ps-3 pe-3.5 text-xs font-semibold transition-[transform,background-color,box-shadow,color] duration-150 ease-out active:scale-[0.96] ${
                      checked
                        ? "bg-[#0B3D2E] text-white shadow-[0_4px_14px_rgba(11,61,46,0.22)] dark:bg-[#FFFFFF] dark:text-[#111713] dark:shadow-[0_4px_14px_rgba(0,0,0,0.35)]"
                        : "fs-liquid-pill text-[#111813] dark:text-[#F5F7F5]"
                    }`}
                  >
                    <span>{fld.field_name}</span>
                    <span className="font-mono text-[10px] tabular-nums opacity-75">
                      {fld.area_hectares.toFixed(1)} ha
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          {/* 2. Planning Window */}
          <section className="fs-liquid-well rounded-2xl p-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-[#15803D] dark:text-[#86EFAC]">
              {r.planningTitle}
            </h3>
            <div className="mt-3 grid grid-cols-1 gap-3.5 text-xs sm:grid-cols-2 lg:grid-cols-3">
              <div className="space-y-1.5">
                <label htmlFor="runner-start-season" className="block font-semibold text-[#243227] dark:text-[#E4EBE5]">
                  {r.startSeason}
                </label>
                <select
                  id="runner-start-season"
                  value={startSeason}
                  onChange={(e) => setStartSeason(e.target.value as Season)}
                  className="min-h-10 w-full rounded-xl border border-[#111813]/15 bg-white/95 px-3 text-base font-medium text-[#111813] focus:border-[#15803D] dark:border-white/12 dark:bg-[#141A16] dark:text-[#F5F7F5] dark:focus:border-[#86EFAC]/60 sm:text-xs [color-scheme:light] dark:[color-scheme:dark]"
                >
                  {SEASON_OPTIONS.map((s) => (
                    <option key={s} value={s}>
                      {SEASON_LABELS[lang][s]}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="runner-start-year" className="block font-semibold text-[#243227] dark:text-[#E4EBE5]">
                  {r.startYear}
                </label>
                <input
                  id="runner-start-year"
                  type="number"
                  inputMode="numeric"
                  min={2024}
                  max={2040}
                  value={startYear}
                  onChange={(e) => setStartYear(Number(e.target.value) || 2026)}
                  className="tabular-nums min-h-10 w-full rounded-xl border border-[#111813]/15 bg-white/95 px-3 text-base font-medium text-[#111813] focus:border-[#15803D] dark:border-white/12 dark:bg-[#141A16] dark:text-[#F5F7F5] dark:focus:border-[#86EFAC]/60 sm:text-xs [color-scheme:light] dark:[color-scheme:dark]"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="runner-horizon-seasons" className="block font-semibold text-[#243227] dark:text-[#E4EBE5]">
                  {r.horizonSeasons}
                </label>
                <select
                  id="runner-horizon-seasons"
                  value={horizonSeasons}
                  onChange={(e) => setHorizonSeasons(Number(e.target.value))}
                  className="min-h-10 w-full rounded-xl border border-[#111813]/15 bg-white/95 px-3 text-base font-medium text-[#111813] focus:border-[#15803D] dark:border-white/12 dark:bg-[#141A16] dark:text-[#F5F7F5] dark:focus:border-[#86EFAC]/60 sm:text-xs [color-scheme:light] dark:[color-scheme:dark]"
                >
                  {[2, 3, 4, 5, 6].map((h) => (
                    <option key={h} value={h}>
                      {h}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="runner-cycle-mode" className="block font-semibold text-[#243227] dark:text-[#E4EBE5]">
                  {r.cycleMode}
                </label>
                <select
                  id="runner-cycle-mode"
                  value={cycleMode}
                  onChange={(e) => setCycleMode(e.target.value as CycleMode)}
                  className="min-h-10 w-full rounded-xl border border-[#111813]/15 bg-white/95 px-3 text-base font-medium text-[#111813] focus:border-[#15803D] dark:border-white/12 dark:bg-[#141A16] dark:text-[#F5F7F5] dark:focus:border-[#86EFAC]/60 sm:text-xs [color-scheme:light] dark:[color-scheme:dark]"
                >
                  <option value="annual_rotation">{r.cycleAnnual}</option>
                  <option value="consecutive_seasons">{r.cycleConsecutive}</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="runner-planting-month" className="block font-semibold text-[#243227] dark:text-[#E4EBE5]">
                  {r.plantingMonth}
                </label>
                <select
                  id="runner-planting-month"
                  value={plantingMonth}
                  onChange={(e) =>
                    setPlantingMonth(e.target.value === "" ? "" : Number(e.target.value))
                  }
                  className="min-h-10 w-full rounded-xl border border-[#111813]/15 bg-white/95 px-3 text-base font-medium text-[#111813] focus:border-[#15803D] dark:border-white/12 dark:bg-[#141A16] dark:text-[#F5F7F5] dark:focus:border-[#86EFAC]/60 sm:text-xs [color-scheme:light] dark:[color-scheme:dark]"
                >
                  <option value="">{r.plantingMonthAuto}</option>
                  {months.map((mName, idx) => (
                    <option key={idx + 1} value={idx + 1}>
                      {mName} ({idx + 1})
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="runner-market-pref" className="block font-semibold text-[#243227] dark:text-[#E4EBE5]">
                  {r.marketPreference}
                </label>
                <select
                  id="runner-market-pref"
                  value={marketPreference}
                  onChange={(e) =>
                    setMarketPreference(e.target.value as MarketPreference)
                  }
                  className="min-h-10 w-full rounded-xl border border-[#111813]/15 bg-white/95 px-3 text-base font-medium text-[#111813] focus:border-[#15803D] dark:border-white/12 dark:bg-[#141A16] dark:text-[#F5F7F5] dark:focus:border-[#86EFAC]/60 sm:text-xs [color-scheme:light] dark:[color-scheme:dark]"
                >
                  {MARKET_OPTIONS.map((mp) => (
                    <option key={mp} value={mp}>
                      {MARKET_PREFERENCE_LABELS[lang][mp]}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </section>

          {/* 3. Priority Weights */}
          <section className="fs-liquid-well rounded-2xl p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-[#15803D] dark:text-[#86EFAC]">
                <Sliders size={15} className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
                <span>{r.prioritiesTitle}</span>
              </h3>

              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`tabular-nums rounded-full px-2.5 py-0.5 font-mono text-[11px] font-semibold ${
                    weightSum === 100
                      ? "bg-emerald-100 text-emerald-800 dark:bg-[#22C55E]/15 dark:text-[#86EFAC]"
                      : "bg-red-100 text-red-800 dark:bg-red-500/20 dark:text-red-300"
                  }`}
                >
                  {r.weightsSum}: {weightSum} / 100
                </span>
                {weightSum !== 100 ? (
                  <button
                    type="button"
                    onClick={handleAutoBalance}
                    className="fs-cta-primary rounded-full px-2.5 py-1 text-[10px] font-semibold active:scale-[0.96]"
                  >
                    {r.autoBalanceBtn}
                  </button>
                ) : null}
              </div>
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              {(
                [
                  ["balanced", r.presetBalanced],
                  ["water", r.presetWater],
                  ["income", r.presetIncome],
                ] as const
              ).map(([presetKey, label]) => (
                <button
                  key={presetKey}
                  type="button"
                  onClick={() => setWeights({ ...WEIGHT_PRESET_MAP[presetKey] })}
                  className="fs-liquid-pill min-h-8 rounded-full px-3.5 text-[11px] font-semibold text-[#111813] active:scale-[0.96] dark:text-[#F5F7F5]"
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="mt-4 grid gap-3.5 sm:grid-cols-2">
              {WEIGHT_KEYS.map((key) => (
                <label key={key} className="space-y-1 text-xs">
                  <div className="flex justify-between font-medium text-[#243227] dark:text-[#E4EBE5]">
                    <span>{r.weightLabels[key]}</span>
                    <span dir="ltr" className="tabular-nums font-mono font-semibold text-[#15803D] dark:text-[#86EFAC]">
                      {weights[key]}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    step={5}
                    value={weights[key]}
                    onChange={(e) =>
                      setWeights((prev) => ({
                        ...prev,
                        [key]: Number(e.target.value),
                      }))
                    }
                    className="w-full accent-[#15803D] dark:accent-[#22C55E] [color-scheme:light] dark:[color-scheme:dark]"
                  />
                </label>
              ))}
            </div>

            {/* Catalog Target / Excluded Crops */}
            {catalogItems.length > 0 ? (
              <div className="mt-4 grid gap-3 border-t border-[#111813]/10 pt-3.5 sm:grid-cols-2 dark:border-white/10">
                <div>
                  <p className="text-[11px] font-semibold text-[#15803D] dark:text-[#86EFAC]">{r.targetCrops}</p>
                  <div className="mt-2 flex max-h-24 flex-wrap gap-1.5 overflow-y-auto">
                    {catalogItems.slice(0, 12).map((item) => {
                      const active = targetCropIds.includes(item.crop_id);
                      return (
                        <button
                          key={item.crop_id}
                          type="button"
                          onClick={() => toggleTargetCrop(item.crop_id)}
                          className={`rounded-full px-2.5 py-1 text-[10px] font-semibold transition-[transform,background-color,color] duration-150 ease-out active:scale-[0.96] ${
                            active
                              ? "bg-[#0B3D2E] text-white dark:bg-[#22C55E] dark:text-[#111713]"
                              : "fs-liquid-pill text-[#111813] dark:text-[#F5F7F5]"
                          }`}
                        >
                          {item.names[lang] || item.display_name || item.crop_id}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <p className="text-[11px] font-semibold text-red-700 dark:text-red-300">{r.excludedCrops}</p>
                  <div className="mt-2 flex max-h-24 flex-wrap gap-1.5 overflow-y-auto">
                    {catalogItems.slice(0, 12).map((item) => {
                      const active = excludedCropIds.includes(item.crop_id);
                      return (
                        <button
                          key={item.crop_id}
                          type="button"
                          onClick={() => toggleExcludedCrop(item.crop_id)}
                          className={`rounded-full px-2.5 py-1 text-[10px] font-semibold transition-[transform,background-color] duration-150 ease-out active:scale-[0.96] ${
                            active
                              ? "bg-red-600 text-white dark:bg-red-500"
                              : "fs-liquid-pill text-[#111813] dark:text-[#F5F7F5]"
                          }`}
                        >
                          {item.names[lang] || item.display_name || item.crop_id}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            ) : null}
          </section>

          {/* 4. Climate What-If */}
          <section className="fs-liquid-well rounded-2xl p-4">
            <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-[#15803D] dark:text-[#86EFAC]">
              <Thermometer size={15} className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
              <span>{r.whatIfTitle}</span>
            </h3>
            <p className="mt-1 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">{r.whatIfDesc}</p>

            <div className="mt-3 grid gap-3 text-xs sm:grid-cols-2">
              <label className="space-y-1">
                <div className="flex justify-between font-medium text-[#243227] dark:text-[#E4EBE5]">
                  <span>{r.tempDelta}</span>
                  <span dir="ltr" className="tabular-nums font-mono font-semibold text-[#15803D] dark:text-[#86EFAC]">
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
                  className="w-full accent-[#15803D] dark:accent-[#22C55E] [color-scheme:light] dark:[color-scheme:dark]"
                />
              </label>

              <label className="space-y-1">
                <div className="flex justify-between font-medium text-[#243227] dark:text-[#E4EBE5]">
                  <span>{r.precipDelta}</span>
                  <span dir="ltr" className="tabular-nums font-mono font-semibold text-[#15803D] dark:text-[#86EFAC]">
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
                  className="w-full accent-[#15803D] dark:accent-[#22C55E] [color-scheme:light] dark:[color-scheme:dark]"
                />
              </label>
            </div>
          </section>

          {/* Footer Submit Actions */}
          <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="fs-liquid-pill min-h-10 rounded-full px-5 text-xs font-semibold text-[#111813] active:scale-[0.96] dark:text-[#F5F7F5]"
            >
              {r.closeBtn}
            </button>
            <button
              type="submit"
              disabled={submitting || selectedFieldIds.length === 0}
              data-testid="submit-ai-analysis-btn"
              className="fs-cta-primary inline-flex min-h-10 items-center gap-2 rounded-full ps-4 pe-5 text-xs font-semibold active:not-disabled:scale-[0.96] disabled:opacity-55"
            >
              <Brain size={15} weight="duotone" aria-hidden="true" />
              <span>{submitting ? r.submittingBtn : r.submitBtn}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

