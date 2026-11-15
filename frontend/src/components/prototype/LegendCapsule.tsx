"use client";

import React from "react";
import type { LegendDef } from "@/lib/prototype/types";

interface LegendCapsuleProps {
  visible: boolean;
  legend: LegendDef | null;
}

export function LegendCapsule({ visible, legend }: LegendCapsuleProps) {
  return (
    <aside
      className={`legend-pill lg-capsule${visible && legend ? " on" : ""}`}
      id="legend"
      aria-label="Active layer scale"
    >
      <div className="legend-meta">
        <span className="legend-title" id="legend-title">
          {legend?.title ?? "Canopy greenness"}
        </span>
        <span className="legend-src" id="legend-src">
          {legend?.src ?? "MODIS"}
        </span>
      </div>
      <div className="legend-scale" dir="ltr">
        <span className="legend-lo" id="legend-lo">
          {legend?.lo ?? "bare"}
        </span>
        <div
          className="legend-bar"
          id="legend-bar"
          style={legend ? { background: legend.bar } : undefined}
        />
        <span className="legend-hi" id="legend-hi">
          {legend?.hi ?? "dense"}
        </span>
      </div>
    </aside>
  );
}

