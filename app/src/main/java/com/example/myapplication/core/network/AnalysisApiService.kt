package com.example.myapplication.core.network

import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Retrofit service for FieldShift Planner Analysis & Catalog endpoints
 * matching `docs/openapi-v3.2.yaml` (base path `/api/v1`).
 */
interface AnalysisApiService {

    @POST("analysis")
    suspend fun submitAnalysis(
        @Header("Idempotency-Key") idempotencyKey: String? = null,
        @Body request: AnalysisSubmitRequestDto
    ): Response<AnalysisQueuedResponseDto>

    @GET("analysis/requests/{request_id}")
    suspend fun pollAnalysisRequest(
        @Path("request_id") requestId: String
    ): Response<AnalysisPollEnvelopeDto>

    @POST("analysis/requests/{request_id}/cancel")
    suspend fun cancelAnalysisRequest(
        @Path("request_id") requestId: String
    ): AnalysisCancelResponseDto

    @GET("analysis/{analysis_id}")
    suspend fun getAnalysisResult(
        @Path("analysis_id") analysisId: String
    ): AnalysisEnvelopeDto

    @GET("farms/{farm_id}/analyses")
    suspend fun listFarmAnalyses(
        @Path("farm_id") farmId: String,
        @Query("limit") limit: Int = 20,
        @Query("cursor") cursor: String? = null,
        @Query("status") status: String? = null
    ): FarmAnalysesPageDto

    @GET("catalog")
    suspend fun getCatalog(
        @Query("limit") limit: Int = 20,
        @Query("cursor") cursor: String? = null,
        @Query("category") category: String? = null,
        @Query("role") role: String? = null,
        @Query("lang") lang: String? = null,
        @Query("version") version: String? = null
    ): CatalogPageDto
}

