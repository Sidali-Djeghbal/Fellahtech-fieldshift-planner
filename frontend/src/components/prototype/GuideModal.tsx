"use client";

import React from "react";
import { CLIMATES, WEIGHTS } from "@/lib/prototype/data";
import { pLoc, type LocaleDict } from "@/lib/prototype/i18n";
import type { Preset, ProtoState } from "@/lib/prototype/types";

interface GuideModalProps {
  open: boolean;
  loc: LocaleDict;
  rawPreset: Preset;
  liveElev: number;
  state: ProtoState;
  onClose: () => void;
}

export function GuideModal({
  open,
  loc,
  rawPreset,
  liveElev,
  state,
  onClose,
}: GuideModalProps) {
  const p = pLoc(rawPreset, loc);
  const clim = CLIMATES[rawPreset.climate];
  const mathText = loc.mathSummaryFmt(
    WEIGHTS[state.priority],
    state,
    p.short,
    clim,
    liveElev
  );

  return (
    <div
      className={`guide-modal${open ? " open" : ""}`}
      id="guide-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="guide-h2"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="guide-card lg-surface">
        <div className="guide-head">
          <div className="guide-title-wrap">
            <h2 id="guide-h2">{loc.guideTitle}</h2>
            <p>{loc.guideSub}</p>
          </div>
          <button
            className="icon-pill tap"
            id="guide-close"
            type="button"
            aria-label="Close guide"
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        <div className="guide-body" id="guide-body">
          <div className="guide-sec">
            <h3>{loc.guideGlossaryH}</h3>
            <div className="glossary-grid" id="guide-glossary">
              {loc.glossaryItems.map((it) => (
                <div className="gloss-item" key={it.term}>
                  <b>{it.term}</b>
                  <span>{it.def}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="guide-sec">
            <h3>{loc.guideFusionH}</h3>
            <div className="fusion-wrap">
              <table className="fusion-table" id="guide-fusion-table">
                <thead>
                  <tr>
                    {loc.fusionCols.map((c) => (
                      <th key={c}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {loc.fusionRows.map((row, rIdx) => (
                    <tr key={rIdx}>
                      {row.map((cell, cIdx) => (
                        <td key={cIdx}>{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="guide-sec">
            <h3>{loc.guideMathH}</h3>
            <div className="math-box" id="guide-live-math">
              {mathText}
            </div>
          </div>

          <div className="guide-warn" id="guide-val-note">
            {loc.guideValidationNote}
          </div>
        </div>
      </div>
    </div>
  );
}

