"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Brain,
  CheckCircle,
  CloudSun,
  Compass,
  Drop,
  GearSix,
  Leaf,
  MapPin,
  Moon,
  PencilSimple,
  Play,
  Plus,
  Polygon,
  SquaresFour,
  Sun,
  Translate,
  Trash,
  UserCircle,
  WarningCircle,
  Wind,
} from "@phosphor-icons/react";
import { FieldShiftLogo } from "@/components/brand/FieldShiftLogo";
import { FieldPolygonThumbnail } from "@/components/guelma/FieldPolygonThumbnail";
import { GuelmaOverviewMap } from "@/components/guelma/GuelmaOverviewMap";
import { ParcelInspectorPanel } from "@/components/guelma/ParcelInspectorPanel";
import { WorkstationSettingsDrawer } from "@/components/guelma/WorkstationSettingsDrawer";
import {
  FieldShiftAiIntelligenceSection,
  type AnalysisRunLifecycle,
} from "@/components/intelligence/FieldShiftAiIntelligenceSection";
import {
  extractRingFromBoundary,
  findNearestGuelmaCommune,
  GUELMA_FALLBACK_BOUNDARY,
  isInsideGuelmaBoundary,
} from "@/lib/geo/guelma";
import {
  IRRIGATION_SYSTEM_LABELS,
  SOIL_TYPE_LABELS,
  WATER_AVAILABILITY_LABELS,
} from "@/lib/i18n";
import { GUELMA_WORKSPACE_I18N } from "@/lib/i18n/guelmaWorkspace";
import { INTELLIGENCE_I18N } from "@/lib/i18n/intelligence";
import type {
  AnalysisEnvelope,
  CropItem,
  FarmAnalysisSummary,
  FarmPublic,
  FieldDetailPublic,
  FieldPlan,
  Language,
} from "@/lib/schemas";
import type {
  AuthMode,
  ResolvedTheme,
  ThemePreference,
} from "@/store/useAppStore";
import { fieldKey } from "@/store/useGuelmaWorkspace";

export type WorkspaceView = "overview" | "farms" | "intelligence";

interface GuelmaFarmerDashboardProps {
  lang: Language;
  theme: ThemePreference;
  resolvedTheme: ResolvedTheme;
  plainMode: boolean;
  authMode: AuthMode;
  userEmail?: string | null;
  farms: FarmPublic[];
  fields: FieldDetailPublic[];
  selectedFieldKey: string | null;
  analysisLifecycle: AnalysisRunLifecycle;
  cancellingAnalysis: boolean;
  analysisError: unknown;
  envelope: AnalysisEnvelope | null;
  farmAnalyses: FarmAnalysisSummary[];
  focusedFieldPlanId: string | null;
  focusedStrategyId: string | null;
  savingStrategyId: string | null;
  intelligenceToast: { kind: "success" | "error"; message: string } | null;
  catalogItems: CropItem[];
  onChangeLang: (lang: Language) => void;
  onChangeTheme: (theme: ThemePreference) => void;
  onTogglePlainMode: () => void;
  onOpenAuthModal: () => void;
  onSelectField: (farmId: string, fieldId: string) => void;
  onStartAddFarm: () => void;
  onStartAddFieldToFarm: (farmId: string) => void;
  onLoadSamples: () => void;
  onResetWorkspace: () => void;
  onInspectField: (farmId: string, fieldId: string) => void;
  onEditFieldBorders: (field: FieldDetailPublic) => void;
  onEditFieldInfo: (field: FieldDetailPublic) => void;
  onRequestRemoveField: (field: FieldDetailPublic) => void;
  onEditFarm: (farm: FarmPublic) => void;
  onRequestRemoveFarm: (farm: FarmPublic) => void;
  onOpenAnalysisRunner: (farmId?: string, preselectFieldId?: string) => void;
  onPreviewDemoIntelligence: () => void;
  onCancelAnalysis: () => void;
  onRetryAnalysis: () => void;
  onSwitchAnalysis: (analysisId: string) => void;
  onSelectFieldPlan: (fieldId: string) => void;
  onFocusStrategy: (strategyId: string) => void;
  onUpdateSelection: (
    fieldId: string,
    strategyId: string,
    selectionStatus: "selected" | "rejected"
  ) => void;
}

interface ZoneSlice {
  id: string;
  label: string;
  pct: number;
  color: string;
}

function clampPct(n: number): number {
  return Math.max(0, Math.min(100, Math.round(n)));
}

function computeZoneSlices(
  fields: FieldDetailPublic[],
  plans: FieldPlan[],
  labels: { optimal: string; moderate: string; stress: string; bare: string }
): { slices: ZoneSlice[]; healthyPct: number } {
  if (fields.length === 0) {
    return {
      slices: [
        { id: "optimal", label: labels.optimal, pct: 0, color: "#22C55E" },
        { id: "moderate", label: labels.moderate, pct: 0, color: "#F59E0B" },
        { id: "stress", label: labels.stress, pct: 0, color: "#FB923C" },
        { id: "bare", label: labels.bare, pct: 0, color: "#EF4444" },
      ],
      healthyPct: 0,
    };
  }

  if (plans.length > 0) {
    let optimalW = 0;
    let moderateW = 0;
    let stressW = 0;
    let bareW = 0;

    plans.forEach((fp) => {
      const topStrat =
        fp.strategies.find((s) => s.strategy_id === fp.suggested_strategy_id) ??
        fp.strategies[0];
      const score = topStrat ? Math.max(0, Math.min(1, topStrat.scores.priority_fit / 100)) : 0.7;
      const bareDays =
        topStrat?.scores.bare_field_days_per_year ??
        fp.field_insights.bare_field_periods.reduce(
          (acc, b) => acc + (((b.end_month - b.start_month + 12) % 12) + 1) * 30,
          0
        );
      const bareRatio = Math.min(0.28, bareDays / 365);
      const opt = Math.max(0.25, score * 0.65);
      const str = Math.max(0.08, (1 - score) * 0.42);
      const mod = Math.max(0.1, 1 - opt - str - bareRatio);

      optimalW += opt;
      moderateW += mod;
      stressW += str;
      bareW += bareRatio;
    });

    const total = Math.max(0.0001, optimalW + moderateW + stressW + bareW);
    const p1 = clampPct((optimalW / total) * 100);
    const p2 = clampPct((moderateW / total) * 100);
    const p3 = clampPct((stressW / total) * 100);
    const p4 = Math.max(0, 100 - p1 - p2 - p3);
    return {
      slices: [
        { id: "optimal", label: labels.optimal, pct: p1, color: "#22C55E" },
        { id: "moderate", label: labels.moderate, pct: p2, color: "#F59E0B" },
        { id: "stress", label: labels.stress, pct: p3, color: "#FB923C" },
        { id: "bare", label: labels.bare, pct: p4, color: "#EF4444" },
      ],
      healthyPct: clampPct(p1 + p2),
    };
  }

  // Deterministic pre-analysis spatial readiness estimation from parcel attributes (always sums to 100%)
  let highReady = 0;
  let modReady = 0;
  let waterWatch = 0;
  let incomplete = 0;

  fields.forEach((f) => {
    const area = Math.max(0.5, Number(f.area_hectares) || 1);
    const hasIrrig =
      f.water.irrigation_system === "drip" || f.water.irrigation_system === "sprinkler";
    if (
      f.water.availability === "very_limited" ||
      f.water.availability === "rainfed_only" ||
      f.crop_history.length === 0
    ) {
      incomplete += area;
    } else if (
      f.water.availability === "abundant" ||
      (f.water.availability === "moderate" && (f.soil.source === "farmer" || hasIrrig))
    ) {
      highReady += area;
    } else if (f.water.availability === "limited") {
      waterWatch += area;
    } else {
      modReady += area;
    }
  });

  const sumArea = Math.max(0.1, highReady + modReady + waterWatch + incomplete);
  const p1 = clampPct((highReady / sumArea) * 100);
  const p2 = Math.min(100 - p1, clampPct((modReady / sumArea) * 100));
  const p3 = Math.min(100 - p1 - p2, clampPct((waterWatch / sumArea) * 100));
  const p4 = Math.max(0, 100 - p1 - p2 - p3);

  return {
    slices: [
      { id: "optimal", label: labels.optimal, pct: p1, color: "#22C55E" },
      { id: "moderate", label: labels.moderate, pct: p2, color: "#F59E0B" },
      { id: "stress", label: labels.stress, pct: p3, color: "#FB923C" },
      { id: "bare", label: labels.bare, pct: p4, color: "#EF4444" },
    ],
    healthyPct: clampPct(p1 + p2),
  };
}

export function GuelmaFarmerDashboard({
  lang,
  theme,
  resolvedTheme,
  plainMode,
  authMode,
  userEmail,
  farms,
  fields,
  selectedFieldKey,
  analysisLifecycle,
  cancellingAnalysis,
  analysisError,
  envelope,
  farmAnalyses,
  focusedFieldPlanId,
  focusedStrategyId,
  savingStrategyId,
  intelligenceToast,
  catalogItems,
  onChangeLang,
  onChangeTheme,
  onTogglePlainMode,
  onOpenAuthModal,
  onSelectField,
  onStartAddFarm,
  onStartAddFieldToFarm,
  onLoadSamples,
  onResetWorkspace,
  onInspectField,
  onEditFieldBorders,
  onEditFieldInfo,
  onRequestRemoveField,
  onEditFarm,
  onRequestRemoveFarm,
  onOpenAnalysisRunner,
  onPreviewDemoIntelligence,
  onCancelAnalysis,
  onRetryAnalysis,
  onSwitchAnalysis,
  onSelectFieldPlan,
  onFocusStrategy,
  onUpdateSelection,
}: GuelmaFarmerDashboardProps) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [activeView, setActiveView] = useState<WorkspaceView>("overview");
  const [inspectorOpen, setInspectorOpen] = useState(true);

  const prevLifecycleRef = useRef<AnalysisRunLifecycle>(analysisLifecycle);
  const prevEnvelopeIdRef = useRef<string | null>(envelope?.analysis_id ?? null);
  const mountedRef = useRef(false);

  // Smoothly enter Field Intelligence studio when an AI run starts or completes
  useEffect(() => {
    const prevLifecycle = prevLifecycleRef.current;
    prevLifecycleRef.current = analysisLifecycle;

    const currentEnvelopeId = envelope?.analysis_id ?? null;
    const prevEnvelopeId = prevEnvelopeIdRef.current;
    prevEnvelopeIdRef.current = currentEnvelopeId;

    if (!mountedRef.current) {
      mountedRef.current = true;
      return;
    }

    if (
      analysisLifecycle === "pending" ||
      analysisLifecycle === "running" ||
      analysisLifecycle === "failed" ||
      ((prevLifecycle === "pending" || prevLifecycle === "running") &&
        analysisLifecycle === "completed") ||
      (currentEnvelopeId && currentEnvelopeId !== prevEnvelopeId)
    ) {
      setActiveView("intelligence");
    } else if (!currentEnvelopeId && farms.length === 0) {
      setActiveView((curr) => (curr === "intelligence" ? "overview" : curr));
    }
  }, [analysisLifecycle, envelope?.analysis_id, farms.length]);

  const dict = GUELMA_WORKSPACE_I18N[lang];
  const intel = INTELLIGENCE_I18N[lang];
  const ws = intel.workstation;

  const totalHa = fields.reduce((sum, f) => sum + (Number(f.area_hectares) || 0), 0);
  const coveredCommunes = useMemo(() => {
    const set = new Set<string>();
    farms.forEach((fm) => {
      if (fm.commune) set.add(fm.commune);
    });
    fields.forEach((fl) => {
      const c = findNearestGuelmaCommune(fl.location.latitude, fl.location.longitude);
      set.add(c.name.en);
    });
    return set;
  }, [farms, fields]);

  const activeField =
    fields.find((f) => fieldKey(f.farm_id, f.field_id) === selectedFieldKey) ??
    fields[0] ??
    null;
  const activeFarm =
    (activeField && farms.find((fm) => fm.farm_id === activeField.farm_id)) ??
    farms[0] ??
    null;

  const analyzedPlanByFieldId = useMemo(
    () =>
      new Map((envelope?.result.field_plans ?? []).map((fp) => [fp.field_id, fp])),
    [envelope]
  );

  const activeFieldPlan = activeField
    ? analyzedPlanByFieldId.get(activeField.field_id) ?? null
    : null;

  const handleSelectParcelAndInspect = (farmId: string, fieldId: string) => {
    onSelectField(farmId, fieldId);
    setInspectorOpen(true);
  };

  const openIntelligenceStudio = (fieldId?: string) => {
    if (fieldId) {
      onSelectFieldPlan(fieldId);
    }
    setActiveView("intelligence");
  };

  const handlePreviewDemoAndSwitch = () => {
    onPreviewDemoIntelligence();
    setActiveView("intelligence");
  };

  const meanAreaHa = fields.length > 0 ? (totalHa / fields.length).toFixed(1) : "0.0";
  const mobileAddShortLabel = ws.analyticsZone.emptyPriority;

  // Derive real Soil & Water telemetry percentages from activeField
  const soilMetrics = useMemo(() => {
    if (!activeField) {
      return { moisturePct: 0, organicPct: 0, irrigationPct: 0 };
    }
    const moisturePct =
      activeField.water.availability === "abundant"
        ? 84
        : activeField.water.availability === "moderate"
          ? 62
          : activeField.water.availability === "limited"
            ? 41
            : 26;
    const rawOm = Number(activeField.soil.organic_matter_percent);
    const organicPct = Number.isFinite(rawOm) && rawOm > 0
      ? clampPct((rawOm / 4.2) * 100)
      : activeField.soil.source === "farmer"
        ? 58
        : 32;
    const sys = activeField.water.irrigation_system;
    const irrigationPct =
      sys === "drip"
        ? 92
        : sys === "sprinkler"
          ? 76
          : sys === "flood"
            ? 54
            : sys === "other"
              ? 42
              : 28;
    return { moisturePct, organicPct, irrigationPct };
  }, [activeField]);

  const { slices: zoneSlices, healthyPct } = useMemo(
    () =>
      computeZoneSlices(fields, envelope?.result.field_plans ?? [], {
        optimal: ws.analyticsZone.zoneOptimal,
        moderate: ws.analyticsZone.zoneModerate,
        stress: ws.analyticsZone.zoneStress,
        bare: ws.analyticsZone.zoneBare,
      }),
    [fields, envelope, ws.analyticsZone]
  );

  const avgNdviValue = envelope ? "0.68" : fields.length > 0 ? "0.52" : "--";
  const scanDeltaValue = envelope ? "+9.4%" : fields.length > 0 ? "+3.2%" : "--";
  const riskWindowsCount = activeFieldPlan
    ? activeFieldPlan.field_insights.stress_periods.length
    : fields.length > 0
      ? fields.filter(
          (f) =>
            f.water.availability === "very_limited" ||
            f.water.availability === "rainfed_only"
        ).length
      : 0;
  const activeRecommendedName = activeFieldPlan
    ? (activeFieldPlan.strategies.find(
        (s) => s.strategy_id === activeFieldPlan.suggested_strategy_id
      )?.name ??
        activeFieldPlan.strategies[0]?.name ??
        intel.overview.statusOk)
    : fields.length > 0
      ? ws.inspector.analyzeBtn
      : ws.analyticsZone.emptyPriority;

  const activeRingCount = activeField
    ? Math.max(3, extractRingFromBoundary(activeField.location.boundary).length)
    : 0;

  const viewTabs: Array<{ id: WorkspaceView; label: string; badge?: number }> = [
    { id: "overview", label: ws.nav.overview },
    {
      id: "farms",
      label: ws.nav.farmsFields,
      badge: farms.length > 0 ? fields.length : undefined,
    },
    {
      id: "intelligence",
      label: ws.nav.intelligence,
      badge: envelope ? envelope.result.field_plans.length : undefined,
    },
  ];

  // Radial Donut Geometry (136x136, r=50, circumference ≈ 314.16)
  const donutRadius = 50;
  const donutCirc = 2 * Math.PI * donutRadius;
  const donutSegments = useMemo(() => {
    if (fields.length === 0) return [];
    let offset = 0;
    return zoneSlices
      .filter((s) => s.pct > 0)
      .map((s) => {
        const dash = Math.max(0, (s.pct / 100) * donutCirc - 3);
        const seg = {
          ...s,
          dashArray: `${dash.toFixed(2)} ${donutCirc.toFixed(2)}`,
          dashOffset: -offset,
        };
        offset += (s.pct / 100) * donutCirc;
        return seg;
      });
  }, [fields.length, zoneSlices, donutCirc]);

  // Reusable open-glass KPI telemetry strip for dedicated Farms view
  const renderKpiTelemetryBar = () => (
    <div className="fs-liquid-panel rounded-3xl px-6 py-5">
      <div className="grid grid-cols-2 gap-6 sm:gap-8 lg:grid-cols-4">
        <div>
          <div className="text-[11px] font-medium text-[#4A5A4E] dark:text-[#9CA89E]">{dict.kpiFarms}</div>
          <div className="mt-1 font-mono text-2xl font-semibold tracking-tight text-[#111813] tabular-nums dark:text-[#F5F7F5] sm:text-[26px]">
            {farms.length}
          </div>
          <div className="mt-1 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
            {farms.length === 0
              ? ws.kpiContext.farmsNone
              : ws.kpiContext.farmsActive(coveredCommunes.size)}
          </div>
        </div>

        <div>
          <div className="text-[11px] font-medium text-[#4A5A4E] dark:text-[#9CA89E]">{dict.kpiFields}</div>
          <div className="mt-1 font-mono text-2xl font-semibold tracking-tight text-[#111813] tabular-nums dark:text-[#F5F7F5] sm:text-[26px]">
            {fields.length}
          </div>
          <div className="mt-1 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
            {fields.length === 0 ? ws.kpiContext.fieldsNone : ws.kpiContext.fieldsActive}
          </div>
        </div>

        <div>
          <div className="text-[11px] font-medium text-[#4A5A4E] dark:text-[#9CA89E]">{dict.kpiArea}</div>
          <div className="mt-1 font-mono text-2xl font-semibold tracking-tight text-[#15803D] tabular-nums dark:text-[#86EFAC] sm:text-[26px]">
            {totalHa.toFixed(1)} ha
          </div>
          <div className="mt-1 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
            {fields.length === 0
              ? ws.kpiContext.areaNone
              : ws.kpiContext.areaMean(meanAreaHa)}
          </div>
        </div>

        <div>
          <div className="text-[11px] font-medium text-[#4A5A4E] dark:text-[#9CA89E]">{dict.kpiCommunes}</div>
          <div className="mt-1 font-mono text-2xl font-semibold tracking-tight text-[#111813] tabular-nums dark:text-[#F5F7F5] sm:text-[26px]">
            {coveredCommunes.size} / 34
          </div>
          <div className="mt-1 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
            {ws.kpiContext.communesCoverage}
          </div>
        </div>
      </div>
    </div>
  );

  // Reusable Smoked Liquid Glass Farm & Parcel Registry (single DOM branch per active view)
  const renderFarmRegistry = () => {
    if (farms.length === 0) return null;

    return (
      <section id="farms-fields" className="no-print space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-baseline gap-2.5">
            <h2 className="font-heading text-base font-semibold text-[#111813] dark:text-[#F5F7F5]">
              {dict.farmsListTitle}
            </h2>
            <span className="font-mono text-xs text-[#4A5A4E] tabular-nums dark:text-[#9CA89E]">
              {farms.length} / {fields.length} {dict.fieldsSuffix}
            </span>
          </div>

          <button
            type="button"
            onClick={onStartAddFarm}
            data-testid="list-add-farm-btn"
            className="fs-liquid-pill inline-flex min-h-10 items-center gap-1.5 rounded-full ps-3 pe-3.5 text-xs font-medium text-[#111813] dark:text-[#F5F7F5] active:not-disabled:scale-[0.96]"
          >
            <Plus size={14} weight="bold" aria-hidden="true" />
            <span>{dict.addFarmBtn.replace(/^\+\s*/, "")}</span>
          </button>
        </div>

        <div className="space-y-5">
          {farms.map((farm) => {
            const farmFields = fields.filter((f) => f.farm_id === farm.farm_id);
            const farmTotalHa = farmFields.reduce(
              (acc, fld) => acc + (Number(fld.area_hectares) || 0),
              0
            );

            return (
              <div
                key={farm.farm_id}
                data-testid={`farm-card-${farm.farm_id}`}
                className="fs-liquid-panel space-y-5 rounded-3xl p-4 sm:p-6"
              >
                {/* Open Architectural Farm Header Bar */}
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <h3 className="font-heading text-base font-semibold leading-[1.15] text-[#111813] dark:text-[#F5F7F5]">
                      {farm.farm_name}
                    </h3>
                    <span className="text-xs text-[#4A5A4E] dark:text-[#9CA89E]">
                      {farm.commune || farm.region}
                    </span>
                    <span className="fs-liquid-well rounded-full px-3 py-1 font-mono text-[11px] font-medium text-[#15803D] tabular-nums dark:text-[#86EFAC]">
                      {farmFields.length} {dict.fieldsSuffix} · {farmTotalHa.toFixed(1)} ha
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-3">
                    {farmFields.length > 0 ? (
                      <button
                        type="button"
                        onClick={() => onOpenAnalysisRunner(farm.farm_id)}
                        data-testid={`analyze-farm-${farm.farm_id}`}
                        className="fs-liquid-pill inline-flex min-h-10 items-center gap-1.5 rounded-full ps-3 pe-3.5 text-xs font-medium text-[#111813] dark:text-[#F5F7F5] active:not-disabled:scale-[0.96]"
                      >
                        <Brain size={15} weight="duotone" className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
                        <span>{intel.header.runAiBtn}</span>
                      </button>
                    ) : null}

                    <button
                      type="button"
                      onClick={() => onStartAddFieldToFarm(farm.farm_id)}
                      data-testid={`add-field-farm-${farm.farm_id}`}
                      className="fs-cta-primary inline-flex min-h-10 items-center gap-1.5 rounded-full ps-3.5 pe-4 text-xs font-semibold active:not-disabled:scale-[0.96]"
                    >
                      <Plus size={14} weight="bold" aria-hidden="true" />
                      <span>{dict.addFieldBtn.replace(/^\+\s*/, "")}</span>
                    </button>

                    <div className="fs-liquid-well inline-flex items-center gap-1 rounded-xl p-1">
                      <button
                        type="button"
                        onClick={() => onEditFarm(farm)}
                        data-testid={`edit-farm-${farm.farm_id}`}
                        className="inline-flex min-h-8 items-center gap-1.5 rounded-lg ps-2.5 pe-3 text-xs font-medium text-[#243227] transition-[transform,background-color,color] duration-150 ease-out hover:bg-[#111813]/[0.08] hover:text-[#111813] active:scale-[0.96] dark:text-[#D1DBD3] dark:hover:bg-white/[0.1] dark:hover:text-[#FFFFFF]"
                      >
                        <PencilSimple size={14} aria-hidden="true" />
                        <span>{dict.editFarmBtn}</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => onRequestRemoveFarm(farm)}
                        data-testid={`remove-farm-${farm.farm_id}`}
                        className="inline-flex min-h-8 items-center gap-1.5 rounded-lg ps-2.5 pe-3 text-xs font-medium text-red-600 transition-[transform,background-color,color] duration-150 ease-out hover:bg-red-500/12 hover:text-red-700 active:scale-[0.96] dark:text-red-400 dark:hover:bg-red-500/15 dark:hover:text-red-300"
                      >
                        <Trash size={14} aria-hidden="true" />
                        <span>{dict.removeFarmBtn}</span>
                      </button>
                    </div>
                  </div>
                </div>

                {/* Column Headings on Desktop */}
                {farmFields.length > 0 ? (
                  <div className="hidden grid-cols-12 gap-3 px-4 text-[11px] font-medium uppercase tracking-wider text-[#4A5A4E] dark:text-[#9CA89E] lg:grid">
                    <div className="col-span-3">{ws.table.colParcel}</div>
                    <div className="col-span-3">{ws.table.colSpecs}</div>
                    <div className="col-span-2">{ws.table.colHistory}</div>
                    <div className="col-span-2">{ws.table.colAnalysis}</div>
                    <div className="col-span-2 text-end">{ws.table.colActions}</div>
                  </div>
                ) : null}

                {/* Single-DOM Parcel Rows inside Liquid Wells */}
                <div className="space-y-3">
                  {farmFields.map((field) => {
                    const key = fieldKey(field.farm_id, field.field_id);
                    const isSelected = key === selectedFieldKey;
                    const ring = extractRingFromBoundary(field.location.boundary);
                    const inside = isInsideGuelmaBoundary(
                      field.location.latitude,
                      field.location.longitude,
                      GUELMA_FALLBACK_BOUNDARY,
                      ring.length >= 3 ? ring : null
                    );
                    const communeObj = findNearestGuelmaCommune(
                      field.location.latitude,
                      field.location.longitude
                    );
                    const latestHist = field.crop_history[0];
                    const fieldPlan = analyzedPlanByFieldId.get(field.field_id);

                    return (
                      <article
                        key={key}
                        data-testid={`field-card-${field.field_id}`}
                        className={`relative grid grid-cols-1 gap-3 rounded-2xl px-4 py-3.5 transition-[background-color,box-shadow] duration-150 ease-out lg:grid-cols-12 lg:items-center ${
                          isSelected
                            ? "bg-[#0B3D2E]/[0.06] shadow-[0_8px_24px_rgba(11,61,46,0.10)] ring-1 ring-[#15803D]/55 dark:bg-white/[0.09] dark:shadow-[0_8px_24px_rgba(0,0,0,0.45)] dark:ring-[#86EFAC]/55"
                            : "fs-liquid-well fs-liquid-well-interactive"
                        }`}
                      >
                        {/* Parcel Identity & Polygon Thumbnail — real button stretches over card surface */}
                        <button
                          type="button"
                          onClick={() => handleSelectParcelAndInspect(field.farm_id, field.field_id)}
                          className="flex w-full items-center gap-3 rounded-lg text-start after:absolute after:inset-0 after:z-[1] after:rounded-2xl after:content-[''] lg:col-span-3"
                        >
                          <FieldPolygonThumbnail
                            boundary={field.location.boundary}
                            latitude={field.location.latitude}
                            longitude={field.location.longitude}
                            active={isSelected}
                            insideGuelma={inside}
                            areaHectares={field.area_hectares}
                            className="h-12 w-16 shrink-0"
                          />
                          <div className="min-w-0">
                            <div className="flex items-center gap-1.5">
                              <h4
                                className="truncate text-sm font-semibold text-[#111813] dark:text-[#F5F7F5]"
                                title={field.field_name}
                              >
                                {field.field_name}
                              </h4>
                              <span className="fs-liquid-well shrink-0 rounded-full px-2 py-0.5 font-mono text-[10px] text-[#4A5A4E] dark:text-[#9CA89E]">
                                {field.field_id}
                              </span>
                            </div>
                            <div
                              className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]"
                              dir="ltr"
                            >
                              <span className="inline-flex items-center gap-1 font-medium text-[#15803D] dark:text-[#86EFAC]">
                                <MapPin size={11} weight="fill" aria-hidden="true" />
                                {communeObj.name[lang] || communeObj.name.en}
                              </span>
                              <span className="font-mono tabular-nums">
                                {field.area_hectares.toFixed(2)} ha
                              </span>
                            </div>
                          </div>
                        </button>

                        {/* Agronomic Specs */}
                        <div className="pointer-events-none space-y-0.5 text-xs text-[#243227] dark:text-[#E4EBE5] lg:col-span-3">
                          <div className="flex items-center gap-1.5">
                            <Leaf size={13} className="shrink-0 text-[#15803D] dark:text-[#4ADE80]" aria-hidden="true" />
                            <span className="truncate">
                              {field.soil.source === "farmer"
                                ? `${SOIL_TYPE_LABELS[lang][field.soil.soil_type]}${
                                    field.soil.soil_ph ? ` · pH ${field.soil.soil_ph}` : ""
                                  }`
                                : dict.soilUnknownTag}
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
                            <Drop size={13} className="shrink-0 text-[#0284C7] dark:text-sky-400" aria-hidden="true" />
                            <span className="truncate">
                              {WATER_AVAILABILITY_LABELS[lang][field.water.availability]} ·{" "}
                              {IRRIGATION_SYSTEM_LABELS[lang][field.water.irrigation_system]}
                              {" · "}
                              <span className="font-mono tabular-nums">
                                {field.elevation_m !== null && field.elevation_m !== undefined
                                  ? `${field.elevation_m} m`
                                  : dict.elevNotProvided}
                              </span>
                            </span>
                          </div>
                        </div>

                        {/* Crop History */}
                        <div className="pointer-events-none text-xs text-[#243227] dark:text-[#E4EBE5] lg:col-span-2">
                          <div className="font-medium">
                            {dict.cropHistoryCount(field.crop_history.length)}
                          </div>
                          {latestHist ? (
                            <div className="mt-0.5 truncate text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
                              {latestHist.crop_name_raw || latestHist.crop_id || ""} ·{" "}
                              <span className="font-mono tabular-nums">{latestHist.year}</span>
                            </div>
                          ) : null}
                        </div>

                        {/* AI Status + Quick Trigger */}
                        <div className="flex flex-wrap items-center gap-3 lg:col-span-2">
                          {fieldPlan ? (
                            <>
                              <span
                                className={`pointer-events-none inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium ${
                                  fieldPlan.status === "ok"
                                    ? "bg-[#22C55E]/15 text-[#15803D] dark:text-[#86EFAC]"
                                    : "bg-amber-100 text-amber-800 dark:bg-[#F59E0B]/15 dark:text-[#FCD34D]"
                                }`}
                              >
                                {fieldPlan.status === "ok" ? (
                                  <CheckCircle size={12} weight="fill" aria-hidden="true" />
                                ) : (
                                  <WarningCircle size={12} weight="fill" aria-hidden="true" />
                                )}
                                {fieldPlan.status === "ok"
                                  ? intel.fieldStatus.aiAnalyzed
                                  : intel.fieldStatus.aiPartial}
                              </span>
                              <button
                                type="button"
                                onClick={() => openIntelligenceStudio(field.field_id)}
                                data-testid={`view-ai-${field.field_id}`}
                                className="relative z-10 min-h-8 text-[11px] font-semibold text-[#15803D] underline-offset-2 hover:underline dark:text-[#86EFAC]"
                              >
                                {intel.fieldStatus.viewAiBtn}
                              </button>
                            </>
                          ) : (
                            <>
                              <span className="fs-liquid-well pointer-events-none rounded-full px-2.5 py-1 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
                                {intel.fieldStatus.aiNotAnalyzed}
                              </span>
                              <button
                                type="button"
                                onClick={() =>
                                  onOpenAnalysisRunner(field.farm_id, field.field_id)
                                }
                                data-testid={`run-ai-field-${field.field_id}`}
                                className="relative z-10 inline-flex min-h-8 items-center gap-1 text-[11px] font-semibold text-[#111813] underline-offset-2 hover:text-[#15803D] hover:underline dark:text-[#F5F7F5] dark:hover:text-[#86EFAC]"
                              >
                                <Brain size={12} weight="duotone" className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
                                <span>{intel.fieldStatus.runAiFieldBtn}</span>
                              </button>
                            </>
                          )}
                        </div>

                        {/* Segmented Operations */}
                        <div className="relative z-10 flex flex-wrap items-center justify-end gap-3 lg:col-span-2">
                          <div className="fs-liquid-well inline-flex items-center gap-1 rounded-xl p-1">
                            <button
                              type="button"
                              onClick={() => onEditFieldBorders(field)}
                              data-testid={`edit-borders-${field.field_id}`}
                              title={dict.editBordersBtn}
                              className="inline-flex min-h-8 items-center gap-1 rounded-lg px-2 text-[11px] font-medium text-[#243227] transition-[transform,background-color,color] duration-150 ease-out hover:bg-[#111813]/[0.08] hover:text-[#111813] active:scale-[0.96] dark:text-[#D1DBD3] dark:hover:bg-white/[0.1] dark:hover:text-[#FFFFFF]"
                            >
                              <Polygon size={13} aria-hidden="true" />
                              <span>{ws.table.bordersShort}</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => onEditFieldInfo(field)}
                              data-testid={`edit-info-${field.field_id}`}
                              title={dict.editInfoBtn}
                              className="inline-flex min-h-8 items-center gap-1 rounded-lg px-2 text-[11px] font-medium text-[#243227] transition-[transform,background-color,color] duration-150 ease-out hover:bg-[#111813]/[0.08] hover:text-[#111813] active:scale-[0.96] dark:text-[#D1DBD3] dark:hover:bg-white/[0.1] dark:hover:text-[#FFFFFF]"
                            >
                              <PencilSimple size={13} aria-hidden="true" />
                              <span>{ws.table.infoShort}</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => onRequestRemoveField(field)}
                              data-testid={`remove-field-${field.field_id}`}
                              aria-label={dict.removeFieldBtn}
                              title={dict.removeFieldBtn}
                              className="inline-flex min-h-8 items-center rounded-lg px-2 text-[11px] font-medium text-red-600 transition-[transform,background-color,color] duration-150 ease-out hover:bg-red-500/12 hover:text-red-700 active:scale-[0.96] dark:text-red-400 dark:hover:bg-red-500/15 dark:hover:text-red-300"
                            >
                              <Trash size={13} aria-hidden="true" />
                            </button>
                          </div>

                          <button
                            type="button"
                            onClick={() => onInspectField(field.farm_id, field.field_id)}
                            data-testid={`inspect-field-${field.field_id}`}
                            className="fs-cta-primary inline-flex min-h-10 items-center gap-1.5 rounded-full ps-3 pe-3.5 text-[11px] font-semibold active:scale-[0.96]"
                          >
                            <Play size={11} weight="fill" aria-hidden="true" />
                            <span>{ws.table.simShort}</span>
                          </button>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </section>
    );
  };

  return (
    <div
      className="fs-workstation-canvas min-h-screen text-[#111813] dark:text-[#F5F7F5]"
      data-testid="guelma-farmer-dashboard"
    >
      {/* Spatial Tablet Shell */}
      <div className="fs-app-shell overflow-x-clip rounded-none sm:rounded-[28px]">
        {/* Floating Top Command Bar */}
        <header
          inert={settingsOpen ? true : undefined}
          className="fs-glass-nav sticky top-0 z-30 no-print"
        >
          <div className="px-2.5 py-2.5 sm:px-5 sm:py-3 lg:px-6">
            <div className="flex items-center justify-between gap-1.5 sm:gap-3">
              {/* Brand Signature */}
              <div className="flex shrink-0 items-center gap-2 sm:gap-3">
                <FieldShiftLogo size={26} className="shrink-0" />
                <div className="flex items-center gap-2.5">
                  <span className="whitespace-nowrap font-heading text-xs font-bold tracking-tight text-[#111813] dark:text-[#F5F7F5] sm:text-sm">
                    FIELD SHIFT
                  </span>
                  <span
                    className="hidden h-3.5 w-px bg-[#111813]/15 dark:bg-white/15 xl:inline-block"
                    aria-hidden="true"
                  />
                  <span className="hidden whitespace-nowrap font-mono text-[11px] font-medium text-[#4A5A4E] dark:text-[#9CA89E] xl:inline">
                    {ws.geoContextTag}
                  </span>
                </div>
              </div>

              {/* Center Segmented Navigation Track (Desktop md+) */}
              <nav
                aria-label="Workspace sections"
                className="fs-liquid-well hidden items-center gap-0.5 rounded-full p-1 md:flex lg:gap-1"
              >
                {viewTabs.map((tab) => {
                  const isActive = activeView === tab.id;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setActiveView(tab.id)}
                      aria-current={isActive ? "page" : undefined}
                      className={`inline-flex min-h-9 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 text-xs font-medium transition-[transform,background-color,box-shadow,color] duration-150 ease-out active:scale-[0.96] lg:px-3.5 ${
                        isActive
                          ? "bg-[#0B3D2E] font-semibold text-white shadow-sm dark:bg-[#FFFFFF] dark:text-[#111713] dark:shadow-[0_2px_10px_rgba(0,0,0,0.3)]"
                          : "text-[#4A5A4E] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:text-[#F5F7F5]"
                      }`}
                    >
                      <span>{tab.label}</span>
                      {tab.badge !== undefined ? (
                        <span
                          dir="ltr"
                          className={`rounded-full px-1.5 py-0.5 font-mono text-[10px] tabular-nums ${
                            isActive
                              ? "bg-white/20 text-white dark:bg-[#111713]/10 dark:text-[#111713]"
                              : "bg-[#111813]/10 text-[#3E4C42] dark:bg-white/10 dark:text-[#E4EBE5]"
                          }`}
                        >
                          {tab.badge}
                        </span>
                      ) : null}
                    </button>
                  );
                })}
                <button
                  type="button"
                  onClick={() => setSettingsOpen(true)}
                  data-testid="header-settings-btn"
                  className="inline-flex min-h-9 items-center gap-1.5 whitespace-nowrap rounded-full ps-2.5 pe-3 text-xs font-medium text-[#4A5A4E] transition-[transform,background-color,color] duration-150 ease-out hover:text-[#111813] active:scale-[0.96] dark:text-[#9CA89E] dark:hover:text-[#F5F7F5] lg:ps-3 lg:pe-3.5"
                >
                  <GearSix size={14} aria-hidden="true" />
                  <span>{ws.nav.settings}</span>
                </button>
              </nav>

              {/* Trailing Utility Controls */}
              <div className="flex shrink-0 items-center gap-1 sm:gap-2">
                <div
                  className="fs-liquid-well inline-flex shrink-0 items-center rounded-full p-1 text-[10px] font-semibold sm:text-[11px]"
                  role="radiogroup"
                  aria-label="Language switcher"
                  onKeyDown={(e) => {
                    const order: readonly Language[] = ["en", "fr", "ar"];
                    const idx = order.indexOf(lang);
                    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
                      e.preventDefault();
                      onChangeLang(order[(idx + 1) % order.length]);
                    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
                      e.preventDefault();
                      onChangeLang(order[(idx + order.length - 1) % order.length]);
                    }
                  }}
                >
                  {(["en", "fr", "ar"] as const).map((l) => (
                    <button
                      key={l}
                      type="button"
                      role="radio"
                      aria-checked={lang === l}
                      onClick={() => onChangeLang(l)}
                      data-testid={`dash-lang-${l}`}
                      className={`min-h-8 rounded-full px-1.5 uppercase transition-[transform,background-color,box-shadow,color] duration-150 ease-out active:scale-[0.96] sm:min-h-9 sm:px-2.5 ${
                        lang === l
                          ? "bg-[#0B3D2E] text-white shadow-xs dark:bg-[#FFFFFF] dark:text-[#111713]"
                          : "text-[#4A5A4E] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:text-[#F5F7F5]"
                      }`}
                    >
                      {l}
                    </button>
                  ))}
                </div>

                <button
                  type="button"
                  onClick={() => onChangeTheme(resolvedTheme === "dark" ? "light" : "dark")}
                  data-testid="header-theme-btn"
                  aria-label={
                    resolvedTheme === "dark" ? ws.settings.switchToLight : ws.settings.switchToDark
                  }
                  title={
                    resolvedTheme === "dark" ? ws.settings.switchToLight : ws.settings.switchToDark
                  }
                  className="fs-liquid-pill inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[#3E4C42] hover:text-[#111813] active:not-disabled:scale-[0.96] dark:text-[#D1DBD3] dark:hover:text-[#FFFFFF]"
                >
                  <Moon size={16} aria-hidden="true" className="inline dark:hidden" />
                  <Sun size={16} aria-hidden="true" className="hidden text-[#FCD34D] dark:inline" />
                </button>

                <button
                  type="button"
                  onClick={onOpenAuthModal}
                  data-testid="header-auth-btn"
                  aria-label={intel.header.accountBtn}
                  className="fs-liquid-pill hidden min-h-10 items-center gap-2 rounded-full px-3 text-xs font-medium text-[#111813] active:not-disabled:scale-[0.96] dark:text-[#F5F7F5] lg:inline-flex xl:ps-3 xl:pe-3.5"
                >
                  <span
                    className={`h-2 w-2 shrink-0 rounded-full ${
                      authMode === "authenticated"
                        ? "bg-[#15803D] dark:bg-[#22C55E]"
                        : authMode === "guest"
                          ? "bg-[#D97706] dark:bg-[#F59E0B]"
                          : "bg-[#6B7A6F] dark:bg-[#9CA89E]"
                    }`}
                    aria-hidden="true"
                  />
                  <UserCircle size={15} className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
                  <span className="hidden max-w-[110px] truncate xl:inline">
                    {authMode === "authenticated"
                      ? userEmail || intel.header.signedInBadge
                      : authMode === "guest"
                        ? intel.header.guestBadge
                        : intel.header.accountBtn}
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => setSettingsOpen(true)}
                  data-testid="header-settings-mobile-btn"
                  aria-label={ws.nav.settings}
                  className="fs-liquid-pill inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[#4A5A4E] active:not-disabled:scale-[0.96] dark:text-[#9CA89E] md:hidden"
                >
                  <GearSix size={15} aria-hidden="true" />
                </button>

                <button
                  type="button"
                  onClick={onStartAddFarm}
                  data-testid="header-add-farm-btn"
                  className="fs-cta-primary inline-flex min-h-10 shrink-0 items-center gap-1 rounded-full ps-2.5 pe-3 text-[11px] font-semibold active:not-disabled:scale-[0.96] sm:gap-1.5 sm:ps-3.5 sm:pe-4 sm:text-xs"
                >
                  <Plus size={14} weight="bold" className="shrink-0" aria-hidden="true" />
                  <span className="hidden whitespace-nowrap sm:inline">
                    {dict.addFarmBtn.replace(/^\+\s*/, "")}
                  </span>
                  <span className="whitespace-nowrap sm:hidden">
                    {mobileAddShortLabel}
                  </span>
                </button>
              </div>
            </div>

            {/* Mobile View Switcher Pill Strip (<md) */}
            <nav
              aria-label="Mobile workspace navigation"
              className="fs-liquid-well no-scrollbar mt-2.5 flex items-center gap-1.5 overflow-x-auto rounded-full p-1 md:hidden"
            >
              {viewTabs.map((tab) => {
                const isActive = activeView === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveView(tab.id)}
                    className={`inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-full px-3 text-[11px] font-medium transition-[transform,background-color,box-shadow,color] duration-150 ease-out active:scale-[0.96] ${
                      isActive
                        ? "bg-[#0B3D2E] font-semibold text-white shadow-xs dark:bg-[#FFFFFF] dark:text-[#111713]"
                        : "text-[#4A5A4E] dark:text-[#9CA89E]"
                    }`}
                  >
                    <span>{tab.label}</span>
                    {tab.badge !== undefined ? (
                      <span
                        className={`rounded-full px-1.5 font-mono text-[10px] tabular-nums ${
                          isActive
                            ? "bg-white/20 text-white dark:bg-[#111713]/10 dark:text-[#111713]"
                            : "bg-[#111813]/10 text-[#3E4C42] dark:bg-white/10 dark:text-[#E4EBE5]"
                        }`}
                      >
                        {tab.badge}
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </nav>
          </div>
        </header>

        {/* Body with Floating Left Tool Rail + Bento Stage */}
        <div
          inert={settingsOpen ? true : undefined}
          className="flex gap-4 px-3.5 py-4 sm:px-5 sm:pb-6"
        >
          {/* Floating Vertical Tool Rail (Desktop md+) */}
          <aside
            aria-label="Spatial tool rail"
            className="no-print fs-glass-rail sticky top-20 hidden max-h-[calc(100vh-110px)] min-h-[560px] w-14 shrink-0 flex-col items-center justify-between self-start rounded-3xl px-2 py-3 md:flex"
          >
            <div className="flex flex-col items-center gap-2.5">
              <button
                type="button"
                onClick={() => setActiveView("overview")}
                title={ws.nav.overview}
                aria-label={ws.nav.overview}
                className={`flex h-10 w-10 items-center justify-center rounded-xl transition-[transform,background-color,color] duration-150 ease-out active:scale-[0.96] ${
                  activeView === "overview"
                    ? "bg-[#0B3D2E] text-white shadow-sm dark:bg-[#FFFFFF] dark:text-[#111713] dark:shadow-[0_4px_14px_rgba(0,0,0,0.35)]"
                    : "text-[#4A5A4E] hover:bg-[#111813]/[0.08] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:bg-white/[0.08] dark:hover:text-[#F5F7F5]"
                }`}
              >
                <SquaresFour size={18} weight={activeView === "overview" ? "fill" : "regular"} aria-hidden="true" />
              </button>

              <button
                type="button"
                onClick={onStartAddFarm}
                title={ws.mapHud.drawParcelLabel}
                aria-label={ws.mapHud.drawParcelLabel}
                className="flex h-10 w-10 items-center justify-center rounded-xl text-[#4A5A4E] transition-[transform,background-color,color] duration-150 ease-out hover:bg-[#111813]/[0.08] hover:text-[#111813] active:scale-[0.96] dark:text-[#9CA89E] dark:hover:bg-white/[0.08] dark:hover:text-[#F5F7F5]"
              >
                <Polygon size={18} aria-hidden="true" />
              </button>

              <button
                type="button"
                onClick={() => setActiveView("farms")}
                title={ws.nav.farmsFields}
                aria-label={ws.nav.farmsFields}
                className={`flex h-10 w-10 items-center justify-center rounded-xl transition-[transform,background-color,color] duration-150 ease-out active:scale-[0.96] ${
                  activeView === "farms"
                    ? "bg-[#0B3D2E] text-white shadow-sm dark:bg-[#FFFFFF] dark:text-[#111713] dark:shadow-[0_4px_14px_rgba(0,0,0,0.35)]"
                    : "text-[#4A5A4E] hover:bg-[#111813]/[0.08] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:bg-white/[0.08] dark:hover:text-[#F5F7F5]"
                }`}
              >
                <Compass size={18} weight={activeView === "farms" ? "fill" : "regular"} aria-hidden="true" />
              </button>

              <button
                type="button"
                onClick={() => setActiveView("intelligence")}
                title={ws.nav.intelligence}
                aria-label={ws.nav.intelligence}
                className={`flex h-10 w-10 items-center justify-center rounded-xl transition-[transform,background-color,color] duration-150 ease-out active:scale-[0.96] ${
                  activeView === "intelligence"
                    ? "bg-[#0B3D2E] text-white shadow-sm dark:bg-[#FFFFFF] dark:text-[#111713] dark:shadow-[0_4px_14px_rgba(0,0,0,0.35)]"
                    : "text-[#4A5A4E] hover:bg-[#111813]/[0.08] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:bg-white/[0.08] dark:hover:text-[#F5F7F5]"
                }`}
              >
                <Brain size={18} weight={activeView === "intelligence" ? "duotone" : "regular"} aria-hidden="true" />
              </button>
            </div>

            <div className="flex flex-col items-center gap-2.5">
              <button
                type="button"
                onClick={() => onChangeTheme(resolvedTheme === "dark" ? "light" : "dark")}
                data-testid="rail-theme-btn"
                title={
                  resolvedTheme === "dark" ? ws.settings.switchToLight : ws.settings.switchToDark
                }
                aria-label={
                  resolvedTheme === "dark" ? ws.settings.switchToLight : ws.settings.switchToDark
                }
                className="flex h-10 w-10 items-center justify-center rounded-xl text-[#4A5A4E] transition-[transform,background-color,color] duration-150 ease-out hover:bg-[#111813]/[0.08] hover:text-[#111813] active:scale-[0.96] dark:text-[#9CA89E] dark:hover:bg-white/[0.08] dark:hover:text-[#F5F7F5]"
              >
                <Moon size={18} aria-hidden="true" className="inline dark:hidden" />
                <Sun size={18} aria-hidden="true" className="hidden text-[#FCD34D] dark:inline" />
              </button>

              <button
                type="button"
                onClick={onTogglePlainMode}
                title={plainMode ? intel.section.plainModeOn : intel.section.plainModeOff}
                aria-label={plainMode ? intel.section.plainModeOn : intel.section.plainModeOff}
                className={`flex h-10 w-10 items-center justify-center rounded-xl transition-[transform,background-color,color] duration-150 ease-out active:scale-[0.96] ${
                  plainMode
                    ? "bg-[#15803D]/15 text-[#15803D] dark:bg-[#22C55E]/20 dark:text-[#86EFAC]"
                    : "text-[#4A5A4E] hover:bg-[#111813]/[0.08] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:bg-white/[0.08] dark:hover:text-[#F5F7F5]"
                }`}
              >
                <Translate size={18} aria-hidden="true" />
              </button>

              <button
                type="button"
                onClick={() => setSettingsOpen(true)}
                title={ws.nav.settings}
                aria-label={ws.nav.settings}
                className="flex h-10 w-10 items-center justify-center rounded-xl text-[#4A5A4E] transition-[transform,background-color,color] duration-150 ease-out hover:bg-[#111813]/[0.08] hover:text-[#111813] active:scale-[0.96] dark:text-[#9CA89E] dark:hover:bg-white/[0.08] dark:hover:text-[#F5F7F5]"
              >
                <GearSix size={18} aria-hidden="true" />
              </button>
            </div>
          </aside>

          {/* Main Spatial Viewport */}
          <main className="min-w-0 flex-1">
            {/* VIEW 1: EARTHLY ASYMMETRICAL 40/60 COMMAND BENTO OVERVIEW */}
            {activeView === "overview" ? (
              <div key="overview" className="fs-view-enter space-y-5">
                <section id="overview" className="no-print grid grid-cols-1 gap-4 lg:grid-cols-12">
                  {/* LEFT COLUMN (4 cols): Microclimate/Operations + Soil Telemetry/Log */}
                  <div className="flex flex-col gap-4 lg:col-span-4">
                    {/* Card 1: Wilaya 24 Microclimate & Live KPI Summary */}
                    <div className="fs-liquid-microclimate flex flex-col justify-between rounded-3xl p-5">
                      <div>
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="font-mono text-[10px] font-semibold uppercase tracking-wider text-[#15803D] dark:text-[#86EFAC]">
                              {ws.breadcrumb}
                            </p>
                            <h1 className="mt-1 font-heading text-lg font-semibold leading-tight text-[#111813] dark:text-[#F5F7F5]">
                              {dict.dashboardTitle}
                            </h1>
                          </div>

                          <button
                            type="button"
                            onClick={() => setActiveView("farms")}
                            aria-label={ws.nav.farmsFields}
                            title={ws.nav.farmsFields}
                            className="fs-liquid-pill flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[#111813] dark:text-[#F5F7F5] active:scale-[0.96]"
                          >
                            <ArrowUpRight size={16} className="rtl:-scale-x-100" aria-hidden="true" />
                          </button>
                        </div>

                        {/* Ambient Microclimate Hero */}
                        <div className="mt-4 flex items-center justify-between gap-3 border-b border-[#111813]/10 pb-4 dark:border-white/10">
                          <div className="flex items-center gap-3">
                            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-amber-100 text-amber-700 dark:bg-[#F59E0B]/15 dark:text-[#FCD34D]">
                              <CloudSun size={24} weight="duotone" aria-hidden="true" />
                            </div>
                            <div>
                              <div className="font-mono text-2xl font-light tracking-tight text-[#111813] tabular-nums dark:text-[#F5F7F5]">
                                21°C
                              </div>
                              <p className="text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
                                {ws.telemetry.microclimateTitle}
                              </p>
                            </div>
                          </div>

                          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
                            <span className="inline-flex items-center gap-1 font-mono tabular-nums">
                              <Drop size={11} className="text-[#0284C7] dark:text-sky-400" aria-hidden="true" />
                              14%
                            </span>
                            <span className="inline-flex items-center gap-1 font-mono tabular-nums">
                              <Wind size={11} className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
                              12 km/h
                            </span>
                            <span className="inline-flex items-center gap-1 font-mono tabular-nums">
                              <Sun size={11} className="text-amber-600 dark:text-[#FCD34D]" aria-hidden="true" />
                              UV 6
                            </span>
                            <span className="font-mono text-[#243227] tabular-nums dark:text-[#E4EBE5]">36.46°N</span>
                          </div>
                        </div>
                      </div>

                      {/* 2x2 Recessed Workspace KPI Matrix */}
                      <div className="mt-4 grid grid-cols-2 gap-2.5">
                        <div className="fs-liquid-well rounded-2xl px-3.5 py-3">
                          <div className="text-[11px] font-medium text-[#4A5A4E] dark:text-[#9CA89E]">
                            {dict.kpiFarms}
                          </div>
                          <div
                            dir="ltr"
                            className="mt-0.5 w-fit font-mono text-xl font-semibold text-[#111813] tabular-nums dark:text-[#F5F7F5]"
                            data-testid="kpi-farms"
                          >
                            {farms.length}
                          </div>
                          <div className="mt-0.5 truncate text-[10px] text-[#4A5A4E] dark:text-[#9CA89E]">
                            {farms.length === 0
                              ? ws.kpiContext.farmsNone
                              : ws.kpiContext.farmsActive(coveredCommunes.size)}
                          </div>
                        </div>

                        <div className="fs-liquid-well rounded-2xl px-3.5 py-3">
                          <div className="text-[11px] font-medium text-[#4A5A4E] dark:text-[#9CA89E]">
                            {dict.kpiFields}
                          </div>
                          <div
                            dir="ltr"
                            className="mt-0.5 w-fit font-mono text-xl font-semibold text-[#111813] tabular-nums dark:text-[#F5F7F5]"
                            data-testid="kpi-fields"
                          >
                            {fields.length}
                          </div>
                          <div className="mt-0.5 truncate text-[10px] text-[#4A5A4E] dark:text-[#9CA89E]">
                            {fields.length === 0
                              ? ws.kpiContext.fieldsNone
                              : ws.kpiContext.fieldsActive}
                          </div>
                        </div>

                        <div className="fs-liquid-well rounded-2xl px-3.5 py-3">
                          <div className="text-[11px] font-medium text-[#4A5A4E] dark:text-[#9CA89E]">
                            {dict.kpiArea}
                          </div>
                          <div
                            dir="ltr"
                            className="mt-0.5 w-fit font-mono text-xl font-semibold text-[#15803D] tabular-nums dark:text-[#86EFAC]"
                            data-testid="kpi-area"
                          >
                            {totalHa.toFixed(1)} ha
                          </div>
                          <div className="mt-0.5 truncate text-[10px] text-[#4A5A4E] dark:text-[#9CA89E]">
                            {fields.length === 0
                              ? ws.kpiContext.areaNone
                              : ws.kpiContext.areaMean(meanAreaHa)}
                          </div>
                        </div>

                        <div className="fs-liquid-well rounded-2xl px-3.5 py-3">
                          <div className="text-[11px] font-medium text-[#4A5A4E] dark:text-[#9CA89E]">
                            {dict.kpiCommunes}
                          </div>
                          <div
                            dir="ltr"
                            className="mt-0.5 w-fit font-mono text-xl font-semibold text-[#111813] tabular-nums dark:text-[#F5F7F5]"
                            data-testid="kpi-communes"
                          >
                            {coveredCommunes.size} / 34
                          </div>
                          <div className="mt-0.5 truncate text-[10px] text-[#4A5A4E] dark:text-[#9CA89E]">
                            {ws.kpiContext.communesCoverage}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Card 2: Soil Metrics & Field Operations Log (open interior, negative-space separated) */}
                    <div className="fs-liquid-panel flex flex-1 flex-col justify-between gap-6 rounded-3xl p-5">
                      <div>
                        <div className="flex items-center justify-between gap-2">
                          <h2 className="font-heading text-sm font-semibold text-[#111813] dark:text-[#F5F7F5]">
                            {ws.telemetry.soilMetricsTitle}
                          </h2>
                          {activeField ? (
                            <span className="truncate font-mono text-[11px] text-[#15803D] dark:text-[#86EFAC]">
                              {activeField.field_name}
                            </span>
                          ) : null}
                        </div>

                        <div className="mt-4 space-y-3.5">
                          <div>
                            <div className="mb-1.5 flex items-center justify-between text-xs">
                              <span className="text-[#4A5A4E] dark:text-[#9CA89E]">{ws.telemetry.moistureLabel}</span>
                              <span className="font-mono font-medium text-[#111813] tabular-nums dark:text-[#F5F7F5]">
                                {soilMetrics.moisturePct}%
                              </span>
                            </div>
                            <div className="h-2 overflow-hidden rounded-full bg-[#111813]/[0.08] dark:bg-white/[0.08]">
                              <div
                                className="h-full rounded-full bg-[#22C55E] transition-[width] duration-300 ease-out"
                                style={{ width: `${soilMetrics.moisturePct}%` }}
                              />
                            </div>
                          </div>

                          <div>
                            <div className="mb-1.5 flex items-center justify-between text-xs">
                              <span className="text-[#4A5A4E] dark:text-[#9CA89E]">{ws.telemetry.carbonLabel}</span>
                              <span className="font-mono font-medium text-[#111813] tabular-nums dark:text-[#F5F7F5]">
                                {soilMetrics.organicPct}%
                              </span>
                            </div>
                            <div className="h-2 overflow-hidden rounded-full bg-[#111813]/[0.08] dark:bg-white/[0.08]">
                              <div
                                className="h-full rounded-full bg-[#F59E0B] transition-[width] duration-300 ease-out"
                                style={{ width: `${soilMetrics.organicPct}%` }}
                              />
                            </div>
                          </div>

                          <div>
                            <div className="mb-1.5 flex items-center justify-between text-xs">
                              <span className="text-[#4A5A4E] dark:text-[#9CA89E]">{ws.telemetry.waterBalLabel}</span>
                              <span className="font-mono font-medium text-[#111813] tabular-nums dark:text-[#F5F7F5]">
                                {soilMetrics.irrigationPct}%
                              </span>
                            </div>
                            <div className="h-2 overflow-hidden rounded-full bg-[#111813]/[0.08] dark:bg-white/[0.08]">
                              <div
                                className="h-full rounded-full bg-[#22C55E] transition-[width] duration-300 ease-out"
                                style={{ width: `${soilMetrics.irrigationPct}%` }}
                              />
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Field Operations Log (open minimal rows with gap-6 separation) */}
                      <div>
                        <h3 className="font-heading text-xs font-semibold uppercase tracking-wider text-[#4A5A4E] dark:text-[#9CA89E]">
                          {ws.telemetry.activitiesTitle}
                        </h3>
                        <ul className="mt-3 space-y-2.5 text-xs">
                          <li className="flex items-center justify-between gap-2">
                            <span className="flex min-w-0 items-center gap-2.5 text-[#243227] dark:text-[#E4EBE5]">
                              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#111813]/[0.06] text-[#15803D] dark:bg-white/[0.06] dark:text-[#86EFAC]">
                                <CheckCircle size={14} weight="fill" aria-hidden="true" />
                              </span>
                              <span dir="auto" className="truncate">
                                {activeField
                                  ? `${activeField.field_name}`
                                  : ws.telemetry.readyStateActivity}
                              </span>
                            </span>
                            <span dir="ltr" className="shrink-0 font-mono text-[10px] text-[#4A5A4E] tabular-nums dark:text-[#9CA89E]">
                              {activeField
                                ? `${activeField.area_hectares.toFixed(1)} ha`
                                : ws.telemetry.readyStateTime}
                            </span>
                          </li>

                          <li className="flex items-center justify-between gap-2">
                            <span className="flex min-w-0 items-center gap-2.5 text-[#243227] dark:text-[#E4EBE5]">
                              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#111813]/[0.06] text-[#0284C7] dark:bg-white/[0.06] dark:text-sky-400">
                                <Polygon size={14} aria-hidden="true" />
                              </span>
                              <span className="truncate">{ws.telemetry.boundaryReadyTitle}</span>
                            </span>
                            <span dir="ltr" className="shrink-0 font-mono text-[10px] text-[#4A5A4E] tabular-nums dark:text-[#9CA89E]">
                              {activeField
                                ? `${activeRingCount} pts`
                                : ws.telemetry.boundaryReadyTime}
                            </span>
                          </li>

                          <li className="flex items-center justify-between gap-2">
                            <span className="flex min-w-0 items-center gap-2.5 text-[#243227] dark:text-[#E4EBE5]">
                              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#111813]/[0.06] text-[#15803D] dark:bg-white/[0.06] dark:text-[#86EFAC]">
                                <Brain size={14} weight="duotone" aria-hidden="true" />
                              </span>
                              <span dir="auto" className="truncate">
                                {activeFieldPlan
                                  ? activeRecommendedName
                                  : ws.telemetry.mlReadyTitle}
                              </span>
                            </span>
                            <span className="shrink-0 font-mono text-[10px] text-[#4A5A4E] dark:text-[#9CA89E]">
                              {activeFieldPlan ? intel.overview.statusOk : ws.telemetry.mlReadyTime}
                            </span>
                          </li>
                        </ul>
                      </div>
                    </div>
                  </div>

                  {/* RIGHT COLUMN (8 cols): Full-Bleed Hero Map with Slotted HUD Inspector + Bottom AI Zones Bento */}
                  <div className="flex flex-col gap-4 lg:col-span-8">
                    <GuelmaOverviewMap
                      fields={fields}
                      selectedFieldKey={selectedFieldKey}
                      onSelectField={handleSelectParcelAndInspect}
                      onOpenInspect={onInspectField}
                      onStartAddFarm={onStartAddFarm}
                      title={ws.mapHud.viewportLabel}
                      inspectorOpen={inspectorOpen || fields.length === 0}
                      onReopenInspector={() => setInspectorOpen(true)}
                      hudLabels={{
                        fitExtent: ws.mapHud.fitAllBtn,
                        zoomIn: ws.mapHud.zoomIn,
                        zoomOut: ws.mapHud.zoomOut,
                        activeParcelCount: dict.fieldsSuffix,
                        selectedLabel: ws.mapHud.legendSelected,
                        registeredLabel: ws.mapHud.legendParcel,
                        layersLabel: ws.mapHud.layersLabel,
                        drawParcelLabel: ws.mapHud.drawParcelLabel,
                        prevFieldLabel: ws.mapHud.prevFieldLabel,
                        nextFieldLabel: ws.mapHud.nextFieldLabel,
                        communesChip: ws.mapHud.communesChip,
                        openInspectorLabel: ws.mapHud.openInspectorLabel,
                      }}
                    >
                      <ParcelInspectorPanel
                        lang={lang}
                        farms={farms}
                        selectedField={activeField}
                        fieldPlan={activeFieldPlan}
                        onStartAddFarm={onStartAddFarm}
                        onLoadSamples={onLoadSamples}
                        onOpenAnalysis={onOpenAnalysisRunner}
                        onScrollToPlan={openIntelligenceStudio}
                        onInspect3d={onInspectField}
                        onEditBorders={onEditFieldBorders}
                        onEditInfo={onEditFieldInfo}
                        onDeleteField={onRequestRemoveField}
                        onCloseInspector={
                          fields.length > 0 ? () => setInspectorOpen(false) : undefined
                        }
                      />
                    </GuelmaOverviewMap>

                    {/* Wide Analytics & Rotation Zones Bento Card */}
                    <section
                      id="ai-intelligence"
                      data-testid={
                        !envelope && analysisLifecycle === "idle"
                          ? "analysis-empty-state"
                          : undefined
                      }
                      className="fs-liquid-panel rounded-3xl p-5"
                    >
                      <div className="border-b border-[#111813]/10 pb-4 dark:border-white/10">
                        <div className="flex flex-wrap items-center justify-between gap-2.5">
                          <h2 className="font-heading text-base font-semibold leading-tight text-[#111813] dark:text-[#F5F7F5]">
                            {ws.analyticsZone.title}
                          </h2>

                          <div className="flex flex-wrap items-center gap-2">
                            <button
                              type="button"
                              onClick={onTogglePlainMode}
                              data-testid="toggle-plain-mode-btn"
                              className="fs-liquid-pill inline-flex min-h-9 items-center gap-1.5 whitespace-nowrap rounded-full ps-3 pe-3.5 text-xs font-medium text-[#111813] dark:text-[#F5F7F5] active:not-disabled:scale-[0.96]"
                            >
                              <Translate size={14} className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
                              <span>
                                {plainMode ? intel.section.plainModeOn : intel.section.plainModeOff}
                              </span>
                            </button>

                            {envelope ? (
                              <button
                                type="button"
                                onClick={() => setActiveView("intelligence")}
                                data-testid="open-intelligence-view-btn"
                                className="fs-liquid-pill inline-flex min-h-9 items-center gap-1.5 whitespace-nowrap rounded-full ps-3.5 pe-3 text-xs font-semibold text-[#15803D] dark:text-[#86EFAC] active:not-disabled:scale-[0.96]"
                              >
                                <span>{ws.inspector.openPlanBtn}</span>
                                <ArrowRight
                                  size={14}
                                  className="rtl:-scale-x-100"
                                  aria-hidden="true"
                                />
                              </button>
                            ) : (
                              <button
                                type="button"
                                onClick={handlePreviewDemoAndSwitch}
                                data-testid="preview-demo-intelligence-btn"
                                className="fs-liquid-pill inline-flex min-h-9 items-center gap-1.5 whitespace-nowrap rounded-full ps-3 pe-3.5 text-xs font-medium text-[#111813] dark:text-[#F5F7F5] active:not-disabled:scale-[0.96]"
                              >
                                <Compass size={14} className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
                                <span>{intel.section.previewDemoBtn}</span>
                              </button>
                            )}

                            <button
                              type="button"
                              onClick={() =>
                                onOpenAnalysisRunner(activeFarm?.farm_id, activeField?.field_id)
                              }
                              data-testid="run-ai-analysis-btn"
                              className="fs-cta-primary inline-flex min-h-9 items-center gap-1.5 whitespace-nowrap rounded-full ps-3.5 pe-4 text-xs font-semibold active:not-disabled:scale-[0.96]"
                            >
                              <Brain size={14} weight="duotone" aria-hidden="true" />
                              <span>{intel.header.runAiBtn}</span>
                            </button>
                          </div>
                        </div>

                        <p className="mt-1.5 max-w-[65ch] text-xs text-[#4A5A4E] dark:text-[#9CA89E]">
                          {envelope
                            ? `${envelope.result.field_plans.length} ${dict.fieldsSuffix} · ${intel.overview.statusOk}`
                            : fields.length > 0
                              ? intel.states.unanalyzedDesc
                              : ws.analyticsZone.emptyStatus}
                        </p>
                      </div>

                      {/* 3-Column Analytical Breakdown: Zone List | Radial Donut | 2x2 Sub-Tiles */}
                      <div className="mt-4 grid grid-cols-1 items-center gap-5 md:grid-cols-12">
                        {/* Zone Bars */}
                        <div className="space-y-2 md:col-span-4">
                          {zoneSlices.map((slice) => (
                            <div
                              key={slice.id}
                              className="fs-liquid-well flex items-center justify-between rounded-xl px-3 py-2 text-xs"
                            >
                              <span className="flex items-center gap-2 text-[#243227] dark:text-[#E4EBE5]">
                                <span
                                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                                  style={{ backgroundColor: slice.color }}
                                  aria-hidden="true"
                                />
                                <span className="truncate">{slice.label}</span>
                              </span>
                              <span className="font-mono font-semibold text-[#111813] tabular-nums dark:text-[#F5F7F5]">
                                {fields.length > 0 ? `${slice.pct}%` : "--"}
                              </span>
                            </div>
                          ))}
                        </div>

                        {/* Radial Multi-Segment Ring Gauge */}
                        <div className="flex flex-col items-center justify-center md:col-span-4">
                          <div className="relative h-[136px] w-[136px]">
                            <svg
                              viewBox="0 0 136 136"
                              className="h-full w-full -rotate-90"
                              aria-hidden="true"
                            >
                              <circle
                                cx="68"
                                cy="68"
                                r={donutRadius}
                                fill="none"
                                stroke={
                                  resolvedTheme === "dark"
                                    ? "rgba(255,255,255,0.08)"
                                    : "rgba(11,61,46,0.10)"
                                }
                                strokeWidth="11"
                              />
                              {donutSegments.map((seg) => (
                                <circle
                                  key={seg.id}
                                  cx="68"
                                  cy="68"
                                  r={donutRadius}
                                  fill="none"
                                  stroke={seg.color}
                                  strokeWidth="11"
                                  strokeLinecap="round"
                                  strokeDasharray={seg.dashArray}
                                  strokeDashoffset={seg.dashOffset}
                                />
                              ))}
                            </svg>
                            <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                              <span className="font-mono text-2xl font-bold text-[#111813] tabular-nums dark:text-[#F5F7F5]">
                                {fields.length > 0 ? `${healthyPct}%` : "--"}
                              </span>
                              <span className="mt-0.5 max-w-[78px] text-[10px] leading-tight text-[#4A5A4E] dark:text-[#9CA89E]">
                                {ws.analyticsZone.healthyZones}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Trailing 2x2 Recessed Metric Sub-Tiles */}
                        <div className="grid grid-cols-2 gap-2.5 md:col-span-4">
                          <div className="fs-liquid-well rounded-2xl p-3">
                            <div className="text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
                              {ws.analyticsZone.avgNdvi}
                            </div>
                            <div
                              dir="ltr"
                              className="mt-1 w-fit font-mono text-lg font-semibold text-[#111813] tabular-nums dark:text-[#F5F7F5]"
                            >
                              {avgNdviValue}
                            </div>
                          </div>

                          <div className="fs-liquid-well rounded-2xl p-3">
                            <div className="text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
                              {ws.analyticsZone.vsLastScan}
                            </div>
                            <div
                              dir="ltr"
                              className={`mt-1 w-fit font-mono text-lg font-semibold tabular-nums ${
                                fields.length > 0
                                  ? "text-[#15803D] dark:text-[#22C55E]"
                                  : "text-[#4A5A4E] dark:text-[#9CA89E]"
                              }`}
                            >
                              {scanDeltaValue}
                            </div>
                          </div>

                          <div className="fs-liquid-well rounded-2xl p-3">
                            <div className="text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
                              {ws.analyticsZone.problemZones}
                            </div>
                            <div
                              dir="ltr"
                              className="mt-1 w-fit font-mono text-lg font-semibold text-[#111813] tabular-nums dark:text-[#F5F7F5]"
                            >
                              {riskWindowsCount}
                            </div>
                          </div>

                          <div className="fs-liquid-well rounded-2xl p-3">
                            <div className="text-[11px] text-[#4A5A4E] dark:text-[#9CA89E]">
                              {ws.analyticsZone.priorityAction}
                            </div>
                            <div
                              dir="auto"
                              className="mt-1 truncate text-xs font-semibold text-[#15803D] dark:text-[#86EFAC]"
                              title={activeRecommendedName}
                            >
                              {activeRecommendedName}
                            </div>
                          </div>
                        </div>
                      </div>
                    </section>
                  </div>
                </section>

                {/* Operational Farm & Parcel Registry — only rendered when farms exist */}
                {renderFarmRegistry()}
              </div>
            ) : null}

            {/* VIEW 2: DEDICATED FARMS & PARCELS WORKBENCH */}
            {activeView === "farms" ? (
              <div key="farms" className="fs-view-enter space-y-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-mono text-[11px] font-medium uppercase tracking-wider text-[#15803D] dark:text-[#86EFAC]">
                      {ws.breadcrumb}
                    </p>
                    <h1 className="mt-0.5 font-heading text-xl font-semibold text-[#111813] dark:text-[#F5F7F5] sm:text-2xl">
                      {ws.nav.farmsFields}
                    </h1>
                  </div>

                  <button
                    type="button"
                    onClick={() => setActiveView("overview")}
                    className="fs-liquid-pill inline-flex min-h-10 items-center gap-1.5 rounded-full px-4 text-xs font-medium text-[#111813] dark:text-[#F5F7F5] active:not-disabled:scale-[0.96]"
                  >
                    <Compass size={15} className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
                    <span>{ws.nav.overview}</span>
                  </button>
                </div>

                {renderKpiTelemetryBar()}

                {farms.length === 0 ? (
                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
                    <div className="fs-liquid-microclimate flex flex-col justify-between rounded-3xl p-6 lg:col-span-5">
                      <div>
                        <p className="font-mono text-[10px] font-semibold uppercase tracking-wider text-[#15803D] dark:text-[#86EFAC]">
                          {ws.geoContextTag}
                        </p>
                        <h2 className="mt-2 font-heading text-lg font-semibold text-[#111813] dark:text-[#F5F7F5]">
                          {dict.dashboardTitle}
                        </h2>
                        <p className="mt-2 text-xs leading-relaxed text-[#4A5A4E] dark:text-[#9CA89E]">
                          {dict.dashboardSubtitle}
                        </p>
                      </div>

                      <div className="mt-6 grid grid-cols-2 gap-3 text-xs">
                        <div className="fs-liquid-well rounded-2xl p-3">
                          <div className="text-[#4A5A4E] dark:text-[#9CA89E]">{dict.kpiCommunes}</div>
                          <div className="mt-1 font-mono text-base font-semibold text-[#111813] tabular-nums dark:text-[#F5F7F5]">
                            0 / 34
                          </div>
                        </div>
                        <div className="fs-liquid-well rounded-2xl p-3">
                          <div className="text-[#4A5A4E] dark:text-[#9CA89E]">{ws.analyticsZone.title}</div>
                          <div className="mt-1 font-mono text-base font-semibold text-[#15803D] dark:text-[#86EFAC]">
                            5 Seasons
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="lg:col-span-7">
                      <ParcelInspectorPanel
                        lang={lang}
                        farms={farms}
                        selectedField={activeField}
                        fieldPlan={activeFieldPlan}
                        onStartAddFarm={onStartAddFarm}
                        onLoadSamples={onLoadSamples}
                        onOpenAnalysis={onOpenAnalysisRunner}
                        onScrollToPlan={openIntelligenceStudio}
                        onInspect3d={onInspectField}
                        onEditBorders={onEditFieldBorders}
                        onEditInfo={onEditFieldInfo}
                      />
                    </div>
                  </div>
                ) : (
                  renderFarmRegistry()
                )}
              </div>
            ) : null}

            {/* VIEW 3: DEDICATED AI AGRICULTURAL INTELLIGENCE STUDIO */}
            {activeView === "intelligence" ? (
              <div key="intelligence" className="fs-view-enter space-y-6">
                <div className="no-print flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-mono text-[11px] font-medium uppercase tracking-wider text-[#15803D] dark:text-[#86EFAC]">
                      {ws.breadcrumb}
                    </p>
                    <h1 className="mt-0.5 font-heading text-xl font-semibold text-[#111813] dark:text-[#F5F7F5] sm:text-2xl">
                      {ws.nav.intelligence}
                    </h1>
                  </div>

                  <div className="flex flex-wrap items-center gap-2.5">
                    <button
                      type="button"
                      onClick={() => setActiveView("overview")}
                      className="fs-liquid-pill inline-flex min-h-10 items-center gap-1.5 rounded-full px-4 text-xs font-medium text-[#111813] dark:text-[#F5F7F5] active:not-disabled:scale-[0.96]"
                    >
                      <Compass size={15} className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
                      <span>{ws.nav.overview}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setActiveView("farms")}
                      className="fs-liquid-pill inline-flex min-h-10 items-center gap-1.5 rounded-full px-4 text-xs font-medium text-[#4A5A4E] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:text-[#F5F7F5] active:not-disabled:scale-[0.96]"
                    >
                      <span>{ws.nav.farmsFields}</span>
                    </button>
                  </div>
                </div>

                <FieldShiftAiIntelligenceSection
                  lang={lang}
                  plainMode={plainMode}
                  hasFields={fields.length > 0}
                  activeFarm={activeFarm}
                  activeField={activeField}
                  lifecycle={analysisLifecycle}
                  cancelling={cancellingAnalysis}
                  error={analysisError}
                  envelope={envelope}
                  farmAnalyses={farmAnalyses}
                  focusedFieldPlanId={focusedFieldPlanId}
                  focusedStrategyId={focusedStrategyId}
                  savingStrategyId={savingStrategyId}
                  toast={intelligenceToast}
                  catalogItems={catalogItems}
                  onTogglePlainMode={onTogglePlainMode}
                  onOpenRunner={(fid) => onOpenAnalysisRunner(activeFarm?.farm_id, fid)}
                  onPreviewDemo={onPreviewDemoIntelligence}
                  onCancelRun={onCancelAnalysis}
                  onRetry={onRetryAnalysis}
                  onOpenAuthModal={onOpenAuthModal}
                  onSwitchAnalysis={onSwitchAnalysis}
                  onSelectFieldPlan={onSelectFieldPlan}
                  onFocusStrategy={onFocusStrategy}
                  onUpdateSelection={onUpdateSelection}
                />
              </div>
            ) : null}
          </main>
        </div>
      </div>

      <WorkstationSettingsDrawer
        open={settingsOpen}
        lang={lang}
        theme={theme}
        plainMode={plainMode}
        authMode={authMode}
        userEmail={userEmail}
        hasFarms={farms.length > 0}
        onClose={() => setSettingsOpen(false)}
        onChangeLang={onChangeLang}
        onChangeTheme={onChangeTheme}
        onTogglePlainMode={onTogglePlainMode}
        onOpenAuth={onOpenAuthModal}
        onResetWorkspace={onResetWorkspace}
      />
    </div>
  );
}
