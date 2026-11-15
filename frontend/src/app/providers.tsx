"use client";

import React, { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAppStore } from "@/store/useAppStore";
import { AppShell } from "@/components/layout/AppShell";

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

  useEffect(() => {
    if (pathname === "/") return;
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang, pathname]);

  return (
    <QueryClientProvider client={queryClient}>
      {pathname === "/" ? children : <AppShell>{children}</AppShell>}
    </QueryClientProvider>
  );
}
