"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Globe,
  Pulse,
  RocketLaunch,
  UserCircle,
  MapPin,
} from "@phosphor-icons/react";
import { isFixtureMode } from "@/lib/api/client";
import {
  getDemoSession,
  getHealth,
  listFarmAnalyses,
  listFarms,
  listFields,
  startGuestSession,
} from "@/lib/api/endpoints";
import { UI_DICT } from "@/lib/i18n";
import type { Language } from "@/lib/schemas";
import { useAppStore } from "@/store/useAppStore";
import { AuthModal } from "@/components/auth/AuthModal";
import { NavigationSidebar } from "@/components/brand/NavigationSidebar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const {
    lang,
    setLang,
    plainMode,
    togglePlainMode,
    authMode,
    guestToken,
    user,
    activeFarmId,
    activeFieldId,
    setGuestSession,
    setActiveFarmId,
    setActiveFieldId,
    setActiveAnalysisId,
    clearSession,
  } = useAppStore();

  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [launchingGuest, setLaunchingGuest] = useState(false);

  const t = UI_DICT[lang];
  const fixture = isFixtureMode();

  const healthQuery = useQuery({
    queryKey: ["health", "dependencies"],
    queryFn: () => getHealth("dependencies"),
    refetchInterval: 60_000,
    retry: 1,
  });

  const guestSessionQuery = useQuery({
    queryKey: ["demo", "session", guestToken],
    queryFn: () => getDemoSession(),
    enabled: authMode === "guest" && Boolean(guestToken),
    retry: 1,
  });

  async function handleQuickLaunchDemo() {
    setLaunchingGuest(true);
    try {
      const res = await startGuestSession(1);
      setGuestSession({
        guestToken: res.guest_token,
        expiresAt: res.expires_at,
      });
      const farms = await listFarms();
      if (farms.items.length > 0) {
        const fid = farms.items[0].farm_id;
        setActiveFarmId(fid);
        const fields = await listFields(fid);
        if (fields.items.length > 0) setActiveFieldId(fields.items[0].field_id);
        const runs = await listFarmAnalyses(fid);
        const ok = runs.items.find((r) => r.analysis_id);
        if (ok?.analysis_id) setActiveAnalysisId(ok.analysis_id);
      }
      await queryClient.invalidateQueries();
    } finally {
      setLaunchingGuest(false);
    }
  }

  const languages: { code: Language; label: string }[] = [
    { code: "en", label: "EN" },
    { code: "fr", label: "FR" },
    { code: "ar", label: "عربي" },
  ];

  const usedQuarters = guestSessionQuery.data?.usage.analysis_quarters ?? 0;
  const maxQuarters = guestSessionQuery.data?.limits.max_analysis_quarters ?? 40;
  const quotaPct = Math.min(100, Math.round((usedQuarters / maxQuarters) * 100));

  return (
    <div className="min-h-screen bg-[#F8FAF8] text-[#111827]">
      {/* Fixed Left Navigation Rail (60px) */}
      <NavigationSidebar
        onOpenAuth={() => setAuthModalOpen(true)}
        onLogout={() => {
          if (authMode !== "none") {
            clearSession();
          } else {
            setAuthModalOpen(true);
          }
        }}
      />

      {/* Main Workspace Offset by Sidebar Rail (60px) */}
      <div className="pl-[60px] flex min-h-screen flex-col">
        {/* Subtle Workspace Header Strip */}
        <header className="no-print sticky top-0 z-30 border-b border-[#E5E7EB] bg-white/95 backdrop-blur-md">
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2">
            {/* Left: Active Field / Farm Breadcrumb */}
            <div className="flex items-center gap-3">
              <Link href="/" className="flex items-center gap-2">
                <span className="font-heading text-sm font-extrabold tracking-wide text-[#00291B]">
                  {t.brandTitle}
                </span>
                {fixture && (
                  <span
                    data-testid="fixture-mode-pill"
                    className="rounded-full bg-[#DCFCE7] px-2 py-0.5 text-[10px] font-bold text-[#15803D]"
                  >
                    {t.chrome.fixtureMode}
                  </span>
                )}
              </Link>

              <div className="hidden h-4 w-px bg-gray-200 sm:block" />

              <div className="hidden items-center gap-1.5 text-xs text-[#6B7280] sm:flex">
                <MapPin size={13} className="text-[#137135]" />
                <span>{t.chrome.activeParcel}:</span>
                <span dir="ltr" className="font-semibold text-[#111827]">
                  {activeFarmId ? `${activeFarmId} · ${activeFieldId ?? "—"}` : t.chrome.noParcel}
                </span>
              </div>
            </div>

            {/* Right: Status, Controls, Language, Auth */}
            <div className="flex flex-wrap items-center gap-2">
              {/* Health Indicator */}
              <div
                title={
                  healthQuery.data
                    ? `Dataset: ${healthQuery.data.dataset.active_version} | Breaker: ${healthQuery.data.ml_service.circuit_breaker}`
                    : "Checking dependencies"
                }
                className="hidden items-center gap-1.5 rounded-lg border border-[#E5E7EB] bg-gray-50 px-2.5 py-1 text-[11px] xl:flex"
              >
                <Pulse
                  size={14}
                  weight="bold"
                  className={
                    healthQuery.data?.status === "ok"
                      ? "text-[#15803D]"
                      : "text-[#DC2626]"
                  }
                />
                <span className="text-[#374151]">
                  {healthQuery.data?.status === "ok"
                    ? healthQuery.data.dataset.active_version ?? t.chrome.systemOk
                    : t.chrome.systemDegraded}
                </span>
              </div>

              {/* Plain Farmer Mode (Aa) */}
              <button
                type="button"
                onClick={togglePlainMode}
                title={t.chrome.plainModeTooltip}
                data-testid="plain-mode-toggle"
                className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition ${
                  plainMode
                    ? "bg-[#84E875] text-[#00291B] font-bold"
                    : "border border-[#E5E7EB] bg-white text-[#374151] hover:bg-gray-50"
                }`}
              >
                {plainMode ? t.chrome.plainModeOn : t.chrome.plainModeOff}
              </button>

              {/* Language Switcher */}
              <div
                role="group"
                aria-label="Language selector"
                className="flex items-center overflow-hidden rounded-lg border border-[#E5E7EB] bg-white"
              >
                <Globe size={13} className="ms-2 hidden text-[#6B7280] sm:block" />
                {languages.map((item) => (
                  <button
                    key={item.code}
                    type="button"
                    data-testid={`lang-${item.code}`}
                    onClick={() => setLang(item.code)}
                    className={`px-2 py-1 text-xs font-semibold transition ${
                      lang === item.code
                        ? "bg-[#00291B] text-white"
                        : "text-[#6B7280] hover:text-[#111827]"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>

              {/* Quick Launch Demo if not authenticated */}
              {authMode === "none" && (
                <button
                  type="button"
                  disabled={launchingGuest}
                  onClick={handleQuickLaunchDemo}
                  data-testid="quick-launch-demo"
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[#00291B] px-3 py-1 text-xs font-semibold text-white shadow-sm hover:bg-[#04421B] transition"
                >
                  <RocketLaunch size={14} weight="bold" className="text-[#84E875]" />
                  <span>{launchingGuest ? "Starting..." : t.chrome.launchDemo}</span>
                </button>
              )}

              {/* Auth / Session Trigger */}
              <button
                type="button"
                onClick={() => setAuthModalOpen(true)}
                data-testid="auth-modal-trigger"
                className="inline-flex items-center gap-1.5 rounded-lg border border-[#E5E7EB] bg-white px-2.5 py-1 text-xs font-semibold text-[#111827] hover:bg-gray-50 shadow-sm"
              >
                <UserCircle size={15} weight="bold" className="text-[#137135]" />
                <span className="max-w-[120px] truncate">
                  {authMode === "authenticated" && user
                    ? user.full_name
                    : authMode === "guest"
                      ? t.chrome.guestWorkspace
                      : t.chrome.signIn}
                </span>
              </button>
            </div>
          </div>

          {/* Guest Quota Strip */}
          {authMode === "guest" && guestSessionQuery.data && (
            <div className="border-t border-[#E5E7EB] bg-emerald-50/60 px-4 py-1">
              <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
                <div className="flex items-center gap-3">
                  <span className="font-semibold text-[#00291B]">{t.chrome.quartersLabel}:</span>
                  <span className="tabular-nums font-bold text-[#137135]">
                    {usedQuarters} / {maxQuarters} qtrs
                  </span>
                  <div className="hidden h-1.5 w-28 overflow-hidden rounded-full bg-gray-200 sm:block">
                    <div
                      className="h-full bg-[#137135] transition-all"
                      style={{ width: `${quotaPct}%` }}
                    />
                  </div>
                  <span className="hidden text-[#6B7280] md:inline">{t.chrome.quartersRule}</span>
                </div>
                <button
                  type="button"
                  onClick={() => setAuthModalOpen(true)}
                  className="font-bold text-[#137135] hover:underline"
                >
                  {t.chrome.claimAccount}
                </button>
              </div>
            </div>
          )}
        </header>

        {/* Content Area */}
        <main className="flex-1 w-full">{children}</main>
      </div>

      <AuthModal open={authModalOpen} onClose={() => setAuthModalOpen(false)} />
    </div>
  );
}
