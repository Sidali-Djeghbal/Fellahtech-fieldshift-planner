"use client";

import React from "react";
import { ArrowUpRight } from "@phosphor-icons/react";

const INTENSITY_COLORS = [
  "#EFFEDF", // L0 Minimal
  "#D4F9B3", // L1 Low
  "#98EA70", // L2 Medium
  "#1B8A5F", // L3 High
  "#072B1F", // L4 Peak
];

// 7 days x 6 hours intensity matrix sample reproducing the mockup distribution
const MATRIX_LEVELS: number[][] = [
  // 1 pm: Mon..Sun
  [0, 1, 2, 4, 3, 1, 0],
  // 2 pm
  [1, 2, 3, 4, 4, 2, 1],
  // 3 pm
  [2, 3, 4, 4, 3, 2, 0],
  // 4 pm
  [3, 4, 4, 3, 2, 1, 1],
  // 5 pm
  [2, 3, 3, 2, 1, 0, 0],
  // 6 pm
  [1, 2, 2, 1, 0, 0, 0],
];

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOURS = ["1 pm", "2 pm", "3 pm", "4 pm", "5 pm", "6 pm"];

export function WeeklyHeatmap() {
  return (
    <div className="rounded-2xl border border-[#E5E7EB] bg-white p-4 shadow-sm select-none">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold text-[#111827]">Weekly Performance</h3>
        <button
          type="button"
          title="View detailed performance"
          className="text-[#111827] hover:text-[#137135] transition"
        >
          <ArrowUpRight size={14} weight="bold" />
        </button>
      </div>

      {/* Grid Table */}
      <div className="mt-3">
        {/* Days Header */}
        <div className="grid grid-cols-[32px_repeat(7,1fr)] gap-1 text-center">
          <span />
          {DAYS.map((day) => (
            <span key={day} className="text-[9.5px] font-medium text-[#6B7280]">
              {day}
            </span>
          ))}
        </div>

        {/* Matrix Rows */}
        <div className="mt-1 space-y-1">
          {HOURS.map((hour, rIdx) => (
            <div key={hour} className="grid grid-cols-[32px_repeat(7,1fr)] items-center gap-1">
              <span className="text-[9px] font-medium text-[#6B7280] text-left">
                {hour}
              </span>
              {MATRIX_LEVELS[rIdx].map((lvl, cIdx) => (
                <div
                  key={cIdx}
                  title={`${DAYS[cIdx]} at ${hour}: Level ${lvl}`}
                  className="h-4 w-full rounded-xs transition hover:opacity-80"
                  style={{ backgroundColor: INTENSITY_COLORS[lvl] }}
                />
              ))}
            </div>
          ))}
        </div>

        {/* Bottom Legend */}
        <div className="mt-3 flex items-center justify-end gap-1 text-[9.5px] text-[#6B7280]">
          <span>Less</span>
          {INTENSITY_COLORS.slice(1).map((col, idx) => (
            <span
              key={idx}
              className="h-2.5 w-2.5 rounded-xs"
              style={{ backgroundColor: col }}
            />
          ))}
          <span>More</span>
        </div>
      </div>
    </div>
  );
}
