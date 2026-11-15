"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { Language, UserProfile } from "@/lib/schemas";

export type AuthMode = "none" | "guest" | "authenticated";

export interface AppState {
  lang: Language;
  plainMode: boolean;
  authMode: AuthMode;
  accessToken: string | null;
  refreshToken: string | null;
  guestToken: string | null;
  guestExpiresAt: string | null;
  user: UserProfile | null;
  activeFarmId: string | null;
  activeFieldId: string | null;
  activeAnalysisId: string | null;
  activeRequestId: string | null;
  bootSplashSeen: boolean;
  simulateDegradedReplay: boolean;

  setLang: (lang: Language) => void;
  togglePlainMode: () => void;
  setPlainMode: (enabled: boolean) => void;
  setGuestSession: (payload: { guestToken: string; expiresAt: string }) => void;
  setAuthenticatedSession: (payload: {
    accessToken: string;
    refreshToken: string;
    user?: UserProfile | null;
    keepGuestToken?: boolean;
  }) => void;
  setUser: (user: UserProfile | null) => void;
  clearGuestToken: () => void;
  clearSession: () => void;
  setActiveFarmId: (farmId: string | null) => void;
  setActiveFieldId: (fieldId: string | null) => void;
  setActiveAnalysisId: (analysisId: string | null) => void;
  setActiveRequestId: (requestId: string | null) => void;
  markBootSplashSeen: () => void;
  setSimulateDegradedReplay: (enabled: boolean) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      lang: "en",
      plainMode: false,
      authMode: "none",
      accessToken: null,
      refreshToken: null,
      guestToken: null,
      guestExpiresAt: null,
      user: null,
      activeFarmId: null,
      activeFieldId: null,
      activeAnalysisId: null,
      activeRequestId: null,
      bootSplashSeen: false,
      simulateDegradedReplay: false,

      setLang: (lang) => set({ lang }),
      togglePlainMode: () => set((s) => ({ plainMode: !s.plainMode })),
      setPlainMode: (plainMode) => set({ plainMode }),
      setGuestSession: ({ guestToken, expiresAt }) =>
        set({
          authMode: "guest",
          guestToken,
          guestExpiresAt: expiresAt,
          accessToken: null,
          refreshToken: null,
          user: null,
        }),
      setAuthenticatedSession: ({ accessToken, refreshToken, user, keepGuestToken = true }) =>
        set((s) => ({
          authMode: "authenticated",
          accessToken,
          refreshToken,
          user: user !== undefined ? user : s.user,
          guestToken: keepGuestToken ? s.guestToken : null,
          guestExpiresAt: keepGuestToken ? s.guestExpiresAt : null,
        })),
      setUser: (user) => set({ user }),
      clearGuestToken: () => set({ guestToken: null, guestExpiresAt: null }),
      clearSession: () =>
        set({
          authMode: "none",
          accessToken: null,
          refreshToken: null,
          guestToken: null,
          guestExpiresAt: null,
          user: null,
          activeFarmId: null,
          activeFieldId: null,
          activeAnalysisId: null,
          activeRequestId: null,
        }),
      setActiveFarmId: (activeFarmId) => set({ activeFarmId }),
      setActiveFieldId: (activeFieldId) => set({ activeFieldId }),
      setActiveAnalysisId: (activeAnalysisId) => set({ activeAnalysisId }),
      setActiveRequestId: (activeRequestId) => set({ activeRequestId }),
      markBootSplashSeen: () => set({ bootSplashSeen: true }),
      setSimulateDegradedReplay: (simulateDegradedReplay) => set({ simulateDegradedReplay }),
    }),
    {
      name: "fieldshift-planner-v32",
      storage: createJSONStorage(() =>
        typeof window !== "undefined"
          ? window.localStorage
          : {
              getItem: () => null,
              setItem: () => {},
              removeItem: () => {},
            }
      ),
      partialize: (state) => ({
        lang: state.lang,
        plainMode: state.plainMode,
        authMode: state.authMode,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        guestToken: state.guestToken,
        guestExpiresAt: state.guestExpiresAt,
        user: state.user,
        activeFarmId: state.activeFarmId,
        activeFieldId: state.activeFieldId,
        activeAnalysisId: state.activeAnalysisId,
        simulateDegradedReplay: state.simulateDegradedReplay,
      }),
    }
  )
);
