"use client";

import React, { useEffect, useMemo, useState } from "react";
import { FieldShiftPrototypeApp } from "@/components/prototype/FieldShiftPrototypeApp";
import { GuelmaFarmerDashboard } from "@/components/guelma/GuelmaFarmerDashboard";
import {
  GuelmaBorderEditorMap,
  type BorderDraftResult,
} from "@/components/guelma/GuelmaBorderEditorMap";
import {
  FarmFieldInfoModal,
  type FarmFieldFormSubmitPayload,
} from "@/components/guelma/FarmFieldInfoModal";
import {
  ConfirmDeleteModal,
  EditFarmModal,
} from "@/components/guelma/FarmWorkspaceModals";
import { extractRingFromBoundary, GUELMA_COMMUNES } from "@/lib/geo/guelma";
import { GUELMA_WORKSPACE_I18N } from "@/lib/i18n/guelmaWorkspace";
import { fieldToPreset } from "@/lib/prototype/engine";
import type { Preset } from "@/lib/prototype/types";
import type { FarmPublic, FieldDetailPublic, Language } from "@/lib/schemas";
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
  const lang = useAppStore((s) => s.lang);
  const setStoreLang = useAppStore((s) => s.setLang);

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

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    try {
      localStorage.setItem("fieldshift.lang", lang);
    } catch {
      /* ignore */
    }
  }, [lang]);

  const dict = GUELMA_WORKSPACE_I18N[lang];

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
          farms={farms}
          fields={fields}
          selectedFieldKey={selectedFieldKey}
          onChangeLang={handleChangeLang}
          onSelectField={(farmId, fieldId) => selectField(farmId, fieldId)}
          onStartAddFarm={handleStartAddFarm}
          onStartAddFieldToFarm={handleStartAddFieldToFarm}
          onLoadSamples={() => loadSampleParcels(lang)}
          onResetWorkspace={resetWorkspace}
          onInspectField={handleInspectField}
          onEditFieldBorders={handleEditFieldBorders}
          onEditFieldInfo={handleEditFieldInfo}
          onRequestRemoveField={(field) => setDeleteTarget({ kind: "field", field })}
          onEditFarm={(farm) => setEditingFarm(farm)}
          onRequestRemoveFarm={(farm) => setDeleteTarget({ kind: "farm", farm })}
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
    </>
  );
}
