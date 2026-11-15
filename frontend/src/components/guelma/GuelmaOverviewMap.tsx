"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  CaretLeft,
  CaretRight,
  CornersOut,
  Crosshair,
  Info,
  Minus,
  PencilLine,
  Plus,
  Stack,
} from "@phosphor-icons/react";
import {
  closeRing,
  computePolygonBbox,
  extractRingFromBoundary,
  GUELMA_DEFAULT_CENTER,
  GUELMA_FALLBACK_BOUNDARY,
} from "@/lib/geo/guelma";
import { useResolvedTheme } from "@/app/providers";
import { canUseWebgl } from "@/lib/geo/webgl";
import type { FieldDetailPublic } from "@/lib/schemas";

export interface GuelmaOverviewMapHudLabels {
  fitExtent: string;
  zoomIn: string;
  zoomOut: string;
  activeParcelCount: string;
  selectedLabel: string;
  registeredLabel: string;
  layersLabel?: string;
  drawParcelLabel?: string;
  prevFieldLabel?: string;
  nextFieldLabel?: string;
  communesChip?: string;
  openInspectorLabel?: string;
}

interface GuelmaOverviewMapProps {
  fields: FieldDetailPublic[];
  selectedFieldKey: string | null;
  onSelectField: (farmId: string, fieldId: string) => void;
  onOpenInspect?: (farmId: string, fieldId: string) => void;
  onStartAddFarm?: () => void;
  title?: string;
  subtitle?: string;
  hudLabels?: GuelmaOverviewMapHudLabels;
  inspectorOpen?: boolean;
  onReopenInspector?: () => void;
  children?: React.ReactNode;
}

const GUELMA_SVG_BOUNDS = {
  minLon: 6.94,
  maxLon: 7.94,
  minLat: 36.02,
  maxLat: 36.7,
};

function projectToSvg(lon: number, lat: number, w = 640, h = 360): [number, number] {
  const x =
    ((lon - GUELMA_SVG_BOUNDS.minLon) /
      (GUELMA_SVG_BOUNDS.maxLon - GUELMA_SVG_BOUNDS.minLon)) *
    w;
  const y =
    ((GUELMA_SVG_BOUNDS.maxLat - lat) /
      (GUELMA_SVG_BOUNDS.maxLat - GUELMA_SVG_BOUNDS.minLat)) *
    h;
  return [Number(x.toFixed(1)), Number(y.toFixed(1))];
}

export function GuelmaOverviewMap({
  fields,
  selectedFieldKey,
  onSelectField,
  onStartAddFarm,
  hudLabels,
  inspectorOpen = true,
  onReopenInspector,
  children,
}: GuelmaOverviewMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapFrameRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [webglFailed, setWebglFailed] = useState(false);
  const [highContrastLayers, setHighContrastLayers] = useState(false);
  const [calloutPin, setCalloutPin] = useState<{ x: number; y: number } | null>(null);
  const resolvedTheme = useResolvedTheme();
  const isDarkTheme = resolvedTheme === "dark";

  const selectedIndex = useMemo(() => {
    if (!selectedFieldKey || fields.length === 0) return -1;
    return fields.findIndex((f) => `${f.farm_id}::${f.field_id}` === selectedFieldKey);
  }, [fields, selectedFieldKey]);

  const selectedField =
    selectedIndex >= 0 ? fields[selectedIndex] : fields.length > 0 ? fields[0] : null;

  const updateCalloutPin = useCallback(() => {
    const frame = mapFrameRef.current;
    if (!frame || !selectedField || !inspectorOpen) {
      setCalloutPin(null);
      return;
    }
    const rect = frame.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;

    const map = mapRef.current;
    if (map && !webglFailed) {
      try {
        const pt = map.project([selectedField.location.longitude, selectedField.location.latitude]);
        const clampedX = Math.max(40, Math.min(rect.width - 40, pt.x));
        const clampedY = Math.max(64, Math.min(rect.height - 64, pt.y));
        setCalloutPin({ x: clampedX, y: clampedY });
        return;
      } catch {
        /* fallback below */
      }
    }

    const [sx, sy] = projectToSvg(
      selectedField.location.longitude,
      selectedField.location.latitude,
      640,
      360
    );
    setCalloutPin({
      x: (sx / 640) * rect.width,
      y: (sy / 360) * rect.height,
    });
  }, [selectedField, inspectorOpen, webglFailed]);

  const handleZoomIn = () => {
    mapRef.current?.zoomIn({ duration: 220 });
  };

  const handleZoomOut = () => {
    mapRef.current?.zoomOut({ duration: 220 });
  };

  const handleFitExtent = () => {
    const map = mapRef.current;
    if (!map) return;
    if (fields.length === 0) {
      map.flyTo({ center: GUELMA_DEFAULT_CENTER, zoom: 9.2, duration: 320 });
      return;
    }
    const bounds = new maplibregl.LngLatBounds();
    fields.forEach((f) => {
      const ring = extractRingFromBoundary(f.location.boundary);
      if (ring && ring.length >= 3) {
        ring.forEach(([lng, lat]) => bounds.extend([lng, lat]));
      } else {
        bounds.extend([f.location.longitude, f.location.latitude]);
      }
    });
    if (!bounds.isEmpty()) {
      map.fitBounds(bounds, { padding: 64, maxZoom: 14, duration: 320 });
    }
  };

  const handleCenterSelected = () => {
    const map = mapRef.current;
    if (!map) return;
    if (selectedField) {
      map.flyTo({
        center: [selectedField.location.longitude, selectedField.location.latitude],
        zoom: 13.8,
        duration: 420,
      });
    } else {
      handleFitExtent();
    }
  };

  const handleStepField = (delta: number) => {
    if (fields.length < 2) return;
    const base = selectedIndex >= 0 ? selectedIndex : 0;
    const nextIdx = (base + delta + fields.length) % fields.length;
    const target = fields[nextIdx];
    if (target) {
      onSelectField(target.farm_id, target.field_id);
    }
  };

  const fieldsRef = useRef(fields);
  fieldsRef.current = fields;
  const onSelectRef = useRef(onSelectField);
  onSelectRef.current = onSelectField;

  const fieldsGeoJson = useMemo(() => {
    const features = fields.map((f) => {
      const key = `${f.farm_id}::${f.field_id}`;
      const extracted = extractRingFromBoundary(f.location.boundary);
      const ring =
        extracted.length >= 3
          ? closeRing(extracted)
          : closeRing([
              [f.location.longitude - 0.001, f.location.latitude - 0.0008],
              [f.location.longitude + 0.001, f.location.latitude - 0.0008],
              [f.location.longitude + 0.001, f.location.latitude + 0.0008],
              [f.location.longitude - 0.001, f.location.latitude + 0.0008],
            ]);
      return {
        type: "Feature" as const,
        properties: {
          fieldKey: key,
          farmId: f.farm_id,
          fieldId: f.field_id,
          fieldName: f.field_name,
          area: `${f.area_hectares.toFixed(1)} ha`,
          selected: key === selectedFieldKey ? 1 : 0,
        },
        geometry: {
          type: "Polygon" as const,
          coordinates: [ring],
        },
      };
    });
    return { type: "FeatureCollection" as const, features };
  }, [fields, selectedFieldKey]);

  const pointsGeoJson = useMemo(() => {
    return {
      type: "FeatureCollection" as const,
      features: fields.map((f) => {
        const key = `${f.farm_id}::${f.field_id}`;
        return {
          type: "Feature" as const,
          properties: {
            fieldKey: key,
            farmId: f.farm_id,
            fieldId: f.field_id,
            fieldName: f.field_name,
            area: `${f.area_hectares.toFixed(1)} ha`,
            selected: key === selectedFieldKey ? 1 : 0,
          },
          geometry: {
            type: "Point" as const,
            coordinates: [f.location.longitude, f.location.latitude],
          },
        };
      }),
    };
  }, [fields, selectedFieldKey]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || webglFailed) return;
    if (!canUseWebgl()) {
      setWebglFailed(true);
      return;
    }

    let map: maplibregl.Map | null = null;
    try {
      const style: maplibregl.StyleSpecification = {
        version: 8,
        sources: {
          esri: {
            type: "raster",
            tiles: [
              "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            ],
            tileSize: 256,
            maxzoom: 19,
          },
        },
        layers: [{ id: "esri-sat", type: "raster", source: "esri" }],
      };

      map = new maplibregl.Map({
        container: el,
        style,
        center: GUELMA_DEFAULT_CENTER,
        zoom: 9.2,
        pitch: 0,
        attributionControl: false,
      });
      mapRef.current = map;

      map.on("load", () => {
        if (!map) return;
        map.addSource("guelma-boundary", {
          type: "geojson",
          data: GUELMA_FALLBACK_BOUNDARY as unknown as GeoJSON.Feature,
        });
        map.addLayer({
          id: "guelma-outline",
          type: "line",
          source: "guelma-boundary",
          paint: {
            "line-color": "#4ADE80",
            "line-width": 2.2,
            "line-dasharray": [4, 3],
            "line-opacity": 0.85,
          },
        });

        map.addSource("workspace-fields", {
          type: "geojson",
          data: fieldsGeoJson,
        });
        map.addLayer({
          id: "workspace-fields-fill",
          type: "fill",
          source: "workspace-fields",
          paint: {
            "fill-color": ["case", ["==", ["get", "selected"], 1], "#4ADE80", "#EAB34D"],
            "fill-opacity": ["case", ["==", ["get", "selected"], 1], 0.35, 0.20],
          },
        });
        map.addLayer({
          id: "workspace-fields-line",
          type: "line",
          source: "workspace-fields",
          paint: {
            "line-color": ["case", ["==", ["get", "selected"], 1], "#FFFFFF", "#EAB34D"],
            "line-width": ["case", ["==", ["get", "selected"], 1], 2.5, 1.8],
          },
        });

        map.addSource("workspace-points", {
          type: "geojson",
          data: pointsGeoJson,
        });
        map.addLayer({
          id: "workspace-points-dot",
          type: "circle",
          source: "workspace-points",
          paint: {
            "circle-radius": ["case", ["==", ["get", "selected"], 1], 8, 6],
            "circle-color": ["case", ["==", ["get", "selected"], 1], "#4ADE80", "#EAB34D"],
            "circle-stroke-width": 2,
            "circle-stroke-color": "#FFFFFF",
          },
        });

        map.on("click", "workspace-fields-fill", (e) => {
          const props = e.features?.[0]?.properties as
            | { farmId?: string; fieldId?: string }
            | undefined;
          if (props?.farmId && props?.fieldId) {
            onSelectRef.current(props.farmId, props.fieldId);
          }
        });
        map.on("click", "workspace-points-dot", (e) => {
          const props = e.features?.[0]?.properties as
            | { farmId?: string; fieldId?: string }
            | undefined;
          if (props?.farmId && props?.fieldId) {
            onSelectRef.current(props.farmId, props.fieldId);
          }
        });
        map.on("mouseenter", "workspace-points-dot", () => {
          if (map) map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", "workspace-points-dot", () => {
          if (map) map.getCanvas().style.cursor = "";
        });

        updateCalloutPin();
      });

      map.on("move", updateCalloutPin);
      map.on("zoom", updateCalloutPin);

      map.on("webglcontextlost", () => setWebglFailed(true));
      map.on("error", (ev) => {
        const msg = String((ev as { error?: { message?: string } })?.error?.message || "");
        if (msg.toLowerCase().includes("webgl")) {
          setWebglFailed(true);
        }
      });
    } catch {
      setWebglFailed(true);
    }

    return () => {
      if (map) {
        map.remove();
        mapRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [webglFailed]);

  // Sync GeoJSON data & camera focus when saved fields or selection changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) {
      updateCalloutPin();
      return;
    }

    const polySrc = map.getSource("workspace-fields") as maplibregl.GeoJSONSource | undefined;
    if (polySrc) polySrc.setData(fieldsGeoJson);

    const ptSrc = map.getSource("workspace-points") as maplibregl.GeoJSONSource | undefined;
    if (ptSrc) ptSrc.setData(pointsGeoJson);

    if (selectedField) {
      const ring = extractRingFromBoundary(selectedField.location.boundary);
      const bbox = ring.length >= 3 ? computePolygonBbox(ring) : null;
      if (bbox) {
        map.fitBounds(
          [
            [bbox[0], bbox[1]],
            [bbox[2], bbox[3]],
          ],
          { padding: 70, maxZoom: 15, duration: 600 }
        );
      } else {
        map.flyTo({
          center: [selectedField.location.longitude, selectedField.location.latitude],
          zoom: 13.8,
          duration: 600,
        });
      }
    } else if (fields.length > 0) {
      const lons = fields.map((f) => f.location.longitude);
      const lats = fields.map((f) => f.location.latitude);
      map.fitBounds(
        [
          [Math.min(...lons) - 0.08, Math.min(...lats) - 0.06],
          [Math.max(...lons) + 0.08, Math.max(...lats) + 0.06],
        ],
        { padding: 60, maxZoom: 12.2, duration: 550 }
      );
    }

    updateCalloutPin();
  }, [fields, fieldsGeoJson, pointsGeoJson, selectedField, updateCalloutPin]);

  useEffect(() => {
    updateCalloutPin();
    window.addEventListener("resize", updateCalloutPin);
    return () => window.removeEventListener("resize", updateCalloutPin);
  }, [updateCalloutPin]);

  // Build SVG fallback representation of Guelma Wilaya outline
  const guelmaOutlineSvgPts = useMemo(() => {
    const geom = GUELMA_FALLBACK_BOUNDARY.geometry;
    const outer =
      geom.type === "MultiPolygon"
        ? ((geom.coordinates as number[][][][])[0]?.[0] as [number, number][]) || []
        : ((geom.coordinates as number[][][])[0] as [number, number][]) || [];
    return outer.map(([lon, lat]) => projectToSvg(lon, lat).join(",")).join(" ");
  }, []);

  const activePillLabel = selectedField
    ? `${selectedField.field_name}`
    : hudLabels?.communesChip ?? "Guelma · 34 communes";

  return (
    <div className="relative" data-testid="guelma-overview-map">
      <div
        ref={mapFrameRef}
        className="lg-map-frame lg-specular relative h-[340px] w-full overflow-hidden rounded-3xl bg-[#0a1310] dark:bg-[#070d0a] sm:h-[420px] md:h-[470px] lg:h-[500px]"
      >
        {/* Full-bleed Satellite Map / SVG Spatial Fallback */}
        <div
          className={`h-full w-full transition-[filter] duration-200 ${
            highContrastLayers ? "brightness-110 contrast-110 saturate-125" : ""
          }`}
        >
          {!webglFailed ? (
            <div ref={containerRef} className="h-full w-full" />
          ) : (
            <svg
              viewBox="0 0 640 360"
              className={
                isDarkTheme
                  ? "h-full w-full bg-[radial-gradient(ellipse_at_60%_35%,rgba(34,197,94,0.16),rgba(13,25,18,0.98)_70%)]"
                  : "h-full w-full bg-[radial-gradient(ellipse_at_60%_35%,rgba(21,128,61,0.14),rgba(232,241,234,0.98)_72%)]"
              }
              data-testid="guelma-overview-svg-fallback"
            >
              <defs>
                <pattern id="fs-topo-grid" width="32" height="32" patternUnits="userSpaceOnUse">
                  <path
                    d="M 32 0 L 0 0 0 32"
                    fill="none"
                    stroke={isDarkTheme ? "rgba(255,255,255,0.04)" : "rgba(11,61,46,0.07)"}
                    strokeWidth="1"
                  />
                </pattern>
              </defs>
              <rect width="640" height="360" fill="url(#fs-topo-grid)" />
              <polygon
                points={guelmaOutlineSvgPts}
                fill={
                  isDarkTheme
                    ? highContrastLayers
                      ? "rgba(34, 197, 94, 0.16)"
                      : "rgba(34, 197, 94, 0.10)"
                    : highContrastLayers
                      ? "rgba(21, 128, 61, 0.18)"
                      : "rgba(21, 128, 61, 0.10)"
                }
                stroke={isDarkTheme ? "rgba(167, 243, 208, 0.55)" : "rgba(11, 61, 46, 0.45)"}
                strokeWidth="1.6"
                strokeDasharray="6 4"
              />
              {fields.map((f) => {
                const key = `${f.farm_id}::${f.field_id}`;
                const isSel = key === selectedFieldKey;
                const [cx, cy] = projectToSvg(f.location.longitude, f.location.latitude, 640, 360);
                return (
                  <g
                    key={key}
                    onClick={() => onSelectField(f.farm_id, f.field_id)}
                    style={{ cursor: "pointer" }}
                  >
                    <circle
                      cx={cx}
                      cy={cy}
                      r={isSel ? 12 : 8}
                      fill={
                        isSel
                          ? isDarkTheme
                            ? "rgba(74, 222, 128, 0.35)"
                            : "rgba(21, 128, 61, 0.25)"
                          : "rgba(234, 179, 77, 0.24)"
                      }
                    />
                    <circle
                      cx={cx}
                      cy={cy}
                      r={isSel ? 6 : 4.5}
                      fill={isSel ? (isDarkTheme ? "#4ADE80" : "#15803D") : "#EAB34D"}
                      stroke={isDarkTheme ? "#FFFFFF" : "#0B3D2E"}
                      strokeWidth="1.8"
                    />
                  </g>
                );
              })}
            </svg>
          )}
        </div>

        {/* Liquid Glass Atmospheric Vignette overlay from Prototype */}
        <div className="lg-vignette" />

        {/* Callout Vector Leader Line + Pin Connector (Desktop/Tablet md+) */}
        {calloutPin && selectedField && inspectorOpen ? (
          <svg
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 z-10 hidden h-full w-full md:block"
          >
            <polyline
              points={`280,${Math.max(120, Math.min(390, calloutPin.y + 42))} ${Math.max(
                290,
                calloutPin.x - 18
              )},${calloutPin.y} ${calloutPin.x},${calloutPin.y}`}
              fill="none"
              stroke={isDarkTheme || !webglFailed ? "rgba(255,255,255,0.78)" : "rgba(11,61,46,0.72)"}
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
            <circle
              cx={calloutPin.x}
              cy={calloutPin.y}
              r="7"
              fill={isDarkTheme ? "rgba(74, 222, 128, 0.35)" : "rgba(21, 128, 61, 0.28)"}
            />
            <circle
              cx={calloutPin.x}
              cy={calloutPin.y}
              r="3.5"
              fill={isDarkTheme || !webglFailed ? "#FFFFFF" : "#0B3D2E"}
            />
          </svg>
        ) : null}

        {/* TOP-LEADING HUD: Layers & Draw Parcel Circular Glass Icons */}
        <div className="pointer-events-none absolute start-3 top-3 z-20 flex items-center gap-2.5">
          <button
            type="button"
            onClick={() => setHighContrastLayers((v) => !v)}
            aria-pressed={highContrastLayers}
            aria-label={hudLabels?.layersLabel ?? "Toggle satellite layer contrast"}
            title={hudLabels?.layersLabel ?? "Toggle satellite layer contrast"}
            className={`pointer-events-auto flex h-10 w-10 items-center justify-center rounded-full transition-[transform,background-color,color] duration-150 ease-out active:scale-[0.96] ${
              highContrastLayers
                ? "lg-capsule lg-capsule-active"
                : "lg-capsule text-[#111813] dark:text-[#F5F7F5]"
            }`}
          >
            <Stack size={17} aria-hidden="true" />
          </button>

          {onStartAddFarm ? (
            <button
              type="button"
              onClick={onStartAddFarm}
              aria-label={hudLabels?.drawParcelLabel ?? "Draw parcel on map"}
              title={hudLabels?.drawParcelLabel ?? "Draw parcel on map"}
              className="lg-capsule pointer-events-auto flex h-10 w-10 items-center justify-center rounded-full text-[#111813] transition-[transform,background-color] duration-150 ease-out active:scale-[0.96] dark:text-[#F5F7F5]"
            >
              <PencilLine size={17} aria-hidden="true" />
            </button>
          ) : null}
        </div>

        {/* TOP-CENTER HUD: Parcel Switcher Pill (< [Active Field / Communes] >) */}
        <div className="pointer-events-none absolute start-1/2 top-3 z-20 hidden max-w-[calc(100%-200px)] -translate-x-1/2 items-center gap-2 rtl:translate-x-1/2 sm:flex">
          <button
            type="button"
            disabled={fields.length < 2}
            onClick={() => handleStepField(-1)}
            aria-label={hudLabels?.prevFieldLabel ?? "Previous parcel"}
            className="lg-capsule pointer-events-auto flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[#111813] transition-[transform,background-color,opacity] duration-150 ease-out active:not-disabled:scale-[0.96] disabled:opacity-40 dark:text-[#F5F7F5]"
          >
            <CaretLeft size={15} weight="bold" className="rtl:-scale-x-100" aria-hidden="true" />
          </button>

          <div className="lg-capsule lg-capsule-active pointer-events-auto flex min-h-10 max-w-[230px] items-center justify-center rounded-full px-4 text-xs font-semibold tracking-tight shadow-md">
            <span dir="auto" className="truncate">
              {activePillLabel}
            </span>
          </div>

          <button
            type="button"
            disabled={fields.length < 2}
            onClick={() => handleStepField(1)}
            aria-label={hudLabels?.nextFieldLabel ?? "Next parcel"}
            className="lg-capsule pointer-events-auto flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[#111813] transition-[transform,background-color,opacity] duration-150 ease-out active:not-disabled:scale-[0.96] disabled:opacity-40 dark:text-[#F5F7F5]"
          >
            <CaretRight size={15} weight="bold" className="rtl:-scale-x-100" aria-hidden="true" />
          </button>
        </div>

        {/* TOP-TRAILING HUD: Fit Extent Circular Glass Button */}
        <div className="pointer-events-none absolute end-3 top-3 z-20">
          <button
            type="button"
            onClick={handleFitExtent}
            aria-label={hudLabels?.fitExtent ?? "Fit extent"}
            title={hudLabels?.fitExtent ?? "Fit extent"}
            data-testid="map-fit-extent-btn"
            className="lg-capsule pointer-events-auto flex h-10 w-10 items-center justify-center rounded-full text-[#111813] transition-[transform,background-color] duration-150 ease-out active:scale-[0.96] dark:text-[#F5F7F5]"
          >
            <CornersOut size={16} aria-hidden="true" />
          </button>
        </div>

        {/* BOTTOM-TRAILING HUD: Vertical + / - Zoom Capsule + Center Location Circle */}
        <div className="pointer-events-none absolute bottom-3 end-3 z-20 flex flex-col items-end gap-2.5">
          <div className="lg-capsule pointer-events-auto flex flex-col gap-1 rounded-full p-1">
            <button
              type="button"
              onClick={handleZoomIn}
              aria-label={hudLabels?.zoomIn ?? "Zoom in"}
              title={hudLabels?.zoomIn ?? "Zoom in"}
              className="flex h-9 w-9 items-center justify-center rounded-full text-[#111813] transition-[transform,background-color] duration-150 ease-out hover:bg-[#111813]/10 active:scale-[0.96] dark:text-[#F5F7F5] dark:hover:bg-white/15"
            >
              <Plus size={15} weight="bold" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={handleZoomOut}
              aria-label={hudLabels?.zoomOut ?? "Zoom out"}
              title={hudLabels?.zoomOut ?? "Zoom out"}
              className="flex h-9 w-9 items-center justify-center rounded-full text-[#111813] transition-[transform,background-color] duration-150 ease-out hover:bg-[#111813]/10 active:scale-[0.96] dark:text-[#F5F7F5] dark:hover:bg-white/15"
            >
              <Minus size={15} weight="bold" aria-hidden="true" />
            </button>
          </div>

          <button
            type="button"
            onClick={handleCenterSelected}
            aria-label={hudLabels?.fitExtent ?? "Fit extent"}
            title={hudLabels?.fitExtent ?? "Fit extent"}
            className="lg-capsule pointer-events-auto flex h-10 w-10 items-center justify-center rounded-full text-[#111813] transition-[transform,background-color] duration-150 ease-out active:scale-[0.96] dark:text-[#F5F7F5]"
          >
            <Crosshair size={16} aria-hidden="true" />
          </button>
        </div>

        {/* Reopen Inspector Pill when closed manually on desktop */}
        {!inspectorOpen && onReopenInspector && fields.length > 0 ? (
          <div className="pointer-events-none absolute bottom-3 start-3 z-20">
            <button
              type="button"
              onClick={onReopenInspector}
              data-testid="reopen-inspector-btn"
              className="lg-capsule pointer-events-auto inline-flex min-h-10 items-center gap-2 rounded-full ps-3.5 pe-4 text-xs font-medium text-[#111813] transition-[transform,background-color] duration-150 ease-out active:scale-[0.96] dark:text-[#F5F7F5]"
            >
              <Info size={15} className="text-[#15803D] dark:text-[#4ADE80]" aria-hidden="true" />
              <span>{hudLabels?.openInspectorLabel ?? "Open parcel inspector"}</span>
            </button>
          </div>
        ) : null}
      </div>

      {/* Single DOM Inspector Card: flows below map on <md mobile, floats inside lower-leading corner on md+ */}
      {children && inspectorOpen ? (
        <div className="mt-3 md:pointer-events-none md:absolute md:bottom-3 md:start-3 md:z-20 md:mt-0 md:w-[336px] md:max-w-[calc(100%-84px)] lg:w-[356px]">
          <div className="md:pointer-events-auto">{children}</div>
        </div>
      ) : null}
    </div>
  );
}
