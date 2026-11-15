"use client";

import React, { useEffect, useRef } from "react";
import { Monitor, Moon, Sun, Translate, Trash, UserCircle, X } from "@phosphor-icons/react";
import { INTELLIGENCE_I18N } from "@/lib/i18n/intelligence";
import { GUELMA_WORKSPACE_I18N } from "@/lib/i18n/guelmaWorkspace";
import type { Language } from "@/lib/schemas";
import type { AuthMode, ThemePreference } from "@/store/useAppStore";

interface WorkstationSettingsDrawerProps {
  open: boolean;
  lang: Language;
  theme: ThemePreference;
  plainMode: boolean;
  authMode: AuthMode;
  userEmail?: string | null;
  hasFarms: boolean;
  onClose: () => void;
  onChangeLang: (lang: Language) => void;
  onChangeTheme: (theme: ThemePreference) => void;
  onTogglePlainMode: () => void;
  onOpenAuth: () => void;
  onResetWorkspace: () => void;
}

export function WorkstationSettingsDrawer({
  open,
  lang,
  theme,
  plainMode,
  authMode,
  userEmail,
  hasFarms,
  onClose,
  onChangeLang,
  onChangeTheme,
  onTogglePlainMode,
  onOpenAuth,
  onResetWorkspace,
}: WorkstationSettingsDrawerProps) {
  const closeBtnRef = useRef<HTMLButtonElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;

    previousFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const raf = window.requestAnimationFrame(() => closeBtnRef.current?.focus());

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.cancelAnimationFrame(raf);
      window.removeEventListener("keydown", handleKeyDown);
      previousFocusRef.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  const intel = INTELLIGENCE_I18N[lang];
  const st = intel.workstation.settings;
  const dict = GUELMA_WORKSPACE_I18N[lang];

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end overscroll-contain"
      role="dialog"
      aria-modal="true"
      aria-label={st.title}
      data-testid="settings-drawer"
    >
      <button
        type="button"
        tabIndex={-1}
        aria-label={st.closeBtn}
        onClick={onClose}
        className="fixed inset-0 bg-[#0F1711]/30 backdrop-blur-sm dark:bg-black/60"
      />

      <div className="fs-hud-glass relative z-10 flex h-full w-full max-w-md flex-col justify-between overscroll-contain rounded-none sm:my-3 sm:me-3 sm:h-[calc(100%-24px)] sm:rounded-3xl">
        <div className="flex-1 overflow-y-auto overscroll-contain px-6 py-6">
          <div className="flex items-start justify-between gap-4 pb-6">
            <div>
              <h2 className="font-heading text-lg font-semibold leading-[1.15] text-[#111813] dark:text-[#F5F7F5]">
                {st.title}
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-[#4A5A4E] dark:text-[#9CA89E]">
                {st.subtitle}
              </p>
            </div>
            <button
              ref={closeBtnRef}
              type="button"
              onClick={onClose}
              aria-label={st.closeBtn}
              data-testid="close-settings-drawer-btn"
              className="fs-liquid-pill flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[#4A5A4E] hover:text-[#111813] active:not-disabled:scale-[0.96] dark:text-[#9CA89E] dark:hover:text-[#FFFFFF]"
            >
              <X size={16} aria-hidden="true" />
            </button>
          </div>

          <div className="divide-y divide-[#111813]/10 dark:divide-white/10">
            {/* Account & Session */}
            <div className="py-5">
              <p className="text-xs font-semibold text-[#111813] dark:text-[#F5F7F5]">
                {st.accountHeading}
              </p>
              <p className="mt-1 text-xs text-[#4A5A4E] dark:text-[#9CA89E]">
                {authMode === "authenticated"
                  ? userEmail || intel.header.signedInBadge
                  : authMode === "guest"
                    ? intel.header.guestBadge
                    : intel.header.accountBtn}
              </p>
              <button
                type="button"
                onClick={() => {
                  onClose();
                  onOpenAuth();
                }}
                data-testid="settings-auth-btn"
                className="fs-liquid-pill mt-3 inline-flex min-h-10 items-center gap-2 rounded-full ps-3 pe-3.5 text-xs font-medium text-[#111813] active:not-disabled:scale-[0.96] dark:text-[#F5F7F5]"
              >
                <UserCircle size={15} className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
                <span>{st.openAccountBtn}</span>
              </button>
            </div>

            {/* Appearance & Theme */}
            <div className="py-5">
              <p id="drawer-theme-label" className="text-xs font-semibold text-[#111813] dark:text-[#F5F7F5]">
                {st.appearanceHeading}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-[#4A5A4E] dark:text-[#9CA89E]">
                {st.appearanceDesc}
              </p>
              <div
                role="radiogroup"
                aria-labelledby="drawer-theme-label"
                className="fs-liquid-well mt-2.5 inline-flex rounded-full p-1 text-xs font-medium"
                onKeyDown={(e) => {
                  const order: readonly ThemePreference[] = ["system", "light", "dark"];
                  const idx = order.indexOf(theme);
                  if (e.key === "ArrowRight" || e.key === "ArrowDown") {
                    e.preventDefault();
                    onChangeTheme(order[(idx + 1) % order.length]);
                  } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
                    e.preventDefault();
                    onChangeTheme(order[(idx + order.length - 1) % order.length]);
                  }
                }}
              >
                {(
                  [
                    { id: "system", label: st.themeSystem, Icon: Monitor },
                    { id: "light", label: st.themeLight, Icon: Sun },
                    { id: "dark", label: st.themeDark, Icon: Moon },
                  ] as const
                ).map(({ id, label, Icon }) => {
                  const isActive = theme === id;
                  return (
                    <button
                      key={id}
                      type="button"
                      role="radio"
                      aria-checked={isActive}
                      data-testid={`settings-theme-${id}`}
                      onClick={() => onChangeTheme(id)}
                      className={`inline-flex min-h-10 items-center gap-1.5 rounded-full px-3.5 transition-[transform,background-color,box-shadow,color] duration-150 ease-out active:scale-[0.96] ${
                        isActive
                          ? "bg-[#0B3D2E] font-semibold text-white shadow-xs dark:bg-[#FFFFFF] dark:text-[#111713]"
                          : "text-[#4A5A4E] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:text-[#F5F7F5]"
                      }`}
                    >
                      <Icon size={14} weight={isActive ? "fill" : "regular"} aria-hidden="true" />
                      <span>{label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Language */}
            <div className="py-5">
              <p id="drawer-lang-label" className="text-xs font-semibold text-[#111813] dark:text-[#F5F7F5]">
                {st.languageHeading}
              </p>
              <div
                role="radiogroup"
                aria-labelledby="drawer-lang-label"
                className="fs-liquid-well mt-2.5 inline-flex rounded-full p-1 text-xs font-medium"
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
                    className={`min-h-10 rounded-full px-3.5 uppercase transition-[transform,background-color,box-shadow,color] duration-150 ease-out active:scale-[0.96] ${
                      lang === l
                        ? "bg-[#0B3D2E] font-semibold text-white shadow-xs dark:bg-[#FFFFFF] dark:text-[#111713]"
                        : "text-[#4A5A4E] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:text-[#F5F7F5]"
                    }`}
                  >
                    {l}
                  </button>
                ))}
              </div>
            </div>

            {/* Terminology Mode */}
            <div className="py-5">
              <p className="text-xs font-semibold text-[#111813] dark:text-[#F5F7F5]">
                {st.terminologyHeading}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-[#4A5A4E] dark:text-[#9CA89E]">
                {st.terminologyDesc}
              </p>
              <button
                type="button"
                onClick={onTogglePlainMode}
                className="fs-liquid-pill mt-3 inline-flex min-h-10 items-center gap-2 rounded-full ps-3 pe-3.5 text-xs font-medium text-[#111813] active:not-disabled:scale-[0.96] dark:text-[#F5F7F5]"
              >
                <Translate size={14} className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
                <span>
                  {plainMode ? intel.section.plainModeOn : intel.section.plainModeOff}
                </span>
              </button>
            </div>

            {/* Workspace Data */}
            {hasFarms ? (
              <div className="py-5">
                <p className="text-xs font-semibold text-[#111813] dark:text-[#F5F7F5]">
                  {st.workspaceHeading}
                </p>
                <p className="mt-1 text-xs leading-relaxed text-[#4A5A4E] dark:text-[#9CA89E]">
                  {st.clearWorkspaceDesc}
                </p>
                <button
                  type="button"
                  onClick={() => {
                    onResetWorkspace();
                    onClose();
                  }}
                  data-testid="reset-workspace-btn"
                  className="mt-3 inline-flex min-h-10 items-center gap-1.5 rounded-full bg-red-50 ps-3 pe-3.5 text-xs font-medium text-red-700 ring-1 ring-red-600/25 transition-[transform,background-color] duration-150 ease-out hover:bg-red-100 active:scale-[0.96] dark:bg-red-500/15 dark:text-red-300 dark:ring-red-400/25 dark:hover:bg-red-500/25"
                >
                  <Trash size={14} aria-hidden="true" />
                  <span>{dict.clearWorkspaceBtn}</span>
                </button>
              </div>
            ) : null}
          </div>
        </div>

        <div className="border-t border-[#111813]/10 bg-[#111813]/[0.03] px-6 py-4 text-end dark:border-white/10 dark:bg-white/[0.03]">
          <button
            type="button"
            onClick={onClose}
            className="fs-liquid-pill min-h-10 rounded-full px-5 text-xs font-medium text-[#111813] active:not-disabled:scale-[0.96] dark:text-[#F5F7F5]"
          >
            {st.closeBtn}
          </button>
        </div>
      </div>
    </div>
  );
}
