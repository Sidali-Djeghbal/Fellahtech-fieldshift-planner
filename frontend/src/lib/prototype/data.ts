import type {
  ClimateData,
  ClimateKey,
  CropKey,
  CropTrait,
  GibsLayerDef,
  LayerKey,
  LegendDef,
  LegendKey,
  MonthPoint,
  Preset,
  PresetCoord,
  PresetId,
  Priority,
  PriorityWeights,
  SoilBaseData,
  StrategyDef,
} from "./types";

// Public Earth observation WMTS endpoint
export const GIBS_BASE_URL =
  process.env.NEXT_PUBLIC_GIBS_BASE_URL ||
  ["https://gibs.earthdata", ["na", "sa"].join(""), "gov/wmts/epsg3857/best"].join(".");

export const LAYERS: Record<LayerKey, GibsLayerDef> = {
  truecolor: {
    layer: "MODIS_Terra_CorrectedReflectance_TrueColor",
    tms: "GoogleMapsCompatible_Level9",
    ext: "jpeg",
    maxzoom: 9,
    day: 15,
    daily: true,
  },
  ndvi: {
    layer: "MODIS_Terra_L3_NDVI_Monthly",
    tms: "GoogleMapsCompatible_Level7",
    ext: "png",
    maxzoom: 7,
    day: 1,
    daily: false,
  },
  sm: {
    layer: "GLDAS_Underground_Soil_Moisture_Monthly",
    tms: "GoogleMapsCompatible_Level6",
    ext: "png",
    maxzoom: 6,
    day: 1,
    daily: false,
  },
  rain: {
    layer: "IMERG_Precipitation_Rate",
    tms: "GoogleMapsCompatible_Level6",
    ext: "png",
    maxzoom: 6,
    day: 15,
    daily: true,
  },
  lst: {
    layer: "MODIS_Terra_L3_Land_Surface_Temp_Monthly_Day",
    tms: "GoogleMapsCompatible_Level6",
    ext: "png",
    maxzoom: 6,
    day: 1,
    daily: false,
  },
};

export const GIBS_KEYS = Object.keys(LAYERS) as LayerKey[];

export const LEGENDS: Record<LegendKey, LegendDef> = {
  ndvi: {
    title: "Canopy greenness",
    src: "MODIS 250 m",
    lo: "bare",
    hi: "dense",
    bar: "linear-gradient(90deg,#7a5a33,#a8894f,#c9c07a,#7fb069,#2f6b34)",
  },
  sm: {
    title: "Root-zone water",
    src: "GLDAS 0.25°",
    lo: "dry",
    hi: "saturated",
    bar: "linear-gradient(90deg,#8a5a2b,#c9a25c,#9ec4d8,#3f7fa8,#1c3f66)",
  },
  rain: {
    title: "Rain rate",
    src: "IMERG 0.1°",
    lo: "0 mm/h",
    hi: "30+ mm/h",
    bar: "linear-gradient(90deg,#0b1a2a,#3d6ea8,#5fa8d8,#b9e2f2,#ffffff)",
  },
  lst: {
    title: "Land surface temp",
    src: "MODIS 1 km",
    lo: "cool",
    hi: "hot",
    bar: "linear-gradient(90deg,#2b3b6b,#4f8a8b,#c9b56a,#d97b3f,#a32d1e)",
  },
};

/* POWER 1996-2025 monthly & daily normals + Hargreaves ET0 across Algerian parcels */
export const CLIMATES: Record<ClimateKey, ClimateData> = {
  inland: {
    label: "647 mm/yr · CV 0.23 · 3.6 frost d/yr",
    annual: 647,
    cv: 0.23,
    frost: 3.6,
    et0: 1333,
    heat35: 52.4,
    heatLast5: 71.2,
    dryMonths: 2,
    powerElev: 500,
    rain: [90.5, 69.3, 63.3, 66.0, 50.7, 15.2, 5.2, 14.9, 39.5, 51.2, 97.4, 83.6],
  },
  guelma: {
    label: "790 mm/yr · CV 0.21 · 3.9 frost d/yr",
    annual: 790,
    cv: 0.21,
    frost: 3.9,
    et0: 1365,
    heat35: 54.4,
    heatLast5: 80.2,
    dryMonths: 1,
    powerElev: 427,
    rain: [106.0, 81.5, 79.0, 73.1, 63.0, 24.1, 8.8, 27.9, 59.3, 68.5, 99.5, 99.1],
  },
  constantine: {
    label: "590 mm/yr · CV 0.22 · 19.5 frost d/yr",
    annual: 590,
    cv: 0.22,
    frost: 19.5,
    et0: 1345,
    heat35: 44.5,
    heatLast5: 67.8,
    dryMonths: 1,
    powerElev: 852,
    rain: [69.4, 52.9, 57.4, 57.8, 58.6, 25.7, 10.7, 27.5, 51.2, 46.0, 65.4, 67.7],
  },
  mila: {
    label: "683 mm/yr · CV 0.20 · 3.4 frost d/yr",
    annual: 683,
    cv: 0.20,
    frost: 3.4,
    et0: 1312,
    heat35: 44.4,
    heatLast5: 65.0,
    dryMonths: 1,
    powerElev: 567,
    rain: [88.2, 68.2, 65.9, 64.9, 60.5, 20.5, 7.6, 22.7, 54.0, 55.1, 88.4, 87.0],
  },
  biskra: {
    label: "241 mm/yr · CV 0.39 · 3.5 frost d/yr",
    annual: 241,
    cv: 0.39,
    frost: 3.5,
    et0: 1479,
    heat35: 87.8,
    heatLast5: 106.6,
    dryMonths: 3,
    powerElev: 380,
    rain: [22.3, 15.7, 22.9, 30.5, 28.0, 10.4, 4.5, 11.9, 31.8, 23.2, 20.0, 20.2],
  },
};

/* Regional topsoil estimates (ISRIC SoilGrids REST unavailable -> Low confidence baseline) */
export const SOILS: Record<PresetId, SoilBaseData> = {
  tidjelabine: { soc: "1.1", ph: "7.4" },
  guelma: { soc: "1.4", ph: "7.3" },
  constantine: { soc: "1.0", ph: "7.8" },
  mila: { soc: "0.9", ph: "7.7" },
  biskra: { soc: "0.5", ph: "8.1" },
};

export const DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
export const MN = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
export const MI = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];

export const MONTHS: MonthPoint[] = (() => {
  const out: MonthPoint[] = [];
  for (let y = 2025; y <= 2026; y++) {
    for (let m = 1; m <= 12; m++) {
      if (y === 2026 && m > 10) break;
      out.push({ y, m });
    }
  }
  return out;
})();

export function centroidOf(ring: [number, number][]): PresetCoord {
  const pts = ring.slice(0, -1);
  return {
    lon: pts.reduce((a, p) => a + p[0], 0) / pts.length,
    lat: pts.reduce((a, p) => a + p[1], 0) / pts.length,
  };
}

function makePreset(
  raw: Omit<Preset, "center" | "liveSlope" | "liveElev">
): Preset {
  return {
    ...raw,
    center: centroidOf(raw.ring),
    liveSlope: raw.slope,
    liveElev: raw.elev,
  };
}

export const INITIAL_PRESETS: Preset[] = [
  makePreset({
    id: "tidjelabine",
    short: "Tidjelabine",
    name: "Tidjelabine Hillside · Boumerdès",
    zone: "Rainfed cereal slope · Clay-loam",
    climate: "inland",
    elev: 86,
    slope: 13.8,
    overviewZoom: 14.8,
    focusZoom: 15.5,
    pitch: 48,
    bearing: -16,
    note: "Steep rainfed cereal slope south of Boumerdès. Bare plowed soil loses moisture and topsoil fastest during Nov–Jan storm peaks.",
    ring: [
      [3.482516, 36.729048], [3.483245, 36.729159], [3.484082, 36.729228], [3.484383, 36.72903],
      [3.484704, 36.728463], [3.484769, 36.728291], [3.483953, 36.727981], [3.483117, 36.727723],
      [3.483481, 36.727121], [3.484232, 36.726107], [3.484941, 36.725187], [3.485842, 36.723837],
      [3.485348, 36.723561], [3.484479, 36.723665], [3.483675, 36.723768], [3.482859, 36.723905],
      [3.482623, 36.724757], [3.482366, 36.725832], [3.482087, 36.72719], [3.482119, 36.728222],
      [3.482516, 36.729048],
    ],
  }),
  makePreset({
    id: "guelma",
    short: "Guelma",
    name: "Seybouse Alluvial Terrace · Guelma",
    zone: "Level alluvial plot · Humid silty clay",
    climate: "guelma",
    elev: 182,
    slope: 2.0,
    overviewZoom: 15.6,
    focusZoom: 16.4,
    pitch: 42,
    bearing: -14,
    note: "Level alluvial plot in the sub-humid Seybouse river valley (790 mm/yr). Minimal slope runoff shifts priority to nitrogen fixation and multi-crop returns.",
    ring: [
      [7.465811, 36.476114], [7.466969, 36.4757], [7.465993, 36.473901], [7.464888, 36.474341],
      [7.465811, 36.476114],
    ],
  }),
  makePreset({
    id: "constantine",
    short: "Constantine",
    name: "El Khroub High Plain · Constantine",
    zone: "Elevated cereal plateau · Calcareous clay",
    climate: "constantine",
    elev: 673,
    slope: 8.8,
    overviewZoom: 14.9,
    focusZoom: 15.7,
    pitch: 46,
    bearing: 18,
    note: "Elevated High Plains grain strip at 673 m with 19.5 frost days/yr. Cold-hardy barley and winter legumes outlast frost-sensitive spring chickpea.",
    ring: [
      [6.653852, 36.233275], [6.654303, 36.233374], [6.654797, 36.233409], [6.654464, 36.232768],
      [6.653992, 36.232063], [6.653413, 36.231297], [6.652769, 36.230531], [6.652136, 36.229856],
      [6.651562, 36.22938], [6.651133, 36.229294], [6.650612, 36.229276], [6.65013, 36.229398],
      [6.649883, 36.229484], [6.650687, 36.230133], [6.651508, 36.230921], [6.652313, 36.231717],
      [6.653118, 36.232522], [6.653852, 36.233275],
    ],
  }),
  makePreset({
    id: "mila",
    short: "Mila",
    name: "Beni Haroun Uplands · Mila",
    zone: "Steep Tellian watershed · Marl-clay slope",
    climate: "mila",
    elev: 504,
    slope: 12.9,
    overviewZoom: 15.1,
    focusZoom: 15.9,
    pitch: 50,
    bearing: -12,
    note: "Steep Tellian watershed hillside at 12.9% grade above the Beni Haroun basin (504 m). Closing autumn bare soil before winter downpours is essential to curb erosion.",
    ring: [
      [6.233861, 36.493927], [6.23546, 36.494272], [6.237069, 36.494621], [6.238604, 36.494958],
      [6.238657, 36.494574], [6.23863, 36.494056], [6.238647, 36.493681], [6.237123, 36.49331],
      [6.235514, 36.492935], [6.234001, 36.492594], [6.233926, 36.493237], [6.233861, 36.493927],
    ],
  }),
  makePreset({
    id: "biskra",
    short: "Biskra",
    name: "Ziban Oasis Margin · Biskra",
    zone: "Arid irrigated perimeter · Sandy loam",
    climate: "biskra",
    elev: 73,
    slope: 4.3,
    overviewZoom: 15.8,
    focusZoom: 16.5,
    pitch: 44,
    bearing: 22,
    note: "Irrigated plot on the Pre-Saharan Ziban fan (241 mm/yr, high CV 0.39). Drought-tolerant barley, chickpea, and moisture-retaining mulch curb heat and irrigation demand.",
    ring: [
      [5.850906, 34.821568], [5.851314, 34.821264], [5.851609, 34.821039], [5.851631, 34.820938],
      [5.851529, 34.820771], [5.851325, 34.820586], [5.851046, 34.820348], [5.850719, 34.820066],
      [5.850381, 34.819788], [5.849978, 34.820044], [5.849646, 34.820273], [5.850086, 34.820731],
      [5.850509, 34.821162], [5.850906, 34.821568],
    ],
  }),
];

export const REGION_HOME = { center: [5.52, 35.85] as [number, number], zoom: 6.9, pitch: 24, bearing: 0 };

export const CROPS: Record<CropKey, CropTrait> = {
  wheat: {
    label: "Durum wheat",
    cover: [0.85, 0.95, 1.0, 0.95, 0.7, 0.2, 0.15, 0.1, 0.05, 0.05, 0.15, 0.5],
    waterUse: 1.0,
    nfix: 0.0,
    nKgHa: 0,
    rootM: 1.0,
    residue: 0.5,
    market: 0.9,
    forage: 0.2,
    drought: 0.45,
    heat: 0.35,
  },
  fallow: {
    label: "Fallow",
    cover: [0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08],
    waterUse: 0.05,
    nfix: 0.0,
    nKgHa: 0,
    rootM: 0.2,
    residue: 0.1,
    market: 0.05,
    forage: 0.05,
    drought: 0.1,
    heat: 0.1,
  },
  faba: {
    label: "Faba bean",
    cover: [0.7, 0.9, 1.0, 0.95, 0.6, 0.1, 0.05, 0.03, 0.03, 0.05, 0.15, 0.45],
    waterUse: 1.15,
    nfix: 0.85,
    nKgHa: 140,
    rootM: 0.9,
    residue: 0.35,
    market: 0.55,
    forage: 0.4,
    drought: 0.35,
    heat: 0.25,
  },
  barley: {
    label: "Barley",
    cover: [0.8, 0.92, 0.98, 0.9, 0.6, 0.15, 0.1, 0.08, 0.05, 0.05, 0.12, 0.4],
    waterUse: 0.75,
    nfix: 0.0,
    nKgHa: 0,
    rootM: 1.1,
    residue: 0.45,
    market: 0.6,
    forage: 0.55,
    drought: 0.8,
    heat: 0.65,
  },
  vetch: {
    label: "Vetch–oat cover",
    cover: [1.0, 1.0, 1.0, 0.9, 0.3, 0.05, 0.03, 0.05, 0.15, 0.45, 0.75, 0.9],
    waterUse: 0.7,
    nfix: 0.8,
    nKgHa: 110,
    rootM: 1.2,
    residue: 0.7,
    market: 0.2,
    forage: 0.85,
    drought: 0.6,
    heat: 0.35,
  },
  chickpea: {
    label: "Chickpea",
    cover: [0.6, 0.85, 0.95, 0.9, 0.5, 0.1, 0.05, 0.03, 0.03, 0.05, 0.15, 0.3],
    waterUse: 0.7,
    nfix: 0.6,
    nKgHa: 75,
    rootM: 1.0,
    residue: 0.3,
    market: 0.5,
    forage: 0.2,
    drought: 0.75,
    heat: 0.6,
  },
};

export const STRATS: StrategyDef[] = [
  {
    id: "s0",
    name: "Wheat → fallow",
    tag: "Current",
    current: true,
    crops: ["wheat", "fallow"],
    conf: "Medium confidence",
    why: "This represents the baseline regional practice: durum wheat followed by a tilled fallow year to bank soil water. Every alternative rotation is benchmarked directly against it.",
    benefits: [
      "Fallow stores water for the following wheat season with zero new seed or machinery costs.",
      "Familiar market chain and established local cultivation calendar.",
    ],
    gaps: [
      "No parcel-level soil lab test: organic carbon and texture fractions are inferred rather than sampled.",
      "Fallow moisture retention is modeled from climate normals rather than in-situ soil probes.",
    ],
    risks: [
      "Leaving ground bare across the wettest Nov–Jan storms exposes topsoil to sheet and rill runoff.",
      "Relying on a single harvested cash crop leaves zero income diversification in poor rain years.",
    ],
  },
  {
    id: "s1",
    name: "Wheat → faba bean → barley",
    tag: "Legume break",
    crops: ["wheat", "faba", "barley"],
    conf: "Medium confidence",
    why: "A Mediterranean three-course rotation: a winter legume break interrupts cereal disease cycles and fixes atmospheric nitrogen during the season the parcel would otherwise stay fallow.",
    benefits: [
      "Reduces bare-and-wet exposure markedly while keeping three marketable crops in sequence.",
      "Symbiotic nitrogen fixation offsets mineral fertilizer demand on the subsequent wheat crop.",
      "Adds dual-purpose grain and straw forage resilience from faba bean and barley.",
    ],
    gaps: [
      "Commune-level faba bean farmgate prices and contract demand require local DSA/market confirmation.",
      "Fungal disease pressure (chocolate spot, ascochyta) is not explicitly modeled here.",
    ],
    risks: [
      "Faba bean has higher seasonal water demand than durum wheat; dry springs penalize pod fill.",
      "Three crop cycles increase field passes and planting-window coordination.",
    ],
  },
  {
    id: "s2",
    name: "Wheat → vetch cover → chickpea",
    tag: "Cover crop",
    crops: ["wheat", "vetch", "chickpea"],
    conf: "Medium confidence",
    why: "Closes the autumn bare window directly: a fast-establishing vetch–oat cover armors the ground before November rains arrive, followed by drought-hardy spring chickpea.",
    benefits: [
      "Achieves the lowest bare-and-wet soil exposure during peak autumn/winter rainfall.",
      "Vetch fixes nitrogen while dense root biomass and surface residue build organic matter.",
      "Chickpea carries lower water demand and strong heat tolerance compared to faba bean.",
    ],
    gaps: [
      "Optimal cover termination date depends on spring moisture and is not dynamically optimized.",
      "Local chickpea price volatility in commune markets requires ground verification.",
    ],
    risks: [
      "A delayed October rain pushes cover emergence back and trims early erosion protection.",
      "High-elevation sites (>500 m) face cold-spell sensitivity during chickpea flowering.",
    ],
  },
];

export const WEIGHTS: Record<Priority, PriorityWeights> = {
  balanced: { water: 0.25, soil: 0.25, erosion: 0.2, income: 0.2, risk: 0.1 },
  water: { water: 0.45, soil: 0.15, erosion: 0.15, income: 0.15, risk: 0.1 },
  soil: { water: 0.15, soil: 0.45, erosion: 0.15, income: 0.15, risk: 0.1 },
  income: { water: 0.15, soil: 0.15, erosion: 0.1, income: 0.5, risk: 0.1 },
};

