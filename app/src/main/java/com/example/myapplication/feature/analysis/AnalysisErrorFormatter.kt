package com.example.myapplication.feature.analysis

import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.example.myapplication.R
import com.example.myapplication.domain.analysis.AnalysisError
import com.example.myapplication.domain.analysis.AnalysisJobStatus
import com.example.myapplication.domain.analysis.CycleMode
import com.example.myapplication.domain.analysis.MarketPreference

@Composable
fun formatAnalysisErrorMessage(error: AnalysisError): String = when (error) {
    is AnalysisError.Network -> error.message
    is AnalysisError.Api -> when {
        error.isGuestLimitReached -> stringResource(R.string.analysis_error_guest_limit)
        error.isRateLimited -> stringResource(R.string.analysis_error_rate_limited)
        error.isInsufficientData -> stringResource(R.string.analysis_error_insufficient_data)
        error.isNotFound -> stringResource(R.string.analysis_error_not_found)
        error.isCatalogMismatch -> stringResource(R.string.analysis_error_catalog_mismatch)
        error.isOutsideDemoBoundary -> stringResource(R.string.fields_error_outside_demo_boundary)
        else -> error.message
    }
}

@Composable
fun CycleMode.label(): String = when (this) {
    CycleMode.ANNUAL_ROTATION -> stringResource(R.string.analysis_cycle_annual)
    CycleMode.CONSECUTIVE_SEASONS -> stringResource(R.string.analysis_cycle_consecutive)
}

@Composable
fun MarketPreference.label(): String = when (this) {
    MarketPreference.LOCAL_MARKET -> stringResource(R.string.analysis_market_local)
    MarketPreference.EXPORT -> stringResource(R.string.analysis_market_export)
    MarketPreference.SUBSISTENCE -> stringResource(R.string.analysis_market_subsistence)
    MarketPreference.MIXED -> stringResource(R.string.analysis_market_mixed)
}

@Composable
fun AnalysisJobStatus.label(): String = when (this) {
    AnalysisJobStatus.PENDING -> stringResource(R.string.analysis_status_pending)
    AnalysisJobStatus.RUNNING -> stringResource(R.string.analysis_status_running)
    AnalysisJobStatus.OK -> stringResource(R.string.analysis_status_ok)
    AnalysisJobStatus.PARTIAL -> stringResource(R.string.analysis_status_partial)
    AnalysisJobStatus.FAILED -> stringResource(R.string.analysis_status_failed)
    AnalysisJobStatus.CANCELLED -> stringResource(R.string.analysis_status_cancelled)
}

