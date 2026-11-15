import {
  closeRing,
  extractRingFromBoundary,
  findNearestGuelmaCommune,
} from "@/lib/geo/guelma";
import { buildLocalizedFarmPresetFields } from "@/lib/i18n/dynamicText";
import type { FarmPublic, FieldDetailPublic } from "@/lib/schemas";
import {
  CLIMATES,
  CROPS,
  DAYS,
  GIBS_BASE_URL,
  LAYERS,
  WEIGHTS,
} from "./data";
import type {
  EvalResult,
  LayerKey,
  MonthPoint,
  Preset,
  Priority,
  ProtoState,
  StrategyDef,
} from "./types";

const clamp01 = (v: number) => Math.max(0, Math.min(1, v));
const mean = (a: number[]) => a.reduce((s, v) => s + v, 0) / a.length;

export function ringAreaHa(coords: [number, number][]): number {
  const R = 6378137;
  const toRad = Math.PI / 180;
  let total = 0;
  for (let i = 0; i < coords.length - 1; i++) {
    const [x1, y1] = coords[i];
    const [x2, y2] = coords[i + 1];
    total += (x2 - x1) * toRad * (2 + Math.sin(y1 * toRad) + Math.sin(y2 * toRad));
  }
  return Math.abs((total * R * R) / 2) / 10000;
}

export function evaluate(
  strat: StrategyDef,
  scenario: Pick<ProtoState, "rain" | "temp" | "irrigated" | "lowInput">,
  priority: Priority,
  preset: Preset,
  liveDem?: { elev: number; slope: number }
): EvalResult {
  const clim = CLIMATES[preset.climate];
  const rainArr = clim.rain;
  const slope = liveDem?.slope ?? preset.liveSlope ?? preset.slope;
  const rainFactor = 1 + (scenario?.rain || 0) / 100;
  const tempAdd = scenario?.temp || 0;
  const irrigated = Boolean(scenario?.irrigated);
  const lowInput = Boolean(scenario?.lowInput);
  const crops = strat.crops.map((k) => CROPS[k]);

  const cover: number[] = [];
  for (let m = 0; m < 12; m++) {
    cover[m] = mean(crops.map((c) => c.cover[m]));
  }

  let exposureDays = 0;
  let wetDaysTotal = 0;
  const monthlyExposure = [];
  for (let m = 0; m < 12; m++) {
    const wet = Math.min(DAYS[m], (rainArr[m] * rainFactor) / 6);
    wetDaysTotal += wet;
    const expM = (1 - cover[m]) * wet;
    exposureDays += expM;
    monthlyExposure.push({
      rain: rainArr[m] * rainFactor,
      cover: cover[m],
      exp: expM,
    });
  }

  const waterNeed = mean(crops.map((c) => c.waterUse));
  const climWaterSupply = Math.max(
    0.58,
    Math.min(1.16, 0.52 + (clim.annual / 650) * 0.48)
  );
  const effectiveSupply = irrigated
    ? Math.max(climWaterSupply, 0.98)
    : climWaterSupply;
  const water = clamp01(1.25 - (waterNeed / (rainFactor * effectiveSupply)) * 0.75);

  const avgNfix = mean(crops.map((c) => c.nfix));
  const avgNKgHa = Math.round(mean(crops.map((c) => c.nKgHa || 0)));
  const soil = clamp01(
    avgNfix * (lowInput ? 0.52 : 0.45) +
      mean(crops.map((c) => c.residue)) * 0.3 +
      mean(cover) * 0.25
  );

  // Slope scales bare-ground runoff vulnerability (flat 1% plain vs 10%+ hillside)
  const slopePenalty = 1 - Math.min(0.5, slope / 38);
  const erosion = clamp01(
    (1 - exposureDays / Math.max(1, wetDaysTotal)) * slopePenalty
  );

  const inputBonus = lowInput ? avgNfix * 0.16 - (avgNfix === 0 ? 0.08 : 0) : 0;
  const irrCost = irrigated ? waterNeed * 0.06 : 0;
  const income = clamp01(
    mean(crops.map((c) => c.market)) * 0.75 +
      mean(crops.map((c) => c.forage)) * 0.25 +
      (crops.length > 2 ? 0.04 : 0) +
      inputBonus -
      irrCost
  );

  const frostAdj = strat.crops.includes("chickpea")
    ? Math.min(0.14, clim.frost * 0.007)
    : 0;
  const cvAdj = Math.max(0, (clim.cv - 0.24) * 0.42);
  const heatTrendPenalty =
    Math.max(0, ((clim.heatLast5 || 65) - 65) * 0.0022) *
    (1 - mean(crops.map((c) => c.heat)));
  const risk = clamp01(
    mean(crops.map((c) => c.drought)) * (irrigated ? 0.72 : 0.6) +
      mean(crops.map((c) => c.heat)) * 0.4 +
      (crops.length > 2 ? 0.05 : 0) -
      tempAdd * 0.06 -
      frostAdj -
      cvAdj -
      heatTrendPenalty
  );

  const w = WEIGHTS[priority];
  const total = Math.round(
    (water * w.water +
      soil * w.soil +
      erosion * w.erosion +
      income * w.income +
      risk * w.risk) *
      100
  );

  return {
    water,
    soil,
    erosion,
    income,
    risk,
    total,
    cover,
    monthlyExposure,
    avgNKgHa,
    exposureDays: Math.round(exposureDays),
    wetDaysTotal: Math.round(wetDaysTotal),
  };
}

export function dateStrFor(key: LayerKey, { y, m }: MonthPoint): string {
  const L = LAYERS[key];
  return `${y}-${String(m).padStart(2, "0")}-${
    L.daily ? String(L.day).padStart(2, "0") : "01"
  }`;
}

export function gibsUrl(key: LayerKey, date: string): string {
  const L = LAYERS[key];
  return `${GIBS_BASE_URL}/${L.layer}/default/${date}/${L.tms}/{z}/{y}/{x}.${L.ext}`;
}

export function presetFeature(p: Preset) {
  return {
    type: "Feature" as const,
    properties: { id: p.id, name: p.name },
    geometry: { type: "Polygon" as const, coordinates: [p.ring] },
  };
}

export function allPresetsFC(presets: Preset[], activeId: string) {
  return {
    type: "FeatureCollection" as const,
    features: presets.filter((p) => p.id !== activeId).map(presetFeature),
  };
}

function canvasFor(size: number): OffscreenCanvas | HTMLCanvasElement {
  if (typeof OffscreenCanvas !== "undefined") {
    return new OffscreenCanvas(size, size);
  }
  const cv = document.createElement("canvas");
  cv.width = cv.height = size;
  return cv;
}

function decodeImage(blob: Blob): Promise<ImageBitmap | HTMLImageElement> {
  if (typeof createImageBitmap === "function") return createImageBitmap(blob);
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const im = new Image();
    im.onload = () => {
      URL.revokeObjectURL(url);
      resolve(im);
    };
    im.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("DEM decode failed"));
    };
    im.src = url;
  });
}

async function readDemTile(lat: number, lon: number, z: number) {
  const n = 2 ** z;
  const latR = (lat * Math.PI) / 180;
  const xf = ((lon + 180) / 360) * n;
  const yf =
    ((1 - Math.log(Math.tan(latR) + 1 / Math.cos(latR)) / Math.PI) / 2) * n;
  const tx = Math.floor(xf);
  const ty = Math.floor(yf);
  const url = `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/${z}/${tx}/${ty}.png`;

  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), 7000);
  try {
    const res = await fetch(url, {
      signal: ac.signal,
      mode: "cors",
      cache: "force-cache",
    });
    if (!res.ok) throw new Error("DEM " + res.status);
    const bitmap = await decodeImage(await res.blob());
    const cv = canvasFor(256);
    const ctx = cv.getContext("2d", { willReadFrequently: true }) as
      | OffscreenCanvasRenderingContext2D
      | CanvasRenderingContext2D
      | null;
    if (!ctx) throw new Error("2D context unavailable");
    ctx.drawImage(bitmap, 0, 0);
    if ("close" in bitmap && typeof bitmap.close === "function") bitmap.close();
    return {
      data: ctx.getImageData(0, 0, 256, 256).data,
      px: Math.round((xf - tx) * 256),
      py: Math.round((yf - ty) * 256),
      latR,
    };
  } finally {
    clearTimeout(timer);
  }
}

export async function measureCoordFromDem(
  lat: number,
  lon: number
): Promise<{ elev: number; slope: number } | null> {
  const cacheKey = `fieldshift.dem.${lat.toFixed(4)}.${lon.toFixed(4)}`;
  try {
    const cached = sessionStorage.getItem(cacheKey);
    if (cached) {
      const [e, s] = cached.split(",");
      return { elev: Number(e), slope: Number(s) };
    }
  } catch {
    /* ignore storage error */
  }

  const z = 12;
  try {
    const { data, px, py, latR } = await readDemTile(lat, lon, z);
    const at = (x: number, y: number) => {
      const cx = Math.max(0, Math.min(255, x));
      const cy = Math.max(0, Math.min(255, y));
      const i = (cy * 256 + cx) * 4;
      return data[i] * 256 + data[i + 1] + data[i + 2] / 256 - 32768;
    };
    const mpp = (156543.03392 * Math.cos(latR)) / 2 ** z;
    const step = 3;
    const gx = (at(px + step, py) - at(px - step, py)) / (2 * step * mpp);
    const gy = (at(px, py + step) - at(px, py - step)) / (2 * step * mpp);
    const elev = Math.round(at(px, py));
    const slope = Number((Math.hypot(gx, gy) * 100).toFixed(1));
    try {
      sessionStorage.setItem(cacheKey, `${elev},${slope}`);
    } catch {
      /* ignore */
    }
    return { elev, slope };
  } catch {
    return null;
  }
}

export async function measureFromDem(
  preset: Preset
): Promise<{ elev: number; slope: number } | null> {
  return measureCoordFromDem(preset.center.lat, preset.center.lon);
}

/**
 * Converts a farmer-owned Farm + Field record from anywhere in Wilaya of Guelma
 * into a simulator Preset for GIBS inspection, 3D relief probing, and rotation evaluation.
 */
export function fieldToPreset(
  farm: Pick<FarmPublic, "farm_id" | "farm_name" | "commune">,
  field: FieldDetailPublic
): Preset {
  const lat = field.location.latitude;
  const lon = field.location.longitude;
  const communeObj = findNearestGuelmaCommune(lat, lon);
  const extracted = extractRingFromBoundary(field.location.boundary);
  let ring: [number, number][];
  if (extracted.length >= 3) {
    ring = closeRing(extracted);
  } else {
    // Fallback small square proportional to hectares around point centroid
    const halfSpan = Math.max(0.0008, Math.sqrt(field.area_hectares * 10_000) / 220_000);
    ring = closeRing([
      [lon - halfSpan, lat - halfSpan],
      [lon + halfSpan, lat - halfSpan],
      [lon + halfSpan, lat + halfSpan],
      [lon - halfSpan, lat + halfSpan],
    ]);
  }
  const clim = CLIMATES[communeObj.climateZone];
  const elev = field.elevation_m ?? clim.powerElev;
  const latestCrop = field.crop_history[0];
  const commune = farm.commune ?? communeObj.name.en;
  const farmMeta = {
    farmName: farm.farm_name,
    fieldId: field.field_id,
    fieldName: field.field_name,
    commune,
    soilType: field.soil.soil_type,
    irrigationSystem: field.water.irrigation_system,
    waterAvailability: field.water.availability,
    waterSource: field.water.source,
    areaHa: field.area_hectares,
    latestCropId: latestCrop?.crop_id ?? null,
    latestCropRaw: latestCrop?.crop_name_raw ?? null,
    latestCropSeason: latestCrop?.season ?? null,
    latestCropYear: latestCrop?.year ?? null,
  };
  const localized = buildLocalizedFarmPresetFields(farmMeta, "en");

  return {
    id: `${farm.farm_id}::${field.field_id}`,
    short: localized.short,
    name: localized.name,
    zone: localized.zone,
    commune,
    soilType: field.soil.soil_type,
    soilPh: field.soil.soil_ph !== null ? String(field.soil.soil_ph) : null,
    soilOm:
      field.soil.organic_matter_percent !== null
        ? String(field.soil.organic_matter_percent)
        : null,
    areaHa: field.area_hectares,
    farmMeta,
    climate: communeObj.climateZone,
    elev,
    slope: 4.5,
    overviewZoom: 15.4,
    focusZoom: 16.2,
    pitch: 42,
    bearing: -12,
    note: localized.note,
    ring,
    center: { lon, lat },
    liveSlope: 4.5,
    liveElev: elev,
  };
}

