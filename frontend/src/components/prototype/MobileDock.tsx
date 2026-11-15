"use client";

import React from "react";
import type { LocaleDict } from "@/lib/prototype/i18n";
import type { MobilePane } from "@/lib/prototype/types";

interface MobileDockProps {
  activePane: MobilePane;
  loc: LocaleDict;
  onSelectPane: (pane: MobilePane) => void;
}

export function MobileDock({
  activePane,
  loc,
  onSelectPane,
}: MobileDockProps) {
  const buttons: { pane: MobilePane; label: string }[] = [
    { pane: "map", label: loc.mobMap },
    { pane: "lab", label: loc.mobLab },
    { pane: "field", label: loc.mobField },
    { pane: "compare", label: loc.mobCompare },
    { pane: "audit", label: loc.mobAudit },
  ];

  return (
    <nav className="mobile-dock lg-capsule" aria-label={loc.ui.ariaMobileViews}>
      {buttons.map((b) => (
        <button
          key={b.pane}
          className="mob-btn tap"
          type="button"
          data-mob={b.pane}
          aria-pressed={activePane === b.pane}
          onClick={() => onSelectPane(b.pane)}
        >
          {b.label}
        </button>
      ))}
    </nav>
  );
}

