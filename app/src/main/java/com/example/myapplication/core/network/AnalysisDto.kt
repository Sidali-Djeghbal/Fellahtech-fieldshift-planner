package com.example.myapplication.core.network

import kotlinx.serialization.EncodeDefault
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class ScenarioOverridesDto(
    @SerialName("temp_delta_c") val tempDeltaC: Double = 0.0,
    @SerialName("precip_pct_delta") val precipPctDelta: Double = 0.0
)

@Serializable
data class PlanningDto(
    @SerialName("start_season") val startSeason: String,
    @SerialName("start_year") val startYear: Int,
    @SerialName("horizon_seasons") val horizonSeasons: Int,
    @SerialName("cycle_mode") val cycleMode: String = "annual_rotation",
    @SerialName("planting_month") val plantingMonth: Int? = null,
    @SerialName("scenario_overrides") val scenarioOverrides: ScenarioOverridesDto? = null
)

@Serializable
data class PriorityWeightsDto(
    @SerialName("water_saving") val waterSaving: Int,
    @SerialName("soil_improvement") val soilImprovement: Int,
    @SerialName("income") val income: Int,
    @SerialName("risk_reduction") val riskReduction: Int,
    @SerialName("forage_value") val forageValue: Int
)

@OptIn(ExperimentalSerializationApi::class)
@Serializable
data class PrioritiesDto(
    @SerialName("weights") val weights: PriorityWeightsDto,
    @SerialName("market_preference") val marketPreference: String,
    @EncodeDefault(EncodeDefault.Mode.ALWAYS)
    @SerialName("target_crop_ids") val targetCropIds: List<String> = emptyList(),
    @EncodeDefault(EncodeDefault.Mode.ALWAYS)
    @SerialName("excluded_crop_ids") val excludedCropIds: List<String> = emptyList(),
    @EncodeDefault(EncodeDefault.Mode.ALWAYS)
    @SerialName("equipment_constraints") val equipmentConstraints: List<String> = emptyList()
)

@Serializable
data class AnalysisSubmitRequestDto(
    @SerialName("farm_id") val farmId: String,
    @SerialName("language") val language: String,
    @SerialName("planning") val planning: PlanningDto,
    @SerialName("priorities") val priorities: PrioritiesDto,
    @SerialName("field_ids") val fieldIds: List<String>
)

@Serializable
data class AnalysisQueuedResponseDto(
    @SerialName("request_id") val requestId: String,
    @SerialName("status") val status: String,
    @SerialName("poll_url") val pollUrl: String,
    @SerialName("poll_interval_ms") val pollIntervalMs: Long,
    @SerialName("warnings") val warnings: List<WarningNoticeDto> = emptyList()
)

@Serializable
data class AnalysisCancelResponseDto(
    @SerialName("request_id") val requestId: String,
    @SerialName("status") val status: String
)

@Serializable
data class DegradedModeMetadataDto(
    @SerialName("kind") val kind: String,
    @SerialName("stale") val stale: Boolean,
    @SerialName("source_analysis_id") val sourceAnalysisId: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("dataset_version") val datasetVersion: String,
    @SerialName("age_seconds") val ageSeconds: Long
)

@Serializable
data class PollErrorObjectDto(
    @SerialName("code") val code: String,
    @SerialName("http_equivalent") val httpEquivalent: Int,
    @SerialName("message") val message: String,
    @SerialName("details") val details: List<JsonElement> = emptyList()
)

@Serializable
data class DataQualityDto(
    @SerialName("completeness_score") val completenessScore: Double? = null,
    @SerialName("confidence_note") val confidenceNote: String? = null,
    @SerialName("missing_data") val missingData: List<String> = emptyList(),
    @SerialName("warnings") val warnings: List<String> = emptyList(),
    @SerialName("limitations") val limitations: List<String> = emptyList()
)

@Serializable
data class FieldInsightsDto(
    @SerialName("climate_trend_summary") val climateTrendSummary: String
)

@Serializable
data class SeasonPlanDto(
    @SerialName("order") val order: Int,
    @SerialName("season") val season: String,
    @SerialName("year") val year: Int,
    @SerialName("planting_month") val plantingMonth: Int? = null,
    @SerialName("crop_id") val cropId: String,
    @SerialName("crop_name") val cropName: String,
    @SerialName("category") val category: String,
    @SerialName("role") val role: String,
    @SerialName("selection_status") val selectionStatus: String
)

@Serializable
data class StrategyScoresDto(
    @SerialName("water_efficiency") val waterEfficiency: Double,
    @SerialName("erosion_protection") val erosionProtection: Double,
    @SerialName("organic_matter_gain") val organicMatterGain: Double,
    @SerialName("nitrogen_contribution") val nitrogenContribution: Double,
    @SerialName("pest_cycle_disruption") val pestCycleDisruption: Double,
    @SerialName("income_forage_value") val incomeForageValue: Double,
    @SerialName("priority_fit") val priorityFit: Double,
    @SerialName("bare_field_days_per_year") val bareFieldDaysPerYear: Int
)

@Serializable
data class ReasonItemDto(
    @SerialName("code") val code: String,
    @SerialName("text") val text: String
)

@Serializable
data class EvidenceItemDto(
    @SerialName("data_source") val dataSource: String,
    @SerialName("source_mission") val sourceMission: String? = null,
    @SerialName("parameter") val parameter: String,
    @SerialName("observed_value") val observedValue: JsonElement,
    @SerialName("unit") val unit: String? = null,
    @SerialName("period") val period: String? = null,
    @SerialName("interpretation") val interpretation: String
)

@Serializable
data class BenefitItemDto(
    @SerialName("benefit_id") val benefitId: String,
    @SerialName("title") val title: String,
    @SerialName("description") val description: String
)

@Serializable
data class RiskItemDto(
    @SerialName("risk_id") val riskId: String,
    @SerialName("title") val title: String,
    @SerialName("description") val description: String,
    @SerialName("severity") val severity: String,
    @SerialName("likelihood") val likelihood: String? = null,
    @SerialName("mitigation") val mitigation: String
)

@Serializable
data class ExplanationDto(
    @SerialName("reasons") val reasons: List<ReasonItemDto> = emptyList(),
    @SerialName("evidence") val evidence: List<EvidenceItemDto> = emptyList(),
    @SerialName("benefits") val benefits: List<BenefitItemDto> = emptyList(),
    @SerialName("risks") val risks: List<RiskItemDto> = emptyList(),
    @SerialName("assumptions") val assumptions: List<String> = emptyList(),
    @SerialName("information_gaps") val informationGaps: List<String> = emptyList(),
    @SerialName("needs_local_review") val needsLocalReview: List<String> = emptyList()
)

@Serializable
data class StrategyDto(
    @SerialName("strategy_id") val strategyId: String,
    @SerialName("name") val name: String,
    @SerialName("is_existing_rotation") val isExistingRotation: Boolean,
    @SerialName("description") val description: String,
    @SerialName("seasons") val seasons: List<SeasonPlanDto> = emptyList(),
    @SerialName("scores") val scores: StrategyScoresDto,
    @SerialName("confidence") val confidence: String,
    @SerialName("explanation") val explanation: ExplanationDto
)

@Serializable
data class RequestedCropEvaluationDto(
    @SerialName("requested_crop_id") val requestedCropId: String,
    @SerialName("outcome") val outcome: String,
    @SerialName("included_in_strategy_ids") val includedInStrategyIds: List<String> = emptyList(),
    @SerialName("replaced_by_crop_id") val replacedByCropId: String? = null,
    @SerialName("explanation") val explanation: String
)

@Serializable
data class FieldPlanDto(
    @SerialName("field_id") val fieldId: String,
    @SerialName("field_name") val fieldName: String,
    @SerialName("status") val status: String,
    @SerialName("partial_reason") val partialReason: String? = null,
    @SerialName("field_insights") val fieldInsights: FieldInsightsDto,
    @SerialName("strategies") val strategies: List<StrategyDto> = emptyList(),
    @SerialName("suggested_strategy_id") val suggestedStrategyId: String? = null,
    @SerialName("requested_crop_results") val requestedCropResults: List<RequestedCropEvaluationDto> = emptyList(),
    @SerialName("data_quality") val dataQuality: DataQualityDto
)

@Serializable
data class AnalysisResultDto(
    @SerialName("schema_version") val schemaVersion: String,
    @SerialName("request_id") val requestId: String,
    @SerialName("dataset_version_used") val datasetVersionUsed: String,
    @SerialName("generated_at") val generatedAt: String,
    @SerialName("status") val status: String,
    @SerialName("language") val language: String,
    @SerialName("ml_engine_version") val mlEngineVersion: String,
    @SerialName("overall_summary") val overallSummary: String,
    @SerialName("disclaimer") val disclaimer: String,
    @SerialName("field_plans") val fieldPlans: List<FieldPlanDto> = emptyList(),
    @SerialName("data_quality") val dataQuality: DataQualityDto
)

@Serializable
data class AnalysisEnvelopeDto(
    @SerialName("analysis_id") val analysisId: String,
    @SerialName("request_id") val requestId: String,
    @SerialName("status") val status: String,
    @SerialName("dataset_version") val datasetVersion: String,
    @SerialName("warnings") val warnings: List<WarningNoticeDto> = emptyList(),
    @SerialName("degraded_mode") val degradedMode: DegradedModeMetadataDto? = null,
    @SerialName("result") val result: AnalysisResultDto
)

@Serializable
data class AnalysisPollEnvelopeDto(
    @SerialName("request_id") val requestId: String,
    @SerialName("status") val status: String,
    @SerialName("poll_interval_ms") val pollIntervalMs: Long? = null,
    @SerialName("analysis_id") val analysisId: String? = null,
    @SerialName("warnings") val warnings: List<WarningNoticeDto> = emptyList(),
    @SerialName("degraded_mode") val degradedMode: DegradedModeMetadataDto? = null,
    @SerialName("error") val error: PollErrorObjectDto? = null,
    @SerialName("result") val result: AnalysisResultDto? = null
)

@Serializable
data class FarmAnalysisSummaryDto(
    @SerialName("request_id") val requestId: String,
    @SerialName("analysis_id") val analysisId: String? = null,
    @SerialName("status") val status: String,
    @SerialName("language") val language: String,
    @SerialName("catalog_version") val catalogVersion: String,
    @SerialName("dataset_version") val datasetVersion: String? = null,
    @SerialName("ml_engine_version") val mlEngineVersion: String? = null,
    @SerialName("warnings") val warnings: List<WarningNoticeDto> = emptyList(),
    @SerialName("created_at") val createdAt: String,
    @SerialName("duration_ms") val durationMs: Long? = null
)

@Serializable
data class FarmAnalysesPageDto(
    @SerialName("items") val items: List<FarmAnalysisSummaryDto> = emptyList(),
    @SerialName("next_cursor") val nextCursor: String? = null,
    @SerialName("has_more") val hasMore: Boolean
)

@Serializable
data class CropNamesDto(
    @SerialName("en") val en: String,
    @SerialName("fr") val fr: String,
    @SerialName("ar") val ar: String
)

@Serializable
data class CropItemDto(
    @SerialName("crop_id") val cropId: String,
    @SerialName("display_name") val displayName: String? = null,
    @SerialName("names") val names: CropNamesDto,
    @SerialName("category") val category: String,
    @SerialName("roles") val roles: List<String> = emptyList(),
    @SerialName("family") val family: String
)

@Serializable
data class CatalogPageDto(
    @SerialName("catalog_version") val catalogVersion: String,
    @SerialName("synced_at") val syncedAt: String,
    @SerialName("items") val items: List<CropItemDto> = emptyList(),
    @SerialName("next_cursor") val nextCursor: String? = null,
    @SerialName("has_more") val hasMore: Boolean
)

