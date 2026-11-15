"use client";

import React, { useEffect, useState } from "react";
import { Check, Trash, Warning, X } from "@phosphor-icons/react";
import { GUELMA_COMMUNES } from "@/lib/geo/guelma";
import { GUELMA_WORKSPACE_I18N } from "@/lib/i18n/guelmaWorkspace";
import type { FarmPatchRequest, FarmPublic, Language } from "@/lib/schemas";

interface EditFarmModalProps {
  open: boolean;
  lang: Language;
  farm: FarmPublic | null;
  onClose: () => void;
  onSave: (farmId: string, patch: FarmPatchRequest) => Promise<void> | void;
}

export function EditFarmModal({
  open,
  lang,
  farm,
  onClose,
  onSave,
}: EditFarmModalProps) {
  const dict = GUELMA_WORKSPACE_I18N[lang];
  const [name, setName] = useState("");
  const [commune, setCommune] = useState("Guelma");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (farm && open) {
      setName(farm.farm_name);
      setCommune(farm.commune || "Guelma");
    }
  }, [farm, open]);

  if (!open || !farm) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      await onSave(farm.farm_id, {
        farm_name: name.trim(),
        commune: commune || null,
      });
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      data-testid="edit-farm-modal"
    >
      <div className="w-full max-w-md rounded-2xl border border-[#DCE3DF] bg-white p-5 text-[#111827] shadow-xl">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-base font-bold text-[#0B4B2E]">{dict.editFarmModal.title}</h3>
            <p className="mt-0.5 text-xs text-[#6B7280]">{dict.editFarmModal.subtitle}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-gray-400 hover:text-gray-700"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-3">
          <div>
            <label className="block text-xs font-semibold text-[#374151]">
              {dict.form.farmNameLabel}
            </label>
            <input
              type="text"
              required
              maxLength={120}
              value={name}
              onChange={(e) => setName(e.target.value)}
              data-testid="edit-farm-name-input"
              className="mt-1 w-full rounded-lg border border-[#D1D5DB] bg-white px-3 py-2 text-xs text-[#111827]"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#374151]">
              {dict.form.communeLabel}
            </label>
            <select
              value={commune}
              onChange={(e) => setCommune(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[#D1D5DB] bg-white px-3 py-2 text-xs text-[#111827]"
            >
              {GUELMA_COMMUNES.map((c) => (
                <option key={c.id} value={c.name.en}>
                  {c.name[lang] || c.name.en} ({c.daira[lang] || c.daira.en})
                </option>
              ))}
            </select>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-[#D1D5DB] bg-white px-3.5 py-2 text-xs font-semibold text-[#374151]"
            >
              {dict.form.cancelBtn}
            </button>
            <button
              type="submit"
              disabled={saving}
              data-testid="edit-farm-save-btn"
              className="inline-flex items-center gap-1 rounded-xl bg-[#0B4B2E] px-4 py-2 text-xs font-bold text-white hover:bg-[#137135]"
            >
              <Check size={14} weight="bold" />
              <span>{dict.editFarmModal.saveBtn}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

interface ConfirmDeleteModalProps {
  open: boolean;
  lang: Language;
  title: string;
  body: string;
  onCancel: () => void;
  onConfirm: () => Promise<void> | void;
}

export function ConfirmDeleteModal({
  open,
  lang,
  title,
  body,
  onCancel,
  onConfirm,
}: ConfirmDeleteModalProps) {
  const dict = GUELMA_WORKSPACE_I18N[lang].confirmDelete;
  const [busy, setBusy] = useState(false);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      data-testid="confirm-delete-modal"
    >
      <div className="w-full max-w-sm rounded-2xl border border-red-200 bg-white p-5 text-[#111827] shadow-xl">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-red-100 text-red-600">
            <Warning size={19} weight="fill" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-[#111827]">{title}</h3>
            <p className="mt-1 text-xs leading-relaxed text-[#4B5563]">{body}</p>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-xl border border-[#D1D5DB] bg-white px-3.5 py-1.5 text-xs font-semibold text-[#374151]"
          >
            {dict.cancelBtn}
          </button>
          <button
            type="button"
            disabled={busy}
            data-testid="confirm-delete-btn"
            onClick={async () => {
              setBusy(true);
              try {
                await onConfirm();
              } finally {
                setBusy(false);
              }
            }}
            className="inline-flex items-center gap-1.5 rounded-xl bg-red-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-red-700"
          >
            <Trash size={14} />
            <span>{dict.confirmRemoveBtn}</span>
          </button>
        </div>
      </div>
    </div>
  );
}

