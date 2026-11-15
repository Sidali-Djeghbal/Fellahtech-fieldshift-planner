"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { MapPin, Compass } from "@phosphor-icons/react";
import {
  extractRingFromBoundary,
  GUELMA_DEFAULT_CENTER,
  GUELMA_FALLBACK_BOUNDARY,
  computePolygonBbox,
  closeRing,
} from "@/lib/geo/guelma";
import { canUseWebgl } from "@/lib/geo/webgl";
import type { FieldDetailPublic } from "@/lib/schemas";

interface GuelmaOverviewMapProps {
  fields: FieldDetailPublic[];
  selectedFieldKey: string | null;
  onSelectField: (farmId: string, fieldId: string) => void;
  onOpenInspect?: (farmId: string, fieldId: string) => void;
  title: string;
  subtitle: string;
}

const GUELMA_SVG_BOUNDS = {
  minLon: 6.94,
  maxLon: 7.94,
  minLat: 36.02,
  maxLat: 36.70,
};

function projectToSvg(lon: number, lat: number, w = 640, h = 280): [number, number] {
  const x = ((lon - GUELMA_SVG_BOUNDS.minLon) / (GUELMA_SVG_BOUNDS.maxLon - GUELMA_SVG_BOUNDS.minLon)) * w;
  const y = ((GUELMA_SVG_BOUNDS.maxLat - lat) / (GUELMA_SVG_BOUNDS.maxLat - GUELMA_SVG_BOUNDS.minLat)) * h;
  return [Number(x.toFixed(1)), Number(y.toFixed(1))];
}

export function GuelmaOverviewMap({
  fields,
  selectedFieldKey,
  onSelectField,
  onOpenInspect,
  title,
  subtitle,
}: GuelmaOverviewMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [webglFailed, setWebglFailed] = useState(false);

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
            "line-color": "#A7F3D0",
            "line-width": 2,
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
            "fill-color": ["case", ["==", ["get", "selected"], 1], "#22C55E", "#38BDF8"],
            "fill-opacity": ["case", ["==", ["get", "selected"], 1], 0.34, 0.22],
          },
        });
        map.addLayer({
          id: "workspace-fields-line",
          type: "line",
          source: "workspace-fields",
          paint: {
            "line-color": ["case", ["==", ["get", "selected"], 1], "#DCFCE7", "#BAE6FD"],
            "line-width": ["case", ["==", ["get", "selected"], 1], 2.5, 1.6],
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
            "circle-color": ["case", ["==", ["get", "selected"], 1], "#16A34A", "#0EA5E9"],
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
      });

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
    if (!map || !map.isStyleLoaded()) return;

    const polySrc = map.getSource("workspace-fields") as maplibregl.GeoJSONSource | undefined;
    if (polySrc) polySrc.setData(fieldsGeoJson);

    const ptSrc = map.getSource("workspace-points") as maplibregl.GeoJSONSource | undefined;
    if (ptSrc) ptSrc.setData(pointsGeoJson);

    const selected = fields.find(
      (f) => `${f.farm_id}::${f.field_id}` === selectedFieldKey
    );
    if (selected) {
      const ring = extractRingFromBoundary(selected.location.boundary);
      const bbox = ring.length >= 3 ? computePolygonBbox(ring) : null;
      if (bbox) {
        map.fitBounds(
          [
            [bbox[0], bbox[1]],
            [bbox[2], bbox[3]],
          ],
          { padding: 55, maxZoom: 15.2, duration: 750 }
        );
      } else {
        map.flyTo({
          center: [selected.location.longitude, selected.location.latitude],
          zoom: 13.8,
          duration: 750,
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
        { padding: 45, maxZoom: 12.2, duration: 700 }
      );
    }
  }, [fields, fieldsGeoJson, pointsGeoJson, selectedFieldKey]);

  // Build SVG fallback representation of Guelma Wilaya outline
  const guelmaOutlineSvgPts = useMemo(() => {
    const geom = GUELMA_FALLBACK_BOUNDARY.geometry;
    const outer =
      geom.type === "MultiPolygon"
        ? ((geom.coordinates as number[][][][])[0]?.[0] as [number, number][]) || []
        : ((geom.coordinates as number[][][])[0] as [number, number][]) || [];
    return outer
      .map(([lon, lat]) => projectToSvg(lon, lat).join(","))
      .join(" ");
  }, []);

  return (
    <div className="overflow-hidden rounded-2xl border border-[#DCE3DF] bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E5EAE7] px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#0B4B2E]/10 text-[#0B4B2E]">
            <Compass size={16} weight="duotone" />
          </span>
          <div>
            <h3 className="text-sm font-bold text-[#111827]">{title}</h3>
            <p className="text-[11px] text-[#6B7280]">{subtitle}</p>
          </div>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-[#ECFDF5] px-2.5 py-1 text-[11px] font-semibold text-[#065F46]">
          <span className="h-1.5 w-1.5 rounded-full bg-[#10B981]" />
          36.05°–36.68° N · 6.96°–7.92° E
        </span>
      </div>

      <div className="relative h-64 w-full bg-[#0C1C15]">
        {!webglFailed ? (
          <div ref={containerRef} className="h-full w-full" />
        ) : (
          <svg
            viewBox="0 0 640 280"
            className="h-full w-full bg-[#0C1C15]"
            data-testid="guelma-overview-svg-fallback"
          >
            <polygon
              points={guelmaOutlineSvgPts}
              fill="rgba(16, 185, 129, 0.08)"
              stroke="#6EE7B7"
              strokeWidth="1.6"
              strokeDasharray="6 4"
            />
            {fields.map((f) => {
              const key = `${f.farm_id}::${f.field_id}`;
              const isSel = key === selectedFieldKey;
              const [cx, cy] = projectToSvg(f.location.longitude, f.location.latitude);
              return (
                <g
                  key={key}
                  onClick={() => onSelectField(f.farm_id, f.field_id)}
                  style={{ cursor: "pointer" }}
                >
                  <circle
                    cx={cx}
                    cy={cy}
                    r={isSel ? 8 : 6}
                    fill={isSel ? "#22C55E" : "#38BDF8"}
                    stroke="#FFFFFF"
                    strokeWidth="2"
                  />
                  <text
                    x={cx + 11}
                    y={cy + 4}
                    fill="#ECFDF5"
                    fontSize="11"
                    fontWeight="600"
                  >
                    {f.field_name}
                  </text>
                </g>
              );
            })}
          </svg>
        )}

        {/* Quick field selector strip overlaid cleanly when fields exist */}
        {fields.length > 0 ? (
          <div className="pointer-events-none absolute inset-x-3 bottom-3 flex flex-wrap gap-1.5">
            {fields.slice(0, 6).map((f) => {
              const key = `${f.farm_id}::${f.field_id}`;
              const isSel = key === selectedFieldKey;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => {
                    onSelectField(f.farm_id, f.field_id);
                    onOpenInspect?.(f.farm_id, f.field_id);
                  }}
                  className={`pointer-events-auto inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold shadow-sm backdrop-blur-md transition ${
                    isSel
                      ? "bg-[#0B4B2E] text-white ring-1 ring-[#6EE7B7]"
                      : "bg-black/65 text-[#ECFDF5] hover:bg-black/80"
                  }`}
                >
                  <MapPin size={12} weight="fill" />
                  <span className="max-w-[140px] truncate">{f.field_name}</span>
                  <span className="font-mono text-[10px] opacity-80">
                    {f.area_hectares.toFixed(1)} ha
                  </span>
                </button>
              );
            })}
          </div>
        ) : null}
      </div>
    </div>
  );
}
