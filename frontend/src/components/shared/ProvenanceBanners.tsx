"use client";

import React from "react";
import { Warning, WarningOctagon, ArrowSquareOut, Compass, UserPlus } from "@phosphor-icons/react";
import type { DegradedModeMetadata, Language, WarningNotice } from "@/lib/schemas";
import { getWarningCopy, presentApiError } from "@/lib/api/errors";
import { UI_DICT } from "@/lib/i18n";

function formatAgeSeconds(seconds: number): string {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  if (hrs > 0) return `${hrs}h ${mins}m`;
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

export function DegradedReplayBanner({
  degradedMode,
  lang,
  theme = "light",
}: {
  degradedMode: DegradedModeMetadata | null | undefined;
  lang: Language;
  theme?: "light" | "dark";
}) {
  if (!degradedMode) return null;
  const t = UI_DICT[lang].comparison;
  const isDark = theme === "dark";

  return (
    <div
      role="alert"
      data-testid="degraded-mode-banner"
      className={`no-print mb-4 rounded-2xl border px-4 py-3.5 shadow-xs backdrop-blur-md ${
        isDark
          ? "border-[#F59E0B]/35 bg-[#F59E0B]/12 text-[#F5F7F5]"
          : "border-amber-400/60 bg-amber-50/85 text-[#18221D]"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <WarningOctagon
            size={22}
            weight="fill"
            className={`mt-0.5 shrink-0 ${isDark ? "text-[#FCD34D]" : "text-amber-600"}`}
            aria-hidden="true"
          />
          <div>
            <p
              className={`font-heading text-sm font-semibold tracking-tight ${
                isDark ? "text-[#FDE68A]" : "text-amber-950"
              }`}
            >
              {t.degradedBannerTitle}
            </p>
            <p
              className={`mt-1 max-w-[65ch] text-xs ${
                isDark ? "text-[#D1DBD3]" : "text-[#39453F]"
              }`}
            >
              {lang === "fr"
                ? "Affichage d'une analyse antérieure rejouée "
                : lang === "ar"
                  ? "عرض نتائج تحليل سابق مُعاد استخدامه "
                  : "Showing replayed prior analysis "}
              <code
                dir="ltr"
                className={`rounded-md px-1.5 py-0.5 font-mono ring-1 ${
                  isDark
                    ? "bg-black/30 text-[#FCD34D] ring-[#F59E0B]/30"
                    : "bg-white/85 text-amber-900 ring-amber-300/60"
                }`}
              >
                {degradedMode.source_analysis_id}
              </code>{" "}
              ({lang === "fr" ? "jeu" : lang === "ar" ? "البيانات" : "dataset"}{" "}
              <code
                dir="ltr"
                className={`rounded-md px-1.5 py-0.5 font-mono ring-1 ${
                  isDark
                    ? "bg-black/30 text-[#F5F7F5] ring-[#F59E0B]/30"
                    : "bg-white/85 text-[#18221D] ring-amber-300/60"
                }`}
              >
                {degradedMode.dataset_version}
              </code>
              , {lang === "fr" ? "généré le" : lang === "ar" ? "بتاريخ" : "generated"}{" "}
              <span dir="ltr">{degradedMode.created_at}</span>).
            </p>
          </div>
        </div>
        <span className="tabular-nums rounded-full bg-amber-600 px-3 py-1 text-xs font-semibold text-white shadow-xs">
          {t.degradedAge}: {formatAgeSeconds(degradedMode.age_seconds)} ({degradedMode.age_seconds}s)
        </span>
      </div>
    </div>
  );
}

export function WarningsBanner({
  warnings,
  lang,
  theme = "light",
}: {
  warnings: WarningNotice[];
  lang: Language;
  theme?: "light" | "dark";
}) {
  if (!warnings || warnings.length === 0) return null;
  const isDark = theme === "dark";

  const unique = Array.from(
    new Map(warnings.map((w) => [w.code, w])).values()
  );

  return (
    <div className="no-print mb-4 flex flex-col gap-2">
      {unique.map((w) => {
        const copy = getWarningCopy(w.code, lang);
        const isUnverified = w.code === "DEMO_PARCEL_UNVERIFIED";
        return (
          <div
            key={w.code}
            data-testid={`warning-${w.code}`}
            className={`flex flex-wrap items-center justify-between gap-2 rounded-2xl border px-4 py-3 text-xs backdrop-blur-md ${
              isDark
                ? "border-[#F59E0B]/30 bg-[#F59E0B]/10 text-[#F5F7F5]"
                : "border-amber-300/60 bg-amber-50/75 text-[#18221D]"
            }`}
          >
            <div className="flex items-start gap-2.5">
              <Warning
                size={18}
                weight="fill"
                className={`mt-0.5 shrink-0 ${isDark ? "text-[#FCD34D]" : "text-amber-600"}`}
                aria-hidden="true"
              />
              <div>
                <p className={`font-semibold ${isDark ? "text-[#F5F7F5]" : "text-[#18221D]"}`}>
                  {copy.label}
                </p>
                <p className={`mt-0.5 max-w-[65ch] ${isDark ? "text-[#9CA89E]" : "text-[#5C6962]"}`}>
                  {copy.description}
                </p>
              </div>
            </div>
            {w.fields && w.fields.length > 0 && (
              <span
                dir="ltr"
                className={
                  isUnverified
                    ? isDark
                      ? "rounded-full bg-[#F59E0B]/20 px-2.5 py-0.5 text-[11px] font-semibold text-[#FDE68A] ring-1 ring-[#F59E0B]/35"
                      : "rounded-full bg-[#FEF3C7] px-2.5 py-0.5 text-[11px] font-semibold text-amber-800 ring-1 ring-amber-300/80"
                    : isDark
                      ? "rounded-full bg-[#22C55E]/15 px-2.5 py-0.5 text-[11px] font-semibold text-[#86EFAC] ring-1 ring-[#4ADE80]/30"
                      : "rounded-full bg-white/85 px-2.5 py-0.5 text-[11px] font-semibold text-[#176B4A] ring-1 ring-[#0B3D2E]/12"
                }
              >
                {w.fields.join(", ")}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function ApiErrorCard({
  error,
  lang,
  onRetry,
  onOpenClaimAccount,
  onGoToSelectField,
  theme = "light",
}: {
  error: unknown;
  lang: Language;
  onRetry?: () => void;
  onOpenClaimAccount?: () => void;
  onGoToSelectField?: () => void;
  theme?: "light" | "dark";
}) {
  if (!error) return null;
  const info = presentApiError(error, lang);
  const isDark = theme === "dark";

  return (
    <div
      role="alert"
      data-testid={`api-error-${info.code}`}
      className={`my-3 rounded-3xl border p-5 backdrop-blur-md ${
        isDark
          ? "border-red-400/35 bg-red-950/55 text-[#F5F7F5]"
          : "fs-liquid-panel border-red-300/70 bg-red-50/65 text-[#18221D]"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <WarningOctagon
            size={22}
            weight="fill"
            className={`mt-0.5 shrink-0 ${isDark ? "text-red-400" : "text-red-600"}`}
            aria-hidden="true"
          />
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3
                className={`font-heading text-sm font-semibold ${
                  isDark ? "text-[#F5F7F5]" : "text-[#18221D]"
                }`}
              >
                {info.title}
              </h3>
              <code
                dir="ltr"
                className={`rounded-md px-2 py-0.5 font-mono text-[11px] font-semibold ring-1 ${
                  isDark
                    ? "bg-red-500/20 text-red-200 ring-red-400/30"
                    : "bg-red-100/90 text-red-800 ring-red-200"
                }`}
              >
                {info.code}
              </code>
            </div>
            <p className={`mt-1 max-w-[65ch] text-xs ${isDark ? "text-[#E4EBE5]" : "text-[#39453F]"}`}>
              {info.guidance}
            </p>
            <p className={`mt-1 text-[11px] ${isDark ? "text-[#9CA89E]" : "text-[#5C6962]"}`}>
              {info.message}
            </p>
            {info.requestId && (
              <p className={`mt-1 text-[11px] ${isDark ? "text-[#9CA89E]" : "text-[#5C6962]"}`}>
                {lang === "fr" ? "ID requête :" : lang === "ar" ? "معرّف الطلب:" : "Request ID:"}{" "}
                <code dir="ltr">{info.requestId}</code>
              </p>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {info.isGuestLimit && onOpenClaimAccount && (
            <button
              type="button"
              onClick={onOpenClaimAccount}
              className={`inline-flex min-h-10 items-center gap-1.5 rounded-full ps-3 pe-3.5 text-xs font-semibold shadow-sm transition-[transform,background-color] active:not-disabled:scale-[0.96] ${
                isDark
                  ? "bg-[#FFFFFF] text-[#111713] hover:bg-[#ECFDF5]"
                  : "bg-[#0B3D2E] text-white hover:bg-[#176B4A]"
              }`}
            >
              <UserPlus size={15} weight="bold" aria-hidden="true" />
              {lang === "fr"
                ? "Créer un compte gratuit & transférer"
                : lang === "ar"
                  ? "إنشاء حساب مجاني وحفظ البيانات"
                  : "Create Free Account & Claim Data"}
            </button>
          )}
          {info.isBoundaryError && onGoToSelectField && (
            <button
              type="button"
              onClick={onGoToSelectField}
              className={`inline-flex min-h-10 items-center gap-1.5 rounded-full ps-3 pe-3.5 text-xs font-semibold shadow-sm transition-[transform,background-color] active:not-disabled:scale-[0.96] ${
                isDark
                  ? "bg-[#FFFFFF] text-[#111713] hover:bg-[#ECFDF5]"
                  : "bg-[#0B3D2E] text-white hover:bg-[#176B4A]"
              }`}
            >
              <Compass size={15} weight="bold" aria-hidden="true" />
              {lang === "fr"
                ? "Ajuster la parcelle sur la carte"
                : lang === "ar"
                  ? "تعديل حدود القطعة على الخريطة"
                  : "Adjust Parcel on Map"}
            </button>
          )}
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className={`inline-flex min-h-10 items-center gap-1.5 rounded-full ps-3 pe-3.5 text-xs font-semibold transition-[transform,background-color] active:not-disabled:scale-[0.96] ${
                isDark
                  ? "border border-white/15 bg-white/[0.08] text-[#F5F7F5] hover:bg-white/[0.14]"
                  : "fs-liquid-pill text-[#18221D]"
              }`}
            >
              <ArrowSquareOut size={15} aria-hidden="true" />
              {lang === "fr" ? "Réessayer" : lang === "ar" ? "إعادة المحاولة" : "Retry"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
