"use client";

import React, { useState } from "react";
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
import { useAppStore } from "@/store/useAppStore";

interface AuthModalProps {
  open: boolean;
  onClose: () => void;
}

export function AuthModal({ open, onClose }: AuthModalProps) {
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
          full_name: fullName || "Guelma Farmer",
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
      setStatusMsg("Signed in successfully.");
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
      setStatusMsg(`Claimed ${res.claimed_farms_count} guest farm(s) into your account.`);
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
      setStatusMsg("JSON export downloaded.");
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

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t.welcomeTitle}
      className="no-print fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
    >
      <div className="relative w-full max-w-lg rounded-2xl bg-white border border-[#E5E7EB] p-6 text-[#111827] shadow-xl">
        <button
          type="button"
          onClick={onClose}
          aria-label="Close authentication modal"
          className="absolute end-4 top-4 rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
        >
          <X size={20} />
        </button>

        <h2 className="font-heading text-lg font-bold text-[#111827]">{t.welcomeTitle}</h2>
        <p className="mt-1 text-xs text-[#6B7280]">{t.welcomeBody}</p>

        {errorMsg && (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {errorMsg}
          </div>
        )}
        {statusMsg && (
          <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
            {statusMsg}
          </div>
        )}

        {/* Claim guest session banner if user just signed in while holding guestToken */}
        {authMode === "authenticated" && guestToken && (
          <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3.5">
            <p className="text-xs font-bold text-[#00291B]">{t.claimBannerTitle}</p>
            <p className="mt-1 text-xs text-[#374151]">{t.claimBannerBody}</p>
            <button
              type="button"
              disabled={busy}
              onClick={handleClaimGuest}
              className="mt-2.5 inline-flex items-center gap-1.5 rounded-lg bg-[#00291B] px-3.5 py-1.5 text-xs font-bold text-white hover:bg-[#04421B]"
            >
              <UserPlus size={15} weight="bold" />
              {t.claimNowBtn}
            </button>
          </div>
        )}

        {/* Authenticated account drawer controls */}
        {authMode === "authenticated" && user ? (
          <div className="mt-4 space-y-3">
            <div className="rounded-xl border border-gray-200 bg-gray-50 p-3.5 text-xs">
              <p className="font-bold text-[#111827]">{user.full_name}</p>
              <p dir="ltr" className="text-gray-500">
                {user.email}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={handleExportData}
                className="inline-flex items-center gap-1.5 rounded-lg bg-[#00291B] px-3 py-2 text-xs font-semibold text-white hover:bg-[#04421B]"
              >
                <DownloadSimple size={16} />
                {t.exportDataBtn}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={handleLogout}
                className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-2 text-xs font-semibold text-[#111827] hover:bg-gray-100"
              >
                <SignOut size={16} />
                {t.logoutBtn}
              </button>
            </div>

            <div className="border-t border-gray-200 pt-3">
              {!confirmDelete ? (
                <button
                  type="button"
                  onClick={() => setConfirmDelete(true)}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-red-600 hover:underline"
                >
                  <Trash size={14} />
                  {t.deleteAccountBtn}
                </button>
              ) : (
                <div className="flex flex-wrap items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-2.5 text-xs">
                  <span className="text-red-800">{t.deleteConfirmText}</span>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={handleDeleteAccount}
                    className="rounded bg-red-600 px-2.5 py-1 font-bold text-white hover:bg-red-700"
                  >
                    Confirm
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(false)}
                    className="rounded border border-gray-300 px-2.5 py-1 text-gray-700 hover:bg-gray-100"
                  >
                    Cancel
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
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#00291B] px-4 py-2.5 text-sm font-bold text-white shadow-md hover:bg-[#04421B] transition"
              >
                <RocketLaunch size={18} weight="bold" className="text-[#84E875]" />
                {t.launchDemoBtn}
              </button>
            )}

            {authMode === "guest" && (
              <div className="flex items-center justify-between rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-xs">
                <span className="text-gray-700">Active Guest Token</span>
                <button
                  type="button"
                  disabled={busy}
                  onClick={handleResetGuest}
                  className="font-semibold text-red-600 hover:underline"
                >
                  {t.endGuestBtn}
                </button>
              </div>
            )}

            <div className="flex gap-2 border-b border-gray-200 pb-2">
              <button
                type="button"
                onClick={() => setTab("register")}
                className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                  tab === "register"
                    ? "bg-[#00291B] text-white"
                    : "text-gray-500 hover:text-gray-900"
                }`}
              >
                {t.registerTab}
              </button>
              <button
                type="button"
                onClick={() => setTab("login")}
                className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                  tab === "login"
                    ? "bg-[#00291B] text-white"
                    : "text-gray-500 hover:text-gray-900"
                }`}
              >
                {t.signInTab}
              </button>
            </div>

            <form onSubmit={handleSubmitAuth} className="space-y-3">
              {tab === "register" && (
                <div>
                  <label className="mb-1 block text-xs font-semibold text-gray-700">
                    {t.fullName}
                  </label>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Karim Benali"
                    className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
                  />
                </div>
              )}
              <div>
                <label className="mb-1 block text-xs font-semibold text-gray-700">
                  {t.email}
                </label>
                <input
                  type="email"
                  required
                  dir="ltr"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="farmer@guelma.dz"
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-gray-700">
                  {t.password}
                </label>
                <input
                  type="password"
                  required
                  minLength={8}
                  dir="ltr"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-[#111827] focus:border-[#00291B] focus:outline-none focus:ring-1 focus:ring-[#00291B]"
                />
              </div>
              <button
                type="submit"
                disabled={busy}
                className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[#00291B] px-4 py-2.5 text-sm font-bold text-white hover:bg-[#04421B] shadow-sm transition"
              >
                <SignIn size={18} />
                {tab === "register" ? t.submitRegister : t.submitLogin}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
