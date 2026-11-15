"use client";

import React, { useState } from "react";
import { X } from "@phosphor-icons/react";

interface FloatingTelemetryProps {
  fieldZone?: string;
  cropType?: string;
  healthScore?: number;
  humidity?: string;
  phLevel?: string;
  hectares?: string;
  waterConsumption?: string;
  fertilizerEfficiency?: string;
  equipmentStatus?: string;
  onClose?: () => void;
}

export function FloatingTelemetry({
  fieldZone = "North Field A1",
  cropType = "Corn Plantation",
  healthScore = 70,
  humidity = "32%",
  phLevel = "2.8",
  hectares = "2.3",
  waterConsumption = "1,250L",
  fertilizerEfficiency = "87%",
  equipmentStatus = "Active",
  onClose,
}: FloatingTelemetryProps) {
  const [closed, setClosed] = useState(false);

  if (closed) return null;

  // Generate 4 concentric dotted arcs for the 180-degree semi-circular health score gauge
  // Angles go from 180 deg (left) to 0 deg (right)
  const rings = [
    { radius: 46, dotsCount: 19 },
    { radius: 40, dotsCount: 16 },
    { radius: 34, dotsCount: 14 },
    { radius: 28, dotsCount: 12 },
  ];

  return (
    <div className="absolute right-4 top-14 z-20 w-[205px] rounded-2xl bg-[#151A06]/92 p-3.5 text-white shadow-2xl backdrop-blur-md border border-white/10 select-none animate-fadeIn">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h4 className="text-[13px] font-bold leading-tight text-white">{fieldZone}</h4>
          <p className="text-[10px] text-gray-400">{cropType}</p>
        </div>
        <button
          type="button"
          onClick={() => {
            setClosed(true);
            onClose?.();
          }}
          className="text-gray-400 hover:text-white transition p-0.5"
          aria-label="Close telemetry"
        >
          <X size={13} weight="bold" />
        </button>
      </div>

      {/* 180° Semi-Circular Dotted Arc Health Score Gauge */}
      <div className="relative mt-2 flex flex-col items-center justify-center">
        <svg width="150" height="85" viewBox="0 0 150 85" className="overflow-visible">
          {rings.map((ring, rIdx) => {
            const dots = [];
            for (let i = 0; i < ring.dotsCount; i++) {
              const fraction = i / (ring.dotsCount - 1);
              // angle from Math.PI (180deg) to 0 (0deg)
              const angle = Math.PI - fraction * Math.PI;
              const cx = (75 + ring.radius * Math.cos(angle)).toFixed(4);
              const cy = (76 - ring.radius * Math.sin(angle)).toFixed(4);

              // 70% threshold
              const isActive = fraction <= healthScore / 100;
              const fill = isActive ? (fraction > 0.4 ? "#4ADE80" : "#548B64") : "rgba(255, 255, 255, 0.45)";

              dots.push(
                <circle
                  key={`${rIdx}-${i}`}
                  cx={cx}
                  cy={cy}
                  r="1.8"
                  fill={fill}
                />
              );
            }
            return <g key={rIdx}>{dots}</g>;
          })}
        </svg>

        {/* Center score readout */}
        <div className="absolute bottom-0 text-center">
          <span className="text-2xl font-black tracking-tight text-white">{healthScore}%</span>
          <p className="text-[9px] font-medium uppercase tracking-wider text-gray-300">
            Health Score
          </p>
        </div>
      </div>

      {/* Horizontal Sub-Metrics Bar */}
      <div className="mt-3.5 grid grid-cols-3 divide-x divide-white/10 rounded-lg bg-white/5 py-1.5 text-center">
        <div>
          <div className="text-[11px] font-bold text-white">{humidity}</div>
          <div className="text-[8.5px] text-gray-400">Humidity</div>
        </div>
        <div>
          <div className="text-[11px] font-bold text-white">{phLevel}</div>
          <div className="text-[8.5px] text-gray-400">Ph Level</div>
        </div>
        <div>
          <div className="text-[11px] font-bold text-white">{hectares}</div>
          <div className="text-[8.5px] text-gray-400">Hectare</div>
        </div>
      </div>

      {/* Divider */}
      <div className="my-2.5 h-px bg-white/10" />

      {/* Key-Value Telemetry Rows */}
      <div className="space-y-1.5 text-[10px]">
        <div className="flex items-center justify-between text-gray-400">
          <span>Water Consumption</span>
          <span className="font-semibold text-white">{waterConsumption}</span>
        </div>
        <div className="flex items-center justify-between text-gray-400">
          <span>Fertilizer Efficiency</span>
          <span className="font-semibold text-white">{fertilizerEfficiency}</span>
        </div>
        <div className="flex items-center justify-between text-gray-400">
          <span>Equipment Status</span>
          <span className="inline-flex items-center gap-1 font-semibold text-white">
            <span className="h-1.5 w-1.5 rounded-full bg-[#4ADE80] animate-pulse" />
            {equipmentStatus}
          </span>
        </div>
      </div>
    </div>
  );
}
