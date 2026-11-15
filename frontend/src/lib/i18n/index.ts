import type {
  CropCategory,
  CropRole,
  EvidenceParameter,
  IrrigationSystem,
  Language,
  MarketPreference,
  Season,
  SoilType,
  StressType,
  WaterAvailability,
  WaterSource,
} from "@/lib/schemas";

import { localizeAnalysisText } from "./dynamicText";

export interface UiDictionary {
  brandTitle: string;
  brandSubtitle: string;
  nav: {
    dashboard: string;
    selectField: string;
    farmProfile: string;
    comparison: string;
    evidence: string;
  };
  chrome: {
    fixtureMode: string;
    plainModeOn: string;
    plainModeOff: string;
    plainModeTooltip: string;
    guestWorkspace: string;
    accountWorkspace: string;
    signIn: string;
    launchDemo: string;
    claimAccount: string;
    quartersLabel: string;
    quartersRule: string;
    systemOk: string;
    systemDegraded: string;
    activeParcel: string;
    noParcel: string;
  };
  auth: {
    welcomeTitle: string;
    welcomeBody: string;
    launchDemoBtn: string;
    signInTab: string;
    registerTab: string;
    email: string;
    password: string;
    fullName: string;
    submitLogin: string;
    submitRegister: string;
    claimBannerTitle: string;
    claimBannerBody: string;
    claimNowBtn: string;
    exportDataBtn: string;
    endGuestBtn: string;
    deleteAccountBtn: string;
    deleteConfirmText: string;
    logoutBtn: string;
    signedInSuccess: string;
    claimedGuestMsg: (count: number) => string;
    jsonDownloaded: string;
    closeModalAria: string;
  };
  dashboard: {
    heroEyebrow: string;
    heroTitle: string;
    heroSubtitle: string;
    ctaSelectField: string;
    ctaRunAnalysis: string;
    kpiParcels: string;
    kpiQuota: string;
    kpiAdopted: string;
    kpiReadiness: string;
    noStrategyYet: string;
    riskSummaryTitle: string;
    historyTitle: string;
    openComparison: string;
    simulateDegradedLabel: string;
  };
  selectField: {
    title: string;
    subtitle: string;
    instantJump: string;
    drawModeOn: string;
    drawModeOff: string;
    clearPolygon: string;
    insideGuelma: string;
    outsideGuelma: string;
    presetsTitle: string;
    outsideTestBtn: string;
    farmLabel: string;
    createFarmBtn: string;
    newFarmName: string;
    fieldIdLabel: string;
    fieldNameLabel: string;
    areaLabel: string;
    elevationLabel: string;
    elevationUnknownHint: string;
    saveContinueBtn: string;
    mapAttribution: string;
    verticesUnit: string;
    parcelsPanelTitle: string;
    newParcelBadge: string;
    latLabel: string;
    lngLabel: string;
    nullPlaceholder: string;
    savingBtn: string;
  };
  farmProfile: {
    title: string;
    subtitle: string;
    secCropHistory: string;
    secSoil: string;
    secWater: string;
    secPlanning: string;
    secPriorities: string;
    addHistoryRow: string;
    otherLocalCrop: string;
    soilUnknownTitle: string;
    soilUnknownDesc: string;
    soilKnownTitle: string;
    soilKnownDesc: string;
    usdaHelperBtn: string;
    usdaTitle: string;
    usdaApply: string;
    waterAvailability: string;
    waterSource: string;
    waterSourceOther: string;
    irrigationSystem: string;
    startSeason: string;
    startYear: string;
    plantingMonth: string;
    horizonSeasons: string;
    cycleMode: string;
    whatIfTitle: string;
    tempDelta: string;
    precipDelta: string;
    weightsSum: string;
    autoBalanceBtn: string;
    marketPreference: string;
    targetCrops: string;
    excludedCrops: string;
    equipmentConstraints: string;
    submitBtn: string;
    pollingTitle: string;
    cancelJobBtn: string;
    seasonLabel: string;
    yearLabel: string;
    cropLabel: string;
    selectCropPlaceholder: string;
    customCropExample: string;
    seasonCheckOk: string;
    soilTextureLabel: string;
    soilPhLabel: string;
    organicMatterLabel: string;
    labTestDateLabel: string;
    annualRotationLabel: string;
    consecutiveSeasonsLabel: string;
    presetBalanced: string;
    presetYield: string;
    presetDrought: string;
    presetLowRisk: string;
    readyToAnalyze: string;
    fixValidationGuards: string;
    statusPrefix: string;
    soilBadgeUnknown: string;
    soilBadgeFarmer: string;
  };
  comparison: {
    title: string;
    subtitle: string;
    degradedBannerTitle: string;
    degradedAge: string;
    recommendedBadge: string;
    baselineBadge: string;
    selectedBadge: string;
    rejectedBadge: string;
    selectStrategyBtn: string;
    rejectStrategyBtn: string;
    bareDaysLabel: string;
    bareDaysPlain: string;
    riskCalendarTitle: string;
    bareWindowTitle: string;
    bareWindowPlain: string;
    stressWindowTitle: string;
    requestedCropsTitle: string;
    benefitsTitle: string;
    risksTitle: string;
    gapsTitle: string;
    whatIfTitle: string;
    whatIfRunBtn: string;
    printBriefBtn: string;
    loadingText: string;
    emptyTitle: string;
    emptyBody: string;
    openProfileBtn: string;
    partialFieldBanner: string;
    radarHeading: string;
    replacedByLabel: string;
    inspectDetailsBtn: string;
    hideDetailsBtn: string;
    mitigationLabel: string;
    whatIfHint: string;
    runningBtn: string;
    tempShiftLabel: string;
    precipChangeLabel: string;
    noBareGaps: string;
    noStressWindows: string;
    seasonsUnitAria: string;
    tableSource: string;
    tableValue: string;
    tablePeriod: string;
    tableInterpretation: string;
  };
  evidence: {
    title: string;
    subtitle: string;
    filterAll: string;
    filterFarmer: string;
    filterDataset: string;
    fusionTitle: string;
    fusionBody: string;
    qualityTitle: string;
    missingDataTitle: string;
    fixInProfileBtn: string;
    spatialTitle: string;
    spatialNote: string;
    directBadge: string;
    derivedBadge: string;
    loadingText: string;
    emptyTitle: string;
    emptyBody: string;
    tagFilterLabel: string;
    tagAll: string;
  };
  common: {
    backToCommandCenter: string;
    checkingDeps: string;
    datasetLabel: string;
    engineLabel: string;
    completenessLabel: string;
    startingLabel: string;
    savingLabel: string;
    runningLabel: string;
    quartersShort: string;
    daysPerYearShort: string;
    removeBtn: string;
    okShort: string;
    bareShort: string;
    ariaLanguageSwitcher: string;
    ariaMobileNav: string;
    ariaToolRail: string;
    ariaWorkflowNav: string;
    ariaCloseModal: string;
    radarAria: string;
    logoTagline: string;
    notFoundTitle: string;
    notFoundDesc: string;
    notFoundBackBtn: string;
  };
  usda: {
    closeAria: string;
    adrRuleText: string;
    percentLabel: string;
    clayLabel: string;
    siltLabel: string;
    sandLabel: string;
    derivedSoilTypeLabel: string;
  };
  brief: {
    docHeading: string;
    strategyPrefix: string;
    metaField: string;
    metaDataset: string;
    metaEngine: string;
    metaGenerated: string;
    seasonSeqHeading: string;
    colNumber: string;
    colSeasonYear: string;
    colCrop: string;
    colCategoryRole: string;
    colIrrigation: string;
    colReason: string;
    risksHeading: string;
    severityPrefix: string;
    mitigationPrefix: string;
    citationsHeading: string;
    colParameter: string;
    colSource: string;
    colValue: string;
    colDatePeriod: string;
    disclaimerPrefix: string;
  };
}

export const UI_DICT: Record<Language, UiDictionary> = {
  en: {
    brandTitle: "FELLAH TECH",
    brandSubtitle: "Agricultural Intelligence & Decision Support · Wilaya of Guelma",
    nav: {
      dashboard: "Dashboard",
      selectField: "Select Your Field",
      farmProfile: "Farm Profile",
      comparison: "Rotations",
      evidence: "Evidence",
    },
    chrome: {
      fixtureMode: "FIXTURE MODE",
      plainModeOn: "Plain Farmer (Aa): ON",
      plainModeOff: "Plain Farmer (Aa)",
      plainModeTooltip: "Translate technical terms into clear everyday farm language",
      guestWorkspace: "Guelma Guest Sandbox",
      accountWorkspace: "Registered Farm Account",
      signIn: "Sign In / Account",
      launchDemo: "Launch Guelma Demo",
      claimAccount: "Claim Guest Data",
      quartersLabel: "Guest Analysis Budget",
      quartersRule: "1 full = 4 qtrs | scenario tweak = 1 qtr",
      systemOk: "Dataset & ML Ready",
      systemDegraded: "Degraded / Replay Mode",
      activeParcel: "Active Parcel",
      noParcel: "No Parcel Selected",
    },
    auth: {
      welcomeTitle: "Wilaya of Guelma Farm Planning Workspace",
      welcomeBody:
        "Start an instant Guelma Guest Sandbox with pre-designated parcel F1, or sign in with your registered farm account.",
      launchDemoBtn: "Launch Guelma Demo Workspace",
      signInTab: "Sign In",
      registerTab: "Register Free Account",
      email: "Email Address",
      password: "Password (min 8 chars)",
      fullName: "Full Name",
      submitLogin: "Sign In",
      submitRegister: "Create Account",
      claimBannerTitle: "Preserve Your Guest Farms & Analyses",
      claimBannerBody: "Transfer your current Guelma guest farms into this permanent account.",
      claimNowBtn: "Claim Guest Session",
      exportDataBtn: "Export JSON Data",
      endGuestBtn: "Reset Guest Session",
      deleteAccountBtn: "Delete Account Permanently",
      deleteConfirmText: "Permanently delete account and all farm records?",
      logoutBtn: "Log Out",
      signedInSuccess: "Signed in successfully.",
      claimedGuestMsg: (count) => `Claimed ${count} guest farm(s) into your account.`,
      jsonDownloaded: "JSON export downloaded.",
      closeModalAria: "Close authentication modal",
    },
    dashboard: {
      heroEyebrow: "WILAYA OF GUELMA · AGRICULTURAL INTELLIGENCE",
      heroTitle: "Climate-Resilient Crop Rotation Planner",
      heroSubtitle:
        "Fuse farmer soil & water observations with pinned local climate baselines (Schema: dataset) for multi-season crop planning.",
      ctaSelectField: "Select or Draw Parcel",
      ctaRunAnalysis: "Configure & Run Analysis",
      kpiParcels: "Active Parcels",
      kpiQuota: "Analysis Budget",
      kpiAdopted: "Adopted Strategy",
      kpiReadiness: "Data & ML Readiness",
      noStrategyYet: "No strategy selected yet",
      riskSummaryTitle: "Parcel & Environmental Risk Summary",
      historyTitle: "Analysis Run History",
      openComparison: "Open Comparison",
      simulateDegradedLabel: "Preview Last-Good Replay Banner (ADR-8)",
    },
    selectField: {
      title: "Select Your Field · Guelma Orbital Map",
      subtitle:
        "Inspect the PostGIS Guelma boundary, draw custom parcel vertices, or load one of 6 verified Guelma test zones.",
      instantJump: "Instant Jump",
      drawModeOn: "Drawing Polygon (Click Map)",
      drawModeOff: "Draw Parcel Polygon",
      clearPolygon: "Clear Ring",
      insideGuelma: "Inside Guelma MVP Boundary",
      outsideGuelma: "Outside Guelma Boundary",
      presetsTitle: "6 Verified Guelma Test Shapes",
      outsideTestBtn: "Load Setif Outside Test (36.19°N, 5.41°E)",
      farmLabel: "Active Farm",
      createFarmBtn: "Create Farm",
      newFarmName: "New Farm Name",
      fieldIdLabel: "Parcel ID",
      fieldNameLabel: "Parcel Name",
      areaLabel: "Area (ha)",
      elevationLabel: "Elevation (m, optional)",
      elevationUnknownHint: "Leave blank if unknown (never auto-filled from DEM)",
      saveContinueBtn: "Save Parcel & Continue to Farm Profile",
      mapAttribution:
        "Visual Satellite Basemap · Agronomic scoring uses pinned Backend Schema: dataset",
      verticesUnit: "vertices",
      parcelsPanelTitle: "Farm Parcels",
      newParcelBadge: "New Parcel",
      latLabel: "Latitude",
      lngLabel: "Longitude",
      nullPlaceholder: "Not set (null)",
      savingBtn: "Saving...",
    },
    farmProfile: {
      title: "Farm Profile & Rotation Priorities",
      subtitle:
        "Verify parcel history, honest soil provenance, irrigation capacity, and priority weights summing strictly to 100.",
      secCropHistory: "1. Past Crop History (1–30 Seasons)",
      secSoil: "2. Soil Provenance (ADR-5)",
      secWater: "3. Water & Irrigation Regime",
      secPlanning: "4. Planning Window & Climate Scenario",
      secPriorities: "5. Farmer Priorities (Sum = 100) & Crop Constraints",
      addHistoryRow: "Add Past Season",
      otherLocalCrop: "Other local crop name",
      soilUnknownTitle: "Unknown / No Soil Test Yet",
      soilUnknownDesc: "Records soil_source: unknown transparently without guessing chemistry.",
      soilKnownTitle: "I Know My Soil Type / Have Lab Results",
      soilKnownDesc: "Enter known texture and optional laboratory pH / organic matter.",
      usdaHelperBtn: "USDA Texture Lab Converter",
      usdaTitle: "Convert Lab Sand / Silt / Clay to SoilType",
      usdaApply: "Apply Derived Soil Type",
      waterAvailability: "Water Availability",
      waterSource: "Primary Water Source",
      waterSourceOther: "Describe Other Water Source",
      irrigationSystem: "Irrigation Hardware",
      startSeason: "Start Season",
      startYear: "Start Year",
      plantingMonth: "Planting Month (Northern Hemisphere Guard)",
      horizonSeasons: "Horizon Seasons (1–6)",
      cycleMode: "Cycle Mode",
      whatIfTitle: "Climate Stress What-If Overrides",
      tempDelta: "Temperature Shift (°C)",
      precipDelta: "Precipitation Change (%)",
      weightsSum: "Priority Total",
      autoBalanceBtn: "Auto-Balance to 100",
      marketPreference: "Market Orientation",
      targetCrops: "Target Crops (Must Consider)",
      excludedCrops: "Excluded Crops (Never Recommend)",
      equipmentConstraints: "Equipment / Field Constraints",
      submitBtn: "Save Profile & Run Rotation Analysis",
      pollingTitle: "Running Agronomic Rotation Optimization",
      cancelJobBtn: "Cancel Analysis Request",
      seasonLabel: "Season",
      yearLabel: "Year",
      cropLabel: "Crop",
      selectCropPlaceholder: "Select crop",
      customCropExample: "e.g. Blé dur local",
      seasonCheckOk: "Northern Hemisphere season check OK",
      soilTextureLabel: "Soil Texture",
      soilPhLabel: "Soil pH (3.0–11.0)",
      organicMatterLabel: "Organic Matter %",
      labTestDateLabel: "Lab Test Date",
      annualRotationLabel: "Annual Rotation",
      consecutiveSeasonsLabel: "Consecutive Seasons",
      presetBalanced: "Balanced Soil",
      presetYield: "Income & Yield",
      presetDrought: "Water Resilience",
      presetLowRisk: "Low Risk",
      readyToAnalyze: "Ready to analyze parcel",
      fixValidationGuards: "Fix validation guards before running.",
      statusPrefix: "Status:",
      soilBadgeUnknown: "Source: unknown",
      soilBadgeFarmer: "Source: farmer",
    },
    comparison: {
      title: "Rotation Strategy Comparison",
      subtitle:
        "Compare baseline continuity against multi-season rotations grounded in Backend AnalysisResult v5.x.",
      degradedBannerTitle: "DEGRADED REPLAY · STALE CACHED ANALYSIS (ADR-8)",
      degradedAge: "Replay Age",
      recommendedBadge: "Recommended Fit",
      baselineBadge: "Existing Baseline",
      selectedBadge: "Selected Plan",
      rejectedBadge: "Rejected",
      selectStrategyBtn: "Select This Strategy",
      rejectStrategyBtn: "Reject",
      bareDaysLabel: "Bare Field Exposure (days/yr)",
      bareDaysPlain: "Days per year with uncovered soil",
      riskCalendarTitle: "12-Month Agronomic Risk Calendar",
      bareWindowTitle: "Bare-Field Exposure Windows",
      bareWindowPlain: "Months when bare soil loses water to heat and wind",
      stressWindowTitle: "Seasonal Climate Stress Windows",
      requestedCropsTitle: "Requested Crop Outcomes",
      benefitsTitle: "Agronomic Benefits",
      risksTitle: "Risks & Mitigations",
      gapsTitle: "Assumptions, Information Gaps & Local Review",
      whatIfTitle: "Quick Climate What-If Comparison",
      whatIfRunBtn: "Run Climate Tweak (1 Quarter)",
      printBriefBtn: "Print / Save 1-Page Brief",
      loadingText: "Loading rotation comparison...",
      emptyTitle: "No rotation analysis selected yet",
      emptyBody:
        "Configure crop history, soil, water, and priorities in Farm Profile to compute ranked multi-season rotation strategies.",
      openProfileBtn: "Open Farm Profile",
      partialFieldBanner: "Partial field result:",
      radarHeading: "Multi-Axis Agronomic Balance",
      replacedByLabel: "Replaced by:",
      inspectDetailsBtn: "Inspect Benefits, Risks & Gaps",
      hideDetailsBtn: "Hide Agronomic Breakdown",
      mitigationLabel: "Mitigation:",
      whatIfHint: "Test hotter/drier seasons against this field profile.",
      runningBtn: "Running...",
      tempShiftLabel: "Temperature Shift",
      precipChangeLabel: "Precipitation Change",
      noBareGaps: "No bare-soil gaps flagged.",
      noStressWindows: "No major stress windows detected.",
      seasonsUnitAria: "seasons",
      tableSource: "Source",
      tableValue: "Value",
      tablePeriod: "Mission / Period",
      tableInterpretation: "Interpretation",
    },
    evidence: {
      title: "Environmental Evidence & Data Transparency",
      subtitle:
        "Inspect every farmer input and pinned dataset baseline driving recommendations, plus explicit data gaps.",
      filterAll: "All Sources",
      filterFarmer: "Farmer Inputs (farmer_input)",
      filterDataset: "Local Dataset / EO (dataset)",
      fusionTitle: "Why Combine Satellite Baselines + Farmer Records?",
      fusionBody:
        "Coarse satellite climate grids cannot see your private well pump, drip pipes, or last autumn's crop. Fusing pinned regional Schema: dataset signals with your parcel records eliminates guesswork.",
      qualityTitle: "Data Quality & Uncertainty Ledger",
      missingDataTitle: "Missing Measurements Reducing Confidence",
      fixInProfileBtn: "Supply Measurements in Farm Profile",
      spatialTitle: "Parcel Spatial Reference (Visual Context Only)",
      spatialNote:
        "Satellite imagery provides visual orientation; agronomic inference reads exclusively from pinned dataset_version.",
      directBadge: "Direct Observation",
      derivedBadge: "Derived Dataset Signal",
      loadingText: "Loading evidence ledger...",
      emptyTitle: "No analysis evidence loaded yet",
      emptyBody:
        "Run or open a field rotation analysis first to inspect full provenance, satellite telemetry, and data completeness.",
      tagFilterLabel: "Agronomic tag:",
      tagAll: "All",
    },
    common: {
      backToCommandCenter: "Command Center",
      checkingDeps: "Checking dependencies",
      datasetLabel: "Dataset",
      engineLabel: "Engine",
      completenessLabel: "Completeness",
      startingLabel: "Starting...",
      savingLabel: "Saving...",
      runningLabel: "Running...",
      quartersShort: "qtrs",
      daysPerYearShort: "d/yr",
      removeBtn: "Remove",
      okShort: "OK",
      bareShort: "BARE",
      ariaLanguageSwitcher: "Language switcher",
      ariaMobileNav: "Mobile workspace navigation",
      ariaToolRail: "Spatial tool rail",
      ariaWorkflowNav: "Analysis studio workflow",
      ariaCloseModal: "Close modal",
      radarAria: "7-axis agronomic strategy score comparison",
      logoTagline: "Precision Farm Rotations",
      notFoundTitle: "Page Not Found",
      notFoundDesc: "The requested workspace route does not exist.",
      notFoundBackBtn: "Return to Command Center",
    },
    usda: {
      closeAria: "Close USDA texture converter",
      adrRuleText:
        "ADR-5 exact rule: Farmer clay + silt + sand percentages must sum to 100% and map deterministically to USDA SoilType.",
      percentLabel: "Percent (%)",
      clayLabel: "Clay",
      siltLabel: "Silt",
      sandLabel: "Sand",
      derivedSoilTypeLabel: "Derived SoilType:",
    },
    brief: {
      docHeading: "FELLAH TECH — 1-Page Field Rotation Brief",
      strategyPrefix: "Strategy:",
      metaField: "Field:",
      metaDataset: "Dataset:",
      metaEngine: "Engine:",
      metaGenerated: "Generated:",
      seasonSeqHeading: "Season Sequence",
      colNumber: "#",
      colSeasonYear: "Season / Year",
      colCrop: "Crop",
      colCategoryRole: "Category / Role",
      colIrrigation: "Irrigation",
      colReason: "Reason",
      risksHeading: "Key Risks & Mitigations",
      severityPrefix: "Severity:",
      mitigationPrefix: "Mitigation:",
      citationsHeading: "Evidence Citations",
      colParameter: "Parameter",
      colSource: "Source",
      colValue: "Value",
      colDatePeriod: "Date / Period",
      disclaimerPrefix: "Disclaimer:",
    },
  },
  fr: {
    brandTitle: "FELLAH TECH",
    brandSubtitle: "Intelligence agricole & aide à la décision · Wilaya de Guelma",
    nav: {
      dashboard: "Tableau de bord",
      selectField: "Choisir la parcelle",
      farmProfile: "Profil agricole",
      comparison: "Rotations",
      evidence: "Preuves",
    },
    chrome: {
      fixtureMode: "MODE FIXTURE",
      plainModeOn: "Langage simple (Aa) : ACTIF",
      plainModeOff: "Langage simple (Aa)",
      plainModeTooltip: "Afficher les explications en langage agricole simple",
      guestWorkspace: "Bac à sable Invité Guelma",
      accountWorkspace: "Compte Agricole Enregistré",
      signIn: "Connexion / Compte",
      launchDemo: "Lancer Démo Guelma",
      claimAccount: "Récupérer session invité",
      quartersLabel: "Quota d'analyse invité",
      quartersRule: "1 complète = 4 trim. | scénario = 1 trim.",
      systemOk: "Jeu de données & ML prêts",
      systemDegraded: "Mode dégradé / Relecture",
      activeParcel: "Parcelle active",
      noParcel: "Aucune parcelle",
    },
    auth: {
      welcomeTitle: "Espace Planification Agricole · Wilaya de Guelma",
      welcomeBody:
        "Démarrez un bac à sable invité à Guelma avec la parcelle F1 ou connectez-vous avec votre compte.",
      launchDemoBtn: "Lancer l'espace démo Guelma",
      signInTab: "Connexion",
      registerTab: "Créer un compte gratuit",
      email: "Adresse e-mail",
      password: "Mot de passe (8 car. min)",
      fullName: "Nom complet",
      submitLogin: "Se connecter",
      submitRegister: "Créer le compte",
      claimBannerTitle: "Conservez vos fermes et analyses invité",
      claimBannerBody: "Transférez vos fermes invité de Guelma vers ce compte permanent.",
      claimNowBtn: "Réclamer la session invité",
      exportDataBtn: "Exporter JSON",
      endGuestBtn: "Réinitialiser session invité",
      deleteAccountBtn: "Supprimer le compte",
      deleteConfirmText: "Supprimer définitivement le compte et toutes les données ?",
      logoutBtn: "Déconnexion",
      signedInSuccess: "Connexion réussie.",
      claimedGuestMsg: (count) =>
        `${count} ferme(s) invitée(s) rattachée(s) à votre compte.`,
      jsonDownloaded: "Export JSON téléchargé.",
      closeModalAria: "Fermer la fenêtre de connexion",
    },
    dashboard: {
      heroEyebrow: "WILAYA DE GUELMA · INTELLIGENCE AGRICOLE",
      heroTitle: "Planificateur de rotation culturale résilient",
      heroSubtitle:
        "Combinez vos observations de sol et d'eau avec les références climatiques locales épinglées (Schema: dataset).",
      ctaSelectField: "Choisir ou tracer une parcelle",
      ctaRunAnalysis: "Configurer et analyser",
      kpiParcels: "Parcelles actives",
      kpiQuota: "Budget d'analyse",
      kpiAdopted: "Stratégie adoptée",
      kpiReadiness: "État données & ML",
      noStrategyYet: "Aucune stratégie sélectionnée",
      riskSummaryTitle: "Synthèse des risques de la parcelle",
      historyTitle: "Historique des analyses",
      openComparison: "Ouvrir comparaison",
      simulateDegradedLabel: "Prévisualiser bannière relecture dégradée (ADR-8)",
    },
    selectField: {
      title: "Choisir votre parcelle · Carte orbitale Guelma",
      subtitle:
        "Visualisez le périmètre PostGIS de Guelma, tracez un polygone ou chargez l'une des 6 parcelles vérifiées.",
      instantJump: "Saut instantané",
      drawModeOn: "Tracé actif (Cliquez sur la carte)",
      drawModeOff: "Tracer le polygone",
      clearPolygon: "Effacer le tracé",
      insideGuelma: "Dans le périmètre MVP de Guelma",
      outsideGuelma: "Hors périmètre de Guelma",
      presetsTitle: "6 formes vérifiées à Guelma",
      outsideTestBtn: "Tester hors zone · Sétif (36.19°N, 5.41°E)",
      farmLabel: "Exploitation active",
      createFarmBtn: "Créer ferme",
      newFarmName: "Nom de la ferme",
      fieldIdLabel: "ID Parcelle",
      fieldNameLabel: "Nom de la parcelle",
      areaLabel: "Surface (ha)",
      elevationLabel: "Altitude (m, optionnel)",
      elevationUnknownHint: "Laisser vide si inconnue (jamais remplie via DEM)",
      saveContinueBtn: "Enregistrer et passer au profil agricole",
      mapAttribution:
        "Fond satellite visuel · Le calcul utilise uniquement Schema: dataset côté serveur",
      verticesUnit: "sommets",
      parcelsPanelTitle: "Parcelles de la ferme",
      newParcelBadge: "Nouvelle parcelle",
      latLabel: "Latitude",
      lngLabel: "Longitude",
      nullPlaceholder: "Non renseigné (null)",
      savingBtn: "Enregistrement...",
    },
    farmProfile: {
      title: "Profil agricole & priorités de rotation",
      subtitle:
        "Renseignez l'historique cultural, la provenance honnête du sol, l'irrigation et 5 poids totalisant 100.",
      secCropHistory: "1. Historique cultural (1–30 saisons)",
      secSoil: "2. Provenance du sol (ADR-5)",
      secWater: "3. Ressources en eau et irrigation",
      secPlanning: "4. Fenêtre de planification et climat",
      secPriorities: "5. Priorités (Total = 100) et contraintes",
      addHistoryRow: "Ajouter une saison",
      otherLocalCrop: "Autre culture locale",
      soilUnknownTitle: "Inconnu / Pas encore d'analyse",
      soilUnknownDesc: "Enregistre soil_source: unknown sans inventer de chimie du sol.",
      soilKnownTitle: "Je connais le type de sol / Résultats labo",
      soilKnownDesc: "Saisissez la texture et les analyses optionnelles pH / MO.",
      usdaHelperBtn: "Convertisseur texture USDA",
      usdaTitle: "Convertir Sable / Limon / Argile en SoilType",
      usdaApply: "Appliquer le type déduit",
      waterAvailability: "Disponibilité en eau",
      waterSource: "Source d'eau principale",
      waterSourceOther: "Préciser l'autre source",
      irrigationSystem: "Système d'irrigation",
      startSeason: "Saison de départ",
      startYear: "Année de départ",
      plantingMonth: "Mois de semis (Contrôle hémisphère Nord)",
      horizonSeasons: "Horizon (1–6 saisons)",
      cycleMode: "Mode de cycle",
      whatIfTitle: "Simulation climatique What-If",
      tempDelta: "Écart température (°C)",
      precipDelta: "Variation précipitations (%)",
      weightsSum: "Total des poids",
      autoBalanceBtn: "Équilibrer à 100",
      marketPreference: "Orientation marché",
      targetCrops: "Cultures souhaitées",
      excludedCrops: "Cultures exclues",
      equipmentConstraints: "Contraintes matérielles",
      submitBtn: "Enregistrer et lancer l'analyse",
      pollingTitle: "Optimisation agronomique en cours",
      cancelJobBtn: "Annuler la requête",
      seasonLabel: "Saison",
      yearLabel: "Année",
      cropLabel: "Culture",
      selectCropPlaceholder: "Choisir une culture",
      customCropExample: "ex. Blé dur local",
      seasonCheckOk: "Cohérence saisonnière hémisphère Nord OK",
      soilTextureLabel: "Texture du sol",
      soilPhLabel: "pH du sol (3,0–11,0)",
      organicMatterLabel: "Matière organique %",
      labTestDateLabel: "Date d'analyse laboratoire",
      annualRotationLabel: "Rotation annuelle",
      consecutiveSeasonsLabel: "Saisons consécutives",
      presetBalanced: "Équilibre du sol",
      presetYield: "Revenu & Rendement",
      presetDrought: "Résilience hydrique",
      presetLowRisk: "Risque minimal",
      readyToAnalyze: "Prêt pour l'analyse de la parcelle",
      fixValidationGuards: "Corrigez les alertes de validation avant de lancer.",
      statusPrefix: "Statut :",
      soilBadgeUnknown: "Source : inconnue",
      soilBadgeFarmer: "Source : exploitant",
    },
    comparison: {
      title: "Comparaison des stratégies de rotation",
      subtitle:
        "Comparez la continuité de référence aux rotations multi-saisons issues du contrat v5.x.",
      degradedBannerTitle: "MODE DÉGRADÉ · RELECTURE ANCIENNE (ADR-8)",
      degradedAge: "Âge du replay",
      recommendedBadge: "Recommandée",
      baselineBadge: "Référence actuelle",
      selectedBadge: "Plan retenu",
      rejectedBadge: "Rejetée",
      selectStrategyBtn: "Choisir cette stratégie",
      rejectStrategyBtn: "Rejeter",
      bareDaysLabel: "Exposition sol nu (jours/an)",
      bareDaysPlain: "Jours par an sans couverture végétale",
      riskCalendarTitle: "Calendrier agronomique sur 12 mois",
      bareWindowTitle: "Fenêtres de sol nu",
      bareWindowPlain: "Mois où le sol nu perd son humidité au soleil",
      stressWindowTitle: "Fenêtres de stress climatique",
      requestedCropsTitle: "Sort des cultures demandées",
      benefitsTitle: "Bénéfices agronomiques",
      risksTitle: "Risques et mesures d'atténuation",
      gapsTitle: "Hypothèses, lacunes et vérifications locales",
      whatIfTitle: "Test rapide de scénario climatique",
      whatIfRunBtn: "Tester le scénario (1 trimestre)",
      printBriefBtn: "Imprimer fiche 1 page",
      loadingText: "Chargement de la comparaison des rotations...",
      emptyTitle: "Aucune analyse de rotation sélectionnée",
      emptyBody:
        "Configurez l'historique cultural, le sol, l'eau et vos priorités dans le profil agricole pour générer des stratégies classées.",
      openProfileBtn: "Ouvrir le profil agricole",
      partialFieldBanner: "Résultat partiel de la parcelle :",
      radarHeading: "Équilibre agronomique multi-axes",
      replacedByLabel: "Remplacé par :",
      inspectDetailsBtn: "Voir bénéfices, risques & lacunes",
      hideDetailsBtn: "Masquer le détail agronomique",
      mitigationLabel: "Atténuation :",
      whatIfHint: "Testez des saisons plus chaudes ou plus sèches sur cette parcelle.",
      runningBtn: "Exécution...",
      tempShiftLabel: "Variation de température",
      precipChangeLabel: "Variation des précipitations",
      noBareGaps: "Aucune période de sol nu signalée.",
      noStressWindows: "Aucune fenêtre de stress majeur détectée.",
      seasonsUnitAria: "saisons",
      tableSource: "Source",
      tableValue: "Valeur",
      tablePeriod: "Mission / Période",
      tableInterpretation: "Interprétation",
    },
    evidence: {
      title: "Preuves environnementales et transparence",
      subtitle:
        "Consultez chaque donnée agriculteur et jeu de données régional utilisé ainsi que les données manquantes.",
      filterAll: "Toutes les sources",
      filterFarmer: "Saisies agriculteur",
      filterDataset: "Jeu local / Satellite",
      fusionTitle: "Pourquoi fusionner références régionales et terrain ?",
      fusionBody:
        "Les grilles climatiques régionales ignorent votre forage ou goutte-à-goutte. L'association avec vos saisies locales garantit une recommandation réaliste.",
      qualityTitle: "Registre de qualité et d'incertitude",
      missingDataTitle: "Mesures manquantes",
      fixInProfileBtn: "Compléter dans le profil",
      spatialTitle: "Référence spatiale (contexte visuel)",
      spatialNote:
        "L'imagerie satellite sert uniquement d'orientation visuelle ; le calcul lit Schema: dataset.",
      directBadge: "Observation directe",
      derivedBadge: "Signal dérivé du jeu",
      loadingText: "Chargement du registre des preuves...",
      emptyTitle: "Aucune preuve d'analyse chargée",
      emptyBody:
        "Lancez ou ouvrez une analyse de parcelle pour consulter la traçabilité complète, les mesures satellite et la complétude des données.",
      tagFilterLabel: "Étiquette agronomique :",
      tagAll: "Toutes",
    },
    common: {
      backToCommandCenter: "Centre de commande",
      checkingDeps: "Vérification des dépendances",
      datasetLabel: "Jeu de données",
      engineLabel: "Moteur",
      completenessLabel: "Complétude",
      startingLabel: "Démarrage...",
      savingLabel: "Enregistrement...",
      runningLabel: "Exécution...",
      quartersShort: "trim.",
      daysPerYearShort: "j/an",
      removeBtn: "Supprimer",
      okShort: "OK",
      bareShort: "SOL NU",
      ariaLanguageSwitcher: "Sélecteur de langue",
      ariaMobileNav: "Navigation mobile",
      ariaToolRail: "Barre d'outils spatiale",
      ariaWorkflowNav: "Navigation du studio d'analyse",
      ariaCloseModal: "Fermer la fenêtre",
      radarAria: "Comparaison agronomique sur 7 axes",
      logoTagline: "Rotations agricoles de précision",
      notFoundTitle: "Page introuvable",
      notFoundDesc: "La page demandée n'existe pas dans cet espace.",
      notFoundBackBtn: "Retour au centre de commande",
    },
    usda: {
      closeAria: "Fermer le convertisseur USDA",
      adrRuleText:
        "Règle ADR-5 : les pourcentages Argile + Limon + Sable doivent totaliser 100 % et correspondent au type de sol USDA.",
      percentLabel: "Pourcentage (%)",
      clayLabel: "Argile",
      siltLabel: "Limon",
      sandLabel: "Sable",
      derivedSoilTypeLabel: "Type de sol déduit :",
    },
    brief: {
      docHeading: "FELLAH TECH — Fiche Rotation 1 Page",
      strategyPrefix: "Stratégie :",
      metaField: "Parcelle :",
      metaDataset: "Jeu de données :",
      metaEngine: "Moteur :",
      metaGenerated: "Généré le :",
      seasonSeqHeading: "Séquence des saisons",
      colNumber: "#",
      colSeasonYear: "Saison / Année",
      colCrop: "Culture",
      colCategoryRole: "Catégorie / Rôle",
      colIrrigation: "Irrigation",
      colReason: "Justification",
      risksHeading: "Principaux risques & mesures",
      severityPrefix: "Gravité :",
      mitigationPrefix: "Atténuation :",
      citationsHeading: "Références & preuves",
      colParameter: "Paramètre",
      colSource: "Source",
      colValue: "Valeur",
      colDatePeriod: "Date / Période",
      disclaimerPrefix: "Avertissement :",
    },
  },
  ar: {
    brandTitle: "FELLAH TECH",
    brandSubtitle: "الذكاء الزراعي ودعم اتخاذ القرار · ولاية قالمة",
    nav: {
      dashboard: "لوحة القيادة",
      selectField: "تحديد القطعة",
      farmProfile: "ملف المزرعة",
      comparison: "الدورة الزراعية",
      evidence: "الأدلة والشفافية",
    },
    chrome: {
      fixtureMode: "وضع المحاكاة",
      plainModeOn: "الوضع المبسط (Aa): مفعل",
      plainModeOff: "الوضع المبسط (Aa)",
      plainModeTooltip: "تحويل المصطلحات الزراعية إلى لغة فلاحية واضحة",
      guestWorkspace: "جلسة قالمة التجريبية",
      accountWorkspace: "حساب مزرعة مسجل",
      signIn: "دخول / حساب",
      launchDemo: "تشغيل تجربة قالمة",
      claimAccount: "حفظ بيانات الضيف",
      quartersLabel: "رصيد التحليلات للضيف",
      quartersRule: "تحليل كامل = 4 وحدات | تعديل مناخي = 1 وحدة",
      systemOk: "البيانات والمحرك جاهزان",
      systemDegraded: "وضع احتياطي قديم",
      activeParcel: "القطعة النشطة",
      noParcel: "لم تُختر قطعة",
    },
    auth: {
      welcomeTitle: "مساحة العمل الميدانية · ولاية قالمة",
      welcomeBody:
        "ابدأ جلسة تجريبية فورية لولاية قالمة مع القطعة F1 أو سجّل الدخول بحسابك الدائم.",
      launchDemoBtn: "تشغيل مساحة تجربة قالمة",
      signInTab: "تسجيل الدخول",
      registerTab: "إنشاء حساب مجاني",
      email: "البريد الإلكتروني",
      password: "كلمة المرور (8 أحرف على الأقل)",
      fullName: "الاسم الكامل",
      submitLogin: "دخول",
      submitRegister: "إنشاء الحساب",
      claimBannerTitle: "احتفظ بمزارعك وتحليلاتك التجريبية",
      claimBannerBody: "انقل بيانات جلسة الضيف الحالية إلى حسابك الدائم بأمان.",
      claimNowBtn: "استرداد جلسة الضيف",
      exportDataBtn: "تصدير البيانات JSON",
      endGuestBtn: "إعادة ضبط جلسة الضيف",
      deleteAccountBtn: "حذف الحساب نهائياً",
      deleteConfirmText: "هل تريد حذف الحساب وجميع المزارع نهائياً؟",
      logoutBtn: "تسجيل الخروج",
      signedInSuccess: "تم تسجيل الدخول بنجاح.",
      claimedGuestMsg: (count) => `تم ضم ${count} مزرعة تجريبية إلى حسابك.`,
      jsonDownloaded: "تم تنزيل ملف JSON بنجاح.",
      closeModalAria: "إغلاق نافذة الحساب",
    },
    dashboard: {
      heroEyebrow: "ولاية قالمة · مركز المتابعة",
      heroTitle: "مخطط الدورات الزراعية المتكيف مع المناخ",
      heroSubtitle:
        "دمج معطيات التربة والري من الفلاح مع المراجع المناخية المحلية الموثقة (Schema: dataset) لتخطيط المواسم القادمة.",
      ctaSelectField: "تحديد أو رسم القطعة",
      ctaRunAnalysis: "إعداد وتشغيل التحليل",
      kpiParcels: "القطع النشطة",
      kpiQuota: "رصيد التحليل",
      kpiAdopted: "الخطة المعتمدة",
      kpiReadiness: "جاهزية البيانات والمحرك",
      noStrategyYet: "لم يتم اختيار خطة بعد",
      riskSummaryTitle: "ملخص مخاطر القطعة والمناخ",
      historyTitle: "سجل التحليلات السابقة",
      openComparison: "فتح المقارنة",
      simulateDegradedLabel: "معاينة شريط البيانات الاحتياطية القديمة (ADR-8)",
    },
    selectField: {
      title: "تحديد القطعة · خريطة قالمة المدارية",
      subtitle:
        "استعرض حدود ولاية قالمة، ارسم حدود أرضك على القمر الصناعي، أو حمّل إحدى القطع الست التجريبية.",
      instantJump: "انتقال فوري",
      drawModeOn: "الرسم مفعل (انقر على الخريطة)",
      drawModeOff: "رسم مضلع القطعة",
      clearPolygon: "مسح الرسم",
      insideGuelma: "داخل حدود ولاية قالمة",
      outsideGuelma: "خارج حدود قالمة",
      presetsTitle: "6 أشكال معتمدة للاختبار في قالمة",
      outsideTestBtn: "اختبار خارج الحدود · سطيف (36.19°N, 5.41°E)",
      farmLabel: "المزرعة النشطة",
      createFarmBtn: "إنشاء مزرعة",
      newFarmName: "اسم المزرعة الجديدة",
      fieldIdLabel: "معرف القطعة",
      fieldNameLabel: "اسم القطعة",
      areaLabel: "المساحة (هكتار)",
      elevationLabel: "الارتفاع (متر، اختياري)",
      elevationUnknownHint: "اتركه فارغاً إذا كان مجهولاً (لا يُملأ تلقائياً)",
      saveContinueBtn: "حفظ القطعة والمتابعة لملف المزرعة",
      mapAttribution:
        "خريطة أقمار صناعية للعرض البصري · التقييم يعتمد حصرياً على Schema: dataset",
      verticesUnit: "نقاط",
      parcelsPanelTitle: "قطع المزرعة",
      newParcelBadge: "قطعة جديدة",
      latLabel: "خط العرض",
      lngLabel: "خط الطول",
      nullPlaceholder: "غير محدد",
      savingBtn: "جارٍ الحفظ...",
    },
    farmProfile: {
      title: "ملف المزرعة وأولويات الدورة الزراعية",
      subtitle:
        "أدخل سجل المحاصيل، مصدر بيانات التربة، نظام السقي، والأوزان الخمسة بمجموع يساوي 100.",
      secCropHistory: "1. سجل المحاصيل السابقة (1–30 موسماً)",
      secSoil: "2. مصدر بيانات التربة (ADR-5)",
      secWater: "3. الماء ونظام السقي",
      secPlanning: "4. نافذة التخطيط والسيناريو المناخي",
      secPriorities: "5. أولويات الفلاح (المجموع = 100) والمحاصيل",
      addHistoryRow: "إضافة موسم سابق",
      otherLocalCrop: "اسم محصول محلي آخر",
      soilUnknownTitle: "غير معروف / لا يوجد تحليل تربة بعد",
      soilUnknownDesc: "يسجل soil_source: unknown بشفافية دون تخمين خصائص التربة.",
      soilKnownTitle: "أعرف نوع التربة / لدي نتائج مخبرية",
      soilKnownDesc: "أدخل القوام والقياسات الاختيارية للحموضة والمادة العضوية.",
      usdaHelperBtn: "حاسبة قوام التربة USDA",
      usdaTitle: "تحويل نسب الرمل والطمي والطين إلى SoilType",
      usdaApply: "تطبيق نوع التربة المحسوب",
      waterAvailability: "توفر المياه",
      waterSource: "مصدر المياه الرئيسي",
      waterSourceOther: "وصف مصدر المياه الآخر",
      irrigationSystem: "نظام السقي",
      startSeason: "موسم البداية",
      startYear: "سنة البداية",
      plantingMonth: "شهر الزراعة (التحقق الفصلي)",
      horizonSeasons: "عدد المواسم (1–6)",
      cycleMode: "نمط الدورة",
      whatIfTitle: "اختبار تغير المناخ (ماذا لو؟)",
      tempDelta: "تغير الحرارة (°C)",
      precipDelta: "تغير الأمطار (%)",
      weightsSum: "مجموع الأوزان",
      autoBalanceBtn: "موازنة تلقائية إلى 100",
      marketPreference: "توجه التسويق",
      targetCrops: "محاصيل مطلوبة",
      excludedCrops: "محاصيل مستبعدة",
      equipmentConstraints: "قيود المعدات",
      submitBtn: "حفظ الملف وتشغيل التحليل",
      pollingTitle: "جارٍ حساب أفضل الدورات الزراعية",
      cancelJobBtn: "إلغاء الطلب",
      seasonLabel: "الموسم",
      yearLabel: "السنة",
      cropLabel: "المحصول",
      selectCropPlaceholder: "اختر محصولاً",
      customCropExample: "مثال: قمح صلب محلي",
      seasonCheckOk: "تطابق الموسم لنصف الكرة الشمالي سليم",
      soilTextureLabel: "قوام التربة",
      soilPhLabel: "حموضة التربة (3.0–11.0)",
      organicMatterLabel: "نسبة المادة العضوية %",
      labTestDateLabel: "تاريخ التحليل المخبري",
      annualRotationLabel: "تناوب سنوي",
      consecutiveSeasonsLabel: "مواسم متتالية",
      presetBalanced: "توازن التربة",
      presetYield: "الدخل والمردود",
      presetDrought: "مقاومة الجفاف",
      presetLowRisk: "أقل مخاطرة",
      readyToAnalyze: "جاهز لتحليل القطعة",
      fixValidationGuards: "يرجى تصحيح تنبيهات التحقق قبل التشغيل.",
      statusPrefix: "الحالة:",
      soilBadgeUnknown: "المصدر: غير محدد",
      soilBadgeFarmer: "المصدر: الفلاح",
    },
    comparison: {
      title: "مقارنة استراتيجيات الدورة الزراعية",
      subtitle:
        "قارن الاستمرار بالزراعة الحالية مع البدائل متعددة المواسم المعتمدة على المخرجات الرسمية.",
      degradedBannerTitle: "وضع احتياطي · نتائج مخزنة قديمة (ADR-8)",
      degradedAge: "عمر النسخة الاحتياطية",
      recommendedBadge: "الأكثر ملاءمة",
      baselineBadge: "النمط الحالي",
      selectedBadge: "الخطة المعتمدة",
      rejectedBadge: "مرفوضة",
      selectStrategyBtn: "اعتماد هذه الخطة",
      rejectStrategyBtn: "رفض",
      bareDaysLabel: "أيام التربة المكشوفة (يوم/سنة)",
      bareDaysPlain: "عدد الأيام التي تبقى فيها الأرض عارية دون غطاء نباتي",
      riskCalendarTitle: "التقويم السنوي للمخاطر الزراعية (12 شهراً)",
      bareWindowTitle: "فترات بقاء التربة مكشوفة",
      bareWindowPlain: "أشهر تجف فيها التربة المكشوفة بسبب الحر والرياح",
      stressWindowTitle: "فترات الإجهاد المناخي",
      requestedCropsTitle: "نتائج المحاصيل المطلوبة",
      benefitsTitle: "الفوائد الزراعية",
      risksTitle: "المخاطر وسبل الوقاية",
      gapsTitle: "الافتراضات والفجوات والمراجعة المحلية",
      whatIfTitle: "مقارنة مناخية سريعة",
      whatIfRunBtn: "تشغيل السيناريو (1 وحدة)",
      printBriefBtn: "طباعة ملخص من صفحة واحدة",
      loadingText: "جارٍ تحميل مقارنة الدورات الزراعية...",
      emptyTitle: "لم يتم اختيار تحليل تناوب زراعي بعد",
      emptyBody:
        "اضبط سجل المحاصيل والتربة والمياه والأولويات في ملف المزرعة لحساب استراتيجيات التناوب المصنفة.",
      openProfileBtn: "فتح ملف المزرعة",
      partialFieldBanner: "نتيجة جزئية للقطعة:",
      radarHeading: "التوازن الزراعي متعدد المحاور",
      replacedByLabel: "تم استبداله بـ:",
      inspectDetailsBtn: "عرض الفوائد والمخاطر والفجوات",
      hideDetailsBtn: "إخفاء التفصيل الزراعي",
      mitigationLabel: "التخفيف:",
      whatIfHint: "اختبر مواسم أكثر حرارة أو جفافاً على خصائص هذه القطعة.",
      runningBtn: "جارٍ التشغيل...",
      tempShiftLabel: "تغير درجة الحرارة",
      precipChangeLabel: "تغير الهطول المطري",
      noBareGaps: "لا توجد فترات تعرٍ للتربة مسجلة.",
      noStressWindows: "لم يتم رصد نوافذ إجهاد رئيسية.",
      seasonsUnitAria: "مواسم",
      tableSource: "المصدر",
      tableValue: "القيمة",
      tablePeriod: "المصدر / الفترة",
      tableInterpretation: "التفسير",
    },
    evidence: {
      title: "الأدلة البيئية وشفافية البيانات",
      subtitle:
        "تحقق من كل معطى أدخله الفلاح أو استُخرج من قاعدة البيانات المحلية مع عرض الفجوات بصدق.",
      filterAll: "كل المصادر",
      filterFarmer: "مدخلات الفلاح",
      filterDataset: "قاعدة البيانات المحلية",
      fusionTitle: "لماذا ندمج بيانات الأقمار الصناعية مع معطيات الفلاح؟",
      fusionBody:
        "خرائط المناخ الإقليمية لا ترى البئر الخاص بك أو شبكة التقطير أو محصول الخريف الماضي؛ دمج المعطيات يمنع الأخطاء.",
      qualityTitle: "مؤشر جودة واكتمال البيانات",
      missingDataTitle: "بيانات ناقصة تؤثر على الدقة",
      fixInProfileBtn: "إكمال القياسات في ملف المزرعة",
      spatialTitle: "المرجع المكاني (للعرض البصري فقط)",
      spatialNote:
        "صور الأقمار الصناعية للتوضيح البصري، بينما يعتمد التحليل على dataset_version المثبت.",
      directBadge: "ملاحظة مباشرة",
      derivedBadge: "مؤشر مشتق من قاعدة البيانات",
      loadingText: "جارٍ تحميل سجل الأدلة...",
      emptyTitle: "لم يتم تحميل أدلة تحليل بعد",
      emptyBody:
        "شغّل أو افتح تحليل قطعة أولاً للاطلاع على مصدر البيانات والقياسات الفضائية واكتمال المعلومات.",
      tagFilterLabel: "الوسم الزراعي:",
      tagAll: "الكل",
    },
    common: {
      backToCommandCenter: "مركز التحكم",
      checkingDeps: "جارٍ فحص التبعيات",
      datasetLabel: "مجموعة البيانات",
      engineLabel: "المحرك",
      completenessLabel: "اكتمال البيانات",
      startingLabel: "جارٍ البدء...",
      savingLabel: "جارٍ الحفظ...",
      runningLabel: "جارٍ التشغيل...",
      quartersShort: "فصول",
      daysPerYearShort: "يوم/سنة",
      removeBtn: "إزالة",
      okShort: "مستقر",
      bareShort: "عارية",
      ariaLanguageSwitcher: "مبدّل اللغة",
      ariaMobileNav: "التنقل عبر الهاتف",
      ariaToolRail: "شريط أدوات الخريطة",
      ariaWorkflowNav: "تنقل استوديو التحليل",
      ariaCloseModal: "إغلاق النافذة",
      radarAria: "مقارنة التقييم الزراعي متعدد المحاور",
      logoTagline: "تناوب المحاصيل الدقيق",
      notFoundTitle: "الصفحة غير موجودة",
      notFoundDesc: "المسار المطلوب غير موجود في مساحة العمل.",
      notFoundBackBtn: "العودة إلى مركز التحكم",
    },
    usda: {
      closeAria: "إغلاق حاسبة قوام التربة USDA",
      adrRuleText:
        "قاعدة ADR-5 الدقيقة: يجب أن يكون مجموع نسب الطين والطمي والرمل 100% للتحويل الدقيق إلى قوام التربة USDA.",
      percentLabel: "النسبة المئوية (%)",
      clayLabel: "طين",
      siltLabel: "طمي",
      sandLabel: "رمل",
      derivedSoilTypeLabel: "قوام التربة المستنتج:",
    },
    brief: {
      docHeading: "FELLAH TECH — ملخص التناوب الزراعي من صفحة واحدة",
      strategyPrefix: "الاستراتيجية:",
      metaField: "القطعة:",
      metaDataset: "قاعدة البيانات:",
      metaEngine: "المحرك:",
      metaGenerated: "تاريخ الإنشاء:",
      seasonSeqHeading: "تسلسل المواسم",
      colNumber: "#",
      colSeasonYear: "الموسم / السنة",
      colCrop: "المحصول",
      colCategoryRole: "الفئة / الدور",
      colIrrigation: "السقي",
      colReason: "السبب العلمي",
      risksHeading: "أبرز المخاطر وإجراءات التخفيف",
      severityPrefix: "الشدة:",
      mitigationPrefix: "التخفيف:",
      citationsHeading: "مراجع الأدلة العلمية",
      colParameter: "المتغير",
      colSource: "المصدر",
      colValue: "القيمة",
      colDatePeriod: "التاريخ / الفترة",
      disclaimerPrefix: "تنويه:",
    },
  },
};

export const MONTH_SHORT: Record<Language, string[]> = {
  en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  fr: ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun", "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"],
  ar: ["جانفي", "فيفري", "مارس", "أفريل", "ماي", "جوان", "جويلية", "أوت", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"],
};

export const SEASON_LABELS: Record<Language, Record<Season, string>> = {
  en: { spring: "Spring", summer: "Summer", autumn: "Autumn", winter: "Winter" },
  fr: { spring: "Printemps", summer: "Été", autumn: "Automne", winter: "Hiver" },
  ar: { spring: "الربيع", summer: "الصيف", autumn: "الخريف", winter: "الشتاء" },
};

export const SOIL_TYPE_LABELS: Record<Language, Record<SoilType, string>> = {
  en: { sandy: "Sandy", clay: "Clay", loamy: "Loamy", silty: "Silty", unknown: "Unknown" },
  fr: { sandy: "Sableux", clay: "Argileux", loamy: "Limono-argileux (Loam)", silty: "Limoneux", unknown: "Inconnu" },
  ar: { sandy: "رملية", clay: "طينية", loamy: "مزيجية متوازنة", silty: "طميية", unknown: "غير معروفة" },
};

export const WATER_AVAILABILITY_LABELS: Record<Language, Record<WaterAvailability, string>> = {
  en: {
    abundant: "Abundant",
    moderate: "Moderate",
    limited: "Limited",
    very_limited: "Very Limited",
    rainfed_only: "Rainfed Only",
  },
  fr: {
    abundant: "Abondante",
    moderate: "Modérée",
    limited: "Limitée",
    very_limited: "Très limitée",
    rainfed_only: "Pluviale uniquement",
  },
  ar: {
    abundant: "وفيرة",
    moderate: "متوسطة",
    limited: "محدودة",
    very_limited: "محدودة جداً",
    rainfed_only: "بعلية (تعتمد على المطر)",
  },
};

export const WATER_SOURCE_LABELS: Record<Language, Record<WaterSource, string>> = {
  en: {
    rainwater: "Rainwater",
    groundwater: "Groundwater",
    well: "Well / Borehole",
    dam_reservoir: "Dam / Reservoir",
    irrigation_network: "Public Irrigation Network",
    other: "Other",
    unknown: "Unknown",
  },
  fr: {
    rainwater: "Eau de pluie",
    groundwater: "Nappe phréatique",
    well: "Puits / Forage",
    dam_reservoir: "Barrage / Retenue",
    irrigation_network: "Réseau d'irrigation",
    other: "Autre",
    unknown: "Inconnu",
  },
  ar: {
    rainwater: "مياه الأمطار",
    groundwater: "مياه جوفية",
    well: "بئر / ثقب مائي",
    dam_reservoir: "سد / حاجز مائي",
    irrigation_network: "شبكة سقي عمومية",
    other: "مصدر آخر",
    unknown: "غير معروف",
  },
};

export const IRRIGATION_SYSTEM_LABELS: Record<Language, Record<IrrigationSystem, string>> = {
  en: {
    rainfed: "Rainfed",
    drip: "Drip Irrigation",
    sprinkler: "Sprinkler",
    flood: "Surface / Flood",
    other: "Other",
    unknown: "Unknown",
  },
  fr: {
    rainfed: "Pluvial",
    drip: "Goutte-à-goutte",
    sprinkler: "Aspersion",
    flood: "Gravitaire / Submersion",
    other: "Autre",
    unknown: "Inconnu",
  },
  ar: {
    rainfed: "سقي مطري",
    drip: "التقطير",
    sprinkler: "الرش المحوري",
    flood: "السقي بالغمر",
    other: "نظام آخر",
    unknown: "غير معروف",
  },
};

export const MARKET_PREFERENCE_LABELS: Record<Language, Record<MarketPreference, string>> = {
  en: {
    local_market: "Local Market",
    export: "Export",
    subsistence: "On-Farm Subsistence",
    mixed: "Mixed Market & Forage",
  },
  fr: {
    local_market: "Marché local",
    export: "Export",
    subsistence: "Autoconsommation",
    mixed: "Mixte (Vente & Fourrage)",
  },
  ar: {
    local_market: "السوق المحلي",
    export: "التصدير",
    subsistence: "الاستهلاك العائلي",
    mixed: "مختلط (تسويق وعلف)",
  },
};

export const CROP_CATEGORY_LABELS: Record<Language, Record<CropCategory, string>> = {
  en: {
    cereals: "Cereals",
    legumes: "Legumes",
    oilseeds: "Oilseeds",
    vegetables: "Vegetables",
    forage: "Forage",
    cover_crops: "Cover Crops",
    fallow: "Fallow",
  },
  fr: {
    cereals: "Céréales",
    legumes: "Légumineuses",
    oilseeds: "Oléagineux",
    vegetables: "Maraîchage",
    forage: "Fourrages",
    cover_crops: "Couvert végétal",
    fallow: "Jachère",
  },
  ar: {
    cereals: "حبوب",
    legumes: "بقوليات",
    oilseeds: "محاصيل زيتية",
    vegetables: "خضروات",
    forage: "أعلاف",
    cover_crops: "محاصيل تغطية",
    fallow: "أرض بور",
  },
};

export const CROP_ROLE_LABELS: Record<Language, Record<CropRole, string>> = {
  en: {
    cash_crop: "Cash Crop",
    nitrogen_fixer: "Nitrogen Fixer",
    forage: "Forage",
    cover_crop: "Cover Crop",
    break_crop: "Break Crop",
    main_crop: "Main Crop",
    fallow: "Fallow",
  },
  fr: {
    cash_crop: "Culture de rente",
    nitrogen_fixer: "Fixateur d'azote",
    forage: "Fourrage",
    cover_crop: "Couvert",
    break_crop: "Culture de rupture",
    main_crop: "Culture principale",
    fallow: "Jachère",
  },
  ar: {
    cash_crop: "محصول نقدي",
    nitrogen_fixer: "مثبت للآزوت",
    forage: "علف",
    cover_crop: "غطاء نباتي",
    break_crop: "كاسر للأمراض",
    main_crop: "محصول رئيسي",
    fallow: "بور",
  },
};

export const STRESS_LABELS: Record<Language, Record<StressType, string>> = {
  en: {
    drought: "Drought Deficit",
    heat: "Heat Stress",
    frost: "Frost Risk",
    waterlogging: "Waterlogging",
    salinity: "Salinity",
    nutrient: "Nutrient Depletion",
  },
  fr: {
    drought: "Déficit hydrique",
    heat: "Stress thermique",
    frost: "Risque de gel",
    waterlogging: "Engorgement",
    salinity: "Salinité",
    nutrient: "Épuisement nutritif",
  },
  ar: {
    drought: "عجز مائي (جفاف)",
    heat: "إجهاد حراري",
    frost: "خطر الصقيع",
    waterlogging: "تغدق المياه",
    salinity: "ملوحة",
    nutrient: "فقر العناصر",
  },
};

export const SCORE_LABELS: Record<
  Language,
  Record<
    | "water_efficiency"
    | "erosion_protection"
    | "organic_matter_gain"
    | "nitrogen_contribution"
    | "pest_cycle_disruption"
    | "income_forage_value"
    | "priority_fit",
    { tech: string; plain: string }
  >
> = {
  en: {
    water_efficiency: { tech: "Water Efficiency", plain: "Saves Irrigation & Rain" },
    erosion_protection: { tech: "Erosion Protection", plain: "Stops Topsoil Wash-Off" },
    organic_matter_gain: { tech: "Organic Matter Gain", plain: "Builds Rich Dark Humus" },
    nitrogen_contribution: { tech: "Nitrogen Contribution", plain: "Feeds Natural Nitrogen" },
    pest_cycle_disruption: { tech: "Pest Cycle Disruption", plain: "Breaks Wheat Root Disease" },
    income_forage_value: { tech: "Income & Forage Value", plain: "Harvest Cash & Animal Feed" },
    priority_fit: { tech: "Priority Fit", plain: "Matches Your Farm Goals" },
  },
  fr: {
    water_efficiency: { tech: "Efficience hydrique", plain: "Économise l'eau du champ" },
    erosion_protection: { tech: "Protection érosion", plain: "Protège la terre fertile" },
    organic_matter_gain: { tech: "Gain matière organique", plain: "Enrichit la terre vivante" },
    nitrogen_contribution: { tech: "Apport d'azote", plain: "Nourrit le sol naturellement" },
    pest_cycle_disruption: { tech: "Rupture bioagresseurs", plain: "Coupe les maladies des céréales" },
    income_forage_value: { tech: "Revenu & fourrage", plain: "Revenu vente et alimentation" },
    priority_fit: { tech: "Adéquation priorités", plain: "Correspond à vos objectifs" },
  },
  ar: {
    water_efficiency: { tech: "كفاءة استهلاك الماء", plain: "يوفر مياه السقي والمطر" },
    erosion_protection: { tech: "الحماية من الانجراف", plain: "يحمي التربة السطحية" },
    organic_matter_gain: { tech: "زيادة المادة العضوية", plain: "يغذي خصوبة الأرض" },
    nitrogen_contribution: { tech: "تثبيت الآزوت", plain: "يضيف سماداً طبيعياً مجانياً" },
    pest_cycle_disruption: { tech: "كسر دورة الآفات", plain: "يمنع أمراض تكرار الحبوب" },
    income_forage_value: { tech: "العائد والأعلاف", plain: "دخل البيع وعلف المواشي" },
    priority_fit: { tech: "توافق الأولويات", plain: "يطابق اختيارات مزرعتك" },
  },
};

export const EVIDENCE_PARAM_LABELS: Record<
  Language,
  Record<EvidenceParameter, { tech: string; plain: string }>
> = {
  en: {
    precipitation: { tech: "Precipitation", plain: "Yearly / Seasonal Rainfall" },
    t2m: { tech: "2m Air Temperature", plain: "Average Field Air Temp" },
    t2m_max: { tech: "Max Air Temperature", plain: "Peak Daytime Heat" },
    t2m_min: { tech: "Min Air Temperature", plain: "Nighttime Cold" },
    rh2m: { tech: "Relative Humidity", plain: "Air Moisture" },
    wind_2m: { tech: "2m Wind Speed", plain: "Drying Surface Wind" },
    solar_radiation: { tech: "Solar Radiation", plain: "Sun Energy" },
    ndvi: { tech: "NDVI Vegetation Index", plain: "Satellite Crop Greenness" },
    soil_moisture_surface: { tech: "Surface Soil Moisture", plain: "Topsoil Dampness" },
    precipitation_anomaly: { tech: "Precipitation Anomaly", plain: "Rain vs Normal Years" },
    evaporative_stress_index: { tech: "Evaporative Stress Index", plain: "Sun Drying Bare Soil" },
    groundwater_anomaly: { tech: "Groundwater Anomaly", plain: "Underground Water Trend" },
    crop_history: { tech: "Crop History", plain: "What Grew Here Before" },
    soil_type: { tech: "Soil Texture", plain: "Soil Feel & Texture" },
    soil_ph: { tech: "Soil pH", plain: "Soil Acidity / Alkalinity" },
    organic_matter_percent: { tech: "Organic Matter %", plain: "Natural Humus Level" },
    elevation_m: { tech: "Elevation", plain: "Height Above Sea Level" },
    water_availability: { tech: "Water Availability", plain: "Water Supply for Irrigation" },
    dataset_feature: { tech: "Dataset Zone Feature", plain: "Local Reference Reading" },
  },
  fr: {
    precipitation: { tech: "Précipitations", plain: "Pluie annuelle / saisonnière" },
    t2m: { tech: "Température à 2m", plain: "Température moyenne de l'air" },
    t2m_max: { tech: "Température max", plain: "Pic de chaleur diurne" },
    t2m_min: { tech: "Température min", plain: "Fraîcheur nocturne" },
    rh2m: { tech: "Humidité relative", plain: "Humidité de l'air" },
    wind_2m: { tech: "Vent à 2m", plain: "Vent desséchant" },
    solar_radiation: { tech: "Rayonnement solaire", plain: "Énergie du soleil" },
    ndvi: { tech: "Indice NDVI", plain: "Verdure satellite des cultures" },
    soil_moisture_surface: { tech: "Humidité de surface", plain: "Humidité du sol superficiel" },
    precipitation_anomaly: { tech: "Anomalie pluviométrique", plain: "Pluie vs moyenne habituelle" },
    evaporative_stress_index: { tech: "Indice de stress évaporatif", plain: "Assèchement par le soleil" },
    groundwater_anomaly: { tech: "Anomalie nappe souterraine", plain: "Tendance de l'eau souterraine" },
    crop_history: { tech: "Historique cultural", plain: "Cultures précédentes" },
    soil_type: { tech: "Texture du sol", plain: "Nature du sol" },
    soil_ph: { tech: "pH du sol", plain: "Acidité / alcalinité" },
    organic_matter_percent: { tech: "Matière organique %", plain: "Richesse en humus" },
    elevation_m: { tech: "Altitude", plain: "Hauteur du terrain" },
    water_availability: { tech: "Disponibilité en eau", plain: "Capacité d'arrosage" },
    dataset_feature: { tech: "Variable du jeu local", plain: "Référence régionale" },
  },
  ar: {
    precipitation: { tech: "الهطول المطري", plain: "معدل الأمطار" },
    t2m: { tech: "حرارة الهواء", plain: "متوسط حرارة الحقل" },
    t2m_max: { tech: "الحرارة القصوى", plain: "ذروة حر النهار" },
    t2m_min: { tech: "الحرارة الدنيا", plain: "برودة الليل" },
    rh2m: { tech: "الرطوبة النسبية", plain: "رطوبة الجو" },
    wind_2m: { tech: "سرعة الرياح", plain: "رياح التجفيف" },
    solar_radiation: { tech: "الإشعاع الشمسي", plain: "طاقة الشمس" },
    ndvi: { tech: "مؤشر الغطاء النباتي NDVI", plain: "اخضرار المحصول فضائياً" },
    soil_moisture_surface: { tech: "رطوبة التربة السطحية", plain: "ندى السطح" },
    precipitation_anomaly: { tech: "انحراف الأمطار", plain: "المطر مقارنة بالسنوات العادية" },
    evaporative_stress_index: { tech: "مؤشر الإجهاد التبخري", plain: "تجفيف الشمس للتربة المكشوفة" },
    groundwater_anomaly: { tech: "تغير المياه الجوفية", plain: "مستوى الماء الباطني" },
    crop_history: { tech: "سجل المحاصيل", plain: "ماذا زُرع سابقاً" },
    soil_type: { tech: "قوام التربة", plain: "طبيعة التربة" },
    soil_ph: { tech: "حموضة التربة pH", plain: "درجة الحموضة أو القلوية" },
    organic_matter_percent: { tech: "نسبة المادة العضوية", plain: "غنى التربة بالدبال" },
    elevation_m: { tech: "الارتفاع", plain: "العلو عن سطح البحر" },
    water_availability: { tech: "توفر المياه", plain: "الماء المتاح للسقي" },
    dataset_feature: { tech: "خاصية بيانات المنطقة", plain: "قراءة مرجعية محلية" },
  },
};

export function localizePlainText(
  text: string,
  lang: Language,
  plainMode: boolean
): string {
  return localizeAnalysisText(text, lang, plainMode);
}

export const RISK_SEVERITY_LABELS: Record<Language, Record<"low" | "medium" | "high", string>> = {
  en: { low: "Low", medium: "Medium", high: "High" },
  fr: { low: "Faible", medium: "Modérée", high: "Élevée" },
  ar: { low: "منخفضة", medium: "متوسطة", high: "مرتفعة" },
};

export const EQUIPMENT_LABELS: Record<Language, Record<string, string>> = {
  en: {
    tractor: "Tractor",
    standard_tractor: "Standard Tractor",
    seed_drill: "Seed Drill",
    planter: "Planter",
    sprayer: "Sprayer",
    harvester: "Harvester",
    combine_harvester: "Combine Harvester",
    hay_baler: "Hay Baler",
    subsoiler: "Subsoiler",
    no_subsoiler: "No Subsoiler",
  },
  fr: {
    tractor: "Tracteur",
    standard_tractor: "Tracteur standard",
    seed_drill: "Semoir en ligne",
    planter: "Planteuse",
    sprayer: "Pulvérisateur",
    harvester: "Moissonneuse",
    combine_harvester: "Moissonneuse-batteuse",
    hay_baler: "Botteleuse à fourrage",
    subsoiler: "Décompacteur",
    no_subsoiler: "Sans sous-soleuse",
  },
  ar: {
    tractor: "جرار",
    standard_tractor: "جرار فلاحى عادي",
    seed_drill: "بذارة",
    planter: "غراسة",
    sprayer: "رشاشة",
    harvester: "حصادة",
    combine_harvester: "حصادة دارسة",
    hay_baler: "مكبس أعلاف وتبن",
    subsoiler: "محراث تحت التربة",
    no_subsoiler: "بدون محراث عميق",
  },
};

export function formatEquipmentLabel(eq: string, lang: Language): string {
  return EQUIPMENT_LABELS[lang]?.[eq] || EQUIPMENT_LABELS.en[eq] || eq.replace(/_/g, " ");
}

export const WEIGHT_PRESET_LABELS: Record<
  Language,
  Record<"water_resilient" | "soil_restorer" | "cash_market" | "balanced_livestock", string>
> = {
  en: {
    water_resilient: "Water Resilient",
    soil_restorer: "Soil Restorer",
    cash_market: "Cash Market",
    balanced_livestock: "Balanced Livestock",
  },
  fr: {
    water_resilient: "Résilience Hydrique",
    soil_restorer: "Régénération du Sol",
    cash_market: "Rentabilité & Marché",
    balanced_livestock: "Équilibre & Fourrage",
  },
  ar: {
    water_resilient: "مقاومة الجفاف والمياه",
    soil_restorer: "تجديد خصوبة التربة",
    cash_market: "العائد والتسويق",
    balanced_livestock: "توازن المزرعة والأعلاف",
  },
};

export const PRIORITY_WEIGHT_LABELS: Record<
  Language,
  Record<"water_saving" | "soil_improvement" | "income" | "risk_reduction" | "forage_value", string>
> = {
  en: {
    water_saving: "Water Saving",
    soil_improvement: "Soil Improvement",
    income: "Farm Income",
    risk_reduction: "Risk Reduction",
    forage_value: "Forage Value",
  },
  fr: {
    water_saving: "Économie d'eau",
    soil_improvement: "Amélioration du sol",
    income: "Revenu agricole",
    risk_reduction: "Réduction des risques",
    forage_value: "Valeur fourragère",
  },
  ar: {
    water_saving: "توفير المياه",
    soil_improvement: "تحسين التربة",
    income: "الدخل الفلاحي",
    risk_reduction: "تقليل المخاطر",
    forage_value: "قيمة الأعلاف",
  },
};

export const ANALYSIS_JOB_STATUS_LABELS: Record<Language, Record<string, string>> = {
  en: {
    queued: "Queued",
    pending: "Pending",
    running: "Running",
    processing: "Processing",
    ok: "Completed",
    partial: "Partial Result",
    failed: "Failed",
    cancelled: "Cancelled",
  },
  fr: {
    queued: "En file",
    pending: "En attente",
    running: "En cours",
    processing: "Traitement",
    ok: "Terminé",
    partial: "Résultat partiel",
    failed: "Échec",
    cancelled: "Annulé",
  },
  ar: {
    queued: "في الانتظار",
    pending: "قيد الانتظار",
    running: "قيد التشغيل",
    processing: "جاري المعالجة",
    ok: "مكتمل",
    partial: "نتيجة جزئية",
    failed: "فشل",
    cancelled: "ملغى",
  },
};

export const REQUESTED_OUTCOME_LABELS: Record<Language, Record<string, string>> = {
  en: {
    included: "Included",
    excluded: "Excluded",
    replaced: "Replaced",
  },
  fr: {
    included: "Inclus",
    excluded: "Exclu",
    replaced: "Remplacé",
  },
  ar: {
    included: "مشمول",
    excluded: "مستبعد",
    replaced: "مُستبدل",
  },
};

export const DATA_SOURCE_LABELS: Record<Language, Record<string, string>> = {
  en: {
    farmer_input: "Farmer Input",
    dataset: "Regional Dataset / EO",
    model_derived: "Model Derived",
  },
  fr: {
    farmer_input: "Saisie agriculteur",
    dataset: "Jeu régional / Satellite",
    model_derived: "Calculé par modèle",
  },
  ar: {
    farmer_input: "معطيات الفلاح",
    dataset: "قاعدة بيانات المنطقة",
    model_derived: "مشتق من النموذج",
  },
};

export const EVIDENCE_GROUP_LABELS: Record<
  Language,
  Record<"all" | "climate" | "water" | "vegetation" | "soil_history", string>
> = {
  en: {
    all: "All",
    climate: "Climate",
    water: "Water",
    vegetation: "Vegetation",
    soil_history: "Soil & History",
  },
  fr: {
    all: "Tout",
    climate: "Climat",
    water: "Eau",
    vegetation: "Végétation",
    soil_history: "Sol & Historique",
  },
  ar: {
    all: "الكل",
    climate: "المناخ",
    water: "المياه",
    vegetation: "الغطاء النباتي",
    soil_history: "التربة والسجل",
  },
};
