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

/* Wilaya of Guelma sub-regional climate normals (1996-2025) & Hargreaves ET0 */
export const CLIMATES: Record<ClimateKey, ClimateData> = {
  seybouse_valley: {
    label: "790 mm/yr · CV 0.21 · 3.9 frost d/yr",
    annual: 790,
    cv: 0.21,
    frost: 3.9,
    et0: 1365,
    heat35: 54.4,
    heatLast5: 80.2,
    dryMonths: 1,
    powerElev: 210,
    rain: [106.0, 81.5, 79.0, 73.1, 63.0, 24.1, 8.8, 27.9, 59.3, 68.5, 99.5, 99.1],
  },
  heliopolis_hills: {
    label: "745 mm/yr · CV 0.22 · 5.1 frost d/yr",
    annual: 745,
    cv: 0.22,
    frost: 5.1,
    et0: 1340,
    heat35: 51.0,
    heatLast5: 75.4,
    dryMonths: 1,
    powerElev: 390,
    rain: [98.0, 77.2, 74.0, 69.5, 60.2, 22.8, 8.2, 25.0, 56.1, 64.5, 94.0, 95.5],
  },
  bouchegouf_basin: {
    label: "710 mm/yr · CV 0.20 · 3.4 frost d/yr",
    annual: 710,
    cv: 0.2,
    frost: 3.4,
    et0: 1355,
    heat35: 56.2,
    heatLast5: 81.0,
    dryMonths: 1,
    powerElev: 245,
    rain: [94.5, 74.0, 71.2, 66.8, 56.4, 21.0, 7.6, 22.9, 53.5, 62.0, 89.6, 90.5],
  },
  oued_zenati: {
    label: "585 mm/yr · CV 0.23 · 11.4 frost d/yr",
    annual: 585,
    cv: 0.23,
    frost: 11.4,
    et0: 1335,
    heat35: 46.8,
    heatLast5: 69.2,
    dryMonths: 2,
    powerElev: 615,
    rain: [74.2, 58.6, 60.4, 59.8, 52.4, 21.5, 9.4, 24.1, 49.5, 50.2, 62.5, 62.4],
  },
  tamlouka_plains: {
    label: "470 mm/yr · CV 0.26 · 15.8 frost d/yr",
    annual: 470,
    cv: 0.26,
    frost: 15.8,
    et0: 1390,
    heat35: 58.6,
    heatLast5: 78.9,
    dryMonths: 2,
    powerElev: 740,
    rain: [57.0, 44.5, 48.2, 47.0, 42.1, 17.5, 7.8, 19.6, 41.2, 41.8, 51.3, 52.0],
  },
};

/* Baseline Guelma zone reference organic carbon / pH when parcel soil lab data is unverified */
export const SOILS: Record<string, SoilBaseData> = {
  seybouse: { soc: "1.4", ph: "7.3" },
  heliopolis: { soc: "1.2", ph: "7.5" },
  bouchegouf: { soc: "1.3", ph: "7.2" },
  oz: { soc: "1.0", ph: "7.7" },
  tamlouka: { soc: "0.9", ph: "7.8" },
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
    id: "seybouse",
    short: "Seybouse",
    name: "Seybouse Alluvial Terrace · Guelma",
    zone: "Level alluvial plot · Humid silty clay",
    commune: "Guelma",
    climate: "seybouse_valley",
    elev: 215,
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
    id: "heliopolis",
    short: "Héliopolis",
    name: "Héliopolis Hillside · Guelma",
    zone: "Sub-humid foothill · Loam-clay slope",
    commune: "Héliopolis",
    climate: "heliopolis_hills",
    elev: 390,
    slope: 9.4,
    overviewZoom: 15.3,
    focusZoom: 16.1,
    pitch: 46,
    bearing: -18,
    note: "North-facing foothill parcel near Héliopolis (745 mm/yr). Winter cover crops sharply cut November–January sheet erosion along the slope.",
    ring: [
      [7.47685, 36.49692], [7.47755, 36.49622], [7.47788, 36.49562], [7.47748, 36.49495],
      [7.47522, 36.49352], [7.47462, 36.49402], [7.474, 36.49468], [7.47322, 36.49518],
      [7.47685, 36.49692],
    ],
  }),
  makePreset({
    id: "bouchegouf",
    short: "Bouchegouf",
    name: "Bouchegouf Valley · Guelma East",
    zone: "Eastern alluvial corridor · Clay-loam",
    commune: "Bouchegouf",
    climate: "bouchegouf_basin",
    elev: 195,
    slope: 3.1,
    overviewZoom: 15.2,
    focusZoom: 16.0,
    pitch: 44,
    bearing: 14,
    note: "Eastern Seybouse basin parcel around Bouchegouf (710 mm/yr). Warm spring window favors diverse durum–faba bean–barley rotations.",
    ring: [
      [7.72705, 36.46336], [7.72855, 36.46338], [7.72948, 36.46332], [7.72988, 36.4616],
      [7.73018, 36.46018], [7.72895, 36.45998], [7.728, 36.46], [7.7273, 36.46032],
      [7.7267, 36.4611], [7.72622, 36.46225], [7.72606, 36.46266], [7.72655, 36.4631],
      [7.72705, 36.46336],
    ],
  }),
  makePreset({
    id: "oz",
    short: "Oued Zenati",
    name: "Oued Zenati Slope · Guelma West",
    zone: "Western highland slope · Calcareous loam",
    commune: "Oued Zenati",
    climate: "oued_zenati",
    elev: 625,
    slope: 8.2,
    overviewZoom: 15.4,
    focusZoom: 16.2,
    pitch: 46,
    bearing: -10,
    note: "Rolling cereal belt above Oued Zenati (585 mm/yr, 11.4 frost d/yr). Moisture retention and frost-hardy winter legumes outperform shallow fallow.",
    ring: [
      [7.14896, 36.32086], [7.15202, 36.32128], [7.1523, 36.32055], [7.15226, 36.31962],
      [7.1506, 36.31942], [7.14908, 36.31938], [7.14892, 36.3202], [7.14896, 36.32086],
    ],
  }),
  makePreset({
    id: "tamlouka",
    short: "Tamlouka",
    name: "Tamlouka High Plains · Guelma South",
    zone: "Semi-arid cereal plateau · Sandy clay loam",
    commune: "Tamlouka",
    climate: "tamlouka_plains",
    elev: 745,
    slope: 4.5,
    overviewZoom: 15.5,
    focusZoom: 16.3,
    pitch: 42,
    bearing: 16,
    note: "Southern high plateau near Tamlouka (470 mm/yr, 15.8 frost d/yr). Drought-tolerant barley and deep-rooting vetch-oat forage buffer dry springs.",
    ring: [
      [7.125, 36.14975], [7.12572, 36.14902], [7.12558, 36.1488], [7.12862, 36.14644],
      [7.12782, 36.14585], [7.12426, 36.14894], [7.12465, 36.14942], [7.125, 36.14975],
    ],
  }),
];

export const REGION_HOME = { center: [7.4333, 36.4667] as [number, number], zoom: 9.8, pitch: 24, bearing: 0 };

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

