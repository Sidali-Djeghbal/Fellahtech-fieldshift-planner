package com.example.myapplication.data.analysis

import com.example.myapplication.core.common.AppLanguage
import com.example.myapplication.core.network.AnalysisApiService
import com.example.myapplication.core.network.ApiErrorParser
import com.example.myapplication.core.network.StrategySelectionRequestDto
import com.example.myapplication.domain.analysis.ActiveAnalysisRequest
import com.example.myapplication.domain.analysis.AnalysisCallResult
import com.example.myapplication.domain.analysis.AnalysisError
import com.example.myapplication.domain.analysis.AnalysisJobStatus
import com.example.myapplication.domain.analysis.AnalysisPollState
import com.example.myapplication.domain.analysis.AnalysisQueuedJob
import com.example.myapplication.domain.analysis.AnalysisRepository
import com.example.myapplication.domain.analysis.AnalysisResultEnvelope
import com.example.myapplication.domain.analysis.AnalysisSubmitInput
import com.example.myapplication.domain.analysis.CatalogPage
import com.example.myapplication.domain.analysis.FarmAnalysesPage
import com.example.myapplication.domain.analysis.StrategySelectionResult
import com.example.myapplication.domain.analysis.StrategySelectionStatus
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton
import retrofit2.HttpException
import retrofit2.Response

@Singleton
class AnalysisRepositoryImpl @Inject constructor(
    private val apiService: AnalysisApiService,
    private val activeAnalysisStore: ActiveAnalysisStore,
    private val errorParser: ApiErrorParser
) : AnalysisRepository {

    override suspend fun getCatalog(
        language: AppLanguage,
        limit: Int,
        cursor: String?
    ): AnalysisCallResult<CatalogPage> = safeCall {
        apiService.getCatalog(
            limit = limit,
            cursor = cursor,
            lang = language.languageTag
        ).toDomain()
    }

    override suspend fun submitAnalysis(
        input: AnalysisSubmitInput,
        idempotencyKey: String
    ): AnalysisCallResult<AnalysisQueuedJob> = safeCall {
        val response = apiService.submitAnalysis(
            idempotencyKey = idempotencyKey,
            request = input.toSubmitRequestDto()
        )
        if (!response.isSuccessful) {
            throw HttpException(response)
        }
        val body = response.body() ?: throw IOException("Empty analysis submit response")
        body.toDomain()
    }

    override suspend fun pollAnalysisRequest(
        requestId: String
    ): AnalysisCallResult<AnalysisPollState> = safeCall {
        val response = apiService.pollAnalysisRequest(requestId)
        if (!response.isSuccessful) {
            throw HttpException(response)
        }
        val body = response.body() ?: throw IOException("Empty analysis poll response")
        val retryAfterSeconds = parseRetryAfterSeconds(response)
        body.toDomain(retryAfterSeconds = retryAfterSeconds)
    }

    override suspend fun cancelAnalysisRequest(
        requestId: String
    ): AnalysisCallResult<AnalysisJobStatus> = safeCall {
        val response = apiService.cancelAnalysisRequest(requestId)
        AnalysisJobStatus.fromApi(response.status)
    }

    override suspend fun getAnalysisResult(
        analysisId: String
    ): AnalysisCallResult<AnalysisResultEnvelope> = safeCall {
        apiService.getAnalysisResult(analysisId).toDomain()
    }

    override suspend fun updateStrategySelection(
        analysisId: String,
        fieldId: String,
        strategyId: String,
        selectionStatus: StrategySelectionStatus
    ): AnalysisCallResult<StrategySelectionResult> = safeCall {
        apiService.updateStrategySelection(
            analysisId = analysisId,
            request = StrategySelectionRequestDto(
                fieldId = fieldId,
                strategyId = strategyId,
                selectionStatus = selectionStatus.apiValue
            )
        ).toDomain()
    }

    override suspend fun listFarmAnalyses(
        farmId: String,
        limit: Int,
        cursor: String?,
        status: AnalysisJobStatus?
    ): AnalysisCallResult<FarmAnalysesPage> = safeCall {
        apiService.listFarmAnalyses(
            farmId = farmId,
            limit = limit,
            cursor = cursor,
            status = status?.apiValue
        ).toDomain()
    }

    override suspend fun getActiveRequest(): ActiveAnalysisRequest? =
        activeAnalysisStore.getActiveRequest()

    override suspend fun saveActiveRequest(request: ActiveAnalysisRequest) {
        activeAnalysisStore.saveActiveRequest(request)
    }

    override suspend fun clearActiveRequest() {
        activeAnalysisStore.clearActiveRequest()
    }

    private fun parseRetryAfterSeconds(response: Response<*>): Long? =
        response.headers()["Retry-After"]?.trim()?.toLongOrNull()

    private inline fun <T> safeCall(block: () -> T): AnalysisCallResult<T> {
        return try {
            AnalysisCallResult.Success(block())
        } catch (e: HttpException) {
            val retryAfterSeconds = e.response()?.headers()?.get("Retry-After")?.trim()?.toLongOrNull()
            val parsed = errorParser.parseHttpException(e)
            AnalysisCallResult.Failure(
                AnalysisError.Api(
                    httpStatus = parsed.httpStatus,
                    errorCode = parsed.errorCode,
                    message = parsed.message,
                    retryAfterSeconds = retryAfterSeconds,
                    requestId = parsed.requestId
                )
            )
        } catch (e: IOException) {
            AnalysisCallResult.Failure(
                AnalysisError.Network(e.message ?: "Network error")
            )
        }
    }
}

