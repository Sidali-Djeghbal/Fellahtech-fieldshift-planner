"use client";

import React from "react";
import { ArrowUpRight, TrendUp } from "@phosphor-icons/react";

interface AnalyticsCardProps {
  headlineMetric?: string;
  trendPercentage?: string;
}

export function AnalyticsCard({
  headlineMetric = "$830,451",
  trendPercentage = "+14.2%",
}: AnalyticsCardProps) {
  return (
    <div className="rounded-2xl border border-[#E5E7EB] bg-white p-4 shadow-sm select-none">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold text-[#111827]">Analytics Performance</h3>
        <button
          type="button"
          title="Open analytics ledger"
          className="text-[#111827] hover:text-[#137135] transition"
        >
          <ArrowUpRight size={14} weight="bold" />
        </button>
      </div>

      {/* Legend Row */}
      <div className="mt-2.5 flex items-center gap-3 text-[10px] text-[#374151]">
        <div className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-xs bg-[#072B1F]" />
          <span>Stocks</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-xs bg-[#1B8A5F]" />
          <span>Bonds</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-xs bg-[#AFDA8A]" />
          <span>Other</span>
        </div>
      </div>

      {/* Headline Metric + Sparkline Trend */}
      <div className="mt-3 flex items-center justify-between">
        <div className="text-xl font-black text-[#111827] tabular-nums">
          {headlineMetric}
        </div>

        {/* Green Trend Pill */}
        <div className="flex items-center gap-1 rounded-full bg-[#DCFCE7] px-2 py-0.5 text-[10px] font-bold text-[#15803D]">
          <TrendUp size={12} weight="bold" />
          <span>{trendPercentage}</span>
        </div>
      </div>

      {/* Mini SVG Sparkline */}
      <div className="mt-2 h-7 w-full">
        <svg viewBox="0 0 200 30" className="h-full w-full overflow-visible">
          <path
            d="M 0 24 Q 30 18, 60 22 T 120 12 T 160 16 T 200 6"
            fill="none"
            stroke="#137135"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      </div>
    </div>
  );
}
