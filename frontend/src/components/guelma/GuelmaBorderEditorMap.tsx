"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  ArrowCounterClockwise,
  ArrowClockwise,
  CheckCircle,
  Compass,
  Crosshair,
  Cube,
  MagnifyingGlass,
  MapPin,
  Polygon,
  Trash,
  WarningCircle,
  X,
} from "@phosphor-icons/react";
import {
  closeRing,
  computeEdgeMidpoints,
  computePerimeterMeters,
  computePolygonAreaHectares,
  computePolygonBbox,
  computePolygonCentroid,
  findNearestGuelmaCommune,
  GUELMA_COMMUNES,
  GUELMA_DEFAULT_CENTER,
  GUELMA_FALLBACK_BOUNDARY,
  GUELMA_PARCEL_PRESETS,
  haversineMeters,
  isInsideGuelmaBoundary,
  ringSegmentsSelfIntersect,
  ringToGeoJsonPolygon,
  stripClosingPoint,
  type GuelmaCommune,
} from "@/lib/geo/guelma";
import { LAYERS } from "@/lib/prototype/data";
import { dateStrFor, gibsUrl, measureCoordFromDem } from "@/lib/prototype/engine";
import { useResolvedTheme } from "@/app/providers";
import { canUseWebgl } from "@/lib/geo/webgl";
import { GUELMA_WORKSPACE_I18N } from "@/lib/i18n/guelmaWorkspace";
import type { Language } from "@/lib/schemas";

export interface BorderDraftResult {
  ring: [number, number][];
  boundary: Record<string, unknown>;
  centroid: { latitude: number; longitude: number };
  areaHectares: number;
  perimeterMeters: number;
  nearestCommune: GuelmaCommune;
}

interface Snapshot {
  vertices: [number, number][];
  isClosed: boolean;
}

interface GuelmaBorderEditorMapProps {
  lang: Language;
  mode: "create" | "edit";
  initialRing?: [number, number][];
  initialCenter?: [number, number];
  onBack: () => void;
  onConfirmBorders: (result: BorderDraftResult) => void;
}

function projectRingLatLonToSvg(
  ring: [number, number][],
  center: [number, number],
  spanLon: number,
  w = 1000,
  h = 620
): [number, number][] {
  const cosLat = Math.cos((center[1] * Math.PI) / 180);
  const spanLat = (spanLon * cosLat * h) / w;
  return ring.map(([lon, lat]) => {
    const x = ((lon - (center[0] - spanLon / 2)) / spanLon) * w;
    const y = (((center[1] + spanLat / 2) - lat) / spanLat) * h;
    return [Number(x.toFixed(1)), Number(y.toFixed(1))];
  });
}

function unprojectSvgToLonLat(
  x: number,
  y: number,
  center: [number, number],
  spanLon: number,
  w = 1000,
  h = 620
): [number, number] {
  const cosLat = Math.cos((center[1] * Math.PI) / 180);
  const spanLat = (spanLon * cosLat * h) / w;
  const lon = center[0] - spanLon / 2 + (x / w) * spanLon;
  const lat = center[1] + spanLat / 2 - (y / h) * spanLat;
  return [Number(lon.toFixed(6)), Number(lat.toFixed(6))];
}

function buildOverlayGeoJson(
  vertices: [number, number][],
  isClosed: boolean,
  hoverCoord: [number, number] | null,
  snapToFirst: boolean
) {
  const polyFeatures: GeoJSON.Feature[] = [];
  if (isClosed && vertices.length >= 3) {
    polyFeatures.push({
      type: "Feature",
      properties: {},
      geometry: {
        type: "Polygon",
        coordinates: [closeRing(vertices)],
      },
    });
  }

  const lineCoords: [number, number][] = isClosed
    ? vertices.length >= 3
      ? closeRing(vertices)
      : []
    : hoverCoord && vertices.length >= 1
    ? snapToFirst && vertices.length >= 3
      ? [...vertices, vertices[0]]
      : [...vertices, hoverCoord]
    : vertices;

  const lineFeatures: GeoJSON.Feature[] =
    lineCoords.length >= 2
      ? [
          {
            type: "Feature",
            properties: {},
            geometry: { type: "LineString", coordinates: lineCoords },
          },
        ]
      : [];

  const rubberFeatures: GeoJSON.Feature[] = [];
  if (!isClosed && hoverCoord && vertices.length >= 2 && !snapToFirst) {
    rubberFeatures.push({
      type: "Feature",
      properties: {},
      geometry: {
        type: "LineString",
        coordinates: [hoverCoord, vertices[0]],
      },
    });
  }

  const labelFeatures: GeoJSON.Feature[] = [];
  const edgeCount = isClosed ? vertices.length : Math.max(0, vertices.length - 1);
  for (let i = 0; i < edgeCount; i++) {
    const a = vertices[i];
    const b = vertices[(i + 1) % vertices.length];
    if (!a || !b) continue;
    const dist = Math.round(haversineMeters(a, b));
    if (dist > 0) {
      labelFeatures.push({
        type: "Feature",
        properties: { label: `${dist} m` },
        geometry: {
          type: "Point",
          coordinates: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2],
        },
      });
    }
  }
  if (!isClosed && hoverCoord && vertices.length >= 1) {
    const last = vertices[vertices.length - 1];
    const target = snapToFirst ? vertices[0] : hoverCoord;
    const dist = Math.round(haversineMeters(last, target));
    if (dist > 0) {
      labelFeatures.push({
        type: "Feature",
        properties: { label: `${dist} m` },
        geometry: {
          type: "Point",
          coordinates: [(last[0] + target[0]) / 2, (last[1] + target[1]) / 2],
        },
      });
    }
  }

  return { polyFeatures, lineFeatures, rubberFeatures, labelFeatures };
}

export function GuelmaBorderEditorMap({
  lang,
  mode,
  initialRing,
  initialCenter,
  onBack,
  onConfirmBorders,
}: GuelmaBorderEditorMapProps) {
  const dict = GUELMA_WORKSPACE_I18N[lang];
  const t = dict.editor;
  const resolvedTheme = useResolvedTheme();
  const isDarkTheme = resolvedTheme === "dark";

  const cleanInitial = useMemo(
    () => (initialRing && initialRing.length >= 3 ? stripClosingPoint(initialRing) : []),
    [initialRing]
  );

  const [vertices, setVertices] = useState<[number, number][]>(cleanInitial);
  const [isClosed, setIsClosed] = useState<boolean>(cleanInitial.length >= 3);
  const [undoStack, setUndoStack] = useState<Snapshot[]>([]);
  const [redoStack, setRedoStack] = useState<Snapshot[]>([]);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [hoverCoord, setHoverCoord] = useState<[number, number] | null>(null);
  const [snapToFirst, setSnapToFirst] = useState(false);

  const defaultFlyCenter: [number, number] = useMemo(() => {
    if (cleanInitial.length >= 3) {
      const c = computePolygonCentroid(cleanInitial);
      if (c) return [c.longitude, c.latitude];
    }
    return initialCenter || GUELMA_DEFAULT_CENTER;
  }, [cleanInitial, initialCenter]);

  const [svgCenter, setSvgCenter] = useState<[number, number]>(defaultFlyCenter);
  const [svgSpanLon] = useState<number>(0.014);
  const [svgDragIdx, setSvgDragIdx] = useState<number | null>(null);
  const [webglFailed, setWebglFailed] = useState(false);

  const [communeQuery, setCommuneQuery] = useState("");
  const [communeDropdownOpen, setCommuneDropdownOpen] = useState(false);
  const [activeCommune, setActiveCommune] = useState<GuelmaCommune>(() =>
    findNearestGuelmaCommune(defaultFlyCenter[1], defaultFlyCenter[0])
  );
  const [tilt3d, setTilt3d] = useState(false);
  const [overlay, setOverlay] = useState<"none" | "ndvi" | "sm">("none");
  const [demRef, setDemRef] = useState<{ elev: number; slope: number } | null>(null);

  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const vertexMarkersRef = useRef<maplibregl.Marker[]>([]);
  const midpointMarkersRef = useRef<maplibregl.Marker[]>([]);
  const draggingVertexRef = useRef(false);

  const liveStateRef = useRef({ vertices, isClosed, undoStack });
  liveStateRef.current = { vertices, isClosed, undoStack };

  const pushSnapshot = useCallback((nextVertices: [number, number][], nextClosed: boolean) => {
    setUndoStack((prev) => [
      ...prev.slice(-29),
      { vertices: liveStateRef.current.vertices, isClosed: liveStateRef.current.isClosed },
    ]);
    setRedoStack([]);
    setVertices(nextVertices);
    setIsClosed(nextClosed);
  }, []);

  const handleUndo = useCallback(() => {
    setUndoStack((prev) => {
      if (prev.length === 0) return prev;
      const top = prev[prev.length - 1];
      setRedoStack((r) => [
        ...r,
        { vertices: liveStateRef.current.vertices, isClosed: liveStateRef.current.isClosed },
      ]);
      setVertices(top.vertices);
      setIsClosed(top.isClosed);
      setSelectedIdx(null);
      return prev.slice(0, -1);
    });
  }, []);

  const handleRedo = useCallback(() => {
    setRedoStack((prev) => {
      if (prev.length === 0) return prev;
      const top = prev[prev.length - 1];
      setUndoStack((u) => [
        ...u,
        { vertices: liveStateRef.current.vertices, isClosed: liveStateRef.current.isClosed },
      ]);
      setVertices(top.vertices);
      setIsClosed(top.isClosed);
      setSelectedIdx(null);
      return prev.slice(0, -1);
    });
  }, []);

  const handleClear = useCallback(() => {
    if (vertices.length === 0) return;
    pushSnapshot([], false);
    setSelectedIdx(null);
    setHoverCoord(null);
    setSnapToFirst(false);
  }, [vertices.length, pushSnapshot]);

  const handleClosePolygon = useCallback(() => {
    if (vertices.length < 3 || isClosed) return;
    pushSnapshot(vertices, true);
    setHoverCoord(null);
    setSnapToFirst(false);
  }, [vertices, isClosed, pushSnapshot]);

  const handleDeleteVertex = useCallback(
    (idx: number) => {
      if (idx < 0 || idx >= vertices.length) return;
      const next = vertices.filter((_, i) => i !== idx);
      const nextClosed = isClosed && next.length >= 3;
      pushSnapshot(next, nextClosed);
      setSelectedIdx(null);
    },
    [vertices, isClosed, pushSnapshot]
  );

  // Live geodesic & province verification computations
  const areaHectares = useMemo(
    () => (vertices.length >= 3 ? computePolygonAreaHectares(vertices) : 0),
    [vertices]
  );
  const perimeterMeters = useMemo(
    () => Math.round(computePerimeterMeters(vertices, isClosed)),
    [vertices, isClosed]
  );
  const centroid = useMemo(() => computePolygonCentroid(vertices), [vertices]);
  const selfIntersects = useMemo(
    () => (vertices.length >= 4 ? ringSegmentsSelfIntersect(vertices) : false),
    [vertices]
  );
  const insideGuelma = useMemo(() => {
    if (vertices.length === 0) return true;
    if (isClosed && vertices.length >= 3 && centroid) {
      return isInsideGuelmaBoundary(
        centroid.latitude,
        centroid.longitude,
        GUELMA_FALLBACK_BOUNDARY,
        vertices
      );
    }
    return vertices.every(([lon, lat]) => isInsideGuelmaBoundary(lat, lon));
  }, [vertices, isClosed, centroid]);

  const nearestCommune = useMemo(() => {
    if (centroid) return findNearestGuelmaCommune(centroid.latitude, centroid.longitude);
    return activeCommune;
  }, [centroid, activeCommune]);

  const canSave =
    isClosed && vertices.length >= 3 && !selfIntersects && insideGuelma && areaHectares > 0;

  // Non-binding live DEM terrain reference fetch when centroid settles
  useEffect(() => {
    if (!centroid) {
      setDemRef(null);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      measureCoordFromDem(centroid.latitude, centroid.longitude).then((res) => {
        if (!cancelled && res) setDemRef(res);
      });
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [centroid]);

  // Update GeoJSON sources directly (used during drag & state updates)
  const syncMapGeoJson = useCallback(
    (
      verts: [number, number][],
      closed: boolean,
      hover: [number, number] | null,
      snap: boolean
    ) => {
      const map = mapRef.current;
      if (!map || !map.isStyleLoaded()) return;
      const { polyFeatures, lineFeatures, rubberFeatures, labelFeatures } =
        buildOverlayGeoJson(verts, closed, hover, snap);

      const polySrc = map.getSource("draw-poly") as maplibregl.GeoJSONSource | undefined;
      if (polySrc) polySrc.setData({ type: "FeatureCollection", features: polyFeatures });

      const lineSrc = map.getSource("draw-line") as maplibregl.GeoJSONSource | undefined;
      if (lineSrc) lineSrc.setData({ type: "FeatureCollection", features: lineFeatures });

      const rubSrc = map.getSource("draw-rubber") as maplibregl.GeoJSONSource | undefined;
      if (rubSrc) rubSrc.setData({ type: "FeatureCollection", features: rubberFeatures });

      const lblSrc = map.getSource("draw-edges-lbl") as maplibregl.GeoJSONSource | undefined;
      if (lblSrc) lblSrc.setData({ type: "FeatureCollection", features: labelFeatures });
    },
    []
  );

  useEffect(() => {
    syncMapGeoJson(vertices, isClosed, hoverCoord, snapToFirst);
  }, [vertices, isClosed, hoverCoord, snapToFirst, syncMapGeoJson]);

  // Initialize MapLibre CAD canvas
  useEffect(() => {
    const el = mapContainerRef.current;
    if (!el || webglFailed) return;
    if (!canUseWebgl()) {
      setWebglFailed(true);
      return;
    }

    let map: maplibregl.Map | null = null;
    try {
      const ndviDate = dateStrFor("ndvi", { y: 2026, m: 4 });
      const smDate = dateStrFor("sm", { y: 2026, m: 4 });

      const style: maplibregl.StyleSpecification = {
        version: 8,
        glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
        sources: {
          esri: {
            type: "raster",
            tiles: [
              "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            ],
            tileSize: 256,
            maxzoom: 19,
          },
          ndvi: {
            type: "raster",
            tiles: [gibsUrl("ndvi", ndviDate)],
            tileSize: 256,
            maxzoom: LAYERS.ndvi.maxzoom,
          },
          sm: {
            type: "raster",
            tiles: [gibsUrl("sm", smDate)],
            tileSize: 256,
            maxzoom: LAYERS.sm.maxzoom,
          },
          "aws-dem": {
            type: "raster-dem",
            tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
            encoding: "terrarium",
            tileSize: 256,
            maxzoom: 14,
          },
        },
        layers: [
          { id: "esri-sat", type: "raster", source: "esri" },
          {
            id: "gibs-ndvi",
            type: "raster",
            source: "ndvi",
            layout: { visibility: "none" },
            paint: { "raster-opacity": 0.56 },
          },
          {
            id: "gibs-sm",
            type: "raster",
            source: "sm",
            layout: { visibility: "none" },
            paint: { "raster-opacity": 0.58 },
          },
        ],
      };

      const startZoom = cleanInitial.length >= 3 ? 15.6 : 12.6;
      map = new maplibregl.Map({
        container: el,
        style,
        center: defaultFlyCenter,
        zoom: startZoom,
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
            "line-opacity": 0.75,
          },
        });

        map.addSource("draw-poly", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
        map.addLayer({
          id: "draw-poly-fill",
          type: "fill",
          source: "draw-poly",
          paint: {
            "fill-color": "#22C55E",
            "fill-opacity": 0.28,
          },
        });

        map.addSource("draw-line", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
        map.addLayer({
          id: "draw-line-stroke",
          type: "line",
          source: "draw-line",
          paint: {
            "line-color": "#ECFDF5",
            "line-width": 2.6,
          },
        });

        map.addSource("draw-rubber", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
        map.addLayer({
          id: "draw-rubber-stroke",
          type: "line",
          source: "draw-rubber",
          paint: {
            "line-color": "#86EFAC",
            "line-width": 1.8,
            "line-dasharray": [3, 3],
          },
        });

        map.addSource("draw-edges-lbl", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
        map.addLayer({
          id: "draw-edges-lbl-sym",
          type: "symbol",
          source: "draw-edges-lbl",
          layout: {
            "text-field": ["get", "label"],
            "text-size": 11,
            "text-allow-overlap": true,
            "text-offset": [0, -0.7],
          },
          paint: {
            "text-color": "#ECFDF5",
            "text-halo-color": "#062317",
            "text-halo-width": 1.6,
          },
        });

        if (cleanInitial.length >= 3) {
          const bbox = computePolygonBbox(cleanInitial);
          if (bbox) {
            map.fitBounds(
              [
                [bbox[0], bbox[1]],
                [bbox[2], bbox[3]],
              ],
              { padding: 90, maxZoom: 16.5, duration: 500 }
            );
          }
        }

        syncMapGeoJson(
          liveStateRef.current.vertices,
          liveStateRef.current.isClosed,
          null,
          false
        );
      });

      map.on("click", (e) => {
        if (draggingVertexRef.current) return;
        const { vertices: curVerts, isClosed: curClosed } = liveStateRef.current;
        if (curClosed) return;

        // Check snap-to-close on vertex #0 if >= 3 vertices
        if (curVerts.length >= 3 && map) {
          const p0 = map.project(curVerts[0]);
          const distPx = Math.hypot(e.point.x - p0.x, e.point.y - p0.y);
          if (distPx <= 16) {
            pushSnapshot(curVerts, true);
            setHoverCoord(null);
            setSnapToFirst(false);
            return;
          }
        }

        const nextCoord: [number, number] = [
          Number(e.lngLat.lng.toFixed(6)),
          Number(e.lngLat.lat.toFixed(6)),
        ];
        pushSnapshot([...curVerts, nextCoord], false);
      });

      map.on("mousemove", (e) => {
        const { vertices: curVerts, isClosed: curClosed } = liveStateRef.current;
        if (curClosed || curVerts.length === 0) return;

        const nextHover: [number, number] = [
          Number(e.lngLat.lng.toFixed(6)),
          Number(e.lngLat.lat.toFixed(6)),
        ];
        setHoverCoord(nextHover);

        if (curVerts.length >= 3 && map) {
          const p0 = map.project(curVerts[0]);
          const distPx = Math.hypot(e.point.x - p0.x, e.point.y - p0.y);
          setSnapToFirst(distPx <= 16);
        } else {
          setSnapToFirst(false);
        }
      });

      map.on("dblclick", (e) => {
        const { vertices: curVerts, isClosed: curClosed } = liveStateRef.current;
        if (!curClosed && curVerts.length >= 3) {
          e.preventDefault();
          pushSnapshot(curVerts, true);
          setHoverCoord(null);
          setSnapToFirst(false);
        }
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
      vertexMarkersRef.current.forEach((m) => m.remove());
      vertexMarkersRef.current = [];
      midpointMarkersRef.current.forEach((m) => m.remove());
      midpointMarkersRef.current = [];
      if (map) {
        map.remove();
        mapRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [webglFailed]);

  // Update GIBS overlays & 3D terrain toggle
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    if (map.getLayer("gibs-ndvi")) {
      map.setLayoutProperty("gibs-ndvi", "visibility", overlay === "ndvi" ? "visible" : "none");
    }
    if (map.getLayer("gibs-sm")) {
      map.setLayoutProperty("gibs-sm", "visibility", overlay === "sm" ? "visible" : "none");
    }
  }, [overlay]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    try {
      if (tilt3d) {
        map.setTerrain({ source: "aws-dem", exaggeration: 1.5 });
      } else {
        map.setTerrain(null);
      }
      map.easeTo({ pitch: tilt3d ? 46 : 0, duration: 550 });
    } catch {
      /* ignore */
    }
  }, [tilt3d]);

  // Synchronize polygon validation colors on MapLibre fill & stroke
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const err = selfIntersects || !insideGuelma;
    if (map.getLayer("draw-poly-fill")) {
      map.setPaintProperty("draw-poly-fill", "fill-color", err ? "#EF4444" : "#22C55E");
    }
    if (map.getLayer("draw-line-stroke")) {
      map.setPaintProperty("draw-line-stroke", "line-color", err ? "#FCA5A5" : "#ECFDF5");
    }
  }, [selfIntersects, insideGuelma]);

  // Rebuild MapLibre Vertex Handles & Edge Midpoints cleanly when geometry changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || webglFailed) return;

    vertexMarkersRef.current.forEach((m) => m.remove());
    vertexMarkersRef.current = [];
    midpointMarkersRef.current.forEach((m) => m.remove());
    midpointMarkersRef.current = [];

    vertices.forEach((coord, idx) => {
      const btn = document.createElement("button");
      btn.type = "button";
      const isFirstSnap = !isClosed && idx === 0 && snapToFirst;
      const isSelected = idx === selectedIdx;
      btn.title = isClosed ? `Corner ${idx + 1}` : idx === 0 ? "First corner (click to close)" : `Corner ${idx + 1}`;
      btn.style.cssText = `
        width: ${isFirstSnap ? "22px" : "20px"};
        height: ${isFirstSnap ? "22px" : "20px"};
        border-radius: 999px;
        border: 2px solid ${isFirstSnap ? "#86EFAC" : isSelected ? "#FDE047" : "#FFFFFF"};
        background: ${idx === 0 ? "#137135" : isSelected ? "#0F172A" : "#0B4B2E"};
        color: #FFFFFF;
        font-size: 10px;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: grab;
        box-shadow: 0 2px 8px rgba(0,0,0,0.45);
      `;
      btn.textContent = String(idx + 1);

      const marker = new maplibregl.Marker({ element: btn, draggable: true })
        .setLngLat(coord)
        .addTo(map);

      btn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const cur = liveStateRef.current;
        if (!cur.isClosed && idx === 0 && cur.vertices.length >= 3) {
          pushSnapshot(cur.vertices, true);
          setHoverCoord(null);
          setSnapToFirst(false);
        } else {
          setSelectedIdx((prev) => (prev === idx ? null : idx));
        }
      });

      btn.addEventListener("contextmenu", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        handleDeleteVertex(idx);
      });

      marker.on("dragstart", () => {
        draggingVertexRef.current = true;
      });
      marker.on("drag", () => {
        const ll = marker.getLngLat();
        const next = liveStateRef.current.vertices.map((v, i) =>
          i === idx ? ([Number(ll.lng.toFixed(6)), Number(ll.lat.toFixed(6))] as [number, number]) : v
        );
        syncMapGeoJson(next, liveStateRef.current.isClosed, null, false);
      });
      marker.on("dragend", () => {
        const ll = marker.getLngLat();
        const next = liveStateRef.current.vertices.map((v, i) =>
          i === idx ? ([Number(ll.lng.toFixed(6)), Number(ll.lat.toFixed(6))] as [number, number]) : v
        );
        pushSnapshot(next, liveStateRef.current.isClosed);
        setTimeout(() => {
          draggingVertexRef.current = false;
        }, 50);
      });

      vertexMarkersRef.current.push(marker);
    });

    if (isClosed && vertices.length >= 3) {
      const midpoints = computeEdgeMidpoints(vertices, true);
      midpoints.forEach((mp) => {
        const el = document.createElement("button");
        el.type = "button";
        el.title = `Insert vertex on ${Math.round(mp.lengthMeters)} m edge`;
        el.textContent = "+";
        el.style.cssText = `
          width: 16px;
          height: 16px;
          border-radius: 999px;
          border: 1.5px solid #ECFDF5;
          background: rgba(11, 75, 46, 0.86);
          color: #A7F3D0;
          font-size: 11px;
          font-weight: 700;
          line-height: 1;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          opacity: 0.9;
        `;
        el.addEventListener("click", (ev) => {
          ev.stopPropagation();
          const cur = liveStateRef.current.vertices;
          const next = [
            ...cur.slice(0, mp.insertIndex),
            mp.coord,
            ...cur.slice(mp.insertIndex),
          ];
          pushSnapshot(next, true);
        });
        const m = new maplibregl.Marker({ element: el }).setLngLat(mp.coord).addTo(map);
        midpointMarkersRef.current.push(m);
      });
    }
  }, [vertices, isClosed, selectedIdx, snapToFirst, webglFailed, pushSnapshot, handleDeleteVertex, syncMapGeoJson]);

  // Keyboard shortcuts
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        if (e.shiftKey) handleRedo();
        else handleUndo();
      } else if ((e.key === "Delete" || e.key === "Backspace") && selectedIdx !== null) {
        e.preventDefault();
        handleDeleteVertex(selectedIdx);
      } else if (e.key === "Escape") {
        setSelectedIdx(null);
        setCommuneDropdownOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleUndo, handleRedo, handleDeleteVertex, selectedIdx]);

  const filteredCommunes = useMemo(() => {
    const q = communeQuery.trim().toLowerCase();
    if (!q) return GUELMA_COMMUNES;
    return GUELMA_COMMUNES.filter(
      (c) =>
        c.name.en.toLowerCase().includes(q) ||
        c.name.fr.toLowerCase().includes(q) ||
        c.name.ar.includes(q) ||
        c.daira.en.toLowerCase().includes(q)
    );
  }, [communeQuery]);

  const handleJumpToCommune = (c: GuelmaCommune) => {
    setActiveCommune(c);
    setSvgCenter(c.center);
    setCommuneDropdownOpen(false);
    setCommuneQuery(c.name[lang] || c.name.en);
    const map = mapRef.current;
    if (map) {
      map.flyTo({ center: c.center, zoom: 14.3, pitch: tilt3d ? 46 : 0, duration: 950 });
    }
  };

  const handleApplyQuickPreset = (presetId: string) => {
    const preset = GUELMA_PARCEL_PRESETS.find((p) => p.id === presetId);
    if (!preset) return;
    const pts = stripClosingPoint(preset.ring);
    pushSnapshot(pts, true);
    setSelectedIdx(null);
    setSvgCenter(preset.center);
    const comm = findNearestGuelmaCommune(preset.center[1], preset.center[0]);
    setActiveCommune(comm);

    const map = mapRef.current;
    if (map) {
      const bbox = computePolygonBbox(pts);
      if (bbox) {
        map.fitBounds(
          [
            [bbox[0], bbox[1]],
            [bbox[2], bbox[3]],
          ],
          { padding: 95, maxZoom: 16.5, duration: 850 }
        );
      }
    }
  };

  const handleSaveBorders = () => {
    if (!canSave || !centroid) return;
    const boundary = ringToGeoJsonPolygon(vertices);
    if (!boundary) return;
    onConfirmBorders({
      ring: closeRing(vertices),
      boundary,
      centroid,
      areaHectares: Number(areaHectares.toFixed(2)),
      perimeterMeters,
      nearestCommune,
    });
  };

  // Interactive SVG canvas handlers (WebGL fallback + Playwright testing compatibility)
  const svgW = 1000;
  const svgH = 620;
  const svgProjectedVertices = useMemo(
    () => projectRingLatLonToSvg(vertices, svgCenter, svgSpanLon, svgW, svgH),
    [vertices, svgCenter, svgSpanLon]
  );
  const svgMidpoints = useMemo(() => {
    if (!isClosed || vertices.length < 3) return [];
    return computeEdgeMidpoints(vertices, true).map((mp) => ({
      ...mp,
      svgPt: projectRingLatLonToSvg([mp.coord], svgCenter, svgSpanLon, svgW, svgH)[0],
    }));
  }, [vertices, isClosed, svgCenter, svgSpanLon]);

  const svgClientToViewbox = (e: React.MouseEvent<SVGSVGElement>): [number, number] => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * svgW;
    const y = ((e.clientY - rect.top) / rect.height) * svgH;
    return [x, y];
  };

  const handleSvgClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (svgDragIdx !== null) return;
    if (isClosed) return;
    const [vx, vy] = svgClientToViewbox(e);

    if (vertices.length >= 3 && svgProjectedVertices[0]) {
      const d = Math.hypot(vx - svgProjectedVertices[0][0], vy - svgProjectedVertices[0][1]);
      if (d <= 18) {
        pushSnapshot(vertices, true);
        return;
      }
    }
    const coord = unprojectSvgToLonLat(vx, vy, svgCenter, svgSpanLon, svgW, svgH);
    pushSnapshot([...vertices, coord], false);
  };

  const handleSvgMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const [vx, vy] = svgClientToViewbox(e);
    if (svgDragIdx !== null) {
      const coord = unprojectSvgToLonLat(vx, vy, svgCenter, svgSpanLon, svgW, svgH);
      setVertices((prev) => prev.map((pt, i) => (i === svgDragIdx ? coord : pt)));
      return;
    }
    if (!isClosed && vertices.length >= 1) {
      const coord = unprojectSvgToLonLat(vx, vy, svgCenter, svgSpanLon, svgW, svgH);
      setHoverCoord(coord);
      if (vertices.length >= 3 && svgProjectedVertices[0]) {
        const d = Math.hypot(vx - svgProjectedVertices[0][0], vy - svgProjectedVertices[0][1]);
        setSnapToFirst(d <= 18);
      }
    }
  };

  const svgHoverPt = useMemo(() => {
    if (!hoverCoord) return null;
    return projectRingLatLonToSvg([hoverCoord], svgCenter, svgSpanLon, svgW, svgH)[0];
  }, [hoverCoord, svgCenter, svgSpanLon]);

  const statusText = useMemo(() => {
    if (selfIntersects) return t.statusSelfIntersect;
    if (!insideGuelma) return t.statusOutsideGuelma;
    if (!isClosed || vertices.length < 3) return t.statusNeedVertices;
    return t.statusReady;
  }, [selfIntersects, insideGuelma, isClosed, vertices.length, t]);

  return (
    <div
      className="relative flex h-screen min-h-[680px] w-full flex-col overflow-hidden bg-[#EEF3EF] text-[#111813] dark:bg-[#121713] dark:text-[#F5F7F5]"
      data-testid="guelma-border-editor"
    >
      {/* Top Floating CAD Bar */}
      <header className="relative z-30 flex flex-wrap items-center justify-between gap-2.5 border-b border-[#111813]/10 bg-white/85 px-2 py-1.5 backdrop-blur-4xl dark:border-white/10 dark:bg-[#121713]/85">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onBack}
            data-testid="border-editor-back"
            className="fs-liquid-pill inline-flex min-h-9 items-center gap-2.5 rounded-full px-3.5 text-xs font-semibold text-[#111813] dark:text-[#F5F7F5] active:not-disabled:scale-[0.97]"
          >
            {t.backDashboard}
          </button>
          <div>
            <h2 className="p-1 text-sm font-semibold text-[#111813] dark:text-[#F5F7F5]">
              {mode === "edit" ? t.editBordersTitle : t.newFieldTitle}
            </h2>
            <p className="hidden text-[11px] text-[#4A5A4E] dark:text-[#9CA89E] md:block">{t.subtitle}</p>
          </div>
        </div>

        {/* 34-Commune Searchable Fly-To Combobox */}
        <div className="relative min-w-[230px] max-w-sm flex-1">
          <div className="relative flex items-center">
            <MagnifyingGlass
              size={15}
              className="pointer-events-none absolute start-3 text-[#15803D] dark:text-[#86EFAC]"
              aria-hidden="true"
            />
            <input
              type="text"
              value={communeQuery}
              onFocus={() => setCommuneDropdownOpen(true)}
              onChange={(e) => {
                setCommuneQuery(e.target.value);
                setCommuneDropdownOpen(true);
              }}
              placeholder={t.searchCommune}
              data-testid="commune-search-input"
              className="min-h-10 w-full rounded-full border border-[#111813]/15 bg-white/95 py-1.5 pe-9 ps-9 text-base text-[#111813] placeholder:text-[#4A5A4E] transition-[border-color] focus:border-[#15803D] focus:outline-none dark:border-white/15 dark:bg-[#141A16]/90 dark:text-[#F5F7F5] dark:placeholder:text-[#9CA89E] dark:focus:border-[#86EFAC]/60 sm:text-xs"
            />
            {communeQuery ? (
              <button
                type="button"
                aria-label="Clear search"
                onClick={() => {
                  setCommuneQuery("");
                  setCommuneDropdownOpen(true);
                }}
                className="absolute end-1.5 flex h-8 w-8 items-center justify-center rounded-full text-[#4A5A4E] transition-colors hover:text-[#111813] dark:text-[#9CA89E] dark:hover:text-white"
              >
                <X size={13} aria-hidden="true" />
              </button>
            ) : null}
          </div>

          {communeDropdownOpen ? (
            <div
              className="fs-hud-glass absolute start-0 top-full z-40 mt-1.5 max-h-64 w-full overflow-y-auto rounded-2xl p-1.5 shadow-2xl"
              data-testid="commune-dropdown"
            >
              <div className="flex items-center justify-between px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-[#15803D] dark:text-[#86EFAC]">
                <span>{t.allCommunesLabel(GUELMA_COMMUNES.length)}</span>
                <button
                  type="button"
                  onClick={() => setCommuneDropdownOpen(false)}
                  aria-label="Close commune menu"
                  className="flex h-7 w-7 items-center justify-center rounded-full text-[#4A5A4E] transition-colors hover:text-[#111813] dark:text-[#9CA89E] dark:hover:text-white"
                >
                  <X size={12} aria-hidden="true" />
                </button>
              </div>
              {filteredCommunes.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => handleJumpToCommune(c)}
                  className="flex min-h-9 w-full items-center justify-between rounded-xl px-2.5 py-1.5 text-start text-xs text-[#111813] transition-[background-color] hover:bg-[#111813]/[0.06] dark:text-[#F5F7F5] dark:hover:bg-white/[0.10]"
                >
                  <span className="font-medium">{c.name[lang] || c.name.en}</span>
                  <span className="text-[10px] text-[#4A5A4E] dark:text-[#9CA89E]">
                    {c.daira[lang] || c.daira.en}
                  </span>
                </button>
              ))}
            </div>
          ) : null}
        </div>

        {/* Layer & 2D/3D Controls */}
        <div className="flex items-center gap-1.5">
          <div className="inline-flex rounded-full border border-[#111813]/12 bg-[#111813]/[0.06] p-0.5 text-[11px] font-semibold dark:border-white/12 dark:bg-black/35">
            {(["none", "ndvi", "sm"] as const).map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => setOverlay(k)}
                className={`min-h-9 rounded-full px-3 transition-[background-color,color] ${
                  overlay === k
                    ? "bg-[#0B3D2E] text-white shadow-xs dark:bg-[#FFFFFF] dark:text-[#111713]"
                    : "text-[#4A5A4E] hover:text-[#111813] dark:text-[#9CA89E] dark:hover:text-white"
                }`}
              >
                {k === "none" ? "RGB" : k.toUpperCase()}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setTilt3d((v) => !v)}
            className={`inline-flex min-h-9 items-center gap-1 rounded-full border px-3 text-[11px] font-semibold transition-[background-color,border-color,color] ${
              tilt3d
                ? "border-[#0B3D2E] bg-[#0B3D2E] text-white shadow-xs dark:border-white dark:bg-[#FFFFFF] dark:text-[#111713]"
                : "border-[#111813]/15 bg-[#111813]/[0.06] text-[#243227] hover:text-[#111813] dark:border-white/15 dark:bg-black/35 dark:text-[#D1DBD3] dark:hover:text-white"
            }`}
          >
            <Cube size={14} aria-hidden="true" />
            <span>{tilt3d ? t.view3d : t.view2d}</span>
          </button>
        </div>
      </header>

      {/* Main Map Viewport */}
      <div className="relative flex-1 overflow-hidden">
        {!webglFailed ? (
          <div ref={mapContainerRef} className="h-full w-full" />
        ) : (
          /* Precision Headless/No-WebGL Geo-Projected SVG Canvas */
          <svg
            viewBox={`0 0 ${svgW} ${svgH}`}
            onClick={handleSvgClick}
            onMouseMove={handleSvgMouseMove}
            onMouseUp={() => {
              if (svgDragIdx !== null) {
                pushSnapshot(vertices, isClosed);
                setSvgDragIdx(null);
              }
            }}
            data-testid="border-editor-svg-canvas"
            className="h-full w-full cursor-crosshair bg-[#EEF3EF] dark:bg-[#121713]"
          >
            <defs>
              <pattern id="cad-grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path
                  d="M 40 0 L 0 0 0 40"
                  fill="none"
                  stroke={isDarkTheme ? "rgba(167,243,208,0.12)" : "rgba(11,61,46,0.10)"}
                  strokeWidth="1"
                />
              </pattern>
            </defs>
            <rect width={svgW} height={svgH} fill="url(#cad-grid)" />
            <text
              x="16"
              y="26"
              fill={isDarkTheme ? "rgba(167,243,208,0.65)" : "#15803D"}
              fontSize="12"
              fontWeight="600"
            >
              {t.svgFallbackNotice} · {activeCommune.name[lang] || activeCommune.name.en} (
              {svgCenter[1].toFixed(4)}° N, {svgCenter[0].toFixed(4)}° E)
            </text>

            {/* Closed polygon fill */}
            {isClosed && svgProjectedVertices.length >= 3 ? (
              <polygon
                points={svgProjectedVertices.map(([x, y]) => `${x},${y}`).join(" ")}
                fill={
                  selfIntersects || !insideGuelma
                    ? isDarkTheme
                      ? "rgba(239,68,68,0.28)"
                      : "rgba(220,38,38,0.20)"
                    : isDarkTheme
                      ? "rgba(34,197,94,0.28)"
                      : "rgba(22,163,74,0.22)"
                }
                stroke={
                  selfIntersects || !insideGuelma
                    ? isDarkTheme
                      ? "#FCA5A5"
                      : "#DC2626"
                    : isDarkTheme
                      ? "#ECFDF5"
                      : "#0B3D2E"
                }
                strokeWidth="2.5"
                strokeLinejoin="round"
              />
            ) : null}

            {/* Open polyline */}
            {!isClosed && svgProjectedVertices.length >= 2 ? (
              <polyline
                points={svgProjectedVertices.map(([x, y]) => `${x},${y}`).join(" ")}
                fill="none"
                stroke={isDarkTheme ? "#ECFDF5" : "#0B3D2E"}
                strokeWidth="2.4"
              />
            ) : null}

            {/* Rubber-band preview line */}
            {!isClosed && svgHoverPt && svgProjectedVertices.length >= 1 ? (
              <line
                x1={svgProjectedVertices[svgProjectedVertices.length - 1][0]}
                y1={svgProjectedVertices[svgProjectedVertices.length - 1][1]}
                x2={snapToFirst ? svgProjectedVertices[0][0] : svgHoverPt[0]}
                y2={snapToFirst ? svgProjectedVertices[0][1] : svgHoverPt[1]}
                stroke={isDarkTheme ? "#86EFAC" : "#15803D"}
                strokeWidth="1.8"
                strokeDasharray="6 4"
              />
            ) : null}

            {/* Midpoint + insertion handles */}
            {svgMidpoints.map((mp) => (
              <g
                key={mp.insertIndex}
                onClick={(ev) => {
                  ev.stopPropagation();
                  const next = [
                    ...vertices.slice(0, mp.insertIndex),
                    mp.coord,
                    ...vertices.slice(mp.insertIndex),
                  ];
                  pushSnapshot(next, true);
                }}
                style={{ cursor: "pointer" }}
              >
                <circle
                  cx={mp.svgPt[0]}
                  cy={mp.svgPt[1]}
                  r="8"
                  fill="rgba(11,75,46,0.9)"
                  stroke={isDarkTheme ? "#ECFDF5" : "#FFFFFF"}
                  strokeWidth="1.5"
                />
                <text
                  x={mp.svgPt[0]}
                  y={mp.svgPt[1] + 4}
                  textAnchor="middle"
                  fill="#ECFDF5"
                  fontSize="12"
                  fontWeight="700"
                >
                  +
                </text>
              </g>
            ))}

            {/* Draggable vertex handles */}
            {svgProjectedVertices.map(([vx, vy], idx) => (
              <g
                key={idx}
                onMouseDown={(ev) => {
                  ev.stopPropagation();
                  setSvgDragIdx(idx);
                  setSelectedIdx(idx);
                }}
                onClick={(ev) => {
                  ev.stopPropagation();
                  if (!isClosed && idx === 0 && vertices.length >= 3) {
                    pushSnapshot(vertices, true);
                  } else {
                    setSelectedIdx(idx);
                  }
                }}
                style={{ cursor: "grab" }}
              >
                <circle
                  cx={vx}
                  cy={vy}
                  r={idx === 0 && snapToFirst ? 12 : 10}
                  fill={idx === 0 ? "#137135" : idx === selectedIdx ? "#0F172A" : "#0B4B2E"}
                  stroke={idx === selectedIdx ? "#FDE047" : "#FFFFFF"}
                  strokeWidth="2"
                />
                <text
                  x={vx}
                  y={vy + 3.5}
                  textAnchor="middle"
                  fill="#FFFFFF"
                  fontSize="10"
                  fontWeight="700"
                >
                  {idx + 1}
                </text>
              </g>
            ))}
          </svg>
        )}

        {/* Quick Guelma Sample Borders Toolbar (Top-Left Overlay) */}
        <div className="pointer-events-none absolute start-3 top-3 z-20 flex flex-col gap-2">
          <div className="fs-hud-glass pointer-events-auto flex flex-wrap items-center gap-1.5 rounded-2xl p-2 shadow-xl">
            <span className="px-1.5 text-[10px] font-semibold uppercase tracking-wider text-[#15803D] dark:text-[#86EFAC]">
              {t.quickPresetLabel}:
            </span>
            {GUELMA_PARCEL_PRESETS.slice(0, 5).map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => handleApplyQuickPreset(p.id)}
                data-testid={`quick-border-${p.id}`}
                className="min-h-9 rounded-xl border border-[#111813]/12 bg-[#111813]/[0.05] px-2.5 py-1 text-[11px] font-medium text-[#111813] transition-[background-color,border-color] hover:border-[#15803D]/50 hover:bg-[#111813]/[0.10] dark:border-white/12 dark:bg-white/[0.06] dark:text-[#F5F7F5] dark:hover:border-[#86EFAC]/40 dark:hover:bg-white/[0.14]"
              >
                {p.commune} · {p.areaHectares} ha
              </button>
            ))}
          </div>

          <div className="pointer-events-auto flex max-w-sm flex-wrap items-center gap-2 rounded-xl border border-[#111813]/10 bg-white/90 px-4 py-2 text-[11px] text-[#243227] backdrop-blur-md dark:border-white/10 dark:bg-[#121713]/85 dark:text-[#D1DBD3]">
            <Crosshair size={15} className="shrink-0 text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
            <span>
              {isClosed
                ? t.hintAdjustVertices
                : vertices.length >= 3
                ? t.hintSnapClose
                : t.hintAddVertex}
            </span>
          </div>
        </div>

        {/* Precision Telemetry & CAD Action Dock (Bottom / Side HUD) */}
        <aside className="fs-hud-glass pointer-events-auto absolute bottom-3 end-3 z-20 w-[330px] max-w-[calc(100vw-24px)] rounded-2xl p-3.5 shadow-[0_24px_60px_rgba(11,61,46,0.16)] dark:shadow-[0_24px_60px_rgba(0,0,0,0.65)]">
          {/* Verification Status Pill */}
          <div
            className={`flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-semibold ${
              selfIntersects || !insideGuelma
                ? "border border-red-600/30 bg-red-50/95 text-red-800 dark:border-red-400/30 dark:bg-red-500/20 dark:text-red-200"
                : canSave
                ? "border border-[#15803D]/35 bg-[#22C55E]/15 text-[#14532D] dark:border-[#4ADE80]/35 dark:bg-[#22C55E]/18 dark:text-[#DCFCE7]"
                : "border border-amber-600/25 bg-amber-50/95 text-amber-900 dark:border-amber-400/25 dark:bg-amber-500/15 dark:text-amber-200"
            }`}
            data-testid="border-status-pill"
          >
            {selfIntersects || !insideGuelma ? (
              <WarningCircle size={16} weight="fill" className="shrink-0 text-red-600 dark:text-red-300" aria-hidden="true" />
            ) : canSave ? (
              <CheckCircle size={16} weight="fill" className="shrink-0 text-[#15803D] dark:text-[#4ADE80]" aria-hidden="true" />
            ) : (
              <Compass size={16} weight="duotone" className="shrink-0 text-amber-600 dark:text-amber-300" aria-hidden="true" />
            )}
            <span>{statusText}</span>
          </div>

          {/* Numeric Telemetry Grid */}
          <div className="mt-2.5 grid grid-cols-2 gap-2 font-mono text-[11px] tabular-nums">
            <div className="rounded-xl border border-[#111813]/10 bg-[#111813]/[0.04] px-2.5 py-2 dark:border-white/10 dark:bg-white/[0.05]">
              <div className="font-sans text-[10px] text-[#4A5A4E] dark:text-[#9CA89E]">{t.areaLbl}</div>
              <div className="mt-0.5 text-sm font-bold text-[#15803D] dark:text-[#86EFAC]" data-testid="cad-area-value">
                {areaHectares > 0 ? `${areaHectares.toFixed(2)} ha` : "0.00 ha"}
              </div>
            </div>
            <div className="rounded-xl border border-[#111813]/10 bg-[#111813]/[0.04] px-2.5 py-2 dark:border-white/10 dark:bg-white/[0.05]">
              <div className="font-sans text-[10px] text-[#4A5A4E] dark:text-[#9CA89E]">{t.perimLbl}</div>
              <div className="mt-0.5 text-sm font-bold text-[#111813] dark:text-[#F5F7F5]" data-testid="cad-perim-value">
                {perimeterMeters} m
              </div>
            </div>
            <div className="rounded-xl border border-[#111813]/10 bg-[#111813]/[0.04] px-2.5 py-2 dark:border-white/10 dark:bg-white/[0.05]">
              <div className="font-sans text-[10px] text-[#4A5A4E] dark:text-[#9CA89E]">{t.verticesLbl}</div>
              <div className="mt-0.5 text-xs font-bold text-[#111813] dark:text-[#F5F7F5]" data-testid="cad-vertices-count">
                {vertices.length} {isClosed ? "(closed)" : ""}
              </div>
            </div>
            <div className="rounded-xl border border-[#111813]/10 bg-[#111813]/[0.04] px-2.5 py-2 dark:border-white/10 dark:bg-white/[0.05]">
              <div className="font-sans text-[10px] text-[#4A5A4E] dark:text-[#9CA89E]">{t.communeDetectedLbl}</div>
              <div className="mt-0.5 truncate font-sans text-xs font-semibold text-[#243227] dark:text-[#D1DBD3]">
                {nearestCommune.name[lang] || nearestCommune.name.en}
              </div>
            </div>
          </div>

          {/* Non-binding DEM Reference & Centroid */}
          <div className="mt-2 flex items-center justify-between rounded-xl border border-[#111813]/10 bg-[#111813]/[0.04] px-2.5 py-1.5 text-[10px] text-[#243227] dark:border-white/10 dark:bg-black/35 dark:text-[#D1DBD3]">
            <span className="inline-flex items-center gap-1 font-mono tabular-nums" dir="ltr">
              <MapPin size={12} className="text-[#15803D] dark:text-[#86EFAC]" aria-hidden="true" />
              {centroid
                ? `${centroid.latitude.toFixed(4)}° N, ${centroid.longitude.toFixed(4)}° E`
                : `${svgCenter[1].toFixed(4)}° N, ${svgCenter[0].toFixed(4)}° E`}
            </span>
            <span className="font-mono tabular-nums text-[#15803D] dark:text-[#86EFAC]" title={t.demNonBindingNote}>
              {demRef ? `${demRef.elev}m · ${demRef.slope}%` : t.demRefLbl}
            </span>
          </div>

          {/* CAD Action Buttons */}
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={handleUndo}
              disabled={undoStack.length === 0}
              data-testid="cad-undo-btn"
              className="inline-flex min-h-9 items-center gap-1 rounded-xl border border-[#111813]/15 bg-[#111813]/[0.05] px-2.5 py-1.5 text-[11px] font-semibold text-[#111813] transition-[background-color,color] hover:bg-[#111813]/[0.12] disabled:opacity-40 dark:border-white/15 dark:bg-white/[0.08] dark:text-[#F5F7F5] dark:hover:bg-white/[0.16]"
            >
              <ArrowCounterClockwise size={13} aria-hidden="true" />
              <span>{t.undo}</span>
            </button>
            <button
              type="button"
              onClick={handleRedo}
              disabled={redoStack.length === 0}
              className="inline-flex min-h-9 items-center gap-1 rounded-xl border border-[#111813]/15 bg-[#111813]/[0.05] px-2.5 py-1.5 text-[11px] font-semibold text-[#111813] transition-[background-color,color] hover:bg-[#111813]/[0.12] disabled:opacity-40 dark:border-white/15 dark:bg-white/[0.08] dark:text-[#F5F7F5] dark:hover:bg-white/[0.16]"
            >
              <ArrowClockwise size={13} aria-hidden="true" />
              <span>{t.redo}</span>
            </button>
            {!isClosed && vertices.length >= 3 ? (
              <button
                type="button"
                onClick={handleClosePolygon}
                data-testid="cad-close-poly-btn"
                className="inline-flex min-h-9 items-center gap-1 rounded-xl border border-[#15803D]/40 bg-[#22C55E]/15 px-2.5 py-1.5 text-[11px] font-semibold text-[#14532D] transition-[background-color,border-color] hover:bg-[#22C55E]/25 dark:border-[#86EFAC]/45 dark:bg-[#22C55E]/20 dark:text-[#DCFCE7] dark:hover:bg-[#22C55E]/30"
              >
                <Polygon size={13} aria-hidden="true" />
                <span>{t.closePoly}</span>
              </button>
            ) : null}
            {selectedIdx !== null && vertices.length > 3 ? (
              <button
                type="button"
                onClick={() => handleDeleteVertex(selectedIdx)}
                className="inline-flex min-h-9 items-center gap-1 rounded-xl border border-amber-600/35 bg-amber-500/15 px-2.5 py-1.5 text-[11px] font-semibold text-amber-900 transition-[background-color] hover:bg-amber-500/25 dark:border-amber-400/40 dark:bg-amber-500/20 dark:text-amber-200 dark:hover:bg-amber-500/30"
              >
                <span>{t.deleteSelectedVertex}</span>
              </button>
            ) : null}
            <button
              type="button"
              onClick={handleClear}
              disabled={vertices.length === 0}
              data-testid="cad-clear-btn"
              className="inline-flex min-h-9 items-center gap-1 rounded-xl border border-[#111813]/15 bg-[#111813]/[0.04] px-2.5 py-1.5 text-[11px] font-semibold text-red-700 transition-[background-color,border-color] hover:border-red-500/35 hover:bg-red-500/15 disabled:opacity-40 dark:border-white/15 dark:bg-white/[0.06] dark:text-red-200 dark:hover:border-red-400/30 dark:hover:bg-red-500/20"
            >
              <Trash size={13} aria-hidden="true" />
              <span>{t.clear}</span>
            </button>
          </div>

          {/* Primary Save CTA */}
          <button
            type="button"
            disabled={!canSave}
            onClick={handleSaveBorders}
            data-testid="save-my-farm-btn"
            className="fs-cta-primary mt-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-full px-4 text-sm font-semibold active:not-disabled:scale-[0.98] disabled:cursor-not-allowed disabled:bg-[#111813]/10 disabled:text-[#6B7A6F] disabled:shadow-none dark:disabled:bg-white/10 dark:disabled:text-[#78847B]"
          >
            <span>{mode === "edit" ? t.saveUpdatedBorders : t.saveMyFarm}</span>
          </button>
        </aside>
      </div>
    </div>
  );
}
