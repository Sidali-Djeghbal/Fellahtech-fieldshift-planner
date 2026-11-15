import type { Language } from "@/lib/schemas";

export interface GuelmaWorkspaceDictionary {
  brandTag: string;
  provinceBadge: string;
  dashboardTitle: string;
  dashboardSubtitle: string;
  addFarmBtn: string;
  addFieldBtn: string;
  loadSamplesBtn: string;
  clearWorkspaceBtn: string;
  emptyTitle: string;
  emptyDesc: string;
  emptyStep1: string;
  emptyStep2: string;
  emptyStep3: string;
  kpiFarms: string;
  kpiFields: string;
  kpiArea: string;
  kpiCommunes: string;
  overviewMapTitle: string;
  overviewMapSub: string;
  farmsListTitle: string;
  communeBadge: string;
  fieldsSuffix: string;
  inspectBtn: string;
  editBordersBtn: string;
  editInfoBtn: string;
  removeFieldBtn: string;
  editFarmBtn: string;
  removeFarmBtn: string;
  soilFarmerKnown: string;
  soilUnknownTag: string;
  elevNotProvided: string;
  cropHistoryCount: (n: number) => string;

  editor: {
    newFieldTitle: string;
    editBordersTitle: string;
    subtitle: string;
    searchCommune: string;
    allCommunesLabel: (n: number) => string;
    quickPresetLabel: string;
    layersLabel: string;
    view2d: string;
    view3d: string;
    undo: string;
    redo: string;
    clear: string;
    closePoly: string;
    backDashboard: string;
    saveMyFarm: string;
    saveUpdatedBorders: string;
    verticesLbl: string;
    areaLbl: string;
    perimLbl: string;
    centroidLbl: string;
    demRefLbl: string;
    demNonBindingNote: string;
    communeDetectedLbl: string;
    statusInsideGuelma: string;
    statusOutsideGuelma: string;
    statusNeedVertices: string;
    statusSelfIntersect: string;
    statusReady: string;
    hintAddVertex: string;
    hintSnapClose: string;
    hintAdjustVertices: string;
    deleteSelectedVertex: string;
    svgFallbackNotice: string;
  };

  form: {
    createTitle: string;
    editFieldTitle: string;
    subtitle: string;
    farmSection: string;
    targetModeNew: string;
    targetModeExisting: string;
    chooseFarmLabel: string;
    farmNameLabel: string;
    farmNamePlaceholder: string;
    countryLabel: string;
    regionLabel: string;
    communeLabel: string;
    communeAutoHint: string;
    fieldSection: string;
    fieldIdLabel: string;
    fieldNameLabel: string;
    fieldNamePlaceholder: string;
    areaLabel: string;
    areaAutoTag: string;
    elevLabel: string;
    elevOptionalPlaceholder: string;
    elevAdrNote: string;
    soilSection: string;
    soilModeUnknown: string;
    soilModeKnown: string;
    soilTypeLabel: string;
    usdaCalcBtn: string;
    soilPhLabel: string;
    soilOmLabel: string;
    soilDateLabel: string;
    waterSection: string;
    waterAvailLabel: string;
    waterSourceLabel: string;
    waterSourceOtherLabel: string;
    irrigationLabel: string;
    historySection: string;
    historySubtitle: string;
    addHistoryBtn: string;
    removeRowLabel: string;
    seasonLabel: string;
    yearLabel: string;
    monthLabel: string;
    monthAutoOption: string;
    catalogCropLabel: string;
    customCropLabel: string;
    customCropPlaceholder: string;
    yieldLabel: string;
    notesLabel: string;
    notesPrivateTag: string;
    cancelBtn: string;
    saveFarmFieldBtn: string;
    updateFieldBtn: string;
    errFarmName: string;
    errFieldId: string;
    errFieldName: string;
    errCropMissing: (row: number) => string;
    errAreaPositive: string;
    errWaterOtherRequired: string;
  };

  editFarmModal: {
    title: string;
    subtitle: string;
    saveBtn: string;
  };

  confirmDelete: {
    fieldTitle: string;
    fieldBody: (name: string) => string;
    farmTitle: string;
    farmBody: (name: string, count: number) => string;
    confirmRemoveBtn: string;
    cancelBtn: string;
  };
  descendingToParcel: string;
  closedTag: string;
  clearSearchAria: string;
  closeCommuneAria: string;
  verticesSummaryTitle: (count: number, perimM: number) => string;
  customCropOption: string;
  parcelDefaultSuffix: string;
}

export const GUELMA_WORKSPACE_I18N: Record<Language, GuelmaWorkspaceDictionary> = {
  en: {
    brandTag: "Wilaya of Guelma · 34 Communes",
    provinceBadge: "Wilaya 24 · Guelma Province",
    dashboardTitle: "Guelma Farm & Field Command Center",
    dashboardSubtitle:
      "Register your farms across all 34 communes of Guelma, trace precision parcel boundaries on satellite imagery, and simulate sustainable crop rotations.",
    addFarmBtn: "Add farm or field",
    addFieldBtn: "Add field to farm",
    loadSamplesBtn: "Load sample parcels",
    clearWorkspaceBtn: "Reset workspace",
    emptyTitle: "No farms or fields added yet",
    emptyDesc:
      "Trace parcel borders on the Guelma satellite canvas to compute hectares and build your agronomic profile.",
    emptyStep1: "Trace field borders across any of Guelma's 34 communes",
    emptyStep2: "Save parcel borders with soil, water, and crop history",
    emptyStep3: "Inspect NDVI, soil moisture, 3D relief, and AI rotations",
    kpiFarms: "Registered farms",
    kpiFields: "Mapped fields",
    kpiArea: "Total area (ha)",
    kpiCommunes: "Guelma communes",
    overviewMapTitle: "Guelma province field map",
    overviewMapSub: "Click any saved field to inspect or simulate crop rotations",
    farmsListTitle: "Farms & fields directory",
    communeBadge: "Commune",
    fieldsSuffix: "fields",
    inspectBtn: "Inspect & simulate",
    editBordersBtn: "Edit borders",
    editInfoBtn: "Edit info",
    removeFieldBtn: "Delete parcel",
    editFarmBtn: "Edit farm info",
    removeFarmBtn: "Delete farm",
    soilFarmerKnown: "Farmer Soil Data",
    soilUnknownTag: "Soil Unverified",
    elevNotProvided: "Elevation unset",
    cropHistoryCount: (n) => `${n} season record${n === 1 ? "" : "s"}`,

    editor: {
      newFieldTitle: "Trace Farm Borders · Wilaya of Guelma",
      editBordersTitle: "Refine Field Borders · Precision CAD",
      subtitle:
        "Jump to any of the 34 communes, click corners along parcel boundaries, adjust edge midpoints, and click Save My Farm.",
      searchCommune: "Jump to commune (e.g. Bouchegouf, Oued Zenati, Guelma)…",
      allCommunesLabel: (n) => `${n} communes in Guelma`,
      quickPresetLabel: "Quick Demo Parcels",
      layersLabel: "Satellite Overlays",
      view2d: "2D Ortho",
      view3d: "3D Relief",
      undo: "Undo",
      redo: "Redo",
      clear: "Clear",
      closePoly: "Close Shape",
      backDashboard: "Back to Dashboard",
      saveMyFarm: "Save My Farm →",
      saveUpdatedBorders: "Apply Updated Borders →",
      verticesLbl: "Vertices",
      areaLbl: "Geodesic Area",
      perimLbl: "Perimeter",
      centroidLbl: "Center",
      demRefLbl: "DEM Terrain Ref",
      demNonBindingNote: "Reference only — farmer profile stays separate",
      communeDetectedLbl: "Nearest Commune",
      statusInsideGuelma: "Inside Guelma Province",
      statusOutsideGuelma: "Outside Guelma boundary",
      statusNeedVertices: "Place at least 3 corners on the parcel",
      statusSelfIntersect: "Edges cross — adjust vertices to uncross",
      statusReady: "Closed polygon ready to save",
      hintAddVertex: "Click on satellite imagery to place boundary corners.",
      hintSnapClose: "Place >=3 corners, then click first green pin or Close Shape.",
      hintAdjustVertices: "Drag corners to refine, click + midpoints to split edges.",
      deleteSelectedVertex: "Delete Selected Vertex",
      svgFallbackNotice: "Precision SVG Satellite Grid Active",
    },

    form: {
      createTitle: "Complete Farm & Field Profile",
      editFieldTitle: "Edit Field Agronomic Profile",
      subtitle:
        "Verified against FELLAH TECH System Design (ENDPOINTS v3.2 · ADR-3 · ADR-5) for Wilaya of Guelma.",
      farmSection: "1. Farm Identity & Location",
      targetModeNew: "Create New Farm",
      targetModeExisting: "Add to Existing Farm",
      chooseFarmLabel: "Select Farm",
      farmNameLabel: "Farm Name",
      farmNamePlaceholder: "e.g. Domaine Seybouse Nord",
      countryLabel: "Country",
      regionLabel: "Wilaya / Region",
      communeLabel: "Commune (Wilaya of Guelma)",
      communeAutoHint: "Auto-matched from drawn coordinates",
      fieldSection: "2. Mapped Field Parameters",
      fieldIdLabel: "Field Code / ID",
      fieldNameLabel: "Field Name",
      fieldNamePlaceholder: "e.g. Parcelle Blé Dur A1",
      areaLabel: "Area (Hectares)",
      areaAutoTag: "Auto-computed from drawn borders",
      elevLabel: "Elevation (m · optional)",
      elevOptionalPlaceholder: "Leave blank unless farmer-verified",
      elevAdrNote: "ADR-5: Leave blank if unknown — never fabricated from DEM automatically.",
      soilSection: "3. Soil Profile (ADR-5)",
      soilModeUnknown: "Soil Unknown / Regional Baseline",
      soilModeKnown: "Farmer Knows / Lab Soil Test",
      soilTypeLabel: "USDA Soil Texture",
      usdaCalcBtn: "USDA Clay/Silt/Sand Calculator",
      soilPhLabel: "Soil pH (3–11)",
      soilOmLabel: "Organic Matter (%)",
      soilDateLabel: "Soil Test Date",
      waterSection: "4. Water & Irrigation",
      waterAvailLabel: "Water Availability",
      waterSourceLabel: "Water Source",
      waterSourceOtherLabel: "Specify Other Source",
      irrigationLabel: "Irrigation System",
      historySection: "5. Multi-Year Crop History (1–30 records)",
      historySubtitle: "At least 1 previous or current season is required for rotation planning.",
      addHistoryBtn: "+ Add Season Row",
      removeRowLabel: "Remove row",
      seasonLabel: "Season",
      yearLabel: "Year",
      monthLabel: "Planting Month",
      monthAutoOption: "Not specified",
      catalogCropLabel: "Catalog Crop",
      customCropLabel: "Custom / Local Variety Name",
      customCropPlaceholder: "e.g. Mohamed Ben Bachir",
      yieldLabel: "Yield (t/ha)",
      notesLabel: "Farmer Notes (private)",
      notesPrivateTag: "Private — kept off public API summaries",
      cancelBtn: "Cancel",
      saveFarmFieldBtn: "Save Farm & Field to Dashboard",
      updateFieldBtn: "Save Changes",
      errFarmName: "Farm name is required (1–120 chars).",
      errFieldId: "Field ID is required (1–64 chars).",
      errFieldName: "Field name is required (1–120 chars).",
      errCropMissing: (row) => `Row ${row}: pick a catalog crop or enter a custom crop name.`,
      errAreaPositive: "Area must be greater than 0 and at most 10,000 hectares.",
      errWaterOtherRequired: "Describe the other water source or pick a listed option.",
    },

    editFarmModal: {
      title: "Edit Farm Details",
      subtitle: "Update farm name or commune across Wilaya of Guelma.",
      saveBtn: "Update Farm",
    },

    confirmDelete: {
      fieldTitle: "Remove Mapped Field?",
      fieldBody: (name) =>
        `Are you sure you want to remove "${name}" from your dashboard? Its drawn boundary and history record will be deleted.`,
      farmTitle: "Remove Entire Farm?",
      farmBody: (name, count) =>
        `Removing "${name}" will permanently delete the farm and ${count} mapped field${count === 1 ? "" : "s"}.`,
      confirmRemoveBtn: "Yes, Remove",
      cancelBtn: "Keep It",
    },
    descendingToParcel: " · Descending to parcel...",
    closedTag: "(closed)",
    clearSearchAria: "Clear search",
    closeCommuneAria: "Close commune menu",
    verticesSummaryTitle: (count, perimM) => `${count} vertices · ${perimM} m perimeter`,
    customCropOption: "— Custom Crop Name —",
    parcelDefaultSuffix: "Parcel",
  },

  fr: {
    brandTag: "Wilaya de Guelma · 34 Communes",
    provinceBadge: "Wilaya 24 · Guelma",
    dashboardTitle: "Tableau de Bord Agricole de Guelma",
    dashboardSubtitle:
      "Enregistrez vos exploitations dans les 34 communes de Guelma, tracez les limites exactes sur imagerie satellite et simulez vos rotations.",
    addFarmBtn: "Ajouter une ferme ou parcelle",
    addFieldBtn: "Ajouter une parcelle",
    loadSamplesBtn: "Charger les parcelles exemples",
    clearWorkspaceBtn: "Réinitialiser",
    emptyTitle: "Aucune ferme ni parcelle enregistrée",
    emptyDesc:
      "Ouvrez la carte satellite interactive de Guelma pour tracer les contours de votre champ, mesurer sa surface exacte et renseigner vos données.",
    emptyStep1: "Tracez la parcelle dans n'importe laquelle des 34 communes",
    emptyStep2: "Cliquez Sauvegarder Ma Ferme puis complétez Sol, Eau & Historique",
    emptyStep3: "Analysez NDVI, humidité racinaire, relief 3D et rotations",
    kpiFarms: "Fermes Enregistrées",
    kpiFields: "Parcelles Cartographiées",
    kpiArea: "Surface Totale",
    kpiCommunes: "Communes de Guelma",
    overviewMapTitle: "Carte des Exploitations · Wilaya de Guelma",
    overviewMapSub: "Cliquez sur une parcelle pour lancer la simulation agronomique",
    farmsListTitle: "Mes Fermes et Parcelles",
    communeBadge: "Commune",
    fieldsSuffix: "parcelles",
    inspectBtn: "Inspecter & Simuler",
    editBordersBtn: "Modifier Contours",
    editInfoBtn: "Modifier Infos",
    removeFieldBtn: "Supprimer",
    editFarmBtn: "Modifier Ferme",
    removeFarmBtn: "Supprimer Ferme",
    soilFarmerKnown: "Sol Renseigné",
    soilUnknownTag: "Sol Non Vérifié",
    elevNotProvided: "Altitude non saisie",
    cropHistoryCount: (n) => `${n} saison${n > 1 ? "s" : ""} déclarée${n > 1 ? "s" : ""}`,

    editor: {
      newFieldTitle: "Tracer les Limites · Wilaya de Guelma",
      editBordersTitle: "Ajuster le Contour · Précision CAD",
      subtitle:
        "Recherchez l'une des 34 communes, placez les sommets du champ, ajustez les poignées puis cliquez Sauvegarder Ma Ferme.",
      searchCommune: "Aller à une commune (ex. Bouchegouf, Oued Zenati, Guelma)…",
      allCommunesLabel: (n) => `${n} communes à Guelma`,
      quickPresetLabel: "Parcelles Démo",
      layersLabel: "Couches Satellite",
      view2d: "Ortho 2D",
      view3d: "Relief 3D",
      undo: "Annuler",
      redo: "Rétablir",
      clear: "Effacer",
      closePoly: "Fermer Polygone",
      backDashboard: "Retour au Tableau de Bord",
      saveMyFarm: "Sauvegarder Ma Ferme →",
      saveUpdatedBorders: "Appliquer le Contour →",
      verticesLbl: "Sommets",
      areaLbl: "Surface Géodésique",
      perimLbl: "Périmètre",
      centroidLbl: "Centre",
      demRefLbl: "Réf. Altitude MNT",
      demNonBindingNote: "Informatif uniquement — profil agriculteur indépendant",
      communeDetectedLbl: "Commune Proche",
      statusInsideGuelma: "Dans la Wilaya de Guelma",
      statusOutsideGuelma: "Hors limites de Guelma",
      statusNeedVertices: "Placez au moins 3 sommets sur la parcelle",
      statusSelfIntersect: "Segments croisés — corrigez les sommets",
      statusReady: "Polygone fermé prêt à enregistrer",
      hintAddVertex: "Cliquez sur l'image satellite pour placer les coins du champ.",
      hintSnapClose: "Placez >=3 coins puis cliquez sur le premier point vert.",
      hintAdjustVertices: "Déplacez les coins ou cliquez + sur les côtés pour affiner.",
      deleteSelectedVertex: "Supprimer Sommet",
      svgFallbackNotice: "Grille Satellite SVG Précision Active",
    },

    form: {
      createTitle: "Informations Ferme & Parcelle",
      editFieldTitle: "Modifier les Informations de la Parcelle",
      subtitle:
        "Conforme à l'architecture FELLAH TECH (ENDPOINTS v3.2 · ADR-3 · ADR-5) pour la Wilaya de Guelma.",
      farmSection: "1. Identité & Localisation de la Ferme",
      targetModeNew: "Nouvelle Ferme",
      targetModeExisting: "Ferme Existante",
      chooseFarmLabel: "Choisir la Ferme",
      farmNameLabel: "Nom de l'Exploitation",
      farmNamePlaceholder: "ex. Domaine Seybouse Nord",
      countryLabel: "Pays",
      regionLabel: "Wilaya / Région",
      communeLabel: "Commune (Wilaya de Guelma)",
      communeAutoHint: "Détectée depuis le contour tracé",
      fieldSection: "2. Paramètres de la Parcelle",
      fieldIdLabel: "Code / ID Parcelle",
      fieldNameLabel: "Nom de la Parcelle",
      fieldNamePlaceholder: "ex. Parcelle Blé Dur A1",
      areaLabel: "Surface (Hectares)",
      areaAutoTag: "Calculée depuis les contours",
      elevLabel: "Altitude (m · optionnel)",
      elevOptionalPlaceholder: "Laisser vide si non mesuré",
      elevAdrNote: "ADR-5 : Laisser vide si inconnu — jamais rempli de force par le MNT.",
      soilSection: "3. Profil Pédologique (ADR-5)",
      soilModeUnknown: "Sol Inconnu / Base Régionale",
      soilModeKnown: "Sol Connu / Analyse Labo",
      soilTypeLabel: "Texture USDA",
      usdaCalcBtn: "Calculateur Argile/Limon/Sable",
      soilPhLabel: "pH du Sol (3–11)",
      soilOmLabel: "Matière Organique (%)",
      soilDateLabel: "Date d'Analyse",
      waterSection: "4. Eau & Irrigation",
      waterAvailLabel: "Disponibilité en Eau",
      waterSourceLabel: "Source d'Eau",
      waterSourceOtherLabel: "Préciser la Source",
      irrigationLabel: "Système d'Irrigation",
      historySection: "5. Historique Cultural (1–30 saisons)",
      historySubtitle: "Au moins 1 saison passée ou actuelle est requise pour l'analyse.",
      addHistoryBtn: "+ Ajouter une Saison",
      removeRowLabel: "Supprimer ligne",
      seasonLabel: "Saison",
      yearLabel: "Année",
      monthLabel: "Mois de Semis",
      monthAutoOption: "Non spécifié",
      catalogCropLabel: "Culture du Catalogue",
      customCropLabel: "Nom Local / Personnalisé",
      customCropPlaceholder: "ex. Blé Dur Vitron",
      yieldLabel: "Rendement (t/ha)",
      notesLabel: "Notes Privées",
      notesPrivateTag: "Confidentiel — exclu des résumés publics",
      cancelBtn: "Annuler",
      saveFarmFieldBtn: "Enregistrer au Tableau de Bord",
      updateFieldBtn: "Enregistrer Modifications",
      errFarmName: "Nom de ferme requis (1–120 caractères).",
      errFieldId: "Identifiant de parcelle requis (1–64 car.).",
      errFieldName: "Nom de parcelle requis (1–120 car.).",
      errCropMissing: (row) => `Ligne ${row} : choisissez une culture ou saisissez un nom.`,
      errAreaPositive: "La surface doit être > 0 et <= 10 000 ha.",
      errWaterOtherRequired: "Précisez la source d'eau ou choisissez une option.",
    },

    editFarmModal: {
      title: "Modifier l'Exploitation",
      subtitle: "Mettre à jour le nom ou la commune dans la Wilaya de Guelma.",
      saveBtn: "Mettre à Jour",
    },

    confirmDelete: {
      fieldTitle: "Supprimer cette Parcelle ?",
      fieldBody: (name) =>
        `Confirmez-vous la suppression de « ${name} » ? Son contour et son historique seront effacés.`,
      farmTitle: "Supprimer toute la Ferme ?",
      farmBody: (name, count) =>
        `Supprimer « ${name} » effacera également ses ${count} parcelle${count > 1 ? "s" : ""}.`,
      confirmRemoveBtn: "Oui, Supprimer",
      cancelBtn: "Conserver",
    },
    descendingToParcel: " · Descente sur la parcelle...",
    closedTag: "(fermé)",
    clearSearchAria: "Effacer la recherche",
    closeCommuneAria: "Fermer le menu des communes",
    verticesSummaryTitle: (count, perimM) => `${count} sommets · périmètre de ${perimM} m`,
    customCropOption: "— Nom de culture personnalisé —",
    parcelDefaultSuffix: "Parcelle",
  },

  ar: {
    brandTag: "ولاية قالمة · 34 بلدية",
    provinceBadge: "الولاية 24 · قالمة",
    dashboardTitle: "لوحة قيادة المزارع والأراضي — ولاية قالمة",
    dashboardSubtitle:
      "سجّل مزارعك عبر كافة بلديات ولاية قالمة الـ34، ارسم حدود حقولك بدقة على صور الأقمار الصناعية، وخطط للتناوب الزراعي المستدام.",
    addFarmBtn: "إضافة مزرعة أو قطعة",
    addFieldBtn: "إضافة قطعة للمزرعة",
    loadSamplesBtn: "تحميل قطع نموذجية من قالمة",
    clearWorkspaceBtn: "إعادة ضبط المساحة",
    emptyTitle: "لا توجد مزارع أو قطع مسجلة بعد",
    emptyDesc:
      "ابدأ بفتح خريطة الأقمار الصناعية التفاعلية لولاية قالمة لتحديد حدود حقلك بدقة، حساب المساحة بالهكتار، وإدخال بيانات المزرعة.",
    emptyStep1: "حدّد حدود القطعة عبر أي من بلديات قالمة الـ 34",
    emptyStep2: "اضغط «حفظ مزرعتي» وأدخل معلومات التربة والمياه والمحاصيل",
    emptyStep3: "راقب الغطاء النباتي NDVI، رطوبة التربة، التضاريس 3D وخطط التناوب",
    kpiFarms: "المزارع المسجلة",
    kpiFields: "القطع المرسومة",
    kpiArea: "المساحة الإجمالية",
    kpiCommunes: "بلديات قالمة المغطاة",
    overviewMapTitle: "خريطة الأراضي المسجلة · ولاية قالمة",
    overviewMapSub: "انقر على أي قطعة لفتح الفحص والمحاكاة الزراعية",
    farmsListTitle: "مزارعي وقطعي الفلاحية",
    communeBadge: "البلدية",
    fieldsSuffix: "قطع",
    inspectBtn: "فحص ومحاكاة",
    editBordersBtn: "تعديل الحدود",
    editInfoBtn: "تعديل المعلومات",
    removeFieldBtn: "حذف",
    editFarmBtn: "تعديل المزرعة",
    removeFarmBtn: "حذف المزرعة",
    soilFarmerKnown: "بيانات تربة مدخلة",
    soilUnknownTag: "تربة غير مفحوصة",
    elevNotProvided: "الارتفاع غير محدد",
    cropHistoryCount: (n) => `${n} موسم مسجل`,

    editor: {
      newFieldTitle: "رسم حدود المزرعة · ولاية قالمة",
      editBordersTitle: "تعديل حدود القطعة بدقة",
      subtitle:
        "انقر على خريطة القمر الصناعي لوضع رؤوس الحدود، واسحب النقاط لتعديل الشكل بدقة وحساب المساحة تلقائياً.",
      searchCommune: "انتقل إلى بلدية (مثل: بوشقوف، وادي الزناتي، قالمة)…",
      allCommunesLabel: (n) => `${n} بلدية في قالمة`,
      quickPresetLabel: "نماذج سريعة",
      layersLabel: "طبقات الأقمار الصناعية",
      view2d: "عمودي 2D",
      view3d: "تضاريس 3D",
      undo: "تراجع",
      redo: "إعادة",
      clear: "مسح الكل",
      closePoly: "إغلاق الشكل",
      backDashboard: "العودة إلى لوحة التحكم",
      saveMyFarm: "حفظ مزرعتي",
      saveUpdatedBorders: "حفظ الحدود المعدلة",
      verticesLbl: "الزوايا",
      areaLbl: "المساحة الجيوديسية",
      perimLbl: "المحيط",
      centroidLbl: "المركز",
      demRefLbl: "مرجع التضاريس DEM",
      demNonBindingNote: "مرجعي فقط — لا يُلزم ملف التربة أو الارتفاع",
      communeDetectedLbl: "أقرب بلدية",
      statusInsideGuelma: "داخل حدود ولاية قالمة",
      statusOutsideGuelma: "خارج حدود ولاية قالمة",
      statusNeedVertices: "ضع 3 زوايا على الأقل لتشكيل الحقل",
      statusSelfIntersect: "الحدود متقاطعة — عدّل النقاط لفك التقاطع",
      statusReady: "الحدود مغلقة وجاهزة للحفظ",
      hintAddVertex: "انقر على خريطة الأقمار الصناعية لإضافة زوايا القطعة.",
      hintSnapClose: "ضع 3 نقاط أو أكثر ثم انقر أول نقطة خضراء للإغلاق.",
      hintAdjustVertices: "اسحب الزوايا للتعديل أو انقر (+) على الأضلاع لإضافة نقطة.",
      deleteSelectedVertex: "حذف الزاوية المحددة",
      svgFallbackNotice: "شبكة التحديد الدقيقة نشطة",
    },

    form: {
      createTitle: "أكمل معلومات المزرعة والقطعة",
      editFieldTitle: "تعديل المعلومات الفلاحية للقطعة",
      subtitle:
        "متوافق مع تصميم النظام وواجهة البرمجة (ENDPOINTS v3.2 · ADR-3 · ADR-5) لولاية قالمة.",
      farmSection: "1. هوية وموقع المزرعة",
      targetModeNew: "إنشاء مزرعة جديدة",
      targetModeExisting: "إضافة لمزرعة حالية",
      chooseFarmLabel: "اختر المزرعة",
      farmNameLabel: "اسم المزرعة / المستثمرة",
      farmNamePlaceholder: "مثال: مزرعة سيبوس الشمالية",
      countryLabel: "الدولة",
      regionLabel: "الولاية",
      communeLabel: "البلدية (ولاية قالمة)",
      communeAutoHint: "مقترحة تلقائياً من إحداثيات الحقل",
      fieldSection: "2. بيانات القطعة المرسومة",
      fieldIdLabel: "رمز القطعة (ID)",
      fieldNameLabel: "اسم القطعة",
      fieldNamePlaceholder: "مثال: قطعة قمح صلب A1",
      areaLabel: "المساحة (هكتار)",
      areaAutoTag: "محسوبة تلقائياً من الحدود",
      elevLabel: "الارتفاع عن البحر (م · اختياري)",
      elevOptionalPlaceholder: "اتركه فارغاً إن لم يكن معروفاً",
      elevAdrNote: "ADR-5: لا يُملأ قسراً من الأقمار دون تأكيد الفلاح.",
      soilSection: "3. خصائص التربة (ADR-5)",
      soilModeUnknown: "التربة غير محددة / مرجع جهوي",
      soilModeKnown: "لدي بيانات التربة / تحليل مخبري",
      soilTypeLabel: "قوام التربة (USDA)",
      usdaCalcBtn: "حاسبة الطين والطمي والرمل",
      soilPhLabel: "حموضة التربة pH (3–11)",
      soilOmLabel: "المادة العضوية (%)",
      soilDateLabel: "تاريخ التحليل",
      waterSection: "4. الموارد المائية والسقي",
      waterAvailLabel: "وفرة المياه",
      waterSourceLabel: "مصدر المياه",
      waterSourceOtherLabel: "تحديد المصدر الآخر",
      irrigationLabel: "نظام السقي",
      historySection: "5. سجل المحاصيل السابق (1–30 موسم)",
      historySubtitle: "مطلوب موسم واحد على الأقل لتشغيل تخطيط التناوب الزراعي.",
      addHistoryBtn: "+ إضافة موسم",
      removeRowLabel: "حذف السطر",
      seasonLabel: "الموسم",
      yearLabel: "السنة",
      monthLabel: "شهر الزراعة",
      monthAutoOption: "غير محدد",
      catalogCropLabel: "المحصول من القائمة",
      customCropLabel: "أو اسم محلي مخصص",
      customCropPlaceholder: "مثال: قمح واهبي / فليو",
      yieldLabel: "المردود (طن/هكتار)",
      notesLabel: "ملاحظات خاصة بالفلاح",
      notesPrivateTag: "خاصة — لا تُنشر في الملخصات",
      cancelBtn: "إلغاء",
      saveFarmFieldBtn: "حفظ المزرعة والقطعة في اللوحة",
      updateFieldBtn: "حفظ التعديلات",
      errFarmName: "اسم المزرعة مطلوب (1–120 حرفاً).",
      errFieldId: "رمز القطعة مطلوب (1–64 حرفاً).",
      errFieldName: "اسم القطعة مطلوب (1–120 حرفاً).",
      errCropMissing: (row) => `السطر ${row}: اختر محصولاً من القائمة أو اكتب اسماً مخصصاً.`,
      errAreaPositive: "يجب أن تكون المساحة أكبر من 0 وأقل من 10,000 هكتار.",
      errWaterOtherRequired: "يرجى توضيح مصدر المياه الآخر أو اختيار مصدر محدد.",
    },

    editFarmModal: {
      title: "تعديل بيانات المزرعة",
      subtitle: "تحديث اسم المزرعة أو البلدية داخل ولاية قالمة.",
      saveBtn: "تحديث المزرعة",
    },

    confirmDelete: {
      fieldTitle: "حذف هذه القطعة؟",
      fieldBody: (name) =>
        `هل أنت متأكد من حذف «${name}» من لوحة القيادة؟ سيتم حذف الحدود والسجل المرتبط بها.`,
      farmTitle: "حذف المزرعة بالكامل؟",
      farmBody: (name, count) =>
        `حذف «${name}» سيؤدي إلى حذف المزرعة مع جميع القطع المرتبطة بها (${count}).`,
      confirmRemoveBtn: "نعم، احذف",
      cancelBtn: "إبقاء",
    },
    descendingToParcel: " · جاري الانتقال إلى القطعة...",
    closedTag: "(مغلق)",
    clearSearchAria: "مسح البحث",
    closeCommuneAria: "إغلاق قائمة البلديات",
    verticesSummaryTitle: (count, perimM) => `${count} رؤوس · محيط ${perimM} م`,
    customCropOption: "— اسم محصول مخصص —",
    parcelDefaultSuffix: "قطعة",
  },
};

