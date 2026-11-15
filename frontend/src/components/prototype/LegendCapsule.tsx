"use client";

import React from "react";
import type { LocaleDict } from "@/lib/prototype/i18n";
import type { LegendDef } from "@/lib/prototype/types";

interface LegendCapsuleProps {
  visible: boolean;
  legend: LegendDef | null;
  loc?: LocaleDict;
}

export function LegendCapsule({ visible, legend, loc }: LegendCapsuleProps) {
  return (
    <aside
      className={`legend-pill lg-capsule${visible && legend ? " on" : ""}`}
      id="legend"
      aria-label={loc?.ui.ariaLegendScale ?? "Active layer scale"}
    >
      <div className="legend-meta">
        <span className="legend-title" id="legend-title">
          {legend?.title ?? loc?.ui.legendFallbackTitle ?? "Canopy greenness"}
        </span>
        <span className="legend-src" id="legend-src">
          {legend?.src ?? "MODIS"}
        </span>
      </div>
      <div className="legend-scale" dir="ltr">
        <span className="legend-lo" id="legend-lo">
          {legend?.lo ?? loc?.ui.legendFallbackLo ?? "bare"}
        </span>
        <div
          className="legend-bar"
          id="legend-bar"
          style={legend ? { background: legend.bar } : undefined}
        />
        <span className="legend-hi" id="legend-hi">
          {legend?.hi ?? loc?.ui.legendFallbackHi ?? "dense"}
        </span>
      </div>
    </aside>
  );
}

