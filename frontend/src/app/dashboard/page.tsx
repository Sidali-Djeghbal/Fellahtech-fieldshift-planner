"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  MagnifyingGlass,
  SlidersHorizontal,
  Compass,
} from "@phosphor-icons/react";
import {
  ApiErrorCard,
  DegradedReplayBanner,
  WarningsBanner,
} from "@/components/shared/ProvenanceBanners";
import {
  getAnalysisResult,
  listFarmAnalyses,
  listFarms,
  listFields,
} from "@/lib/api/endpoints";
import { UI_DICT } from "@/lib/i18n";
import { useAppStore } from "@/store/useAppStore";
import { DashboardMap } from "@/components/dashboard/DashboardMap";
import { FieldOverviewTable, FieldRecord } from "@/components/dashboard/FieldOverviewTable";
import { WeatherWidget } from "@/components/dashboard/WeatherWidget";
import { ResourceDonutChart } from "@/components/dashboard/ResourceDonutChart";
import { WeeklyHeatmap } from "@/components/dashboard/WeeklyHeatmap";
import { AnalyticsCard } from "@/components/dashboard/AnalyticsCard";

export default function DashboardPage() {
  const {
    lang,
    authMode,
    activeFarmId,
    activeAnalysisId,
    simulateDegradedReplay,
    setActiveFarmId,
    setActiveFieldId,
    setSimulateDegradedReplay,
  } = useAppStore();

  const [searchQuery, setSearchQuery] = useState("");
  const t = UI_DICT[lang];
  const hasSession = authMode !== "none";

  const farmsQuery = useQuery({
    queryKey: ["farms", authMode],
    queryFn: () => listFarms(),
    enabled: hasSession,
  });

  const resolvedFarmId = activeFarmId ?? farmsQuery.data?.items[0]?.farm_id ?? null;

  const fieldsQuery = useQuery({
    queryKey: ["fields", resolvedFarmId],
    queryFn: () => listFields(resolvedFarmId!),
    enabled: hasSession && Boolean(resolvedFarmId),
  });

  const analysesQuery = useQuery({
    queryKey: ["analyses", resolvedFarmId],
    queryFn: () => listFarmAnalyses(resolvedFarmId!),
    enabled: hasSession && Boolean(resolvedFarmId),
  });

  const resolvedAnalysisId =
    activeAnalysisId ??
    analysesQuery.data?.items.find((a) => a.analysis_id)?.analysis_id ??
    null;

  const analysisDetailQuery = useQuery({
    queryKey: ["analysis", resolvedAnalysisId, simulateDegradedReplay],
    queryFn: () => getAnalysisResult(resolvedAnalysisId!),
    enabled: hasSession && Boolean(resolvedAnalysisId),
  });

  const activeFarm = farmsQuery.data?.items.find((f) => f.farm_id === resolvedFarmId) ?? farmsQuery.data?.items[0];
  const backendFields = fieldsQuery.data?.items ?? [];
  const allWarnings = backendFields.flatMap((f) => f.warnings);
  const analysisEnv = analysisDetailQuery.data;

  // Convert backend fields to monitoring table records if available, otherwise use reference defaults
  const tableRecords: FieldRecord[] = backendFields.length > 0
    ? backendFields.map((f, idx) => ({
        id: f.field_id,
        fieldZone: f.field_id === "field_north_a1" ? "North Field A1" : f.field_id === "field_east_b2" ? "East Field B2" : f.field_id,
        cropType: idx % 2 === 0 ? "Corn" : "Wheat",
        status: f.is_unverified_demo_parcel ? "Stable" : "Healthy",
        soilMoisture: idx % 2 === 0 ? "68%" : "72%",
        temperature: idx % 2 === 0 ? "26°C" : "24°C",
        growthStage: idx % 2 === 0 ? "Vegetative" : "Flowering",
      }))
    : [
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

  // If simulateDegradedReplay is toggled, build a realistic degraded replay metadata payload
  const effectiveDegradedMode = simulateDegradedReplay
    ? {
        kind: "last_good_replay" as const,
        stale: true as const,
        source_analysis_id: "analysis_4f9a8c120e3b",
        created_at: new Date(Date.now() - 18420000).toISOString(),
        dataset_version: "2026.11-guelma-v1",
        age_seconds: 18420,
      }
    : analysisEnv?.degraded_mode;

  return (
    <div className="mx-auto max-w-[1440px] px-4 py-4 space-y-4">
      {/* Degraded mode simulation banner */}
      {effectiveDegradedMode && (
        <DegradedReplayBanner degradedMode={effectiveDegradedMode} lang={lang} />
      )}

      {/* Warnings & Error Banners */}
      <WarningsBanner warnings={allWarnings} lang={lang} />
      {farmsQuery.error && <ApiErrorCard error={farmsQuery.error} lang={lang} />}

      {/* Simulation & Operational Controls Strip */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-white px-3.5 py-2 border border-[#E5E7EB] text-xs shadow-xs">
        <div className="flex items-center gap-3">
          <span className="font-semibold text-[#111827]">
            {activeFarm ? activeFarm.farm_name : "Guelma Agricultural Station"}
          </span>
          <div className="h-3 w-px bg-gray-200" />
          <Link
            href="/select-field"
            className="inline-flex items-center gap-1 font-medium text-[#137135] hover:underline"
          >
            <Compass size={13} weight="bold" />
            <span>Select Field</span>
          </Link>
          <Link
            href="/farm-profile"
            className="inline-flex items-center gap-1 font-medium text-[#137135] hover:underline"
          >
            <SlidersHorizontal size={13} weight="bold" />
            <span>Farm Profile</span>
          </Link>
        </div>

        <div className="flex items-center gap-4">
          <label className="inline-flex cursor-pointer items-center gap-1.5 text-[11px] text-[#6B7280]">
            <input
              type="checkbox"
              data-testid="toggle-degraded-preview"
              checked={simulateDegradedReplay}
              onChange={(e) => setSimulateDegradedReplay(e.target.checked)}
              className="accent-[#137135] rounded"
            />
            <span>{t.dashboard.simulateDegradedLabel}</span>
          </label>
        </div>
      </div>

      {/* Main 2-Column Split: Center Workspace (Map + Table) & Right Telemetry Column */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_272px] xl:grid-cols-[1fr_280px]">
        {/* Center Workspace (Map + Monitoring Table) */}
        <div className="space-y-4 min-w-0">
          {/* Central Satellite Map with Boundary Polygon & Heatmap Overlay */}
          <DashboardMap
            activeParcelName="North Field A1"
            cropName="Corn"
            onExport={() => alert("Exporting field telemetry report...")}
          />

          {/* Central Bottom Field Monitoring Overview Table */}
          <FieldOverviewTable
            records={tableRecords}
            onSelectField={(record) => {
              if (activeFarm) setActiveFarmId(activeFarm.farm_id);
              setActiveFieldId(record.id);
            }}
          />
        </div>

        {/* Right-Hand Telemetry Column (272px) */}
        <div className="space-y-3.5 w-full">
          {/* Widget 1: Search Bar Pill */}
          <div className="relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Type to search..."
              className="w-full rounded-full border border-[#E5E7EB] bg-white py-2 pl-9 pr-4 text-xs text-[#111827] placeholder-[#9CA3AF] shadow-xs focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
            />
            <MagnifyingGlass
              size={15}
              className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#6B7280]"
            />
          </div>

          {/* Widget 2: Location & Weather Card */}
          <WeatherWidget
            location="Purwokerto, Central Java, Indonesia"
            temperature="26°C"
            condition="Sunny Day"
            timeDate="8.45 AM | Jan 26"
            humidity="35%"
            rainForecast="26°C"
            windSpeed="8m/s"
          />

          {/* Widget 3: Resource Monitoring Donut Chart */}
          <ResourceDonutChart />

          {/* Widget 4: Weekly Performance Heatmap Matrix */}
          <WeeklyHeatmap />

          {/* Widget 5: Analytics Performance Card */}
          <AnalyticsCard
            headlineMetric="$830,451"
            trendPercentage="+14.2%"
          />
        </div>
      </div>
    </div>
  );
}
