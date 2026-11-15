"use client";

import Link from "next/link";
import { UI_DICT } from "@/lib/i18n";
import { useAppStore } from "@/store/useAppStore";

export function NotFoundView() {
  const lang = useAppStore((s) => s.lang);
  const c = UI_DICT[lang].common;
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-6 text-center">
      <h2 className="text-2xl font-bold text-[#111827] dark:text-[#F1F5F2]">{c.notFoundTitle}</h2>
      <p className="mt-2 text-sm text-[#6B7280] dark:text-[#9CA89E]">{c.notFoundDesc}</p>
      <Link
        href="/"
        className="mt-4 rounded-lg bg-[#00291B] px-4 py-2 text-xs font-semibold text-white transition hover:bg-[#003825]"
      >
        {c.notFoundBackBtn}
      </Link>
    </div>
  );
}

