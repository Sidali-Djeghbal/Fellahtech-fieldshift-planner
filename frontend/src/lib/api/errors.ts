import type { ErrorCode, Language, WarningCode } from "@/lib/schemas";

export interface ApiErrorDetails {
  status: number;
  code: ErrorCode;
  message: string;
  details: Array<Record<string, unknown>>;
  requestId: string | null;
  retryAfterSeconds?: number | null;
}

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: ErrorCode;
  readonly details: Array<Record<string, unknown>>;
  readonly requestId: string | null;
  readonly retryAfterSeconds: number | null;

  constructor(info: ApiErrorDetails) {
    super(info.message);
    this.name = "ApiClientError";
    this.status = info.status;
    this.code = info.code;
    this.details = info.details;
    this.requestId = info.requestId;
    this.retryAfterSeconds = info.retryAfterSeconds ?? null;
  }
}

export interface ErrorPresentation {
  title: string;
  guidance: string;
  severity: "warning" | "error";
  isGuestLimit: boolean;
  isBoundaryError: boolean;
  isRateLimited: boolean;
  isAuthError: boolean;
  isOutage: boolean;
}

const ERROR_COPY: Record<
  ErrorCode,
  Record<Language, { title: string; guidance: string }>
> = {
  INVALID_INPUT: {
    en: {
      title: "Invalid Input Values",
      guidance: "Check highlighted fields (weights sum = 100, planting month matches season, disjoint crops).",
    },
    fr: {
      title: "Données d'entrée invalides",
      guidance: "Vérifiez les champs signalés (somme des poids = 100, mois cohérent avec la saison).",
    },
    ar: {
      title: "بيانات إدخال غير صالحة",
      guidance: "تحقق من الحقول المحددة (مجموع الأوزان = 100، توافق شهر الزراعة مع الفصل).",
    },
  },
  UNAUTHORIZED: {
    en: {
      title: "Session Expired or Unauthorized",
      guidance: "Sign in again or restart a Guelma Guest Demo session to continue.",
    },
    fr: {
      title: "Session expirée ou non autorisée",
      guidance: "Reconnectez-vous ou relancez une session démo invité pour Guelma.",
    },
    ar: {
      title: "انتهت الجلسة أو غير مصرح",
      guidance: "أعد تسجيل الدخول أو ابدأ جلسة تجريبية جديدة لولاية قالمة.",
    },
  },
  GUEST_LIMIT_REACHED: {
    en: {
      title: "Guest Sandbox Limit Reached",
      guidance: "Guest sessions allow 3 farms, 5 fields/farm, and 40 canonical quarters (10 full analyses). Create a free account to claim your data and unlock unlimited planning.",
    },
    fr: {
      title: "Limite du mode invité atteinte",
      guidance: "Le bac à sable invité autorise 3 fermes, 5 parcelles/ferme et 40 trimestres (10 analyses complètes). Créez un compte gratuit pour conserver vos données.",
    },
    ar: {
      title: "تم بلوغ حد الجلسة التجريبية",
      guidance: "تتيح جلسة الضيف 3 مزارع و5 قطع للمزرعة و40 وحدة تحليل (10 تحليلات كاملة). أنشئ حساباً مجانياً لحفظ بياناتك ومتابعة العمل.",
    },
  },
  NOT_FOUND: {
    en: {
      title: "Resource Not Found",
      guidance: "The requested farm, parcel, or analysis record does not exist or belongs to another session.",
    },
    fr: {
      title: "Ressource introuvable",
      guidance: "La ferme, la parcelle ou l'analyse demandée est introuvable dans cette session.",
    },
    ar: {
      title: "العنصر غير موجود",
      guidance: "المزرعة أو القطعة أو التحليل المطلوب غير موجود في هذه الجلسة.",
    },
  },
  CONFLICT: {
    en: {
      title: "Record Conflict",
      guidance: "A duplicate parcel ID or conflicting request state occurred. Refresh and retry.",
    },
    fr: {
      title: "Conflit d'état",
      guidance: "Un identifiant en double ou un changement d'état concurrent s'est produit.",
    },
    ar: {
      title: "تعارض في البيانات",
      guidance: "يوجد معرف مكرر أو حالة متعارضة. حدّث الصفحة وأعد المحاولة.",
    },
  },
  CATALOG_VERSION_MISMATCH: {
    en: {
      title: "Crop Catalog Updated",
      guidance: "Reloading the latest synchronized crop catalog before submitting.",
    },
    fr: {
      title: "Catalogue des cultures mis à jour",
      guidance: "Rechargement du catalogue synchronisé avant de soumettre.",
    },
    ar: {
      title: "تم تحديث دليل المحاصيل",
      guidance: "أعد تحميل دليل المحاصيل المحدث قبل الإرسال.",
    },
  },
  OUTSIDE_DEMO_BOUNDARY: {
    en: {
      title: "Outside Guelma MVP Boundary",
      guidance: "Guest parcels must lie inside the Wilaya of Guelma PostGIS polygon. Move your parcel inside the blue Guelma boundary or register a free account.",
    },
    fr: {
      title: "Hors périmètre MVP de Guelma",
      guidance: "Les parcelles invitées doivent se situer dans le polygone de Guelma. Déplacez la parcelle ou créez un compte gratuit.",
    },
    ar: {
      title: "خارج حدود ولاية قالمة التجريبية",
      guidance: "يجب أن تقع قطع الضيف داخل حدود ولاية قالمة. انقل القطعة داخل الحدود الزرقاء أو أنشئ حساباً مجانياً.",
    },
  },
  INSUFFICIENT_DATA: {
    en: {
      title: "Insufficient Field Information",
      guidance: "Add at least one crop history season and complete water/location fields before analyzing.",
    },
    fr: {
      title: "Données agronomiques insuffisantes",
      guidance: "Ajoutez au moins une saison d'historique cultural et les paramètres d'eau/localisation.",
    },
    ar: {
      title: "بيانات الحقل غير كافية",
      guidance: "أضف موسماً واحداً على الأقل في سجل المحاصيل وأكمل بيانات الماء والموقع.",
    },
  },
  RATE_LIMIT_EXCEEDED: {
    en: {
      title: "Too Many Requests",
      guidance: "Wait for the Retry-After countdown before polling or submitting again.",
    },
    fr: {
      title: "Trop de requêtes",
      guidance: "Patientez pendant le compte à rebours avant de relancer.",
    },
    ar: {
      title: "تم تجاوز حد الطلبات",
      guidance: "انتظر انتهاء المؤقت قبل إعادة المحاولة.",
    },
  },
  INTERNAL_ERROR: {
    en: {
      title: "Unexpected Server Error",
      guidance: "Retry in a moment and keep the Request ID if the issue persists.",
    },
    fr: {
      title: "Erreur serveur inattendue",
      guidance: "Réessayez dans un instant et conservez l'identifiant de requête.",
    },
    ar: {
      title: "خطأ غير متوقع في الخادم",
      guidance: "أعد المحاولة بعد قليل واحتفظ بمعرف الطلب عند الحاجة.",
    },
  },
  ML_UNAVAILABLE: {
    en: {
      title: "Agronomic Engine Temporarily Unavailable",
      guidance: "The ML circuit breaker is open. Review previously saved analyses or retry shortly.",
    },
    fr: {
      title: "Moteur agronomique indisponible",
      guidance: "Le disjoncteur ML est ouvert. Consultez vos analyses sauvegardées ou réessayez.",
    },
    ar: {
      title: "محرك التوصيات غير متاح مؤقتاً",
      guidance: "قاطع الدائرة مفتوح مؤقتاً. يمكنك مراجعة التحليلات المحفوظة أو إعادة المحاولة.",
    },
  },
  ML_INVALID_RESPONSE: {
    en: {
      title: "Invalid Model Response Blocked",
      guidance: "The backend rejected an unverified ML payload for safety. Retry or view saved history.",
    },
    fr: {
      title: "Réponse modèle rejetée par validation",
      guidance: "Le serveur a bloqué une réponse non conforme au contrat v5.x. Réessayez.",
    },
    ar: {
      title: "تم رفض مخرجات غير مطابقة للمواصفات",
      guidance: "رفض الخادم استجابة غير صالحة لضمان دقة التوصيات. أعد المحاولة.",
    },
  },
  ML_CONTRACT_ERROR: {
    en: {
      title: "Schema Contract Mismatch",
      guidance: "Backend-ML contract validation failed. Check system health and retry.",
    },
    fr: {
      title: "Erreur de contrat de schéma",
      guidance: "La validation du contrat Backend-ML a échoué.",
    },
    ar: {
      title: "عدم تطابق عقد البيانات",
      guidance: "فشل التحقق من عقد البيانات بين الخادم ومحرك التحليل.",
    },
  },
  DATASET_VERSION_UNAVAILABLE: {
    en: {
      title: "Pinned Dataset Version Mismatch (SEM-07)",
      guidance: "The requested dataset version is not active on the engine. Retry with current active dataset.",
    },
    fr: {
      title: "Version de jeu de données indisponible (SEM-07)",
      guidance: "La version demandée ne correspond pas au jeu actif.",
    },
    ar: {
      title: "إصدار مجموعة البيانات غير متاح (SEM-07)",
      guidance: "إصدار البيانات المحدد غير مطابق للإصدار النشط حالياً.",
    },
  },
  ML_DATASET_ERROR: {
    en: {
      title: "Dataset Feature Lookup Error",
      guidance: "Could not read local dataset features for this coordinate zone.",
    },
    fr: {
      title: "Erreur de lecture du jeu de données",
      guidance: "Impossible de lire les variables locales pour cette zone.",
    },
    ar: {
      title: "خطأ في قراءة بيانات المنطقة",
      guidance: "تعذر استرجاع الخصائص البيئية المحلية لهذه الإحداثيات.",
    },
  },
  SERVICE_UNAVAILABLE: {
    en: {
      title: "Backend Database Unavailable",
      guidance: "PostgreSQL/PostGIS health check failed. Wait for service recovery.",
    },
    fr: {
      title: "Base de données indisponible",
      guidance: "PostgreSQL/PostGIS est injoignable pour le moment.",
    },
    ar: {
      title: "قاعدة البيانات غير متاحة",
      guidance: "تعذر الاتصال بقاعدة البيانات حالياً.",
    },
  },
  DATASET_UNAVAILABLE: {
    en: {
      title: "No Active Environmental Dataset",
      guidance: "The server has no active dataset_version in dataset_registry.",
    },
    fr: {
      title: "Aucun jeu de données actif",
      guidance: "Aucune version active n'est configurée sur le serveur.",
    },
    ar: {
      title: "لا توجد مجموعة بيانات نشطة",
      guidance: "لم يتم تفعيل أي إصدار لبيانات المرجع على الخادم.",
    },
  },
  ML_TIMEOUT: {
    en: {
      title: "Agronomic Engine Timed Out",
      guidance: "Inference exceeded the response timeout. Retry or inspect saved results.",
    },
    fr: {
      title: "Délai dépassé du moteur ML",
      guidance: "L'analyse a expiré. Réessayez ou consultez vos résultats enregistrés.",
    },
    ar: {
      title: "انتهت مهلة محرك التحليل",
      guidance: "استغرق التحليل وقتاً أطول من المتوقع. أعد المحاولة.",
    },
  },
  JOB_TIMEOUT: {
    en: {
      title: "Analysis Job Lease Timed Out",
      guidance: "The background job expired before completion. Re-submit the analysis.",
    },
    fr: {
      title: "Délai du traitement dépassé",
      guidance: "La tâche asynchrone a expiré. Relancez l'analyse.",
    },
    ar: {
      title: "انتهت مهلة مهمة التحليل",
      guidance: "انتهت مهلة المعالجة قبل الاكتمال. أعد إرسال الطلب.",
    },
  },
};

export function presentApiError(
  error: unknown,
  lang: Language
): ErrorPresentation & { code: ErrorCode; message: string; requestId: string | null; retryAfterSeconds: number | null } {
  if (error instanceof ApiClientError) {
    const copy = ERROR_COPY[error.code]?.[lang] ?? ERROR_COPY.INTERNAL_ERROR[lang];
    return {
      code: error.code,
      title: copy.title,
      guidance: copy.guidance,
      message: error.message,
      requestId: error.requestId,
      retryAfterSeconds: error.retryAfterSeconds,
      severity: error.code === "GUEST_LIMIT_REACHED" || error.code === "OUTSIDE_DEMO_BOUNDARY" ? "warning" : "error",
      isGuestLimit: error.code === "GUEST_LIMIT_REACHED",
      isBoundaryError: error.code === "OUTSIDE_DEMO_BOUNDARY",
      isRateLimited: error.code === "RATE_LIMIT_EXCEEDED",
      isAuthError: error.code === "UNAUTHORIZED",
      isOutage:
        error.status >= 500 ||
        [
          "ML_UNAVAILABLE",
          "ML_INVALID_RESPONSE",
          "ML_CONTRACT_ERROR",
          "ML_DATASET_ERROR",
          "DATASET_VERSION_UNAVAILABLE",
          "SERVICE_UNAVAILABLE",
          "DATASET_UNAVAILABLE",
          "ML_TIMEOUT",
          "JOB_TIMEOUT",
        ].includes(error.code),
    };
  }

  const fallbackMessage =
    error instanceof Error ? error.message : "Unknown network or application error";
  return {
    code: "INTERNAL_ERROR",
    title: ERROR_COPY.INTERNAL_ERROR[lang].title,
    guidance: ERROR_COPY.INTERNAL_ERROR[lang].guidance,
    message: fallbackMessage,
    requestId: null,
    retryAfterSeconds: null,
    severity: "error",
    isGuestLimit: false,
    isBoundaryError: false,
    isRateLimited: false,
    isAuthError: false,
    isOutage: true,
  };
}

export function getWarningCopy(code: WarningCode, lang: Language): { label: string; description: string } {
  if (code === "DEMO_PARCEL_UNVERIFIED") {
    if (lang === "fr") {
      return {
        label: "DEMO_PARCEL_UNVERIFIED · Parcelle témoin non étudiée",
        description:
          "Parcelle prédéfinie par l'équipe à Guelma : les mesures chimiques du sol et l'altitude n'ont pas encore été relevées sur le terrain.",
      };
    }
    if (lang === "ar") {
      return {
        label: "DEMO_PARCEL_UNVERIFIED · قطعة تجريبية غير مفحوصة ميدانياً",
        description:
          "هذه القطعة مخصصة مسبقاً من الفريق في قالمة؛ لم يتم بعد إجراء تحاليل التربة الميدانية أو قياس الارتفاع.",
      };
    }
    return {
      label: "DEMO_PARCEL_UNVERIFIED · Unstudied Demo Parcel",
      description:
        "Pre-designated by the project team in Guelma; real soil chemistry and elevation measurements have not yet been surveyed.",
    };
  }

  if (lang === "fr") {
    return {
      label: "MVP_OUTSIDE_COVERAGE · Hors couverture MVP Guelma",
      description:
        "Cette parcelle enregistrée se trouve hors du périmètre MVP de Guelma ; la confiance régionale peut être réduite.",
    };
  }
  if (lang === "ar") {
    return {
      label: "MVP_OUTSIDE_COVERAGE · خارج نطاق التغطية التجريبية لقالمة",
      description:
        "تقع هذه القطعة خارج حدود ولاية قالمة المشمولة بالنسخة الأولية؛ قد تنخفض دقة المعايرة الإقليمية.",
    };
  }
  return {
    label: "MVP_OUTSIDE_COVERAGE · Outside Guelma Coverage",
    description:
      "This saved parcel lies outside the Wilaya of Guelma MVP dataset zone; regional signal precision may be reduced.",
  };
}
