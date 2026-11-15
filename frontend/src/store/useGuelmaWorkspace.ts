"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import {
  createFarm as apiCreateFarm,
  createField as apiCreateField,
  deleteFarm as apiDeleteFarm,
  deleteField as apiDeleteField,
  listFarms as apiListFarms,
  listFields as apiListFields,
  getField as apiGetField,
  patchFarm as apiPatchFarm,
  replaceField as apiReplaceField,
} from "@/lib/api/endpoints";
import {
  GUELMA_PARCEL_PRESETS,
  ringToGeoJsonPolygon,
} from "@/lib/geo/guelma";
import {
  serializeFieldWriteRequest,
  type FarmPatchRequest,
  type FarmPublic,
  type FarmWriteRequest,
  type FieldDetailPublic,
  type FieldWriteDraft,
  type Language,
} from "@/lib/schemas";
import { useAppStore } from "@/store/useAppStore";

export function deriveSoilSource(soil: FieldWriteDraft["soil"]): "farmer" | "unknown" {
  const hasType = soil.soil_type !== "unknown";
  const hasPh = soil.soil_ph !== "" && soil.soil_ph !== null && soil.soil_ph !== undefined;
  const hasOm =
    soil.organic_matter_percent !== "" &&
    soil.organic_matter_percent !== null &&
    soil.organic_matter_percent !== undefined;
  const hasDate = Boolean(soil.soil_test_date && String(soil.soil_test_date).trim() !== "");
  return hasType || hasPh || hasOm || hasDate ? "farmer" : "unknown";
}

function buildLocalFieldRecord(farmId: string, draft: FieldWriteDraft): FieldDetailPublic {
  const serialized = serializeFieldWriteRequest(draft);
  const soilSource = deriveSoilSource(draft.soil);

  return {
    farm_id: farmId,
    field_id: serialized.field_id,
    field_name: serialized.field_name,
    is_unverified_demo_parcel: Boolean(serialized.is_unverified_demo_parcel),
    location: {
      latitude: serialized.location.latitude,
      longitude: serialized.location.longitude,
      boundary: serialized.location.boundary ?? null,
    },
    area_hectares: serialized.area_hectares,
    elevation_m: serialized.elevation_m ?? null,
    soil: {
      soil_type: serialized.soil.soil_type,
      source: soilSource,
      soil_ph: serialized.soil.soil_ph ?? null,
      organic_matter_percent: serialized.soil.organic_matter_percent ?? null,
      soil_test_date: serialized.soil.soil_test_date ?? null,
    },
    water: {
      availability: serialized.water.availability,
      source: serialized.water.source,
      source_other: serialized.water.source_other ?? null,
      irrigation_system: serialized.water.irrigation_system,
    },
    warnings: [],
    crop_history: serialized.crop_history.map((item) => ({
      season: item.season,
      year: item.year,
      planting_month: item.planting_month ?? null,
      crop_id: item.crop_id ?? null,
      crop_name_raw: item.crop_name_raw ?? null,
      yield_tons_per_hectare: item.yield_tons_per_hectare ?? null,
      notes: item.notes ?? null,
    })),
  };
}

function nextNumericFarmId(existing: FarmPublic[]): string {
  const maxNum = existing.reduce((max, f) => {
    const m = /^farm_(\d+)$/.exec(f.farm_id);
    const n = m ? Number(m[1]) : 0;
    return Number.isFinite(n) && n > max ? n : max;
  }, 0);
  return `farm_${maxNum + 1}`;
}

export function fieldKey(farmId: string, fieldId: string): string {
  return `${farmId}::${fieldId}`;
}

export interface GuelmaWorkspaceState {
  farms: FarmPublic[];
  fields: FieldDetailPublic[];
  selectedFieldKey: string | null;
  syncing: boolean;
  lastError: string | null;

  selectField: (farmId: string, fieldId: string | null) => void;
  addFarmWithField: (
    farmPayload: FarmWriteRequest,
    fieldDraft: FieldWriteDraft
  ) => Promise<{ farm: FarmPublic; field: FieldDetailPublic }>;
  addFieldToFarm: (
    farmId: string,
    fieldDraft: FieldWriteDraft
  ) => Promise<FieldDetailPublic>;
  updateFarm: (farmId: string, patch: FarmPatchRequest) => Promise<void>;
  deleteFarm: (farmId: string) => Promise<void>;
  updateField: (
    farmId: string,
    fieldId: string,
    fieldDraft: FieldWriteDraft
  ) => Promise<FieldDetailPublic>;
  deleteField: (farmId: string, fieldId: string) => Promise<void>;
  loadSampleParcels: (lang: Language) => void;
  reconcileFarmId: (oldFarmId: string, nextFarm: FarmPublic) => void;
  syncFromBackend: () => Promise<void>;
  reset: () => void;
}

export const useGuelmaWorkspace = create<GuelmaWorkspaceState>()(
  persist(
    (set, get) => ({
      farms: [],
      fields: [],
      selectedFieldKey: null,
      syncing: false,
      lastError: null,

      selectField: (farmId, fieldId) =>
        set({
          selectedFieldKey: fieldId ? fieldKey(farmId, fieldId) : null,
        }),

      addFarmWithField: async (farmPayload, fieldDraft) => {
        const hasSession = useAppStore.getState().authMode !== "none";
        let createdFarm: FarmPublic;
        let createdField: FieldDetailPublic;

        if (hasSession) {
          try {
            createdFarm = await apiCreateFarm(farmPayload);
            const pub = await apiCreateField(createdFarm.farm_id, fieldDraft);
            createdField = {
              ...pub,
              crop_history: buildLocalFieldRecord(createdFarm.farm_id, fieldDraft).crop_history,
            };
          } catch {
            const farmId = nextNumericFarmId(get().farms);
            createdFarm = {
              farm_id: farmId,
              farm_name: farmPayload.farm_name,
              country: farmPayload.country,
              region: farmPayload.region,
              commune: farmPayload.commune ?? null,
              field_count: 1,
              created_at: new Date().toISOString(),
            };
            createdField = buildLocalFieldRecord(farmId, fieldDraft);
          }
        } else {
          const farmId = nextNumericFarmId(get().farms);
          createdFarm = {
            farm_id: farmId,
            farm_name: farmPayload.farm_name,
            country: farmPayload.country,
            region: farmPayload.region,
            commune: farmPayload.commune ?? null,
            field_count: 1,
            created_at: new Date().toISOString(),
          };
          createdField = buildLocalFieldRecord(farmId, fieldDraft);
        }

        const existingFarms = get().farms.filter((f) => f.farm_id !== createdFarm.farm_id);
        const fields = [...get().fields, createdField];
        const finalFarm: FarmPublic = {
          ...createdFarm,
          field_count: fields.filter((fld) => fld.farm_id === createdFarm.farm_id).length,
        };

        set({
          farms: [...existingFarms, finalFarm],
          fields,
          selectedFieldKey: fieldKey(finalFarm.farm_id, createdField.field_id),
          lastError: null,
        });

        useAppStore.getState().setActiveFarmId(finalFarm.farm_id);
        useAppStore.getState().setActiveFieldId(createdField.field_id);
        return { farm: finalFarm, field: createdField };
      },

      addFieldToFarm: async (farmId, fieldDraft) => {
        const hasSession = useAppStore.getState().authMode !== "none";
        let createdField: FieldDetailPublic;

        if (hasSession) {
          try {
            const pub = await apiCreateField(farmId, fieldDraft);
            createdField = {
              ...pub,
              crop_history: buildLocalFieldRecord(farmId, fieldDraft).crop_history,
            };
          } catch {
            createdField = buildLocalFieldRecord(farmId, fieldDraft);
          }
        } else {
          createdField = buildLocalFieldRecord(farmId, fieldDraft);
        }

        const existingWithoutDup = get().fields.filter(
          (f) => !(f.farm_id === farmId && f.field_id === createdField.field_id)
        );
        const nextFields = [...existingWithoutDup, createdField];
        const nextFarms = get().farms.map((farm) =>
          farm.farm_id === farmId
            ? {
                ...farm,
                field_count: nextFields.filter((fld) => fld.farm_id === farmId).length,
              }
            : farm
        );

        set({
          farms: nextFarms,
          fields: nextFields,
          selectedFieldKey: fieldKey(farmId, createdField.field_id),
          lastError: null,
        });

        useAppStore.getState().setActiveFarmId(farmId);
        useAppStore.getState().setActiveFieldId(createdField.field_id);
        return createdField;
      },

      updateFarm: async (farmId, patch) => {
        const hasSession = useAppStore.getState().authMode !== "none";
        if (hasSession) {
          try {
            await apiPatchFarm(farmId, patch);
          } catch {
            /* keep local update */
          }
        }
        set((state) => ({
          farms: state.farms.map((f) =>
            f.farm_id === farmId
              ? {
                  ...f,
                  ...(patch.farm_name !== undefined ? { farm_name: patch.farm_name } : {}),
                  ...(patch.commune !== undefined ? { commune: patch.commune } : {}),
                }
              : f
          ),
        }));
      },

      deleteFarm: async (farmId) => {
        const hasSession = useAppStore.getState().authMode !== "none";
        if (hasSession) {
          try {
            await apiDeleteFarm(farmId);
          } catch {
            /* keep local removal */
          }
        }
        set((state) => {
          const nextFarms = state.farms.filter((f) => f.farm_id !== farmId);
          const nextFields = state.fields.filter((f) => f.farm_id !== farmId);
          const firstField = nextFields[0] ?? null;
          return {
            farms: nextFarms,
            fields: nextFields,
            selectedFieldKey:
              state.selectedFieldKey?.startsWith(`${farmId}::`)
                ? firstField
                  ? fieldKey(firstField.farm_id, firstField.field_id)
                  : null
                : state.selectedFieldKey,
          };
        });
      },

      updateField: async (farmId, fieldId, fieldDraft) => {
        const hasSession = useAppStore.getState().authMode !== "none";
        let updatedField: FieldDetailPublic;
        const nextDraft: FieldWriteDraft = { ...fieldDraft, field_id: fieldId };

        if (hasSession) {
          try {
            updatedField = await apiReplaceField(farmId, fieldId, nextDraft);
          } catch {
            updatedField = buildLocalFieldRecord(farmId, nextDraft);
          }
        } else {
          updatedField = buildLocalFieldRecord(farmId, nextDraft);
        }

        set((state) => ({
          fields: state.fields.map((f) =>
            f.farm_id === farmId && f.field_id === fieldId ? updatedField : f
          ),
          selectedFieldKey: fieldKey(farmId, fieldId),
        }));

        return updatedField;
      },

      deleteField: async (farmId, fieldId) => {
        const hasSession = useAppStore.getState().authMode !== "none";
        if (hasSession) {
          try {
            await apiDeleteField(farmId, fieldId);
          } catch {
            /* keep local removal */
          }
        }
        set((state) => {
          const nextFields = state.fields.filter(
            (f) => !(f.farm_id === farmId && f.field_id === fieldId)
          );
          const nextFarms = state.farms.map((farm) =>
            farm.farm_id === farmId
              ? {
                  ...farm,
                  field_count: nextFields.filter((fld) => fld.farm_id === farmId).length,
                }
              : farm
          );
          const currentRemoved = state.selectedFieldKey === fieldKey(farmId, fieldId);
          const fallback = nextFields[0] ?? null;
          return {
            farms: nextFarms,
            fields: nextFields,
            selectedFieldKey: currentRemoved
              ? fallback
                ? fieldKey(fallback.farm_id, fallback.field_id)
                : null
              : state.selectedFieldKey,
          };
        });
      },

      loadSampleParcels: (lang) => {
        const currentFarms = get().farms;
        const currentFields = get().fields;
        const sampleFarmId = currentFarms.some((f) => f.farm_id === "farm_1")
          ? nextNumericFarmId(currentFarms)
          : "farm_1";

        const sampleName =
          lang === "ar"
            ? "مستثمرة سيبوس النموذجية · قالمة"
            : lang === "fr"
            ? "Exploitation Pilote Seybouse · Guelma"
            : "Seybouse Pilot Farm · Guelma";

        const sampleFarm: FarmPublic = {
          farm_id: sampleFarmId,
          farm_name: sampleName,
          country: "Algeria",
          region: "Guelma",
          commune: "Guelma",
          field_count: 4,
          created_at: new Date().toISOString(),
        };

        const pickedPresets = GUELMA_PARCEL_PRESETS.slice(0, 4);
        const sampleFields: FieldDetailPublic[] = pickedPresets.map((p, idx) =>
          buildLocalFieldRecord(sampleFarmId, {
            field_id: `G-${idx + 1}`,
            field_name: p.zoneName[lang] || p.zoneName.en,
            is_unverified_demo_parcel: false,
            location: {
              longitude: p.center[0],
              latitude: p.center[1],
              boundary: ringToGeoJsonPolygon(p.ring),
            },
            area_hectares: p.areaHectares,
            elevation_m: "",
            soil: {
              soil_type: "unknown",
              soil_ph: "",
              organic_matter_percent: "",
              soil_test_date: "",
            },
            water: {
              availability: idx < 2 ? "moderate" : "limited",
              source: idx === 0 ? "dam_reservoir" : "rainwater",
              source_other: "",
              irrigation_system: idx === 0 ? "sprinkler" : "rainfed",
            },
            crop_history: [
              {
                season: "autumn",
                year: 2024,
                planting_month: 11,
                crop_id: idx % 2 === 0 ? "durum_wheat" : "barley",
                crop_name_raw: "",
                yield_tons_per_hectare: idx === 0 ? 3.2 : 2.1,
                notes: `${p.commune} · Demo sample`,
              },
            ],
          })
        );

        set({
          farms: [...currentFarms, sampleFarm],
          fields: [...currentFields, ...sampleFields],
          selectedFieldKey: fieldKey(sampleFarmId, sampleFields[0].field_id),
        });
      },

      reconcileFarmId: (oldFarmId, nextFarm) =>
        set((state) => {
          const nextFields = state.fields.map((fld) =>
            fld.farm_id === oldFarmId ? { ...fld, farm_id: nextFarm.farm_id } : fld
          );
          const nextSelected =
            state.selectedFieldKey && state.selectedFieldKey.startsWith(`${oldFarmId}::`)
              ? `${nextFarm.farm_id}::${state.selectedFieldKey.slice(oldFarmId.length + 2)}`
              : state.selectedFieldKey;
          return {
            farms: state.farms.map((fm) =>
              fm.farm_id === oldFarmId
                ? {
                    ...nextFarm,
                    field_count: nextFields.filter((fld) => fld.farm_id === nextFarm.farm_id)
                      .length,
                  }
                : fm
            ),
            fields: nextFields,
            selectedFieldKey: nextSelected,
          };
        }),

      syncFromBackend: async () => {
        if (useAppStore.getState().authMode === "none") return;
        set({ syncing: true });
        try {
          const farmPage = await apiListFarms();
          const allFields: FieldDetailPublic[] = [];
          for (const farm of farmPage.items) {
            const page = await apiListFields(farm.farm_id);
            for (const fSummary of page.items) {
              try {
                const detail = await apiGetField(farm.farm_id, fSummary.field_id);
                allFields.push(detail);
              } catch {
                allFields.push({ ...fSummary, crop_history: [] });
              }
            }
          }
          if (farmPage.items.length > 0 || get().farms.length === 0) {
            set({
              farms: farmPage.items,
              fields: allFields,
              selectedFieldKey: allFields[0]
                ? fieldKey(allFields[0].farm_id, allFields[0].field_id)
                : null,
              syncing: false,
            });
          } else {
            set({ syncing: false });
          }
        } catch {
          set({ syncing: false });
        }
      },

      reset: () =>
        set({
          farms: [],
          fields: [],
          selectedFieldKey: null,
          syncing: false,
          lastError: null,
        }),
    }),
    {
      name: "fieldshift.guelma.workspace.v1",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        farms: state.farms,
        fields: state.fields,
        selectedFieldKey: state.selectedFieldKey,
      }),
    }
  )
);
