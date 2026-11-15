"use client";

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import maplibregl from "maplibre-gl";
import {
  CLIMATES,
  GIBS_KEYS,
  INITIAL_PRESETS,
  LAYERS,
  MONTHS,
  REGION_HOME,
  SOILS,
  STRATS,
  CROPS,
} from "@/lib/prototype/data";
import {
  allPresetsFC,
  dateStrFor,
  evaluate,
  gibsUrl,
  measureFromDem,
  presetFeature,
  ringAreaHa,
} from "@/lib/prototype/engine";
import { getLoc, I18N, pLoc } from "@/lib/prototype/i18n";
import type {
  InspectorTab,
  Lang,
  LayerKey,
  LegendKey,
  MobilePane,
  Preset,
  PresetId,
  Priority,
  ProtoState,
  StratId,
} from "@/lib/prototype/types";
import { useResolvedTheme } from "@/app/providers";
import { useAppStore } from "@/store/useAppStore";
import { BootSplash } from "./BootSplash";
import { FieldInspectorWindow } from "./FieldInspectorWindow";
import { GuideModal } from "./GuideModal";
import { LegendCapsule } from "./LegendCapsule";
import { MobileDock } from "./MobileDock";
import { RotationLabWindow } from "./RotationLabWindow";
import { SkyDiveOverlay } from "./SkyDiveOverlay";
import { TimelineCapsule } from "./TimelineCapsule";
import { TopToolbar } from "./TopToolbar";
import "./prototype.css";

declare global {
  interface Window {
    __map?: maplibregl.Map;
    __field?: Preset["center"];
    __boot?: { start: number; idle: number | null };
    __engine?: Record<string, unknown>;
  }
}

const LEGEND_ORDER: LegendKey[] = ["ndvi", "sm", "rain", "lst"];
const PREVIEW_ORDER: LegendKey[] = ["ndvi", "rain", "sm", "lst"];

function truecolorOpacityForZoom(z: number): number {
  if (z <= 8.6) return 1;
  if (z >= 9.8) return 0;
  return 1 - (z - 8.6) / 1.2;
}

export interface FieldShiftPrototypeAppProps {
  externalPresets?: Preset[];
  initialPresetId?: string;
  backLabel?: string;
  editBordersLabel?: string;
  onBackToDashboard?: () => void;
  onEditBorders?: (presetId: string) => void;
}

export function FieldShiftPrototypeApp({
  externalPresets,
  initialPresetId,
  backLabel,
  editBordersLabel,
  onBackToDashboard,
  onEditBorders,
}: FieldShiftPrototypeAppProps = {}) {
  const setStoreLang = useAppStore((s) => s.setLang);
  const resolvedTheme = useResolvedTheme();

  const presets = useMemo(
    () => (externalPresets && externalPresets.length > 0 ? externalPresets : INITIAL_PRESETS),
    [externalPresets]
  );

  const [protoState, setProtoState] = useState<ProtoState>({
    lang: "en",
    priority: "balanced",
    rain: 0,
    temp: 0,
    selected: "s0",
    irrigated: false,
    lowInput: false,
    plainMode: false,
  });

  const [presetId, setPresetId] = useState<PresetId>(
    initialPresetId || presets[0]?.id || "seybouse"
  );

  useEffect(() => {
    if (initialPresetId && presets.some((p) => p.id === initialPresetId)) {
      setPresetId(initialPresetId);
    } else if (!presets.some((p) => p.id === presetId) && presets[0]) {
      setPresetId(presets[0].id);
    }
  }, [initialPresetId, presets, presetId]);
  const [liveDemMap, setLiveDemMap] = useState<
    Partial<Record<PresetId, { elev: number; slope: number }>>
  >({});

  const [toggles, setToggles] = useState<Record<LayerKey, boolean>>({
    truecolor: false,
    ndvi: false,
    sm: false,
    rain: false,
    lst: false,
  });

  const [activeLegendKey, setActiveLegendKey] = useState<LegendKey | null>(
    null
  );
  const [monthIndex, setMonthIndex] = useState(0);
  const [playing, setPlaying] = useState(false);

  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("field");
  const [labCollapsed, setLabCollapsed] = useState(false);
  const [inspCollapsed, setInspCollapsed] = useState(false);
  const [zenMode, setZenMode] = useState(false);
  const [mobPane, setMobPane] = useState<MobilePane>("map");
  const [guideOpen, setGuideOpen] = useState(false);
  const [isRegionalView, setIsRegionalView] = useState(false);
  const [canZoomDetail, setCanZoomDetail] = useState(true);
  const [tiltOn, setTiltOn] = useState(true);

  const [bootVisible, setBootVisible] = useState(true);
  const [bootFadingOut, setBootFadingOut] = useState(false);
  const [bootNote, setBootNote] = useState(
    I18N.en.bootConnect
  );

  const [skyDiving, setSkyDiving] = useState(false);
  const [skyDone, setSkyDone] = useState(true);
  const [skyStage, setSkyStage] = useState(0);
  const [skyFlash, setSkyFlash] = useState<"none" | "pulse" | "lock">("none");

  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const labRef = useRef<HTMLElement | null>(null);
  const inspRef = useRef<HTMLElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const pinLabelRef = useRef<HTMLSpanElement | null>(null);

  const terrainEnabledRef = useRef(false);
  const skyDiveActiveRef = useRef(false);
  const skyDiveDoneRef = useRef(true);
  const skyDiveStageRef = useRef(0);
  const skyDiveTimersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const activeMoveHandlerRef = useRef<(() => void) | null>(null);
  const tileDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const warnedRef = useRef(false);

  const loc = useMemo(() => getLoc(protoState.lang), [protoState.lang]);
  const activePreset = useMemo(
    () => presets.find((p) => p.id === presetId) ?? presets[0],
    [presets, presetId]
  );

  const activeLiveDem = liveDemMap[activePreset.id];
  const liveElev = activeLiveDem?.elev ?? activePreset.elev;
  const liveSlope = activeLiveDem?.slope ?? activePreset.slope;

  const evalResults = useMemo(
    () =>
      STRATS.map((strat) => ({
        strat,
        res: evaluate(strat, protoState, protoState.priority, activePreset, {
          elev: liveElev,
          slope: liveSlope,
        }),
      })),
    [protoState, activePreset, liveElev, liveSlope]
  );

  const selectedResult = useMemo(
    () =>
      evalResults.find((x) => x.strat.id === protoState.selected) ??
      evalResults[0],
    [evalResults, protoState.selected]
  );

  // Refs synced with latest values for MapLibre callbacks
  const latestRef = useRef({
    loc,
    presets,
    activePreset,
    protoState,
    toggles,
    zenMode,
    labCollapsed,
    inspCollapsed,
    tiltOn,
    monthIndex,
  });
  latestRef.current = {
    loc,
    presets,
    activePreset,
    protoState,
    toggles,
    zenMode,
    labCollapsed,
    inspCollapsed,
    tiltOn,
    monthIndex,
  };

  // Detect initial URL/storage language on client mount
  useEffect(() => {
    let initialLang: Lang = "en";
    const q = new URLSearchParams(window.location.search).get("lang");
    if (q === "en" || q === "fr" || q === "ar") {
      initialLang = q;
    } else {
      try {
        const saved =
          localStorage.getItem("fieldshift.lang") ||
          localStorage.getItem("ard.lang");
        if (saved === "en" || saved === "fr" || saved === "ar") {
          initialLang = saved;
        }
      } catch {
        /* ignore */
      }
    }
    if (initialLang !== "en") {
      setProtoState((prev) => ({ ...prev, lang: initialLang }));
      setBootNote(getLoc(initialLang).bootConnect);
      setStoreLang(initialLang);
    }
  }, [setStoreLang]);

  // Sync document lang/dir/title
  useEffect(() => {
    document.documentElement.lang = protoState.lang;
    document.documentElement.dir = protoState.lang === "ar" ? "rtl" : "ltr";
    document.title = loc.pageTitle;
  }, [protoState.lang, loc.pageTitle]);

  const computeDockedPadding = useCallback(() => {
    if (typeof window === "undefined") {
      return { top: 72, bottom: 94, left: 402, right: 374 };
    }
    if (window.innerWidth <= 900) {
      return { top: 72, bottom: 140, left: 16, right: 16 };
    }
    const { zenMode: z, labCollapsed: lc, inspCollapsed: ic } = latestRef.current;
    const labOpen = !z && !lc;
    const inspOpen = !z && !ic;
    const labWidth = labRef.current?.getBoundingClientRect().width || 376;
    const inspWidth = inspRef.current?.getBoundingClientRect().width || 348;
    const labPad = labOpen ? labWidth + 26 : 24;
    const inspPad = inspOpen ? inspWidth + 26 : 24;
    const rtl = document.documentElement.dir === "rtl";

    return {
      top: 72,
      bottom: 94,
      left: rtl ? inspPad : labPad,
      right: rtl ? labPad : inspPad,
    };
  }, []);

  const applyMapPadding = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    if (skyDiveActiveRef.current) {
      map.setPadding({ top: 0, bottom: 0, left: 0, right: 0 });
      return;
    }
    map.setPadding(computeDockedPadding());
  }, [computeDockedPadding]);

  useEffect(() => {
    const t = setTimeout(applyMapPadding, 20);
    window.addEventListener("resize", applyMapPadding);
    return () => {
      clearTimeout(t);
      window.removeEventListener("resize", applyMapPadding);
    };
  }, [
    applyMapPadding,
    zenMode,
    labCollapsed,
    inspCollapsed,
    protoState.lang,
  ]);

  const enableTerrain = useCallback(() => {
    const map = mapRef.current;
    if (!map || terrainEnabledRef.current) return;
    terrainEnabledRef.current = true;
    try {
      map.setTerrain({ source: "dem", exaggeration: 1.15 });
      if (map.getStyle && map.getStyle().layers.length < 2) {
        throw new Error("terrain reset style");
      }
    } catch {
      try {
        map.setTerrain(null);
      } catch {
        /* ignore */
      }
    }
  }, []);

  const clearMoveWait = useCallback(() => {
    const map = mapRef.current;
    if (activeMoveHandlerRef.current && map) {
      map.off("moveend", activeMoveHandlerRef.current);
    }
    activeMoveHandlerRef.current = null;
  }, []);

  const cancelSkyDive = useCallback(() => {
    clearMoveWait();
    if (!skyDiveActiveRef.current && skyDiveDoneRef.current) {
      enableTerrain();
      return;
    }
    skyDiveTimersRef.current.forEach(clearTimeout);
    skyDiveTimersRef.current = [];
    skyDiveActiveRef.current = false;
    skyDiveDoneRef.current = true;
    setSkyDiving(false);
    setSkyDone(true);
    applyMapPadding();
    enableTerrain();
  }, [applyMapPadding, clearMoveWait, enableTerrain]);

  const startSkyDiveIntro = useCallback(
    (force = false) => {
      const map = mapRef.current;
      if (!map) return;
      if (skyDiveActiveRef.current || (skyDiveDoneRef.current && !force)) {
        return;
      }

      clearMoveWait();
      skyDiveTimersRef.current.forEach(clearTimeout);
      skyDiveTimersRef.current = [];
      skyDiveActiveRef.current = true;
      skyDiveDoneRef.current = false;
      skyDiveStageRef.current = 0;

      setSkyDiving(true);
      setSkyDone(false);
      setSkyStage(0);
      setSkyFlash("none");
      map.setPadding({ top: 0, bottom: 0, left: 0, right: 0 });

      const { activePreset: ap, tiltOn: tOn } = latestRef.current;
      const target: [number, number] = [ap.center.lon, ap.center.lat];
      const easeInOutCubic = (t: number) =>
        t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

      if (force) {
        try {
          map.setTerrain(null);
          terrainEnabledRef.current = false;
        } catch {
          /* ignore */
        }
        try {
          map.jumpTo({
            center: target,
            zoom: 5.2,
            pitch: 0,
            bearing: 0,
            padding: { top: 0, bottom: 0, left: 0, right: 0 },
          });
        } catch {
          /* ignore */
        }
      }

      const startTimer = setTimeout(() => {
        if (!skyDiveActiveRef.current || !mapRef.current) return;
        const diveMs = 2250;
        const targetPad = computeDockedPadding();

        mapRef.current.easeTo({
          center: target,
          zoom: ap.overviewZoom,
          pitch: tOn ? ap.pitch : 0,
          bearing: ap.bearing,
          padding: targetPad,
          duration: diveMs,
          easing: easeInOutCubic,
          essential: true,
        });

        setIsRegionalView(false);
        setCanZoomDetail(ap.overviewZoom < ap.focusZoom - 0.35);

        let fired = false;
        let fallbackId: ReturnType<typeof setTimeout> | null = null;
        const done = () => {
          if (fired) return;
          fired = true;
          if (fallbackId) clearTimeout(fallbackId);
          clearMoveWait();
          if (!skyDiveActiveRef.current) return;

          skyDiveActiveRef.current = false;
          skyDiveDoneRef.current = true;
          setSkyDone(true);
          setSkyDiving(false);
          applyMapPadding();

          const terrTimer = setTimeout(enableTerrain, 220);
          skyDiveTimersRef.current.push(terrTimer);
        };

        activeMoveHandlerRef.current = done;
        mapRef.current.once("moveend", done);
        fallbackId = setTimeout(done, diveMs + 140);
        skyDiveTimersRef.current.push(fallbackId);
      }, force ? 60 : 140);

      skyDiveTimersRef.current.push(startTimer);
    },
    [applyMapPadding, clearMoveWait, computeDockedPadding, enableTerrain]
  );

  // Measure DEM for active preset
  const refreshDemForPreset = useCallback(async (preset: Preset) => {
    const res = await measureFromDem(preset);
    if (res) {
      setLiveDemMap((prev) => ({
        ...prev,
        [preset.id]: res,
      }));
    }
  }, []);

  useEffect(() => {
    refreshDemForPreset(activePreset);
  }, [activePreset, refreshDemForPreset]);

  // Keep GeoJSON polygon, marker position, and pin label synced
  useEffect(() => {
    const map = mapRef.current;
    const locP = pLoc(activePreset, loc);
    const ha = ringAreaHa(activePreset.ring).toFixed(1);
    if (pinLabelRef.current) {
      pinLabelRef.current.textContent = `${locP.short} · ${ha} ${loc.uHa}`;
    }
    if (markerRef.current) {
      markerRef.current.setLngLat([
        activePreset.center.lon,
        activePreset.center.lat,
      ]);
    }
    if (map) {
      const fieldSrc = map.getSource("field") as
        | maplibregl.GeoJSONSource
        | undefined;
      if (fieldSrc?.setData) {
        fieldSrc.setData(presetFeature(activePreset));
      }
      const otherSrc = map.getSource("presets-other") as
        | maplibregl.GeoJSONSource
        | undefined;
      if (otherSrc?.setData) {
        otherSrc.setData(allPresetsFC(presets, activePreset.id));
      }
    }
    window.__field = activePreset.center;
  }, [activePreset, presets, loc]);

  // Keep parcel fill/line/glow color synced with erosion score
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer("field-fill")) return;
    const erosion = selectedResult.res.erosion;
    const col =
      erosion >= 0.37 ? "#4ade80" : erosion >= 0.3 ? "#eab34d" : "#f06449";
    try {
      map.setPaintProperty("field-fill", "fill-color", col);
      map.setPaintProperty("field-line", "line-color", col);
      map.setPaintProperty("field-glow", "line-color", col);
    } catch {
      /* ignore before layer ready */
    }
  }, [selectedResult]);

  // Apply GIBS tiles whenever monthIndex changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const when = MONTHS[monthIndex] || MONTHS[0];
    if (tileDebounceRef.current) clearTimeout(tileDebounceRef.current);
    tileDebounceRef.current = setTimeout(() => {
      GIBS_KEYS.forEach((key) => {
        if (map.getLayer(key)) {
          map.setPaintProperty(key, "raster-fade-duration", 120);
        }
        const src = map.getSource("src-" + key) as
          | maplibregl.RasterTileSource
          | undefined;
        if (src && typeof src.setTiles === "function") {
          try {
            src.setTiles([gibsUrl(key, dateStrFor(key, when))]);
          } catch {
            /* ignore */
          }
        }
      });
    }, 65);
  }, [monthIndex]);

  // Apply raster visibility and opacity whenever toggles change
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    GIBS_KEYS.forEach((key) => {
      if (!map.getLayer(key)) return;
      const on = toggles[key];
      map.setLayoutProperty(key, "visibility", on ? "visible" : "none");
      if (key === "truecolor") {
        map.setPaintProperty(
          key,
          "raster-opacity",
          on ? truecolorOpacityForZoom(map.getZoom()) : 0
        );
      } else {
        map.setPaintProperty(
          key,
          "raster-opacity",
          on ? (key === "ndvi" ? 0.54 : 0.62) : 0
        );
      }
    });
  }, [toggles]);

  // Preset Selection handler (used by TopToolbar & map click)
  const handleSelectPreset = useCallback(
    (id: PresetId, fly = true) => {
      const next = presets.find((p) => p.id === id);
      if (!next) return;
      setPresetId(next.id);
      if (fly && mapRef.current) {
        cancelSkyDive();
        const pitchOnNow = latestRef.current.tiltOn;
        mapRef.current.flyTo({
          center: [next.center.lon, next.center.lat],
          zoom: next.overviewZoom,
          pitch: pitchOnNow ? next.pitch : 0,
          bearing: next.bearing,
          curve: 1.25,
          duration: 1550,
          essential: true,
        });
        setIsRegionalView(false);
        setCanZoomDetail(next.overviewZoom < next.focusZoom - 0.35);
      }
    },
    [cancelSkyDive, presets]
  );

  const selectPresetRef = useRef(handleSelectPreset);
  selectPresetRef.current = handleSelectPreset;

  // Layer toggle handler
  const handleToggleLayer = useCallback(
    (key: LayerKey, forceOn?: boolean) => {
      setToggles((prev) => {
        const nextOn = forceOn !== undefined ? forceOn : !prev[key];
        const next = { ...prev, [key]: nextOn };
        if (key === "truecolor" && nextOn) next.ndvi = false;
        if (key === "ndvi" && nextOn) next.truecolor = false;

        if (nextOn && key !== "truecolor") {
          setActiveLegendKey(key);
        } else if (!nextOn && key !== "truecolor") {
          const fallback = LEGEND_ORDER.find(
            (k) => k !== key && next[k]
          );
          setActiveLegendKey(fallback ?? null);
        }

        if (
          key === "truecolor" &&
          nextOn &&
          mapRef.current &&
          mapRef.current.getZoom() > 9.4
        ) {
          cancelSkyDive();
          const ap = latestRef.current.activePreset;
          mapRef.current.flyTo({
            center: [ap.center.lon, ap.center.lat],
            zoom: 8.6,
            pitch: 0,
            bearing: 0,
            duration: 1100,
          });
          setIsRegionalView(true);
          setCanZoomDetail(true);
        }
        return next;
      });
    },
    [cancelSkyDive]
  );

  // Initialize single MapLibre GL v5 instance
  useEffect(() => {
    const container = mapContainerRef.current;
    if (!container) return;

    const skipSkyIntro =
      window.location.hash === "#still" ||
      window.location.search.includes("demo=1") ||
      (typeof window.matchMedia === "function" &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches);

    if (!skipSkyIntro) {
      skyDiveDoneRef.current = false;
      setSkyDone(false);
      setSkyDiving(true);
    }

    const startPreset = latestRef.current.activePreset;
    window.__boot = { start: performance.now(), idle: null };

    let map: maplibregl.Map | null = null;
    let bootRemoved = false;
    let bootFallbackTimer: ReturnType<typeof setTimeout> | null = null;
    let bootRemoveTimer: ReturnType<typeof setTimeout> | null = null;

    const dismissBoot = (note?: string) => {
      if (bootRemoved) return;
      bootRemoved = true;
      if (note) setBootNote(note);
      setBootFadingOut(true);
      bootRemoveTimer = setTimeout(() => setBootVisible(false), 360);
      if (!skipSkyIntro) startSkyDiveIntro();
    };

    try {
      map = new maplibregl.Map({
        container,
        style: {
          version: 8,
          sources: {
            base: {
              type: "raster",
              tiles: [
                "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
              ],
              tileSize: 256,
              maxzoom: 17,
              attribution: "Esri, Maxar, Earthstar Geographics",
            },
            dem: {
              type: "raster-dem",
              tiles: [
                "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png",
              ],
              encoding: "terrarium",
              tileSize: 256,
              maxzoom: 15,
            },
          },
          layers: [
            {
              id: "bg",
              type: "background",
              paint: { "background-color": "#0a1310" },
            },
            {
              id: "base",
              type: "raster",
              source: "base",
              paint: {
                "raster-opacity": 1,
                "raster-fade-duration": 140,
                "raster-saturation": -0.06,
                "raster-contrast": 0.04,
              },
            },
          ],
        },
        center: [startPreset.center.lon, startPreset.center.lat],
        zoom: skipSkyIntro ? startPreset.overviewZoom : 5.2,
        pitch: 0,
        bearing: skipSkyIntro ? startPreset.bearing : 0,
        maxPitch: 70,
        canvasContextAttributes: { antialias: false },
        fadeDuration: 120,
        renderWorldCopies: false,
        attributionControl: false,
      });

      mapRef.current = map;
      window.__map = map;
      window.__field = startPreset.center;

      map.once("idle", () => {
        if (window.__boot) window.__boot.idle = performance.now();
        dismissBoot();
      });

      map.once("load", () => {
        if (!map) return;
        setTimeout(() => dismissBoot(), 600);
        if (skipSkyIntro) enableTerrain();

        // Field layers
        map.addSource("presets-other", {
          type: "geojson",
          data: allPresetsFC(latestRef.current.presets, latestRef.current.activePreset.id),
        });
        map.addLayer({
          id: "presets-fill",
          type: "fill",
          source: "presets-other",
          paint: { "fill-color": "#94a3b8", "fill-opacity": 0.08 },
        });
        map.addLayer({
          id: "presets-line",
          type: "line",
          source: "presets-other",
          paint: {
            "line-color": "rgba(244,247,244,0.55)",
            "line-width": 1.3,
            "line-dasharray": [3, 2],
          },
        });

        map.addSource("field", {
          type: "geojson",
          data: presetFeature(latestRef.current.activePreset),
        });
        map.addLayer({
          id: "field-fill",
          type: "fill",
          source: "field",
          paint: { "fill-color": "#eab34d", "fill-opacity": 0.16 },
        });
        map.addLayer({
          id: "field-glow",
          type: "line",
          source: "field",
          paint: {
            "line-color": "#eab34d",
            "line-width": 9,
            "line-blur": 10,
            "line-opacity": 0.42,
          },
        });
        map.addLayer({
          id: "field-line",
          type: "line",
          source: "field",
          paint: {
            "line-color": "#eab34d",
            "line-width": 2.1,
            "line-opacity": 0.98,
          },
        });

        // GIBS raster layers inserted below presets-line
        const initWhen = MONTHS[latestRef.current.monthIndex] || MONTHS[0];
        GIBS_KEYS.forEach((key) => {
          if (!map) return;
          const L = LAYERS[key];
          const srcId = "src-" + key;
          if (!map.getSource(srcId)) {
            map.addSource(srcId, {
              type: "raster",
              tiles: [gibsUrl(key, dateStrFor(key, initWhen))],
              tileSize: 256,
              maxzoom: L.maxzoom,
              attribution: "GIBS / " + L.layer,
            });
          }
          if (!map.getLayer(key)) {
            map.addLayer(
              {
                id: key,
                type: "raster",
                source: srcId,
                layout: { visibility: "none" },
                paint: {
                  "raster-opacity": 0,
                  "raster-fade-duration": 120,
                  "raster-resampling": "linear",
                },
              },
              "presets-line"
            );
          }
        });

        // Hover & click other presets
        map.on("mouseenter", "presets-fill", () => {
          if (map) map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", "presets-fill", () => {
          if (map) map.getCanvas().style.cursor = "";
        });
        map.on("click", "presets-fill", (e) => {
          const feat = e.features?.[0];
          const pid = feat?.properties?.id as PresetId | undefined;
          if (pid) {
            (e.originalEvent as Event & { _handledPresetClick?: boolean })._handledPresetClick =
              true;
            selectPresetRef.current(pid, true);
          }
        });

        // Pulsing pin marker
        const pinEl = document.createElement("div");
        pinEl.className = "pin";
        pinEl.dir = "ltr";
        const dotEl = document.createElement("span");
        dotEl.className = "pin-dot";
        const lblEl = document.createElement("span");
        lblEl.className = "pin-lbl";
        lblEl.id = "pin-lbl";
        lblEl.dir = "auto";
        const curLoc = latestRef.current.loc;
        const curP = pLoc(latestRef.current.activePreset, curLoc);
        const curHa = ringAreaHa(latestRef.current.activePreset.ring).toFixed(
          1
        );
        lblEl.textContent = `${curP.short} · ${curHa} ${curLoc.uHa}`;
        pinLabelRef.current = lblEl;
        pinEl.append(dotEl, lblEl);

        markerRef.current = new maplibregl.Marker({
          element: pinEl,
          anchor: "left",
        })
          .setLngLat([
            latestRef.current.activePreset.center.lon,
            latestRef.current.activePreset.center.lat,
          ])
          .addTo(map);

        applyMapPadding();
      });

      map.on("dragstart", cancelSkyDive);
      map.on("wheel", cancelSkyDive);
      map.on("mousedown", cancelSkyDive);
      map.on("touchstart", cancelSkyDive);

      map.on("zoom", () => {
        if (!map) return;
        const z = map.getZoom();
        if (latestRef.current.toggles.truecolor && map.getLayer("truecolor")) {
          map.setPaintProperty(
            "truecolor",
            "raster-opacity",
            truecolorOpacityForZoom(z)
          );
        }
        if (skyDiveActiveRef.current) {
          const lockZ = latestRef.current.activePreset.overviewZoom - 1.1;
          let nextStep = 0;
          if (z >= lockZ) nextStep = 3;
          else if (z >= 10.4) nextStep = 2;
          else if (z >= 7.2) nextStep = 1;
          if (nextStep > skyDiveStageRef.current) {
            skyDiveStageRef.current = nextStep;
            setSkyStage(nextStep);
            if (nextStep === 3) setSkyFlash("lock");
          }
        }
        setIsRegionalView(z < 12.2);
        setCanZoomDetail(z < latestRef.current.activePreset.focusZoom - 0.35);
      });

      map.on("click", (e) => {
        const orig = e.originalEvent as Event & { _handledPresetClick?: boolean };
        if (orig?._handledPresetClick || !map) return;
        let h: number | null = null;
        try {
          h = map.queryTerrainElevation
            ? map.queryTerrainElevation(e.lngLat)
            : null;
        } catch {
          h = null;
        }
        const curLoc = latestRef.current.loc;
        new maplibregl.Popup({ closeButton: false, offset: 12 })
          .setLngLat(e.lngLat)
          .setHTML(
            `<div style="color:rgba(205,220,212,0.6);font-size:10px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase">${curLoc.probeTitle}</div>` +
              `<div dir="ltr" style="margin-top:3px;font-family:var(--font-mono);font-size:11.5px">${e.lngLat.lat.toFixed(
                4
              )}° N, ${e.lngLat.lng.toFixed(4)}° E</div>` +
              `<div style="margin-top:2px;color:#eab34d;font-weight:600">${
                h != null
                  ? curLoc.probeElev(Math.round(h))
                  : curLoc.probeLoading
              }</div>`
          )
          .addTo(map);
      });

      map.on("error", (e) => {
        if (warnedRef.current) return;
        const msg = String(
          (e as { error?: { message?: string } })?.error?.message || ""
        );
        if (/sprite|glyphs|style/i.test(msg)) return;
        warnedRef.current = true;
        setBootNote(latestRef.current.loc.bootSlowNet);
      });
    } catch {
      dismissBoot();
    }

    if (skipSkyIntro) {
      dismissBoot();
    } else {
      bootFallbackTimer = setTimeout(
        () => dismissBoot(latestRef.current.loc.bootSlowTiles),
        3500
      );
    }

    window.__engine = {
      evaluate,
      STRATS,
      CROPS,
      PRESETS: latestRef.current.presets,
      SOILS,
      I18N,
      replayIntro: () => startSkyDiveIntro(true),
      cancelSkyDive,
      openGuide: () => setGuideOpen(true),
      closeGuide: () => setGuideOpen(false),
    };

    const timersRef = skyDiveTimersRef.current;

    return () => {
      if (bootFallbackTimer) clearTimeout(bootFallbackTimer);
      if (bootRemoveTimer) clearTimeout(bootRemoveTimer);
      if (tileDebounceRef.current) clearTimeout(tileDebounceRef.current);
      timersRef.forEach(clearTimeout);
      if (markerRef.current) {
        markerRef.current.remove();
        markerRef.current = null;
      }
      if (map) {
        map.remove();
      }
      mapRef.current = null;
    };
  }, [applyMapPadding, cancelSkyDive, enableTerrain, startSkyDiveIntro]);

  // Play interval
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      setMonthIndex((idx) => (idx + 1) % MONTHS.length);
    }, 800);
    return () => clearInterval(id);
  }, [playing]);

  // Global keyboard shortcuts (Space play/pause, Escape closes modal/returns to field)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const tag = document.activeElement?.tagName ?? "";
      if (
        e.code === "Space" &&
        !/INPUT|BUTTON|TEXTAREA|SELECT/.test(tag)
      ) {
        e.preventDefault();
        setPlaying((p) => !p);
      }
      if (e.code === "Escape") {
        if (guideOpen) {
          setGuideOpen(false);
          return;
        }
        if (inspectorTab === "audit" || inspectorTab === "compare") {
          setInspectorTab("field");
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [guideOpen, inspectorTab]);

  // Focus & 3D Tilt handlers
  const handleToggleFocus = useCallback(() => {
    cancelSkyDive();
    const map = mapRef.current;
    if (!map) return;
    const isRegionalNow = map.getZoom() < 12.2;
    if (isRegionalNow) {
      map.flyTo({
        center: [activePreset.center.lon, activePreset.center.lat],
        zoom: activePreset.focusZoom,
        pitch: tiltOn ? activePreset.pitch : 0,
        bearing: activePreset.bearing,
        duration: 1450,
        essential: true,
      });
      setIsRegionalView(false);
      setCanZoomDetail(false);
    } else {
      map.flyTo({
        center: REGION_HOME.center,
        zoom: REGION_HOME.zoom,
        pitch: tiltOn ? REGION_HOME.pitch : 0,
        bearing: REGION_HOME.bearing,
        duration: 1450,
        essential: true,
      });
      setIsRegionalView(true);
      setCanZoomDetail(true);
    }
  }, [activePreset, cancelSkyDive, tiltOn]);

  const handleFocusCardAction = useCallback(() => {
    cancelSkyDive();
    const map = mapRef.current;
    if (!map) {
      handleToggleFocus();
      return;
    }
    if (map.getZoom() < activePreset.focusZoom - 0.35) {
      map.flyTo({
        center: [activePreset.center.lon, activePreset.center.lat],
        zoom: activePreset.focusZoom,
        pitch: tiltOn ? activePreset.pitch : 0,
        bearing: activePreset.bearing,
        duration: 1350,
        essential: true,
      });
      setIsRegionalView(false);
      setCanZoomDetail(false);
    } else {
      handleToggleFocus();
    }
  }, [activePreset, cancelSkyDive, handleToggleFocus, tiltOn]);

  const handleToggleTilt = useCallback(() => {
    cancelSkyDive();
    const next = !tiltOn;
    setTiltOn(next);
    mapRef.current?.easeTo({
      pitch: next ? activePreset.pitch : 0,
      bearing: next ? activePreset.bearing : 0,
      duration: 750,
      essential: true,
    });
  }, [activePreset, cancelSkyDive, tiltOn]);

  const handleSelectLang = useCallback(
    (nextLang: Lang) => {
      if (nextLang === protoState.lang) return;
      setProtoState((prev) => ({ ...prev, lang: nextLang }));
      setStoreLang(nextLang);
      try {
        localStorage.setItem("fieldshift.lang", nextLang);
        localStorage.setItem("ard.lang", nextLang);
      } catch {
        /* ignore */
      }
    },
    [protoState.lang, setStoreLang]
  );

  const handleSelectInspectorTab = useCallback((tab: InspectorTab) => {
    setInspectorTab(tab);
    if (tab !== "field") {
      setInspCollapsed(false);
    }
  }, []);

  const handleSelectStrategy = useCallback(
    (id: StratId, openAudit = true) => {
      setProtoState((prev) => ({ ...prev, selected: id }));
      if (openAudit) {
        handleSelectInspectorTab("audit");
        if (typeof window !== "undefined" && window.innerWidth <= 900) {
          setMobPane("audit");
        }
      }
    },
    [handleSelectInspectorTab]
  );

  const handleSelectMobilePane = useCallback(
    (mode: MobilePane) => {
      setMobPane(mode);
      if (mode === "field" || mode === "compare" || mode === "audit") {
        handleSelectInspectorTab(mode);
      }
    },
    [handleSelectInspectorTab]
  );

  const handleCyclePreviewLayer = useCallback(() => {
    const activeKey = (
      ["ndvi", "rain", "sm", "lst", "truecolor"] as LayerKey[]
    ).find((k) => toggles[k]);
    if (!activeKey) {
      handleToggleLayer("ndvi", true);
      return;
    }
    const idx = PREVIEW_ORDER.indexOf(activeKey as LegendKey);
    const nextKey = PREVIEW_ORDER[(idx + 1) % PREVIEW_ORDER.length];
    if (nextKey !== activeKey) handleToggleLayer(activeKey, false);
    handleToggleLayer(nextKey, true);
  }, [handleToggleLayer, toggles]);

  const activeLegend = useMemo(() => {
    const k = activeLegendKey && toggles[activeLegendKey]
      ? activeLegendKey
      : LEGEND_ORDER.find((key) => toggles[key]);
    return k ? loc.legends[k] : null;
  }, [activeLegendKey, toggles, loc.legends]);

  const skyAltLabel = useMemo(() => {
    const ha = ringAreaHa(activePreset.ring).toFixed(1);
    const place = pLoc(activePreset, loc).short;
    const labels = loc.skyAlts(ha, place);
    return labels[skyStage] || labels[0];
  }, [activePreset, loc, skyStage]);

  const rootClassName = [
    "fs-proto-root",
    skyDiving ? "sky-diving" : "",
    protoState.plainMode ? "plain-mode" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={rootClassName}
      data-theme={resolvedTheme}
      data-testid="fieldshift-prototype-root"
    >
      <div ref={mapContainerRef} id="map" className="fs-map" />
      <div className="vignette" />

      <SkyDiveOverlay
        done={skyDone}
        stage={skyStage}
        flashKind={skyFlash}
        altLabel={skyAltLabel}
      />

      <BootSplash
        visible={bootVisible}
        fadingOut={bootFadingOut}
        note={bootNote}
        loc={loc}
      />

      <TopToolbar
        presets={presets}
        activePreset={activePreset}
        lang={protoState.lang}
        loc={loc}
        toggles={toggles}
        isRegionalView={isRegionalView}
        tiltOn={tiltOn}
        zenMode={zenMode}
        plainMode={protoState.plainMode}
        backLabel={backLabel}
        editBordersLabel={editBordersLabel}
        onBackToDashboard={onBackToDashboard}
        onEditBorders={onEditBorders ? () => onEditBorders(activePreset.id) : undefined}
        onSelectPreset={(id) => handleSelectPreset(id, true)}
        onSelectLang={handleSelectLang}
        onToggleLayer={(key) => handleToggleLayer(key)}
        onToggleFocus={handleToggleFocus}
        onToggleTilt={handleToggleTilt}
        onToggleZen={() => setZenMode((z) => !z)}
        onTogglePlain={() =>
          setProtoState((p) => ({ ...p, plainMode: !p.plainMode }))
        }
        onOpenGuide={() => setGuideOpen(true)}
      />

      <LegendCapsule visible={Boolean(activeLegend)} legend={activeLegend} loc={loc} />

      <RotationLabWindow
        loc={loc}
        priority={protoState.priority}
        selectedStrat={protoState.selected}
        irrigated={protoState.irrigated}
        lowInput={protoState.lowInput}
        rain={protoState.rain}
        temp={protoState.temp}
        collapsed={labCollapsed}
        zenMode={zenMode}
        mobOpen={mobPane === "lab"}
        results={evalResults}
        panelRef={labRef}
        onToggleCollapse={() => setLabCollapsed((c) => !c)}
        onChangePriority={(priority: Priority) =>
          setProtoState((p) => ({ ...p, priority }))
        }
        onToggleIrrigated={() =>
          setProtoState((p) => ({ ...p, irrigated: !p.irrigated }))
        }
        onToggleLowInput={() =>
          setProtoState((p) => ({ ...p, lowInput: !p.lowInput }))
        }
        onSelectStrategy={(id) => handleSelectStrategy(id, true)}
        onSelectScenarioPreset={(rain, temp) =>
          setProtoState((p) => ({ ...p, rain, temp }))
        }
        onChangeRain={(rain) => setProtoState((p) => ({ ...p, rain }))}
        onChangeTemp={(temp) => setProtoState((p) => ({ ...p, temp }))}
      />

      <FieldInspectorWindow
        loc={loc}
        lang={protoState.lang}
        rawPreset={activePreset}
        liveElev={liveElev}
        liveSlope={liveSlope}
        activeTab={inspectorTab}
        selectedStrat={protoState.selected}
        irrigated={protoState.irrigated}
        lowInput={protoState.lowInput}
        rain={protoState.rain}
        temp={protoState.temp}
        monthIndex={monthIndex}
        canZoomDetail={canZoomDetail}
        collapsed={inspCollapsed}
        zenMode={zenMode}
        mobOpen={
          mobPane === "field" || mobPane === "compare" || mobPane === "audit"
        }
        results={evalResults}
        panelRef={inspRef}
        onSelectTab={handleSelectInspectorTab}
        onToggleCollapse={() => setInspCollapsed((c) => !c)}
        onFocusCardAction={handleFocusCardAction}
        onSelectStrategy={handleSelectStrategy}
      />

      <TimelineCapsule
        loc={loc}
        clim={CLIMATES[activePreset.climate]}
        monthIndex={monthIndex}
        playing={playing}
        toggles={toggles}
        onTogglePlay={() => setPlaying((p) => !p)}
        onScrub={(idx) => {
          setPlaying(false);
          setMonthIndex(idx);
        }}
        onScrubCommit={(idx) => setMonthIndex(idx)}
        onSelectMonthFromSpark={(mNum) => {
          setPlaying(false);
          const idx = MONTHS.findIndex((x) => x.m === mNum);
          if (idx >= 0) setMonthIndex(idx);
        }}
        onCyclePreviewLayer={handleCyclePreviewLayer}
      />

      <MobileDock
        activePane={mobPane}
        loc={loc}
        onSelectPane={handleSelectMobilePane}
      />

      <GuideModal
        open={guideOpen}
        loc={loc}
        rawPreset={activePreset}
        liveElev={liveElev}
        state={protoState}
        onClose={() => setGuideOpen(false)}
      />
    </div>
  );
}

