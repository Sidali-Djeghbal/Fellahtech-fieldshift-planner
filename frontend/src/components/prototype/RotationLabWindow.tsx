"use client";

import React from "react";
import { sLoc, type LocaleDict } from "@/lib/prototype/i18n";
import type {
  EvalResult,
  Priority,
  StratId,
  StrategyDef,
} from "@/lib/prototype/types";

interface StrategyWithEval {
  strat: StrategyDef;
  res: EvalResult;
}

interface RotationLabWindowProps {
  loc: LocaleDict;
  priority: Priority;
  selectedStrat: StratId;
  irrigated: boolean;
  lowInput: boolean;
  rain: number;
  temp: number;
  collapsed: boolean;
  zenMode: boolean;
  mobOpen: boolean;
  results: StrategyWithEval[];
  panelRef: React.RefObject<HTMLElement | null>;
  onToggleCollapse: () => void;
  onChangePriority: (p: Priority) => void;
  onToggleIrrigated: () => void;
  onToggleLowInput: () => void;
  onSelectStrategy: (id: StratId) => void;
  onSelectScenarioPreset: (rain: number, temp: number) => void;
  onChangeRain: (rain: number) => void;
  onChangeTemp: (temp: number) => void;
}

const PRIORITIES: { id: Priority; getLabel: (loc: LocaleDict) => string }[] = [
  { id: "balanced", getLabel: (l) => l.prioBalanced },
  { id: "water", getLabel: (l) => l.prioWater },
  { id: "soil", getLabel: (l) => l.prioSoil },
  { id: "income", getLabel: (l) => l.prioIncome },
];

const SCEN_CHIPS: {
  rain: number;
  temp: number;
  id?: string;
  getLabel: (loc: LocaleDict) => string;
}[] = [
  { rain: 0, temp: 0, id: "reset", getLabel: (l) => l.chipBase },
  { rain: -20, temp: 0, getLabel: (l) => l.chipDry },
  { rain: -25, temp: 2.5, getLabel: (l) => l.chipShock },
];

export function RotationLabWindow({
  loc,
  priority,
  selectedStrat,
  irrigated,
  lowInput,
  rain,
  temp,
  collapsed,
  zenMode,
  mobOpen,
  results,
  panelRef,
  onToggleCollapse,
  onChangePriority,
  onToggleIrrigated,
  onToggleLowInput,
  onSelectStrategy,
  onSelectScenarioPreset,
  onChangeRain,
  onChangeTemp,
}: RotationLabWindowProps) {
  const base = results[0].res;
  const best = results.reduce((a, b) => (b.res.total > a.res.total ? b : a));
  const hasScen = Boolean(rain || temp);
  const scenText = loc.scenActive(rain, temp);

  return (
    <section
      ref={panelRef}
      className={`lab-window lg-surface${collapsed ? " collapsed" : ""}${
        zenMode ? " hidden-mode" : ""
      }${mobOpen ? " mob-open" : ""}`}
      id="lab"
      aria-label={loc.ui.ariaLab}
    >
      <div className="win-head">
        <div className="win-title-wrap">
          <h2 className="win-title">{loc.labTitle}</h2>
          <span
            className={`scen-badge${hasScen ? " active" : ""}`}
            id="scen-note"
          >
            {scenText}
          </span>
        </div>
        <button
          className="icon-pill tap"
          id="collapse"
          type="button"
          aria-label={loc.ui.ariaCollapseLab}
          aria-expanded={!collapsed}
          onClick={onToggleCollapse}
        >
          {collapsed ? "+" : "–"}
        </button>
      </div>

      <div className="lab-scroll" id="lab-body">
        <div className="seg-track" role="group" aria-label={loc.ui.ariaPriority}>
          {PRIORITIES.map((p) => (
            <button
              key={p.id}
              className="prio tap"
              type="button"
              data-prio={p.id}
              aria-pressed={priority === p.id}
              onClick={() => onChangePriority(p.id)}
            >
              {p.getLabel(loc)}
            </button>
          ))}
        </div>

        <div className="constraint-row" role="group" aria-label={loc.ui.ariaConstraints}>
          <button
            className="const-btn is-irrig tap"
            id="c-irrig"
            type="button"
            aria-pressed={irrigated}
            onClick={onToggleIrrigated}
          >
            <i className="const-dot" aria-hidden="true" />
            <span id="c-irrig-lbl">
              {irrigated ? loc.constIrrig : loc.constRainfed}
            </span>
          </button>
          <button
            className="const-btn tap"
            id="c-lowin"
            type="button"
            aria-pressed={lowInput}
            onClick={onToggleLowInput}
          >
            <i className="const-dot" aria-hidden="true" />
            <span id="c-lowin-lbl">{loc.constLowIn}</span>
          </button>
        </div>

        <div className="strats" id="strats">
          {results.map(({ strat: rawS, res: r }) => {
            const s = sLoc(rawS, loc);
            const vals = [r.water, r.soil, r.erosion, r.income, r.risk];
            const topDim = vals.reduce(
              (bestIdx, v, idx, arr) => (v > arr[bestIdx] ? idx : bestIdx),
              0
            );
            const delta = base.exposureDays - r.exposureDays;
            const isCurr = Boolean(rawS.current);
            const isBest = rawS.id === best.strat.id;
            const tagClass = isCurr ? "curr" : isBest ? "best" : "";
            const tagText = isCurr
              ? loc.currentTag
              : isBest
              ? loc.bestTag
              : s.tag;

            return (
              <button
                key={rawS.id}
                className="strat tap"
                type="button"
                aria-current={selectedStrat === rawS.id ? "true" : undefined}
                data-id={rawS.id}
                aria-label={loc.fitAria(s.name, r.total)}
                onClick={() => onSelectStrategy(rawS.id)}
              >
                <div className="strat-main">
                  <div className="strat-top">
                    <span className="strat-name">{s.name}</span>
                    <span className={`strat-tag ${tagClass}`}>{tagText}</span>
                  </div>
                  <div className="strat-sub">
                    <span className="dims" aria-hidden="true">
                      {vals.map((v, i) => (
                        <i
                          key={loc.dims[i]}
                          style={{
                            height: `${Math.max(3, Math.round(v * 12))}px`,
                          }}
                          className={i === topDim ? "hi" : ""}
                          title={`${loc.dims[i]}: ${Math.round(v * 100)}%`}
                        />
                      ))}
                    </span>
                    <span className="exp-pill num">
                      <b>{r.exposureDays}</b> {loc.bareWetShort}
                    </span>
                    {isCurr ? (
                      <span className="exp-delta warn">{loc.baselinePill}</span>
                    ) : (
                      <span
                        className={`exp-delta${delta > 0 ? "" : " warn"}`}
                      >
                        {loc.deltaShort(delta)}
                      </span>
                    )}
                  </div>
                </div>
                <div className="strat-score num">
                  <strong>{r.total}</strong>
                  <span>{loc.fitCard}</span>
                </div>
              </button>
            );
          })}
        </div>

        <div className="scen-box">
          <div className="scen-head">
            <span className="scen-title">{loc.scenTitle}</span>
            <div className="scen-presets">
              {SCEN_CHIPS.map((c) => (
                <button
                  key={`${c.rain},${c.temp}`}
                  id={c.id}
                  type="button"
                  className={`mini-chip tap${
                    rain === c.rain && temp === c.temp ? " on" : ""
                  }`}
                  data-scen={`${c.rain},${c.temp}`}
                  onClick={() => onSelectScenarioPreset(c.rain, c.temp)}
                >
                  {c.getLabel(loc)}
                </button>
              ))}
            </div>
          </div>

          <div className="slider-row">
            <label htmlFor="rain-s">{loc.lblRain}</label>
            <input
              type="range"
              id="rain-s"
              min={-30}
              max={30}
              step={5}
              value={rain}
              onChange={(e) => onChangeRain(Number(e.target.value))}
            />
            <output className="num" id="rain-o" dir="ltr">
              {rain > 0 ? `+${rain}%` : `${rain}%`}
            </output>
          </div>

          <div className="slider-row">
            <label htmlFor="temp-s">{loc.lblTemp}</label>
            <input
              type="range"
              id="temp-s"
              min={0}
              max={4}
              step={0.5}
              value={temp}
              onChange={(e) => onChangeTemp(Number(e.target.value))}
            />
            <output className="num" id="temp-o" dir="ltr">
              +{temp.toFixed(1).replace(".0", "")}°C
            </output>
          </div>
        </div>
      </div>
    </section>
  );
}

