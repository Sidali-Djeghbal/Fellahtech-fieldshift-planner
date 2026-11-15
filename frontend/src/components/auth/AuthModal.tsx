"use client";

import React, { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  DownloadSimple,
  RocketLaunch,
  SignIn,
  SignOut,
  Trash,
  UserPlus,
  X,
} from "@phosphor-icons/react";
import {
  claimGuestSession,
  deleteDemoSession,
  deleteMe,
  exportMeData,
  getMe,
  listFarms,
  listFields,
  listFarmAnalyses,
  loginUser,
  logoutUser,
  registerUser,
  startGuestSession,
} from "@/lib/api/endpoints";
import { presentApiError } from "@/lib/api/errors";
import { UI_DICT } from "@/lib/i18n";
import { GUELMA_WORKSPACE_I18N } from "@/lib/i18n/guelmaWorkspace";
import { useAppStore } from "@/store/useAppStore";

interface AuthModalProps {
  open: boolean;
  onClose: () => void;
  theme?: "light" | "dark";
}

export function AuthModal({ open, onClose, theme = "light" }: AuthModalProps) {
  const queryClient = useQueryClient();
  const {
    lang,
    authMode,
    user,
    guestToken,
    refreshToken,
    setGuestSession,
    setAuthenticatedSession,
    clearGuestToken,
    clearSession,
    setActiveFarmId,
    setActiveFieldId,
    setActiveAnalysisId,
  } = useAppStore();

  const t = UI_DICT[lang].auth;
  const [tab, setTab] = useState<"login" | "register">("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const isDark = theme === "dark";

  useEffect(() => {
    if (!open) return;
    previousFocusRef.current = document.activeElement as HTMLElement | null;
    return () => {
      previousFocusRef.current?.focus?.();
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) {
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, busy, onClose]);

  if (!open) return null;

  async function hydrateWorkspaceAfterAuth() {
    const farmsPage = await listFarms();
    if (farmsPage.items.length > 0) {
      const firstFarm = farmsPage.items[0];
      setActiveFarmId(firstFarm.farm_id);
      const fieldsPage = await listFields(firstFarm.farm_id);
      if (fieldsPage.items.length > 0) {
        setActiveFieldId(fieldsPage.items[0].field_id);
      }
      const analyses = await listFarmAnalyses(firstFarm.farm_id);
      const okRun = analyses.items.find((a) => a.analysis_id);
      if (okRun?.analysis_id) {
        setActiveAnalysisId(okRun.analysis_id);
      }
    }
    await queryClient.invalidateQueries();
  }

  async function handleStartGuest() {
    setBusy(true);
    setErrorMsg(null);
    setStatusMsg(null);
    try {
      const res = await startGuestSession(1);
      setGuestSession({
        guestToken: res.guest_token,
        expiresAt: res.expires_at,
      });
      await hydrateWorkspaceAfterAuth();
      onClose();
    } catch (err) {
      setErrorMsg(presentApiError(err, lang).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmitAuth(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErrorMsg(null);
    setStatusMsg(null);
    try {
      if (tab === "register") {
        const res = await registerUser({
          email,
          password,
          full_name: fullName || UI_DICT[lang].chrome.guestWorkspace,
          preferred_lang: lang,
        });
        setAuthenticatedSession({
          accessToken: res.access_token,
          refreshToken: res.refresh_token,
          user: res.user,
          keepGuestToken: true,
        });
      } else {
        const tokens = await loginUser({ email, password });
        setAuthenticatedSession({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
          keepGuestToken: true,
        });
        const profile = await getMe();
        useAppStore.getState().setUser(profile);
      }
      await hydrateWorkspaceAfterAuth();
      setStatusMsg(t.signedInSuccess);
      if (!guestToken) {
        onClose();
      }
    } catch (err) {
      setErrorMsg(presentApiError(err, lang).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleClaimGuest() {
    setBusy(true);
    setErrorMsg(null);
    try {
      const res = await claimGuestSession();
      clearGuestToken();
      await hydrateWorkspaceAfterAuth();
      setStatusMsg(t.claimedGuestMsg(res.claimed_farms_count));
    } catch (err) {
      setErrorMsg(presentApiError(err, lang).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleExportData() {
    setBusy(true);
    setErrorMsg(null);
    try {
      const data = await exportMeData();
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `fieldshift-export-${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setStatusMsg(t.jsonDownloaded);
    } catch (err) {
      setErrorMsg(presentApiError(err, lang).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleLogout() {
    setBusy(true);
    try {
      await logoutUser(refreshToken);
    } catch {
      // Clear local session regardless
    } finally {
      clearSession();
      await queryClient.invalidateQueries();
      setBusy(false);
      onClose();
    }
  }

  async function handleResetGuest() {
    setBusy(true);
    try {
      await deleteDemoSession();
    } catch {
      // Ignore if already expired
    } finally {
      clearSession();
      await queryClient.invalidateQueries();
      setBusy(false);
      onClose();
    }
  }

  async function handleDeleteAccount() {
    setBusy(true);
    setErrorMsg(null);
    try {
      await deleteMe();
      clearSession();
      await queryClient.invalidateQueries();
      setConfirmDelete(false);
      onClose();
    } catch (err) {
      setErrorMsg(presentApiError(err, lang).message);
    } finally {
      setBusy(false);
    }
  }

  const inputClassName = isDark
    ? "min-h-10 w-full rounded-xl border border-white/12 bg-[#141A16] px-3 py-2 text-base text-[#F5F7F5] placeholder:text-[#78847B] transition-[border-color] focus:border-[#86EFAC]/60 focus:outline-none sm:text-xs"
    : "min-h-10 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-base text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B] sm:text-xs";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t.welcomeTitle}
      className="no-print fixed inset-0 z-50 flex items-center justify-center p-4 overscroll-contain"
    >
      <button
        type="button"
        onClick={onClose}
        aria-label={t.closeModalAria}
        className={isDark ? "fixed inset-0 bg-black/65 backdrop-blur-sm" : "fixed inset-0 bg-black/50 backdrop-blur-sm"}
      />
      <div
        className={
          isDark
            ? "fs-hud-glass relative z-10 w-full max-w-lg rounded-3xl p-6 text-[#F5F7F5] shadow-[0_32px_90px_rgba(0,0,0,0.65)]"
            : "relative z-10 w-full max-w-lg rounded-2xl border border-[#E5E7EB] bg-white p-6 text-[#111827] shadow-xl"
        }
      >
        <button
          type="button"
          onClick={onClose}
          aria-label={t.closeModalAria}
          className={
            isDark
              ? "fs-liquid-pill absolute end-4 top-4 flex h-10 w-10 items-center justify-center rounded-full text-[#9CA89E] hover:text-white active:not-disabled:scale-[0.96]"
              : "absolute end-4 top-4 flex h-10 w-10 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
          }
        >
          <X size={20} aria-hidden="true" />
        </button>

        <h2
          className={`font-heading pe-10 text-lg font-bold ${
            isDark ? "text-[#F5F7F5]" : "text-[#111827]"
          }`}
        >
          {t.welcomeTitle}
        </h2>
        <p className={`mt-1 text-xs ${isDark ? "text-[#9CA89E]" : "text-[#6B7280]"}`}>
          {t.welcomeBody}
        </p>

        {errorMsg && (
          <div
            role="alert"
            className={`mt-3 rounded-xl border px-3 py-2 text-xs ${
              isDark
                ? "border-red-400/30 bg-red-500/15 text-red-200"
                : "border-red-200 bg-red-50 text-red-700"
            }`}
          >
            {errorMsg}
          </div>
        )}
        {statusMsg && (
          <div
            className={`mt-3 rounded-xl border px-3 py-2 text-xs ${
              isDark
                ? "border-[#4ADE80]/30 bg-[#22C55E]/15 text-[#BBF7D0]"
                : "border-emerald-200 bg-emerald-50 text-emerald-800"
            }`}
          >
            {statusMsg}
          </div>
        )}

        {/* Claim guest session banner if user just signed in while holding guestToken */}
        {authMode === "authenticated" && guestToken && (
          <div
            className={
              isDark
                ? "fs-liquid-well mt-4 rounded-2xl p-4"
                : "mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3.5"
            }
          >
            <p className={`text-xs font-bold ${isDark ? "text-[#F5F7F5]" : "text-[#00291B]"}`}>
              {t.claimBannerTitle}
            </p>
            <p className={`mt-1 text-xs ${isDark ? "text-[#D1DBD3]" : "text-[#374151]"}`}>
              {t.claimBannerBody}
            </p>
            <button
              type="button"
              disabled={busy}
              onClick={handleClaimGuest}
              className={
                isDark
                  ? "fs-cta-primary mt-3 inline-flex min-h-9 items-center gap-1.5 rounded-full px-4 text-xs font-semibold active:not-disabled:scale-[0.97]"
                  : "mt-2.5 inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-[#00291B] px-3.5 py-1.5 text-xs font-bold text-white hover:bg-[#04421B]"
              }
            >
              <UserPlus size={15} weight="bold" aria-hidden="true" />
              {t.claimNowBtn}
            </button>
          </div>
        )}

        {/* Authenticated account drawer controls */}
        {authMode === "authenticated" && user ? (
          <div className="mt-4 space-y-3">
            <div
              className={
                isDark
                  ? "fs-liquid-well rounded-2xl p-3.5 text-xs"
                  : "rounded-xl border border-gray-200 bg-gray-50 p-3.5 text-xs"
              }
            >
              <p className={`font-bold ${isDark ? "text-[#F5F7F5]" : "text-[#111827]"}`}>
                {user.full_name}
              </p>
              <p dir="ltr" className={isDark ? "text-[#9CA89E]" : "text-gray-500"}>
                {user.email}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={handleExportData}
                className={
                  isDark
                    ? "fs-cta-primary inline-flex min-h-10 items-center gap-1.5 rounded-full px-4 text-xs font-semibold active:not-disabled:scale-[0.97]"
                    : "inline-flex min-h-10 items-center gap-1.5 rounded-lg bg-[#00291B] px-3 py-2 text-xs font-semibold text-white hover:bg-[#04421B]"
                }
              >
                <DownloadSimple size={16} aria-hidden="true" />
                {t.exportDataBtn}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={handleLogout}
                className={
                  isDark
                    ? "fs-liquid-pill inline-flex min-h-10 items-center gap-1.5 rounded-full px-4 text-xs font-semibold text-[#F5F7F5] active:not-disabled:scale-[0.97]"
                    : "inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-2 text-xs font-semibold text-[#111827] hover:bg-gray-100"
                }
              >
                <SignOut size={16} aria-hidden="true" />
                {t.logoutBtn}
              </button>
            </div>

            <div className={`border-t pt-3 ${isDark ? "border-white/10" : "border-gray-200"}`}>
              {!confirmDelete ? (
                <button
                  type="button"
                  onClick={() => setConfirmDelete(true)}
                  className={`inline-flex min-h-9 items-center gap-1.5 text-xs font-semibold hover:underline ${
                    isDark ? "text-red-300" : "text-red-600"
                  }`}
                >
                  <Trash size={14} aria-hidden="true" />
                  {t.deleteAccountBtn}
                </button>
              ) : (
                <div
                  className={`flex flex-wrap items-center gap-2 rounded-xl border p-2.5 text-xs ${
                    isDark
                      ? "border-red-400/30 bg-red-500/15"
                      : "border-red-200 bg-red-50"
                  }`}
                >
                  <span className={isDark ? "text-red-200" : "text-red-800"}>
                    {t.deleteConfirmText}
                  </span>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={handleDeleteAccount}
                    className="min-h-8 rounded-lg bg-red-600 px-2.5 py-1 font-bold text-white transition-colors hover:bg-red-700"
                  >
                    {GUELMA_WORKSPACE_I18N[lang].confirmDelete.confirmRemoveBtn}
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(false)}
                    className={
                      isDark
                        ? "fs-liquid-pill min-h-8 rounded-lg px-2.5 py-1 text-[#D1DBD3] hover:text-white"
                        : "min-h-8 rounded-lg border border-gray-300 px-2.5 py-1 text-gray-700 hover:bg-gray-100"
                    }
                  >
                    {GUELMA_WORKSPACE_I18N[lang].confirmDelete.cancelBtn}
                  </button>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            {authMode === "none" && (
              <button
                type="button"
                disabled={busy}
                onClick={handleStartGuest}
                data-testid="launch-guelma-demo-btn"
                className={
                  isDark
                    ? "fs-cta-primary flex min-h-11 w-full items-center justify-center gap-2 rounded-full px-4 py-2.5 text-sm font-semibold active:not-disabled:scale-[0.98]"
                    : "flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-[#00291B] px-4 py-2.5 text-sm font-bold text-white shadow-md transition-colors hover:bg-[#04421B]"
                }
              >
                <RocketLaunch
                  size={18}
                  weight="bold"
                  className={isDark ? "text-[#16A34A]" : "text-[#84E875]"}
                  aria-hidden="true"
                />
                {t.launchDemoBtn}
              </button>
            )}

            {authMode === "guest" && (
              <div
                className={
                  isDark
                    ? "fs-liquid-well flex items-center justify-between rounded-2xl px-3.5 py-2.5 text-xs"
                    : "flex items-center justify-between rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-xs"
                }
              >
                <span className={isDark ? "text-[#D1DBD3]" : "text-gray-700"}>
                  {UI_DICT[lang].chrome.guestWorkspace}
                </span>
                <button
                  type="button"
                  disabled={busy}
                  onClick={handleResetGuest}
                  className={`min-h-8 font-semibold hover:underline ${
                    isDark ? "text-red-300" : "text-red-600"
                  }`}
                >
                  {t.endGuestBtn}
                </button>
              </div>
            )}

            <div
              className={
                isDark
                  ? "inline-flex gap-1 rounded-full border border-white/12 bg-black/30 p-0.5"
                  : "flex gap-2 border-b border-gray-200 pb-2"
              }
            >
              <button
                type="button"
                onClick={() => setTab("register")}
                className={
                  isDark
                    ? `min-h-9 rounded-full px-3.5 py-1.5 text-xs font-semibold transition-[background-color,color] ${
                        tab === "register"
                          ? "bg-[#FFFFFF] text-[#111713] shadow-xs"
                          : "text-[#9CA89E] hover:text-white"
                      }`
                    : `min-h-9 rounded-lg px-3 py-1.5 text-xs font-bold transition-[background-color,color] ${
                        tab === "register"
                          ? "bg-[#00291B] text-white"
                          : "text-gray-500 hover:text-gray-900"
                      }`
                }
              >
                {t.registerTab}
              </button>
              <button
                type="button"
                onClick={() => setTab("login")}
                className={
                  isDark
                    ? `min-h-9 rounded-full px-3.5 py-1.5 text-xs font-semibold transition-[background-color,color] ${
                        tab === "login"
                          ? "bg-[#FFFFFF] text-[#111713] shadow-xs"
                          : "text-[#9CA89E] hover:text-white"
                      }`
                    : `min-h-9 rounded-lg px-3 py-1.5 text-xs font-bold transition-[background-color,color] ${
                        tab === "login"
                          ? "bg-[#00291B] text-white"
                          : "text-gray-500 hover:text-gray-900"
                      }`
                }
              >
                {t.signInTab}
              </button>
            </div>

            <form onSubmit={handleSubmitAuth} className="space-y-3">
              {tab === "register" && (
                <div>
                  <label
                    className={`mb-1 block text-xs font-semibold ${
                      isDark ? "text-[#D1DBD3]" : "text-gray-700"
                    }`}
                  >
                    {t.fullName}
                  </label>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Karim Benali"
                    className={inputClassName}
                  />
                </div>
              )}
              <div>
                <label
                  className={`mb-1 block text-xs font-semibold ${
                    isDark ? "text-[#D1DBD3]" : "text-gray-700"
                  }`}
                >
                  {t.email}
                </label>
                <input
                  type="email"
                  required
                  dir="ltr"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="farmer@guelma.dz"
                  className={inputClassName}
                />
              </div>
              <div>
                <label
                  className={`mb-1 block text-xs font-semibold ${
                    isDark ? "text-[#D1DBD3]" : "text-gray-700"
                  }`}
                >
                  {t.password}
                </label>
                <input
                  type="password"
                  required
                  minLength={8}
                  dir="ltr"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={inputClassName}
                />
              </div>
              <button
                type="submit"
                disabled={busy}
                className={
                  isDark
                    ? "fs-cta-primary inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-full px-4 py-2.5 text-sm font-semibold active:not-disabled:scale-[0.98]"
                    : "inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-[#00291B] px-4 py-2.5 text-sm font-bold text-white shadow-sm transition-colors hover:bg-[#04421B]"
                }
              >
                <SignIn size={18} aria-hidden="true" />
                {tab === "register" ? t.submitRegister : t.submitLogin}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
