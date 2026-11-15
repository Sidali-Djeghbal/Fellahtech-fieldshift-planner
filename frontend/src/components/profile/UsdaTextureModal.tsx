"use client";

import React, { useState } from "react";
import { Calculator, X } from "@phosphor-icons/react";
import { SOIL_TYPE_LABELS, UI_DICT } from "@/lib/i18n";
import type { Language, SoilType } from "@/lib/schemas";
import { classifyUsdaSoilTexture } from "@/lib/validation";

interface UsdaTextureModalProps {
  open: boolean;
  lang: Language;
  onClose: () => void;
  onApply: (soilType: Exclude<SoilType, "unknown">) => void;
}

export function UsdaTextureModal({
  open,
  lang,
  onClose,
  onApply,
}: UsdaTextureModalProps) {
  const [unit, setUnit] = useState<"percent" | "g_per_kg">("percent");
  const [clay, setClay] = useState(28);
  const [silt, setSilt] = useState(38);
  const [sand, setSand] = useState(34);

  if (!open) return null;

  const t = UI_DICT[lang].farmProfile;
  const derived = classifyUsdaSoilTexture({ clay, silt, sand, unit });

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t.usdaTitle}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
    >
      <div className="relative w-full max-w-md rounded-2xl bg-white border border-[#E5E7EB] p-5 text-[#111827] shadow-xl">
        <button
          type="button"
          onClick={onClose}
          aria-label="Close USDA texture converter"
          className="absolute end-4 top-4 rounded-lg p-1 text-gray-400 hover:text-gray-700"
        >
          <X size={18} />
        </button>

        <div className="flex items-center gap-2">
          <Calculator size={20} className="text-[#137135]" />
          <h3 className="font-heading text-base font-bold text-[#111827]">{t.usdaTitle}</h3>
        </div>
        <p className="mt-1 text-xs text-[#6B7280]">
          ADR-5 exact rule: clay &ge; 40% &rarr; clay; else silt &ge; 50% &rarr; silty; else sand &ge; 70% &rarr; sandy; else loamy.
        </p>

        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={() => {
              if (unit === "g_per_kg") {
                setClay(Math.round(clay / 10));
                setSilt(Math.round(silt / 10));
                setSand(Math.round(sand / 10));
                setUnit("percent");
              }
            }}
            className={`rounded-lg px-3 py-1 text-xs font-bold transition ${
              unit === "percent" ? "bg-[#00291B] text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            Percent (%)
          </button>
          <button
            type="button"
            onClick={() => {
              if (unit === "percent") {
                setClay(clay * 10);
                setSilt(silt * 10);
                setSand(sand * 10);
                setUnit("g_per_kg");
              }
            }}
            className={`rounded-lg px-3 py-1 text-xs font-bold transition ${
              unit === "g_per_kg" ? "bg-[#00291B] text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            g / kg
          </button>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-3">
          <div>
            <label className="mb-1 block text-xs font-semibold text-[#374151]">Clay</label>
            <input
              type="number"
              min={0}
              max={unit === "percent" ? 100 : 1000}
              value={clay}
              onChange={(e) => setClay(Number(e.target.value))}
              className="tabular-nums w-full rounded-lg border border-gray-300 bg-white px-2.5 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-[#374151]">Silt</label>
            <input
              type="number"
              min={0}
              max={unit === "percent" ? 100 : 1000}
              value={silt}
              onChange={(e) => setSilt(Number(e.target.value))}
              className="tabular-nums w-full rounded-lg border border-gray-300 bg-white px-2.5 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-[#374151]">Sand</label>
            <input
              type="number"
              min={0}
              max={unit === "percent" ? 100 : 1000}
              value={sand}
              onChange={(e) => setSand(Number(e.target.value))}
              className="tabular-nums w-full rounded-lg border border-gray-300 bg-white px-2.5 py-2 text-xs text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
            />
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50/70 p-3">
          <span className="text-xs font-medium text-[#111827]">Derived SoilType:</span>
          <span className="rounded-full bg-[#DCFCE7] text-[#15803D] border border-emerald-300 px-3 py-0.5 text-xs font-bold">
            {SOIL_TYPE_LABELS[lang][derived]} ({derived})
          </span>
        </div>

        <button
          type="button"
          onClick={() => {
            onApply(derived);
            onClose();
          }}
          className="mt-4 w-full rounded-xl bg-[#00291B] px-4 py-2.5 text-xs font-bold text-white hover:bg-[#04421B] shadow-sm transition"
        >
          {t.usdaApply}
        </button>
      </div>
    </div>
  );
}
