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
}: {
  degradedMode: DegradedModeMetadata | null | undefined;
  lang: Language;
}) {
  if (!degradedMode) return null;
  const t = UI_DICT[lang].comparison;

  return (
    <div
      role="alert"
      data-testid="degraded-mode-banner"
      className="no-print mb-4 rounded-xl border-2 border-amber-500 bg-amber-50 px-4 py-3 text-[#111827] shadow-sm"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <WarningOctagon size={24} weight="fill" className="mt-0.5 shrink-0 text-amber-600" />
          <div>
            <p className="font-heading text-sm font-extrabold tracking-wide text-amber-900">
              {t.degradedBannerTitle}
            </p>
            <p className="mt-1 text-xs text-[#374151]">
              Showing replayed prior analysis{" "}
              <code dir="ltr" className="rounded bg-white border border-amber-200 px-1.5 py-0.5 text-amber-800 font-bold">
                {degradedMode.source_analysis_id}
              </code>{" "}
              (dataset{" "}
              <code dir="ltr" className="rounded bg-white border border-amber-200 px-1.5 py-0.5 text-[#111827]">
                {degradedMode.dataset_version}
              </code>
              , generated <span dir="ltr">{degradedMode.created_at}</span>).
            </p>
          </div>
        </div>
        <span className="tabular-nums rounded-full bg-amber-600 px-3 py-1 text-xs font-bold text-white shadow-xs">
          {t.degradedAge}: {formatAgeSeconds(degradedMode.age_seconds)} ({degradedMode.age_seconds}s)
        </span>
      </div>
    </div>
  );
}

export function WarningsBanner({
  warnings,
  lang,
}: {
  warnings: WarningNotice[];
  lang: Language;
}) {
  if (!warnings || warnings.length === 0) return null;

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
            className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-amber-200 bg-amber-50/70 px-4 py-2.5 text-xs text-[#111827]"
          >
            <div className="flex items-start gap-2.5">
              <Warning size={18} weight="fill" className="mt-0.5 shrink-0 text-amber-600" />
              <div>
                <p className="font-bold text-[#111827]">{copy.label}</p>
                <p className="mt-0.5 text-[#374151]">{copy.description}</p>
              </div>
            </div>
            {w.fields && w.fields.length > 0 && (
              <span
                dir="ltr"
                className={
                  isUnverified
                    ? "rounded-full bg-[#FEF3C7] text-[#D97706] border border-amber-300 font-bold px-2.5 py-0.5 text-[11px]"
                    : "rounded-full bg-white border border-gray-200 px-2.5 py-0.5 text-[11px] font-semibold text-[#137135]"
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
}: {
  error: unknown;
  lang: Language;
  onRetry?: () => void;
  onOpenClaimAccount?: () => void;
  onGoToSelectField?: () => void;
}) {
  if (!error) return null;
  const info = presentApiError(error, lang);

  return (
    <div
      role="alert"
      data-testid={`api-error-${info.code}`}
      className="my-3 rounded-xl border-2 border-red-500 bg-white p-4 text-[#111827] shadow-sm"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <WarningOctagon size={22} weight="fill" className="mt-0.5 shrink-0 text-red-600" />
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-heading text-sm font-bold text-[#111827]">{info.title}</h3>
              <code
                dir="ltr"
                className="rounded bg-red-100 text-red-800 border border-red-200 px-2 py-0.5 text-[11px] font-bold"
              >
                {info.code}
              </code>
            </div>
            <p className="mt-1 text-xs text-[#374151]">{info.guidance}</p>
            <p className="mt-1 text-[11px] text-[#6B7280]">{info.message}</p>
            {info.requestId && (
              <p className="mt-1 text-[11px] text-[#6B7280]">
                Request ID: <code dir="ltr">{info.requestId}</code>
              </p>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {info.isGuestLimit && onOpenClaimAccount && (
            <button
              type="button"
              onClick={onOpenClaimAccount}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#00291B] text-white font-bold px-3 py-1.5 text-xs hover:bg-[#04421B] shadow-sm"
            >
              <UserPlus size={15} weight="bold" />
              Create Free Account & Claim Data
            </button>
          )}
          {info.isBoundaryError && onGoToSelectField && (
            <button
              type="button"
              onClick={onGoToSelectField}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#00291B] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#04421B] shadow-sm"
            >
              <Compass size={15} weight="bold" />
              Adjust Parcel on Map
            </button>
          )}
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[#E5E7EB] bg-white px-3 py-1.5 text-xs font-semibold text-[#111827] hover:bg-gray-50 shadow-sm"
            >
              <ArrowSquareOut size={15} />
              Retry
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
