"use client";

import React, { useState } from "react";

interface Segment {
  label: string;
  percentage: number;
  color: string;
}

export const DEFAULT_SEGMENTS: Segment[] = [
  { label: "Irrigation Systems", percentage: 30, color: "#003523" },
  { label: "Crop Nutrition", percentage: 23, color: "#18664C" },
  { label: "Equipment Maintenance", percentage: 18, color: "#AFDA8A" },
  { label: "Pest Control", percentage: 17, color: "#D0A034" },
  { label: "Logistics & Distribution", percentage: 12, color: "#BC4C4B" },
];

export function ResourceDonutChart() {
  const [timeRange, setTimeRange] = useState<"Week" | "Month" | "Year">("Week");

  // SVG Donut geometry
  const size = 120;
  const strokeWidth = 24;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  let cumulativeOffset = 0;

  return (
    <div className="rounded-2xl border border-[#E5E7EB] bg-white p-4 shadow-sm select-none">
      {/* Header and Filter Pill */}
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold text-[#111827]">Resource Monitoring</h3>

        {/* Segmented Control */}
        <div className="flex items-center rounded-full bg-[#F3F4F6] p-0.5 text-[10px] font-medium text-[#6B7280]">
          {(["Week", "Month", "Year"] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setTimeRange(tab)}
              className={`rounded-full px-2 py-0.5 transition ${
                timeRange === tab
                  ? "bg-white font-bold text-[#111827] shadow-xs"
                  : "hover:text-[#111827]"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* Grid: Legend Left + Donut Right */}
      <div className="mt-3.5 flex items-center justify-between gap-3">
        {/* Left Column: Legend */}
        <div className="flex-1 space-y-1.5 text-[10.5px]">
          {DEFAULT_SEGMENTS.map((seg) => (
            <div key={seg.label} className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 min-w-0">
                <span
                  className="h-2 w-2 shrink-0 rounded-xs"
                  style={{ backgroundColor: seg.color }}
                />
                <span className="truncate text-[#374151] font-medium">{seg.label}</span>
              </div>
              <span className="shrink-0 text-[#111827] font-semibold tabular-nums ml-1">
                {seg.percentage}%
              </span>
            </div>
          ))}
        </div>

        {/* Right Column: Native SVG Donut Chart */}
        <div className="relative shrink-0 flex items-center justify-center">
          <svg
            width={size}
            height={size}
            viewBox={`0 0 ${size} ${size}`}
            className="transform -rotate-90"
          >
            {DEFAULT_SEGMENTS.map((seg, idx) => {
              const dashLength = (seg.percentage / 100) * circumference;
              const dashOffset = -cumulativeOffset;
              cumulativeOffset += dashLength;

              return (
                <circle
                  key={idx}
                  cx={size / 2}
                  cy={size / 2}
                  r={radius}
                  fill="transparent"
                  stroke={seg.color}
                  strokeWidth={strokeWidth}
                  strokeDasharray={`${dashLength} ${circumference - dashLength}`}
                  strokeDashoffset={dashOffset}
                  strokeLinecap="butt"
                />
              );
            })}
          </svg>
          {/* Inner Donut Hole Text */}
          <div className="absolute text-center">
            <span className="text-[11px] font-bold text-[#111827]">100%</span>
          </div>
        </div>
      </div>
    </div>
  );
}
