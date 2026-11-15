"use client";

import React from "react";
import { UI_DICT } from "@/lib/i18n";
import { pLoc, type LocaleDict } from "@/lib/prototype/i18n";
import type { Lang, LayerKey, Preset, PresetId } from "@/lib/prototype/types";

interface TopToolbarProps {
  presets: Preset[];
  activePreset: Preset;
  lang: Lang;
  loc: LocaleDict;
  toggles: Record<LayerKey, boolean>;
  isRegionalView: boolean;
  tiltOn: boolean;
  zenMode: boolean;
  plainMode: boolean;
  backLabel?: string;
  editBordersLabel?: string;
  onBackToDashboard?: () => void;
  onEditBorders?: () => void;
  onSelectPreset: (id: PresetId) => void;
  onSelectLang: (lang: Lang) => void;
  onToggleLayer: (key: LayerKey) => void;
  onToggleFocus: () => void;
  onToggleTilt: () => void;
  onToggleZen: () => void;
  onTogglePlain: () => void;
  onOpenGuide: () => void;
}

const LAYER_ORDER: LayerKey[] = ["truecolor", "ndvi", "sm", "rain", "lst"];

export function TopToolbar({
  presets,
  activePreset,
  lang,
  loc,
  toggles,
  isRegionalView,
  tiltOn,
  zenMode,
  plainMode,
  backLabel,
  editBordersLabel,
  onBackToDashboard,
  onEditBorders,
  onSelectPreset,
  onSelectLang,
  onToggleLayer,
  onToggleFocus,
  onToggleTilt,
  onToggleZen,
  onTogglePlain,
  onOpenGuide,
}: TopToolbarProps) {
  const layerLabel = (key: LayerKey): string => {
    switch (key) {
      case "truecolor":
        return loc.layerTruecolor;
      case "ndvi":
        return loc.layerNdvi;
      case "sm":
        return loc.layerSm;
      case "rain":
        return loc.layerRain;
      case "lst":
        return loc.layerLst;
    }
  };

  return (
    <header className="topbar">
      <div className="topbar-group">
        {onBackToDashboard ? (
          <button
            className="lg-capsule tap"
            type="button"
            data-testid="proto-back-dashboard"
            onClick={onBackToDashboard}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              height: "36px",
              padding: "0 12px",
              borderRadius: "999px",
              color: "#f4f7f4",
              fontWeight: 600,
              fontSize: "12px",
              cursor: "pointer",
              border: "1px solid rgba(255,255,255,0.14)",
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            <span>{backLabel || UI_DICT[lang].common.backToCommandCenter}</span>
          </button>
        ) : null}
        <div className="brand-dock lg-capsule" aria-label={loc.ui.ariaPresetsRegion}>
          <div className="brand-id">
            <svg
              className="brand-glyph"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M12 21c-4.5-2.6-7-6.8-7-11.2C7.8 9.8 10.6 11.4 12 14c1.4-2.6 4.2-4.2 7-4.2 0 4.4-2.5 8.6-7 11.2z" />
              <path d="M12 14V3" />
            </svg>
            <div className="brand-title">
              FieldShift<span>{loc.brandRegion}</span>
            </div>
          </div>

          <div
            className="preset-pills"
            id="preset-pills"
            role="group"
            aria-label={loc.ui.ariaPresetsSelect}
          >
            {presets.map((raw) => {
              const p = pLoc(raw, loc);
              return (
                <button
                  key={p.id}
                  className="preset-btn tap"
                  type="button"
                  data-preset={p.id}
                  title={loc.presetTip(p)}
                  aria-pressed={p.id === activePreset.id}
                  onClick={() => onSelectPreset(p.id)}
                >
                  <span>{p.short}</span>
                  <span className="p-slope num">{p.slope}%</span>
                </button>
              );
            })}
          </div>

          <div className="preset-select-wrap">
            <select
              className="preset-select"
              id="preset-select"
              aria-label={loc.ui.ariaSelectParcel}
              value={activePreset.id}
              onChange={(e) => onSelectPreset(e.target.value as PresetId)}
            >
              {presets.map((raw) => {
                const p = pLoc(raw, loc);
                return (
                  <option key={p.id} value={p.id}>
                    {loc.presetOpt(p)}
                  </option>
                );
              })}
            </select>
          </div>
        </div>

        <div className="lang-dock lg-capsule" id="lang-dock" role="group" aria-label={loc.ui.ariaLanguage}>
          <button
            className="lang-btn tap"
            type="button"
            data-lang="en"
            aria-pressed={lang === "en"}
            title="English"
            onClick={() => onSelectLang("en")}
          >
            EN
          </button>
          <button
            className="lang-btn tap"
            type="button"
            data-lang="ar"
            aria-pressed={lang === "ar"}
            title="العربية"
            onClick={() => onSelectLang("ar")}
          >
            عربي
          </button>
          <button
            className="lang-btn tap"
            type="button"
            data-lang="fr"
            aria-pressed={lang === "fr"}
            title="Français"
            onClick={() => onSelectLang("fr")}
          >
            FR
          </button>
        </div>
      </div>

      <div className="topbar-group">
        <nav className="layer-dock lg-capsule" aria-label={loc.ui.ariaLayers}>
          {LAYER_ORDER.map((key) => (
            <button
              key={key}
              className="layer-btn tap"
              type="button"
              data-layer={key}
              aria-pressed={toggles[key]}
              title={loc.layerTips[key]}
              onClick={() => onToggleLayer(key)}
            >
              <i className="dot" />
              <span>{layerLabel(key)}</span>
            </button>
          ))}
        </nav>

        <div className="tools-dock lg-capsule" aria-label={loc.ui.ariaControls}>
          <button
            className="tool-btn primary tap"
            id="focus"
            type="button"
            title={loc.focusTip}
            onClick={onToggleFocus}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="3" />
              <path d="M12 2v3m0 14v3M2 12h3m14 0h3" />
            </svg>
            <span id="focus-lbl">
              {isRegionalView ? loc.toolParcel : loc.toolRegion}
            </span>
          </button>

          <button
            className="tool-btn tap"
            id="tilt-btn"
            type="button"
            aria-pressed={tiltOn}
            title={loc.tiltTip}
            onClick={onToggleTilt}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 3l9 4.5-9 4.5-9-4.5L12 3z" />
              <path d="M3 12l9 4.5 9-4.5" />
            </svg>
            <span>{loc.tool3d}</span>
          </button>

          <button
            className="tool-btn tap"
            id="zen-btn"
            type="button"
            aria-pressed={zenMode}
            title={loc.zenTip}
            onClick={onToggleZen}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="3" y="4" width="18" height="16" rx="3" />
              <path d="M9 4v16" />
            </svg>
            <span>{loc.toolClean}</span>
          </button>

          {onEditBorders ? (
            <button
              className="tool-btn tap"
              type="button"
              data-testid="proto-edit-borders"
              onClick={onEditBorders}
            >
              <span>{editBordersLabel || loc.ui.bordersBtn}</span>
            </button>
          ) : null}

          <button
            className="tool-btn tap"
            id="plain-btn"
            type="button"
            aria-pressed={plainMode}
            title={loc.plainTip}
            onClick={onTogglePlain}
          >
            <b style={{ fontWeight: 700, letterSpacing: "-0.02em" }}>Aa</b>
            <span>{loc.toolPlain}</span>
          </button>

          <button
            className="tool-btn tap"
            id="guide-btn"
            type="button"
            title={loc.guideTip}
            onClick={onOpenGuide}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="9" />
              <path d="M9.5 9.5a2.5 2.5 0 0 1 4.8.8c0 1.7-2.3 2.1-2.3 3.7" />
              <circle cx="12" cy="17.2" r=".6" fill="currentColor" />
            </svg>
            <span>{loc.toolGuide}</span>
          </button>
        </div>
      </div>
    </header>
  );
}

