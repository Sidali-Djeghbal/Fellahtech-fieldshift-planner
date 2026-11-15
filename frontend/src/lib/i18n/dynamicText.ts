import { resolveCropDisplayName } from "@/lib/analysis/workspaceAnalysis";
import { localizeCommuneName } from "@/lib/geo/guelma";
import {
  IRRIGATION_SYSTEM_LABELS,
  SEASON_LABELS,
  SOIL_TYPE_LABELS,
  WATER_AVAILABILITY_LABELS,
  WATER_SOURCE_LABELS,
} from "@/lib/i18n";
import type {
  IrrigationSystem,
  Language,
  Season,
  SoilType,
  WaterAvailability,
  WaterSource,
} from "@/lib/schemas";

type Tri = { en: string; fr: string; ar: string };

const EXACT_PHRASE_MAP: Record<string, Tri> = {
  // Farm & Field Names
  "Ferme Guelma Demo": {
    en: "Guelma Demo Farm",
    fr: "Ferme Démo de Guelma",
    ar: "مزرعة قالمة التجريبية",
  },
  "Guelma Farm": {
    en: "Guelma Farm",
    fr: "Ferme de Guelma",
    ar: "مزرعة قالمة",
  },
  "Exploitation Pilote Seybouse · Guelma": {
    en: "Seybouse Pilot Farm · Guelma",
    fr: "Exploitation Pilote Seybouse · Guelma",
    ar: "مستثمرة سيبوس النموذجية · قالمة",
  },
  "Seybouse Pilot Farm · Guelma": {
    en: "Seybouse Pilot Farm · Guelma",
    fr: "Exploitation Pilote Seybouse · Guelma",
    ar: "مستثمرة سيبوس النموذجية · قالمة",
  },
  "Guelma Team Demo Parcel (Unstudied)": {
    en: "Guelma Team Demo Parcel (Unstudied)",
    fr: "Parcelle Démo Équipe Guelma (Non étudiée)",
    ar: "القطعة التجريبية لفريق قالمة (غير مفحوصة)",
  },
  "Parcelle Seybouse": {
    en: "Seybouse Parcel",
    fr: "Parcelle Seybouse",
    ar: "قطعة سيبوس",
  },
  "Seybouse Alluvial Plain": {
    en: "Seybouse Alluvial Plain",
    fr: "Plaine alluviale de la Seybouse",
    ar: "سهل سيبوس الرسوبي",
  },
  "Plaine alluviale de la Seybouse": {
    en: "Seybouse Alluvial Plain",
    fr: "Plaine alluviale de la Seybouse",
    ar: "سهل سيبوس الرسوبي",
  },
  "Heliopolis Hillside": {
    en: "Heliopolis Hillside",
    fr: "Coteau d'Héliopolis",
    ar: "مرتفعات هيليوبوليس",
  },
  "Coteau d'Héliopolis": {
    en: "Heliopolis Hillside",
    fr: "Coteau d'Héliopolis",
    ar: "مرتفعات هيليوبوليس",
  },
  "Bouchegouf Valley": {
    en: "Bouchegouf Valley",
    fr: "Vallée de Bouchegouf",
    ar: "وادي بوشقوف",
  },
  "Vallée de Bouchegouf": {
    en: "Bouchegouf Valley",
    fr: "Vallée de Bouchegouf",
    ar: "وادي بوشقوف",
  },
  "Oued Zenati Slope": {
    en: "Oued Zenati Slope",
    fr: "Versant d'Oued Zenati",
    ar: "منحدر وادي الزناتي",
  },
  "Versant d'Oued Zenati": {
    en: "Oued Zenati Slope",
    fr: "Versant d'Oued Zenati",
    ar: "منحدر وادي الزناتي",
  },
  "Bouhamdane Dam Basin": {
    en: "Bouhamdane Dam Basin",
    fr: "Bassin du barrage Bouhamdane",
    ar: "حوض سد بوحمدان",
  },
  "Bassin du barrage Bouhamdane": {
    en: "Bouhamdane Dam Basin",
    fr: "Bassin du barrage Bouhamdane",
    ar: "حوض سد بوحمدان",
  },
  "Tamlouka High Plain": {
    en: "Tamlouka High Plain",
    fr: "Haute Plaine de Tamlouka",
    ar: "الهضبة العليا تاملوكة",
  },

  // Executive Summaries & Disclaimers
  "Rotating spring chickpea and forage vetch into cereal-dominated parcel F1 reduces multi-year moisture depletion and breaks cereal disease cycles.": {
    en: "Rotating spring chickpea and forage vetch into cereal-dominated parcel F1 reduces multi-year moisture depletion and breaks cereal disease cycles.",
    fr: "L'alternance du pois chiche de printemps et de la vesce fourragère sur la parcelle F1 dominée par les céréales limite l'épuisement hydrique pluriannuel et coupe les cycles pathogènes.",
    ar: "يُسهم إدماج الحمص الربيعي والبيقية العلفية في القطعة F1 المهيمن عليها بالحبوب في تقليل استنزاف الرطوبة على مدى المواسم وكسر دورات أمراض الحبوب.",
  },
  "Recommendations depend on the unverified demo parcel inputs supplied and dataset_version 2026.11-guelma-v1; verify soil chemistry locally prior to planting.": {
    en: "Recommendations depend on the unverified demo parcel inputs supplied and dataset_version 2026.11-guelma-v1; verify soil chemistry locally prior to planting.",
    fr: "Ces recommandations reposent sur les données non vérifiées de la parcelle témoin et sur le jeu de données 2026.11-guelma-v1 ; confirmez les analyses de sol avant le semis.",
    ar: "تعتمد هذه التوصيات على معطيات القطعة التجريبية غير المفحوصة وإصدار البيانات 2026.11-guelma-v1؛ يرجى التحقق من خصائص التربة ميدانياً قبل الزراعة.",
  },

  // Field Insights
  "Dataset zone 2026.11-guelma-v1 indicates recurring dry summer months with moderate spring variability.": {
    en: "Dataset zone 2026.11-guelma-v1 indicates recurring dry summer months with moderate spring variability.",
    fr: "La zone climatique 2026.11-guelma-v1 montre des étés régulièrement secs avec une variabilité printanière modérée.",
    ar: "تشير بيانات المنطقة 2026.11-guelma-v1 إلى أشهر صيف جافة متكررة مع تذبذب معتدل في أمطار الربيع.",
  },
  "Summer fallow gap observed between cereal harvests.": {
    en: "Summer fallow gap observed between cereal harvests.",
    fr: "Période de sol nu estival observée entre deux récoltes céréalières.",
    ar: "تم رصد فترة بور صيفية تبقى فيها التربة مكشوفة بين مواسم حصاد الحبوب.",
  },
  "Seasonal water deficit pattern in local dataset for zone F1.": {
    en: "Seasonal water deficit pattern in local dataset for zone F1.",
    fr: "Schéma saisonnier de déficit hydrique relevé dans les données locales pour la zone F1.",
    ar: "نمط عجز مائي موسمي مرصود في قاعدة البيانات المحلية لنطاق القطعة F1.",
  },

  // Strategy Names
  "Existing Cereal Baseline": {
    en: "Existing Cereal Baseline",
    fr: "Référence Céréalière Actuelle",
    ar: "المرجع الحالي لزراعة الحبوب",
  },
  "Chickpea & Drip Forage Balanced Rotation": {
    en: "Chickpea & Drip Forage Balanced Rotation",
    fr: "Rotation Équilibrée Pois Chiche & Fourrage Goutte-à-Goutte",
    ar: "التناوب المتوازن: الحمص والأعلاف بالتنقيط",
  },
  "Market Cereal & Legume Cash Focus": {
    en: "Market Cereal & Legume Cash Focus",
    fr: "Rotation Orientée Marché Céréales & Légumineuses",
    ar: "تناوب نقدي يركّز على الحبوب والبقوليات التسويقية",
  },
  "Balanced Water & Soil Rotation": {
    en: "Balanced Water & Soil Rotation",
    fr: "Rotation Équilibrée Eau & Sol",
    ar: "التناوب المتوازن للماء والتربة",
  },
  "Soil Recovery Rotation": {
    en: "Soil Recovery Rotation",
    fr: "Rotation Régénératrice des Sols",
    ar: "تناوب استعادة خصوبة التربة",
  },
  "Water-Resilient Rotation": {
    en: "Water-Resilient Rotation",
    fr: "Rotation Résiliente au Stress Hydrique",
    ar: "تناوب مقاوم لشح المياه",
  },
  "Market Cereal-Legume Mix": {
    en: "Market Cereal-Legume Mix",
    fr: "Combinaison Marché Céréales-Légumineuses",
    ar: "مزيج الحبوب والبقوليات الموجه للسوق",
  },

  // Strategy Descriptions
  "Continues historical autumn cereal dominance as the comparison baseline.": {
    en: "Continues historical autumn cereal dominance as the comparison baseline.",
    fr: "Maintient l'historique dominant de céréales d'automne comme référence de comparaison.",
    ar: "يواصل النمط التقليدي المعتمد على الحبوب الخريفية كمرجع أساسي للمقارنة.",
  },
  "Introduces nitrogen-fixing chickpea and conserved forage vetch alongside durum wheat.": {
    en: "Introduces nitrogen-fixing chickpea and conserved forage vetch alongside durum wheat.",
    fr: "Introduit le pois chiche fixateur d'azote et la vesce fourragère avec le blé dur.",
    ar: "يُدخل الحمص المثبت للآزوت والبيقية العلفية المحافظة على الرطوبة بالتناوب مع القمح الصلب.",
  },
  "Prioritizes market revenue with alternating durum wheat and chickpea cycles.": {
    en: "Prioritizes market revenue with alternating durum wheat and chickpea cycles.",
    fr: "Privilégie le revenu commercial en alternant blé dur et pois chiche.",
    ar: "يعطي الأولوية للعائد التسويقي عبر تعاقب دورات القمح الصلب والحمص.",
  },

  // Reasons
  "Reflects prior autumn wheat/barley cropping history.": {
    en: "Reflects prior autumn wheat/barley cropping history.",
    fr: "Reflète l'historique précédent en blé et orge d'automne.",
    ar: "يعكس السجل الزراعي السابق المعتمد على القمح والشعير الخريفي.",
  },
  "Includes farmer requested crop chickpea in season 1.": {
    en: "Includes farmer requested crop chickpea in season 1.",
    fr: "Intègre dès la saison 1 la culture demandée par l'agriculteur : pois chiche.",
    ar: "يدمج المحصول المطلوب من الفلاح (الحمص) بدايةً من المرحلة الأولى.",
  },
  "Balances pulse and oilseed break crops around cash wheat.": {
    en: "Balances pulse and oilseed break crops around cash wheat.",
    fr: "Équilibre légumineuses et cultures de rupture autour du blé de vente.",
    ar: "يوازن بين البقوليات والمحاصيل الكاسرة للدورات حول محصول القمح النقدي.",
  },

  // Evidence Interpretations
  "Farmer-reported moderate well availability with drip irrigation.": {
    en: "Farmer-reported moderate well availability with drip irrigation.",
    fr: "Disponibilité modérée du puits avec irrigation goutte-à-goutte déclarée par l'agriculteur.",
    ar: "وفرة متوسطة لمياه البئر مع سقي بالتنقيط وفق تصريح الفلاح.",
  },
  "Mean annual dataset precipitation aligns with spring chickpea establishment.": {
    en: "Mean annual dataset precipitation aligns with spring chickpea establishment.",
    fr: "Les précipitations annuelles moyennes du jeu de données conviennent à l'implantation du pois chiche de printemps.",
    ar: "يتوافق متوسط التساقطات السنوية في المنطقة مع متطلبات نمو الحمص الربيعي.",
  },
  "Drier years favor drought-tolerant legumes over fallow cereals.": {
    en: "Drier years favor drought-tolerant legumes over fallow cereals.",
    fr: "Les années sèches favorisent les légumineuses tolérantes plutôt que les céréales après jachère.",
    ar: "في السنوات الجافة تتفوق البقوليات المقاومة للجفاف مقارنة بتكرار الحبوب والبور.",
  },
  "Moderate well irrigation supports spring oilseed establishment.": {
    en: "Moderate well irrigation supports spring oilseed establishment.",
    fr: "L'irrigation modérée par puits soutient le démarrage des cultures de printemps.",
    ar: "يدعم السقي المعتدل من البئر نجاح الزراعة الربيعية.",
  },
  "Farmer lab soil pH measurement guides legume nodulation fit.": {
    en: "Farmer lab soil pH measurement guides legume nodulation fit.",
    fr: "L'analyse de pH du sol oriente l'aptitude à la nodulation des légumineuses.",
    ar: "يوجّه قياس حموضة التربة (pH) المخبري ملاءمة تكوين العقد الجذرية للبقوليات.",
  },
  "Farmer-provided parcel elevation.": {
    en: "Farmer-provided parcel elevation.",
    fr: "Altitude de parcelle renseignée par l'agriculteur.",
    ar: "ارتفاع القطعة المُدخل مباشرة من طرف الفلاح.",
  },

  // Benefits
  "Familiar machinery workflow": {
    en: "Familiar machinery workflow",
    fr: "Itinéraire mécanisé habituel",
    ar: "مسار عمل مألوف بالآلات الحالية",
  },
  "Requires no immediate equipment change.": {
    en: "Requires no immediate equipment change.",
    fr: "Ne nécessite aucun changement d'équipement immédiat.",
    ar: "لا يتطلب أي تغيير فوري في المعدات الفلاحية.",
  },
  "Biological nitrogen fixation": {
    en: "Biological nitrogen fixation",
    fr: "Fixation biologique de l'azote",
    ar: "تثبيت الآزوت البيولوجي",
  },
  "Spring chickpea lowers synthetic nitrogen demand for autumn wheat.": {
    en: "Spring chickpea lowers synthetic nitrogen demand for autumn wheat.",
    fr: "Le pois chiche de printemps réduit les besoins en azote de synthèse du blé d'automne suivant.",
    ar: "يقلّص الحمص الربيعي الحاجة للأسمدة الآزوتية الكيميائية للقمح الخريفي الموالي.",
  },
  "High gross revenue potential": {
    en: "High gross revenue potential",
    fr: "Fort potentiel de revenu brut",
    ar: "مردود مالي إجمالي مرتفع",
  },
  "Maximize marketed crop share across 4 seasons.": {
    en: "Maximize marketed crop share across 4 seasons.",
    fr: "Maximise la part des cultures commercialisées sur les 4 saisons.",
    ar: "يعظّم حصة المحاصيل التسويقية الموجهة للبيع على مدى 4 مواسم.",
  },

  // Risks & Mitigations
  "Cereal monoculture pathogen carryover": {
    en: "Cereal monoculture pathogen carryover",
    fr: "Maintien des pathogènes en monoculture céréalière",
    ar: "تراكم مسببات أمراض الحبوب الأحادية",
  },
  "Consecutive cereals increase root disease pressure.": {
    en: "Consecutive cereals increase root disease pressure.",
    fr: "Les céréales successives aggravent la pression des maladies racinaires.",
    ar: "تكرار زراعة الحبوب يزيد ضغط الأمراض الفطرية والجذرية.",
  },
  "Introduce a legume break crop.": {
    en: "Introduce a legume break crop.",
    fr: "Introduire une légumineuse de coupure.",
    ar: "إدخال محصول بقولي لكسر دورة الآفات.",
  },
  "Soil chemistry uncertainty": {
    en: "Soil chemistry uncertainty",
    fr: "Incertitude sur la chimie du sol",
    ar: "عدم يقين في الخصائص الكيميائية للتربة",
  },
  "Unstudied parcel soil pH could affect legume nodulation.": {
    en: "Unstudied parcel soil pH could affect legume nodulation.",
    fr: "Un pH du sol non mesuré peut influencer la nodulation des légumineuses.",
    ar: "قد يؤثر عدم معرفة حموضة التربة (pH) في القطعة غير المدروسة على كفاءة تثبيت الآزوت.",
  },
  "Collect topsoil lab sample before spring sowing.": {
    en: "Collect topsoil lab sample before spring sowing.",
    fr: "Prélever un échantillon de sol superficiel pour analyse avant le semis de printemps.",
    ar: "أخذ عينة من التربة السطحية للتحليل المخبري قبل البذر الربيعي.",
  },
  "Higher irrigation demand in summer": {
    en: "Higher irrigation demand in summer",
    fr: "Demande en irrigation plus élevée en été",
    ar: "ارتفاع الحاجة إلى السقي صيفاً",
  },
  "Oilseed phase demands reliable mid-season watering.": {
    en: "Oilseed phase demands reliable mid-season watering.",
    fr: "La phase estivale exige un arrosage fiable en milieu de cycle.",
    ar: "تتطلب هذه المرحلة سقياً منتظماً وموثوقاً في منتصف الموسم.",
  },
  "Schedule drip irrigation during flowering.": {
    en: "Schedule drip irrigation during flowering.",
    fr: "Planifier le goutte-à-goutte durant la floraison.",
    ar: "برمجة السقي بالتنقيط بانتظام خلال مرحلة الإزهار.",
  },

  // Assumptions, Information Gaps & Local Review
  "Parcel F1 field parameters remain unstudied until surveyed.": {
    en: "Parcel F1 field parameters remain unstudied until surveyed.",
    fr: "Les paramètres pédologiques de la parcelle F1 restent non étudiés tant qu'un relevé n'est pas effectué.",
    ar: "تظل خصائص القطعة F1 غير مدروسة ميدانياً إلى غاية إجراء الفحص الحقلي.",
  },
  "Missing laboratory soil pH and organic matter measurements.": {
    en: "Missing laboratory soil pH and organic matter measurements.",
    fr: "Mesures de laboratoire manquantes pour le pH et la matière organique.",
    ar: "قياسات المختبر لحموضة التربة pH والمادة العضوية غير متوفرة حالياً.",
  },
  "Verify soil texture and organic matter on parcel F1.": {
    en: "Verify soil texture and organic matter on parcel F1.",
    fr: "Vérifier la texture et la matière organique sur la parcelle F1.",
    ar: "التحقق ميدانياً من قوام التربة ونسبة المادة العضوية في القطعة F1.",
  },
  "Drip irrigation system remains operational for supplemental spring moisture.": {
    en: "Drip irrigation system remains operational for supplemental spring moisture.",
    fr: "Le système goutte-à-goutte reste opérationnel pour l'appoint hydrique printanier.",
    ar: "بقاء شبكة السقي بالتنقيط جاهزة لتوفير السقي التكميلي في الربيع.",
  },
  "Parcel F1 awaits physical soil sampling (`is_unverified_demo_parcel: true`).": {
    en: "Parcel F1 awaits physical soil sampling (unverified demo parcel).",
    fr: "La parcelle F1 attend un prélèvement physique de sol (parcelle témoin non vérifiée).",
    ar: "تنتظر القطعة F1 أخذ عينات تربة ميدانية (قطعة تجريبية غير مفحوصة).",
  },
  "Confirm chickpea seed variety suitability with local extension service.": {
    en: "Confirm chickpea seed variety suitability with local extension service.",
    fr: "Valider le choix variétal de pois chiche auprès de la vulgarisation agricole locale.",
    ar: "التأكد من ملاءمة صنف بذور الحمص محلياً بالتنسيق مع مصالح الإرشاد الفلاحي.",
  },
  "No soil salinity issues on unstudied parcel F1.": {
    en: "No soil salinity issues on unstudied parcel F1.",
    fr: "Absence supposée de salinité excessive sur la parcelle F1 non étudiée.",
    ar: "افتراض خلو التربة من مشكلات الملوحة العالية في القطعة F1.",
  },
  "Exact well summer yield rate not measured.": {
    en: "Exact well summer yield rate not measured.",
    fr: "Le débit estival exact du puits n'a pas été mesuré.",
    ar: "لم يُقَس التدفق الصيفي الدقيق للبئر.",
  },
  "Verify local buyer uptake for spring oilseed.": {
    en: "Verify local buyer uptake for spring oilseed.",
    fr: "Vérifier les débouchés locaux de commercialisation pour les cultures de printemps.",
    ar: "التأكد من وجود قنوات تسويق محلية لمحاصيل الموسم الربيعي.",
  },

  // Requested Crop Results
  "Chickpea fits spring 2027 well as a nitrogen-fixing legume breaking historical autumn cereal dominance.": {
    en: "Chickpea fits spring 2027 well as a nitrogen-fixing legume breaking historical autumn cereal dominance.",
    fr: "Le pois chiche s'intègre idéalement au printemps 2027 comme légumineuse fixatrice d'azote rompant la dominance céréalière.",
    ar: "يناسب الحمص ربيع 2027 تماماً كبقولية مثبّتة للآزوت تكسر هيمنة الحبوب الخريفية السابقة.",
  },

  // Data Quality Notes, Warnings & Limitations
  "Reduced completeness because parcel F1 is an unverified demo parcel with unknown soil chemistry.": {
    en: "Reduced completeness because parcel F1 is an unverified demo parcel with unknown soil chemistry.",
    fr: "Complétude réduite car la parcelle F1 est une parcelle témoin dont la chimie du sol reste inconnue.",
    ar: "نسبة الاكتمال منخفضة لأن القطعة F1 تجريبية وغير مفحوصة وبيانات التربة فيها غير محددة.",
  },
  "Farm-level confidence reflects 1 unverified demo parcel.": {
    en: "Farm-level confidence reflects 1 unverified demo parcel.",
    fr: "La fiabilité globale reflète 1 parcelle témoin non vérifiée.",
    ar: "تعكس ثقة بيانات المزرعة وجود قطعة تجريبية واحدة غير مفحوصة.",
  },
  "Complete farmer soil chemistry, elevation, water, and crop history provided.": {
    en: "Complete farmer soil chemistry, elevation, water, and crop history provided.",
    fr: "Données complètes de chimie du sol, altitude, irrigation et historique fournies par l'agriculteur.",
    ar: "تتوفر بيانات كاملة عن التربة والارتفاع ومصدر المياه وسجل المحاصيل.",
  },
  "Predictions rely on dataset_version 2026.11-guelma-v1 regional signals rather than verified soil sampling on F1.": {
    en: "Predictions rely on dataset_version 2026.11-guelma-v1 regional signals rather than verified soil sampling on F1.",
    fr: "Les estimations reposent sur les signaux régionaux 2026.11-guelma-v1 plutôt que sur une analyse de sol vérifiée en F1.",
    ar: "تعتمد التوقعات على المعطيات الإقليمية للإصدار 2026.11-guelma-v1 بدل نتائج تحليل التربة في القطعة F1.",
  },
  "Awaiting field survey data for pre-designated parcel F1.": {
    en: "Awaiting field survey data for pre-designated parcel F1.",
    fr: "En attente des relevés de terrain pour la parcelle désignée F1.",
    ar: "في انتظار بيانات الفحص الحقلي للقطعة التجريبية F1.",
  },
  "Relies on regional dataset_version 2026.11-guelma-v1 while unstudied parcel awaits soil lab measurements.": {
    en: "Relies on regional dataset_version 2026.11-guelma-v1 while unstudied parcel awaits soil lab measurements.",
    fr: "Repose sur le jeu régional 2026.11-guelma-v1 en attendant l'analyse de sol de la parcelle non étudiée.",
    ar: "يعتمد على بيانات المنطقة 2026.11-guelma-v1 ريثما تُستكمل تحاليل التربة المخبرية للقطعة.",
  },
  "Combined farmer soil/water records with pinned 2026.11-guelma-v1 regional climate signals.": {
    en: "Combined farmer soil/water records with pinned 2026.11-guelma-v1 regional climate signals.",
    fr: "Combine les relevés sol/eau de l'agriculteur aux signaux climatiques régionaux 2026.11-guelma-v1.",
    ar: "يدمج سجلات الفلاح للتربة والمياه مع المؤشرات المناخية الإقليمية لإصدار 2026.11-guelma-v1.",
  },
  "DEMO_PARCEL_UNVERIFIED": {
    en: "Unverified demo parcel (field measurements pending)",
    fr: "Parcelle témoin non vérifiée (mesures terrain en attente)",
    ar: "قطعة تجريبية غير مفحوصة ميدانياً (بانتظار القياسات الحقلية)",
  },
  "DEMO_PARCEL_UNVERIFIED: Parcel measurements have not yet been studied.": {
    en: "DEMO_PARCEL_UNVERIFIED: Parcel measurements have not yet been studied.",
    fr: "Parcelle témoin non vérifiée : les mesures de terrain n'ont pas encore été relevées.",
    ar: "قطعة تجريبية غير مفحوصة: لم يتم بعد إجراء القياسات الميدانية للتربة والارتفاع.",
  },
};

const STRATEGY_ID_NAMES: Record<string, Tri> = {
  S1_baseline_cereal: {
    en: "Existing Cereal Baseline",
    fr: "Référence Céréalière Actuelle",
    ar: "المرجع الحالي لزراعة الحبوب",
  },
  S2_water_resilient: {
    en: "Chickpea & Drip Forage Balanced Rotation",
    fr: "Rotation Équilibrée Pois Chiche & Fourrage",
    ar: "التناوب المتوازن: الحمص والأعلاف بالتنقيط",
  },
  S3_income_diversified: {
    en: "Market Cereal & Legume Cash Focus",
    fr: "Rotation Marché Céréales & Légumineuses",
    ar: "تناوب نقدي للحبوب والبقوليات التسويقية",
  },
};

const MISSING_FIELD_LABELS: Record<
  string,
  { plain: Tri; tech: Tri }
> = {
  soil_ph: {
    plain: {
      en: "soil acidity (pH test)",
      fr: "acidité du sol (test pH)",
      ar: "حموضة التربة (اختبار pH)",
    },
    tech: {
      en: "soil pH",
      fr: "pH du sol",
      ar: "حموضة التربة (soil_ph)",
    },
  },
  organic_matter_percent: {
    plain: {
      en: "soil fertility (organic matter)",
      fr: "fertilité du sol (matière organique)",
      ar: "نسبة المادة العضوية (خصوبة التربة)",
    },
    tech: {
      en: "organic matter (%)",
      fr: "matière organique (%)",
      ar: "المادة العضوية (%)",
    },
  },
  elevation_m: {
    plain: {
      en: "field altitude (optional)",
      fr: "altitude de parcelle (optionnel)",
      ar: "ارتفاع القطعة (اختياري)",
    },
    tech: {
      en: "elevation (m)",
      fr: "altitude (m)",
      ar: "الارتفاع عن البحر (م)",
    },
  },
};

export function localizeFarmName(name: string | null | undefined, lang: Language): string {
  if (!name) return "";
  const hit = EXACT_PHRASE_MAP[name.trim()];
  if (hit) return hit[lang];
  return name;
}

export function localizeFieldName(name: string | null | undefined, lang: Language): string {
  if (!name) return "";
  const trimmed = name.trim();
  const hit = EXACT_PHRASE_MAP[trimmed];
  if (hit) return hit[lang];
  return name;
}

export function localizeStrategyName(
  strategyId: string,
  rawName: string | null | undefined,
  lang: Language
): string {
  if (rawName) {
    const exact = EXACT_PHRASE_MAP[rawName.trim()];
    if (exact) return exact[lang];
  }
  const byId = STRATEGY_ID_NAMES[strategyId];
  if (byId && (!rawName || rawName === strategyId)) return byId[lang];
  return rawName || strategyId;
}

export function localizeStrategyDescription(
  _strategyId: string,
  rawDesc: string,
  lang: Language
): string {
  const exact = EXACT_PHRASE_MAP[rawDesc.trim()];
  if (exact) return exact[lang];
  return rawDesc;
}

export function localizeDynamicPhrase(text: string, lang: Language): string {
  const trimmed = text.trim();
  const exact = EXACT_PHRASE_MAP[trimmed];
  if (exact) return exact[lang];

  // Dynamic Scenario overall_summary:
  // "Scenario (+0°C, +20%) rotation analysis — Guelma Team Demo Parcel (Unstudied) (1 parcel)."
  const scenMatch = trimmed.match(
    /^Scenario \(([^)]+)\) rotation analysis — (.+?) \((\d+) parcel(s)?\)\.?$/i
  );
  if (scenMatch) {
    const [, params, rawField, countStr] = scenMatch;
    const fName = localizeFieldName(rawField, lang);
    const cnt = Number(countStr);
    if (lang === "fr") {
      return `Analyse du scénario (${params}) — ${fName} (${cnt} parcelle${cnt > 1 ? "s" : ""}).`;
    }
    if (lang === "ar") {
      return `تحليل سيناريو التناوب (${params}) — ${fName} (${formatParcelCount(cnt, "ar")}).`;
    }
    return `Scenario (${params}) rotation analysis — ${fName} (${cnt} parcel${cnt > 1 ? "s" : ""}).`;
  }

  // Dynamic Scenario climate_trend_summary:
  // "Adjusted scenario (+0°C, -20% rain) increases summer evaporative deficit across X; legume-forage cover cuts bare-soil loss."
  const climateScen = trimmed.match(
    /^Adjusted scenario \(([^,]+),\s*([^)]+?) rain\) increases summer evaporative deficit across (.+?); legume-forage cover cuts bare-soil loss\.?$/i
  );
  if (climateScen) {
    const [, tDelta, pDelta, rawField] = climateScen;
    const fName = localizeFieldName(rawField, lang);
    if (lang === "fr") {
      return `Le scénario ajusté (${tDelta}, ${pDelta} de pluie) accentue le déficit hydrique estival sur ${fName} ; le couvert légumineuse-fourrage réduit la perte en sol nu.`;
    }
    if (lang === "ar") {
      return `يزيد السيناريو المعدّل (${tDelta}، أمطار ${pDelta}) من العجز المائي الصيفي في ${fName}؛ ويساعد غطاء البقوليات والأعلاف في تقليل فقدان رطوبة التربة المكشوفة.`;
    }
    return text;
  }

  // Dynamic Farmer soil_type evidence interpretation:
  // "Farmer-verified loamy soil texture."
  const soilMatch = trimmed.match(/^Farmer-verified ([a-z_]+) soil texture\.?$/i);
  if (soilMatch) {
    const sKey = soilMatch[1] as SoilType;
    const sLabel = SOIL_TYPE_LABELS[lang]?.[sKey] ?? sKey;
    if (lang === "fr") return `Texture de sol confirmée par l'agriculteur : ${sLabel}.`;
    if (lang === "ar") return `قوام التربة المؤكد من الفلاح: ${sLabel}.`;
    return text;
  }

  // Dynamic Requested crop result explanation:
  // "Requested crop chickpea evaluated against water (moderate) and seasonal window."
  const reqCropMatch = trimmed.match(
    /^Requested crop ([a-z0-9_]+) evaluated against water \(([a-z_]+)\) and seasonal window\.?$/i
  );
  if (reqCropMatch) {
    const [, cid, availKey] = reqCropMatch;
    const cropLabel = resolveCropDisplayName(cid, null, undefined, lang);
    const availLabel =
      WATER_AVAILABILITY_LABELS[lang]?.[availKey as WaterAvailability] ?? availKey;
    if (lang === "fr") {
      return `Culture demandée « ${cropLabel} » évaluée selon la disponibilité en eau (${availLabel}) et la fenêtre saisonnière.`;
    }
    if (lang === "ar") {
      return `تم تقييم المحصول المطلوب (${cropLabel}) بناءً على وفرة المياه (${availLabel}) والنافذة الموسمية.`;
    }
    return `Requested crop ${cropLabel} evaluated against water (${availLabel}) and seasonal window.`;
  }

  // Dynamic DataQuality confidence note:
  // "Completeness 80%: missing elevation_m."
  const compMatch = trimmed.match(/^Completeness (\d+)%: missing (.+?)\.?$/i);
  if (compMatch) {
    const [, pct, missingRaw] = compMatch;
    const translatedMissing = missingRaw
      .split(",")
      .map((s) => localizeMissingField(s.trim(), lang, false))
      .join(lang === "ar" ? "، " : ", ");
    if (lang === "fr") {
      return `Complétude ${pct} % : données manquantes (${translatedMissing}).`;
    }
    if (lang === "ar") {
      return `نسبة الاكتمال ${pct}%: المعطيات الناقصة (${translatedMissing}).`;
    }
    return `Completeness ${pct}%: missing ${missingRaw}.`;
  }

  // Dynamic field unverified warning message fallback:
  if (trimmed.startsWith("DEMO_PARCEL_UNVERIFIED:")) {
    return EXACT_PHRASE_MAP[
      "DEMO_PARCEL_UNVERIFIED: Parcel measurements have not yet been studied."
    ][lang];
  }

  return text;
}

export function localizeAnalysisText(
  text: string,
  lang: Language,
  plainMode: boolean
): string {
  const translated = localizeDynamicPhrase(text, lang);
  if (!plainMode) return translated;

  if (lang === "en") {
    return translated
      .replace(/biological nitrogen fixation/gi, "natural soil nitrogen feeding")
      .replace(
        /cereal monoculture pathogen carryover/gi,
        "root disease build-up from planting cereals every year"
      )
      .replace(/bare-field exposure/gi, "bare dry soil left uncovered")
      .replace(/bare-soil loss/gi, "sun-dried bare soil loss")
      .replace(/abiotic stress/gi, "weather and soil stress")
      .replace(/evaporative deficit/gi, "sun-drying water loss")
      .replace(/evaporative/gi, "sun-drying");
  }
  if (lang === "fr") {
    return translated
      .replace(/fixation biologique de l'azote/gi, "enrichissement naturel en azote")
      .replace(/pathogènes/gi, "maladies des racines")
      .replace(/stress abiotique/gi, "stress climatique et du sol")
      .replace(/déficit évaporatif/gi, "perte d'eau par évaporation")
      .replace(/évaporatif/gi, "séchant au soleil");
  }
  if (lang === "ar") {
    return translated
      .replace(/تثبيت الآزوت البيولوجي|تثبيت النيتروجين البيولوجي/g, "تغذية التربة طبيعياً بالآزوت")
      .replace(/الإجهاد اللاأحيائي/g, "إجهاد الطقس والتربة")
      .replace(/مؤشر الإجهاد التبخري/g, "تجفيف الشمس للتربة المكشوفة")
      .replace(/العجز التبخري/g, "فقدان الرطوبة بحرارة الشمس")
      .replace(/انكشاف التربة العارية/g, "بقاء التربة مكشوفة بدون غطاء");
  }
  return translated;
}

export function localizeMissingField(
  rawCode: string,
  lang: Language,
  plainMode: boolean
): string {
  const parts = rawCode.trim().split(".");
  const fieldKey = parts.length > 1 ? parts[parts.length - 1] : parts[0];
  const prefix = parts.length > 1 ? `${parts.slice(0, -1).join(".")} · ` : "";
  const entry = MISSING_FIELD_LABELS[fieldKey];
  if (!entry) return rawCode;
  const label = plainMode ? entry.plain[lang] : entry.tech[lang];
  return `${prefix}${label}`;
}

export function localizeEvidenceValue(
  val: string | number | boolean | null | undefined,
  lang: Language
): string {
  if (val === null || val === undefined) return "—";
  if (typeof val === "boolean") {
    return val
      ? lang === "ar"
        ? "نعم"
        : lang === "fr"
        ? "Oui"
        : "Yes"
      : lang === "ar"
      ? "لا"
      : lang === "fr"
      ? "Non"
      : "No";
  }
  if (typeof val === "number") return String(val);
  const key = val.trim().toLowerCase();
  if (key in WATER_AVAILABILITY_LABELS[lang]) {
    return WATER_AVAILABILITY_LABELS[lang][key as WaterAvailability];
  }
  if (key in SOIL_TYPE_LABELS[lang]) {
    return SOIL_TYPE_LABELS[lang][key as SoilType];
  }
  const simple: Record<string, Tri> = {
    moderate: { en: "Moderate", fr: "Modérée", ar: "متوسطة" },
    low: { en: "Low", fr: "Faible", ar: "منخفضة" },
    high: { en: "High", fr: "Élevée", ar: "مرتفعة" },
    mild: { en: "Mild", fr: "Léger", ar: "خفيف" },
    unknown: { en: "Unknown", fr: "Inconnu", ar: "غير محدد" },
  };
  return simple[key]?.[lang] ?? String(val);
}

export function localizeUnit(unit: string | null | undefined, lang: Language): string {
  if (!unit) return "";
  const key = unit.trim();
  const units: Record<string, Tri> = {
    "mm/year": { en: "mm/year", fr: "mm/an", ar: "مم/سنة" },
    "% vs historical mean": {
      en: "% vs historical mean",
      fr: "% vs moyenne historique",
      ar: "% مقارنة بالمتوسط التاريخي",
    },
    m: { en: "m", fr: "m", ar: "م" },
    ha: { en: "ha", fr: "ha", ar: "هكتار" },
  };
  return units[key]?.[lang] ?? unit;
}

export function localizePeriod(period: string | null | undefined, lang: Language): string {
  if (!period) return "";
  const key = period.trim();
  const periods: Record<string, Tri> = {
    "dataset-zone-baseline": {
      en: "Dataset Zone Baseline",
      fr: "Référence zone climatique",
      ar: "خط الأساس للمنطقة",
    },
    "dataset-dry-quantile": {
      en: "Dataset Dry Quantile",
      fr: "Quantile sec régional",
      ar: "المئين الجاف للبيانات",
    },
  };
  return periods[key]?.[lang] ?? period;
}

export function localizeCropIdBadge(cropId: string, lang: Language): string {
  if (lang === "en") return cropId;
  return resolveCropDisplayName(cropId, null, undefined, lang);
}

export function formatAreaHa(ha: number, lang: Language, decimals = 1): string {
  const num = ha.toFixed(decimals);
  return lang === "ar" ? `${num} هكتار` : `${num} ha`;
}

export function formatMeters(meters: number, lang: Language): string {
  return lang === "ar" ? `${Math.round(meters)} م` : `${Math.round(meters)} m`;
}

export function formatVerticesCount(count: number, lang: Language): string {
  if (lang === "ar") {
    if (count === 1) return "نقطة 1";
    if (count === 2) return "نقطتان";
    if (count >= 3 && count <= 10) return `${count} نقاط`;
    return `${count} نقطة`;
  }
  return `${count} pts`;
}

export function formatParcelCount(count: number, lang: Language): string {
  if (lang === "en") return `${count} parcel${count === 1 ? "" : "s"}`;
  if (lang === "fr") return `${count} parcelle${count <= 1 ? "" : "s"}`;
  if (count === 0) return "0 قطعة";
  if (count === 1) return "قطعة واحدة";
  if (count === 2) return "قطعتان";
  if (count <= 10) return `${count} قطع`;
  return `${count} قطعة`;
}

export function formatSeasonMonthShort(month: number, lang: Language): string {
  if (lang === "ar") return `ش${month}`;
  return `M${month}`;
}

export interface DynamicPresetMetaInput {
  farmName: string;
  fieldId: string;
  fieldName: string;
  commune: string;
  soilType: string;
  irrigationSystem: string;
  waterAvailability: string;
  waterSource: string;
  areaHa: number;
  latestCropId?: string | null;
  latestCropRaw?: string | null;
  latestCropSeason?: string | null;
  latestCropYear?: number | null;
}

/**
 * Formats localized display fields for a farmer-owned field converted into a
 * 3D simulator preset across EN, FR, and AR.
 */
export function buildLocalizedFarmPresetFields(
  meta: DynamicPresetMetaInput,
  lang: Language
): { short: string; name: string; zone: string; note: string } {
  const farmLoc = localizeFarmName(meta.farmName, lang);
  const fieldLoc = localizeFieldName(meta.fieldName, lang);
  const communeLoc = localizeCommuneName(meta.commune, lang);
  const wilayaLoc = lang === "ar" ? "قالمة" : "Guelma";

  const soilLoc =
    SOIL_TYPE_LABELS[lang]?.[meta.soilType as SoilType] ?? meta.soilType;
  const irrLoc =
    IRRIGATION_SYSTEM_LABELS[lang]?.[meta.irrigationSystem as IrrigationSystem] ??
    meta.irrigationSystem;
  const availLoc =
    WATER_AVAILABILITY_LABELS[lang]?.[meta.waterAvailability as WaterAvailability] ??
    meta.waterAvailability;
  const srcLoc =
    WATER_SOURCE_LABELS[lang]?.[meta.waterSource as WaterSource] ??
    meta.waterSource;
  const areaLoc = formatAreaHa(meta.areaHa, lang);

  const locationSuffix =
    farmLoc.toLowerCase().includes(communeLoc.toLowerCase())
      ? ""
      : communeLoc.trim().toLowerCase() === wilayaLoc.trim().toLowerCase()
        ? ` (${communeLoc})`
        : ` (${communeLoc}, ${wilayaLoc})`;

  let cropSuffix = "";
  if (meta.latestCropId) {
    const cropLabel = resolveCropDisplayName(
      meta.latestCropId,
      meta.latestCropRaw,
      undefined,
      lang
    );
    const seasonLabel =
      (meta.latestCropSeason &&
        SEASON_LABELS[lang]?.[meta.latestCropSeason as Season]) ??
      meta.latestCropSeason ??
      "";
    const yearLabel = meta.latestCropYear ? String(meta.latestCropYear) : "";
    const seasonYear = [seasonLabel, yearLabel].filter(Boolean).join(" ");
    if (lang === "fr") {
      cropSuffix = ` Dernière culture enregistrée : ${cropLabel}${seasonYear ? ` (${seasonYear})` : ""}.`;
    } else if (lang === "ar") {
      cropSuffix = ` آخر محصول مسجّل: ${cropLabel}${seasonYear ? ` (${seasonYear})` : ""}.`;
    } else {
      cropSuffix = ` Latest recorded crop: ${cropLabel}${seasonYear ? ` (${seasonYear})` : ""}.`;
    }
  }

  const note =
    lang === "fr"
      ? `${farmLoc}${locationSuffix}. Superficie ${areaLoc}, disponibilité en eau : ${availLoc} (${srcLoc}).${cropSuffix}`
      : lang === "ar"
        ? `${farmLoc}${locationSuffix}. المساحة ${areaLoc}، توفر المياه: ${availLoc} (${srcLoc}).${cropSuffix}`
        : `${farmLoc}${locationSuffix}. Area ${areaLoc}, water availability: ${availLoc} (${srcLoc}).${cropSuffix}`;

  const shortBase = fieldLoc.length > 18 ? fieldLoc.slice(0, 18) : fieldLoc;
  return {
    short: `${shortBase} (${meta.fieldId})`,
    name: `${fieldLoc} · ${communeLoc}`,
    zone: `${farmLoc} · ${soilLoc} · ${irrLoc}`,
    note,
  };
}
