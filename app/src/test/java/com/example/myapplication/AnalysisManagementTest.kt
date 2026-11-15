package com.example.myapplication

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
import com.example.myapplication.core.network.PlanningDto
import com.example.myapplication.core.network.PrioritiesDto
import com.example.myapplication.core.network.PriorityWeightsDto
import com.example.myapplication.data.analysis.ActiveAnalysisStore
import com.example.myapplication.data.analysis.AnalysisRepositoryImpl
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
import com.example.myapplication.domain.analysis.FarmAnalysesPage
import com.example.myapplication.domain.analysis.FieldPlan
import com.example.myapplication.domain.analysis.MarketPreference
import com.example.myapplication.domain.analysis.PlanningConfig
import com.example.myapplication.domain.analysis.PriorityWeights
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
import com.example.myapplication.feature.analysis.AnalysisProgressViewModel
import com.example.myapplication.feature.analysis.AnalysisResultViewModel
import com.example.myapplication.feature.analysis.AnalysisValidationError
import java.io.IOException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.Headers
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response

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
        var activeRequest: ActiveAnalysisRequest? = null
        var submitCalls: Int = 0
        var pollCalls: Int = 0
        var lastIdempotencyKey: String? = null

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
        override suspend fun listFarmAnalyses(farmId: String, limit: Int, cursor: String?, status: AnalysisJobStatus?): AnalysisCallResult<FarmAnalysesPage> =
            AnalysisCallResult.Success(FarmAnalysesPage(emptyList(), null, false))
        override suspend fun getActiveRequest(): ActiveAnalysisRequest? = activeRequest
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

