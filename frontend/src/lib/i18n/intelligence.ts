import type { CropCategory, Language, SelectionStatus, SeverityLevel } from "@/lib/schemas";

export interface WorkstationDictionary {
  nav: {
    overview: string;
    farmsFields: string;
    intelligence: string;
    settings: string;
  };
  breadcrumb: string;
  geoContextTag: string;
  kpiContext: {
    farmsNone: string;
    farmsActive: (n: number) => string;
    fieldsNone: string;
    fieldsActive: string;
    areaNone: string;
    areaMean: (avgHa: string) => string;
    communesCoverage: string;
  };
  mapHud: {
    viewportLabel: string;
    fitAllBtn: string;
    zoomIn: string;
    zoomOut: string;
    legendSelected: string;
    legendParcel: string;
    layersLabel: string;
    drawParcelLabel: string;
    prevFieldLabel: string;
    nextFieldLabel: string;
    communesChip: string;
    closeInspectorLabel: string;
    openInspectorLabel: string;
    readinessLabel: string;
  };
  telemetry: {
    microclimateTitle: string;
    tempLabel: string;
    precipLabel: string;
    windLabel: string;
    solarLabel: string;
    coverageTitle: string;
    soilMetricsTitle: string;
    moistureLabel: string;
    carbonLabel: string;
    waterBalLabel: string;
    activitiesTitle: string;
    readyStateActivity: string;
    readyStateTime: string;
    boundaryReadyTitle: string;
    boundaryReadyTime: string;
    mlReadyTitle: string;
    mlReadyTime: string;
  };
  analyticsZone: {
    title: string;
    healthyZones: string;
    zoneOptimal: string;
    zoneModerate: string;
    zoneStress: string;
    zoneBare: string;
    avgNdvi: string;
    vsLastScan: string;
    problemZones: string;
    priorityAction: string;
    emptyPriority: string;
    emptyStatus: string;
  };
  inspector: {
    headerTitle: string;
    noSelection: string;
    area: string;
    commune: string;
    coordinates: string;
    soil: string;
    water: string;
    elevation: string;
    latestCrop: string;
    aiStatus: string;
    analyzeBtn: string;
    openPlanBtn: string;
    sim3dBtn: string;
    editBordersBtn: string;
    editInfoBtn: string;
  };
  table: {
    colParcel: string;
    colSpecs: string;
    colHistory: string;
    colAnalysis: string;
    colActions: string;
    bordersShort: string;
    infoShort: string;
    removeShort: string;
    simShort: string;
  };
  settings: {
    title: string;
    subtitle: string;
    appearanceHeading: string;
    appearanceDesc: string;
    themeSystem: string;
    themeLight: string;
    themeDark: string;
    switchToLight: string;
    switchToDark: string;
    accountHeading: string;
    openAccountBtn: string;
    languageHeading: string;
    terminologyHeading: string;
    terminologyDesc: string;
    workspaceHeading: string;
    clearWorkspaceDesc: string;
    closeBtn: string;
  };
}

export interface IntelligenceDictionary {
  workstation: WorkstationDictionary;
  header: {
    guestDemoBtn: string;
    accountBtn: string;
    guestBadge: string;
    signedInBadge: string;
    aiReadyTag: string;
    runAiBtn: string;
  };
  fieldStatus: {
    aiAnalyzed: string;
    aiPartial: string;
    aiRunning: string;
    aiNotAnalyzed: string;
    viewAiBtn: string;
    runAiFieldBtn: string;
    soilVerified: string;
    soilUnknown: string;
    waterReady: string;
    elevationMissing: string;
  };
  section: {
    badge: string;
    title: string;
    subtitle: string;
    plainModeToggle: string;
    plainModeOn: string;
    plainModeOff: string;
    printBriefBtn: string;
    runNewBtn: string;
    previewDemoBtn: string;
    openComparisonPage: string;
    historyLabel: string;
    noSavedRuns: string;
  };
  states: {
    noFieldsTitle: string;
    noFieldsDesc: string;
    unanalyzedTitle: string;
    unanalyzedDesc: string;
    pendingTitle: string;
    pendingDesc: string;
    runningTitle: string;
    runningDesc: string;
    cancelBtn: string;
    cancelling: string;
    cancelledTitle: string;
    cancelledDesc: string;
    failedTitle: string;
    retryBtn: string;
    unlinkedFieldTitle: string;
    unlinkedFieldDesc: string;
    unlinkedFieldCta: string;
  };
  runner: {
    modalTitle: string;
    modalSubtitle: string;
    fieldsTitle: string;
    planningTitle: string;
    startSeason: string;
    startYear: string;
    horizonSeasons: string;
    cycleMode: string;
    cycleAnnual: string;
    cycleConsecutive: string;
    plantingMonth: string;
    plantingMonthAuto: string;
    prioritiesTitle: string;
    weightLabels: {
      water_saving: string;
      soil_improvement: string;
      income: string;
      risk_reduction: string;
      forage_value: string;
    };
    autoBalanceBtn: string;
    presetBalanced: string;
    presetWater: string;
    presetIncome: string;
    weightsSum: string;
    marketPreference: string;
    targetCrops: string;
    excludedCrops: string;
    whatIfTitle: string;
    whatIfDesc: string;
    tempDelta: string;
    precipDelta: string;
    submitBtn: string;
    submittingBtn: string;
    closeBtn: string;
    selectAtLeastOneField: string;
  };
  overview: {
    summaryHeading: string;
    disclaimerHeading: string;
    statusOk: string;
    statusPartial: string;
    freshBadge: string;
    staleBadge: string;
    analysisIdLabel: string;
    generatedAtLabel: string;
    datasetVersionLabel: string;
    engineVersionLabel: string;
    schemaVersionLabel: string;
    envelopeWarningsTitle: string;
    fieldSelectorHeading: string;
    partialBannerTitle: string;
  };
  insights: {
    heading: string;
    bareCalendarTitle: string;
    bareLegend: string;
    activeLegend: string;
    stressLegend: string;
    noBarePeriods: string;
    stressMatrixTitle: string;
    noStressPeriods: string;
    climateTrendTitle: string;
    evidenceLabel: string;
    monthsShortUnit: string;
    statusOkLabel: string;
  };
  strategies: {
    heading: string;
    subtitle: string;
    recommendedBadge: string;
    baselineBadge: string;
    statusBadge: Record<SelectionStatus, string>;
    selectBtn: string;
    selectedBtn: string;
    rejectBtn: string;
    rejectedBtn: string;
    savingBtn: string;
    toastSelected: (name: string) => string;
    toastRejected: (name: string) => string;
    toastError: string;
    priorityFitLabel: string;
    confidenceLabel: string;
    bareDaysLabel: string;
    bareDaysUnit: string;
    radarTitle: string;
    noStrategiesPartial: string;
    scoreSectionTitle: string;
  };
  timeline: {
    heading: string;
    emptyNotice: string;
    orderPrefix: string;
    plantingMonthLabel: string;
    monthNotSet: string;
    roleLabel: string;
    categoryLabel: string;
    statusLabel: string;
    notesLabel: string;
    noNotes: string;
    detailHint: string;
  };
  explanations: {
    heading: string;
    tabs: {
      reasons: string;
      evidence: string;
      benefits: string;
      risks: string;
      assumptions: string;
      gaps: string;
      review: string;
    };
    codeToggleShow: string;
    codeToggleHide: string;
    farmerInputBadge: string;
    datasetBadge: string;
    derivedBadge: string;
    directBadge: string;
    missionLabel: string;
    observedLabel: string;
    periodLabel: string;
    severityLabel: string;
    likelihoodLabel: string;
    mitigationLabel: string;
    emptyList: string;
  };
  requestedCrops: {
    heading: string;
    subtitle: string;
    emptyNotice: string;
    outcomes: {
      included: string;
      replaced: string;
      excluded: string;
    };
    replacedBy: string;
    includedIn: string;
    noStrategies: string;
    evidenceCount: (n: number) => string;
    comparisonCount: (n: number) => string;
  };
  quality: {
    heading: string;
    farmTitle: string;
    fieldTitle: string;
    completenessLabel: string;
    completenessUnavailable: string;
    completenessVsConfidenceNote: string;
    missingDataTitle: string;
    missingDataEmpty: string;
    modelWarningsTitle: string;
    modelWarningsEmpty: string;
    limitationsTitle: string;
    limitationsEmpty: string;
  };
  severity: Record<SeverityLevel, string>;
  categories: Record<CropCategory, string>;
}

export const INTELLIGENCE_I18N: Record<Language, IntelligenceDictionary> = {
  en: {
    workstation: {
      nav: {
        overview: "Overview",
        farmsFields: "Farms & Fields",
        intelligence: "Field Intelligence",
        settings: "Settings",
      },
      breadcrumb: "Guelma / Agricultural Operations",
      geoContextTag: "Guelma Edition",
      kpiContext: {
        farmsNone: "No operations registered",
        farmsActive: (n) => `${n} commune${n === 1 ? "" : "s"} active`,
        fieldsNone: "Awaiting polygon borders",
        fieldsActive: "Georeferenced parcels",
        areaNone: "Draw borders on map",
        areaMean: (avgHa) => `${avgHa} ha mean / parcel`,
        communesCoverage: "Wilaya 24 coverage",
      },
      mapHud: {
        viewportLabel: "Guelma satellite workspace",
        fitAllBtn: "Fit extent",
        zoomIn: "Zoom in",
        zoomOut: "Zoom out",
        legendSelected: "Selected",
        legendParcel: "Parcel",
        layersLabel: "Toggle satellite layer contrast",
        drawParcelLabel: "Draw parcel on map",
        prevFieldLabel: "Previous parcel",
        nextFieldLabel: "Next parcel",
        communesChip: "Guelma · 34 communes",
        closeInspectorLabel: "Close inspector",
        openInspectorLabel: "Open parcel inspector",
        readinessLabel: "Agronomic readiness",
      },
      telemetry: {
        microclimateTitle: "Wilaya 24 microclimate",
        tempLabel: "Temp",
        precipLabel: "Precip",
        windLabel: "Wind",
        solarLabel: "Solar UV",
        coverageTitle: "Wilaya 24 operations",
        soilMetricsTitle: "Soil & parcel telemetry",
        moistureLabel: "Root moisture",
        carbonLabel: "Vegetation / OM",
        waterBalLabel: "Water balance",
        activitiesTitle: "Field activity log",
        readyStateActivity: "Wilaya 24 boundaries indexed",
        readyStateTime: "34 communes",
        boundaryReadyTitle: "Satellite orthophoto active",
        boundaryReadyTime: "10m grid",
        mlReadyTitle: "Rotation optimizer standby",
        mlReadyTime: "Ready",
      },
      analyticsZone: {
        title: "Crop health & rotation zones",
        healthyZones: "healthy zones",
        zoneOptimal: "Optimal cover",
        zoneModerate: "Monitor moisture",
        zoneStress: "Abiotic caution",
        zoneBare: "Bare soil exposure",
        avgNdvi: "Avg NDVI",
        vsLastScan: "vs last scan",
        problemZones: "Risk windows",
        priorityAction: "Priority focus",
        emptyPriority: "Add parcel",
        emptyStatus: "Standby",
      },
      inspector: {
        headerTitle: "Field Inspector",
        noSelection: "Select a mapped parcel on the map or table to inspect agronomic parameters.",
        area: "Area",
        commune: "Commune",
        coordinates: "Coordinates",
        soil: "Soil Profile",
        water: "Water & Irrigation",
        elevation: "Elevation",
        latestCrop: "Latest Season",
        aiStatus: "Rotation Intelligence",
        analyzeBtn: "Run Analysis",
        openPlanBtn: "Open AI Plan",
        sim3dBtn: "3D Inspect",
        editBordersBtn: "Borders",
        editInfoBtn: "Edit Info",
      },
      table: {
        colParcel: "Parcel / Location",
        colSpecs: "Soil, Water & Elevation",
        colHistory: "Crop History",
        colAnalysis: "AI Status",
        colActions: "Operations",
        bordersShort: "Borders",
        infoShort: "Info",
        removeShort: "Remove",
        simShort: "Simulate",
      },
      settings: {
        title: "Workstation Settings",
        subtitle: "Manage session synchronization, language direction, appearance, terminology mode, and local state.",
        appearanceHeading: "Appearance & Theme",
        appearanceDesc: "Match your operating system preference or lock the workstation to Light or Dark mode.",
        themeSystem: "System",
        themeLight: "Light",
        themeDark: "Dark",
        switchToLight: "Switch to Light mode",
        switchToDark: "Switch to Dark mode",
        accountHeading: "Account & Cloud Sync",
        openAccountBtn: "Manage Session & Account",
        languageHeading: "Display Language & Direction",
        terminologyHeading: "Agronomic Terminology",
        terminologyDesc: "Switch between technical agronomic terminology and simplified farmer wording.",
        workspaceHeading: "Workspace Data",
        clearWorkspaceDesc: "Remove locally mapped demo parcels and reset workspace state.",
        closeBtn: "Close",
      },
    },
    header: {
      guestDemoBtn: "Guest Sandbox",
      accountBtn: "Account & Sync",
      guestBadge: "Guest Sandbox",
      signedInBadge: "Signed In",
      aiReadyTag: "AI Rotation Ready",
      runAiBtn: "Run AI Analysis",
    },
    fieldStatus: {
      aiAnalyzed: "AI Plan Ready",
      aiPartial: "Partial AI Plan",
      aiRunning: "Analyzing…",
      aiNotAnalyzed: "Not Yet Analyzed",
      viewAiBtn: "View AI Plan",
      runAiFieldBtn: "Analyze Parcel",
      soilVerified: "Lab / Farmer Soil",
      soilUnknown: "Soil Regional Ref.",
      waterReady: "Water Configured",
      elevationMissing: "Elev. unprovided",
    },
    section: {
      badge: "ML Intelligence Engine",
      title: "FieldShift AI Agricultural Intelligence",
      subtitle:
        "Satellite vegetation curves, seasonal hydrological balance, and explainable crop-rotation decisions grounded in Wilaya of Guelma agronomic records.",
      plainModeToggle: "Farmer Plain Mode",
      plainModeOn: "Plain Language",
      plainModeOff: "Technical Mode",
      printBriefBtn: "Print 1-Page Brief",
      runNewBtn: "Run New AI Analysis",
      previewDemoBtn: "Load Guelma Demo Intelligence",
      openComparisonPage: "Full Comparison Studio",
      historyLabel: "Analysis Runs",
      noSavedRuns: "No completed runs yet",
    },
    states: {
      noFieldsTitle: "Map a Farm Parcel First to Unlock AI Intelligence",
      noFieldsDesc:
        "Draw parcel borders on the Guelma satellite map or load the Seybouse pilot farm above, then run the ML engine for crop rotation strategies, bare-soil timelines, and scientific evidence.",
      unanalyzedTitle: "Parcel Mapped — Ready for ML Crop-Rotation Analysis",
      unanalyzedDesc:
        "Your farm coordinates, water profile, soil declaration, and crop history are ready. Launch the AI planner to evaluate 3 to 5 multi-season rotations tailored to your priorities.",
      pendingTitle: "Queuing Parcel Analysis Request…",
      pendingDesc: "Preparing field boundaries, water constraints, and regional dataset version pinning.",
      runningTitle: "Running Multi-Season Crop Rotation Simulation…",
      runningDesc:
        "Evaluating evapotranspiration, bare-soil radiation windows, nitrogen carryover, and cereal root-disease break cycles.",
      cancelBtn: "Cancel Analysis Request",
      cancelling: "Cancelling…",
      cancelledTitle: "Analysis Request Cancelled",
      cancelledDesc: "You cancelled the in-flight ML job cleanly before completion. You can adjust assumptions and re-run anytime.",
      failedTitle: "Analysis Request Could Not Complete",
      retryBtn: "Retry Analysis",
      unlinkedFieldTitle: "This Selected Parcel Was Not Included in the Active Analysis Run",
      unlinkedFieldDesc:
        "The active analysis covers other fields in this farm. Run a fresh analysis including this parcel to inspect its dedicated bare-soil calendar and strategies.",
      unlinkedFieldCta: "Analyze This Parcel Now",
    },
    runner: {
      modalTitle: "Configure AI Crop-Rotation Analysis",
      modalSubtitle:
        "Submits an asynchronous planning job via FieldShift API with your exact parcel geometry, soil/water declaration, and weighted agronomic priorities.",
      fieldsTitle: "1. Target Parcels Included in Analysis",
      planningTitle: "2. Planning Window & Crop Cycle",
      startSeason: "Starting Season",
      startYear: "Start Year",
      horizonSeasons: "Horizon (Seasons)",
      cycleMode: "Cycle Mode",
      cycleAnnual: "Annual Rotation (Multi-Year)",
      cycleConsecutive: "Consecutive Seasons",
      plantingMonth: "Preferred Planting Month",
      plantingMonthAuto: "Auto (match starting season)",
      prioritiesTitle: "3. Agronomic Priority Weights (Must Sum to 100%)",
      weightLabels: {
        water_saving: "Water Saving",
        soil_improvement: "Soil Health & Organic Matter",
        income: "Farm Income & Market Value",
        risk_reduction: "Drought & Disease Risk Reduction",
        forage_value: "Livestock Forage Output",
      },
      autoBalanceBtn: "Auto-balance to 100%",
      presetBalanced: "Balanced Guelma",
      presetWater: "Water Saving First",
      presetIncome: "Income & Forage",
      weightsSum: "Total Weight",
      marketPreference: "Market & Destination",
      targetCrops: "Target Crops to Test / Include",
      excludedCrops: "Crops to Exclude",
      whatIfTitle: "4. Climate What-If Scenario Overrides",
      whatIfDesc: "Stress-test rotations against hotter or drier future seasons.",
      tempDelta: "Temperature Shift (°C)",
      precipDelta: "Precipitation Change (%)",
      submitBtn: "Launch AI Analysis",
      submittingBtn: "Submitting Job…",
      closeBtn: "Close",
      selectAtLeastOneField: "Select at least one parcel to analyze.",
    },
    overview: {
      summaryHeading: "Executive Agronomic Summary",
      disclaimerHeading: "Important Decision Support Notice",
      statusOk: "Completed (OK)",
      statusPartial: "Partial Coverage",
      freshBadge: "Fresh ML Evaluation",
      staleBadge: "Degraded Mode — Stale Replay",
      analysisIdLabel: "Analysis ID",
      generatedAtLabel: "Generated",
      datasetVersionLabel: "Dataset Version",
      engineVersionLabel: "ML Engine",
      schemaVersionLabel: "Schema",
      envelopeWarningsTitle: "System & Parcel Envelope Warnings",
      fieldSelectorHeading: "Analyzed Parcels",
      partialBannerTitle: "Partial Field Plan Notice",
    },
    insights: {
      heading: "Parcel Seasonal Insights",
      bareCalendarTitle: "12-Month Bare Soil Exposure Timeline",
      bareLegend: "Bare Soil Exposure",
      activeLegend: "Vegetated / Covered",
      stressLegend: "Abiotic Stress Window",
      noBarePeriods: "No prolonged bare-soil windows flagged across the annual cycle.",
      stressMatrixTitle: "Seasonal Stress Indicator Matrix",
      noStressPeriods: "No moderate or high abiotic stress clusters flagged.",
      climateTrendTitle: "Regional Climate Trend Signal",
      evidenceLabel: "Observed Signal",
      monthsShortUnit: "Mo",
      statusOkLabel: "Covered",
    },
    strategies: {
      heading: "Rotation Strategy Comparison",
      subtitle: "Compare every evaluated strategy across agronomic balance scores, priority fit, and annual bare-soil exposure.",
      recommendedBadge: "AI Recommended",
      baselineBadge: "Current Baseline",
      statusBadge: {
        suggested: "Suggested",
        selected: "Selected Plan",
        rejected: "Rejected",
      },
      selectBtn: "Select Strategy",
      selectedBtn: "Selected as Plan",
      rejectBtn: "Reject",
      rejectedBtn: "Rejected",
      savingBtn: "Saving…",
      toastSelected: (name) => `Saved “${name}” as your selected rotation plan.`,
      toastRejected: (name) => `Marked “${name}” as rejected.`,
      toastError: "Could not save strategy selection. Changes reverted.",
      priorityFitLabel: "Priority Fit",
      confidenceLabel: "Strategy Confidence",
      bareDaysLabel: "Bare Soil Exposure",
      bareDaysUnit: "days / yr",
      radarTitle: "7-Axis Trade-Off vs Baseline",
      noStrategiesPartial: "Strategies unavailable under partial degraded evaluation.",
      scoreSectionTitle: "All 8 Evaluation Metrics",
    },
    timeline: {
      heading: "Season-by-Season Crop Rotation Timeline",
      emptyNotice: "No seasonal sequence entries provided for this strategy.",
      orderPrefix: "Step",
      plantingMonthLabel: "Planting Month",
      monthNotSet: "Flexible / Not specified",
      roleLabel: "Agronomic Role",
      categoryLabel: "Crop Family Group",
      statusLabel: "Plan Status",
      notesLabel: "Field & Rotation Notes",
      noNotes: "No additional notes for this season.",
      detailHint: "Click any season card to inspect planting window, role, and agronomic notes.",
    },
    explanations: {
      heading: "Explanation & Scientific Evidence",
      tabs: {
        reasons: "Why Recommended",
        evidence: "Scientific Evidence",
        benefits: "Expected Benefits",
        risks: "Risks & Mitigation",
        assumptions: "Assumptions",
        gaps: "Info Gaps",
        review: "Local Review",
      },
      codeToggleShow: "Show technical code",
      codeToggleHide: "Hide code",
      farmerInputBadge: "Farmer Input",
      datasetBadge: "Verified Dataset",
      derivedBadge: "Derived Metric",
      directBadge: "Direct Record",
      missionLabel: "Source Mission",
      observedLabel: "Observed",
      periodLabel: "Window",
      severityLabel: "Severity",
      likelihoodLabel: "Likelihood",
      mitigationLabel: "Recommended Mitigation",
      emptyList: "No items reported in this category.",
    },
    requestedCrops: {
      heading: "Requested Target Crop Evaluation",
      subtitle: "How your preferred target crops performed during multi-season optimization.",
      emptyNotice: "No specific target crops were requested in this analysis run.",
      outcomes: {
        included: "Included",
        replaced: "Replaced",
        excluded: "Excluded",
      },
      replacedBy: "Replaced by",
      includedIn: "Included in strategies",
      noStrategies: "Not scheduled",
      evidenceCount: (n) => `${n} evidence record${n === 1 ? "" : "s"}`,
      comparisonCount: (n) => `${n} comparison row${n === 1 ? "" : "s"}`,
    },
    quality: {
      heading: "Data Quality, Completeness & Limitations",
      farmTitle: "Farm-Level Assessment Quality",
      fieldTitle: "Selected Field Data Quality",
      completenessLabel: "Input Data Completeness",
      completenessUnavailable: "Not scored",
      completenessVsConfidenceNote:
        "Completeness measures field data & sensor coverage (0–100%). It is distinct from individual strategy model confidence (low / medium / high).",
      missingDataTitle: "Missing Inputs Checklist",
      missingDataEmpty: "All core soil, water, elevation, and crop history records provided.",
      modelWarningsTitle: "Model & Data Warnings",
      modelWarningsEmpty: "No model-level data warnings raised.",
      limitationsTitle: "Analytical Limitations",
      limitationsEmpty: "No additional scope limitations reported.",
    },
    severity: {
      low: "Low",
      medium: "Medium",
      high: "High",
    },
    categories: {
      cereals: "Cereals",
      legumes: "Legumes",
      oilseeds: "Oilseeds",
      vegetables: "Vegetables",
      forage: "Forage",
      cover_crops: "Cover Crops",
      fallow: "Fallow",
    },
  },
  fr: {
    workstation: {
      nav: {
        overview: "Aperçu",
        farmsFields: "Fermes & Parcelles",
        intelligence: "Intelligence Parcellaire",
        settings: "Paramètres",
      },
      breadcrumb: "Guelma / Opérations Agronomiques",
      geoContextTag: "Wilaya de Guelma · DZ-24",
      kpiContext: {
        farmsNone: "Aucune exploitation enregistrée",
        farmsActive: (n) => `${n} commune${n > 1 ? "s" : ""} active${n > 1 ? "s" : ""}`,
        fieldsNone: "En attente de délimitation",
        fieldsActive: "Parcelles géoréférencées",
        areaNone: "Tracez les limites sur carte",
        areaMean: (avgHa) => `${avgHa} ha moyenne / parcelle`,
        communesCoverage: "Couverture Wilaya 24",
      },
      mapHud: {
        viewportLabel: "Espace satellite Guelma",
        fitAllBtn: "Ajuster la vue",
        zoomIn: "Zoomer",
        zoomOut: "Dézoomer",
        legendSelected: "Sélectionnée",
        legendParcel: "Parcelle",
        layersLabel: "Contraste des couches satellite",
        drawParcelLabel: "Tracer une parcelle",
        prevFieldLabel: "Parcelle précédente",
        nextFieldLabel: "Parcelle suivante",
        communesChip: "Guelma · 34 communes",
        closeInspectorLabel: "Fermer l'inspecteur",
        openInspectorLabel: "Ouvrir l'inspecteur",
        readinessLabel: "Indice de préparation",
      },
      telemetry: {
        microclimateTitle: "Microclimat Wilaya 24",
        tempLabel: "Temp",
        precipLabel: "Précip.",
        windLabel: "Vent",
        solarLabel: "UV solaire",
        coverageTitle: "Couverture Wilaya 24",
        soilMetricsTitle: "Télémétrie sol & parcelle",
        moistureLabel: "Humidité racinaire",
        carbonLabel: "Couvert / MO",
        waterBalLabel: "Bilan hydrique",
        activitiesTitle: "Journal des opérations",
        readyStateActivity: "34 communes de Guelma indexées",
        readyStateTime: "DZ-24",
        boundaryReadyTitle: "Orthophoto satellite active",
        boundaryReadyTime: "Grille 10 m",
        mlReadyTitle: "Optimiseur de rotation prêt",
        mlReadyTime: "Actif",
      },
      analyticsZone: {
        title: "Santé des cultures & zones de rotation",
        healthyZones: "zones saines",
        zoneOptimal: "Couvert optimal",
        zoneModerate: "Suivi hydrique",
        zoneStress: "Stress abiotique",
        zoneBare: "Exposition sol nu",
        avgNdvi: "NDVI moy.",
        vsLastScan: "vs dernier scan",
        problemZones: "Fenêtres à risque",
        priorityAction: "Action prioritaire",
        emptyPriority: "Tracer parcelle",
        emptyStatus: "En attente",
      },
      inspector: {
        headerTitle: "Inspecteur de Parcelle",
        noSelection: "Sélectionnez une parcelle sur la carte ou le registre pour inspecter ses paramètres.",
        area: "Surface",
        commune: "Commune",
        coordinates: "Coordonnées",
        soil: "Profil Sol",
        water: "Eau & Irrigation",
        elevation: "Altitude",
        latestCrop: "Dernière Saison",
        aiStatus: "Intelligence Rotation",
        analyzeBtn: "Analyser",
        openPlanBtn: "Voir Plan IA",
        sim3dBtn: "Vue 3D",
        editBordersBtn: "Limites",
        editInfoBtn: "Infos",
      },
      table: {
        colParcel: "Parcelle / Localisation",
        colSpecs: "Sol, Eau & Altitude",
        colHistory: "Historique Cultural",
        colAnalysis: "Statut IA",
        colActions: "Opérations",
        bordersShort: "Limites",
        infoShort: "Infos",
        removeShort: "Suppr.",
        simShort: "Simuler",
      },
      settings: {
        title: "Paramètres de l'Espace",
        subtitle: "Gérez votre session, la langue d'affichage, le thème visuel, la terminologie et les données locales.",
        appearanceHeading: "Apparence & Thème",
        appearanceDesc: "Suivez les préférences système ou forcez l'espace de travail en mode Clair ou Sombre.",
        themeSystem: "Système",
        themeLight: "Clair",
        themeDark: "Sombre",
        switchToLight: "Passer en mode clair",
        switchToDark: "Passer en mode sombre",
        accountHeading: "Compte & Synchronisation",
        openAccountBtn: "Gérer Session & Compte",
        languageHeading: "Langue & Sens d'affichage",
        terminologyHeading: "Terminologie Agronomique",
        terminologyDesc: "Alternez entre termes techniques agronomiques et formulation simplifiée.",
        workspaceHeading: "Données de l'espace",
        clearWorkspaceDesc: "Réinitialiser les fermes et parcelles enregistrées localement.",
        closeBtn: "Fermer",
      },
    },
    header: {
      guestDemoBtn: "Bac à sable Invité",
      accountBtn: "Compte & Synchro",
      guestBadge: "Mode Invité",
      signedInBadge: "Connecté",
      aiReadyTag: "IA Rotation Prête",
      runAiBtn: "Lancer l'Analyse IA",
    },
    fieldStatus: {
      aiAnalyzed: "Plan IA Prêt",
      aiPartial: "Plan Partiel",
      aiRunning: "Analyse…",
      aiNotAnalyzed: "Non analysée",
      viewAiBtn: "Voir Plan IA",
      runAiFieldBtn: "Analyser",
      soilVerified: "Sol Vérifié",
      soilUnknown: "Réf. Régionale Sol",
      waterReady: "Eau Configurée",
      elevationMissing: "Altitude non fournie",
    },
    section: {
      badge: "Moteur d'Intelligence ML",
      title: "Intelligence Agronomique IA FieldShift",
      subtitle:
        "Courbes satellitaires, bilan hydrique saisonnier et rotations explicables ancrées sur la Wilaya de Guelma.",
      plainModeToggle: "Mode Simplifié",
      plainModeOn: "Langage Simple",
      plainModeOff: "Mode Technique",
      printBriefBtn: "Imprimer Fiche A4",
      runNewBtn: "Nouvelle Analyse IA",
      previewDemoBtn: "Charger Démo IA Guelma",
      openComparisonPage: "Studio Comparaison",
      historyLabel: "Historique des Analyses",
      noSavedRuns: "Aucune analyse enregistrée",
    },
    states: {
      noFieldsTitle: "Cartographiez une parcelle pour activer l'IA",
      noFieldsDesc:
        "Tracez une parcelle sur la carte de Guelma ou chargez les parcelles pilotes Seybouse, puis lancez le moteur de rotation IA.",
      unanalyzedTitle: "Parcelle cartographiée — Prête pour l'analyse IA",
      unanalyzedDesc:
        "Vos limites, profil hydrique, sol et historique cultural sont prêts. Lancez l'optimisation IA pour comparer 3 à 5 stratégies.",
      pendingTitle: "Mise en file de la requête d'analyse…",
      pendingDesc: "Préparation des limites, contraintes hydriques et versionnage des données.",
      runningTitle: "Simulation de rotation multi-saisons en cours…",
      runningDesc:
        "Calcul de l'évapotranspiration, fenêtres de sol nu, reliquat azoté et rupture des cycles parasitaires.",
      cancelBtn: "Annuler l'analyse",
      cancelling: "Annulation…",
      cancelledTitle: "Analyse annulée",
      cancelledDesc: "La requête ML en cours a été annulée proprement. Vous pouvez ajuster vos paramètres et relancer.",
      failedTitle: "Échec de l'analyse ML",
      retryBtn: "Réessayer",
      unlinkedFieldTitle: "Cette parcelle ne fait pas partie de l'analyse active",
      unlinkedFieldDesc:
        "L'analyse sélectionnée concerne d'autres parcelles. Lancez une analyse incluant cette parcelle pour voir ses recommandations.",
      unlinkedFieldCta: "Analyser cette parcelle",
    },
    runner: {
      modalTitle: "Configurer l'analyse IA de rotation",
      modalSubtitle:
        "Soumet une tâche asynchrone via l'API FieldShift avec géométrie réelle, profil eau/sol et pondération des priorités.",
      fieldsTitle: "1. Parcelles cibles incluses",
      planningTitle: "2. Fenêtre de planification & cycle",
      startSeason: "Saison de départ",
      startYear: "Année",
      horizonSeasons: "Horizon (saisons)",
      cycleMode: "Mode de cycle",
      cycleAnnual: "Rotation Annuelle",
      cycleConsecutive: "Saisons Consécutives",
      plantingMonth: "Mois de semis souhaité",
      plantingMonthAuto: "Auto (selon saison)",
      prioritiesTitle: "3. Poids des priorités agronomiques (Total = 100%)",
      weightLabels: {
        water_saving: "Économie d'eau",
        soil_improvement: "Santé des sols & humus",
        income: "Revenu & débouchés",
        risk_reduction: "Réduction des risques",
        forage_value: "Valeur fourragère",
      },
      autoBalanceBtn: "Équilibrer à 100%",
      presetBalanced: "Équilibre Guelma",
      presetWater: "Économie d'Eau",
      presetIncome: "Revenu & Fourrage",
      weightsSum: "Somme",
      marketPreference: "Débouché & Marché",
      targetCrops: "Cultures souhaitées à tester",
      excludedCrops: "Cultures à exclure",
      whatIfTitle: "4. Simulation climatique What-If",
      whatIfDesc: "Testez la robustesse face à un climat plus chaud ou plus sec.",
      tempDelta: "Écart température (°C)",
      precipDelta: "Variation pluie (%)",
      submitBtn: "Lancer l'Analyse IA",
      submittingBtn: "Envoi en cours…",
      closeBtn: "Fermer",
      selectAtLeastOneField: "Sélectionnez au moins une parcelle.",
    },
    overview: {
      summaryHeading: "Synthèse Agronomique Globale",
      disclaimerHeading: "Avertissement d'aide à la décision",
      statusOk: "Terminée (OK)",
      statusPartial: "Couverture Partielle",
      freshBadge: "Évaluation ML Récente",
      staleBadge: "Mode Dégradé — Rejeu Antérieur",
      analysisIdLabel: "ID Analyse",
      generatedAtLabel: "Généré le",
      datasetVersionLabel: "Jeu de données",
      engineVersionLabel: "Moteur ML",
      schemaVersionLabel: "Schéma",
      envelopeWarningsTitle: "Alertes Enveloppe Système & Parcelles",
      fieldSelectorHeading: "Parcelles analysées",
      partialBannerTitle: "Plan parcellaire partiel",
    },
    insights: {
      heading: "Indicateurs Saisonniers de la Parcelle",
      bareCalendarTitle: "Chronologie annuelle d'exposition du sol nu (12 mois)",
      bareLegend: "Sol Nu Exposé",
      activeLegend: "Couvert Végétal",
      stressLegend: "Stress Climatique",
      noBarePeriods: "Aucune période critique de sol nu prolongé signalée.",
      stressMatrixTitle: "Matrice des stress environnementaux",
      noStressPeriods: "Aucun épisode de stress modéré ou élevé signalé.",
      climateTrendTitle: "Signal climatique régional",
      evidenceLabel: "Observation",
      monthsShortUnit: "Mois",
      statusOkLabel: "Couvert",
    },
    strategies: {
      heading: "Comparaison des Stratégies de Rotation",
      subtitle: "Comparez les scénarios sur 7 scores agronomiques normalisés (0–100) et les jours annuels de sol nu.",
      recommendedBadge: "Recommandée par l'IA",
      baselineBadge: "Référence Actuelle",
      statusBadge: {
        suggested: "Suggérée",
        selected: "Sélectionnée",
        rejected: "Rejetée",
      },
      selectBtn: "Choisir ce plan",
      selectedBtn: "Plan sélectionné",
      rejectBtn: "Rejeter",
      rejectedBtn: "Rejeté",
      savingBtn: "Enregistrement…",
      toastSelected: (name) => `« ${name} » enregistrée comme rotation choisie.`,
      toastRejected: (name) => `« ${name} » marquée comme rejetée.`,
      toastError: "Impossible d'enregistrer le choix. État restauré.",
      priorityFitLabel: "Adéquation Priorités",
      confidenceLabel: "Confiance stratégie",
      bareDaysLabel: "Exposition Sol Nu",
      bareDaysUnit: "j / an",
      radarTitle: "Compromis 7 axes vs Référence",
      noStrategiesPartial: "Stratégies non disponibles en mode dégradé partiel.",
      scoreSectionTitle: "Les 8 indicateurs d'évaluation",
    },
    timeline: {
      heading: "Frise Chronologique de Rotation Saisonnière",
      emptyNotice: "Aucune séquence saisonnière fournie pour cette stratégie.",
      orderPrefix: "Étape",
      plantingMonthLabel: "Mois de semis",
      monthNotSet: "Flexible / Non précisé",
      roleLabel: "Rôle agronomique",
      categoryLabel: "Famille / Catégorie",
      statusLabel: "Statut",
      notesLabel: "Notes agronomiques",
      noNotes: "Aucune note complémentaire pour cette saison.",
      detailHint: "Cliquez sur une saison pour afficher les détails de semis, rôle et notes.",
    },
    explanations: {
      heading: "Explications & Preuves Scientifiques",
      tabs: {
        reasons: "Motifs clés",
        evidence: "Preuves scientifiques",
        benefits: "Bénéfices",
        risks: "Risques & Parades",
        assumptions: "Hypothèses",
        gaps: "Manques d'info",
        review: "Revue locale",
      },
      codeToggleShow: "Afficher code technique",
      codeToggleHide: "Masquer code",
      farmerInputBadge: "Saisie Agriculteur",
      datasetBadge: "Jeu de Données Vérifié",
      derivedBadge: "Calcul Dérivé",
      directBadge: "Mesure Directe",
      missionLabel: "Source / Mission",
      observedLabel: "Valeur observée",
      periodLabel: "Période",
      severityLabel: "Sévérité",
      likelihoodLabel: "Probabilité",
      mitigationLabel: "Mesure d'atténuation",
      emptyList: "Aucun élément signalé dans cette catégorie.",
    },
    requestedCrops: {
      heading: "Évaluation des Cultures Ciblées",
      subtitle: "Statut d'intégration des cultures demandées lors de l'optimisation.",
      emptyNotice: "Aucune culture cible particulière n'a été spécifiée.",
      outcomes: {
        included: "Intégrée",
        replaced: "Remplacée",
        excluded: "Exclue",
      },
      replacedBy: "Remplacée par",
      includedIn: "Incluse dans les stratégies",
      noStrategies: "Non planifiée",
      evidenceCount: (n) => `${n} preuve${n > 1 ? "s" : ""}`,
      comparisonCount: (n) => `${n} comparaison${n > 1 ? "s" : ""}`,
    },
    quality: {
      heading: "Qualité des Données, Complétude & Limites",
      farmTitle: "Qualité au niveau de l'Exploitation",
      fieldTitle: "Qualité des Données de la Parcelle",
      completenessLabel: "Complétude des données d'entrée",
      completenessUnavailable: "Non évaluée",
      completenessVsConfidenceNote:
        "La complétude (0–100%) reflète la richesse des données fournies, distincte de la confiance du modèle sur chaque stratégie.",
      missingDataTitle: "Données manquantes à compléter",
      missingDataEmpty: "Toutes les données sol, eau, altitude et historique sont fournies.",
      modelWarningsTitle: "Avertissements Modèle & Données",
      modelWarningsEmpty: "Aucun avertissement analytique émis.",
      limitationsTitle: "Limites méthodologiques",
      limitationsEmpty: "Aucune limite supplémentaire signalée.",
    },
    severity: {
      low: "Faible",
      medium: "Modérée",
      high: "Élevée",
    },
    categories: {
      cereals: "Céréales",
      legumes: "Légumineuses",
      oilseeds: "Oléagineux",
      vegetables: "Maraîchage",
      forage: "Fourrages",
      cover_crops: "Couverts végétaux",
      fallow: "Jachère",
    },
  },
  ar: {
    workstation: {
      nav: {
        overview: "نظرة عامة",
        farmsFields: "المزارع والقطع",
        intelligence: "ذكاء الحقل",
        settings: "الإعدادات",
      },
      breadcrumb: "قالمة / العمليات الفلاحية",
      geoContextTag: "ولاية قالمة · DZ-24",
      kpiContext: {
        farmsNone: "لا توجد مزارع مسجلة",
        farmsActive: (n) => `${n} بلدية نشطة`,
        fieldsNone: "بانتظار رسم الحدود",
        fieldsActive: "قطع محددة جغرافياً",
        areaNone: "ارسم الحدود على الخريطة",
        areaMean: (avgHa) => `${avgHa} هـ متوسط / قطعة`,
        communesCoverage: "تغطية ولاية 24",
      },
      mapHud: {
        viewportLabel: "منطقة القمر الصناعي · قالمة",
        fitAllBtn: "احتواء الحدود",
        zoomIn: "تكبير",
        zoomOut: "تصغير",
        legendSelected: "محددة",
        legendParcel: "قطعة",
        layersLabel: "تبديل تباين الطبقات",
        drawParcelLabel: "رسم قطعة على الخريطة",
        prevFieldLabel: "القطعة السابقة",
        nextFieldLabel: "القطعة التالية",
        communesChip: "قالمة · 34 بلدية",
        closeInspectorLabel: "إغلاق المعاينة",
        openInspectorLabel: "فتح المعاينة",
        readinessLabel: "جاهزية المحصول",
      },
      telemetry: {
        microclimateTitle: "المناخ المحلي · ولاية 24",
        tempLabel: "الحرارة",
        precipLabel: "الأمطار",
        windLabel: "الرياح",
        solarLabel: "الإشعاع",
        coverageTitle: "عمليات ولاية قالمة",
        soilMetricsTitle: "مؤشرات التربة والمياه",
        moistureLabel: "رطوبة الجذور",
        carbonLabel: "الغطاء والمادة العضوية",
        waterBalLabel: "التوازن المائي",
        activitiesTitle: "سجل النشاط الميداني",
        readyStateActivity: "فهرسة 34 بلدية بولاية قالمة",
        readyStateTime: "DZ-24",
        boundaryReadyTitle: "صور الأقمار الصناعية نشطة",
        boundaryReadyTime: "دقة 10 م",
        mlReadyTitle: "مخطط التناوب الذكي جاهز",
        mlReadyTime: "جاهز",
      },
      analyticsZone: {
        title: "صحة المحاصيل ومناطق التناوب",
        healthyZones: "مناطق سليمة",
        zoneOptimal: "غطاء مثالي",
        zoneModerate: "مراقبة الرطوبة",
        zoneStress: "تنبيه إجهاد",
        zoneBare: "كشف التربة العارية",
        avgNdvi: "متوسط NDVI",
        vsLastScan: "مقارنة بالمسح",
        problemZones: "فترات حرجة",
        priorityAction: "أولوية التدخل",
        emptyPriority: "أضف قطعة",
        emptyStatus: "استعداد",
      },
      inspector: {
        headerTitle: "معاينة القطعة",
        noSelection: "اختر قطعة على الخريطة أو الجدول لعرض معطياتها التربوية والمائية.",
        area: "المساحة",
        commune: "البلدية",
        coordinates: "الإحداثيات",
        soil: "التربة",
        water: "المياه والسقي",
        elevation: "الارتفاع",
        latestCrop: "آخر موسم",
        aiStatus: "حالة التحليل الذكي",
        analyzeBtn: "تشغيل التحليل",
        openPlanBtn: "عرض الخطة",
        sim3dBtn: "محاكاة 3D",
        editBordersBtn: "الحدود",
        editInfoBtn: "البيانات",
      },
      table: {
        colParcel: "القطعة والموقع",
        colSpecs: "التربة والماء والارتفاع",
        colHistory: "سجل المحاصيل",
        colAnalysis: "التحليل الذكي",
        colActions: "الإجراءات",
        bordersShort: "الحدود",
        infoShort: "تعديل",
        removeShort: "حذف",
        simShort: "محاكاة",
      },
      settings: {
        title: "إعدادات منصة العمل",
        subtitle: "إدارة المزامنة السحابية، لغة العرض، المظهر البصري، مستوى المصطلحات، وإعادة ضبط البيانات المحلية.",
        appearanceHeading: "المظهر والسمة البصرية",
        appearanceDesc: "مطابقة إعدادات النظام تلقائياً أو تثبيت الوضع الفاتح أو الداكن.",
        themeSystem: "النظام",
        themeLight: "فاتح",
        themeDark: "داكن",
        switchToLight: "التبديل إلى الوضع الفاتح",
        switchToDark: "التبديل إلى الوضع الداكن",
        accountHeading: "الحساب والمزامنة",
        openAccountBtn: "إدارة الحساب والجلسة",
        languageHeading: "لغة العرض والاتجاه",
        terminologyHeading: "مستوى المصطلحات الفلاحية",
        terminologyDesc: "التبديل بين المصطلحات العلمية الدقيقة والصياغة الفلاحية المبسطة.",
        workspaceHeading: "بيانات مساحة العمل",
        clearWorkspaceDesc: "مسح المزارع والقطع المحفوظة محلياً وإعادة التهيئة.",
        closeBtn: "إغلاق",
      },
    },
    header: {
      guestDemoBtn: "جلسة تجريبية",
      accountBtn: "الحساب والمزامنة",
      guestBadge: "وضع تجريبي",
      signedInBadge: "مسجل الدخول",
      aiReadyTag: "الذكاء الاصطناعي جاهز",
      runAiBtn: "تشغيل التحليل الذكي",
    },
    fieldStatus: {
      aiAnalyzed: "تحليل الذكاء جاهز",
      aiPartial: "تغطية جزئية",
      aiRunning: "جارٍ التحليل…",
      aiNotAnalyzed: "غير محللة بعد",
      viewAiBtn: "عرض خطة الذكاء",
      runAiFieldBtn: "تحليل القطعة",
      soilVerified: "تربة موثقة",
      soilUnknown: "مرجع جهوي للتربة",
      waterReady: "بيانات المياه جاهزة",
      elevationMissing: "الارتفاع غير محدد",
    },
    section: {
      badge: "محرك الذكاء الزراعي",
      title: "ذكاء FieldShift الزراعي لتحليل الدورات",
      subtitle:
        "مؤشرات الأقمار الصناعية، التوازن المائي الفصلي، وتوصيات تناوب زراعي مبررة علمياً لولاية قالمة.",
      plainModeToggle: "وضع الفلاح المبسط",
      plainModeOn: "لغة مبسطة",
      plainModeOff: "الوضع العلمي",
      printBriefBtn: "طباعة ملخص صفحة واحدة",
      runNewBtn: "تشغيل تحليل جديد",
      previewDemoBtn: "معاينة ذكاء قالمة النموذجي",
      openComparisonPage: "استوديو المقارنة الكامل",
      historyLabel: "سجل التحليلات",
      noSavedRuns: "لا توجد تحليلات مكتملة بعد",
    },
    states: {
      noFieldsTitle: "ارسم قطعة أرض أولاً لتفعيل الذكاء الزراعي",
      noFieldsDesc:
        "حدّد حدود قطعتك على خريطة ولاية قالمة أو حمّل قطع سيبوس النموذجية، ثم شغّل محرك التحليل الذكي.",
      unanalyzedTitle: "القطعة مسجلة — جاهزة لتحليل التناوب الزراعي",
      unanalyzedDesc:
        "إحداثيات المزرعة وموارد السقي والتربة وسجل المحاصيل جاهزة. أطلق التحليل للحصول على 3 إلى 5 استراتيجيات تناوب.",
      pendingTitle: "جارٍ إدراج طلب التحليل في قائمة المعالجة…",
      pendingDesc: "تجهيز حدود القطعة ومعطيات المياه وربط نسخة البيانات المرجعية.",
      runningTitle: "جارٍ تشغيل محاكاة الدورات الزراعية بالذكاء الاصطناعي…",
      runningDesc:
        "تقييم البخر نتح، فترات كشف التربة، رصيد الآزوت الطبيعي، وكسر دورات أمراض الحبوب.",
      cancelBtn: "إلغاء طلب التحليل",
      cancelling: "جارٍ الإلغاء…",
      cancelledTitle: "تم إلغاء طلب التحليل",
      cancelledDesc: "تم إيقاف المهمة قبل الاكتمال بنجاح. يمكنك تعديل الأولويات وإعادة التشغيل في أي وقت.",
      failedTitle: "تعذّر إتمام طلب التحليل",
      retryBtn: "إعادة المحاولة",
      unlinkedFieldTitle: "هذه القطعة غير مشمولة في التحليل المعروض حالياً",
      unlinkedFieldDesc:
        "التحليل النشط يخص قطعاً أخرى في هذه المزرعة. شغّل تحليلاً جديداً يشمل هذه القطعة لعرض تقويمها واستراتيجياتها.",
      unlinkedFieldCta: "تحليل هذه القطعة الآن",
    },
    runner: {
      modalTitle: "إعداد تشغيل تحليل التناوب الزراعي الذكي",
      modalSubtitle:
        "يرسل طلب تحليل غير متزامن عبر واجهة FieldShift باستخدام حدود قطعتك ومعطيات التربة والمياه وأوزان الأولويات.",
      fieldsTitle: "١. القطع المشمولة في التحليل",
      planningTitle: "٢. نافذة التخطيط ونمط الدورة",
      startSeason: "فصل البداية",
      startYear: "السنة",
      horizonSeasons: "الأفق (عدد المواسم)",
      cycleMode: "نمط التغطية",
      cycleAnnual: "دورة سنوية متكاملة",
      cycleConsecutive: "مواسم متتالية",
      plantingMonth: "شهر الزراعة المفضل",
      plantingMonthAuto: "تلقائي (متوافق مع الفصل)",
      prioritiesTitle: "٣. أوزان الأولويات الفلاحية (المجموع = 100%)",
      weightLabels: {
        water_saving: "توفير مياه السقي",
        soil_improvement: "تحسين التربة والدبال",
        income: "العائد المالي والسوق",
        risk_reduction: "تقليل مخاطر الجفاف والأمراض",
        forage_value: "إنتاج الأعلاف والمواشي",
      },
      autoBalanceBtn: "موازنة إلى 100%",
      presetBalanced: "توازن قالمة",
      presetWater: "أولوية حفظ الماء",
      presetIncome: "الدخل والأعلاف",
      weightsSum: "المجموع",
      marketPreference: "توجه السوق",
      targetCrops: "محاصيل مستهدفة للاختبار",
      excludedCrops: "محاصيل مستبعدة",
      whatIfTitle: "٤. محاكاة تغيّر المناخ (ماذا لو؟)",
      whatIfDesc: "اختبر صمود الاستراتيجيات في مواسم أشد حرارة أو جفافاً.",
      tempDelta: "تغيّر الحرارة (°C)",
      precipDelta: "تغيّر الأمطار (%)",
      submitBtn: "إطلاق التحليل الذكي",
      submittingBtn: "جارٍ الإرسال…",
      closeBtn: "إغلاق",
      selectAtLeastOneField: "اختر قطعة واحدة على الأقل للتحليل.",
    },
    overview: {
      summaryHeading: "الملخص الفلاحي التنفيذي",
      disclaimerHeading: "تنبيه دعم القرار الزراعي",
      statusOk: "مكتمل (سليم)",
      statusPartial: "نتائج جزئية",
      freshBadge: "تحليل جديد من المحرك",
      staleBadge: "الوضع الاحتياطي — إعادة عرض سابقة",
      analysisIdLabel: "معرّف التحليل",
      generatedAtLabel: "تاريخ التوليد",
      datasetVersionLabel: "إصدار البيانات",
      engineVersionLabel: "إصدار المحرك",
      schemaVersionLabel: "المخطط",
      envelopeWarningsTitle: "تنبيهات النظام والقطع (المغلف الخارجي)",
      fieldSelectorHeading: "القطع المحللة",
      partialBannerTitle: "ملاحظة خطة جزئية للقطعة",
    },
    insights: {
      heading: "المؤشرات الفصلية للقطعة",
      bareCalendarTitle: "التقويم السنوي لانكشاف التربة (١٢ شهراً)",
      bareLegend: "تربة مكشوفة",
      activeLegend: "غطاء نباتي",
      stressLegend: "إجهاد مناخي",
      noBarePeriods: "لم تُسجل فترات خطيرة لانكشاف التربة خلال الدورة السنوية.",
      stressMatrixTitle: "مصفوفة الإجهادات البيئية الشهرية",
      noStressPeriods: "لا توجد مؤشرات إجهاد مناخي متوسطة أو مرتفعة.",
      climateTrendTitle: "الاتجاه المناخي المحلي الملاحظ",
      evidenceLabel: "الدليل الملاحظ",
      monthsShortUnit: "شهر",
      statusOkLabel: "مغطاة",
    },
    strategies: {
      heading: "مقارنة استراتيجيات التناوب الزراعي",
      subtitle: "قارن كل استراتيجية عبر 7 مؤشرات تقييم وأيام انكشاف التربة السنوية.",
      recommendedBadge: "توصية الذكاء",
      baselineBadge: "المرجع الحالي",
      statusBadge: {
        suggested: "مقترحة",
        selected: "مختارة للخطة",
        rejected: "مرفوضة",
      },
      selectBtn: "اعتماد الاستراتيجية",
      selectedBtn: "خطة معتمدة",
      rejectBtn: "رفض",
      rejectedBtn: "مرفوضة",
      savingBtn: "جارٍ الحفظ…",
      toastSelected: (name) => `تم حفظ «${name}» كخطة تناوب معتمدة لمزرعتك.`,
      toastRejected: (name) => `تم تعليم «${name}» كمرفوضة.`,
      toastError: "تعذر حفظ الاختيار لدى الخادم. تمت استعادة الحالة السابقة.",
      priorityFitLabel: "توافق الأولويات",
      confidenceLabel: "درجة ثقة الاستراتيجية",
      bareDaysLabel: "أيام انكشاف التربة",
      bareDaysUnit: "يوم / سنة",
      radarTitle: "توازن ٧ محاور مقارنة بالمرجع",
      noStrategiesPartial: "لا تتوفر استراتيجيات كاملة في هذا التقييم الجزئي.",
      scoreSectionTitle: "مؤشرات التقييم الثمانية",
    },
    timeline: {
      heading: "الجدول الزمني الفصلي للتناوب الزراعي",
      emptyNotice: "لا توجد مراحل موسمية مسجلة لهذه الاستراتيجية.",
      orderPrefix: "مرحلة",
      plantingMonthLabel: "شهر الزراعة",
      monthNotSet: "مرن / غير محدد",
      roleLabel: "الدور الزراعي",
      categoryLabel: "الفصيلة النباتية",
      statusLabel: "الحالة",
      notesLabel: "ملاحظات التوصية",
      noNotes: "لا توجد ملاحظات إضافية لهذا الموسم.",
      detailHint: "انقر على أي موسم لعرض شهر الزراعة والدور والملاحظات الميدانية.",
    },
    explanations: {
      heading: "التفسير والأدلة العلمية",
      tabs: {
        reasons: "لماذا نوصي بها",
        evidence: "الأدلة العلمية",
        benefits: "الفوائد المتوقعة",
        risks: "المخاطر والتفادي",
        assumptions: "الافتراضات",
        gaps: "نقص البيانات",
        review: "المراجعة المحلية",
      },
      codeToggleShow: "عرض الرمز التقني",
      codeToggleHide: "إخفاء الرمز",
      farmerInputBadge: "مدخل الفلاح",
      datasetBadge: "بيانات علمية موثقة",
      derivedBadge: "مؤشر مشتق",
      directBadge: "قياس مباشر",
      missionLabel: "المصدر / القمر",
      observedLabel: "القيمة المرصودة",
      periodLabel: "الفترة",
      severityLabel: "الشدة",
      likelihoodLabel: "الاحتمال",
      mitigationLabel: "إجراء التخفيف الموصى به",
      emptyList: "لا توجد عناصر في هذا القسم.",
    },
    requestedCrops: {
      heading: "تقييم المحاصيل المستهدفة من الفلاح",
      subtitle: "نتيجة إدماج أو استبدال المحاصيل التي طلبت اختبارها في الدورة.",
      emptyNotice: "لم تُطلب محاصيل مستهدفة إضافية في هذا التحليل.",
      outcomes: {
        included: "مدمج في الخطة",
        replaced: "تم استبداله",
        excluded: "مستبعد",
      },
      replacedBy: "استُبدل بـ",
      includedIn: "مدمج في الاستراتيجيات",
      noStrategies: "غير مدرج",
      evidenceCount: (n) => `${n} دليل علمي`,
      comparisonCount: (n) => `${n} صف مقارنة`,
    },
    quality: {
      heading: "جودة البيانات، الاكتمال والقيود",
      farmTitle: "جودة بيانات المزرعة الشاملة",
      fieldTitle: "جودة بيانات القطعة المحددة",
      completenessLabel: "نسبة اكتمال المعطيات",
      completenessUnavailable: "غير محسوبة",
      completenessVsConfidenceNote:
        "نسبة الاكتمال تقيس توفر معطيات الفلاح والأقمار الصناعية (0–100%)، وهي مستقلة عن درجة ثقة النموذج في كل استراتيجية.",
      missingDataTitle: "قائمة المعطيات الناقصة",
      missingDataEmpty: "جميع بيانات التربة والماء والارتفاع وسجل المحاصيل مكتملة.",
      modelWarningsTitle: "تحذيرات النموذج والبيانات",
      modelWarningsEmpty: "لا توجد تحذيرات صادرة عن المحرك.",
      limitationsTitle: "القيود المنهجية للتحليل",
      limitationsEmpty: "لا توجد قيود إضافية مسجلة.",
    },
    severity: {
      low: "منخفض",
      medium: "متوسط",
      high: "مرتفع",
    },
    categories: {
      cereals: "حبوب",
      legumes: "بقوليات",
      oilseeds: "محاصيل زيتية",
      vegetables: "خضروات",
      forage: "أعلاف",
      cover_crops: "محاصيل تغطية",
      fallow: "أرض بور",
    },
  },
};
