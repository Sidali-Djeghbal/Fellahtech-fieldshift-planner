"use client";

import React, { useEffect, useId, useRef, useState } from "react";
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
  const titleId = useId();
  const nameInputId = useId();
  const communeSelectId = useId();
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (farm && open) {
      setName(farm.farm_name);
      setCommune(farm.commune || "Guelma");
    }
  }, [farm, open]);

  useEffect(() => {
    if (!open) return;
    previousFocusRef.current = document.activeElement as HTMLElement | null;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !saving) onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      previousFocusRef.current?.focus();
    };
  }, [open, onClose, saving]);

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
      className="fixed inset-0 z-50 flex items-center justify-center p-4 overscroll-contain"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      data-testid="edit-farm-modal"
    >
      <button
        type="button"
        onClick={onClose}
        aria-label={dict.form.cancelBtn}
        className="fixed inset-0 bg-[#0F1711]/30 backdrop-blur-xs dark:bg-black/60"
      />
      <div className="fs-hud-glass relative z-10 w-full max-w-md rounded-3xl p-6 text-[#111813] dark:text-[#F5F7F5]">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 id={titleId} className="font-heading text-base font-semibold text-[#111813] dark:text-[#F5F7F5]">
              {dict.editFarmModal.title}
            </h3>
            <p className="mt-0.5 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">{dict.editFarmModal.subtitle}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={dict.form.cancelBtn}
            className="fs-liquid-pill flex h-10 w-10 items-center justify-center rounded-full text-[#4A5A4E] hover:text-[#111813] active:not-disabled:scale-[0.96] dark:text-[#9CA89E] dark:hover:text-[#FFFFFF]"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-3.5">
          <div>
            <label htmlFor={nameInputId} className="block text-xs font-semibold text-[#243227] dark:text-[#E4EBE5]">
              {dict.form.farmNameLabel}
            </label>
            <input
              id={nameInputId}
              type="text"
              required
              maxLength={120}
              value={name}
              onChange={(e) => setName(e.target.value)}
              data-testid="edit-farm-name-input"
              className="mt-1 min-h-10 w-full rounded-xl border border-[#111813]/15 bg-white/90 px-3.5 py-2 text-base text-[#111813] focus:border-[#15803D] focus:outline-none dark:border-white/12 dark:bg-[#141A16] dark:text-[#F5F7F5] dark:focus:border-[#86EFAC]/60 sm:text-xs"
            />
          </div>
          <div>
            <label htmlFor={communeSelectId} className="block text-xs font-semibold text-[#243227] dark:text-[#E4EBE5]">
              {dict.form.communeLabel}
            </label>
            <select
              id={communeSelectId}
              value={commune}
              onChange={(e) => setCommune(e.target.value)}
              className="mt-1 min-h-10 w-full rounded-xl border border-[#111813]/15 bg-white/90 px-3.5 py-2 text-base text-[#111813] focus:border-[#15803D] focus:outline-none dark:border-white/12 dark:bg-[#141A16] dark:text-[#F5F7F5] dark:focus:border-[#86EFAC]/60 sm:text-xs"
            >
              {GUELMA_COMMUNES.map((c) => (
                <option key={c.id} value={c.name.en}>
                  {c.name[lang] || c.name.en} ({c.daira[lang] || c.daira.en})
                </option>
              ))}
            </select>
          </div>
          <div className="flex justify-end gap-2.5 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="fs-liquid-pill min-h-10 rounded-full px-4 text-xs font-semibold text-[#111813] active:not-disabled:scale-[0.96] dark:text-[#E4EBE5]"
            >
              {dict.form.cancelBtn}
            </button>
            <button
              type="submit"
              disabled={saving}
              data-testid="edit-farm-save-btn"
              className="fs-cta-primary inline-flex min-h-10 items-center gap-1.5 rounded-full ps-4 pe-4.5 text-xs font-semibold active:not-disabled:scale-[0.96] disabled:opacity-60"
            >
              <Check size={14} weight="bold" aria-hidden="true" />
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
  const titleId = useId();
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previousFocusRef.current = document.activeElement as HTMLElement | null;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onCancel();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      previousFocusRef.current?.focus();
    };
  }, [open, onCancel, busy]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 overscroll-contain"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      data-testid="confirm-delete-modal"
    >
      <button
        type="button"
        onClick={onCancel}
        aria-label={dict.cancelBtn}
        className="fixed inset-0 bg-[#0F1711]/30 backdrop-blur-xs dark:bg-black/60"
      />
      <div className="fs-hud-glass relative z-10 w-full max-w-sm rounded-3xl p-6 text-[#111813] dark:text-[#F5F7F5]">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-red-50 text-red-600 ring-1 ring-red-600/20 dark:bg-red-500/20 dark:text-red-300 dark:ring-red-400/30">
            <Warning size={19} weight="fill" aria-hidden="true" />
          </div>
          <div>
            <h3 id={titleId} className="font-heading text-sm font-semibold text-[#111813] dark:text-[#F5F7F5]">
              {title}
            </h3>
            <p className="mt-1 max-w-[65ch] text-xs leading-relaxed text-[#4A5A4E] dark:text-[#9CA89E]">{body}</p>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2.5">
          <button
            type="button"
            onClick={onCancel}
            className="fs-liquid-pill min-h-10 rounded-full px-4 text-xs font-semibold text-[#111813] active:not-disabled:scale-[0.96] dark:text-[#E4EBE5]"
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
            className="inline-flex min-h-10 items-center gap-1.5 rounded-full bg-red-600 ps-3.5 pe-4 text-xs font-semibold text-white shadow-sm transition-[transform,background-color] hover:bg-red-700 active:not-disabled:scale-[0.96] disabled:opacity-60"
          >
            <Trash size={14} aria-hidden="true" />
            <span>{dict.confirmRemoveBtn}</span>
          </button>
        </div>
      </div>
    </div>
  );
}

