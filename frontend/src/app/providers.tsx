"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ResolvedTheme, ThemePreference, useAppStore } from "@/store/useAppStore";
import { CommandCenterShell } from "@/components/guelma/CommandCenterShell";

const ResolvedThemeContext = createContext<ResolvedTheme>("light");

export function useResolvedTheme(): ResolvedTheme {
  return useContext(ResolvedThemeContext);
}

function getSystemTheme(): ResolvedTheme {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return "light";
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyDocumentTheme(preference: ThemePreference): ResolvedTheme {
  const nextResolved: ResolvedTheme =
    preference === "system" ? getSystemTheme() : preference;
  if (typeof document !== "undefined") {
    const root = document.documentElement;
    root.dataset.theme = nextResolved;
    root.classList.toggle("dark", nextResolved === "dark");
    root.style.colorScheme = nextResolved;
  }
  return nextResolved;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  const lang = useAppStore((s) => s.lang);
  const theme = useAppStore((s) => s.theme);
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>("light");

  useEffect(() => {
    const updateTheme = () => {
      setResolvedTheme(applyDocumentTheme(theme));
    };

    updateTheme();

    if (
      theme !== "system" ||
      typeof window === "undefined" ||
      typeof window.matchMedia !== "function"
    ) {
      return;
    }

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    mediaQuery.addEventListener("change", updateTheme);
    return () => {
      mediaQuery.removeEventListener("change", updateTheme);
    };
  }, [theme]);

  const isWorkspaceRoute = pathname === "/" || pathname === "/dashboard";

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);

  return (
    <ResolvedThemeContext.Provider value={resolvedTheme}>
      <QueryClientProvider client={queryClient}>
        {isWorkspaceRoute ? children : <CommandCenterShell>{children}</CommandCenterShell>}
      </QueryClientProvider>
    </ResolvedThemeContext.Provider>
  );
}
