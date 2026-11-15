"use client";

import React from "react";
import {
  MapPin,
  Sun,
  Drop,
  CloudRain,
  Wind,
} from "@phosphor-icons/react";

interface WeatherWidgetProps {
  location?: string;
  temperature?: string;
  condition?: string;
  timeDate?: string;
  humidity?: string;
  rainForecast?: string;
  windSpeed?: string;
}

export function WeatherWidget({
  location = "Purwokerto, Central Java, Indonesia",
  temperature = "26°C",
  condition = "Sunny Day",
  timeDate = "8.45 AM | Jan 26",
  humidity = "35%",
  rainForecast = "26°C",
  windSpeed = "8m/s",
}: WeatherWidgetProps) {
  return (
    <div className="rounded-2xl border border-[#E5E7EB] bg-white p-4 shadow-sm select-none">
      {/* Top Location Header */}
      <div className="flex items-center gap-1.5 text-xs font-medium text-[#111827]">
        <MapPin size={14} weight="bold" className="text-[#137135] shrink-0" />
        <span className="truncate">{location}</span>
      </div>

      {/* Hero Temperature & Condition */}
      <div className="mt-3 flex items-center justify-between">
        <div className="text-4xl font-extrabold tracking-tight text-[#111827]">
          {temperature}
        </div>
        <div className="text-right">
          <div className="flex items-center justify-end gap-1.5">
            <Sun size={20} weight="fill" className="text-[#D0A034]" />
            <span className="text-xs font-bold text-[#111827]">{condition}</span>
          </div>
          <p className="text-[10px] text-[#6B7280]">{timeDate}</p>
        </div>
      </div>

      {/* 3-Column Weather Metrics Sub-card */}
      <div className="mt-3.5 grid grid-cols-3 divide-x divide-[#E5E7EB] rounded-xl bg-[#F9FAFB] p-2 text-center">
        {/* Humidity */}
        <div className="px-1 flex flex-col items-center">
          <div className="flex items-center gap-1 text-[10px] text-[#6B7280]">
            <Drop size={12} weight="bold" className="text-[#137135]" />
            <span>Humidity</span>
          </div>
          <span className="mt-0.5 text-xs font-bold text-[#111827]">{humidity}</span>
        </div>

        {/* Rain Forecast */}
        <div className="px-1 flex flex-col items-center">
          <div className="flex items-center gap-1 text-[10px] text-[#6B7280]">
            <CloudRain size={12} weight="bold" className="text-[#5FA87D]" />
            <span>Rain</span>
          </div>
          <span className="mt-0.5 text-xs font-bold text-[#111827]">{rainForecast}</span>
        </div>

        {/* Wind */}
        <div className="px-1 flex flex-col items-center">
          <div className="flex items-center gap-1 text-[10px] text-[#6B7280]">
            <Wind size={12} weight="bold" className="text-[#6B7280]" />
            <span>Wind</span>
          </div>
          <span className="mt-0.5 text-xs font-bold text-[#111827]">{windSpeed}</span>
        </div>
      </div>
    </div>
  );
}
