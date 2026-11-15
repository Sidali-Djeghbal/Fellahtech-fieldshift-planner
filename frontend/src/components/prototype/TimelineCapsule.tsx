"use client";

import React from "react";
import { MONTHS } from "@/lib/prototype/data";
import type { LocaleDict } from "@/lib/prototype/i18n";
import type { ClimateData, LayerKey } from "@/lib/prototype/types";

interface TimelineCapsuleProps {
  loc: LocaleDict;
  clim: ClimateData;
  monthIndex: number;
  playing: boolean;
  toggles: Record<LayerKey, boolean>;
  onTogglePlay: () => void;
  onScrub: (index: number) => void;
  onScrubCommit: (index: number) => void;
  onSelectMonthFromSpark: (monthNumber: number) => void;
  onCyclePreviewLayer: () => void;
}

const SYNC_PRIORITY: LayerKey[] = ["ndvi", "rain", "sm", "lst", "truecolor"];

export function TimelineCapsule({
  loc,
  clim,
  monthIndex,
  playing,
  toggles,
  onTogglePlay,
  onScrub,
  onScrubCommit,
  onSelectMonthFromSpark,
  onCyclePreviewLayer,
}: TimelineCapsuleProps) {
  const when = MONTHS[monthIndex] || { y: 2025, m: 1 };
  const dateStr = `${loc.mn[when.m - 1]} ${when.y}`;
  const mm = clim.rain[when.m - 1] ?? 0;
  const mmInt = Math.round(mm);
  const rainPillCls =
    "time-rain-pill num" + (mm >= 65 ? " wet" : mm <= 16 ? " hot" : "");

  const tagState =
    mm >= 65
      ? { text: loc.wetTag, cls: "time-tag wet" }
      : mm >= 28
      ? { text: loc.growTag, cls: "time-tag grow" }
      : mm > 16
      ? { text: loc.aridTag, cls: "time-tag arid" }
      : { text: loc.hotTag, cls: "time-tag hot" };

  const activeLayer = SYNC_PRIORITY.find((k) => toggles[k]);
  const syncLabel = activeLayer
    ? loc.timeSynced(loc.layerShort[activeLayer] || activeLayer, dateStr)
    : loc.timePreview;

  const maxR = Math.max(...clim.rain);

  return (
    <footer className="timeline-wrap">
      <div
        className="timeline-dock lg-capsule"
        role="region"
        aria-label={loc.ui.ariaTimeline}
      >
        <div className="time-header">
          <div className="time-purpose">
            <span className="time-kicker-dot" aria-hidden="true" />
            <span className="time-kicker" id="time-kicker">
              {loc.timeKicker}
            </span>
          </div>
          <button
            className={`time-sync-btn tap${activeLayer ? " live" : ""}`}
            type="button"
            id="time-sync-btn"
            onClick={onCyclePreviewLayer}
          >
            {syncLabel}
          </button>
        </div>

        <div className="time-main">
          <button
            className="play-btn tap"
            id="play"
            type="button"
            aria-label={loc.ui.ariaPlay}
            onClick={onTogglePlay}
          >
            <svg viewBox="0 0 10 10">
              <path
                id="play-icon"
                d={
                  playing
                    ? "M1 0.5 H3.6 V9.5 H1 Z M6.4 0.5 H9 V9.5 H6.4 Z"
                    : "M1.5 0.5 L9 5 L1.5 9.5 Z"
                }
              />
            </svg>
          </button>

          <div className="time-meta">
            <div className="time-date-row">
              <span className="time-date num" id="t-date">
                {dateStr}
              </span>
              <span className={rainPillCls} id="t-rain-pill">
                {mmInt} {loc.uMm}
              </span>
            </div>
            <span className={tagState.cls} id="t-tag">
              {tagState.text}
            </span>
          </div>

          <div className="time-scrubber" dir="ltr">
            <input
              type="range"
              id="slider"
              min={0}
              max={MONTHS.length - 1}
              value={monthIndex}
              step={1}
              aria-label={loc.ui.ariaTimelineMonth}
              onChange={(e) => onScrub(Number(e.target.value))}
              onMouseUp={(e) =>
                onScrubCommit(Number((e.target as HTMLInputElement).value))
              }
              onTouchEnd={(e) =>
                onScrubCommit(Number((e.target as HTMLInputElement).value))
              }
            />
            <div className="time-ticks num" id="time-ticks">
              {loc.ticks.map((tk) => (
                <span key={tk}>{tk}</span>
              ))}
            </div>
          </div>

          <div className="spark-wrap">
            <span className="spark-hdr" id="spark-hdr">
              {loc.sparkLbl}
            </span>
            <div
              className="spark"
              id="spark"
              dir="ltr"
              aria-label={loc.ui.ariaRainfallNormal}
            >
              {clim.rain.map((rVal, i) => (
                <button
                  key={i}
                  type="button"
                  title={loc.sparkTip(loc.mn[i], rVal.toFixed(0))}
                  style={{
                    height: `${Math.max(4, Math.round((rVal / maxR) * 26))}px`,
                  }}
                  className={when.m === i + 1 ? "on" : undefined}
                  data-m={i + 1}
                  onClick={() => onSelectMonthFromSpark(i + 1)}
                />
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="disclaimer-line">{loc.disclaimer}</div>
    </footer>
  );
}

