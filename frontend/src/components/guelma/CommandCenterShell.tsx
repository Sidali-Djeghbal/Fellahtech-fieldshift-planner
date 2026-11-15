"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Brain,
  ChartBar,
  Compass,
  FileText,
  GearSix,
  MapPin,
  MapTrifold,
  Moon,
  Plant,
  Plus,
  Pulse,
  RocketLaunch,
  SquaresFour,
  Sun,
  Translate,
} from "@phosphor-icons/react";
import { useResolvedTheme } from "@/app/providers";
import { AuthModal } from "@/components/auth/AuthModal";
import { FieldShiftLogo } from "@/components/brand/FieldShiftLogo";
import { WorkstationSettingsDrawer } from "@/components/guelma/WorkstationSettingsDrawer";
import { WorkspaceShellContext } from "@/components/guelma/WorkspaceShellContext";
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
import { GUELMA_WORKSPACE_I18N } from "@/lib/i18n/guelmaWorkspace";
import { INTELLIGENCE_I18N } from "@/lib/i18n/intelligence";
import type { Language } from "@/lib/schemas";
import {
  type AuthMode,
  type ResolvedTheme,
  type ThemePreference,
  useAppStore,
} from "@/store/useAppStore";

export type CommandCenterView = "overview" | "farms" | "intelligence";

interface CommandCenterShellProps {
  children: React.ReactNode;
  /** True when rendered for "/" or "/dashboard" workspace views. */
  isWorkspaceHome?: boolean;
  activeView?: CommandCenterView;
  onSelectView?: (view: CommandCenterView) => void;
  fieldsCount?: number;
  analysesCount?: number;
  hasFarms?: boolean;
  onStartAddFarm?: () => void;
  onResetWorkspace?: () => void;
  onOpenAuthModal?: () => void;
  onChangeLang?: (lang: Language) => void;
  onChangeTheme?: (theme: ThemePreference) => void;
  onTogglePlainMode?: () => void;
  langOverride?: Language;
  themeOverride?: ThemePreference;
  resolvedThemeOverride?: ResolvedTheme;
  plainModeOverride?: boolean;
  authModeOverride?: AuthMode;
  userEmailOverride?: string | null;
  testId?: string;
}

const STUDIO_ROUTES = ["/select-field", "/farm-profile", "/comparison", "/evidence"] as const;

export function CommandCenterShell({
  children,
  isWorkspaceHome = false,
  activeView = "overview",
  onSelectView,
  fieldsCount = 0,
  analysesCount = 0,
  hasFarms = false,
  onStartAddFarm,
  onResetWorkspace,
  onOpenAuthModal,
  onChangeLang,
  onChangeTheme,
  onTogglePlainMode,
  langOverride,
  themeOverride,
  resolvedThemeOverride,
  plainModeOverride,
  authModeOverride,
  userEmailOverride,
  testId,
}: CommandCenterShellProps) {
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [internalAuthOpen, setInternalAuthOpen] = useState(false);
  const [launchingGuest, setLaunchingGuest] = useState(false);

  const storeTheme = useAppStore((s) => s.theme);
  const storeResolvedTheme = useResolvedTheme();
  const storeLang = useAppStore((s) => s.lang);
  const storePlainMode = useAppStore((s) => s.plainMode);
  const storeAuthMode = useAppStore((s) => s.authMode);
  const storeUser = useAppStore((s) => s.user);
  const guestToken = useAppStore((s) => s.guestToken);
  const activeFarmId = useAppStore((s) => s.activeFarmId);
  const activeFieldId = useAppStore((s) => s.activeFieldId);
  const activeAnalysisId = useAppStore((s) => s.activeAnalysisId);
  const setStoreLang = useAppStore((s) => s.setLang);
  const setStoreTheme = useAppStore((s) => s.setTheme);
  const toggleStorePlainMode = useAppStore((s) => s.togglePlainMode);
  const setGuestSession = useAppStore((s) => s.setGuestSession);
  const setActiveFarmId = useAppStore((s) => s.setActiveFarmId);
  const setActiveFieldId = useAppStore((s) => s.setActiveFieldId);
  const setActiveAnalysisId = useAppStore((s) => s.setActiveAnalysisId);

  const lang = langOverride ?? storeLang;
  const theme = themeOverride ?? storeTheme;
  const resolvedTheme = resolvedThemeOverride ?? storeResolvedTheme;
  const plainMode = plainModeOverride ?? storePlainMode;
  const authMode = authModeOverride ?? storeAuthMode;
  const userEmail =
    userEmailOverride !== undefined ? userEmailOverride : (storeUser?.email ?? null);

  const handleLangChange = onChangeLang ?? setStoreLang;
  const handleThemeChange = onChangeTheme ?? setStoreTheme;
  const handlePlainModeToggle = onTogglePlainMode ?? toggleStorePlainMode;
  const handleOpenAuth = onOpenAuthModal ?? (() => setInternalAuthOpen(true));

  const dict = GUELMA_WORKSPACE_I18N[lang];
  const uiDict = UI_DICT[lang];
  const intel = INTELLIGENCE_I18N[lang];
  const ws = intel.workstation;
  const mobileAddShortLabel = ws.analyticsZone.emptyPriority;

  const isStudioRoute = STUDIO_ROUTES.some(
    (route) => pathname === route || pathname?.startsWith(`${route}/`)
  );
  const studioHref = activeAnalysisId
    ? `/comparison?analysisId=${encodeURIComponent(activeAnalysisId)}`
    : "/select-field";

  const fixture = isFixtureMode();

  const healthQuery = useQuery({
    queryKey: ["health", "dependencies"],
    queryFn: () => getHealth("dependencies"),
    refetchInterval: 60_000,
    retry: 1,
    enabled: !isWorkspaceHome,
  });

  const guestSessionQuery = useQuery({
    queryKey: ["demo", "session", guestToken],
    queryFn: () => getDemoSession(),
    enabled: !isWorkspaceHome && authMode === "guest" && Boolean(guestToken),
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

  const usedQuarters = guestSessionQuery.data?.usage.analysis_quarters ?? 0;
  const maxQuarters = guestSessionQuery.data?.limits.max_analysis_quarters ?? 40;
  const quotaPct = Math.min(100, Math.round((usedQuarters / maxQuarters) * 100));

  const viewTabs: Array<{
    id: CommandCenterView;
    label: string;
    badge?: number;
    href: string;
  }> = [
    { id: "overview", label: ws.nav.overview, href: "/" },
    {
      id: "farms",
      label: ws.nav.farmsFields,
      badge: fieldsCount > 0 ? fieldsCount : undefined,
      href: "/?view=farms",
    },
    {
      id: "intelligence",
      label: ws.nav.intelligence,
      badge: analysesCount > 0 ? analysesCount : undefined,
      href: "/?view=intelligence",
    },
  ];

  const studioSteps = [
    { href: "/select-field", label: uiDict.nav.selectField, Icon: MapTrifold },
    { href: "/farm-profile", label: uiDict.nav.farmProfile, Icon: Plant },
    { href: "/comparison", label: uiDict.nav.comparison, Icon: ChartBar },
    { href: "/evidence", label: uiDict.nav.evidence, Icon: FileText },
  ] as const;

  const isActiveView = (view: CommandCenterView) => isWorkspaceHome && activeView === view;

  return (
    <WorkspaceShellContext.Provider value={{ openAuthModal: handleOpenAuth }}>
      <div
        className="fs-workstation-canvas min-h-screen text-[#111813] dark:text-[#F5F7F5]"
        data-testid={testId}
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
                <Link href="/" className="flex shrink-0 items-center gap-2 sm:gap-2.5">
                  <FieldShiftLogo size={32} />
                  <div className="flex items-center gap-2.5">
                    <span className="whitespace-nowrap font-heading text-xs font-bold tracking-tight text-[#111813] dark:text-[#F5F7F5] sm:text-sm">
                      {uiDict.brandTitle}
                    </span>
                    <span
                      className="hidden h-3.5 w-px bg-[#111813]/15 dark:bg-white/15 xl:inline-block"
                      aria-hidden="true"
                    />
                    <span className="hidden whitespace-nowrap font-mono text-[11px] font-medium text-[#4A5A4E] dark:text-[#9CA89E] xl:inline">
                      {ws.geoContextTag}
                    </span>
                  </div>
                </Link>

                {/* Trailing Utility Controls */}
                <div className="flex shrink-0 items-center gap-1 sm:gap-2">
                  <div
                    className="fs-liquid-well inline-flex shrink-0 items-center rounded-full p-1 text-[10px] font-semibold sm:text-[11px]"
                    role="radiogroup"
                    aria-label={uiDict.common.ariaLanguageSwitcher}
                    onKeyDown={(e) => {
                      const order: readonly Language[] = ["en", "fr", "ar"];
                      const idx = order.indexOf(lang);
                      if (e.key === "ArrowRight" || e.key === "ArrowDown") {
                        e.preventDefault();
                        handleLangChange(order[(idx + 1) % order.length]);
                      } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
                        e.preventDefault();
                        handleLangChange(order[(idx + order.length - 1) % order.length]);
                      }
                    }}
                  >
                    {(["en", "fr", "ar"] as const).map((l) => (
                      <button
                        key={l}
                        type="button"
                        role="radio"
                        aria-checked={lang === l}
                        onClick={() => handleLangChange(l)}
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
                    onClick={() => setSettingsOpen(true)}
                    data-testid="header-settings-mobile-btn"
                    aria-label={ws.nav.settings}
                    className="fs-liquid-pill inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[#4A5A4E] active:not-disabled:scale-[0.96] dark:text-[#9CA89E] md:hidden"
                  >
                    <GearSix size={15} aria-hidden="true" />
                  </button>

                  {isWorkspaceHome && onStartAddFarm ? (
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
                  ) : (
                    <Link
                      href="/?action=draw"
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
                    </Link>
                  )}
                </div>
              </div>

              {/* Mobile View Switcher Pill Strip (<md) */}
              <nav
                aria-label={uiDict.common.ariaMobileNav}
                className="fs-liquid-well no-scrollbar mt-2.5 flex items-center gap-1.5 overflow-x-auto rounded-full p-1 md:hidden"
              >
                {viewTabs.map((tab) => {
                  const active = isActiveView(tab.id);
                  const pillClass = `inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-full px-3 text-[11px] font-medium transition-[transform,background-color,box-shadow,color] duration-150 ease-out active:scale-[0.96] ${
                    active
                      ? "bg-[#0B3D2E] font-semibold text-white shadow-xs dark:bg-[#FFFFFF] dark:text-[#111713]"
                      : "text-[#4A5A4E] dark:text-[#9CA89E]"
                  }`;
                  const inner = (
                    <>
                      <span>{tab.label}</span>
                      {tab.badge !== undefined ? (
                        <span
                          className={`rounded-full px-1.5 font-mono text-[10px] tabular-nums ${
                            active
                              ? "bg-white/20 text-white dark:bg-[#111713]/10 dark:text-[#111713]"
                              : "bg-[#111813]/10 text-[#3E4C42] dark:bg-white/10 dark:text-[#E4EBE5]"
                          }`}
                        >
                          {tab.badge}
                        </span>
                      ) : null}
                    </>
                  );

                  if (isWorkspaceHome && onSelectView) {
                    return (
                      <button
                        key={tab.id}
                        type="button"
                        onClick={() => onSelectView(tab.id)}
                        className={pillClass}
                      >
                        {inner}
                      </button>
                    );
                  }

                  return (
                    <Link key={tab.id} href={tab.href} className={pillClass}>
                      {inner}
                    </Link>
                  );
                })}
                <Link
                  href={studioHref}
                  className={`inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-full px-3 text-[11px] font-medium transition-[transform,background-color,box-shadow,color] duration-150 ease-out active:scale-[0.96] ${
                    isStudioRoute
                      ? "bg-[#0B3D2E] font-semibold text-white shadow-xs dark:bg-[#FFFFFF] dark:text-[#111713]"
                      : "text-[#4A5A4E] dark:text-[#9CA89E]"
                  }`}
                >
                  <span>{ws.nav.studio}</span>
                </Link>
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
              aria-label={uiDict.common.ariaToolRail}
              className="no-print fs-glass-rail no-scrollbar sticky top-20 hidden max-h-[calc(100vh-110px)] min-h-[540px] w-14 shrink-0 flex-col items-center justify-between self-start overflow-y-auto rounded-3xl px-2 py-3 md:flex"
            >
              <div className="flex flex-col items-center gap-2">
                {isWorkspaceHome && onSelectView ? (
                  <button
                    type="button"
                    onClick={() => onSelectView("overview")}
                    title={ws.nav.overview}
                    aria-label={ws.nav.overview}
                    className={`flex h-9 w-9 items-center justify-center rounded-xl transition-[transform,background-color,color] duration-150 ease-out active:scale-[0.96] ${
                      isActiveView("overview")
                        ? "bg-[#0B3D2E] text-white shadow-sm dark:bg-[#FFFFFF] dark:text-[#111713] dark:shadow-[0_4px_14px_rgba(0,0,0,0.35)]"
                        : "text-[#4A5A4E] hover:bg-[#111813]/[0.08] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:bg-white/[0.08] dark:hover:text-[#F5F7F5]"
                    }`}
                  >
                    <SquaresFour
                      size={18}
                      weight={isActiveView("overview") ? "fill" : "regular"}
                      aria-hidden="true"
                    />
                  </button>
                ) : (
                  <Link
                    href="/"
                    title={ws.nav.overview}
                    aria-label={ws.nav.overview}
                    className="flex h-9 w-9 items-center justify-center rounded-xl text-[#4A5A4E] transition-[transform,background-color,color] duration-150 ease-out hover:bg-[#111813]/[0.08] hover:text-[#111813] active:scale-[0.96] dark:text-[#9CA89E] dark:hover:bg-white/[0.08] dark:hover:text-[#F5F7F5]"
                  >
                    <SquaresFour size={18} weight="regular" aria-hidden="true" />
                  </Link>
                )}


                {isWorkspaceHome && onSelectView ? (
                  <button
                    type="button"
                    onClick={() => onSelectView("farms")}
                    title={ws.nav.farmsFields}
                    aria-label={ws.nav.farmsFields}
                    className={`flex h-9 w-9 items-center justify-center rounded-xl transition-[transform,background-color,color] duration-150 ease-out active:scale-[0.96] ${
                      isActiveView("farms")
                        ? "bg-[#0B3D2E] text-white shadow-sm dark:bg-[#FFFFFF] dark:text-[#111713] dark:shadow-[0_4px_14px_rgba(0,0,0,0.35)]"
                        : "text-[#4A5A4E] hover:bg-[#111813]/[0.08] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:bg-white/[0.08] dark:hover:text-[#F5F7F5]"
                    }`}
                  >
                    <Compass
                      size={18}
                      weight={isActiveView("farms") ? "fill" : "regular"}
                      aria-hidden="true"
                    />
                  </button>
                ) : (
                  <Link
                    href="/?view=farms"
                    title={ws.nav.farmsFields}
                    aria-label={ws.nav.farmsFields}
                    className="flex h-9 w-9 items-center justify-center rounded-xl text-[#4A5A4E] transition-[transform,background-color,color] duration-150 ease-out hover:bg-[#111813]/[0.08] hover:text-[#111813] active:scale-[0.96] dark:text-[#9CA89E] dark:hover:bg-white/[0.08] dark:hover:text-[#F5F7F5]"
                  >
                    <Compass size={18} weight="regular" aria-hidden="true" />
                  </Link>
                )}

                {isWorkspaceHome && onSelectView ? (
                  <button
                    type="button"
                    onClick={() => onSelectView("intelligence")}
                    title={ws.nav.intelligence}
                    aria-label={ws.nav.intelligence}
                    className={`flex h-9 w-9 items-center justify-center rounded-xl transition-[transform,background-color,color] duration-150 ease-out active:scale-[0.96] ${
                      isActiveView("intelligence")
                        ? "bg-[#0B3D2E] text-white shadow-sm dark:bg-[#FFFFFF] dark:text-[#111713] dark:shadow-[0_4px_14px_rgba(0,0,0,0.35)]"
                        : "text-[#4A5A4E] hover:bg-[#111813]/[0.08] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:bg-white/[0.08] dark:hover:text-[#F5F7F5]"
                    }`}
                  >
                    <Brain
                      size={18}
                      weight={isActiveView("intelligence") ? "duotone" : "regular"}
                      aria-hidden="true"
                    />
                  </button>
                ) : (
                  <Link
                    href="/?view=intelligence"
                    title={ws.nav.intelligence}
                    aria-label={ws.nav.intelligence}
                    className="flex h-9 w-9 items-center justify-center rounded-xl text-[#4A5A4E] transition-[transform,background-color,color] duration-150 ease-out hover:bg-[#111813]/[0.08] hover:text-[#111813] active:scale-[0.96] dark:text-[#9CA89E] dark:hover:bg-white/[0.08] dark:hover:text-[#F5F7F5]"
                  >
                    <Brain size={18} weight="regular" aria-hidden="true" />
                  </Link>
                )}

                {/* Moved Studio Route Links inside the Unified Rail */}
                <div className="my-1 h-px w-6 bg-[#111813]/12 dark:bg-white/12" aria-hidden="true" />

                {studioSteps.map(({ href, label, Icon }) => {
                  const active = pathname === href || pathname?.startsWith(`${href}/`);
                  return (
                    <Link
                      key={href}
                      href={href}
                      title={label}
                      aria-label={label}
                      aria-current={active ? "page" : undefined}
                      className={`flex h-9 w-9 items-center justify-center rounded-xl transition-[transform,background-color,color] duration-150 ease-out active:scale-[0.96] ${
                        active
                          ? "bg-[#0B3D2E] text-white shadow-sm dark:bg-[#FFFFFF] dark:text-[#111713] dark:shadow-[0_4px_14px_rgba(0,0,0,0.35)]"
                          : "text-[#4A5A4E] hover:bg-[#111813]/[0.08] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:bg-white/[0.08] dark:hover:text-[#F5F7F5]"
                      }`}
                    >
                      <Icon size={18} weight={active ? "fill" : "regular"} aria-hidden="true" />
                    </Link>
                  );
                })}
              </div>

              <div className="mt-3 flex flex-col items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleThemeChange(resolvedTheme === "dark" ? "light" : "dark")}
                  data-testid="rail-theme-btn"
                  title={
                    resolvedTheme === "dark" ? ws.settings.switchToLight : ws.settings.switchToDark
                  }
                  aria-label={
                    resolvedTheme === "dark" ? ws.settings.switchToLight : ws.settings.switchToDark
                  }
                  className="flex h-9 w-9 items-center justify-center rounded-xl text-[#4A5A4E] transition-[transform,background-color,color] duration-150 ease-out hover:bg-[#111813]/[0.08] hover:text-[#111813] active:scale-[0.96] dark:text-[#9CA89E] dark:hover:bg-white/[0.08] dark:hover:text-[#F5F7F5]"
                >
                  <Moon size={18} aria-hidden="true" className="inline dark:hidden" />
                  <Sun size={18} aria-hidden="true" className="hidden text-[#FCD34D] dark:inline" />
                </button>

                <button
                  type="button"
                  onClick={handlePlainModeToggle}
                  title={plainMode ? intel.section.plainModeOn : intel.section.plainModeOff}
                  aria-label={plainMode ? intel.section.plainModeOn : intel.section.plainModeOff}
                  className={`flex h-9 w-9 items-center justify-center rounded-xl transition-[transform,background-color,color] duration-150 ease-out active:scale-[0.96] ${
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
                  data-testid="rail-settings-btn"
                  title={ws.nav.settings}
                  aria-label={ws.nav.settings}
                  className="flex h-9 w-9 items-center justify-center rounded-xl text-[#4A5A4E] transition-[transform,background-color,color] duration-150 ease-out hover:bg-[#111813]/[0.08] hover:text-[#111813] active:scale-[0.96] dark:text-[#9CA89E] dark:hover:bg-white/[0.08] dark:hover:text-[#F5F7F5]"
                >
                  <GearSix size={18} aria-hidden="true" />
                </button>
              </div>
            </aside>

            {/* Main Spatial Viewport */}
            <main className="min-w-0 flex-1 max-w-[1440px] mx-auto">
              {!isWorkspaceHome && (
                <div className="no-print mb-5 space-y-2.5">
                  <div className="fs-liquid-panel flex flex-wrap items-center justify-between gap-3 rounded-3xl px-4 py-3">
                    {/* 4-Step Studio Route Switcher */}
                    <nav
                      aria-label={uiDict.common.ariaWorkflowNav}
                      className="fs-liquid-well no-scrollbar flex items-center gap-1 overflow-x-auto rounded-full p-1"
                    >
                      {studioSteps.map(({ href, label, Icon }, idx) => {
                        const active = pathname === href || pathname?.startsWith(`${href}/`);
                        return (
                          <Link
                            key={href}
                            href={href}
                            aria-current={active ? "page" : undefined}
                            className={`inline-flex min-h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-3 text-xs font-medium transition-[transform,background-color,box-shadow,color] duration-150 ease-out active:scale-[0.96] ${
                              active
                                ? "bg-[#0B3D2E] font-semibold text-white shadow-xs dark:bg-[#FFFFFF] dark:text-[#111713]"
                                : "text-[#4A5A4E] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:text-[#F5F7F5]"
                            }`}
                          >
                            <Icon size={14} weight={active ? "fill" : "regular"} aria-hidden="true" />
                            <span dir="ltr" className="font-mono text-[10px] opacity-75">
                              {idx + 1}.
                            </span>
                            <span>{label}</span>
                          </Link>
                        );
                      })}
                    </nav>

                    {/* Status, Active Parcel & Sandbox Launch Controls */}
                    <div className="flex flex-wrap items-center gap-2">
                      {fixture && (
                        <span
                          data-testid="fixture-mode-pill"
                          className="rounded-full bg-[#22C55E]/15 px-2.5 py-1 font-mono text-[10px] font-semibold text-[#15803D] ring-1 ring-[#15803D]/25 dark:bg-[#22C55E]/20 dark:text-[#86EFAC] dark:ring-[#4ADE80]/30"
                        >
                          {uiDict.chrome.fixtureMode}
                        </span>
                      )}

                      <div className="fs-liquid-well hidden items-center gap-1.5 rounded-full px-3 py-1 text-xs text-[#4A5A4E] dark:text-[#9CA89E] sm:inline-flex">
                        <MapPin
                          size={13}
                          className="text-[#15803D] dark:text-[#86EFAC]"
                          aria-hidden="true"
                        />
                        <span>{uiDict.chrome.activeParcel}:</span>
                        <span dir="ltr" className="font-mono font-semibold text-[#111813] dark:text-[#F5F7F5]">
                          {activeFarmId ? `${activeFarmId} · ${activeFieldId ?? "—"}` : uiDict.chrome.noParcel}
                        </span>
                      </div>

                      <div
                        title={
                          healthQuery.data
                            ? `${uiDict.common.datasetLabel}: ${healthQuery.data.dataset.active_version} | ${healthQuery.data.ml_service.circuit_breaker}`
                            : uiDict.common.checkingDeps
                        }
                        className="fs-liquid-well hidden items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] xl:inline-flex"
                      >
                        <Pulse
                          size={13}
                          weight="bold"
                          className={
                            healthQuery.data?.status === "ok"
                              ? "text-[#15803D] dark:text-[#22C55E]"
                              : "text-red-600 dark:text-red-400"
                          }
                          aria-hidden="true"
                        />
                        <span className="font-mono text-[#3E4C42] dark:text-[#D1DBD3]">
                          {healthQuery.data?.status === "ok"
                            ? healthQuery.data.dataset.active_version ?? uiDict.chrome.systemOk
                            : uiDict.chrome.systemDegraded}
                        </span>
                      </div>

                      {authMode === "none" && (
                        <button
                          type="button"
                          disabled={launchingGuest}
                          onClick={handleQuickLaunchDemo}
                          data-testid="quick-launch-demo"
                          className="fs-cta-primary inline-flex min-h-9 items-center gap-1.5 rounded-full px-3.5 text-xs font-semibold active:not-disabled:scale-[0.96] disabled:opacity-50"
                        >
                          <RocketLaunch
                            size={14}
                            weight="bold"
                            className="text-[#84E875] dark:text-[#15803D]"
                            aria-hidden="true"
                          />
                          <span>{launchingGuest ? uiDict.common.startingLabel : uiDict.chrome.launchDemo}</span>
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Guest Analysis Quota Strip */}
                  {authMode === "guest" && guestSessionQuery.data && (
                    <div className="fs-liquid-well flex flex-wrap items-center justify-between gap-2 rounded-2xl px-4 py-2 text-[11px]">
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="font-semibold text-[#111813] dark:text-[#F5F7F5]">
                          {uiDict.chrome.quartersLabel}:
                        </span>
                        <span
                          dir="ltr"
                          className="font-mono font-semibold tabular-nums text-[#15803D] dark:text-[#86EFAC]"
                        >
                          {usedQuarters} / {maxQuarters} {uiDict.common.quartersShort}
                        </span>
                        <div className="hidden h-1.5 w-28 overflow-hidden rounded-full bg-[#111813]/10 dark:bg-white/10 sm:block">
                          <div
                            className="h-full bg-[#15803D] transition-all dark:bg-[#22C55E]"
                            style={{ width: `${quotaPct}%` }}
                          />
                        </div>
                        <span className="hidden text-[#4A5A4E] dark:text-[#9CA89E] md:inline">
                          {uiDict.chrome.quartersRule}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={handleOpenAuth}
                        className="font-semibold text-[#15803D] hover:underline dark:text-[#86EFAC]"
                      >
                        {uiDict.chrome.claimAccount}
                      </button>
                    </div>
                  )}
                </div>
              )}

              {children}
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
          hasFarms={hasFarms}
          onClose={() => setSettingsOpen(false)}
          onChangeLang={handleLangChange}
          onChangeTheme={handleThemeChange}
          onTogglePlainMode={handlePlainModeToggle}
          onOpenAuth={handleOpenAuth}
          onResetWorkspace={
            onResetWorkspace ??
            (() => {
              void queryClient.invalidateQueries();
            })
          }
        />

        {!onOpenAuthModal && (
          <AuthModal
            open={internalAuthOpen}
            theme={resolvedTheme}
            onClose={() => {
              setInternalAuthOpen(false);
              void queryClient.invalidateQueries();
            }}
          />
        )}
      </div>
    </WorkspaceShellContext.Provider>
  );
}

