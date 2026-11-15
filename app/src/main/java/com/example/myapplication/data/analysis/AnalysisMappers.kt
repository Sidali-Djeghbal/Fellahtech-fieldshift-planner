package com.example.myapplication.data.analysis

import com.example.myapplication.core.common.AppLanguage
import com.example.myapplication.core.network.AnalysisEnvelopeDto
import com.example.myapplication.core.network.AnalysisPollEnvelopeDto
import com.example.myapplication.core.network.AnalysisQueuedResponseDto
import com.example.myapplication.core.network.AnalysisResultDto
import com.example.myapplication.core.network.AnalysisSubmitRequestDto
import com.example.myapplication.core.network.BenefitItemDto
import com.example.myapplication.core.network.CatalogPageDto
import com.example.myapplication.core.network.CropItemDto
import com.example.myapplication.core.network.DataQualityDto
import com.example.myapplication.core.network.DegradedModeMetadataDto
import com.example.myapplication.core.network.EvidenceItemDto
import com.example.myapplication.core.network.ExplanationDto
import com.example.myapplication.core.network.FarmAnalysesPageDto
import com.example.myapplication.core.network.FarmAnalysisSummaryDto
import com.example.myapplication.core.network.FieldPlanDto
import com.example.myapplication.core.network.PlanningDto
import com.example.myapplication.core.network.PollErrorObjectDto
import com.example.myapplication.core.network.PrioritiesDto
import com.example.myapplication.core.network.PriorityWeightsDto
import com.example.myapplication.core.network.ReasonItemDto
import com.example.myapplication.core.network.RequestedCropEvaluationDto
import com.example.myapplication.core.network.RiskItemDto
import com.example.myapplication.core.network.ScenarioOverridesDto
import com.example.myapplication.core.network.SeasonPlanDto
import com.example.myapplication.core.network.StrategyDto
import com.example.myapplication.core.network.StrategyScoresDto
import com.example.myapplication.core.network.StrategySelectionResponseDto
import com.example.myapplication.data.auth.toDomain
import com.example.myapplication.domain.analysis.AnalysisJobStatus
import com.example.myapplication.domain.analysis.AnalysisPollState
import com.example.myapplication.domain.analysis.AnalysisQueuedJob
import com.example.myapplication.domain.analysis.AnalysisResultData
import com.example.myapplication.domain.analysis.AnalysisResultEnvelope
import com.example.myapplication.domain.analysis.AnalysisSubmitInput
import com.example.myapplication.domain.analysis.BenefitItem
import com.example.myapplication.domain.analysis.CatalogPage
import com.example.myapplication.domain.analysis.CropCatalogItem
import com.example.myapplication.domain.analysis.DataQuality
import com.example.myapplication.domain.analysis.DegradedModeInfo
import com.example.myapplication.domain.analysis.EvidenceItem
import com.example.myapplication.domain.analysis.Explanation
import com.example.myapplication.domain.analysis.FarmAnalysesPage
import com.example.myapplication.domain.analysis.FarmAnalysisSummary
import com.example.myapplication.domain.analysis.FieldPlan
import com.example.myapplication.domain.analysis.PollErrorInfo
import com.example.myapplication.domain.analysis.ReasonItem
import com.example.myapplication.domain.analysis.RequestedCropEvaluation
import com.example.myapplication.domain.analysis.RiskItem
import com.example.myapplication.domain.analysis.SeasonPlan
import com.example.myapplication.domain.analysis.SeverityLevel
import com.example.myapplication.domain.analysis.Strategy
import com.example.myapplication.domain.analysis.StrategyScores
import com.example.myapplication.domain.analysis.StrategySelectionResult
import com.example.myapplication.domain.analysis.StrategySelectionStatus
import com.example.myapplication.domain.field.Season
import java.io.IOException
import kotlinx.serialization.json.JsonPrimitive

fun AnalysisSubmitInput.toSubmitRequestDto(): AnalysisSubmitRequestDto = AnalysisSubmitRequestDto(
    farmId = farmId,
    language = language.languageTag,
    planning = PlanningDto(
        startSeason = planning.startSeason.apiValue,
        startYear = planning.startYear,
        horizonSeasons = planning.horizonSeasons,
        cycleMode = planning.cycleMode.apiValue,
        plantingMonth = planning.plantingMonth,
        scenarioOverrides = planning.scenarioOverrides?.let {
            ScenarioOverridesDto(
                tempDeltaC = it.tempDeltaC,
                precipPctDelta = it.precipPctDelta
            )
        }
    ),
    priorities = PrioritiesDto(
        weights = PriorityWeightsDto(
            waterSaving = weights.waterSaving,
            soilImprovement = weights.soilImprovement,
            income = weights.income,
            riskReduction = weights.riskReduction,
            forageValue = weights.forageValue
        ),
        marketPreference = marketPreference.apiValue,
        targetCropIds = targetCropIds,
        excludedCropIds = excludedCropIds,
        equipmentConstraints = equipmentConstraints
    ),
    fieldIds = fieldIds
)

fun AnalysisQueuedResponseDto.toDomain(): AnalysisQueuedJob = AnalysisQueuedJob(
    requestId = requestId,
    status = AnalysisJobStatus.fromApi(status),
    pollUrl = pollUrl,
    pollIntervalMs = pollIntervalMs,
    warnings = warnings.map { it.toDomain() }
)

fun AnalysisPollEnvelopeDto.toDomain(retryAfterSeconds: Long?): AnalysisPollState = AnalysisPollState(
    requestId = requestId,
    status = AnalysisJobStatus.fromApi(status),
    pollIntervalMs = pollIntervalMs,
    retryAfterSeconds = retryAfterSeconds,
    analysisId = analysisId,
    warnings = warnings.map { it.toDomain() },
    degradedMode = degradedMode?.toDomain(),
    error = error?.toDomain(),
    result = result?.toDomain()
)

fun AnalysisEnvelopeDto.toDomain(): AnalysisResultEnvelope = AnalysisResultEnvelope(
    analysisId = analysisId,
    requestId = requestId,
    status = AnalysisJobStatus.fromApi(status),
    datasetVersion = datasetVersion,
    warnings = warnings.map { it.toDomain() },
    degradedMode = degradedMode?.toDomain(),
    result = result.toDomain()
)

fun DegradedModeMetadataDto.toDomain(): DegradedModeInfo = DegradedModeInfo(
    kind = kind,
    stale = stale,
    sourceAnalysisId = sourceAnalysisId,
    createdAt = createdAt,
    datasetVersion = datasetVersion,
    ageSeconds = ageSeconds
)

fun PollErrorObjectDto.toDomain(): PollErrorInfo = PollErrorInfo(
    code = code,
    httpEquivalent = httpEquivalent,
    message = message
)

fun DataQualityDto.toDomain(): DataQuality = DataQuality(
    completenessScore = completenessScore,
    confidenceNote = confidenceNote,
    missingData = missingData,
    warnings = warnings,
    limitations = limitations
)

fun SeasonPlanDto.toDomain(): SeasonPlan = SeasonPlan(
    order = order,
    season = Season.fromApi(season),
    year = year,
    plantingMonth = plantingMonth,
    cropId = cropId,
    cropName = cropName,
    category = category,
    role = role,
    selectionStatus = selectionStatus
)

fun StrategyScoresDto.toDomain(): StrategyScores = StrategyScores(
    waterEfficiency = waterEfficiency,
    erosionProtection = erosionProtection,
    organicMatterGain = organicMatterGain,
    nitrogenContribution = nitrogenContribution,
    pestCycleDisruption = pestCycleDisruption,
    incomeForageValue = incomeForageValue,
    priorityFit = priorityFit,
    bareFieldDaysPerYear = bareFieldDaysPerYear
)

fun ReasonItemDto.toDomain(): ReasonItem = ReasonItem(code = code, text = text)

fun EvidenceItemDto.toDomain(): EvidenceItem {
    val obs = when (val elem = observedValue) {
        is JsonPrimitive -> elem.content
        else -> elem.toString()
    }
    return EvidenceItem(
        dataSource = dataSource,
        sourceMission = sourceMission,
        parameter = parameter,
        observedValue = obs,
        unit = unit,
        period = period,
        interpretation = interpretation
    )
}

fun BenefitItemDto.toDomain(): BenefitItem = BenefitItem(
    benefitId = benefitId,
    title = title,
    description = description
)

fun RiskItemDto.toDomain(): RiskItem = RiskItem(
    riskId = riskId,
    title = title,
    description = description,
    severity = SeverityLevel.fromApi(severity),
    likelihood = likelihood?.let { SeverityLevel.fromApi(it) },
    mitigation = mitigation
)

fun ExplanationDto.toDomain(): Explanation = Explanation(
    reasons = reasons.map { it.toDomain() },
    evidence = evidence.map { it.toDomain() },
    benefits = benefits.map { it.toDomain() },
    risks = risks.map { it.toDomain() },
    assumptions = assumptions,
    informationGaps = informationGaps,
    needsLocalReview = needsLocalReview
)

fun StrategyDto.toDomain(): Strategy = Strategy(
    strategyId = strategyId,
    name = name,
    isExistingRotation = isExistingRotation,
    description = description,
    seasons = seasons.map { it.toDomain() },
    scores = scores.toDomain(),
    confidence = SeverityLevel.fromApi(confidence),
    explanation = explanation.toDomain()
)

fun RequestedCropEvaluationDto.toDomain(): RequestedCropEvaluation = RequestedCropEvaluation(
    requestedCropId = requestedCropId,
    outcome = outcome,
    includedInStrategyIds = includedInStrategyIds,
    replacedByCropId = replacedByCropId,
    explanation = explanation
)

fun FieldPlanDto.toDomain(): FieldPlan = FieldPlan(
    fieldId = fieldId,
    fieldName = fieldName,
    status = AnalysisJobStatus.fromApi(status),
    partialReason = partialReason,
    climateTrendSummary = fieldInsights.climateTrendSummary,
    strategies = strategies.map { it.toDomain() },
    suggestedStrategyId = suggestedStrategyId,
    requestedCropResults = requestedCropResults.map { it.toDomain() },
    dataQuality = dataQuality.toDomain()
)

fun AnalysisResultDto.toDomain(): AnalysisResultData = AnalysisResultData(
    schemaVersion = schemaVersion,
    requestId = requestId,
    datasetVersionUsed = datasetVersionUsed,
    generatedAt = generatedAt,
    status = AnalysisJobStatus.fromApi(status),
    language = AppLanguage.fromLanguageTag(language),
    mlEngineVersion = mlEngineVersion,
    overallSummary = overallSummary,
    disclaimer = disclaimer,
    fieldPlans = fieldPlans.map { it.toDomain() },
    dataQuality = dataQuality.toDomain()
)

fun FarmAnalysisSummaryDto.toDomain(): FarmAnalysisSummary = FarmAnalysisSummary(
    requestId = requestId,
    analysisId = analysisId,
    status = AnalysisJobStatus.fromApi(status),
    language = AppLanguage.fromLanguageTag(language),
    catalogVersion = catalogVersion,
    datasetVersion = datasetVersion,
    mlEngineVersion = mlEngineVersion,
    warnings = warnings.map { it.toDomain() },
    createdAt = createdAt,
    durationMs = durationMs
)

fun FarmAnalysesPageDto.toDomain(): FarmAnalysesPage = FarmAnalysesPage(
    items = items.map { it.toDomain() },
    nextCursor = nextCursor,
    hasMore = hasMore
)

fun CropItemDto.toDomain(): CropCatalogItem = CropCatalogItem(
    cropId = cropId,
    displayName = displayName,
    nameEn = names.en,
    nameFr = names.fr,
    nameAr = names.ar,
    category = category,
    roles = roles,
    family = family
)

fun CatalogPageDto.toDomain(): CatalogPage = CatalogPage(
    catalogVersion = catalogVersion,
    syncedAt = syncedAt,
    items = items.map { it.toDomain() },
    nextCursor = nextCursor,
    hasMore = hasMore
)

fun StrategySelectionResponseDto.toDomain(): StrategySelectionResult {
    val mappedStatus = StrategySelectionStatus.fromApiOrNull(selectionStatus)
        ?: throw IOException("Unexpected selection_status: $selectionStatus")
    return StrategySelectionResult(
        analysisId = analysisId,
        fieldId = fieldId,
        strategyId = strategyId,
        selectionStatus = mappedStatus
    )
}

