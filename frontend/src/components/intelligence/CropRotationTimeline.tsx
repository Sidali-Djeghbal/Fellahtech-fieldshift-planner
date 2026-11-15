"use client";

import React, { useState } from "react";
import { CalendarCheck, Leaf, NotePencil } from "@phosphor-icons/react";
import { CATEGORY_STYLE_MAP, resolveCropDisplayName } from "@/lib/analysis/workspaceAnalysis";
import { CROP_ROLE_LABELS, MONTH_SHORT, SEASON_LABELS } from "@/lib/i18n";
import { INTELLIGENCE_I18N } from "@/lib/i18n/intelligence";
import type { CropItem, Language, SeasonPlan } from "@/lib/schemas";

interface CropRotationTimelineProps {
  strategyId: string;
  seasons: SeasonPlan[];
  catalogMap: Map<string, CropItem>;
  lang: Language;
}

export function CropRotationTimeline({
  strategyId,
  seasons,
  catalogMap,
  lang,
}: CropRotationTimelineProps) {
  const dict = INTELLIGENCE_I18N[lang];
  const t = dict.timeline;
  const ordered = [...seasons].sort((a, b) => a.order - b.order);
  const [selectedOrder, setSelectedOrder] = useState<number>(ordered[0]?.order ?? 1);

  if (ordered.length === 0) {
    return (
      <div className="fs-liquid-well rounded-2xl p-4 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">
        {t.emptyNotice}
      </div>
    );
  }

  const activeSeason = ordered.find((s) => s.order === selectedOrder) ?? ordered[0];
  const months = MONTH_SHORT[lang];

  return (
    <div
      className="space-y-3"
      data-testid={`rotation-timeline-${strategyId}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="flex items-center gap-1.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-[#111813] dark:text-[#F5F7F5]">
          <CalendarCheck size={15} weight="duotone" className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
          <span>{t.heading}</span>
        </h4>
        <span className="text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">{t.detailHint}</span>
      </div>

      {/* Connected Horizontal Season Rail */}
      <div className="fs-liquid-well overflow-x-auto rounded-2xl p-1.5">
        <div className="flex min-w-max gap-1.5">
          {ordered.map((s) => {
            const isFocused = s.order === activeSeason.order;
            const catStyle = CATEGORY_STYLE_MAP[s.category];
            const cropLabel = resolveCropDisplayName(s.crop_id, s.crop_name, catalogMap, lang);

            return (
              <button
                key={`${s.order}-${s.crop_id}`}
                type="button"
                onClick={() => setSelectedOrder(s.order)}
                data-testid={`timeline-node-${strategyId}-${s.order}`}
                className={`flex min-w-[185px] flex-1 flex-col justify-between rounded-xl p-3 text-start transition-[transform,background-color,box-shadow] duration-150 ease-out active:scale-[0.98] ${
                  isFocused
                    ? "bg-white shadow-[0_6px_18px_rgba(11,61,46,0.12)] ring-1 ring-[#15803D]/55 dark:bg-white/[0.11] dark:shadow-[0_6px_18px_rgba(0,0,0,0.35)] dark:ring-[#86EFAC]/55"
                    : "hover:bg-[#111813]/[0.05] dark:hover:bg-white/[0.06]"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[10px] font-semibold text-[#4A5A4E] dark:text-[#9CA89E]">
                      {t.orderPrefix} {s.order}
                    </span>
                    <span className="fs-liquid-well rounded-full px-2 py-0.5 font-mono text-[10px] font-medium tabular-nums text-[#111813] dark:text-[#F5F7F5]">
                      {SEASON_LABELS[lang][s.season]} {s.year}
                    </span>
                  </div>

                  <p className="mt-1.5 line-clamp-2 text-sm font-semibold text-[#111813] dark:text-[#F5F7F5]">
                    {cropLabel}
                  </p>
                </div>

                <div className="mt-2.5 space-y-1.5">
                  <span
                    className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${catStyle.badgeClass}`}
                  >
                    <span className={`h-1.5 w-1.5 rounded-full ${catStyle.dotClass}`} aria-hidden="true" />
                    {dict.categories[s.category]}
                  </span>

                  <div className="flex items-center justify-between gap-2 text-[10px] text-[#4A5A4E] dark:text-[#9CA89E]">
                    <span className="truncate font-medium">
                      {CROP_ROLE_LABELS[lang][s.role]}
                    </span>
                    <span dir="ltr" className="tabular-nums font-mono">
                      {s.planting_month ? months[s.planting_month - 1] : "—"}
                    </span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Selected Season Detail Strip */}
      <div className="fs-liquid-well rounded-2xl p-4 text-xs">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#22C55E]/15 text-[#15803D] dark:text-[#86EFAC]">
              <Leaf size={16} weight="duotone" aria-hidden="true" />
            </span>
            <div>
              <p className="font-semibold text-[#111813] dark:text-[#F5F7F5]">
                {resolveCropDisplayName(
                  activeSeason.crop_id,
                  activeSeason.crop_name,
                  catalogMap,
                  lang
                )}
              </p>
              <p className="text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
                {SEASON_LABELS[lang][activeSeason.season]} {activeSeason.year} ·{" "}
                {t.plantingMonthLabel}:{" "}
                <strong className="text-[#111813] dark:text-[#F5F7F5]">
                  {activeSeason.planting_month
                    ? `${months[activeSeason.planting_month - 1]} (${activeSeason.planting_month})`
                    : t.monthNotSet}
                </strong>
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-1.5 text-[10px] font-semibold">
            <span
              className={`rounded-full px-2.5 py-0.5 ${
                CATEGORY_STYLE_MAP[activeSeason.category].badgeClass
              }`}
            >
              {t.categoryLabel}: {dict.categories[activeSeason.category]}
            </span>
            <span className="fs-liquid-pill rounded-full px-2.5 py-0.5 text-[#111813] dark:text-[#F5F7F5]">
              {t.roleLabel}: {CROP_ROLE_LABELS[lang][activeSeason.role]}
            </span>
            <span className="fs-liquid-pill rounded-full px-2.5 py-0.5 text-[#4A5A4E] dark:text-[#9CA89E]">
              {t.statusLabel}: {dict.strategies.statusBadge[activeSeason.selection_status]}
            </span>
          </div>
        </div>

        <div className="mt-3 flex items-start gap-2 border-t border-[#111813]/10 pt-2.5 text-[11px] text-[#243227] dark:border-white/10 dark:text-[#E4EBE5]">
          <NotePencil size={14} className="mt-0.5 shrink-0 text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
          <div>
            <span className="font-semibold">{t.notesLabel}: </span>
            <span className="text-[#4A5A4E] dark:text-[#9CA89E]">
              {activeSeason.notes ? activeSeason.notes : t.noNotes}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
