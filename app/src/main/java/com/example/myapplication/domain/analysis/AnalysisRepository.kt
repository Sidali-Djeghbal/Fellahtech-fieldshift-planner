package com.example.myapplication.domain.analysis

import com.example.myapplication.core.common.AppLanguage

interface AnalysisRepository {
    suspend fun getCatalog(
        language: AppLanguage,
        limit: Int = 50,
        cursor: String? = null
    ): AnalysisCallResult<CatalogPage>

    suspend fun submitAnalysis(
        input: AnalysisSubmitInput,
        idempotencyKey: String
    ): AnalysisCallResult<AnalysisQueuedJob>

    suspend fun pollAnalysisRequest(requestId: String): AnalysisCallResult<AnalysisPollState>

    suspend fun cancelAnalysisRequest(requestId: String): AnalysisCallResult<AnalysisJobStatus>

    suspend fun getAnalysisResult(analysisId: String): AnalysisCallResult<AnalysisResultEnvelope>

    suspend fun listFarmAnalyses(
        farmId: String,
        limit: Int = 20,
        cursor: String? = null,
        status: AnalysisJobStatus? = null
    ): AnalysisCallResult<FarmAnalysesPage>

    suspend fun getActiveRequest(): ActiveAnalysisRequest?
    suspend fun saveActiveRequest(request: ActiveAnalysisRequest)
    suspend fun clearActiveRequest()
}

