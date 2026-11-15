package com.example.myapplication

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import com.example.myapplication.core.common.AppLanguage
import com.example.myapplication.core.common.UiState
import com.example.myapplication.core.network.AnalysisApiService
import com.example.myapplication.core.network.AnalysisCancelResponseDto
import com.example.myapplication.core.network.AnalysisEnvelopeDto
import com.example.myapplication.core.network.AnalysisPollEnvelopeDto
import com.example.myapplication.core.network.AnalysisQueuedResponseDto
import com.example.myapplication.core.network.AnalysisResultDto
import com.example.myapplication.core.network.AnalysisSubmitRequestDto
import com.example.myapplication.core.network.ApiErrorParser
import com.example.myapplication.core.network.CatalogPageDto
import com.example.myapplication.core.network.CropItemDto
import com.example.myapplication.core.network.CropNamesDto
import com.example.myapplication.core.network.DataQualityDto
import com.example.myapplication.core.network.DegradedModeMetadataDto
import com.example.myapplication.core.network.FarmAnalysesPageDto
import com.example.myapplication.core.network.FieldInsightsDto
import com.example.myapplication.core.network.FieldPlanDto
import com.example.myapplication.core.network.NetworkModule
import com.example.myapplication.core.network.PlanningDto
import com.example.myapplication.core.network.PrioritiesDto
import com.example.myapplication.core.network.PriorityWeightsDto
import com.example.myapplication.core.network.StrategySelectionRequestDto
import com.example.myapplication.core.network.StrategySelectionResponseDto
import com.example.myapplication.data.analysis.ActiveAnalysisStore
import com.example.myapplication.data.analysis.AnalysisRepositoryImpl
import com.example.myapplication.data.analysis.DataStoreActiveAnalysisStore
import com.example.myapplication.data.analysis.toDomain
import com.example.myapplication.domain.analysis.ActiveAnalysisRequest
import com.example.myapplication.domain.analysis.AnalysisCallResult
import com.example.myapplication.domain.analysis.AnalysisError
import com.example.myapplication.domain.analysis.AnalysisJobStatus
import com.example.myapplication.domain.analysis.AnalysisPollState
import com.example.myapplication.domain.analysis.AnalysisQueuedJob
import com.example.myapplication.domain.analysis.AnalysisRepository
import com.example.myapplication.domain.analysis.AnalysisResultData
import com.example.myapplication.domain.analysis.AnalysisResultEnvelope
import com.example.myapplication.domain.analysis.AnalysisSubmitInput
import com.example.myapplication.domain.analysis.CatalogPage
import com.example.myapplication.domain.analysis.CropCatalogItem
import com.example.myapplication.domain.analysis.CycleMode
import com.example.myapplication.domain.analysis.DataQuality
import com.example.myapplication.domain.analysis.DegradedModeInfo
import com.example.myapplication.domain.analysis.Explanation
import com.example.myapplication.domain.analysis.FarmAnalysesPage
import com.example.myapplication.domain.analysis.FarmAnalysisSummary
import com.example.myapplication.domain.analysis.FieldPlan
import com.example.myapplication.domain.analysis.MarketPreference
import com.example.myapplication.domain.analysis.PlanningConfig
import com.example.myapplication.domain.analysis.PollErrorInfo
import com.example.myapplication.domain.analysis.PriorityWeights
import com.example.myapplication.domain.analysis.SeasonPlan
import com.example.myapplication.domain.analysis.SeverityLevel
import com.example.myapplication.domain.analysis.Strategy
import com.example.myapplication.domain.analysis.StrategyDisplaySelection
import com.example.myapplication.domain.analysis.StrategyScores
import com.example.myapplication.domain.analysis.StrategySelectionResult
import com.example.myapplication.domain.analysis.StrategySelectionStatus
import com.example.myapplication.domain.auth.WarningNotice
import com.example.myapplication.domain.farm.Farm
import com.example.myapplication.domain.farm.FarmPage
import com.example.myapplication.domain.farm.FarmRepository
import com.example.myapplication.domain.farm.FarmResult
import com.example.myapplication.domain.farm.FarmWriteInput
import com.example.myapplication.domain.field.FieldLocation
import com.example.myapplication.domain.field.FieldPage
import com.example.myapplication.domain.field.FieldRepository
import com.example.myapplication.domain.field.FieldResult
import com.example.myapplication.domain.field.FieldSoil
import com.example.myapplication.domain.field.FieldSummary
import com.example.myapplication.domain.field.FieldWater
import com.example.myapplication.domain.field.FieldWriteInput
import com.example.myapplication.domain.field.IrrigationSystem
import com.example.myapplication.domain.field.Season
import com.example.myapplication.domain.field.SoilSource
import com.example.myapplication.domain.field.SoilType
import com.example.myapplication.domain.field.WaterAvailability
import com.example.myapplication.domain.field.WaterSource
import com.example.myapplication.feature.analysis.AnalysisConfigViewModel
import com.example.myapplication.feature.analysis.AnalysisHistoryViewModel
import com.example.myapplication.feature.analysis.AnalysisProgressViewModel
import com.example.myapplication.feature.analysis.AnalysisResultViewModel
import com.example.myapplication.feature.analysis.AnalysisValidationError
import com.example.myapplication.feature.analysis.HistoryItemAction
import java.io.IOException
import java.nio.file.Files
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.Headers
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.ResponseBody.Companion.toResponseBody
import okio.Buffer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

@OptIn(ExperimentalCoroutinesApi::class)
class AnalysisManagementTest {

    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        encodeDefaults = true
    }

    @Test
    fun `analysis DTOs serialize and deserialize OpenAPI v3_2 and ML contract v5_0`() {
        val submitDto = AnalysisSubmitRequestDto(
            farmId = "farm_1",
            language = "fr",
            planning = PlanningDto(
                startSeason = "autumn",
                startYear = 2026,
                horizonSeasons = 3,
                cycleMode = "annual_rotation"
            ),
            priorities = PrioritiesDto(
                weights = PriorityWeightsDto(80, 70, 90, 75, 40),
                marketPreference = "mixed",
                targetCropIds = listOf("durum_wheat"),
                excludedCropIds = emptyList(),
                equipmentConstraints = listOf("no_till")
            ),
            fieldIds = listOf("field_01")
        )
        val encoded = json.encodeToString(submitDto)
        assertTrue(encoded.contains("\"farm_id\":\"farm_1\""))
        assertTrue(encoded.contains("\"horizon_seasons\":3"))
        assertTrue(encoded.contains("\"market_preference\":\"mixed\""))

        val envelopeJson = """
            {
              "analysis_id": "analysis_0123456789ab",
              "request_id": "11111111-1111-1111-1111-111111111111",
              "status": "partial",
              "dataset_version": "ds_2026_10",
              "warnings": [{"code": "MVP_OUTSIDE_COVERAGE", "message": "Outside MVP"}],
              "degraded_mode": {
                "kind": "last_good_replay",
                "stale": true,
                "source_analysis_id": "analysis_abcdefabcdef",
                "created_at": "2026-10-01T10:00:00Z",
                "dataset_version": "ds_2026_09",
                "age_seconds": 120
              },
              "result": {
                "schema_version": "5.0",
                "request_id": "11111111-1111-1111-1111-111111111111",
                "dataset_version_used": "ds_2026_09",
                "generated_at": "2026-10-01T10:00:00Z",
                "status": "partial",
                "language": "fr",
                "ml_engine_version": "ml-5.0.1",
                "overall_summary": "Partial summary",
                "disclaimer": "Advisory only",
                "field_plans": [
                  {
                    "field_id": "field_01",
                    "field_name": "North Plot",
                    "status": "partial",
                    "partial_reason": "Missing recent soil lab data",
                    "field_insights": {"climate_trend_summary": "Dry autumn"},
                    "strategies": [],
                    "suggested_strategy_id": null,
                    "requested_crop_results": [],
                    "data_quality": {"missing_data": ["soil_ph"], "warnings": [], "limitations": []}
                  }
                ],
                "data_quality": {"missing_data": [], "warnings": [], "limitations": []}
              }
            }
        """.trimIndent()

        val envelope = json.decodeFromString<AnalysisEnvelopeDto>(envelopeJson).toDomain()
        assertEquals(AnalysisJobStatus.PARTIAL, envelope.status)
        assertNotNull(envelope.degradedMode)
        assertEquals(120L, envelope.degradedMode?.ageSeconds)
        assertEquals("Missing recent soil lab data", envelope.result.fieldPlans.first().partialReason)
        assertEquals(AppLanguage.FRENCH, envelope.result.language)
    }

    @Test
    fun `AnalysisRepositoryImpl parses Retry-After and maps 403 409 422 429 and IOException`() = runTest {
        val api = FakeAnalysisApiService()
        val store = InMemoryActiveAnalysisStore()
        val repo = AnalysisRepositoryImpl(api, store, ApiErrorParser(json))

        api.pollResponse = Response.success(
            AnalysisPollEnvelopeDto(
                requestId = "req-1",
                status = "running",
                pollIntervalMs = 2000L
            ),
            Headers.headersOf("Retry-After", "4")
        )
        val poll = repo.pollAnalysisRequest("req-1") as AnalysisCallResult.Success
        assertEquals(4L, poll.data.retryAfterSeconds)
        assertEquals(AnalysisJobStatus.RUNNING, poll.data.status)

        api.submitException = httpException(
            403,
            """{"error":{"code":"GUEST_LIMIT_REACHED","message":"Guest limit"}}"""
        )
        val guestErr = repo.submitAnalysis(sampleSubmitInput(), "key-1") as AnalysisCallResult.Failure
        assertTrue((guestErr.error as AnalysisError.Api).isGuestLimitReached)

        api.submitException = httpException(
            409,
            """{"error":{"code":"CATALOG_VERSION_MISMATCH","message":"Catalog mismatch"}}"""
        )
        val mismatchErr = repo.submitAnalysis(sampleSubmitInput(), "key-1") as AnalysisCallResult.Failure
        assertTrue((mismatchErr.error as AnalysisError.Api).isCatalogMismatch)

        api.submitException = httpException(
            422,
            """{"error":{"code":"INSUFFICIENT_DATA","message":"Not enough data"}}"""
        )
        val insufficient = repo.submitAnalysis(sampleSubmitInput(), "key-1") as AnalysisCallResult.Failure
        assertTrue((insufficient.error as AnalysisError.Api).isInsufficientData)

        api.pollException = httpException(
            429,
            """{"error":{"code":"RATE_LIMIT_EXCEEDED","message":"Slow down"}}""",
            retryAfter = "7"
        )
        val rateLimited = repo.pollAnalysisRequest("req-1") as AnalysisCallResult.Failure
        val apiErr = rateLimited.error as AnalysisError.Api
        assertTrue(apiErr.isRateLimited)
        assertEquals(7L, apiErr.retryAfterSeconds)

        api.pollException = IOException("Offline")
        val netErr = repo.pollAnalysisRequest("req-1") as AnalysisCallResult.Failure
        assertTrue(netErr.error is AnalysisError.Network)
    }

    @Test
    fun `AnalysisConfigViewModel validates inputs, preserves Idempotency-Key across retries, and prevents duplicate submits`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val farmRepo = FakeFarmRepository(listOf(Farm("farm_1", "Atlas Farm", "DZ", "Guelma", null, 1, "2026-10-01T00:00:00Z")))
            val fieldRepo = FakeFieldRepository(listOf(sampleFieldSummary("f1", "North Plot")))
            val analysisRepo = FakeAnalysisRepository()
            analysisRepo.catalogResult = AnalysisCallResult.Success(
                CatalogPage(
                    catalogVersion = "v1",
                    syncedAt = "2026-10-01T00:00:00Z",
                    items = listOf(
                        CropCatalogItem("wheat", "Wheat", "Wheat", "Blé", "قمح", "cereals", listOf("main_crop"), "Poaceae")
                    ),
                    nextCursor = null,
                    hasMore = false
                )
            )

            val vm = AnalysisConfigViewModel(farmRepo, fieldRepo, analysisRepo)
            vm.initialize(AppLanguage.ARABIC)
            advanceUntilIdle()

            assertEquals("قمح", vm.uiState.value.catalogItems.first().localizedName(AppLanguage.ARABIC))
            assertEquals("farm_1", vm.uiState.value.selectedFarmId)
            assertEquals(setOf("f1"), vm.uiState.value.selectedFieldIds)

            // Validation checks
            vm.onStartYearChanged("1999")
            vm.submit()
            assertEquals(AnalysisValidationError.START_YEAR_INVALID, vm.uiState.value.validationError)

            vm.onStartYearChanged("2026")
            // Retry preserves the same Idempotency-Key on transient network failure
            analysisRepo.submitResult = AnalysisCallResult.Failure(AnalysisError.Network("Timeout"))
            vm.submit()
            advanceUntilIdle()
            val firstKey = analysisRepo.lastIdempotencyKey
            assertNotNull(firstKey)
            assertNotNull(vm.uiState.value.submitError)

            // Retry same config -> exact same key
            val gate = CompletableDeferred<AnalysisCallResult<AnalysisQueuedJob>>()
            analysisRepo.deferredSubmit = gate
            vm.submit()
            runCurrent()
            assertTrue(vm.uiState.value.isSubmitting)
            // Duplicate submit while in flight is ignored
            vm.submit()
            assertEquals(2, analysisRepo.submitCalls)
            assertEquals(firstKey, analysisRepo.lastIdempotencyKey)

            gate.complete(
                AnalysisCallResult.Success(
                    AnalysisQueuedJob("req-uuid-1", AnalysisJobStatus.PENDING, "/analysis/requests/req-uuid-1", 1500L, emptyList())
                )
            )
            advanceUntilIdle()
            assertFalse(vm.uiState.value.isSubmitting)
            assertEquals("req-uuid-1", vm.uiState.value.queuedJob?.requestId)
            assertEquals("req-uuid-1", analysisRepo.activeRequest?.requestId)

            // Modifying config generates a new key on next submit
            vm.onHorizonChanged(4)
            analysisRepo.deferredSubmit = null
            analysisRepo.submitResult = AnalysisCallResult.Success(
                AnalysisQueuedJob("req-uuid-2", AnalysisJobStatus.PENDING, "/analysis/requests/req-uuid-2", 1500L, emptyList())
            )
            vm.submit()
            advanceUntilIdle()
            assertNotEquals(firstKey, analysisRepo.lastIdempotencyKey)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `AnalysisProgressViewModel pauses on background, respects Retry-After, handles network errors without resubmit, and resolves 409 cancel`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val analysisRepo = FakeAnalysisRepository()
            analysisRepo.activeRequest = ActiveAnalysisRequest("req-1", "farm_1", 1000L, 100L)
            analysisRepo.pollResponses.addAll(
                listOf(
                    AnalysisCallResult.Success(
                        AnalysisPollState("req-1", AnalysisJobStatus.PENDING, 1000L, 3L, null, emptyList(), null, null, null)
                    ),
                    AnalysisCallResult.Failure(AnalysisError.Network("Temporary drop")),
                    AnalysisCallResult.Success(
                        AnalysisPollState("req-1", AnalysisJobStatus.RUNNING, 1000L, null, null, emptyList(), null, null, null)
                    )
                )
            )

            val vm = AnalysisProgressViewModel(analysisRepo)
            vm.initialize("req-1")
            vm.setForegroundActive(true)
            runCurrent()

            // First poll returned Retry-After: 3 (3000ms > 1000ms)
            assertEquals(1, analysisRepo.pollCalls)
            assertEquals(0, analysisRepo.submitCalls)
            assertNotNull(analysisRepo.activeRequest)

            // Before 3000ms elapses, should not poll again
            advanceTimeBy(2500L)
            runCurrent()
            assertEquals(1, analysisRepo.pollCalls)

            // At 3000ms, second poll runs and hits Network error -> activeRequest still preserved, no resubmit
            advanceTimeBy(600L)
            runCurrent()
            assertEquals(2, analysisRepo.pollCalls)
            assertEquals(0, analysisRepo.submitCalls)
            assertNotNull(analysisRepo.activeRequest)
            assertTrue(vm.uiState.value.transportError is AnalysisError.Network)

            // Backgrounding pauses polling
            vm.setForegroundActive(false)
            advanceTimeBy(10_000L)
            runCurrent()
            assertEquals(2, analysisRepo.pollCalls)

            // Returning to foreground resumes polling
            vm.setForegroundActive(true)
            runCurrent()
            assertEquals(3, analysisRepo.pollCalls)
            assertEquals(AnalysisJobStatus.RUNNING, vm.uiState.value.status)

            // Cancel returns 409 -> fetches latest state and discovers job completed OK!
            analysisRepo.cancelResult = AnalysisCallResult.Failure(
                AnalysisError.Api(409, "CONFLICT", "Already completed")
            )
            analysisRepo.pollResponses.add(
                AnalysisCallResult.Success(
                    AnalysisPollState("req-1", AnalysisJobStatus.OK, null, null, "analysis_0123456789ab", emptyList(), null, null, null)
                )
            )
            vm.cancelAnalysis()
            advanceUntilIdle()
            assertEquals(AnalysisJobStatus.OK, vm.uiState.value.status)
            assertEquals("analysis_0123456789ab", vm.uiState.value.analysisId)
            assertNull(analysisRepo.activeRequest)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `AnalysisResultViewModel loads partial and degraded results and handles 404`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val analysisRepo = FakeAnalysisRepository()
            val vm = AnalysisResultViewModel(analysisRepo)

            analysisRepo.resultResponse = AnalysisCallResult.Failure(
                AnalysisError.Api(404, "NOT_FOUND", "Not found")
            )
            vm.loadResult("analysis_missing")
            advanceUntilIdle()
            assertTrue(vm.uiState.value.envelopeState is UiState.Error)
            assertTrue((vm.uiState.value.error as AnalysisError.Api).isNotFound)

            val partialEnvelope = AnalysisResultEnvelope(
                analysisId = "analysis_0123456789ab",
                requestId = "req-1",
                status = AnalysisJobStatus.PARTIAL,
                datasetVersion = "ds_1",
                warnings = listOf(WarningNotice("MVP_OUTSIDE_COVERAGE", "Outside MVP", emptyList())),
                degradedMode = DegradedModeInfo("last_good_replay", true, "analysis_old", "2026-10-01T00:00:00Z", "ds_0", 90L),
                result = AnalysisResultData(
                    schemaVersion = "5.0",
                    requestId = "req-1",
                    datasetVersionUsed = "ds_0",
                    generatedAt = "2026-10-01T00:00:00Z",
                    status = AnalysisJobStatus.PARTIAL,
                    language = AppLanguage.ENGLISH,
                    mlEngineVersion = "5.0.0",
                    overallSummary = "Summary",
                    disclaimer = "Disclaimer",
                    fieldPlans = listOf(
                        FieldPlan(
                            fieldId = "f1",
                            fieldName = "North Plot",
                            status = AnalysisJobStatus.PARTIAL,
                            partialReason = "No lab test",
                            climateTrendSummary = "Dry",
                            strategies = emptyList(),
                            suggestedStrategyId = null,
                            requestedCropResults = emptyList(),
                            dataQuality = DataQuality(0.7, null, emptyList(), emptyList(), emptyList())
                        )
                    ),
                    dataQuality = DataQuality(0.7, null, emptyList(), emptyList(), emptyList())
                )
            )
            analysisRepo.resultResponse = AnalysisCallResult.Success(partialEnvelope)
            vm.loadResult("analysis_0123456789ab", forceRefresh = true)
            advanceUntilIdle()
            val success = vm.uiState.value.envelopeState as UiState.Success
            assertEquals(AnalysisJobStatus.PARTIAL, success.data.status)
            assertEquals(90L, success.data.degradedMode?.ageSeconds)
            assertEquals(1, success.data.warnings.size)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `NetworkModule provideJson serializes required empty priorities arrays for OpenAPI v3_2`() {
        val prodJson = NetworkModule.provideJson()
        val submitDto = AnalysisSubmitRequestDto(
            farmId = "farm_1",
            language = "en",
            planning = PlanningDto(
                startSeason = "autumn",
                startYear = 2026,
                horizonSeasons = 3
            ),
            priorities = PrioritiesDto(
                weights = PriorityWeightsDto(80, 70, 90, 75, 40),
                marketPreference = "mixed"
            ),
            fieldIds = listOf("field_01")
        )

        val encoded = prodJson.encodeToString(submitDto)
        val root = prodJson.parseToJsonElement(encoded).jsonObject
        val priorities = root.getValue("priorities").jsonObject

        assertTrue(priorities.containsKey("target_crop_ids"))
        assertTrue(priorities.containsKey("excluded_crop_ids"))
        assertTrue(priorities.containsKey("equipment_constraints"))
        assertEquals(0, priorities.getValue("target_crop_ids").jsonArray.size)
        assertEquals(0, priorities.getValue("excluded_crop_ids").jsonArray.size)
        assertEquals(0, priorities.getValue("equipment_constraints").jsonArray.size)
    }

    @Test
    fun `AnalysisConfigViewModel invalidates Idempotency-Key when language changes and preserves on same-language reinit`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val farmRepo = FakeFarmRepository(listOf(Farm("farm_1", "Atlas Farm", "DZ", "Guelma", null, 1, "2026-10-01T00:00:00Z")))
            val fieldRepo = FakeFieldRepository(listOf(sampleFieldSummary("f1", "North Plot")))
            val analysisRepo = FakeAnalysisRepository()
            analysisRepo.submitResult = AnalysisCallResult.Failure(AnalysisError.Network("Timeout"))

            val vm = AnalysisConfigViewModel(farmRepo, fieldRepo, analysisRepo)
            vm.initialize(AppLanguage.ENGLISH)
            advanceUntilIdle()

            vm.submit()
            advanceUntilIdle()
            val firstKey = analysisRepo.lastIdempotencyKey
            assertNotNull(firstKey)

            // Same-language re-initialization preserves the existing key
            vm.initialize(AppLanguage.ENGLISH)
            advanceUntilIdle()
            vm.submit()
            advanceUntilIdle()
            assertEquals(firstKey, analysisRepo.lastIdempotencyKey)

            // Changing language invalidates the key for the next submission
            vm.initialize(AppLanguage.FRENCH)
            advanceUntilIdle()
            vm.submit()
            advanceUntilIdle()
            assertNotEquals(firstKey, analysisRepo.lastIdempotencyKey)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `AnalysisProgressViewModel handles foreground activation before active-request lookup completes`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val analysisRepo = FakeAnalysisRepository()
            val activeDeferred = CompletableDeferred<ActiveAnalysisRequest?>()
            analysisRepo.deferredActiveRequest = activeDeferred

            val vm = AnalysisProgressViewModel(analysisRepo)
            vm.initialize("req-early")
            assertEquals("req-early", vm.uiState.value.requestId)

            // Foreground becomes active before getActiveRequest() resumes
            vm.setForegroundActive(true)
            runCurrent()
            assertEquals(1, analysisRepo.pollCalls)

            activeDeferred.complete(ActiveAnalysisRequest("req-early", "farm_1", 1500L, 100L))
            runCurrent()
            // Still only 1 poll call (no duplicate polling loop started)
            assertEquals(1, analysisRepo.pollCalls)
            assertEquals(1500L, vm.uiState.value.lastPollIntervalMs)

            vm.setForegroundActive(false)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `AnalysisProgressViewModel 409 cancel with transient poll failure preserves active request and recovers on retry`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val analysisRepo = FakeAnalysisRepository()
            analysisRepo.activeRequest = ActiveAnalysisRequest("req-409", "farm_1", 1000L, 100L)
            analysisRepo.cancelResult = AnalysisCallResult.Failure(
                AnalysisError.Api(409, "CONFLICT", "Already completed")
            )
            analysisRepo.pollResponses.addAll(
                listOf(
                    AnalysisCallResult.Failure(AnalysisError.Network("Temporary drop")),
                    AnalysisCallResult.Success(
                        AnalysisPollState("req-409", AnalysisJobStatus.OK, null, null, "analysis_0123456789ab", emptyList(), null, null, null)
                    )
                )
            )

            val vm = AnalysisProgressViewModel(analysisRepo)
            vm.initialize("req-409")
            advanceUntilIdle()

            vm.cancelAnalysis()
            advanceUntilIdle()

            assertNotNull(analysisRepo.activeRequest)
            assertFalse(vm.uiState.value.status.isTerminal)
            assertTrue(vm.uiState.value.cancelError is AnalysisError.Network)
            assertTrue(vm.uiState.value.transportError is AnalysisError.Network)

            vm.setForegroundActive(true)
            vm.retryPolling()
            runCurrent()

            assertEquals(AnalysisJobStatus.OK, vm.uiState.value.status)
            assertEquals("analysis_0123456789ab", vm.uiState.value.analysisId)
            assertNull(analysisRepo.activeRequest)
            assertNull(vm.uiState.value.cancelError)
            assertNull(vm.uiState.value.transportError)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `DataStoreActiveAnalysisStore persists restores and recovers from corrupt stored data`() = runTest {
        val tempDir = Files.createTempDirectory("active_analysis_store_test").toFile()
        try {
            val dataStore = PreferenceDataStoreFactory.create(
                scope = backgroundScope,
                produceFile = { tempDir.resolve("active_analysis.preferences_pb") }
            )
            val store = DataStoreActiveAnalysisStore(dataStore, NetworkModule.provideJson())

            val expected = ActiveAnalysisRequest(
                requestId = "req-ds-1",
                farmId = "farm_42",
                pollIntervalMs = 2500L,
                createdAtEpochMs = 1_700_000_000_000L
            )
            store.saveActiveRequest(expected)
            assertEquals(expected, store.getActiveRequest())

            val key = stringPreferencesKey("active_analysis_request")
            dataStore.edit { prefs -> prefs[key] = "{not-valid-json" }

            assertNull(store.getActiveRequest())
            assertNull(dataStore.data.first()[key])
        } finally {
            tempDir.deleteRecursively()
        }
    }

    @Test
    fun `AnalysisProgressViewModel handles FAILED and CANCELLED terminal polls and 200 cancel`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            // 1. FAILED terminal poll
            val failedRepo = FakeAnalysisRepository()
            failedRepo.activeRequest = ActiveAnalysisRequest("req-fail", "farm_1", 1000L, 100L)
            failedRepo.pollResponses.add(
                AnalysisCallResult.Success(
                    AnalysisPollState(
                        requestId = "req-fail",
                        status = AnalysisJobStatus.FAILED,
                        pollIntervalMs = null,
                        retryAfterSeconds = null,
                        analysisId = null,
                        warnings = emptyList(),
                        degradedMode = null,
                        error = PollErrorInfo("ML_TIMEOUT", 504, "Engine timed out"),
                        result = null
                    )
                )
            )
            val failedVm = AnalysisProgressViewModel(failedRepo)
            failedVm.initialize("req-fail")
            failedVm.setForegroundActive(true)
            runCurrent()
            assertEquals(AnalysisJobStatus.FAILED, failedVm.uiState.value.status)
            assertEquals("ML_TIMEOUT", failedVm.uiState.value.pollErrorInfo?.code)
            assertNull(failedRepo.activeRequest)
            assertFalse(failedVm.uiState.value.isPolling)

            // 2. CANCELLED terminal poll
            val cancelledRepo = FakeAnalysisRepository()
            cancelledRepo.activeRequest = ActiveAnalysisRequest("req-canc", "farm_1", 1000L, 100L)
            cancelledRepo.pollResponses.add(
                AnalysisCallResult.Success(
                    AnalysisPollState("req-canc", AnalysisJobStatus.CANCELLED, null, null, null, emptyList(), null, null, null)
                )
            )
            val cancelledVm = AnalysisProgressViewModel(cancelledRepo)
            cancelledVm.initialize("req-canc")
            cancelledVm.setForegroundActive(true)
            runCurrent()
            assertEquals(AnalysisJobStatus.CANCELLED, cancelledVm.uiState.value.status)
            assertNull(cancelledRepo.activeRequest)
            assertFalse(cancelledVm.uiState.value.isPolling)

            // 3. 200 cancel success
            val cancel200Repo = FakeAnalysisRepository()
            cancel200Repo.activeRequest = ActiveAnalysisRequest("req-200", "farm_1", 1000L, 100L)
            cancel200Repo.cancelResult = AnalysisCallResult.Success(AnalysisJobStatus.CANCELLED)
            val cancel200Vm = AnalysisProgressViewModel(cancel200Repo)
            cancel200Vm.initialize("req-200")
            advanceUntilIdle()
            cancel200Vm.cancelAnalysis()
            advanceUntilIdle()
            assertEquals(AnalysisJobStatus.CANCELLED, cancel200Vm.uiState.value.status)
            assertNull(cancel200Repo.activeRequest)
            assertFalse(cancel200Vm.uiState.value.isCancelling)
            assertFalse(cancel200Vm.uiState.value.isPolling)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `AnalysisRepositoryImpl submitAnalysis sends HTTP POST to analysis with Idempotency-Key and serialized body including retries`() = runTest {
        data class CapturedRequest(
            val method: String,
            val encodedPath: String,
            val idempotencyKey: String?,
            val body: String
        )

        val prodJson = NetworkModule.provideJson()
        val captured = mutableListOf<CapturedRequest>()
        val client = OkHttpClient.Builder()
            .addInterceptor { chain ->
                val req = chain.request()
                val buffer = Buffer()
                req.body?.writeTo(buffer)
                captured += CapturedRequest(
                    method = req.method,
                    encodedPath = req.url.encodedPath,
                    idempotencyKey = req.header("Idempotency-Key"),
                    body = buffer.readUtf8()
                )
                if (captured.size == 1) {
                    throw IOException("Simulated timeout")
                }
                val responseJson = """
                    {
                      "request_id": "req-http-1",
                      "status": "pending",
                      "poll_url": "/api/v1/analysis/requests/req-http-1",
                      "poll_interval_ms": 2000,
                      "warnings": []
                    }
                """.trimIndent()
                okhttp3.Response.Builder()
                    .request(req)
                    .protocol(Protocol.HTTP_1_1)
                    .code(202)
                    .message("Accepted")
                    .body(responseJson.toResponseBody("application/json".toMediaType()))
                    .build()
            }
            .build()

        val apiService = Retrofit.Builder()
            .baseUrl("https://api.example.com/api/v1/")
            .client(client)
            .addConverterFactory(prodJson.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(AnalysisApiService::class.java)

        val repo = AnalysisRepositoryImpl(
            apiService = apiService,
            activeAnalysisStore = InMemoryActiveAnalysisStore(),
            errorParser = ApiErrorParser(prodJson)
        )

        val firstAttempt = repo.submitAnalysis(sampleSubmitInput(), "idem-key-123")
        assertTrue(firstAttempt is AnalysisCallResult.Failure)
        assertTrue((firstAttempt as AnalysisCallResult.Failure).error is AnalysisError.Network)

        val retryAttempt = repo.submitAnalysis(sampleSubmitInput(), "idem-key-123")
        assertTrue(retryAttempt is AnalysisCallResult.Success)
        assertEquals("req-http-1", (retryAttempt as AnalysisCallResult.Success).data.requestId)

        assertEquals(2, captured.size)
        captured.forEach { req ->
            assertEquals("POST", req.method)
            assertEquals("/api/v1/analysis", req.encodedPath)
            assertEquals("idem-key-123", req.idempotencyKey)

            val root = prodJson.parseToJsonElement(req.body).jsonObject
            assertEquals("farm_1", root.getValue("farm_id").jsonPrimitive.content)
            assertEquals("en", root.getValue("language").jsonPrimitive.content)
            assertEquals(listOf("f1"), root.getValue("field_ids").jsonArray.map { it.jsonPrimitive.content })

            val priorities = root.getValue("priorities").jsonObject
            assertEquals("mixed", priorities.getValue("market_preference").jsonPrimitive.content)
            assertEquals(0, priorities.getValue("target_crop_ids").jsonArray.size)
            assertEquals(0, priorities.getValue("excluded_crop_ids").jsonArray.size)
            assertEquals(0, priorities.getValue("equipment_constraints").jsonArray.size)
        }
    }

    @Test
    fun `StrategySelectionRequestDto serializes exact OpenAPI v3_2 fields with NetworkModule provideJson`() {
        val prodJson = NetworkModule.provideJson()
        val selectedPayload = prodJson.encodeToString(
            StrategySelectionRequestDto(
                fieldId = "field_01",
                strategyId = "strat_balanced",
                selectionStatus = StrategySelectionStatus.SELECTED.apiValue
            )
        )
        val selectedObj = prodJson.parseToJsonElement(selectedPayload).jsonObject
        assertEquals("field_01", selectedObj.getValue("field_id").jsonPrimitive.content)
        assertEquals("strat_balanced", selectedObj.getValue("strategy_id").jsonPrimitive.content)
        assertEquals("selected", selectedObj.getValue("selection_status").jsonPrimitive.content)

        val rejectedPayload = prodJson.encodeToString(
            StrategySelectionRequestDto(
                fieldId = "field_02",
                strategyId = "strat_alt",
                selectionStatus = StrategySelectionStatus.REJECTED.apiValue
            )
        )
        val rejectedObj = prodJson.parseToJsonElement(rejectedPayload).jsonObject
        assertEquals("rejected", rejectedObj.getValue("selection_status").jsonPrimitive.content)
    }

    @Test
    fun `AnalysisRepositoryImpl updateStrategySelection sends PATCH and maps 200 and unexpected status`() = runTest {
        data class CapturedPatch(
            val method: String,
            val encodedPath: String,
            val body: String
        )

        val prodJson = NetworkModule.provideJson()
        val captured = mutableListOf<CapturedPatch>()
        var nextStatusToReturn = "selected"

        val client = OkHttpClient.Builder()
            .addInterceptor { chain ->
                val req = chain.request()
                val buffer = Buffer()
                req.body?.writeTo(buffer)
                captured += CapturedPatch(
                    method = req.method,
                    encodedPath = req.url.encodedPath,
                    body = buffer.readUtf8()
                )
                val responseJson = """
                    {
                      "analysis_id": "analysis_0123456789ab",
                      "field_id": "field_01",
                      "strategy_id": "strat_balanced",
                      "selection_status": "$nextStatusToReturn"
                    }
                """.trimIndent()
                okhttp3.Response.Builder()
                    .request(req)
                    .protocol(Protocol.HTTP_1_1)
                    .code(200)
                    .message("OK")
                    .body(responseJson.toResponseBody("application/json".toMediaType()))
                    .build()
            }
            .build()

        val apiService = Retrofit.Builder()
            .baseUrl("https://api.example.com/api/v1/")
            .client(client)
            .addConverterFactory(prodJson.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(AnalysisApiService::class.java)

        val repo = AnalysisRepositoryImpl(
            apiService = apiService,
            activeAnalysisStore = InMemoryActiveAnalysisStore(),
            errorParser = ApiErrorParser(prodJson)
        )

        val result = repo.updateStrategySelection(
            analysisId = "analysis_0123456789ab",
            fieldId = "field_01",
            strategyId = "strat_balanced",
            selectionStatus = StrategySelectionStatus.SELECTED
        )
        assertTrue(result is AnalysisCallResult.Success)
        val data = (result as AnalysisCallResult.Success).data
        assertEquals("analysis_0123456789ab", data.analysisId)
        assertEquals("field_01", data.fieldId)
        assertEquals("strat_balanced", data.strategyId)
        assertEquals(StrategySelectionStatus.SELECTED, data.selectionStatus)

        assertEquals(1, captured.size)
        assertEquals("PATCH", captured.first().method)
        assertEquals("/api/v1/analysis/analysis_0123456789ab/selection", captured.first().encodedPath)
        val reqBody = prodJson.parseToJsonElement(captured.first().body).jsonObject
        assertEquals("field_01", reqBody.getValue("field_id").jsonPrimitive.content)
        assertEquals("strat_balanced", reqBody.getValue("strategy_id").jsonPrimitive.content)
        assertEquals("selected", reqBody.getValue("selection_status").jsonPrimitive.content)

        // Unexpected selection_status in 200 response fails cleanly instead of silently coercing
        nextStatusToReturn = "suggested"
        val invalidStatusResult = repo.updateStrategySelection(
            analysisId = "analysis_0123456789ab",
            fieldId = "field_01",
            strategyId = "strat_balanced",
            selectionStatus = StrategySelectionStatus.REJECTED
        )
        assertTrue(invalidStatusResult is AnalysisCallResult.Failure)
        assertTrue((invalidStatusResult as AnalysisCallResult.Failure).error is AnalysisError.Network)
    }

    @Test
    fun `AnalysisRepositoryImpl updateStrategySelection maps 400 and 404 API errors`() = runTest {
        val api = FakeAnalysisApiService()
        val repo = AnalysisRepositoryImpl(api, InMemoryActiveAnalysisStore(), ApiErrorParser(json))

        api.selectionException = httpException(
            400,
            """{"error":{"code":"INVALID_INPUT","message":"Unknown strategy_id","request_id":"req-400"}}"""
        )
        val badRequest = repo.updateStrategySelection(
            analysisId = "analysis_0123456789ab",
            fieldId = "field_01",
            strategyId = "missing_strat",
            selectionStatus = StrategySelectionStatus.SELECTED
        )
        assertTrue(badRequest is AnalysisCallResult.Failure)
        val err400 = (badRequest as AnalysisCallResult.Failure).error as AnalysisError.Api
        assertEquals(400, err400.httpStatus)
        assertEquals("INVALID_INPUT", err400.errorCode)

        api.selectionException = httpException(
            404,
            """{"error":{"code":"NOT_FOUND","message":"Analysis not found","request_id":"req-404"}}"""
        )
        val notFound = repo.updateStrategySelection(
            analysisId = "analysis_missing",
            fieldId = "field_01",
            strategyId = "strat_1",
            selectionStatus = StrategySelectionStatus.REJECTED
        )
        assertTrue(notFound is AnalysisCallResult.Failure)
        val err404 = (notFound as AnalysisCallResult.Failure).error as AnalysisError.Api
        assertEquals(404, err404.httpStatus)
        assertTrue(err404.isNotFound)
    }

    @Test
    fun `AnalysisResultViewModel updateStrategySelection selects rejects switches selection and prevents duplicate requests`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val repo = FakeAnalysisRepository()
            repo.resultResponse = AnalysisCallResult.Success(sampleEnvelopeWithStrategies())
            val vm = AnalysisResultViewModel(repo)
            vm.loadResult("analysis_0123456789ab")
            advanceUntilIdle()

            // Hold first PATCH in flight to test duplicate submission prevention
            val gate = CompletableDeferred<AnalysisCallResult<StrategySelectionResult>>()
            repo.deferredSelection = gate

            vm.updateStrategySelection("field_01", "S2_water_resilient", StrategySelectionStatus.SELECTED)
            runCurrent()
            assertTrue("field_01" in vm.uiState.value.mutatingFieldIds)
            assertEquals("field_01:S2_water_resilient", vm.uiState.value.mutatingStrategyKey)

            // Duplicate or competing selection on the same field while in flight is ignored
            vm.updateStrategySelection("field_01", "S1_baseline", StrategySelectionStatus.SELECTED)
            assertEquals(1, repo.selectionCalls)

            // Complete PATCH 200 -> S2 becomes SELECTED, S1 stays SUGGESTED
            repo.resultResponse = AnalysisCallResult.Failure(AnalysisError.Network("skip refresh"))
            gate.complete(
                AnalysisCallResult.Success(
                    StrategySelectionResult("analysis_0123456789ab", "field_01", "S2_water_resilient", StrategySelectionStatus.SELECTED)
                )
            )
            advanceUntilIdle()

            assertTrue(vm.uiState.value.mutatingFieldIds.isEmpty())
            assertNull(vm.uiState.value.mutatingStrategyKey)
            val afterSelectS2 = (vm.uiState.value.envelopeState as UiState.Success).data.result.fieldPlans.first().strategies
            assertEquals(StrategyDisplaySelection.SUGGESTED, afterSelectS2[0].displaySelectionStatus)
            assertEquals(StrategyDisplaySelection.SELECTED, afterSelectS2[1].displaySelectionStatus)

            // Switch selection to S1 -> S2 reverts to SUGGESTED (matching backend upsert_analysis_selection)
            repo.deferredSelection = null
            vm.updateStrategySelection("field_01", "S1_baseline", StrategySelectionStatus.SELECTED)
            advanceUntilIdle()

            val afterSwitchS1 = (vm.uiState.value.envelopeState as UiState.Success).data.result.fieldPlans.first().strategies
            assertEquals(StrategyDisplaySelection.SELECTED, afterSwitchS1[0].displaySelectionStatus)
            assertEquals(StrategyDisplaySelection.SUGGESTED, afterSwitchS1[1].displaySelectionStatus)

            // Reject S2 -> S2 becomes REJECTED and remains in strategies list
            vm.updateStrategySelection("field_01", "S2_water_resilient", StrategySelectionStatus.REJECTED)
            advanceUntilIdle()

            val afterRejectS2 = (vm.uiState.value.envelopeState as UiState.Success).data.result.fieldPlans.first().strategies
            assertEquals(2, afterRejectS2.size)
            assertEquals(StrategyDisplaySelection.SELECTED, afterRejectS2[0].displaySelectionStatus)
            assertEquals(StrategyDisplaySelection.REJECTED, afterRejectS2[1].displaySelectionStatus)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `AnalysisHistoryViewModel initial load selects first farm and loads history`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val farm1 = Farm("farm_1", "North Olive", "DZ", "Guelma", null, 2, "2026-10-01T00:00:00Z")
            val farm2 = Farm("farm_2", "South Wheat", "DZ", "Setif", null, 1, "2026-10-02T00:00:00Z")
            val summary = FarmAnalysisSummary(
                requestId = "req-1",
                analysisId = "analysis_0123456789ab",
                status = AnalysisJobStatus.OK,
                language = AppLanguage.ENGLISH,
                catalogVersion = "v1",
                datasetVersion = null,
                mlEngineVersion = "5.0",
                warnings = listOf(WarningNotice("W1", "Low rainfall", emptyList())),
                createdAt = "2026-11-15T10:00:00Z",
                durationMs = 1420L
            )
            val analysisRepo = FakeAnalysisRepository().apply {
                historyHandler = { farmId, _, cursor, status ->
                    assertEquals("farm_1", farmId)
                    assertNull(cursor)
                    assertNull(status)
                    AnalysisCallResult.Success(FarmAnalysesPage(listOf(summary), null, false))
                }
            }
            val vm = AnalysisHistoryViewModel(FakeFarmRepository(listOf(farm1, farm2)), analysisRepo)
            vm.initialize()
            advanceUntilIdle()

            val state = vm.uiState.value
            assertFalse(state.isLoadingFarms)
            assertFalse(state.isLoadingHistory)
            assertEquals("farm_1", state.selectedFarmId)
            assertEquals(listOf(summary), state.items)
            assertFalse(state.hasMore)
            assertEquals(1, analysisRepo.historyCalls.size)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `AnalysisHistoryViewModel handles empty history and empty farms`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val emptyFarmRepo = FakeFarmRepository(emptyList())
            val analysisRepo = FakeAnalysisRepository()
            val noFarmsVm = AnalysisHistoryViewModel(emptyFarmRepo, analysisRepo)
            noFarmsVm.initialize()
            advanceUntilIdle()

            assertTrue(noFarmsVm.uiState.value.farms.isEmpty())
            assertNull(noFarmsVm.uiState.value.selectedFarmId)
            assertTrue(analysisRepo.historyCalls.isEmpty())

            val farm = Farm("farm_1", "North Olive", "DZ", "Guelma", null, 1, "2026-10-01T00:00:00Z")
            val emptyHistoryVm = AnalysisHistoryViewModel(FakeFarmRepository(listOf(farm)), analysisRepo)
            emptyHistoryVm.initialize()
            advanceUntilIdle()

            assertEquals("farm_1", emptyHistoryVm.uiState.value.selectedFarmId)
            assertTrue(emptyHistoryVm.uiState.value.items.isEmpty())
            assertNull(emptyHistoryVm.uiState.value.historyError)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `AnalysisHistoryViewModel status filtering resets cursor and passes status`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val farm = Farm("farm_1", "North Olive", "DZ", "Guelma", null, 2, "2026-10-01T00:00:00Z")
            val analysisRepo = FakeAnalysisRepository().apply {
                historyHandler = { _, _, _, status ->
                    if (status == null) {
                        AnalysisCallResult.Success(
                            FarmAnalysesPage(
                                items = listOf(
                                    FarmAnalysisSummary("req-1", "analysis_0123456789ab", AnalysisJobStatus.OK, AppLanguage.ENGLISH, "v1", null, null, emptyList(), "2026-11-15T10:00:00Z", 1000L)
                                ),
                                nextCursor = "cursor_page_2",
                                hasMore = true
                            )
                        )
                    } else {
                        AnalysisCallResult.Success(
                            FarmAnalysesPage(
                                items = listOf(
                                    FarmAnalysisSummary("req-2", null, AnalysisJobStatus.RUNNING, AppLanguage.FRENCH, "v1", null, null, emptyList(), "2026-11-15T11:00:00Z", null)
                                ),
                                nextCursor = null,
                                hasMore = false
                            )
                        )
                    }
                }
            }
            val vm = AnalysisHistoryViewModel(FakeFarmRepository(listOf(farm)), analysisRepo)
            vm.initialize()
            advanceUntilIdle()
            assertEquals("cursor_page_2", vm.uiState.value.nextCursor)
            assertTrue(vm.uiState.value.hasMore)

            vm.selectStatusFilter(AnalysisJobStatus.RUNNING)
            advanceUntilIdle()

            val state = vm.uiState.value
            assertEquals(AnalysisJobStatus.RUNNING, state.selectedStatusFilter)
            assertNull(state.nextCursor)
            assertFalse(state.hasMore)
            assertEquals(listOf("req-2"), state.items.map { it.requestId })
            assertEquals(AnalysisJobStatus.RUNNING, analysisRepo.historyCalls.last().status)
            assertNull(analysisRepo.historyCalls.last().cursor)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `AnalysisHistoryViewModel cursor pagination appends deduplicated items`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val farm = Farm("farm_1", "North Olive", "DZ", "Guelma", null, 2, "2026-10-01T00:00:00Z")
            val item1 = FarmAnalysisSummary("req-1", "analysis_111111111111", AnalysisJobStatus.OK, AppLanguage.ENGLISH, "v1", null, null, emptyList(), "2026-11-15T10:00:00Z", 900L)
            val item2 = FarmAnalysisSummary("req-2", "analysis_222222222222", AnalysisJobStatus.PARTIAL, AppLanguage.ENGLISH, "v1", null, null, List(2) { WarningNotice("W$it", "warn", emptyList()) }, "2026-11-15T09:00:00Z", 1100L)
            val analysisRepo = FakeAnalysisRepository().apply {
                historyHandler = { _, _, cursor, _ ->
                    if (cursor == null) {
                        AnalysisCallResult.Success(FarmAnalysesPage(listOf(item1), "cursor_2", true))
                    } else {
                        // Include duplicate item1 to verify deduplication by requestId
                        AnalysisCallResult.Success(FarmAnalysesPage(listOf(item1, item2), null, false))
                    }
                }
            }
            val vm = AnalysisHistoryViewModel(FakeFarmRepository(listOf(farm)), analysisRepo)
            vm.initialize()
            advanceUntilIdle()
            assertTrue(vm.uiState.value.hasMore)

            vm.loadMore()
            advanceUntilIdle()

            val state = vm.uiState.value
            assertEquals(listOf("req-1", "req-2"), state.items.map { it.requestId })
            assertFalse(state.hasMore)
            assertNull(state.nextCursor)
            assertEquals("cursor_2", analysisRepo.historyCalls.last().cursor)

            // Extra loadMore when hasMore is false does nothing
            val callsBefore = analysisRepo.historyCalls.size
            vm.loadMore()
            advanceUntilIdle()
            assertEquals(callsBefore, analysisRepo.historyCalls.size)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `AnalysisHistoryViewModel refresh reloads first page and replaces items`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val farm = Farm("farm_1", "North Olive", "DZ", "Guelma", null, 1, "2026-10-01T00:00:00Z")
            var pageVersion = 1
            val analysisRepo = FakeAnalysisRepository().apply {
                historyHandler = { _, _, _, _ ->
                    if (pageVersion == 1) {
                        AnalysisCallResult.Success(
                            FarmAnalysesPage(
                                listOf(FarmAnalysisSummary("req-old", "analysis_aaaaaaaaaaaa", AnalysisJobStatus.OK, AppLanguage.ENGLISH, "v1", null, null, emptyList(), "2026-11-15T08:00:00Z", 800L)),
                                null,
                                false
                            )
                        )
                    } else {
                        AnalysisCallResult.Success(
                            FarmAnalysesPage(
                                listOf(FarmAnalysisSummary("req-new", null, AnalysisJobStatus.PENDING, AppLanguage.ENGLISH, "v1", null, null, emptyList(), "2026-11-15T12:00:00Z", null)),
                                null,
                                false
                            )
                        )
                    }
                }
            }
            val vm = AnalysisHistoryViewModel(FakeFarmRepository(listOf(farm)), analysisRepo)
            vm.initialize()
            advanceUntilIdle()
            assertEquals(listOf("req-old"), vm.uiState.value.items.map { it.requestId })

            pageVersion = 2
            vm.refresh()
            advanceUntilIdle()

            assertFalse(vm.uiState.value.isRefreshing)
            assertEquals(listOf("req-new"), vm.uiState.value.items.map { it.requestId })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `AnalysisHistoryViewModel handles API and network errors on load and loadMore`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val farm = Farm("farm_1", "North Olive", "DZ", "Guelma", null, 1, "2026-10-01T00:00:00Z")
            val item1 = FarmAnalysisSummary("req-1", "analysis_111111111111", AnalysisJobStatus.OK, AppLanguage.ENGLISH, "v1", null, null, emptyList(), "2026-11-15T10:00:00Z", 900L)
            var failFirst = true
            val analysisRepo = FakeAnalysisRepository().apply {
                historyHandler = { _, _, cursor, _ ->
                    when {
                        failFirst -> AnalysisCallResult.Failure(AnalysisError.Api(500, "INTERNAL", "Server error"))
                        cursor == null -> AnalysisCallResult.Success(FarmAnalysesPage(listOf(item1), "c2", true))
                        else -> AnalysisCallResult.Failure(AnalysisError.Network("Timeout"))
                    }
                }
            }
            val vm = AnalysisHistoryViewModel(FakeFarmRepository(listOf(farm)), analysisRepo)
            vm.initialize()
            advanceUntilIdle()

            assertTrue(vm.uiState.value.historyError is AnalysisError.Api)
            assertTrue(vm.uiState.value.items.isEmpty())

            // Retry succeeds
            failFirst = false
            vm.retryHistory()
            advanceUntilIdle()
            assertNull(vm.uiState.value.historyError)
            assertEquals(listOf("req-1"), vm.uiState.value.items.map { it.requestId })

            // Load more fails with Network error while preserving existing items
            vm.loadMore()
            advanceUntilIdle()
            assertTrue(vm.uiState.value.loadMoreError is AnalysisError.Network)
            assertEquals(listOf("req-1"), vm.uiState.value.items.map { it.requestId })
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `AnalysisHistoryViewModel resolveItemAction handles ok partial pending running and missing analysisId`() {
        val vm = AnalysisHistoryViewModel(FakeFarmRepository(emptyList()), FakeAnalysisRepository())

        val okItem = FarmAnalysisSummary("req-1", "analysis_0123456789ab", AnalysisJobStatus.OK, AppLanguage.ENGLISH, "v1", null, null, emptyList(), "2026-11-15T10:00:00Z", 900L)
        assertEquals(HistoryItemAction.OpenResult("analysis_0123456789ab"), vm.resolveItemAction(okItem))

        val partialItem = okItem.copy(status = AnalysisJobStatus.PARTIAL, analysisId = "analysis_abcdef123456")
        assertEquals(HistoryItemAction.OpenResult("analysis_abcdef123456"), vm.resolveItemAction(partialItem))

        val missingIdOk = okItem.copy(analysisId = null)
        assertEquals(HistoryItemAction.Unavailable, vm.resolveItemAction(missingIdOk))

        val invalidIdOk = okItem.copy(analysisId = "not_a_valid_id")
        assertEquals(HistoryItemAction.Unavailable, vm.resolveItemAction(invalidIdOk))

        val pendingItem = okItem.copy(requestId = "req-pending", analysisId = null, status = AnalysisJobStatus.PENDING)
        assertEquals(HistoryItemAction.OpenProgress("req-pending"), vm.resolveItemAction(pendingItem))

        val runningItem = okItem.copy(requestId = "req-running", analysisId = null, status = AnalysisJobStatus.RUNNING)
        assertEquals(HistoryItemAction.OpenProgress("req-running"), vm.resolveItemAction(runningItem))

        val failedItem = okItem.copy(requestId = "req-failed", analysisId = null, status = AnalysisJobStatus.FAILED)
        assertEquals(HistoryItemAction.Unavailable, vm.resolveItemAction(failedItem))
    }

    @Test
    fun `AnalysisResultViewModel updateStrategySelection preserves envelope and exposes error on API and network failures`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val repo = FakeAnalysisRepository()
            repo.resultResponse = AnalysisCallResult.Success(sampleEnvelopeWithStrategies())
            val vm = AnalysisResultViewModel(repo)
            vm.loadResult("analysis_0123456789ab")
            advanceUntilIdle()

            repo.selectionResult = AnalysisCallResult.Failure(
                AnalysisError.Api(400, "INVALID_INPUT", "Unknown strategy_id")
            )
            vm.updateStrategySelection("field_01", "S2_water_resilient", StrategySelectionStatus.SELECTED)
            advanceUntilIdle()

            assertTrue(vm.uiState.value.envelopeState is UiState.Success)
            assertTrue(vm.uiState.value.mutatingFieldIds.isEmpty())
            val apiErr = vm.uiState.value.selectionError as AnalysisError.Api
            assertEquals(400, apiErr.httpStatus)

            vm.dismissSelectionError()
            assertNull(vm.uiState.value.selectionError)

            repo.selectionResult = AnalysisCallResult.Failure(AnalysisError.Network("Timeout"))
            vm.updateStrategySelection("field_01", "S2_water_resilient", StrategySelectionStatus.REJECTED)
            advanceUntilIdle()

            assertTrue(vm.uiState.value.envelopeState is UiState.Success)
            assertTrue(vm.uiState.value.selectionError is AnalysisError.Network)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `AnalysisResultViewModel syncs read-time merged selections from GET response`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val repo = FakeAnalysisRepository()
            repo.resultResponse = AnalysisCallResult.Success(
                sampleEnvelopeWithStrategies(s1Status = "rejected", s2Status = "selected")
            )
            val vm = AnalysisResultViewModel(repo)
            vm.loadResult("analysis_0123456789ab")
            advanceUntilIdle()

            val strategies = (vm.uiState.value.envelopeState as UiState.Success).data.result.fieldPlans.first().strategies
            assertEquals(StrategyDisplaySelection.REJECTED, strategies[0].displaySelectionStatus)
            assertEquals(StrategyDisplaySelection.SELECTED, strategies[1].displaySelectionStatus)
        } finally {
            Dispatchers.resetMain()
        }
    }

    private fun httpException(code: Int, body: String, retryAfter: String? = null): HttpException {
        val responseBody = body.toResponseBody("application/json".toMediaType())
        val raw = if (retryAfter != null) {
            Response.error<Any>(
                responseBody,
                okhttp3.Response.Builder()
                    .code(code)
                    .message("Error")
                    .protocol(okhttp3.Protocol.HTTP_1_1)
                    .request(okhttp3.Request.Builder().url("http://localhost/").build())
                    .header("Retry-After", retryAfter)
                    .build()
            )
        } else {
            Response.error<Any>(code, responseBody)
        }
        return HttpException(raw)
    }

    private fun sampleSubmitInput() = AnalysisSubmitInput(
        farmId = "farm_1",
        language = AppLanguage.ENGLISH,
        planning = PlanningConfig(Season.AUTUMN, 2026, 3, CycleMode.ANNUAL_ROTATION),
        weights = PriorityWeights(),
        marketPreference = MarketPreference.MIXED,
        fieldIds = listOf("f1")
    )

    private fun sampleEnvelopeWithStrategies(
        s1Status: String = "suggested",
        s2Status: String = "suggested"
    ): AnalysisResultEnvelope {
        val scores = StrategyScores(70.0, 65.0, 60.0, 55.0, 50.0, 75.0, 74.0, 90)
        val emptyExplanation = Explanation(emptyList(), emptyList(), emptyList(), emptyList(), emptyList(), emptyList(), emptyList())
        return AnalysisResultEnvelope(
            analysisId = "analysis_0123456789ab",
            requestId = "req-1",
            status = AnalysisJobStatus.OK,
            datasetVersion = "ds_1",
            warnings = emptyList(),
            degradedMode = null,
            result = AnalysisResultData(
                schemaVersion = "5.0",
                requestId = "req-1",
                datasetVersionUsed = "ds_1",
                generatedAt = "2026-10-01T00:00:00Z",
                status = AnalysisJobStatus.OK,
                language = AppLanguage.ENGLISH,
                mlEngineVersion = "5.0.0",
                overallSummary = "Summary",
                disclaimer = "Disclaimer",
                fieldPlans = listOf(
                    FieldPlan(
                        fieldId = "field_01",
                        fieldName = "North Plot",
                        status = AnalysisJobStatus.OK,
                        partialReason = null,
                        climateTrendSummary = "Moderate",
                        strategies = listOf(
                            Strategy(
                                strategyId = "S1_baseline",
                                name = "Existing Baseline",
                                isExistingRotation = true,
                                description = "Baseline",
                                seasons = listOf(
                                    SeasonPlan(1, Season.AUTUMN, 2026, 11, "durum_wheat", "Durum Wheat", "cereals", "main_crop", s1Status)
                                ),
                                scores = scores,
                                confidence = SeverityLevel.MEDIUM,
                                explanation = emptyExplanation
                            ),
                            Strategy(
                                strategyId = "S2_water_resilient",
                                name = "Water Resilient",
                                isExistingRotation = false,
                                description = "Recommended",
                                seasons = listOf(
                                    SeasonPlan(1, Season.SPRING, 2027, 3, "chickpea", "Chickpea", "legumes", "nitrogen_fixer", s2Status)
                                ),
                                scores = scores.copy(priorityFit = 84.0),
                                confidence = SeverityLevel.HIGH,
                                explanation = emptyExplanation
                            )
                        ),
                        suggestedStrategyId = "S2_water_resilient",
                        requestedCropResults = emptyList(),
                        dataQuality = DataQuality(0.9, null, emptyList(), emptyList(), emptyList())
                    )
                ),
                dataQuality = DataQuality(0.9, null, emptyList(), emptyList(), emptyList())
            )
        )
    }

    private fun sampleFieldSummary(fieldId: String, name: String) = FieldSummary(
        farmId = "farm_1",
        fieldId = fieldId,
        fieldName = name,
        isUnverifiedDemoParcel = false,
        location = FieldLocation(36.4, 7.4),
        areaHectares = 3.0,
        elevationM = 120.0,
        soil = FieldSoil(SoilType.LOAMY, SoilSource.FARMER),
        water = FieldWater(WaterAvailability.MODERATE, WaterSource.WELL, null, IrrigationSystem.DRIP),
        warnings = emptyList()
    )

    private class InMemoryActiveAnalysisStore : ActiveAnalysisStore {
        var current: ActiveAnalysisRequest? = null
        override suspend fun getActiveRequest(): ActiveAnalysisRequest? = current
        override suspend fun saveActiveRequest(request: ActiveAnalysisRequest) {
            current = request
        }
        override suspend fun clearActiveRequest() {
            current = null
        }
    }

    private class FakeFarmRepository(private val farms: List<Farm>) : FarmRepository {
        override suspend fun listFarms(
            limit: Int,
            cursor: String?,
            country: String?,
            region: String?,
            search: String?
        ): FarmResult<FarmPage> = FarmResult.Success(FarmPage(farms, null, false))
        override suspend fun getFarm(farmId: String): FarmResult<Farm> = throw UnsupportedOperationException()
        override suspend fun createFarm(input: FarmWriteInput): FarmResult<Farm> = throw UnsupportedOperationException()
        override suspend fun updateFarm(farmId: String, input: FarmWriteInput): FarmResult<Farm> = throw UnsupportedOperationException()
        override suspend fun deleteFarm(farmId: String): FarmResult<Unit> = throw UnsupportedOperationException()
    }

    private class FakeFieldRepository(private val fields: List<FieldSummary>) : FieldRepository {
        override suspend fun listFields(
            farmId: String,
            limit: Int,
            cursor: String?,
            soilType: SoilType?,
            waterAvailability: WaterAvailability?
        ): FieldResult<FieldPage> = FieldResult.Success(FieldPage(fields, null, false))
        override suspend fun getField(farmId: String, fieldId: String) = throw UnsupportedOperationException()
        override suspend fun createField(farmId: String, input: FieldWriteInput) = throw UnsupportedOperationException()
        override suspend fun updateField(farmId: String, fieldId: String, input: FieldWriteInput) = throw UnsupportedOperationException()
        override suspend fun deleteField(farmId: String, fieldId: String) = throw UnsupportedOperationException()
    }

    private class FakeAnalysisRepository : AnalysisRepository {
        var catalogResult: AnalysisCallResult<CatalogPage> =
            AnalysisCallResult.Success(CatalogPage("v1", "2026-10-01T00:00:00Z", emptyList(), null, false))
        var submitResult: AnalysisCallResult<AnalysisQueuedJob> =
            AnalysisCallResult.Failure(AnalysisError.Network("unset"))
        var deferredSubmit: CompletableDeferred<AnalysisCallResult<AnalysisQueuedJob>>? = null
        val pollResponses = ArrayDeque<AnalysisCallResult<AnalysisPollState>>()
        var cancelResult: AnalysisCallResult<AnalysisJobStatus> =
            AnalysisCallResult.Success(AnalysisJobStatus.CANCELLED)
        var resultResponse: AnalysisCallResult<AnalysisResultEnvelope> =
            AnalysisCallResult.Failure(AnalysisError.Network("unset"))
        var selectionResult: AnalysisCallResult<StrategySelectionResult>? = null
        var deferredSelection: CompletableDeferred<AnalysisCallResult<StrategySelectionResult>>? = null
        var activeRequest: ActiveAnalysisRequest? = null
        var deferredActiveRequest: CompletableDeferred<ActiveAnalysisRequest?>? = null
        var submitCalls: Int = 0
        var pollCalls: Int = 0
        var selectionCalls: Int = 0
        var lastIdempotencyKey: String? = null
        val historyCalls = mutableListOf<HistoryCall>()
        var historyHandler: (String, Int, String?, AnalysisJobStatus?) -> AnalysisCallResult<FarmAnalysesPage> =
            { _, _, _, _ -> AnalysisCallResult.Success(FarmAnalysesPage(emptyList(), null, false)) }

        data class HistoryCall(
            val farmId: String,
            val limit: Int,
            val cursor: String?,
            val status: AnalysisJobStatus?
        )

        override suspend fun getCatalog(language: AppLanguage, limit: Int, cursor: String?) = catalogResult

        override suspend fun submitAnalysis(
            input: AnalysisSubmitInput,
            idempotencyKey: String
        ): AnalysisCallResult<AnalysisQueuedJob> {
            submitCalls++
            lastIdempotencyKey = idempotencyKey
            return deferredSubmit?.await() ?: submitResult
        }

        override suspend fun pollAnalysisRequest(requestId: String): AnalysisCallResult<AnalysisPollState> {
            pollCalls++
            return if (pollResponses.isNotEmpty()) {
                pollResponses.removeFirst()
            } else {
                AnalysisCallResult.Success(
                    AnalysisPollState(requestId, AnalysisJobStatus.RUNNING, 1000L, null, null, emptyList(), null, null, null)
                )
            }
        }

        override suspend fun cancelAnalysisRequest(requestId: String) = cancelResult
        override suspend fun getAnalysisResult(analysisId: String) = resultResponse
        override suspend fun updateStrategySelection(
            analysisId: String,
            fieldId: String,
            strategyId: String,
            selectionStatus: StrategySelectionStatus
        ): AnalysisCallResult<StrategySelectionResult> {
            selectionCalls++
            return deferredSelection?.await()
                ?: selectionResult
                ?: AnalysisCallResult.Success(
                    StrategySelectionResult(analysisId, fieldId, strategyId, selectionStatus)
                )
        }
        override suspend fun listFarmAnalyses(farmId: String, limit: Int, cursor: String?, status: AnalysisJobStatus?): AnalysisCallResult<FarmAnalysesPage> {
            historyCalls += HistoryCall(farmId, limit, cursor, status)
            return historyHandler(farmId, limit, cursor, status)
        }
        override suspend fun getActiveRequest(): ActiveAnalysisRequest? =
            deferredActiveRequest?.await() ?: activeRequest
        override suspend fun saveActiveRequest(request: ActiveAnalysisRequest) {
            activeRequest = request
        }
        override suspend fun clearActiveRequest() {
            activeRequest = null
        }
    }

    private class FakeAnalysisApiService : AnalysisApiService {
        var submitException: Throwable? = null
        var pollException: Throwable? = null
        var pollResponse: Response<AnalysisPollEnvelopeDto>? = null
        var selectionException: Throwable? = null

        override suspend fun submitAnalysis(
            idempotencyKey: String?,
            request: AnalysisSubmitRequestDto
        ): Response<AnalysisQueuedResponseDto> {
            submitException?.let { throw it }
            return Response.success(
                202,
                AnalysisQueuedResponseDto("req-1", "pending", "/analysis/requests/req-1", 2000L)
            )
        }

        override suspend fun pollAnalysisRequest(requestId: String): Response<AnalysisPollEnvelopeDto> {
            pollException?.let { throw it }
            return pollResponse!!
        }

        override suspend fun cancelAnalysisRequest(requestId: String) =
            AnalysisCancelResponseDto(requestId, "cancelled")

        override suspend fun getAnalysisResult(analysisId: String): AnalysisEnvelopeDto =
            throw UnsupportedOperationException()

        override suspend fun updateStrategySelection(
            analysisId: String,
            request: StrategySelectionRequestDto
        ): StrategySelectionResponseDto {
            selectionException?.let { throw it }
            return StrategySelectionResponseDto(
                analysisId = analysisId,
                fieldId = request.fieldId,
                strategyId = request.strategyId,
                selectionStatus = request.selectionStatus
            )
        }

        override suspend fun listFarmAnalyses(
            farmId: String,
            limit: Int,
            cursor: String?,
            status: String?
        ): FarmAnalysesPageDto = FarmAnalysesPageDto(emptyList(), null, false)

        override suspend fun getCatalog(
            limit: Int,
            cursor: String?,
            category: String?,
            role: String?,
            lang: String?,
            version: String?
        ): CatalogPageDto = CatalogPageDto("v1", "2026-10-01T00:00:00Z", listOf(
            CropItemDto("wheat", "Wheat", CropNamesDto("Wheat", "Blé", "قمح"), "cereals", listOf("main_crop"), "Poaceae")
        ), null, false)
    }
}

