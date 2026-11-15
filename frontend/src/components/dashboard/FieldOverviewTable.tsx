"use client";

import React, { useState } from "react";
import {
  Calendar,
  CaretDown,
  DotsThreeVertical,
  Check,
} from "@phosphor-icons/react";

export interface FieldRecord {
  id: string;
  fieldZone: string;
  cropType: string;
  status: "Healthy" | "Stable" | "Attention";
  soilMoisture: string;
  temperature: string;
  growthStage: string;
}

const DEFAULT_RECORDS: FieldRecord[] = [
  {
    id: "f1",
    fieldZone: "North Field A1",
    cropType: "Corn",
    status: "Healthy",
    soilMoisture: "68%",
    temperature: "26°C",
    growthStage: "Vegetative",
  },
  {
    id: "f2",
    fieldZone: "East Field B2",
    cropType: "Wheat",
    status: "Stable",
    soilMoisture: "72%",
    temperature: "24°C",
    growthStage: "Flowering",
  },
];

interface FieldOverviewTableProps {
  records?: FieldRecord[];
  onSelectField?: (record: FieldRecord) => void;
}

export function FieldOverviewTable({
  records = DEFAULT_RECORDS,
  onSelectField,
}: FieldOverviewTableProps) {
  const [selectedIds, setSelectedIds] = useState<string[]>(["f1"]);

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const toggleAll = () => {
    if (selectedIds.length === records.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(records.map((r) => r.id));
    }
  };

  return (
    <div className="w-full rounded-2xl border border-[#E5E7EB] bg-white p-4 shadow-sm select-none">
      {/* Header Row */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3">
        <h3 className="text-sm font-bold text-[#111827]">
          Field Monitoring Overview
        </h3>

        <div className="flex items-center gap-2">
          {/* Date Pill */}
          <button
            type="button"
            className="flex items-center gap-1.5 rounded-lg border border-[#E5E7EB] bg-white px-2.5 py-1 text-xs font-medium text-[#111827] hover:bg-gray-50 transition"
          >
            <span>June 2026</span>
            <Calendar size={13} className="text-[#6B7280]" />
          </button>

          {/* Filter Pill */}
          <button
            type="button"
            className="flex items-center gap-1.5 rounded-lg border border-[#E5E7EB] bg-white px-2.5 py-1 text-xs font-medium text-[#111827] hover:bg-gray-50 transition"
          >
            <span>Filter</span>
            <CaretDown size={12} className="text-[#6B7280]" />
          </button>

          {/* More Action */}
          <button
            type="button"
            className="flex h-7 w-7 items-center justify-center rounded-lg border border-[#E5E7EB] bg-white text-[#6B7280] hover:text-[#111827] hover:bg-gray-50 transition"
          >
            <DotsThreeVertical size={14} weight="bold" />
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-[#F3F4F6] bg-[#F9FAFB] text-[11px] font-semibold text-[#111827]">
              <th className="py-2.5 pl-3 pr-2 w-8">
                <button
                  type="button"
                  onClick={toggleAll}
                  className="flex h-4 w-4 items-center justify-center rounded bg-[#00291B] text-white transition"
                  aria-label="Select all fields"
                >
                  <Check size={11} weight="bold" />
                </button>
              </th>
              <th className="py-2.5 px-3">Field Zone</th>
              <th className="py-2.5 px-3">Crop Type</th>
              <th className="py-2.5 px-3">Status</th>
              <th className="py-2.5 px-3">Soil Moisture</th>
              <th className="py-2.5 px-3">Temp.</th>
              <th className="py-2.5 px-3">Growth Stage</th>
              <th className="py-2.5 pr-3 pl-2 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#F3F4F6]">
            {records.map((row) => {
              const isSelected = selectedIds.includes(row.id);
              return (
                <tr
                  key={row.id}
                  onClick={() => onSelectField?.(row)}
                  className="hover:bg-gray-50/80 transition cursor-pointer"
                >
                  <td className="py-2.5 pl-3 pr-2">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleSelect(row.id);
                      }}
                      className={`flex h-4 w-4 items-center justify-center rounded border transition ${
                        isSelected
                          ? "bg-[#00291B] border-[#00291B] text-white"
                          : "border-gray-300 bg-white"
                      }`}
                      aria-label={`Select ${row.fieldZone}`}
                    >
                      {isSelected && <Check size={10} weight="bold" />}
                    </button>
                  </td>
                  <td className="py-2.5 px-3 font-semibold text-[#111827]">
                    {row.fieldZone}
                  </td>
                  <td className="py-2.5 px-3 text-[#374151]">{row.cropType}</td>
                  <td className="py-2.5 px-3">
                    {row.status === "Healthy" ? (
                      <span className="inline-flex items-center rounded-full bg-[#DCFCE7] px-2 py-0.5 text-[10px] font-semibold text-[#15803D]">
                        Healthy
                      </span>
                    ) : row.status === "Stable" ? (
                      <span className="inline-flex items-center rounded-full bg-[#FEF3C7] px-2 py-0.5 text-[10px] font-semibold text-[#D97706]">
                        Stable
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-700">
                        Attention
                      </span>
                    )}
                  </td>
                  <td className="py-2.5 px-3 tabular-nums text-[#374151]">
                    {row.soilMoisture}
                  </td>
                  <td className="py-2.5 px-3 tabular-nums text-[#374151]">
                    {row.temperature}
                  </td>
                  <td className="py-2.5 px-3 text-[#374151]">
                    {row.growthStage}
                  </td>
                  <td className="py-2.5 pr-3 pl-2 text-right">
                    <button
                      type="button"
                      onClick={(e) => e.stopPropagation()}
                      className="text-[#6B7280] hover:text-[#111827] p-1"
                    >
                      <DotsThreeVertical size={14} weight="bold" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
