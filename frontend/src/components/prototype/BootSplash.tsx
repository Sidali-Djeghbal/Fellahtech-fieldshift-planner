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
          <img
            src="/assets/logo.svg"
            alt="FELLAH TECH"
            width={44}
            height={44}
          />
        </div>
        <div className="boot-mark">
          FELLAH TECH<em>.</em>
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

