"use client";

import React from "react";

interface SkyDiveOverlayProps {
  done: boolean;
  stage: number;
  flashKind: "none" | "pulse" | "lock";
  altLabel: string;
}

export function SkyDiveOverlay({
  done,
  stage,
  flashKind,
  altLabel,
}: SkyDiveOverlayProps) {
  const fxClass = `sky-fx${done ? " done" : ` step-${stage}`}`;
  const flashClass = `sky-flash${flashKind === "none" ? "" : ` ${flashKind}`}`;

  return (
    <div className={fxClass} id="sky-fx" aria-hidden="true">
      <div className="sky-clouds" />
      <div className={flashClass} id="sky-flash" />
      <div className="sky-reticle">
        <i className="c1" />
        <i className="c2" />
        <i className="c3" />
        <i className="c4" />
        <span className="sky-alt" id="sky-alt">
          {altLabel}
        </span>
      </div>
    </div>
  );
}

