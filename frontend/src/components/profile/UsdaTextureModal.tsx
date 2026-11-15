"use client";

import React, { useEffect, useRef, useState } from "react";
import { Calculator, X } from "@phosphor-icons/react";
import { SOIL_TYPE_LABELS, UI_DICT } from "@/lib/i18n";
import type { Language, SoilType } from "@/lib/schemas";
import { classifyUsdaSoilTexture } from "@/lib/validation";

interface UsdaTextureModalProps {
  open: boolean;
  lang: Language;
  onClose: () => void;
  onApply: (soilType: Exclude<SoilType, "unknown">) => void;
  theme?: "light" | "dark";
}

export function UsdaTextureModal({
  open,
  lang,
  onClose,
  onApply,
  theme = "light",
}: UsdaTextureModalProps) {
  const [unit, setUnit] = useState<"percent" | "g_per_kg">("percent");
  const [clay, setClay] = useState(28);
  const [silt, setSilt] = useState(38);
  const [sand, setSand] = useState(34);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previousFocusRef.current = document.activeElement as HTMLElement | null;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      previousFocusRef.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  const isDark = theme === "dark";
  const t = UI_DICT[lang].farmProfile;
  const derived = classifyUsdaSoilTexture({ clay, silt, sand, unit });

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t.usdaTitle}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 overscroll-contain"
    >
      <button
        type="button"
        tabIndex={-1}
        aria-label="Close USDA texture converter"
        onClick={onClose}
        className="fixed inset-0 bg-black/60 backdrop-blur-sm"
      />
      <div
        className={`relative z-10 w-full max-w-md rounded-3xl p-5 shadow-xl ${
          isDark
            ? "fs-hud-glass text-[#F5F7F5]"
            : "border border-[#E5E7EB] bg-white text-[#111827]"
        }`}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close USDA texture converter"
          className={`absolute end-4 top-4 flex h-9 w-9 items-center justify-center rounded-full ${
            isDark
              ? "fs-liquid-pill text-[#9CA89E] hover:text-[#FFFFFF]"
              : "text-gray-400 hover:text-gray-700"
          }`}
        >
          <X size={18} aria-hidden="true" />
        </button>

        <div className="flex items-center gap-2">
          <Calculator
            size={20}
            className={isDark ? "text-[#86EFAC]" : "text-[#137135]"}
            aria-hidden="true"
          />
          <h3
            className={`font-heading text-base font-bold ${
              isDark ? "text-[#F5F7F5]" : "text-[#111827]"
            }`}
          >
            {t.usdaTitle}
          </h3>
        </div>
        <p className={`mt-1 text-xs ${isDark ? "text-[#9CA89E]" : "text-[#6B7280]"}`}>
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
            className={`min-h-9 rounded-full px-3.5 py-1 text-xs font-bold transition-[background-color,color] ${
              unit === "percent"
                ? isDark
                  ? "bg-[#FFFFFF] text-[#111713]"
                  : "bg-[#00291B] text-white"
                : isDark
                  ? "bg-white/[0.08] text-[#9CA89E] hover:text-[#F5F7F5]"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
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
            className={`min-h-9 rounded-full px-3.5 py-1 text-xs font-bold transition-[background-color,color] ${
              unit === "g_per_kg"
                ? isDark
                  ? "bg-[#FFFFFF] text-[#111713]"
                  : "bg-[#00291B] text-white"
                : isDark
                  ? "bg-white/[0.08] text-[#9CA89E] hover:text-[#F5F7F5]"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            g / kg
          </button>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-3">
          <div>
            <label
              className={`mb-1 block text-xs font-semibold ${
                isDark ? "text-[#E4EBE5]" : "text-[#374151]"
              }`}
            >
              Clay
            </label>
            <input
              type="number"
              min={0}
              max={unit === "percent" ? 100 : 1000}
              value={clay}
              onChange={(e) => setClay(Number(e.target.value))}
              className={`tabular-nums min-h-10 w-full rounded-xl border px-2.5 py-2 text-base sm:text-xs ${
                isDark
                  ? "border-white/12 bg-[#141A16] text-[#F5F7F5]"
                  : "border-gray-300 bg-white text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
              }`}
            />
          </div>
          <div>
            <label
              className={`mb-1 block text-xs font-semibold ${
                isDark ? "text-[#E4EBE5]" : "text-[#374151]"
              }`}
            >
              Silt
            </label>
            <input
              type="number"
              min={0}
              max={unit === "percent" ? 100 : 1000}
              value={silt}
              onChange={(e) => setSilt(Number(e.target.value))}
              className={`tabular-nums min-h-10 w-full rounded-xl border px-2.5 py-2 text-base sm:text-xs ${
                isDark
                  ? "border-white/12 bg-[#141A16] text-[#F5F7F5]"
                  : "border-gray-300 bg-white text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
              }`}
            />
          </div>
          <div>
            <label
              className={`mb-1 block text-xs font-semibold ${
                isDark ? "text-[#E4EBE5]" : "text-[#374151]"
              }`}
            >
              Sand
            </label>
            <input
              type="number"
              min={0}
              max={unit === "percent" ? 100 : 1000}
              value={sand}
              onChange={(e) => setSand(Number(e.target.value))}
              className={`tabular-nums min-h-10 w-full rounded-xl border px-2.5 py-2 text-base sm:text-xs ${
                isDark
                  ? "border-white/12 bg-[#141A16] text-[#F5F7F5]"
                  : "border-gray-300 bg-white text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
              }`}
            />
          </div>
        </div>

        <div
          className={`mt-4 flex items-center justify-between rounded-2xl border p-3 ${
            isDark
              ? "border-[#4ADE80]/25 bg-[#22C55E]/10"
              : "border-emerald-200 bg-emerald-50/70"
          }`}
        >
          <span
            className={`text-xs font-medium ${isDark ? "text-[#E4EBE5]" : "text-[#111827]"}`}
          >
            Derived SoilType:
          </span>
          <span
            className={`rounded-full border px-3 py-0.5 text-xs font-bold ${
              isDark
                ? "border-[#4ADE80]/30 bg-[#22C55E]/20 text-[#86EFAC]"
                : "border-emerald-300 bg-[#DCFCE7] text-[#15803D]"
            }`}
          >
            {SOIL_TYPE_LABELS[lang][derived]} ({derived})
          </span>
        </div>

        <button
          type="button"
          onClick={() => {
            onApply(derived);
            onClose();
          }}
          className={`mt-4 min-h-10 w-full rounded-full px-4 py-2.5 text-xs font-bold shadow-sm transition-[background-color,transform] active:scale-[0.98] ${
            isDark
              ? "bg-[#FFFFFF] text-[#111713] hover:bg-[#ECFDF5]"
              : "bg-[#00291B] text-white hover:bg-[#04421B]"
          }`}
        >
          {t.usdaApply}
        </button>
      </div>
    </div>
  );
}
