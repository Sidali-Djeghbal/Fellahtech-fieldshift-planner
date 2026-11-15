package com.example.myapplication.domain.analysis

import com.example.myapplication.core.common.AppLanguage
import com.example.myapplication.domain.auth.WarningNotice
import com.example.myapplication.domain.field.Season

enum class CycleMode(val apiValue: String) {
    ANNUAL_ROTATION("annual_rotation"),
    CONSECUTIVE_SEASONS("consecutive_seasons");

    companion object {
        fun fromApi(value: String): CycleMode =
            entries.firstOrNull { it.apiValue == value } ?: ANNUAL_ROTATION
    }
}

enum class MarketPreference(val apiValue: String) {
    LOCAL_MARKET("local_market"),
    EXPORT("export"),
    SUBSISTENCE("subsistence"),
    MIXED("mixed");

    companion object {
        fun fromApi(value: String): MarketPreference =
            entries.firstOrNull { it.apiValue == value } ?: MIXED
    }
}

enum class AnalysisJobStatus(val apiValue: String) {
    PENDING("pending"),
    RUNNING("running"),
    OK("ok"),
    PARTIAL("partial"),
    FAILED("failed"),
    CANCELLED("cancelled");

    val isTerminal: Boolean
        get() = this == OK || this == PARTIAL || this == FAILED || this == CANCELLED

    val isSuccessTerminal: Boolean
        get() = this == OK || this == PARTIAL

    companion object {
        fun fromApi(value: String): AnalysisJobStatus =
            entries.firstOrNull { it.apiValue == value } ?: PENDING
    }
}

enum class SeverityLevel(val apiValue: String) {
    LOW("low"),
    MEDIUM("medium"),
    HIGH("high");

    companion object {
        fun fromApi(value: String): SeverityLevel =
            entries.firstOrNull { it.apiValue == value } ?: MEDIUM
    }
}

data class PriorityWeights(
    val waterSaving: Int = 70,
    val soilImprovement: Int = 70,
    val income: Int = 75,
    val riskReduction: Int = 70,
    val forageValue: Int = 40
)

data class ScenarioOverrides(
    val tempDeltaC: Double = 0.0,
    val precipPctDelta: Double = 0.0
)

data class PlanningConfig(
    val startSeason: Season,
    val startYear: Int,
    val horizonSeasons: Int,
    val cycleMode: CycleMode = CycleMode.ANNUAL_ROTATION,
    val plantingMonth: Int? = null,
    val scenarioOverrides: ScenarioOverrides? = null
)

data class AnalysisSubmitInput(
    val farmId: String,
    val language: AppLanguage,
    val planning: PlanningConfig,
    val weights: PriorityWeights,
    val marketPreference: MarketPreference,
    val targetCropIds: List<String> = emptyList(),
    val excludedCropIds: List<String> = emptyList(),
    val equipmentConstraints: List<String> = emptyList(),
    val fieldIds: List<String>
)

data class ActiveAnalysisRequest(
    val requestId: String,
    val farmId: String,
    val pollIntervalMs: Long,
    val createdAtEpochMs: Long
)

data class AnalysisQueuedJob(
    val requestId: String,
    val status: AnalysisJobStatus,
    val pollUrl: String,
    val pollIntervalMs: Long,
    val warnings: List<WarningNotice>
)

data class DegradedModeInfo(
    val kind: String,
    val stale: Boolean,
    val sourceAnalysisId: String,
    val createdAt: String,
    val datasetVersion: String,
    val ageSeconds: Long
)

data class PollErrorInfo(
    val code: String,
    val httpEquivalent: Int,
    val message: String
)

data class DataQuality(
    val completenessScore: Double?,
    val confidenceNote: String?,
    val missingData: List<String>,
    val warnings: List<String>,
    val limitations: List<String>
)

data class SeasonPlan(
    val order: Int,
    val season: Season,
    val year: Int,
    val plantingMonth: Int?,
    val cropId: String,
    val cropName: String,
    val category: String,
    val role: String,
    val selectionStatus: String
)

data class StrategyScores(
    val waterEfficiency: Double,
    val erosionProtection: Double,
    val organicMatterGain: Double,
    val nitrogenContribution: Double,
    val pestCycleDisruption: Double,
    val incomeForageValue: Double,
    val priorityFit: Double,
    val bareFieldDaysPerYear: Int
)

data class ReasonItem(
    val code: String,
    val text: String
)

data class EvidenceItem(
    val dataSource: String,
    val sourceMission: String?,
    val parameter: String,
    val observedValue: String,
    val unit: String?,
    val period: String?,
    val interpretation: String
)

data class BenefitItem(
    val benefitId: String,
    val title: String,
    val description: String
)

data class RiskItem(
    val riskId: String,
    val title: String,
    val description: String,
    val severity: SeverityLevel,
    val likelihood: SeverityLevel?,
    val mitigation: String
)

data class Explanation(
    val reasons: List<ReasonItem>,
    val evidence: List<EvidenceItem>,
    val benefits: List<BenefitItem>,
    val risks: List<RiskItem>,
    val assumptions: List<String>,
    val informationGaps: List<String>,
    val needsLocalReview: List<String>
)

data class Strategy(
    val strategyId: String,
    val name: String,
    val isExistingRotation: Boolean,
    val description: String,
    val seasons: List<SeasonPlan>,
    val scores: StrategyScores,
    val confidence: SeverityLevel,
    val explanation: Explanation
)

data class RequestedCropEvaluation(
    val requestedCropId: String,
    val outcome: String,
    val includedInStrategyIds: List<String>,
    val replacedByCropId: String?,
    val explanation: String
)

data class FieldPlan(
    val fieldId: String,
    val fieldName: String,
    val status: AnalysisJobStatus,
    val partialReason: String?,
    val climateTrendSummary: String,
    val strategies: List<Strategy>,
    val suggestedStrategyId: String?,
    val requestedCropResults: List<RequestedCropEvaluation>,
    val dataQuality: DataQuality
)

data class AnalysisResultData(
    val schemaVersion: String,
    val requestId: String,
    val datasetVersionUsed: String,
    val generatedAt: String,
    val status: AnalysisJobStatus,
    val language: AppLanguage,
    val mlEngineVersion: String,
    val overallSummary: String,
    val disclaimer: String,
    val fieldPlans: List<FieldPlan>,
    val dataQuality: DataQuality
)

data class AnalysisPollState(
    val requestId: String,
    val status: AnalysisJobStatus,
    val pollIntervalMs: Long?,
    val retryAfterSeconds: Long?,
    val analysisId: String?,
    val warnings: List<WarningNotice>,
    val degradedMode: DegradedModeInfo?,
    val error: PollErrorInfo?,
    val result: AnalysisResultData?
)

data class AnalysisResultEnvelope(
    val analysisId: String,
    val requestId: String,
    val status: AnalysisJobStatus,
    val datasetVersion: String,
    val warnings: List<WarningNotice>,
    val degradedMode: DegradedModeInfo?,
    val result: AnalysisResultData
)

data class FarmAnalysisSummary(
    val requestId: String,
    val analysisId: String?,
    val status: AnalysisJobStatus,
    val language: AppLanguage,
    val catalogVersion: String,
    val datasetVersion: String?,
    val mlEngineVersion: String?,
    val warnings: List<WarningNotice>,
    val createdAt: String,
    val durationMs: Long?
)

data class FarmAnalysesPage(
    val items: List<FarmAnalysisSummary>,
    val nextCursor: String?,
    val hasMore: Boolean
)

data class CropCatalogItem(
    val cropId: String,
    val displayName: String?,
    val nameEn: String,
    val nameFr: String,
    val nameAr: String,
    val category: String,
    val roles: List<String>,
    val family: String
) {
    fun localizedName(language: AppLanguage): String = when (language) {
        AppLanguage.ENGLISH -> nameEn
        AppLanguage.FRENCH -> nameFr
        AppLanguage.ARABIC -> nameAr
    }.ifBlank { displayName ?: cropId }
}

data class CatalogPage(
    val catalogVersion: String,
    val syncedAt: String,
    val items: List<CropCatalogItem>,
    val nextCursor: String?,
    val hasMore: Boolean
)

sealed interface AnalysisError {
    val message: String

    data class Api(
        val httpStatus: Int,
        val errorCode: String?,
        override val message: String,
        val retryAfterSeconds: Long? = null,
        val requestId: String? = null
    ) : AnalysisError {
        val isUnauthorized: Boolean
            get() = httpStatus == 401 || errorCode == "UNAUTHORIZED"

        val isGuestLimitReached: Boolean
            get() = httpStatus == 403 && errorCode == "GUEST_LIMIT_REACHED"

        val isNotFound: Boolean
            get() = httpStatus == 404 || errorCode == "NOT_FOUND"

        val isConflict: Boolean
            get() = httpStatus == 409 || errorCode == "CONFLICT"

        val isCatalogMismatch: Boolean
            get() = errorCode == "CATALOG_VERSION_MISMATCH"

        val isOutsideDemoBoundary: Boolean
            get() = errorCode == "OUTSIDE_DEMO_BOUNDARY"

        val isInsufficientData: Boolean
            get() = errorCode == "INSUFFICIENT_DATA"

        val isRateLimited: Boolean
            get() = httpStatus == 429 || errorCode == "RATE_LIMIT_EXCEEDED"
    }

    data class Network(
        override val message: String
    ) : AnalysisError
}

sealed interface AnalysisCallResult<out T> {
    data class Success<T>(val data: T) : AnalysisCallResult<T>
    data class Failure(val error: AnalysisError) : AnalysisCallResult<Nothing>
}

