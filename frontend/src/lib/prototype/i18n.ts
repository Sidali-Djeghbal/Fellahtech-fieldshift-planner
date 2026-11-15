import { LEGENDS, MI, MN } from "./data";
import type {
  ClimateData,
  ClimateKey,
  Lang,
  LayerKey,
  LegendDef,
  LegendKey,
  Preset,
  PresetId,
  PriorityWeights,
  ProtoState,
  SoilBaseData,
  StratId,
  StrategyDef,
} from "./types";

export interface GlossaryItem {
  term: string;
  def: string;
}

export interface SoilLoc {
  texture: string;
  omTrend: string;
}

export interface PresetLoc {
  short: string;
  name: string;
  zone: string;
  note: string;
}

export interface StratLoc {
  name: string;
  tag: string;
  conf: string;
  why: string;
  benefits: string[];
  gaps: string[];
  risks: string[];
}

export interface LocaleDict {
  pageTitle: string;
  bootSub: string;
  bootConnect: string;
  bootSlowTiles: string;
  bootSlowNet: string;
  brandRegion: string;
  layerTruecolor: string;
  layerNdvi: string;
  layerSm: string;
  layerRain: string;
  layerLst: string;
  layerTips: Record<LayerKey, string>;
  toolRegion: string;
  toolParcel: string;
  tool3d: string;
  toolClean: string;
  focusTip: string;
  tiltTip: string;
  zenTip: string;
  labTitle: string;
  prioBalanced: string;
  prioWater: string;
  prioSoil: string;
  prioIncome: string;
  scenTitle: string;
  chipBase: string;
  chipDry: string;
  chipShock: string;
  lblRain: string;
  lblTemp: string;
  tabField: string;
  tabCompare: string;
  tabAudit: string;
  toolPlain: string;
  toolGuide: string;
  plainTip: string;
  guideTip: string;
  constRainfed: string;
  constIrrig: string;
  constLowIn: string;
  hlthStressLbl: string;
  hlthSoilLbl: string;
  confPower: string;
  confSoilLow: string;
  plainStress: string;
  plainSoil: string;
  localReviewNote: string;
  mobCompare: string;
  cmpKicker: string;
  cmpTitleFmt: (short: string) => string;
  cmpSubFmt: (scenTxt: string, consTxt: string) => string;
  cmpInspect: string;
  cmpShort: Record<StratId, string>;
  cmpRows: {
    fit: string;
    bareWet: string;
    water: string;
    nfix: string;
    roots: string;
    pest: string;
    stress: string;
    conf: string;
  };
  cmpVals: {
    irrOn: string;
    rainfedMode: string;
    lowInOn: string;
    stdMode: string;
    break0: string;
    break1: string;
    break2: string;
    confMed: string;
    confLowGap: string;
    roots0: string;
    roots1: string;
    roots2: string;
  };
  heatSummaryFmt: (h30: number, h5: number, dryM: number) => string;
  wbSummaryFmt: (
    rain: number,
    et0: number,
    wb: number,
    pElev: number,
    demElev: number
  ) => string;
  soilMetaFmt: (s: SoilBaseData & SoilLoc) => string;
  soils: Record<PresetId, SoilLoc>;
  guideTitle: string;
  guideSub: string;
  guideGlossaryH: string;
  guideFusionH: string;
  guideMathH: string;
  guideValidationNote: string;
  glossaryItems: GlossaryItem[];
  fusionCols: [string, string, string, string];
  fusionRows: [string, string, string, string][];
  mathSummaryFmt: (
    w: PriorityWeights,
    s: ProtoState,
    pName: string,
    clim: ClimateData,
    pElev: number
  ) => string;
  statArea: string;
  statSlope: string;
  statElev: string;
  statRain: string;
  uHa: string;
  uM: string;
  uMm: string;
  ovTitle: string;
  zoomDetail: string;
  showRegion: string;
  provLine1: string;
  provLine2: string;
  backField: string;
  fitSuffix: string;
  fitCard: string;
  hWhy: string;
  hNow: string;
  hEvidence: string;
  hBenefits: string;
  hGaps: string;
  hRisks: string;
  ticks: [string, string, string, string];
  timeKicker: string;
  timePreview: string;
  timeSynced: (layerName: string, dateStr: string) => string;
  sparkLbl: string;
  layerShort: Record<LayerKey, string>;
  disclaimer: string;
  mobMap: string;
  mobLab: string;
  mobField: string;
  mobAudit: string;
  mn: string[];
  mi: string[];
  dims: [string, string, string, string, string];
  auditDims: [string, string, string, string, string];
  wetTag: string;
  growTag: string;
  aridTag: string;
  hotTag: string;
  currentTag: string;
  bestTag: string;
  baselinePill: string;
  baselineBench: string;
  kickerBase: string;
  kickerAlt: string;
  bareWetShort: string;
  bareWetYr: string;
  fitAria: (name: string, total: number) => string;
  deltaShort: (d: number) => string;
  deltaLong: (d: number) => string;
  skyAlts: (ha: string, place: string) => [string, string, string, string];
  scenActive: (r: number, tm: number) => string;
  sparkTip: (mName: string, mm: string) => string;
  presetTip: (p: { name: string; slope: number; elev: number }) => string;
  presetOpt: (p: { name: string; slope: number }) => string;
  ovTip: (mName: string, rain: string, cov: number) => string;
  ovCapBase: (exp: number, slope: string) => string;
  ovCapAlt: (exp: number, saved: number) => string;
  onParcelBase: (
    name: string,
    slope: string,
    elev: number,
    exp: number,
    wet: number
  ) => string;
  onParcelAlt: (
    name: string,
    slope: string,
    elev: number,
    exp: number,
    delta: number
  ) => string;
  evidence: (
    clim: ClimateData,
    peakRain: string,
    peakMonth: string,
    slope: string,
    elev: number,
    pName: string,
    s: StrategyDef
  ) => string[];
  probeTitle: string;
  probeElev: (h: number) => string;
  probeLoading: string;
  climates: Record<ClimateKey, string>;
  legends: Record<LegendKey, LegendDef>;
  presets?: Record<PresetId, PresetLoc>;
  strats?: Record<StratId, StratLoc>;
}

export const I18N: Record<Lang, LocaleDict> = {
  en: {
    pageTitle: "FieldShift — Algeria",
    bootSub: "FieldShift · Algeria",
    bootConnect: "Connecting satellite & terrain",
    bootSlowTiles: "Loading regional tiles…",
    bootSlowNet: "Slow network — streaming regional imagery",
    brandRegion: "Algeria",
    layerTruecolor: "Imagery",
    layerNdvi: "Canopy",
    layerSm: "Soil Water",
    layerRain: "Rainfall",
    layerLst: "Heat",
    layerTips: {
      truecolor: "MODIS Terra True Color (250m)",
      ndvi: "MODIS Canopy Greenness (NDVI)",
      sm: "GLDAS Root-Zone Soil Water",
      rain: "GPM IMERG Precipitation Rate",
      lst: "MODIS Land Surface Heat",
    },
    toolRegion: "Overview",
    toolParcel: "Parcel",
    tool3d: "3D",
    toolClean: "Clean",
    focusTip: "Focus active parcel or zoom out",
    tiltTip: "Toggle 3D terrain tilt",
    zenTip: "Hide or show floating panels",
    labTitle: "Rotation Lab",
    prioBalanced: "Balanced",
    prioWater: "Water",
    prioSoil: "Soil",
    prioIncome: "Income",
    scenTitle: "Climate stress · What if?",
    chipBase: "Baseline",
    chipDry: "Dry −20%",
    chipShock: "Shock",
    lblRain: "Rainfall",
    lblTemp: "Warming",
    tabField: "Field",
    tabCompare: "Compare",
    tabAudit: "Audit",
    toolPlain: "Plain",
    toolGuide: "Guide",
    plainTip: "Toggle farmer-friendly plain language & larger type",
    guideTip: "Open science definitions, data resolution fusion & validation guide",
    constRainfed: "Water: Rainfed",
    constIrrig: "Water: Irrigated",
    constLowIn: "Low-input / No-till",
    hlthStressLbl: "Thermal & ET₀ Balance",
    hlthSoilLbl: "Topsoil & Organic Matter",
    confPower: "POWER · Med",
    confSoilLow: "Regional est. · Low",
    plainStress:
      "Hot days >=35°C raise crop thirst before winter rain arrives; bare summer soil bakes moisture away.",
    plainSoil:
      "Organic carbon works like a sponge—higher levels keep rain stored in the root zone between storms.",
    localReviewNote:
      "Decision-support tool only: combines satellite & climate grids and does not replace farmer judgment or local DSA / ITGC soil tests.",
    mobCompare: "Compare",
    cmpKicker: "All 3 strategies side-by-side",
    cmpTitleFmt: (short) => `${short} · Rotation Matrix`,
    cmpSubFmt: (scenTxt, consTxt) =>
      `Live score under ${scenTxt} · ${consTxt}. Tap any column to select.`,
    cmpInspect: "Open selected strategy audit →",
    cmpShort: {
      s0: "Wheat → fallow",
      s1: "Wheat → faba → barley",
      s2: "Wheat → vetch → chickpea",
    },
    cmpRows: {
      fit: "Overall fit (/100)",
      bareWet: "Bare · wet exposure",
      water: "Water supply fit",
      nfix: "Avg N₂ fixed",
      roots: "Max root · OM trend",
      pest: "Disease cycle break",
      stress: "Heat & frost buffer",
      conf: "Evidence confidence",
    },
    cmpVals: {
      irrOn: "Supplemental irrigation",
      rainfedMode: "Rainfed",
      lowInOn: "Low-input constraint",
      stdMode: "Standard inputs",
      break0: "None (cereal repeat)",
      break1: "Strong (legume break)",
      break2: "High (cover + pulse)",
      confMed: "Med (Climate+DEM)",
      confLowGap: "Med / Verify market",
      roots0: "Shallow fallow gap",
      roots1: "1.1 m · Builds OM",
      roots2: "1.2 m · High residue",
    },
    heatSummaryFmt: (h30, h5, dryM) =>
      `${h30.toFixed(0)} → ${h5.toFixed(0)} d/yr >=35°C (30y → last 5y) · ${dryM} dry mo (<15 mm)`,
    wbSummaryFmt: (rain, et0, wb, pElev, demElev) =>
      `Rain ${rain} vs ET₀ ${et0} mm/yr (${wb} mm) · POWER grid ${pElev} m vs DEM ${demElev} m`,
    soilMetaFmt: (s) =>
      `Est. SOC ${s.soc}% · pH ${s.ph} · ${s.omTrend} · Lab core missing`,
    soils: {
      tidjelabine: {
        texture: "Clay-loam cambisol",
        omTrend: "Depleting under bare tillage",
      },
      guelma: {
        texture: "Silty clay alluvial",
        omTrend: "Moderate OM · High fertility",
      },
      constantine: {
        texture: "Calcareous clay-loam",
        omTrend: "Vulnerable to crusting",
      },
      mila: {
        texture: "Marl-clay hillside",
        omTrend: "Slope sheet-wash risk",
      },
      biskra: {
        texture: "Sandy loam gypsic",
        omTrend: "Low OM · Heat oxidation risk",
      },
    },
    guideTitle: "Science, Resolution Fusion & Local Validation Guide",
    guideSub:
      "Plain-language terms, scale harmonization across satellite Earth observation & local Algeria verification gaps",
    guideGlossaryH: "1. Plain-Language Agronomic Glossary",
    guideFusionH: "2. Satellite Scale Harmonization & Data Confidence",
    guideMathH: "3. Active Scoring Weights & Water Balance Audit",
    guideValidationNote:
      "Judgment & Local Review: Satellite pixels span 250 m to 55 km while rainfall, market prices, soil organic carbon, and salinity vary per field. Verify fertilizer, cultivar, and irrigation timing with your commune DSA (Direction des Services Agricoles), ITGC / ITAFV technicians, or a certified soil laboratory.",
    glossaryItems: [
      {
        term: "Canopy Greenness (NDVI · MODIS 250 m)",
        def: "Measures leaf greenness from 0 (bare plowed dirt) to 1 (dense canopy). Shows when wet autumn storms hit unprotected soil.",
      },
      {
        term: "Reference Evapotranspiration (ET₀ · mm/yr)",
        def: "Total atmosphere water demand driven by heat and sunlight (1,312–1,479 mm/yr across these sites). Compare Rain vs ET₀ to see irrigation pressure.",
      },
      {
        term: "Soil Moisture Anomaly (GLDAS / SMAP)",
        def: "How dry or wet the root zone sits versus its 30-year norm. GLDAS (0.25°) & SMAP (9 km) track watershed drought, not single-terrace irrigation.",
      },
      {
        term: "Bare · Wet Runoff Days (d/yr)",
        def: "Estimated rainy days occurring while ground cover is sparse. Steep parcels (Tidjelabine 13.8%, Mila 12.9%) lose topsoil fast on those days.",
      },
      {
        term: "Heat Spike (>=35°C) & Frost (<=0°C)",
        def: "30-yr POWER counts show +19 to +26 extra hot days/yr in the last 5 years—harming faba/chickpea pod set; Constantine averages 19.5 frost d/yr.",
      },
      {
        term: "Biological N₂ Fixation (kg N/ha)",
        def: "Legumes (faba bean, vetch, chickpea) capture atmospheric nitrogen with soil bacteria, cutting synthetic urea fertilizer cost for the next wheat crop.",
      },
    ],
    fusionCols: [
      "Source",
      "Native Grid",
      "Harmonization on Parcel",
      "Limitation & Ground Verification",
    ],
    fusionRows: [
      [
        "Esri World Imagery",
        "~1.2 m (z=17)",
        "Exact parcel boundary trace & field area (ha)",
        "Snapshot date varies; visually confirm field boundaries",
      ],
      [
        "AWS Terrarium / SRTM DEM",
        "30 m grid",
        "Elevation & 3-px finite-difference slope (%)",
        "Smooths micro-terraces or contour bunds; verify drainage lines",
      ],
      [
        "MODIS NDVI & LST",
        "250 m / 1 km",
        "Regional vegetation greenness & surface heat overlay",
        "250 m pixel mixes neighbor plots; check parcel canopy directly",
      ],
      [
        "GPM IMERG & GLDAS SM",
        "0.1° (~11 km) / 0.25°",
        "Storm rate & root-zone water visual replay",
        "Global gridded precipitation; calibrate with ONM rain gauges",
      ],
      [
        "POWER (1996–2025)",
        "0.5° (~55 km)",
        "30-yr daily rain, frost, >=35°C heat & FAO-56 ET₀",
        "Cell elev differs from plot (e.g. 500m vs 86m); may under-catch convective rain",
      ],
      [
        "SoilGrids 250 m / Regional Band",
        "250 m (unavailable)",
        "Regional texture, SOC% & pH baseline shown as Low conf.",
        "ISRIC REST timed out & no 1:500k lab API; requires DSA / INRAA soil core",
      ],
      [
        "Sentinel-2 & ECOSTRESS",
        "10 m / 70 m (context)",
        "Benchmark targets for future parcel ET & NDVI zoom",
        "Requires Earthdata/Copernicus API extraction outside static browser tile cache",
      ],
    ],
    mathSummaryFmt: (w, s, pName, clim, pElev) =>
      `Active weights (${s.priority}): Water ${Math.round(w.water * 100)}% · Soil ${Math.round(w.soil * 100)}% · Erosion ${Math.round(w.erosion * 100)}% · Income ${Math.round(w.income * 100)}% · Resilience ${Math.round(w.risk * 100)}%. ` +
      `Constraints: ${s.irrigated ? "Supplemental irrigation ON" : "Rainfed"} · ${s.lowInput ? "Low-input N-saver ON" : "Standard inputs"} · Scenario: ${s.rain > 0 ? "+" : ""}${s.rain}% rain, +${s.temp}°C. ` +
      `At ${pName}: POWER ${clim.annual} mm rain vs ${clim.et0} mm ET₀ (${clim.heat35} → ${clim.heatLast5} d/yr >=35°C; cell elev ${clim.powerElev} m vs DEM ${pElev} m).`,
    statArea: "Parcel area",
    statSlope: "DEM slope",
    statElev: "Elevation",
    statRain: "Month normal",
    uHa: "ha",
    uM: "m",
    uMm: "mm",
    ovTitle: "Rain vs bare soil overlap",
    zoomDetail: "Zoom to parcel detail",
    showRegion: "Show Algeria overview",
    provLine1: "DEM · AWS Terrarium (SRTM 30 m grid)",
    provLine2: "Climate · POWER 1996–2025 daily climatology",
    backField: "← Back to field profile",
    fitSuffix: "/ 100 fit",
    fitCard: "/ 100",
    hWhy: "Why this was suggested",
    hNow: "On this parcel",
    hEvidence: "Evidence",
    hBenefits: "Benefits",
    hGaps: "Information gaps",
    hRisks: "Risks · local review needed",
    ticks: ["Jan '25", "Jul '25", "Jan '26", "Oct '26"],
    timeKicker: "Satellite & Season Replay · Syncs satellite map layers & field rain",
    timePreview: "Preview on map: Canopy ↗",
    timeSynced: (layerName, dateStr) => `Synced: ${layerName} · ${dateStr}`,
    sparkLbl: "30y rain",
    layerShort: {
      truecolor: "Imagery",
      ndvi: "Canopy (NDVI)",
      sm: "Soil Water",
      rain: "Rainfall",
      lst: "Heat",
    },
    disclaimer:
      "Esri World Imagery · GIBS (MODIS · IMERG · GLDAS) · AWS Terrain DEM · POWER 1996–2025 · Decision-support prototype, verify with a local agronomist",
    mobMap: "Map",
    mobLab: "Rotations",
    mobField: "Field",
    mobAudit: "Audit",
    mn: MN,
    mi: MI,
    dims: ["Water", "Soil", "Erosion", "Income", "Risk"],
    auditDims: ["Water", "Soil", "Erosion", "Income", "Resilience"],
    wetTag: "Heavy rain · bare soil runoff risk",
    growTag: "Active growth · modest rain",
    aridTag: "Light rain · moisture watch",
    hotTag: "Dry heat · harvest & fallow",
    currentTag: "Current",
    bestTag: "Best fit",
    baselinePill: "baseline",
    baselineBench: "Baseline benchmark",
    kickerBase: "Baseline",
    kickerAlt: "Alternative",
    bareWetShort: "d bare·wet",
    bareWetYr: "bare·wet d/yr",
    fitAria: (name, total) => `${name}: fit ${total} out of 100`,
    deltaShort: (d) => (d > 0 ? `−${d} d` : `+${Math.abs(d)} d`),
    deltaLong: (d) =>
      d > 0 ? `−${d} fewer exposed days` : `+${Math.abs(d)} more exposed days`,
    skyAlts: (ha, place) => [
      "ORBIT · ~1,300 KM",
      "ALGERIA · ~120 KM",
      `${String(place || "ALGERIA").toUpperCase()} · ~11 KM`,
      `PARCEL LOCK · ${ha} HA`,
    ],
    scenActive: (r, tm) => {
      const b: string[] = [];
      if (r) b.push(`${r > 0 ? "+" : ""}${r}% rain`);
      if (tm) b.push(`+${tm}°C`);
      return b.length ? b.join(" · ") : "Baseline";
    },
    sparkTip: (mName, mm) => `${mName} 30-yr normal: ${mm} mm (click to jump)`,
    presetTip: (p) => `${p.name} · ${p.slope}% slope · ${p.elev} m`,
    presetOpt: (p) => `${p.name} (${p.slope}% slope)`,
    ovTip: (mName, rain, cov) => `${mName}: ${rain} mm rain · ${cov}% canopy cover`,
    ovCapBase: (exp, slope) =>
      `${exp} bare·wet days/yr on ${slope}% slope. Red bars flag storms hitting exposed soil.`,
    ovCapAlt: (exp, saved) =>
      saved > 0
        ? `Cuts bare·wet soil risk to ${exp} d/yr (${saved} fewer days exposed vs current fallow).`
        : `${exp} bare·wet days/yr under this climate scenario.`,
    onParcelBase: (name, slope, elev, exp, wet) =>
      `At ${name} (${slope}% slope, ${elev} m), this baseline exposes soil for ${exp} of ${wet} wet days/yr.`,
    onParcelAlt: (name, slope, elev, exp, delta) =>
      `At ${name} (${slope}% slope, ${elev} m), bare-and-wet exposure drops to ${exp} d/yr — ${
        delta > 0 ? `${delta} fewer` : `${Math.abs(delta)} more`
      } days than wheat → fallow.`,
    evidence: (clim, peakRain, peakMonth, slope, elev, pName, s) => [
      `POWER 1996–2025: ${clim.annual} mm/yr (CV ${clim.cv} · ${clim.frost} frost d/yr), peaking at ${peakRain} mm in ${peakMonth}.`,
      `AWS Terrarium 30 m DEM: ${slope}% grade at ${elev} m elevation on ${pName}.`,
      s.current
        ? "MODIS NDVI shows low winter ground cover while peak rains hit bare fallow."
        : s.id === "s1"
        ? clim.frost >= 10
          ? "Faba bean and barley endure frost-prone high-plain winters while fixing nitrogen."
          : "Faba bean maintains winter cover and fixes nitrogen before the cereal cycle."
        : clim.annual < 320
        ? "High-residue vetch cover curbs arid surface evaporation; chickpea cuts irrigation draw."
        : "Vetch–oat cover closes canopy prior to heavy autumn storms; chickpea adds drought resilience.",
    ],
    probeTitle: "Terrain Probe",
    probeElev: (h) => `${h} m elevation`,
    probeLoading: "Elevation loading…",
    climates: {
      inland: "647 mm/yr · CV 0.23 · 3.6 frost d/yr",
      guelma: "790 mm/yr · CV 0.21 · 3.9 frost d/yr",
      constantine: "590 mm/yr · CV 0.22 · 19.5 frost d/yr",
      mila: "683 mm/yr · CV 0.20 · 3.4 frost d/yr",
      biskra: "241 mm/yr · CV 0.39 · 3.5 frost d/yr",
    },
    legends: LEGENDS,
  },
  fr: {
    pageTitle: "FieldShift — Algérie",
    bootSub: "Rotation des cultures · Algérie",
    bootConnect: "Connexion satellite et relief",
    bootSlowTiles: "Chargement des tuiles régionales…",
    bootSlowNet: "Réseau lent — flux d'imagerie régionale",
    brandRegion: "Algérie",
    layerTruecolor: "Imagerie",
    layerNdvi: "Végétation",
    layerSm: "Eau du sol",
    layerRain: "Pluies",
    layerLst: "Chaleur",
    layerTips: {
      truecolor: "MODIS Terra Couleur réelle (250 m)",
      ndvi: "MODIS Indice de végétation (NDVI)",
      sm: "GLDAS Humidité racinaire du sol",
      rain: "GPM IMERG Taux de précipitation",
      lst: "MODIS Température de surface",
    },
    toolRegion: "Global",
    toolParcel: "Parcelle",
    tool3d: "3D",
    toolClean: "Épuré",
    focusTip: "Centrer sur la parcelle ou vue régionale",
    tiltTip: "Basculer la vue 3D du relief",
    zenTip: "Masquer ou afficher les panneaux",
    labTitle: "Laboratoire",
    prioBalanced: "Équilibré",
    prioWater: "Eau",
    prioSoil: "Sol",
    prioIncome: "Revenu",
    scenTitle: "Stress climatique · Scénario",
    chipBase: "Référence",
    chipDry: "Sec −20%",
    chipShock: "Choc",
    lblRain: "Pluie",
    lblTemp: "Chaleur",
    tabField: "Parcelle",
    tabCompare: "Comparer",
    tabAudit: "Audit",
    toolPlain: "Clair",
    toolGuide: "Guide",
    plainTip: "Basculer en mode langage clair agriculteur",
    guideTip: "Ouvrir le guide scientifique, fusion d'échelles et validation",
    constRainfed: "Eau : Pluvial",
    constIrrig: "Eau : Irrigué",
    constLowIn: "Faible intrant",
    hlthStressLbl: "Stress thermique & ET₀",
    hlthSoilLbl: "Sol & Matière organique",
    confPower: "POWER · Moy",
    confSoilLow: "Est. rég. · Faible",
    plainStress:
      "Les jours >=35°C accélèrent la soif des cultures avant l'hiver ; le sol nu d'été perd son humidité.",
    plainSoil:
      "Le carbone organique agit comme une éponge qui retient les pluies d'hiver dans les racines.",
    localReviewNote:
      "Outil d'aide uniquement : croise satellite et climat, ne remplace ni l'expertise paysanne ni les analyses DSA / ITGC.",
    mobCompare: "Comparer",
    cmpKicker: "Comparaison des 3 rotations",
    cmpTitleFmt: (short) => `${short} · Matrice comparative`,
    cmpSubFmt: (scenTxt, consTxt) =>
      `Score en direct (${scenTxt} · ${consTxt}). Touchez une colonne pour l'activer.`,
    cmpInspect: "Ouvrir l'audit de cette rotation →",
    cmpShort: {
      s0: "Blé → jachère",
      s1: "Blé → féverole → orge",
      s2: "Blé → vesce → pois chiche",
    },
    cmpRows: {
      fit: "Score global (/100)",
      bareWet: "Exposition sol nu·humide",
      water: "Adéquation hydrique",
      nfix: "Azote N₂ fixé moy.",
      roots: "Enracinement · MO",
      pest: "Rupture maladies",
      stress: "Tampon gel & chaleur",
      conf: "Confiance données",
    },
    cmpVals: {
      irrOn: "Irrigation d'appoint",
      rainfedMode: "Pluvial strict",
      lowInOn: "Mode faible intrant",
      stdMode: "Intrants standards",
      break0: "Nul (retour céréale)",
      break1: "Fort (coupure légumineuse)",
      break2: "Élevé (couvert + pois)",
      confMed: "Moy. (Climat+MNT)",
      confLowGap: "Moy. / Prix à vérifier",
      roots0: "Lacune jachère",
      roots1: "1,1 m · Enrichit MO",
      roots2: "1,2 m · Fort résidu",
    },
    heatSummaryFmt: (h30, h5, dryM) =>
      `${h30.toFixed(0)} → ${h5.toFixed(0)} j/an >=35°C (30a → 5a) · ${dryM} mois secs (<15 mm)`,
    wbSummaryFmt: (rain, et0, wb, pElev, demElev) =>
      `Pluie ${rain} vs ET₀ ${et0} mm/an (${wb} mm) · Grille POWER ${pElev} m vs MNT ${demElev} m`,
    soilMetaFmt: (s) =>
      `Est. COS ${s.soc}% · pH ${s.ph} · ${s.omTrend} · Sans analyse labo`,
    soils: {
      tidjelabine: {
        texture: "Argilo-limoneux",
        omTrend: "Baisse sous labour nu",
      },
      guelma: {
        texture: "Limon argileux alluvial",
        omTrend: "MO modérée · Sol fertile",
      },
      constantine: {
        texture: "Argilo-calcaire",
        omTrend: "Risque de battance",
      },
      mila: {
        texture: "Marno-argileux en pente",
        omTrend: "Érosion hydrique forte",
      },
      biskra: {
        texture: "Sablo-limoneux gypseux",
        omTrend: "MO faible · Oxydation",
      },
    },
    guideTitle: "Guide scientifique, fusion d'échelles & validation locale",
    guideSub:
      "Définitions simples, harmonisation multi-résolutions satellite et lacunes locales en Algérie",
    guideGlossaryH: "1. Glossaire agronomique simplifié",
    guideFusionH: "2. Harmonisation des résolutions & niveaux de confiance",
    guideMathH: "3. Pondération active & bilan hydrique",
    guideValidationNote:
      "Jugement et validation locale : les pixels satellites couvrent de 250 m à 55 km alors que pluies locales, prix, carbone du sol et salinité varient par parcelle. Validez doses, variétés et irrigation auprès de la DSA, l'ITGC/ITAFV ou un laboratoire agronomique.",
    glossaryItems: [
      {
        term: "Indice de végétation (NDVI · MODIS 250 m)",
        def: "Mesure la vigueur verte du couvert de 0 (sol labouré nu) à 1 (couvert dense) pour repérer les pluies sur sol nu.",
      },
      {
        term: "Évapotranspiration ET₀ (mm/an)",
        def: "Demande en eau de l'atmosphère (1 312–1 479 mm/an ici). Comparer Pluie et ET₀ montre le déficit hydrique.",
      },
      {
        term: "Humidité du sol (GLDAS / SMAP)",
        def: "Écart d'humidité racinaire face à la normale 30 ans. Suit la sécheresse de bassin, pas une vanne d'irrigation isolée.",
      },
      {
        term: "Jours nu·humide (j/an)",
        def: "Jours de pluie tombant sur sol peu couvert. Critique sur les versants en pente (Tidjelabine 13,8 %, Mila 12,9 %).",
      },
      {
        term: "Pics chaleur (>=35°C) & Gel (<=0°C)",
        def: "POWER montre +19 à +26 jours chauds en plus sur 5 ans ; Constantine subit 19,5 j de gel/an pénalisant le pois chiche.",
      },
      {
        term: "Fixation symbiotique N₂ (kg N/ha)",
        def: "Féverole, vesce et pois chiche captent l'azote de l'air, réduisant l'engrais minéral nécessaire pour le blé suivant.",
      },
    ],
    fusionCols: [
      "Source",
      "Résolution native",
      "Lien à la parcelle",
      "Limite & vérification terrain",
    ],
    fusionRows: [
      [
        "Esri World Imagery",
        "~1,2 m (z=17)",
        "Tracé exact de la parcelle et surface (ha)",
        "Date de prise variable ; confirmer limites sur le terrain",
      ],
      [
        "AWS Terrarium / MNT SRTM",
        "Grille 30 m",
        "Altitude et pente par différences finies",
        "Lisse les micro-talus ; vérifier les rigoles d'écoulement",
      ],
      [
        "MODIS NDVI & LST",
        "250 m / 1 km",
        "Suivi mensuel végétation et chaleur de surface",
        "Un pixel 250 m mélange plusieurs champs ; observer sur place",
      ],
      [
        "GPM IMERG & GLDAS SM",
        "0,1° (~11 km) / 0,25°",
        "Animation des pluies et humidité racinaire",
        "Grille globale ; étalonner aux stations ONM locales",
      ],
      [
        "POWER (1996–2025)",
        "0,5° (~55 km)",
        "Séries quotidiennes 30 ans, gel, >=35°C et ET₀",
        "Altitude de maille différente (ex. 500 m vs 86 m) ; sous-estime parfois l'orage",
      ],
      [
        "SoilGrids 250 m / Est. rég.",
        "250 m (indispo.)",
        "Texture, COS% et pH régionaux (confiance faible)",
        "API ISRIC expirée sans carte 1:500k ouverte ; analyse labo requise",
      ],
      [
        "Sentinel-2 & ECOSTRESS",
        "10 m / 70 m (contexte)",
        "Cibles haute résolution pour ET et NDVI parcellaire",
        "Extraction API requise hors tuiles web statiques",
      ],
    ],
    mathSummaryFmt: (w, s, pName, clim, pElev) =>
      `Poids actifs (${s.priority}) : Eau ${Math.round(w.water * 100)}% · Sol ${Math.round(w.soil * 100)}% · Érosion ${Math.round(w.erosion * 100)}% · Revenu ${Math.round(w.income * 100)}% · Résilience ${Math.round(w.risk * 100)}%. ` +
      `Contraintes : ${s.irrigated ? "Irrigation d'appoint ON" : "Pluvial"} · ${s.lowInput ? "Faible intrant ON" : "Intrants standards"} · Scénario : ${s.rain > 0 ? "+" : ""}${s.rain}% pluie, +${s.temp}°C. ` +
      `Sur ${pName} : POWER ${clim.annual} mm pluie vs ${clim.et0} mm ET₀ (${clim.heat35} → ${clim.heatLast5} j/an >=35°C ; maille ${clim.powerElev} m vs MNT ${pElev} m).`,
    statArea: "Surface",
    statSlope: "Pente MNT",
    statElev: "Altitude",
    statRain: "Normale mois",
    uHa: "ha",
    uM: "m",
    uMm: "mm",
    ovTitle: "Pluie vs sol nu",
    zoomDetail: "Zoomer sur la parcelle",
    showRegion: "Vue nationale Algérie",
    provLine1: "MNT · AWS Terrarium (grille SRTM 30 m)",
    provLine2: "Climat · POWER climatologie 1996–2025",
    backField: "← Retour au profil",
    fitSuffix: "/ 100 score",
    fitCard: "/ 100",
    hWhy: "Pourquoi ce choix",
    hNow: "Sur cette parcelle",
    hEvidence: "Données probantes",
    hBenefits: "Avantages",
    hGaps: "Limites des données",
    hRisks: "Risques · validation locale",
    ticks: ["Jan '25", "Juil '25", "Jan '26", "Oct '26"],
    timeKicker: "Chronologie satellite & saison · Pilote les couches satellite & la pluie",
    timePreview: "Tester sur la carte : Végétation ↗",
    timeSynced: (layerName, dateStr) => `Synchronisé : ${layerName} · ${dateStr}`,
    sparkLbl: "Pluie 30 ans",
    layerShort: {
      truecolor: "Imagerie",
      ndvi: "Végétation",
      sm: "Eau du sol",
      rain: "Pluies",
      lst: "Chaleur",
    },
    disclaimer:
      "Esri World Imagery · GIBS (MODIS · IMERG · GLDAS) · AWS Terrain MNT · POWER 1996–2025 · Prototype d'aide à la décision, vérifier avec un agronome",
    mobMap: "Carte",
    mobLab: "Rotations",
    mobField: "Parcelle",
    mobAudit: "Audit",
    mn: ["JAN", "FÉV", "MAR", "AVR", "MAI", "JUIN", "JUIL", "AOÛ", "SEP", "OCT", "NOV", "DÉC"],
    mi: ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"],
    dims: ["Eau", "Sol", "Érosion", "Revenu", "Risque"],
    auditDims: ["Eau", "Sol", "Érosion", "Revenu", "Résilience"],
    wetTag: "Fortes pluies · risque de ruissellement",
    growTag: "Croissance active · pluie modérée",
    aridTag: "Pluie faible · vigilance hydrique",
    hotTag: "Chaleur sèche · post-récolte",
    currentTag: "Actuel",
    bestTag: "Optimal",
    baselinePill: "référence",
    baselineBench: "Référence actuelle",
    kickerBase: "Référence",
    kickerAlt: "Alternative",
    bareWetShort: "j nu·humide",
    bareWetYr: "j nu·humide/an",
    fitAria: (name, total) => `${name} : score ${total} sur 100`,
    deltaShort: (d) => (d > 0 ? `−${d} j` : `+${Math.abs(d)} j`),
    deltaLong: (d) =>
      d > 0 ? `−${d} j d'exposition en moins` : `+${Math.abs(d)} j d'exposition en plus`,
    skyAlts: (ha, place) => [
      "ORBITE · ~1 300 KM",
      "ALGÉRIE · ~120 KM",
      `${String(place || "ALGÉRIE").toUpperCase()} · ~11 KM`,
      `PARCELLE · ${ha} HA`,
    ],
    scenActive: (r, tm) => {
      const b: string[] = [];
      if (r) b.push(`${r > 0 ? "+" : ""}${r}% pluie`);
      if (tm) b.push(`+${tm}°C`);
      return b.length ? b.join(" · ") : "Référence";
    },
    sparkTip: (mName, mm) => `${mName} normale 30 ans : ${mm} mm (cliquer)`,
    presetTip: (p) => `${p.name} · pente ${p.slope}% · ${p.elev} m`,
    presetOpt: (p) => `${p.name} (pente ${p.slope}%)`,
    ovTip: (mName, rain, cov) => `${mName} : ${rain} mm pluie · ${cov}% couvert`,
    ovCapBase: (exp, slope) =>
      `${exp} j nu·humide/an sur pente de ${slope}%. Les barres rouges signalent les pluies sur sol nu.`,
    ovCapAlt: (exp, saved) =>
      saved > 0
        ? `Réduit l'exposition à ${exp} j/an (${saved} jours en moins vs jachère actuelle).`
        : `${exp} jours nu·humide/an dans ce scénario climatique.`,
    onParcelBase: (name, slope, elev, exp, wet) =>
      `À ${name} (pente ${slope}%, ${elev} m), ce scénario expose le sol ${exp} jours sur ${wet} jours humides/an.`,
    onParcelAlt: (name, slope, elev, exp, delta) =>
      `À ${name} (pente ${slope}%, ${elev} m), l'exposition tombe à ${exp} j/an — soit ${
        delta > 0 ? `${delta} j en moins` : `${Math.abs(delta)} j en plus`
      } par rapport à blé → jachère.`,
    evidence: (clim, peakRain, peakMonth, slope, elev, pName, s) => [
      `POWER 1996–2025 : ${clim.annual} mm/an (CV ${clim.cv} · ${clim.frost} j gel/an), pic à ${peakRain} mm (${peakMonth}).`,
      `AWS Terrarium MNT 30 m : pente de ${slope}% à ${elev} m d'altitude (${pName}).`,
      s.current
        ? "L'indice NDVI MODIS confirme un faible couvert hivernal lors des pluies maximales."
        : s.id === "s1"
        ? clim.frost >= 10
          ? "Féverole et orge résistent mieux aux hivers gélifs des Hauts Plateaux tout en fixant l'azote."
          : "La féverole maintient le couvert d'hiver et fixe l'azote avant la céréale."
        : clim.annual < 320
        ? "Les résidus de vesce freinent l'évaporation en climat aride ; le pois chiche réduit l'irrigation."
        : "Le couvert vesce-avoine protège avant les pluies d'automne ; le pois chiche tolère la sécheresse.",
    ],
    probeTitle: "Sonde terrain",
    probeElev: (h) => `${h} m d'altitude`,
    probeLoading: "Chargement altitude…",
    climates: {
      inland: "647 mm/an · CV 0.23 · 3,6 j gel/an",
      guelma: "790 mm/an · CV 0.21 · 3,9 j gel/an",
      constantine: "590 mm/an · CV 0.22 · 19,5 j gel/an",
      mila: "683 mm/an · CV 0.20 · 3,4 j gel/an",
      biskra: "241 mm/an · CV 0.39 · 3,5 j gel/an",
    },
    legends: {
      ndvi: { ...LEGENDS.ndvi, title: "Couvert végétal", lo: "nu", hi: "dense" },
      sm: { ...LEGENDS.sm, title: "Eau racinaire", lo: "sec", hi: "saturé" },
      rain: { ...LEGENDS.rain, title: "Précipitations", lo: "0 mm/h", hi: "30+ mm/h" },
      lst: { ...LEGENDS.lst, title: "Temp. de surface", lo: "frais", hi: "chaud" },
    },
    presets: {
      tidjelabine: {
        short: "Tidjelabine",
        name: "Coteau de Tidjelabine",
        zone: "Coteau céréalier pluvial · Argilo-limoneux",
        note: "Versant céréalier en pente au sud de Boumerdès. Le sol labouré nu perd rapidement humidité et terre lors des averses de nov.–jan.",
      },
      guelma: {
        short: "Guelma",
        name: "Plaine alluviale de la Seybouse",
        zone: "Terrasse alluviale plane · Limon argileux humide",
        note: "Parcelle alluviale nivelée (2,0 %) au cœur du bassin humide de Guelma (790 mm/an). Faible érosion : la fertilisation azotée et l'intensification priment.",
      },
      constantine: {
        short: "Constantine",
        name: "Hautes Plaines d'El Khroub",
        zone: "Plateau céréalier d'altitude · Argilo-calcaire",
        note: "Grand ruban céréalier sur les Hauts Plateaux à 673 m (19,5 j de gel/an). L'orge et la féverole tolèrent mieux l'hiver rigoureux que le pois chiche.",
      },
      mila: {
        short: "Mila",
        name: "Versant Tellien de Beni Haroun",
        zone: "Versant marno-argileux en pente · Tête de bassin",
        note: "Parcelle en forte pente (12,9 %) dominant l'oued et le barrage de Beni Haroun à 504 m. Un couvert permanent d'automne est vital contre l'érosion.",
      },
      biskra: {
        short: "Biskra",
        name: "Périmètre des Ziban · Biskra",
        zone: "Piémont aride irrigué · Sablo-limoneux",
        note: "Îlot agricole irrigué en bordure saharienne (241 mm/an, CV 0,39). Orge et pois chiche économisent l'eau face au stress thermique et hydrique.",
      },
    },
    strats: {
      s0: {
        name: "Blé dur → jachère",
        tag: "Actuel",
        conf: "Confiance moyenne",
        why: "Pratique régionale de référence : blé dur suivi d'une année de jachère travaillée pour stocker l'eau. Chaque alternative est comparée directement à cette base.",
        benefits: [
          "La jachère stocke l'eau pour le blé suivant sans achat de semences ni charges supplémentaires.",
          "Filière commerciale et calendrier cultural bien maîtrisés localement.",
        ],
        gaps: [
          "Pas d'analyse de sol sur parcelle : carbone organique et texture estimés par modèle.",
          "Bilan hydrique de la jachère basé sur les normales climatiques sans sonde in situ.",
        ],
        risks: [
          "Laisser le sol nu pendant les fortes pluies de nov.–jan. favorise le ruissellement et l'érosion.",
          "Une seule culture récoltée accroît la vulnérabilité économique les années sèches.",
        ],
      },
      s1: {
        name: "Blé → féverole → orge",
        tag: "Légumineuse",
        conf: "Confiance moyenne",
        why: "Rotation méditerranéenne triennale : la légumineuse d'hiver coupe les cycles de maladies céréalières et fixe l'azote durant l'année habituellement laissée en jachère.",
        benefits: [
          "Réduit nettement les jours de sol nu sous la pluie tout en gardant trois cultures valorisables.",
          "La fixation symbiotique d'azote réduit les besoins en engrais minéraux pour le blé.",
          "Diversifie les revenus grain + fourrage entre féverole et orge.",
        ],
        gaps: [
          "Prix bord champ de la féverole et débouchés communaux à confirmer auprès de la DSA.",
          "Pression fongique (botrytis, ascochytose) non modélisée explicitement ici.",
        ],
        risks: [
          "La féverole consomme plus d'eau que le blé : un printemps sec pénalise le remplissage.",
          "Trois cycles exigent une meilleure coordination des travaux et fenêtres de semis.",
        ],
      },
      s2: {
        name: "Blé → vesce-avoine → pois chiche",
        tag: "Couvert",
        conf: "Confiance moyenne",
        why: "Referme la fenêtre d'automne : le couvert vesce-avoine protège le sol avant les pluies de novembre, suivi d'un pois chiche de printemps tolérant à la sécheresse.",
        benefits: [
          "Obtient la plus faible exposition sol nu·humide lors des pluies d'automne et d'hiver.",
          "La vesce fixe l'azote pendant que racines et résidus enrichissent la matière organique.",
          "Le pois chiche demande peu d'eau et résiste mieux à la chaleur que la féverole.",
        ],
        gaps: [
          "La date optimale de destruction du couvert dépend de l'humidité printanière réelle.",
          "Volatilité locale des prix du pois chiche à vérifier sur les marchés communaux.",
        ],
        risks: [
          "Des pluies tardives en octobre retardent la levée du couvert et réduisent l'effet anti-érosif.",
          "Sensibilité au froid printanier pour le pois chiche sur les hautes plaines (> 500 m).",
        ],
      },
    },
  },
  ar: {
    pageTitle: "FieldShift · تحول الحقول — الجزائر",
    bootSub: "تناوب المحاصيل · الجزائر",
    bootConnect: "جاري الاتصال بالأقمار والتضاريس",
    bootSlowTiles: "جاري تحميل الخرائط الإقليمية…",
    bootSlowNet: "شبكة بطيئة — بث الصور الإقليمية",
    brandRegion: "الجزائر",
    layerTruecolor: "صور حقيقية",
    layerNdvi: "الغطاء النباتي",
    layerSm: "رطوبة التربة",
    layerRain: "الأمطار",
    layerLst: "الحرارة",
    layerTips: {
      truecolor: "صور MODIS Terra الحقيقية (250 م)",
      ndvi: "مؤشر الغطاء النباتي MODIS (NDVI)",
      sm: "رطوبة منطقة الجذور GLDAS",
      rain: "معدل الهطول المطري GPM IMERG",
      lst: "حرارة سطح الأرض MODIS",
    },
    toolRegion: "شامل",
    toolParcel: "القطعة",
    tool3d: "ثلاثي",
    toolClean: "إخفاء",
    focusTip: "التركيز على القطعة أو عرض المنطقة",
    tiltTip: "تبديل العرض ثلاثي الأبعاد",
    zenTip: "إظهار أو إخفاء النوافذ",
    labTitle: "مختبر التناوب",
    prioBalanced: "متوازن",
    prioWater: "الماء",
    prioSoil: "التربة",
    prioIncome: "الدخل",
    scenTitle: "الإجهاد المناخي · سيناريو",
    chipBase: "المرجع",
    chipDry: "جفاف −20%",
    chipShock: "صدمة",
    lblRain: "الأمطار",
    lblTemp: "الاحترار",
    tabField: "القطعة",
    tabCompare: "مقارنة",
    tabAudit: "التدقيق",
    toolPlain: "مبسّط",
    toolGuide: "الدليل",
    plainTip: "تفعيل وضع القراءة المبسطة للفلاح وبخط أوضح",
    guideTip: "فتح الدليل العلمي ودمج الدقة والتحقق الميداني",
    constRainfed: "الماء: مطري",
    constIrrig: "الماء: مسقي",
    constLowIn: "مدخلات منخفضة",
    hlthStressLbl: "الإجهاد الحراري و ET₀",
    hlthSoilLbl: "التربة والمادة العضوية",
    confPower: "POWER · متوسطة",
    confSoilLow: "تقدير إقليمي · منخفضة",
    plainStress:
      "تضاعف الأيام الحارة (>=35°م) عطش النباتات؛ وترك التربة عارية صيفاً يبدد رطوبتها.",
    plainSoil:
      "يعمل الكربون العضوي كإسفنجة داخل التربة؛ ارتفاعه يحفظ ماء المطر لفترة أطول.",
    localReviewNote:
      "أداة مساعدة فقط: تدمج الأقمار والمناخ ولا تعوّض خبرة الفلاح أو تحاليل المصالح الفلاحية والـ ITGC.",
    mobCompare: "مقارنة",
    cmpKicker: "مقارنة الدورات الثلاث جنباً لجنب",
    cmpTitleFmt: (short) => `${short} · مصفوفة المقارنة`,
    cmpSubFmt: (scenTxt, consTxt) =>
      `تقييم مباشر (${scenTxt} · ${consTxt}). انقر أي عمود لاختياره.`,
    cmpInspect: "فتح تدقيق الخطة المختارة ←",
    cmpShort: {
      s0: "قمح ← بور",
      s1: "قمح ← فول ← شعير",
      s2: "قمح ← بيقية ← حمص",
    },
    cmpRows: {
      fit: "الملاءمة العامة (/100)",
      bareWet: "انكشاف مكشوف·ممطر",
      water: "توازن الماء",
      nfix: "الآزوت المثبت",
      roots: "عمق الجذر · المادة العضوية",
      pest: "كسر دورة الأمراض",
      stress: "تحمل الصقيع والحر",
      conf: "مستوى الثقة",
    },
    cmpVals: {
      irrOn: "سقي تكميلي",
      rainfedMode: "زراعة مطرية",
      lowInOn: "مدخلات منخفضة",
      stdMode: "مدخلات عادية",
      break0: "منعدم (تكرار حبوب)",
      break1: "قوي (فاصل بقولي)",
      break2: "عالي (غطاء + حمص)",
      confMed: "متوسطة (مناخ+تضاريس)",
      confLowGap: "متوسطة / تحقق السعر",
      roots0: "فجوة بور سطحية",
      roots1: "1.1 م · يبني المادة",
      roots2: "1.2 م · بقايا كثيفة",
    },
    heatSummaryFmt: (h30, h5, dryM) =>
      `${h30.toFixed(0)} ← ${h5.toFixed(0)} ي/سنة >=35°م (30 سنة ← آخر 5) · ${dryM} شهر جاف (<15 مم)`,
    wbSummaryFmt: (rain, et0, wb, pElev, demElev) =>
      `مطر ${rain} مقابل تبخر ET₀ ${et0} مم (${wb} مم) · شبكة POWER ${pElev} م مقابل ${demElev} م`,
    soilMetaFmt: (s) =>
      `تقدير كربون ${s.soc}% · pH ${s.ph} · ${s.omTrend} · بدون تحليل مخبري`,
    soils: {
      tidjelabine: {
        texture: "طينية طمية",
        omTrend: "استنزاف مع الحرث العاري",
      },
      guelma: {
        texture: "طمي طيني رسوبي",
        omTrend: "خصوبة جيدة ومتوازنة",
      },
      constantine: {
        texture: "كلسية طينية",
        omTrend: "حساسة لتقشر السطح",
      },
      mila: {
        texture: "طينية مارنية منحدِرة",
        omTrend: "خطر انجراف مرتفع",
      },
      biskra: {
        texture: "رملية طمية جبسية",
        omTrend: "مادة عضوية منخفضة",
      },
    },
    guideTitle: "الدليل العلمي ودمج الدقة والتحقق الميداني",
    guideSub:
      "شروح مبسطة للفلاحين، مواءمة دقة بيانات الأقمار الصناعية، وفجوات التحقق المحلي بالجزائر",
    guideGlossaryH: "1. قاموس فلاحي مبسط للمؤشرات",
    guideFusionH: "2. دمج دقة الأقمار الصناعية ومستوى الثقة",
    guideMathH: "3. الأوزان النشطة والميزان المائي للقطعة",
    guideValidationNote:
      "تذكير الحكم المحلي: تتراوح دقة الأقمار بين 250 م و55 كم بينما تختلف الملوحة والأسعار والكربون العضوي من قطعة لأخرى. يجب تأكيد البذور والأسمدة ومواعيد السقي مع مديرية المصالح الفلاحية DSA أو معهد ITGC أو مخبر تحاليل التربة.",
    glossaryItems: [
      {
        term: "خضرة الغطاء النباتي (NDVI · 250 م)",
        def: "يقيس كثافة الأوراق من 0 (أرض محروثة عارية) إلى 1 (غطاء كثيف) لكشف الأمطار الساقطة على تربة مكشوفة.",
      },
      {
        term: "الطلب المناخي للماء ET₀ (مم/سنة)",
        def: "مجموع تبخر التربة ونتح النبات (1312–1479 مم/سنة هنا). مقارنة المطر بـ ET₀ تُظهر العجز المائي الحقيقي.",
      },
      {
        term: "شذوذ رطوبة التربة (GLDAS / SMAP)",
        def: "انحراف رطوبة الجذور عن معدل 30 سنة. يراقب الجفاف الجهوي ولا يقيس السقي الفردي.",
      },
      {
        term: "أيام مكشوف·ممطر (ي/سنة)",
        def: "عدد الأيام الممطرة والتربة عارية. أشد خطورة في المنحدرات (تيجلابين 13.8%، ميلة 12.9%).",
      },
      {
        term: "موجات الحر (>=35°م) والصقيع (<=0°م)",
        def: "تظهر بيانات 30 سنة قفزة +19 إلى +26 يوم حر إضافي آخر 5 سنوات، مع 19.5 يوم صقيع سنوياً بقسنطينة.",
      },
      {
        term: "تثبيت الآزوت الحيوي N₂ (كغ/هكتار)",
        def: "تثبت البقوليات (الفول، البيقية، الحمص) آزوت الهواء عبر عقد الجذور، ما يوفر سماد اليوريا للقمح التالي.",
      },
    ],
    fusionCols: ["المصدر", "الدقة الأصلية", "المواءمة على القطعة", "الحدود والتحقق المحلي"],
    fusionRows: [
      [
        "صور Esri الفضائية",
        "~1.2 م (z=17)",
        "رسم حدود القطعة الفعلية والمساحة (هـ)",
        "تاريخ الالتقاط متغير؛ يُتحقق من الحدود ميدانياً",
      ],
      [
        "نموذج الارتفاع SRTM / AWS",
        "شبكة 30 م",
        "الارتفاع ونسبة الانحدار بالفرق المحدود",
        "يمسح المدرجات الصغيرة؛ يجب فحص مجاري الجريان",
      ],
      [
        "MODIS NDVI و LST",
        "250 م / 1 كم",
        "خرائط الخضرة الشهرية وحرارة السطح",
        "البكسل 250 م يدمج قطع الجوار؛ المعاينة الحقلية لازمة",
      ],
      [
        "GPM IMERG و GLDAS SM",
        "0.1° / 0.25°",
        "عرض شهري للأمطار ورطوبة الجذور",
        "شبكة شمولية؛ تُعاير بمحطات الأرصاد ONM",
      ],
      [
        "POWER (1996–2025)",
        "0.5° (~55 كم)",
        "سلسلة 30 سنة يومية: المطر، الصقيع، الحر وET₀",
        "ارتفاع الخلية يختلف عن القطعة (مثلاً 500 م مقابل 86 م)",
      ],
      [
        "SoilGrids 250 م / تقدير إقليمي",
        "250 م (متوقف)",
        "قوام التربة والكربون العضوي وpH (ثقة منخفضة)",
        "تعذّر خادم ISRIC؛ يتطلب تحليلاً مخبرياً محلياً",
      ],
      [
        "Sentinel-2 و ECOSTRESS",
        "10 م / 70 م (مرجعي)",
        "دقة عالية مستقبلية لنتح وغطاء كل قطعة",
        "يتطلب استخراجاً عبر واجهات برمجية خارج التخزين الساكن",
      ],
    ],
    mathSummaryFmt: (w, s, pName, clim, pElev) =>
      `الأوزان الحالية (${s.priority}): الماء ${Math.round(w.water * 100)}% · التربة ${Math.round(w.soil * 100)}% · التعرية ${Math.round(w.erosion * 100)}% · الدخل ${Math.round(w.income * 100)}% · المرونة ${Math.round(w.risk * 100)}%. ` +
      `القيود: ${s.irrigated ? "سقي تكميلي مفعل" : "مطري"} · ${s.lowInput ? "مدخلات منخفضة مفعلة" : "مدخلات عادية"} · السيناريو: ${s.rain > 0 ? "+" : ""}${s.rain}% مطر، +${s.temp}°م. ` +
      `في ${pName}: أمطار ${clim.annual} مم مقابل ET₀ ${clim.et0} مم (${clim.heat35} ← ${clim.heatLast5} ي >=35°م؛ شبكة ${clim.powerElev} م مقابل ${pElev} م).`,
    statArea: "المساحة",
    statSlope: "الانحدار",
    statElev: "الارتفاع",
    statRain: "معدل الشهر",
    uHa: "هـ",
    uM: "م",
    uMm: "مم",
    ovTitle: "المطر مقابل التربة المكشوفة",
    zoomDetail: "تكبير القطعة",
    showRegion: "عرض خريطة الجزائر",
    provLine1: "التضاريس · AWS Terrarium (دقة 30 م)",
    provLine2: "المناخ · أرصاد POWER 1996–2025",
    backField: "← العودة لملف القطعة",
    fitSuffix: "/ 100 ملاءمة",
    fitCard: "/ 100",
    hWhy: "سبب هذا الاقتراح",
    hNow: "وضع هذه القطعة",
    hEvidence: "الأدلة المرصودة",
    hBenefits: "الفوائد",
    hGaps: "فجوات البيانات",
    hRisks: "المخاطر · مراجعة محلية",
    ticks: ["جانفي 25", "جويلية 25", "جانفي 26", "أكتوبر 26"],
    timeKicker: "الخط الزمني للأقمار والمناخ · يزامن طبقات الخريطة والأمطار",
    timePreview: "معاينة الغطاء النباتي على الخريطة ↗",
    timeSynced: (layerName, dateStr) => `متزامن: ${layerName} · ${dateStr}`,
    sparkLbl: "أمطار 30 سنة",
    layerShort: {
      truecolor: "صور حقيقية",
      ndvi: "الغطاء النباتي",
      sm: "رطوبة التربة",
      rain: "الأمطار",
      lst: "الحرارة",
    },
    disclaimer:
      "صور Esri · بيانات GIBS (MODIS · IMERG · GLDAS) · نموذج الارتفاع AWS · أرصاد POWER 1996–2025 · نموذج مساعدة قرار، يُراجع مع مهندس فلاحي",
    mobMap: "الخريطة",
    mobLab: "التناوب",
    mobField: "القطعة",
    mobAudit: "التدقيق",
    mn: [
      "جانفي",
      "فيفري",
      "مارس",
      "أفريل",
      "ماي",
      "جوان",
      "جويلية",
      "أوت",
      "سبتمبر",
      "أكتوبر",
      "نوفمبر",
      "ديسمبر",
    ],
    mi: ["ج", "ف", "م", "أ", "م", "ج", "ج", "أ", "س", "أ", "ن", "د"],
    dims: ["الماء", "التربة", "التعرية", "الدخل", "المخاطر"],
    auditDims: ["الماء", "التربة", "التعرية", "الدخل", "المرونة"],
    wetTag: "أمطار غزيرة · خطر جريان التربة المكشوفة",
    growTag: "رطوبة نشطة · نمو الغطاء النباتي",
    aridTag: "أمطار خفيفة · مراقبة نقص المياه",
    hotTag: "حرارة وجفاف صيفي · ما بعد الحصاد",
    currentTag: "الحالي",
    bestTag: "الأنسب",
    baselinePill: "مرجع",
    baselineBench: "معيار المقارنة",
    kickerBase: "المرجع",
    kickerAlt: "بديل مقترح",
    bareWetShort: "ي مكشوف·ممطر",
    bareWetYr: "يوم مكشوف/سنة",
    fitAria: (name, total) => `${name}: الملاءمة ${total} من 100`,
    deltaShort: (d) => (d > 0 ? `−${d} ي` : `+${Math.abs(d)} ي`),
    deltaLong: (d) =>
      d > 0 ? `${d} يوم انكشاف أقل` : `${Math.abs(d)} يوم انكشاف إضافي`,
    skyAlts: (ha, place) => [
      "المدار · 1300 كم",
      "الجزائر · 120 كم",
      `${place || "الجزائر"} · 11 كم`,
      `تحديد القطعة · ${ha} هـ`,
    ],
    scenActive: (r, tm) => {
      const b: string[] = [];
      if (r) b.push(`${r > 0 ? "+" : ""}${r}% مطر`);
      if (tm) b.push(`+${tm}°C`);
      return b.length ? b.join(" · ") : "المرجع";
    },
    sparkTip: (mName, mm) => `${mName} معدل 30 سنة: ${mm} مم (انقر للانتقال)`,
    presetTip: (p) => `${p.name} · انحدار ${p.slope}% · ${p.elev} م`,
    presetOpt: (p) => `${p.name} (انحدار ${p.slope}%)`,
    ovTip: (mName, rain, cov) => `${mName}: ${rain} مم مطر · ${cov}% غطاء نباتي`,
    ovCapBase: (exp, slope) =>
      `${exp} يوم تربة مكشوفة وممطرة/سنة على انحدار ${slope}%. الأعمدة الحمراء تشير لتساقط الأمطار على تربة عارية.`,
    ovCapAlt: (exp, saved) =>
      saved > 0
        ? `يخفض خطر التربة المكشوفة إلى ${exp} يوم/سنة (${saved} يوماً أقل مقارنة بالبور الحالي).`
        : `${exp} يوم تربة مكشوفة/سنة في هذا السيناريو المناخي.`,
    onParcelBase: (name, slope, elev, exp, wet) =>
      `في ${name} (انحدار ${slope}%، ارتفاع ${elev} م)، يعرّض النمط الحالي التربة لمدة ${exp} من أصل ${wet} يوم ممطر سنوياً.`,
    onParcelAlt: (name, slope, elev, exp, delta) =>
      `في ${name} (انحدار ${slope}%، ارتفاع ${elev} م)، ينخفض الانكشاف إلى ${exp} يوم/سنة — أي ${
        delta > 0 ? `${delta} يوماً أقل` : `${Math.abs(delta)} يوماً أكثر`
      } مقارنة بالقمح والبور.`,
    evidence: (clim, peakRain, peakMonth, slope, elev, pName, s) => [
      `أرصاد POWER 1996–2025: ${clim.annual} مم/سنة (تشتت ${clim.cv} · ${clim.frost} يوم صقيع/سنة)، ذروة ${peakRain} مم (${peakMonth}).`,
      `نموذج التضاريس 30 م AWS: انحدار ${slope}% على ارتفاع ${elev} م في ${pName}.`,
      s.current
        ? "يؤكد مؤشر NDVI انخفاض الغطاء الشتوي أثناء ذروة الأمطار فوق الأرض البور."
        : s.id === "s1"
        ? clim.frost >= 10
          ? "يتحمل الفول والشعير برودة الهضاب العليا شتاءً مع تثبيت الآزوت قبل الحبوب."
          : "يحافظ الفول على غطاء شتوي ويثبت الآزوت قبل دورة القمح والشعير."
        : clim.annual < 320
        ? "بقايا البيقية تقلص التبخر في المناخ الجاف، والحمص يخفض استهلاك مياه السقي."
        : "يغلق مزيج البيقية والشوفان الغطاء قبل عواصف الخريف، ويمنح الحمص تحملاً للجفاف.",
    ],
    probeTitle: "فحص التضاريس",
    probeElev: (h) => `${h} م ارتفاع`,
    probeLoading: "جاري تحميل الارتفاع…",
    climates: {
      inland: "647 مم/سنة · تشتت 0.23 · 3.6 يوم صقيع",
      guelma: "790 مم/سنة · تشتت 0.21 · 3.9 يوم صقيع",
      constantine: "590 مم/سنة · تشتت 0.22 · 19.5 يوم صقيع",
      mila: "683 مم/سنة · تشتت 0.20 · 3.4 يوم صقيع",
      biskra: "241 مم/سنة · تشتت 0.39 · 3.5 يوم صقيع",
    },
    legends: {
      ndvi: { ...LEGENDS.ndvi, title: "الغطاء النباتي", lo: "عارية", hi: "كثيف" },
      sm: { ...LEGENDS.sm, title: "رطوبة الجذور", lo: "جافة", hi: "مشبعة" },
      rain: { ...LEGENDS.rain, title: "شدة الأمطار", lo: "0 مم/س", hi: "30+ مم/س" },
      lst: { ...LEGENDS.lst, title: "حرارة السطح", lo: "معتدل", hi: "حار" },
    },
    presets: {
      tidjelabine: {
        short: "تيجلابين",
        name: "مرتفعات تيجلابين · بومرداس",
        zone: "منحدر حبوب مطرية · تربة طينية طمية",
        note: "منحدر زراعي للحبوب جنوب بومرداس. تفقد التربة المحروثة المكشوفة الرطوبة والتربة السطحية بسرعة خلال عواصف نوفمبر–جانفي.",
      },
      guelma: {
        short: "قالمة",
        name: "سهل سيبوس الرسوبي · قالمة",
        zone: "مدرج نهري مستوٍ · طمي طيني رطب",
        note: "قطعة زراعية مستوية (2.0%) في حوض وادي سيبوس الرطب (790 مم/سنة). خطر التعرية ضئيل للغاية فتتصدر خصوبة الآزوت والعائد الاقتصادي الأولوية.",
      },
      constantine: {
        short: "قسنطينة",
        name: "الهضاب العليا الخروب · قسنطينة",
        zone: "هضبة حبوب مرتفعة · تربة كلسية طينية",
        note: "شريط حبوب مفتوح بالهضاب العليا على ارتفاع 673 م مع 19.5 يوم صقيع سنوياً. يتفوق الشعير والفول شتاءً بينما يتأثر الحمص ببرد الربيع.",
      },
      mila: {
        short: "ميلة",
        name: "سفوح بني هارون التلية · ميلة",
        zone: "منحدر تلي شديد الميل · طين مارني",
        note: "منحدر تلي بنسبة انحدار 12.9% على ارتفاع 504 م بحوض بني هارون. الغطاء النباتي الخريفي المستمر ضروري لوقف انجراف التربة السطحية.",
      },
      biskra: {
        short: "بسكرة",
        name: "محيط الزيبان المسقي · بسكرة",
        zone: "واحة هامشية جافة · تربة رملية طمية",
        note: "قطعة فلاحية مسقية في حزام الزيبان الجاف (241 مم/سنة وتذبذب مطري مرتفع 0.39). الشعير والحمص والغطاء الحافظ للرطوبة يقللون استهلاك مياه السقي.",
      },
    },
    strats: {
      s0: {
        name: "قمح صلب ← بور",
        tag: "الحالي",
        conf: "ثقة متوسطة",
        why: "الممارسة المرجعية المحلية: قمح صلب يليه موسم بور محروث لتخزين رطوبة التربة. تُقاس كل الخطط البديلة مقارنةً بهذا المسار.",
        benefits: [
          "يخزّن البور رطوبة للموسم الموالي دون تكاليف بذور أو عمليات زراعية إضافية.",
          "سلسلة تسويق مألوفة وتقويم فلاحي معروف محلياً.",
        ],
        gaps: [
          "لا يوجد تحليل مخبري للتربة؛ الكربون العضوي والقوام مستنتجان نموذجياً.",
          "تُقدَّر رطوبة البور من المعدلات المناخية دون مجسّات ميدانية في الحقل.",
        ],
        risks: [
          "ترك الأرض عارية خلال أشد أمطار نوفمبر–جانفي يعرض التربة للانجراف السطحي.",
          "الاعتماد على محصول نقدي واحد يرفع خطر تراجع الدخل في المواسم الجافة.",
        ],
      },
      s1: {
        name: "قمح ← فول ← شعير",
        tag: "بقوليات",
        conf: "ثقة متوسطة",
        why: "دورة متوسطية ثلاثية: تكسر البقوليات الشتوية دورة أمراض الحبوب وتثبت الآزوت الجوي خلال السنة التي تبقى فيها القطعة بوراً.",
        benefits: [
          "يقلّص أيام التربة المكشوفة والممطرة بشكل ملحوظ مع الإبقاء على ثلاثة محاصيل مسوَّقة.",
          "تثبيت الآزوت يقلل الحاجة للأسمدة المعدنية في محصول القمح الموالي.",
          "يوفر تنويعاً بين الحبوب والأعلاف عبر الفول والشعير.",
        ],
        gaps: [
          "أسعار الفول محلياً والطلب التعاقدي يحتاجان تأكيداً من المصالح الفلاحية.",
          "ضغط الأمراض الفطرية (التبقع الشوكولاتي والأسكوكيتا) غير مدمج في الحساب.",
        ],
        risks: [
          "الفول أكثر استهلاكاً للماء من القمح؛ جفاف الربيع يضعف امتلاء القرون.",
          "تتطلب الدورات الثلاث تنسيقاً أدق لمواعيد البذر والخدمة.",
        ],
      },
      s2: {
        name: "قمح ← بيقية-شوفان ← حمص",
        tag: "غطاء واقٍ",
        conf: "ثقة متوسطة",
        why: "يغلق فجوة الخريف العارية مباشرة: ينمو خليط البيقية والشوفان سريعاً لحماية التربة قبل أمطار نوفمبر، يليه حمص ربيعي مقاوم للجفاف.",
        benefits: [
          "يحقق أقل عدد أيام انكشاف للتربة تحت أمطار الخريف والشتاء.",
          "تثبت البيقية الآزوت بينما ترفع الجذور والمخلفات المادة العضوية للتربة.",
          "الحمص أقل استهلاكاً للماء وأشد تحملاً للحرارة مقارنة بالفول.",
        ],
        gaps: [
          "الموعد الأمثل لإنهاء الغطاء النباتي يعتمد على رطوبة الربيع الفعلية.",
          "تقلبات أسعار الحمص في الأسواق المحلية تحتاج تحققاً ميدانياً.",
        ],
        risks: [
          "تأخر أمطار أكتوبر يؤخر إنبات الغطاء ويقلص الحماية المبكرة من التعرية.",
          "الحقول الداخلية المرتفعة (> 500 م) قد تتأثر بموجات الصقيع وقت إزهار الحمص.",
        ],
      },
    },
  },
};

export function getLoc(lang: Lang): LocaleDict {
  return I18N[lang] || I18N.en;
}

export function pLoc(p: Preset, loc: LocaleDict): Preset {
  const ov = loc.presets?.[p.id];
  return ov ? { ...p, ...ov } : p;
}

export function sLoc(s: StrategyDef, loc: LocaleDict): StrategyDef {
  const ov = loc.strats?.[s.id];
  return ov ? { ...s, ...ov } : s;
}

