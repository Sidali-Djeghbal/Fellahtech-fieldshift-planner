"use client";

import React, { useEffect, useRef } from "react";
import { SOIL_TYPE_LABELS } from "@/lib/i18n";
import { GUELMA_WORKSPACE_I18N } from "@/lib/i18n/guelmaWorkspace";
import { CLIMATES, MONTHS, SOILS } from "@/lib/prototype/data";
import { ringAreaHa } from "@/lib/prototype/engine";
import { pLoc, sLoc, type LocaleDict } from "@/lib/prototype/i18n";
import type {
  EvalResult,
  InspectorTab,
  Lang,
  Preset,
  StratId,
  StrategyDef,
} from "@/lib/prototype/types";

interface StrategyWithEval {
  strat: StrategyDef;
  res: EvalResult;
}

interface FieldInspectorWindowProps {
  loc: LocaleDict;
  lang?: Lang;
  rawPreset: Preset;
  liveElev: number;
  liveSlope: number;
  activeTab: InspectorTab;
  selectedStrat: StratId;
  irrigated: boolean;
  lowInput: boolean;
  rain: number;
  temp: number;
  monthIndex: number;
  canZoomDetail: boolean;
  collapsed: boolean;
  zenMode: boolean;
  mobOpen: boolean;
  results: StrategyWithEval[];
  panelRef: React.RefObject<HTMLElement | null>;
  onSelectTab: (tab: InspectorTab) => void;
  onToggleCollapse: () => void;
  onFocusCardAction: () => void;
  onSelectStrategy: (id: StratId, openAudit: boolean) => void;
}

export function FieldInspectorWindow({
  loc,
  lang = "en",
  rawPreset,
  liveElev,
  liveSlope,
  activeTab,
  selectedStrat,
  irrigated,
  lowInput,
  rain,
  temp,
  monthIndex,
  canZoomDetail,
  collapsed,
  zenMode,
  mobOpen,
  results,
  panelRef,
  onSelectTab,
  onToggleCollapse,
  onFocusCardAction,
  onSelectStrategy,
}: FieldInspectorWindowProps) {
  const bodyRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = 0;
    }
  }, [activeTab]);

  const p = pLoc(rawPreset, loc);
  const clim = CLIMATES[rawPreset.climate];
  const ha = (rawPreset.areaHa ?? ringAreaHa(rawPreset.ring)).toFixed(1);
  const slopeStr = liveSlope.toFixed(1);
  const when = MONTHS[monthIndex] || { y: 2025, m: 1 };
  const monthRain = clim.rain[when.m - 1] ?? 0;

  const wb = clim.annual - clim.et0;
  const farmerSoilKnown = Boolean(rawPreset.soilType && rawPreset.soilType !== "unknown");
  const soilBase = {
    soc: rawPreset.soilOm ?? (SOILS[rawPreset.id]?.soc || "1.1"),
    ph: rawPreset.soilPh ?? (SOILS[rawPreset.id]?.ph || "7.4"),
  };
  const soilLoc = farmerSoilKnown
    ? {
        texture:
          (rawPreset.soilType && rawPreset.soilType !== "unknown"
            ? SOIL_TYPE_LABELS[lang]?.[rawPreset.soilType as keyof (typeof SOIL_TYPE_LABELS)["en"]]
            : undefined) ?? SOIL_TYPE_LABELS[lang].loamy,
        omTrend: rawPreset.commune
          ? `${rawPreset.commune} · ${GUELMA_WORKSPACE_I18N[lang].soilFarmerKnown}`
          : GUELMA_WORKSPACE_I18N[lang].soilFarmerKnown,
      }
    : loc.soils[rawPreset.id] || {
        texture: SOIL_TYPE_LABELS[lang].loamy,
        omTrend: "—",
      };

  const base = results[0].res;
  const selEntry =
    results.find((x) => x.strat.id === selectedStrat) || results[0];
  const selLoc = sLoc(selEntry.strat, loc);
  const selRes = selEntry.res;

  // Overlap bar calculation
  const rainArr = selRes.monthlyExposure.map((x) => x.rain);
  const maxR = Math.max(10, ...rainArr);
  const savedDays = base.exposureDays - selRes.exposureDays;

  // Comparison highlights
  const maxFit = Math.max(...results.map((x) => x.res.total));
  const minExp = Math.min(...results.map((x) => x.res.exposureDays));
  const maxWat = Math.max(...results.map((x) => x.res.water));
  const maxRisk = Math.max(...results.map((x) => x.res.risk));
  const vals = loc.cmpVals;
  const consTxt = `${irrigated ? vals.irrOn : vals.rainfedMode} · ${
    lowInput ? vals.lowInOn : vals.stdMode
  }`;

  const cellClass = (
    id: StratId,
    good: boolean,
    warn = false,
    isNum = false
  ) => {
    const cls: string[] = [];
    if (id === selectedStrat) cls.push("cmp-sel-col");
    if (good) cls.push("cmp-best");
    else if (warn) cls.push("cmp-warn");
    if (isNum) cls.push("num");
    return cls.join(" ");
  };

  // Audit values
  const peakIdx = clim.rain.indexOf(Math.max(...clim.rain));
  const peakRain = clim.rain[peakIdx].toFixed(0);
  const peakMonthName = loc.mn[peakIdx] || loc.mn[0];
  const auditVals = [
    selRes.water,
    selRes.soil,
    selRes.erosion,
    selRes.income,
    selRes.risk,
  ];
  const dynamicEvidence = loc.evidence(
    clim,
    peakRain,
    peakMonthName,
    slopeStr,
    liveElev,
    p.name,
    selEntry.strat
  );

  return (
    <aside
      ref={panelRef}
      className={`inspector lg-surface${collapsed ? " collapsed" : ""}${
        zenMode ? " hidden-mode" : ""
      }${mobOpen ? " mob-open" : ""}`}
      id="inspector"
      aria-label={loc.ui.ariaInspector}
    >
      <div className="win-head">
        <div className="insp-tabs" role="tablist" aria-label={loc.ui.ariaInspectorView}>
          <button
            className="insp-tab tap"
            id="tab-field"
            type="button"
            role="tab"
            aria-selected={activeTab === "field"}
            onClick={() => onSelectTab("field")}
          >
            {loc.tabField}
          </button>
          <button
            className="insp-tab tap"
            id="tab-compare"
            type="button"
            role="tab"
            aria-selected={activeTab === "compare"}
            onClick={() => onSelectTab("compare")}
          >
            {loc.tabCompare}
          </button>
          <button
            className="insp-tab tap"
            id="tab-audit"
            type="button"
            role="tab"
            aria-selected={activeTab === "audit"}
            onClick={() => onSelectTab("audit")}
          >
            {loc.tabAudit}
          </button>
        </div>
        <button
          className="icon-pill tap"
          id="collapse-insp"
          type="button"
          aria-label={loc.ui.ariaCollapseInspector}
          aria-expanded={!collapsed}
          onClick={onToggleCollapse}
        >
          {collapsed ? "+" : "–"}
        </button>
      </div>

      <div className="insp-body" id="insp-body" ref={bodyRef}>
        {/* Pane 1: Field Profile */}
        <div
          className={`insp-pane${activeTab === "field" ? " active" : ""}`}
          id="pane-field"
          role="tabpanel"
        >
          <div className="place-kicker">
            <i />
            <span id="f-zone">{p.zone}</span>
          </div>
          <h2 className="insp-h2" id="f-name">
            {p.name}
          </h2>
          <div className="coords-row num">
            <span id="f-coords" dir="ltr">
              {rawPreset.center.lat.toFixed(4)}° N ·{" "}
              {rawPreset.center.lon.toFixed(4)}° E
            </span>
            <span id="f-climate-summary">
              {loc.climates[rawPreset.climate] || clim.label}
            </span>
          </div>
          <p className="zone-note" id="f-note">
            {p.note}
          </p>

          <div className="stats-grid">
            <div className="stat-tile">
              <span>{loc.statArea}</span>
              <b className="num" id="s-area">
                {ha}
                <i>{loc.uHa}</i>
              </b>
            </div>
            <div className="stat-tile">
              <span>{loc.statSlope}</span>
              <b className="num" id="s-slope">
                {slopeStr}
                <i>%</i>
              </b>
            </div>
            <div className="stat-tile">
              <span>{loc.statElev}</span>
              <b className="num" id="s-elev">
                {liveElev}
                <i>{loc.uM}</i>
              </b>
            </div>
            <div className="stat-tile">
              <span>{loc.statRain}</span>
              <b className="num" id="s-rain">
                {monthRain.toFixed(0)}
                <i>{loc.uMm}</i>
              </b>
            </div>
          </div>

          <div className="health-grid">
            <div className="health-card">
              <div className="health-top">
                <span className="health-lbl">{loc.hlthStressLbl}</span>
                <span className="conf-tag med">{loc.confPower}</span>
              </div>
              <div className="health-val num" id="h-heat-val">
                {loc.heatSummaryFmt(
                  clim.heat35,
                  clim.heatLast5,
                  clim.dryMonths
                )}
              </div>
              <div className="health-sub num" id="h-wb-val">
                {loc.wbSummaryFmt(
                  clim.annual,
                  clim.et0,
                  wb,
                  clim.powerElev,
                  liveElev
                )}
              </div>
              <div className="plain-hint">{loc.plainStress}</div>
            </div>

            <div className="health-card">
              <div className="health-top">
                <span className="health-lbl">{loc.hlthSoilLbl}</span>
                <span className={`conf-tag ${farmerSoilKnown ? "med" : "low"}`}>
                  {farmerSoilKnown ? loc.confPower : loc.confSoilLow}
                </span>
              </div>
              <div className="health-val" id="h-soil-tex">
                {soilLoc.texture}
              </div>
              <div className="health-sub num" id="h-soil-meta">
                {loc.soilMetaFmt({ ...soilBase, ...soilLoc })}
              </div>
              <div className="plain-hint">{loc.plainSoil}</div>
            </div>
          </div>

          <div className="local-review-strip" id="f-local-strip">
            {loc.localReviewNote}
          </div>

          <div className="overlap-card">
            <div className="overlap-top">
              <strong>{loc.ovTitle}</strong>
              <span id="ov-strat-lbl">{selLoc.name}</span>
            </div>
            <div
              className="overlap-bars"
              id="overlap-bars"
              dir="ltr"
              aria-hidden="true"
            >
              {selRes.monthlyExposure.map((mData, idx) => {
                const isRisk = mData.rain >= 45 && mData.cover < 0.45;
                const isCovered = mData.rain >= 45 && mData.cover >= 0.65;
                const h = Math.max(10, Math.round((mData.rain / maxR) * 100));
                const cls =
                  "ov-col" +
                  (isRisk ? " risk" : isCovered ? " covered" : "") +
                  (idx === when.m - 1 ? " cur-m" : "");
                return (
                  <div
                    key={idx}
                    className={cls}
                    title={loc.ovTip(
                      loc.mn[idx],
                      mData.rain.toFixed(0),
                      Math.round(mData.cover * 100)
                    )}
                  >
                    <div className="ov-stack">
                      <div className="ov-rain" style={{ height: `${h}%` }} />
                    </div>
                    <em>{loc.mi[idx]}</em>
                  </div>
                );
              })}
            </div>
            <p className="overlap-cap" id="ov-cap">
              {selEntry.strat.current
                ? loc.ovCapBase(selRes.exposureDays, slopeStr)
                : loc.ovCapAlt(selRes.exposureDays, savedDays)}
            </p>
          </div>

          <button
            className="btn-primary tap"
            id="focus-card-btn"
            type="button"
            onClick={onFocusCardAction}
          >
            {canZoomDetail ? loc.zoomDetail : loc.showRegion}
          </button>

          <div className="prov-card" id="prov">
            {loc.provLine1}
            <br />
            {loc.provLine2}
          </div>
        </div>

        {/* Pane 2: Side-by-Side Comparison Matrix */}
        <div
          className={`insp-pane${activeTab === "compare" ? " active" : ""}`}
          id="pane-compare"
          role="tabpanel"
          aria-live="polite"
        >
          <div className="place-kicker">
            <i />
            <span>{loc.cmpKicker}</span>
          </div>
          <h2 className="insp-h2" id="cmp-title">
            {loc.cmpTitleFmt(p.short)}
          </h2>
          <p className="cmp-sub" id="cmp-sub">
            {loc.cmpSubFmt(loc.scenActive(rain, temp), consTxt)}
          </p>
          <div className="cmp-wrap">
            <table
              className="cmp-table"
              id="cmp-table"
              aria-label={loc.ui.ariaComparisonMatrix}
            >
              <thead>
                <tr>
                  <th />
                  {results.map(({ strat }) => {
                    const isSel = strat.id === selectedStrat;
                    return (
                      <th key={strat.id}>
                        <button
                          type="button"
                          className={`cmp-col-btn tap${isSel ? " sel" : ""}`}
                          data-cmp-id={strat.id}
                          onClick={() => onSelectStrategy(strat.id, false)}
                        >
                          {loc.cmpShort[strat.id]}
                          <small>{sLoc(strat, loc).tag}</small>
                        </button>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>{loc.cmpRows.fit}</td>
                  {results.map(({ strat, res }) => (
                    <td
                      key={strat.id}
                      className={cellClass(
                        strat.id,
                        res.total === maxFit,
                        false,
                        true
                      )}
                    >
                      {res.total}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>{loc.cmpRows.bareWet}</td>
                  {results.map(({ strat, res }) => {
                    const d = base.exposureDays - res.exposureDays;
                    const note = strat.current ? "" : ` (${loc.deltaShort(d)})`;
                    return (
                      <td
                        key={strat.id}
                        className={cellClass(
                          strat.id,
                          res.exposureDays === minExp,
                          Boolean(strat.current),
                          true
                        )}
                      >
                        {res.exposureDays} d{note}
                      </td>
                    );
                  })}
                </tr>
                <tr>
                  <td>{loc.cmpRows.water}</td>
                  {results.map(({ strat, res }) => (
                    <td
                      key={strat.id}
                      className={cellClass(
                        strat.id,
                        res.water === maxWat,
                        false,
                        true
                      )}
                    >
                      {Math.round(res.water * 100)}%
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>{loc.cmpRows.nfix}</td>
                  {results.map(({ strat, res }) => (
                    <td
                      key={strat.id}
                      className={cellClass(
                        strat.id,
                        res.avgNKgHa > 0,
                        res.avgNKgHa === 0,
                        true
                      )}
                    >
                      {res.avgNKgHa} kg/ha
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>{loc.cmpRows.roots}</td>
                  {results.map(({ strat }, i) => (
                    <td
                      key={strat.id}
                      className={cellClass(strat.id, i > 0, i === 0)}
                    >
                      {i === 0
                        ? vals.roots0
                        : i === 1
                        ? vals.roots1
                        : vals.roots2}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>{loc.cmpRows.pest}</td>
                  {results.map(({ strat }, i) => (
                    <td
                      key={strat.id}
                      className={cellClass(strat.id, i > 0, i === 0)}
                    >
                      {i === 0
                        ? vals.break0
                        : i === 1
                        ? vals.break1
                        : vals.break2}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>{loc.cmpRows.stress}</td>
                  {results.map(({ strat, res }) => (
                    <td
                      key={strat.id}
                      className={cellClass(
                        strat.id,
                        res.risk === maxRisk,
                        false,
                        true
                      )}
                    >
                      {Math.round(res.risk * 100)}%
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>{loc.cmpRows.conf}</td>
                  {results.map(({ strat }, i) => (
                    <td
                      key={strat.id}
                      className={cellClass(strat.id, false)}
                    >
                      {i === 0 ? vals.confMed : vals.confLowGap}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
          <button
            className="btn-primary tap"
            id="cmp-audit-btn"
            type="button"
            onClick={() => onSelectStrategy(selectedStrat, true)}
          >
            {loc.cmpInspect}
          </button>
        </div>

        {/* Pane 3: Strategy Audit */}
        <div
          className={`insp-pane${activeTab === "audit" ? " active" : ""}`}
          id="pane-audit"
          role="tabpanel"
          aria-live="polite"
        >
          <button
            className="audit-back tap"
            id="back"
            type="button"
            onClick={() => onSelectTab("field")}
          >
            {loc.backField}
          </button>
          <div className="place-kicker">
            <i />
            <span id="d-kicker">
              {selEntry.strat.current
                ? `${loc.kickerBase} · ${p.short}`
                : `${loc.kickerAlt} · ${p.short}`}
            </span>
          </div>
          <h2 className="insp-h2" id="d-name">
            {selLoc.name}
          </h2>

          <div className="audit-hero">
            <div>
              <div className="audit-score num">
                <span id="d-score">{selRes.total}</span>
                <small id="d-fit-lbl">{loc.fitSuffix}</small>
              </div>
            </div>
            <div className="audit-exp">
              <b className="num" id="d-exp">
                {selRes.exposureDays} {loc.bareWetYr}
              </b>
              <span
                id="d-delta"
                className={
                  selEntry.strat.current || savedDays <= 0 ? "warn" : ""
                }
              >
                {selEntry.strat.current
                  ? loc.baselineBench
                  : loc.deltaLong(savedDays)}
              </span>
            </div>
          </div>

          <div className="conf-row">
            <span className="conf-pill">
              <i />
              <span id="d-conf">{selLoc.conf}</span>
            </span>
          </div>

          <div className="dim-breakdown" id="d-dims">
            {loc.auditDims.map((name, idx) => {
              const pct = Math.round(auditVals[idx] * 100);
              const barColor =
                pct >= 70
                  ? "var(--leaf)"
                  : pct >= 45
                  ? "var(--gold)"
                  : "var(--clay)";
              return (
                <div className="dim-row" key={name}>
                  <span>{name}</span>
                  <div className="dim-track">
                    <div
                      className="dim-fill"
                      style={{ width: `${pct}%`, background: barColor }}
                    />
                  </div>
                  <b className="num">{pct}%</b>
                </div>
              );
            })}
          </div>

          <div className="audit-block">
            <h3>{loc.hWhy}</h3>
            <p id="d-why">{selLoc.why}</p>
          </div>
          <div className="audit-block">
            <h3>{loc.hNow}</h3>
            <p id="d-now">
              {selEntry.strat.current
                ? loc.onParcelBase(
                    p.name,
                    slopeStr,
                    liveElev,
                    selRes.exposureDays,
                    selRes.wetDaysTotal
                  )
                : loc.onParcelAlt(
                    p.name,
                    slopeStr,
                    liveElev,
                    selRes.exposureDays,
                    savedDays
                  )}
            </p>
          </div>
          <div className="audit-block">
            <h3>{loc.hEvidence}</h3>
            <ul id="d-evidence">
              {dynamicEvidence.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
          <div className="audit-block">
            <h3>{loc.hBenefits}</h3>
            <ul id="d-benefits">
              {selLoc.benefits.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
          <div className="audit-block">
            <h3>{loc.hGaps}</h3>
            <ul id="d-gaps">
              {selLoc.gaps.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
          <div className="audit-block">
            <h3>{loc.hRisks}</h3>
            <ul id="d-risks">
              {selLoc.risks.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </aside>
  );
}

