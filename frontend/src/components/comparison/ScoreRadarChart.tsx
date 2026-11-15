"use client";

import React from "react";
import { SCORE_LABELS } from "@/lib/i18n";
import type { Language, Strategy } from "@/lib/schemas";

const AXES: Array<
  | "water_efficiency"
  | "erosion_protection"
  | "organic_matter_gain"
  | "nitrogen_contribution"
  | "pest_cycle_disruption"
  | "income_forage_value"
  | "priority_fit"
> = [
  "water_efficiency",
  "erosion_protection",
  "organic_matter_gain",
  "nitrogen_contribution",
  "pest_cycle_disruption",
  "income_forage_value",
  "priority_fit",
];

export function ScoreRadarChart({
  baseline,
  focused,
  lang,
  plainMode,
  variant = "light",
}: {
  baseline?: Strategy;
  focused?: Strategy;
  lang: Language;
  plainMode: boolean;
  variant?: "light" | "dark";
}) {
  const isDark = variant === "dark";
  const ringStroke = isDark ? "rgba(255, 255, 255, 0.14)" : "rgba(0, 41, 27, 0.12)";
  const axisStroke = isDark ? "rgba(255, 255, 255, 0.16)" : "rgba(0, 41, 27, 0.15)";
  const labelFill = isDark ? "#D1DBD3" : "#374151";
  const focusedStroke = isDark ? "#22C55E" : "#137135";
  const focusedFill = isDark ? "rgba(34, 197, 94, 0.24)" : "rgba(19, 113, 53, 0.22)";
  const baselineStroke = isDark ? "#F59E0B" : "#9CA3AF";
  const baselineFill = isDark ? "rgba(245, 158, 11, 0.14)" : "rgba(107, 114, 128, 0.12)";

  const size = 340;
  const cx = size / 2;
  const cy = size / 2;
  const maxR = 86;

  const pointAt = (index: number, score: number): [number, number] => {
    const angle = (Math.PI * 2 * index) / AXES.length - Math.PI / 2;
    const r = (Math.max(0, Math.min(100, score)) / 100) * maxR;
    return [
      Number((cx + r * Math.cos(angle)).toFixed(2)),
      Number((cy + r * Math.sin(angle)).toFixed(2)),
    ];
  };

  const toPolygon = (strategy?: Strategy) => {
    if (!strategy) return "";
    return AXES.map((key, idx) => pointAt(idx, strategy.scores[key]).join(",")).join(" ");
  };

  return (
    <div className="flex flex-col items-center select-none">
      <svg
        viewBox={`0 0 ${size} ${size}`}
        className="h-64 w-full max-w-[340px]"
        role="img"
        aria-label="7-axis agronomic strategy score comparison"
      >
        {[25, 50, 75, 100].map((ring) => (
          <polygon
            key={ring}
            points={AXES.map((_, idx) => pointAt(idx, ring).join(",")).join(" ")}
            fill="none"
            stroke={ringStroke}
            strokeWidth="1"
          />
        ))}
        {AXES.map((key, idx) => {
          const angle = (Math.PI * 2 * idx) / AXES.length - Math.PI / 2;
          const cos = Math.cos(angle);
          const anchor = cos > 0.22 ? "start" : cos < -0.22 ? "end" : "middle";
          const [x2, y2] = pointAt(idx, 100);
          const [lx, ly] = pointAt(idx, 114);
          const labelText = plainMode
            ? SCORE_LABELS[lang][key].plain
            : SCORE_LABELS[lang][key].tech;
          return (
            <g key={key}>
              <line
                x1={cx}
                y1={cy}
                x2={x2}
                y2={y2}
                stroke={axisStroke}
                strokeWidth="1"
              />
              <text
                x={lx}
                y={ly}
                fill={labelFill}
                fontSize="8.5"
                fontWeight="600"
                textAnchor={anchor}
                dominantBaseline="middle"
              >
                {labelText.slice(0, 26)}
              </text>
            </g>
          );
        })}
        {baseline && (
          <polygon
            points={toPolygon(baseline)}
            fill={baselineFill}
            stroke={baselineStroke}
            strokeWidth="1.8"
            strokeDasharray="4 3"
          />
        )}
        {focused && (
          <polygon
            points={toPolygon(focused)}
            fill={focusedFill}
            stroke={focusedStroke}
            strokeWidth="2.4"
          />
        )}
      </svg>

      <div className="mt-2 flex flex-wrap justify-center gap-4 text-[11px]">
        {baseline && (
          <span
            className={`inline-flex items-center gap-1.5 ${
              isDark ? "text-[#FCD34D]" : "text-[#6B7280]"
            }`}
          >
            <span
              className={`h-2.5 w-2.5 rounded-full border ${
                isDark ? "border-[#F59E0B]" : "border-gray-400"
              }`}
            />
            {baseline.name}
          </span>
        )}
        {focused && (
          <span
            className={`inline-flex items-center gap-1.5 font-bold ${
              isDark ? "text-[#86EFAC]" : "text-[#137135]"
            }`}
          >
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                isDark ? "bg-[#22C55E]" : "bg-[#137135]"
              }`}
            />
            {focused.name}
          </span>
        )}
      </div>
    </div>
  );
}
