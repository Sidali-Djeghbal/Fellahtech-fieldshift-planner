"use client";

import React from "react";
import type { LocaleDict } from "@/lib/prototype/i18n";

interface BootSplashProps {
  visible: boolean;
  fadingOut: boolean;
  note: string;
  loc: LocaleDict;
}

export function BootSplash({
  visible,
  fadingOut,
  note,
  loc,
}: BootSplashProps) {
  if (!visible) return null;

  return (
    <div className={`boot${fadingOut ? " gone" : ""}`} id="boot">
      <div className="boot-card">
        <div className="boot-emblem" aria-hidden="true">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.9"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 21c-4.5-2.6-7-6.8-7-11.2C7.8 9.8 10.6 11.4 12 14c1.4-2.6 4.2-4.2 7-4.2 0 4.4-2.5 8.6-7 11.2z" />
            <path d="M12 14V3" />
          </svg>
        </div>
        <div className="boot-mark">
          FieldShift<em>.</em>
        </div>
        <div className="boot-sub">{loc.bootSub}</div>
        <div className="boot-track" dir="ltr" aria-hidden="true">
          <span />
        </div>
        <span className="boot-note" id="boot-note">
          {note}
        </span>
      </div>
    </div>
  );
}

