"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { AuthModal } from "@/components/auth/AuthModal";
import {
  FarmFieldInfoModal,
  type FarmFieldFormSubmitPayload,
} from "@/components/guelma/FarmFieldInfoModal";
import {
  ConfirmDeleteModal,
  EditFarmModal,
} from "@/components/guelma/FarmWorkspaceModals";
import {
  GuelmaBorderEditorMap,
  type BorderDraftResult,
} from "@/components/guelma/GuelmaBorderEditorMap";
import { GuelmaFarmerDashboard } from "@/components/guelma/GuelmaFarmerDashboard";
import { AnalysisRunnerModal } from "@/components/intelligence/AnalysisRunnerModal";
import type { AnalysisRunLifecycle } from "@/components/intelligence/FieldShiftAiIntelligenceSection";
import { FieldShiftPrototypeApp } from "@/components/prototype/FieldShiftPrototypeApp";
import {
  applySelectionToEnvelope,
  findFieldPlanForField,
  submitAndPollWorkspaceAnalysis,
  syncWorkspaceFarmAndFields,
} from "@/lib/analysis/workspaceAnalysis";
import {
  cancelAnalysisRequest,
  fetchAllCatalogItems,
  getAnalysisResult,
  listFarmAnalyses,
  startGuestSession,
  updateAnalysisSelection,
} from "@/lib/api/endpoints";
import { extractRingFromBoundary, GUELMA_COMMUNES } from "@/lib/geo/guelma";
import { GUELMA_WORKSPACE_I18N } from "@/lib/i18n/guelmaWorkspace";
import { INTELLIGENCE_I18N } from "@/lib/i18n/intelligence";
import { fieldToPreset } from "@/lib/prototype/engine";
import type { Preset } from "@/lib/prototype/types";
import type {
  AnalysisEnvelope,
  AnalysisSubmitRequest,
  CropItem,
  FarmAnalysisSummary,
  FarmPublic,
  FieldDetailPublic,
  Language,
} from "@/lib/schemas";
import { useResolvedTheme } from "@/app/providers";
import { useAppStore } from "@/store/useAppStore";
import { fieldKey, useGuelmaWorkspace } from "@/store/useGuelmaWorkspace";

type WorkspaceView = "dashboard" | "border-editor" | "inspect-sim";

type EditorTarget =
  | { kind: "new-farm" }
  | { kind: "add-to-farm"; farmId: string }
  | { kind: "edit-field-borders"; field: FieldDetailPublic };

type DeleteTarget =
  | { kind: "field"; field: FieldDetailPublic }
  | { kind: "farm"; farm: FarmPublic };

export function FieldShiftWorkspaceRoot() {
  const theme = useAppStore((s) => s.theme);
  const resolvedTheme = useResolvedTheme();
  const lang = useAppStore((s) => s.lang);
  const plainMode = useAppStore((s) => s.plainMode);
  const authMode = useAppStore((s) => s.authMode);
  const user = useAppStore((s) => s.user);
  const activeAnalysisId = useAppStore((s) => s.activeAnalysisId);
  const setTheme = useAppStore((s) => s.setTheme);
  const setStoreLang = useAppStore((s) => s.setLang);
  const togglePlainMode = useAppStore((s) => s.togglePlainMode);
  const setGuestSession = useAppStore((s) => s.setGuestSession);
  const setActiveFarmId = useAppStore((s) => s.setActiveFarmId);
  const setActiveFieldId = useAppStore((s) => s.setActiveFieldId);
  const setActiveAnalysisId = useAppStore((s) => s.setActiveAnalysisId);
  const setActiveRequestId = useAppStore((s) => s.setActiveRequestId);

  const farms = useGuelmaWorkspace((s) => s.farms);
  const fields = useGuelmaWorkspace((s) => s.fields);
  const selectedFieldKey = useGuelmaWorkspace((s) => s.selectedFieldKey);
  const selectField = useGuelmaWorkspace((s) => s.selectField);
  const addFarmWithField = useGuelmaWorkspace((s) => s.addFarmWithField);
  const addFieldToFarm = useGuelmaWorkspace((s) => s.addFieldToFarm);
  const updateFarm = useGuelmaWorkspace((s) => s.updateFarm);
  const deleteFarm = useGuelmaWorkspace((s) => s.deleteFarm);
  const updateField = useGuelmaWorkspace((s) => s.updateField);
  const deleteField = useGuelmaWorkspace((s) => s.deleteField);
  const loadSampleParcels = useGuelmaWorkspace((s) => s.loadSampleParcels);
  const reconcileFarmId = useGuelmaWorkspace((s) => s.reconcileFarmId);
  const syncFromBackend = useGuelmaWorkspace((s) => s.syncFromBackend);
  const resetWorkspace = useGuelmaWorkspace((s) => s.reset);

  const [view, setView] = useState<WorkspaceView>("dashboard");
  const [editorTarget, setEditorTarget] = useState<EditorTarget>({ kind: "new-farm" });
  const [borderDraft, setBorderDraft] = useState<BorderDraftResult | null>(null);
  const [infoModalOpen, setInfoModalOpen] = useState(false);
  const [editingField, setEditingField] = useState<FieldDetailPublic | null>(null);
  const [defaultTargetFarmId, setDefaultTargetFarmId] = useState<string | null>(null);
  const [editingFarm, setEditingFarm] = useState<FarmPublic | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [inspectPresetId, setInspectPresetId] = useState<string | undefined>(undefined);
  const [authModalOpen, setAuthModalOpen] = useState(false);

  // AI Intelligence State
  const [catalogItems, setCatalogItems] = useState<CropItem[]>([]);
  const [runnerModalState, setRunnerModalState] = useState<{
    open: boolean;
    farmId: string | null;
    preselectFieldIds: string[];
  }>({ open: false, farmId: null, preselectFieldIds: [] });
  const [analysisLifecycle, setAnalysisLifecycle] =
    useState<AnalysisRunLifecycle>("idle");
  const [cancellingAnalysis, setCancellingAnalysis] = useState(false);
  const [analysisError, setAnalysisError] = useState<unknown>(null);
  const [envelope, setEnvelope] = useState<AnalysisEnvelope | null>(null);
  const [farmAnalyses, setFarmAnalyses] = useState<FarmAnalysisSummary[]>([]);
  const [focusedFieldPlanId, setFocusedFieldPlanId] = useState<string | null>(null);
  const [focusedStrategyId, setFocusedStrategyId] = useState<string | null>(null);
  const [savingStrategyId, setSavingStrategyId] = useState<string | null>(null);
  const [intelligenceToast, setIntelligenceToast] = useState<{
    kind: "success" | "error";
    message: string;
  } | null>(null);
  const [inFlightRequestId, setInFlightRequestId] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastSubmittedRef = useRef<{
    farm: FarmPublic;
    targetFields: FieldDetailPublic[];
    submitRequest: Omit<AnalysisSubmitRequest, "farm_id">;
  } | null>(null);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    try {
      localStorage.setItem("fieldshift.lang", lang);
    } catch {
      /* ignore */
    }
  }, [lang]);

  // Fetch catalog items once session exists (or reload cleanly on language toggle)
  useEffect(() => {
    if (authMode === "none") return;
    let cancelled = false;
    fetchAllCatalogItems(lang)
      .then((res) => {
        if (!cancelled) setCatalogItems(res.items);
      })
      .catch(() => {
        /* non-fatal; timeline falls back to result crop_name */
      });
    return () => {
      cancelled = true;
    };
  }, [authMode, lang]);

  // Hydrate activeAnalysisId if stored in session & auth is already initialized
  useEffect(() => {
    if (authMode === "none" || !activeAnalysisId || envelope) return;
    let cancelled = false;
    getAnalysisResult(activeAnalysisId)
      .then((loaded) => {
        if (cancelled) return;
        setEnvelope(loaded);
        setAnalysisLifecycle("completed");
        const firstPlan = loaded.result.field_plans[0];
        if (firstPlan) {
          setFocusedFieldPlanId(firstPlan.field_id);
          setFocusedStrategyId(
            firstPlan.suggested_strategy_id ?? firstPlan.strategies[0]?.strategy_id ?? null
          );
        }
      })
      .catch(() => {
        /* ignore stale persisted analysisId */
      });
    return () => {
      cancelled = true;
    };
  }, [authMode, activeAnalysisId, envelope]);

  // Auto-dismiss transient toast
  useEffect(() => {
    if (!intelligenceToast) return;
    const timer = window.setTimeout(() => setIntelligenceToast(null), 4500);
    return () => window.clearTimeout(timer);
  }, [intelligenceToast]);

  const dict = GUELMA_WORKSPACE_I18N[lang];
  const intelDict = INTELLIGENCE_I18N[lang];

  const handleChangeLang = (nextLang: Language) => {
    setStoreLang(nextLang);
  };

  // Convert user's saved farms & fields into simulator Preset objects
  const userPresets = useMemo<Preset[]>(() => {
    return fields.map((fld) => {
      const parent =
        farms.find((fm) => fm.farm_id === fld.farm_id) ?? {
          farm_id: fld.farm_id,
          farm_name: "Guelma Farm",
          commune: null,
        };
      return fieldToPreset(parent, fld);
    });
  }, [farms, fields]);

  const handleStartAddFarm = () => {
    setEditorTarget({ kind: "new-farm" });
    setBorderDraft(null);
    setEditingField(null);
    setDefaultTargetFarmId(null);
    setView("border-editor");
  };

  const handleStartAddFieldToFarm = (farmId: string) => {
    setEditorTarget({ kind: "add-to-farm", farmId });
    setBorderDraft(null);
    setEditingField(null);
    setDefaultTargetFarmId(farmId);
    setView("border-editor");
  };

  const handleEditFieldBorders = (field: FieldDetailPublic) => {
    setEditorTarget({ kind: "edit-field-borders", field });
    setBorderDraft(null);
    setEditingField(field);
    setDefaultTargetFarmId(field.farm_id);
    setView("border-editor");
  };

  const handleEditFieldInfo = (field: FieldDetailPublic) => {
    setEditingField(field);
    setBorderDraft(null);
    setDefaultTargetFarmId(field.farm_id);
    setInfoModalOpen(true);
  };

  const handleConfirmBorders = async (result: BorderDraftResult) => {
    if (editorTarget.kind === "edit-field-borders") {
      const fld = editorTarget.field;
      await updateField(fld.farm_id, fld.field_id, {
        field_id: fld.field_id,
        field_name: fld.field_name,
        is_unverified_demo_parcel: fld.is_unverified_demo_parcel,
        location: {
          latitude: result.centroid.latitude,
          longitude: result.centroid.longitude,
          boundary: result.boundary,
        },
        area_hectares: result.areaHectares,
        elevation_m: fld.elevation_m ?? "",
        soil: {
          soil_type: fld.soil.soil_type,
          soil_ph: fld.soil.soil_ph ?? "",
          organic_matter_percent: fld.soil.organic_matter_percent ?? "",
          soil_test_date: fld.soil.soil_test_date ?? "",
        },
        water: {
          availability: fld.water.availability,
          source: fld.water.source,
          source_other: fld.water.source_other ?? "",
          irrigation_system: fld.water.irrigation_system,
        },
        crop_history:
          fld.crop_history.length > 0
            ? fld.crop_history.map((h) => ({
                season: h.season,
                year: h.year,
                planting_month: h.planting_month ?? null,
                crop_id: h.crop_id ?? null,
                crop_name_raw: h.crop_name_raw ?? null,
                yield_tons_per_hectare: h.yield_tons_per_hectare ?? null,
                notes: h.notes ?? null,
              }))
            : [
                {
                  season: "autumn",
                  year: 2024,
                  planting_month: 11,
                  crop_id: "durum_wheat",
                },
              ],
      });
      setBorderDraft(null);
      setEditingField(null);
      setView("dashboard");
      return;
    }

    setBorderDraft(result);
    setEditingField(null);
    setDefaultTargetFarmId(
      editorTarget.kind === "add-to-farm" ? editorTarget.farmId : null
    );
    setInfoModalOpen(true);
  };

  const handleSubmitInfoForm = async (payload: FarmFieldFormSubmitPayload) => {
    if (payload.mode === "edit_field" && payload.existingFarmId && payload.editingFieldId) {
      await updateField(
        payload.existingFarmId,
        payload.editingFieldId,
        payload.fieldDraft
      );
      setInfoModalOpen(false);
      setEditingField(null);
      setBorderDraft(null);
      return;
    }

    if (payload.targetFarmMode === "existing" && payload.existingFarmId) {
      await addFieldToFarm(payload.existingFarmId, payload.fieldDraft);
    } else {
      await addFarmWithField(payload.farmPayload, payload.fieldDraft);
    }

    setInfoModalOpen(false);
    setBorderDraft(null);
    setEditingField(null);
    setView("dashboard");
  };

  const handleInspectField = (farmId: string, fieldId: string) => {
    selectField(farmId, fieldId);
    const key = fieldKey(farmId, fieldId);
    const matched = userPresets.find((p) => p.id === key);
    setInspectPresetId(matched ? matched.id : userPresets[0]?.id);
    setView("inspect-sim");
  };

  const handleOpenAnalysisRunner = (farmId?: string, preselectFieldId?: string) => {
    const resolvedFarmId =
      farmId ??
      (selectedFieldKey ? selectedFieldKey.split("::")[0] : null) ??
      farms[0]?.farm_id ??
      null;
    const targetFarmFields = fields.filter((f) => f.farm_id === resolvedFarmId);
    const preselectIds = preselectFieldId
      ? [preselectFieldId]
      : targetFarmFields.slice(0, 1).map((f) => f.field_id);

    setRunnerModalState({
      open: true,
      farmId: resolvedFarmId,
      preselectFieldIds: preselectIds,
    });

    if (useAppStore.getState().authMode === "none") {
      startGuestSession(1)
        .then((guest) => {
          setGuestSession({
            guestToken: guest.guest_token,
            expiresAt: guest.expires_at,
          });
        })
        .catch(() => {
          /* handled cleanly upon submission if network fails */
        });
    }
  };

  const executeAnalysisJob = async (job: {
    farm: FarmPublic;
    targetFields: FieldDetailPublic[];
    submitRequest: Omit<AnalysisSubmitRequest, "farm_id">;
  }) => {
    lastSubmittedRef.current = job;
    setRunnerModalState((prev) => ({ ...prev, open: false }));
    setAnalysisError(null);
    setAnalysisLifecycle("pending");
    setCancellingAnalysis(false);

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const { farmId } = await syncWorkspaceFarmAndFields({
        farm: job.farm,
        fields: job.targetFields,
        onReconcileFarmId: reconcileFarmId,
      });

      setActiveFarmId(farmId);
      setActiveFieldId(job.targetFields[0]?.field_id ?? null);

      const finalPoll = await submitAndPollWorkspaceAnalysis({
        request: {
          ...job.submitRequest,
          farm_id: farmId,
        },
        signal: controller.signal,
        onQueued: (requestId) => {
          setInFlightRequestId(requestId);
          setActiveRequestId(requestId);
        },
        onPollUpdate: (poll) => {
          if (poll.status === "pending" || poll.status === "running") {
            setAnalysisLifecycle(poll.status);
          }
        },
      });

      setInFlightRequestId(null);

      if (finalPoll.status === "cancelled") {
        setAnalysisLifecycle("cancelled");
        return;
      }

      if (finalPoll.status === "failed") {
        setAnalysisLifecycle("failed");
        setAnalysisError(
          new Error(finalPoll.error?.message || "Analysis job failed.")
        );
        return;
      }

      if (finalPoll.analysis_id) {
        const [fullEnvelope, runsPage, catalog] = await Promise.all([
          getAnalysisResult(finalPoll.analysis_id),
          listFarmAnalyses(farmId).catch(() => ({
            items: [],
            next_cursor: null,
            has_more: false,
          })),
          fetchAllCatalogItems(lang)
            .then((res) => res.items)
            .catch(() => [] as CropItem[]),
        ]);

        if (catalog.length > 0) setCatalogItems(catalog);
        setFarmAnalyses(runsPage.items);
        setEnvelope(fullEnvelope);
        setActiveAnalysisId(fullEnvelope.analysis_id);
        setAnalysisLifecycle("completed");

        const firstPlan =
          findFieldPlanForField(fullEnvelope, job.targetFields[0]?.field_id) ??
          fullEnvelope.result.field_plans[0];
        if (firstPlan) {
          setFocusedFieldPlanId(firstPlan.field_id);
          setFocusedStrategyId(
            firstPlan.suggested_strategy_id ?? firstPlan.strategies[0]?.strategy_id ?? null
          );
        }
      }
    } catch (err) {
      setInFlightRequestId(null);
      setAnalysisLifecycle("failed");
      setAnalysisError(err);
    }
  };

  const handleCancelAnalysis = async () => {
    setCancellingAnalysis(true);
    abortControllerRef.current?.abort();
    if (inFlightRequestId) {
      try {
        await cancelAnalysisRequest(inFlightRequestId);
      } catch {
        /* ignore if already terminal */
      }
    }
    setInFlightRequestId(null);
    setCancellingAnalysis(false);
    setAnalysisLifecycle("cancelled");
  };

  const handlePreviewDemoIntelligence = async () => {
    setAnalysisError(null);
    setAnalysisLifecycle("running");
    try {
      if (useAppStore.getState().authMode === "none") {
        const guest = await startGuestSession(1);
        setGuestSession({
          guestToken: guest.guest_token,
          expiresAt: guest.expires_at,
        });
      }

      await syncFromBackend();
      const runs = await listFarmAnalyses("farm_1");
      const targetAnalysisId =
        runs.items.find((a) => a.analysis_id)?.analysis_id ?? "analysis_4f9a8c120e3b";

      const [loadedEnvelope, catalog] = await Promise.all([
        getAnalysisResult(targetAnalysisId),
        fetchAllCatalogItems(lang)
          .then((res) => res.items)
          .catch(() => [] as CropItem[]),
      ]);

      if (catalog.length > 0) setCatalogItems(catalog);
      setFarmAnalyses(runs.items);
      setEnvelope(loadedEnvelope);
      setActiveFarmId("farm_1");
      setActiveAnalysisId(loadedEnvelope.analysis_id);
      setAnalysisLifecycle("completed");

      const firstPlan = loadedEnvelope.result.field_plans[0];
      if (firstPlan) {
        setFocusedFieldPlanId(firstPlan.field_id);
        setFocusedStrategyId(
          firstPlan.suggested_strategy_id ?? firstPlan.strategies[0]?.strategy_id ?? null
        );
      }
    } catch (err) {
      setAnalysisLifecycle("failed");
      setAnalysisError(err);
    }
  };

  const handleSwitchAnalysis = async (analysisId: string) => {
    setAnalysisError(null);
    try {
      const nextEnv = await getAnalysisResult(analysisId);
      setEnvelope(nextEnv);
      setActiveAnalysisId(nextEnv.analysis_id);
      setAnalysisLifecycle("completed");
      const firstPlan = nextEnv.result.field_plans[0];
      if (firstPlan) {
        setFocusedFieldPlanId(firstPlan.field_id);
        setFocusedStrategyId(
          firstPlan.suggested_strategy_id ?? firstPlan.strategies[0]?.strategy_id ?? null
        );
      }
    } catch (err) {
      setAnalysisError(err);
    }
  };

  const handleUpdateSelection = async (
    fieldId: string,
    strategyId: string,
    selectionStatus: "selected" | "rejected"
  ) => {
    if (!envelope) return;
    const prevEnvelope = envelope;
    const optimistic = applySelectionToEnvelope(
      envelope,
      fieldId,
      strategyId,
      selectionStatus
    );
    setEnvelope(optimistic);
    setFocusedStrategyId(strategyId);
    setSavingStrategyId(strategyId);

    const strategyName =
      findFieldPlanForField(optimistic, fieldId)?.strategies.find(
        (s) => s.strategy_id === strategyId
      )?.name ?? strategyId;

    try {
      await updateAnalysisSelection(envelope.analysis_id, {
        field_id: fieldId,
        strategy_id: strategyId,
        selection_status: selectionStatus,
      });
      const refreshed = await getAnalysisResult(envelope.analysis_id);
      setEnvelope(refreshed);
      setIntelligenceToast({
        kind: "success",
        message:
          selectionStatus === "selected"
            ? intelDict.strategies.toastSelected(strategyName)
            : intelDict.strategies.toastRejected(strategyName),
      });
    } catch {
      setEnvelope(prevEnvelope);
      setIntelligenceToast({
        kind: "error",
        message: intelDict.strategies.toastError,
      });
    } finally {
      setSavingStrategyId(null);
    }
  };

  const runnerFarm =
    farms.find((fm) => fm.farm_id === runnerModalState.farmId) ?? farms[0] ?? null;
  const runnerFarmFields = runnerFarm
    ? fields.filter((fld) => fld.farm_id === runnerFarm.farm_id)
    : [];

  const editorInitialRing = useMemo(() => {
    if (editorTarget.kind === "edit-field-borders") {
      return extractRingFromBoundary(editorTarget.field.location.boundary);
    }
    return undefined;
  }, [editorTarget]);

  const editorInitialCenter = useMemo<[number, number] | undefined>(() => {
    if (editorTarget.kind === "edit-field-borders") {
      return [
        editorTarget.field.location.longitude,
        editorTarget.field.location.latitude,
      ];
    }
    if (editorTarget.kind === "add-to-farm") {
      const sibling = fields.find((f) => f.farm_id === editorTarget.farmId);
      if (sibling) return [sibling.location.longitude, sibling.location.latitude];
      const farm = farms.find((f) => f.farm_id === editorTarget.farmId);
      if (farm?.commune) {
        const comm = GUELMA_COMMUNES.find(
          (c) => c.name.en.toLowerCase() === farm.commune?.toLowerCase()
        );
        if (comm) return comm.center;
      }
    }
    return undefined;
  }, [editorTarget, fields, farms]);

  if (view === "inspect-sim") {
    return (
      <FieldShiftPrototypeApp
        externalPresets={userPresets.length > 0 ? userPresets : undefined}
        initialPresetId={inspectPresetId}
        backLabel={dict.editor.backDashboard}
        editBordersLabel={dict.editBordersBtn}
        onBackToDashboard={() => setView("dashboard")}
        onEditBorders={(presetId) => {
          const matchedField = fields.find(
            (f) => fieldKey(f.farm_id, f.field_id) === presetId
          );
          if (matchedField) handleEditFieldBorders(matchedField);
        }}
      />
    );
  }

  return (
    <>
      {view === "dashboard" ? (
        <GuelmaFarmerDashboard
          lang={lang}
          theme={theme}
          resolvedTheme={resolvedTheme}
          plainMode={plainMode}
          authMode={authMode}
          userEmail={user?.email ?? null}
          farms={farms}
          fields={fields}
          selectedFieldKey={selectedFieldKey}
          analysisLifecycle={analysisLifecycle}
          cancellingAnalysis={cancellingAnalysis}
          analysisError={analysisError}
          envelope={envelope}
          farmAnalyses={farmAnalyses}
          focusedFieldPlanId={focusedFieldPlanId}
          focusedStrategyId={focusedStrategyId}
          savingStrategyId={savingStrategyId}
          intelligenceToast={intelligenceToast}
          catalogItems={catalogItems}
          onChangeLang={handleChangeLang}
          onChangeTheme={setTheme}
          onTogglePlainMode={togglePlainMode}
          onOpenAuthModal={() => setAuthModalOpen(true)}
          onSelectField={(farmId, fieldId) => {
            selectField(farmId, fieldId);
            setFocusedFieldPlanId(fieldId);
          }}
          onStartAddFarm={handleStartAddFarm}
          onStartAddFieldToFarm={handleStartAddFieldToFarm}
          onLoadSamples={() => loadSampleParcels(lang)}
          onResetWorkspace={() => {
            resetWorkspace();
            setEnvelope(null);
            setFarmAnalyses([]);
            setAnalysisLifecycle("idle");
            setAnalysisError(null);
          }}
          onInspectField={handleInspectField}
          onEditFieldBorders={handleEditFieldBorders}
          onEditFieldInfo={handleEditFieldInfo}
          onRequestRemoveField={(field) => setDeleteTarget({ kind: "field", field })}
          onEditFarm={(farm) => setEditingFarm(farm)}
          onRequestRemoveFarm={(farm) => setDeleteTarget({ kind: "farm", farm })}
          onOpenAnalysisRunner={handleOpenAnalysisRunner}
          onPreviewDemoIntelligence={() => void handlePreviewDemoIntelligence()}
          onCancelAnalysis={() => void handleCancelAnalysis()}
          onRetryAnalysis={() => {
            if (lastSubmittedRef.current) {
              void executeAnalysisJob(lastSubmittedRef.current);
            } else {
              handleOpenAnalysisRunner();
            }
          }}
          onSwitchAnalysis={(id) => void handleSwitchAnalysis(id)}
          onSelectFieldPlan={(fid) => {
            setFocusedFieldPlanId(fid);
            const plan = envelope?.result.field_plans.find((fp) => fp.field_id === fid);
            if (plan) {
              setFocusedStrategyId(
                plan.suggested_strategy_id ?? plan.strategies[0]?.strategy_id ?? null
              );
            }
          }}
          onFocusStrategy={setFocusedStrategyId}
          onUpdateSelection={(fid, sid, status) =>
            void handleUpdateSelection(fid, sid, status)
          }
        />
      ) : (
        <GuelmaBorderEditorMap
          lang={lang}
          mode={editorTarget.kind === "edit-field-borders" ? "edit" : "create"}
          initialRing={editorInitialRing}
          initialCenter={editorInitialCenter}
          onBack={() => {
            setBorderDraft(null);
            setEditingField(null);
            setView("dashboard");
          }}
          onConfirmBorders={handleConfirmBorders}
        />
      )}

      <FarmFieldInfoModal
        open={infoModalOpen}
        lang={lang}
        existingFarms={farms}
        existingFields={fields}
        borderDraft={borderDraft}
        editingField={editingField}
        defaultFarmId={defaultTargetFarmId}
        onClose={() => {
          setInfoModalOpen(false);
          setEditingField(null);
          setBorderDraft(null);
        }}
        onEditBorders={
          editingField
            ? () => {
                setInfoModalOpen(false);
                handleEditFieldBorders(editingField);
              }
            : undefined
        }
        onSubmit={handleSubmitInfoForm}
      />

      <EditFarmModal
        open={Boolean(editingFarm)}
        lang={lang}
        farm={editingFarm}
        onClose={() => setEditingFarm(null)}
        onSave={updateFarm}
      />

      <ConfirmDeleteModal
        open={Boolean(deleteTarget)}
        lang={lang}
        title={
          deleteTarget?.kind === "farm"
            ? dict.confirmDelete.farmTitle
            : dict.confirmDelete.fieldTitle
        }
        body={
          deleteTarget?.kind === "farm"
            ? dict.confirmDelete.farmBody(
                deleteTarget.farm.farm_name,
                fields.filter((f) => f.farm_id === deleteTarget.farm.farm_id).length
              )
            : deleteTarget?.kind === "field"
              ? dict.confirmDelete.fieldBody(deleteTarget.field.field_name)
              : ""
        }
        onCancel={() => setDeleteTarget(null)}
        onConfirm={async () => {
          if (!deleteTarget) return;
          if (deleteTarget.kind === "farm") {
            await deleteFarm(deleteTarget.farm.farm_id);
          } else {
            await deleteField(deleteTarget.field.farm_id, deleteTarget.field.field_id);
          }
          setDeleteTarget(null);
        }}
      />

      <AnalysisRunnerModal
        open={runnerModalState.open}
        lang={lang}
        farm={runnerFarm}
        farmFields={runnerFarmFields}
        initialFieldIds={runnerModalState.preselectFieldIds}
        catalogItems={catalogItems}
        submitting={analysisLifecycle === "pending" || analysisLifecycle === "running"}
        onClose={() => setRunnerModalState((prev) => ({ ...prev, open: false }))}
        onSubmit={(job) => void executeAnalysisJob(job)}
      />

      <AuthModal
        open={authModalOpen}
        theme={resolvedTheme}
        onClose={() => {
          setAuthModalOpen(false);
          void syncFromBackend();
        }}
      />
    </>
  );
}
