package com.example.myapplication.feature.analysis

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.myapplication.domain.analysis.AnalysisCallResult
import com.example.myapplication.domain.analysis.AnalysisError
import com.example.myapplication.domain.analysis.AnalysisJobStatus
import com.example.myapplication.domain.analysis.AnalysisPollState
import com.example.myapplication.domain.analysis.AnalysisRepository
import com.example.myapplication.domain.analysis.DegradedModeInfo
import com.example.myapplication.domain.analysis.PollErrorInfo
import com.example.myapplication.domain.auth.WarningNotice
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

data class AnalysisProgressUiState(
    val requestId: String = "",
    val status: AnalysisJobStatus = AnalysisJobStatus.PENDING,
    val analysisId: String? = null,
    val warnings: List<WarningNotice> = emptyList(),
    val degradedMode: DegradedModeInfo? = null,
    val pollErrorInfo: PollErrorInfo? = null,
    val transportError: AnalysisError? = null,
    val isPolling: Boolean = false,
    val isCancelling: Boolean = false,
    val cancelError: AnalysisError? = null,
    val lastPollIntervalMs: Long = 2000L
)

@HiltViewModel
class AnalysisProgressViewModel @Inject constructor(
    private val analysisRepository: AnalysisRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(AnalysisProgressUiState())
    val uiState: StateFlow<AnalysisProgressUiState> = _uiState.asStateFlow()

    private var pollingJob: Job? = null
    private var isForeground: Boolean = false
    private var consecutiveFailures: Int = 0

    fun initialize(requestId: String) {
        if (_uiState.value.requestId == requestId) return
        viewModelScope.launch {
            val saved = analysisRepository.getActiveRequest()
            val initialInterval = saved?.takeIf { it.requestId == requestId }?.pollIntervalMs ?: 2000L
            _uiState.update {
                AnalysisProgressUiState(
                    requestId = requestId,
                    lastPollIntervalMs = initialInterval
                )
            }
            if (isForeground) {
                startPollingLoop()
            }
        }
    }

    fun setForegroundActive(active: Boolean) {
        isForeground = active
        if (active) {
            if (_uiState.value.requestId.isNotBlank() && !_uiState.value.status.isTerminal) {
                startPollingLoop()
            }
        } else {
            stopPollingLoop()
        }
    }

    fun retryPolling() {
        consecutiveFailures = 0
        _uiState.update { it.copy(transportError = null) }
        if (isForeground && _uiState.value.requestId.isNotBlank() && !_uiState.value.status.isTerminal) {
            startPollingLoop()
        }
    }

    fun cancelAnalysis() {
        val requestId = _uiState.value.requestId
        if (requestId.isBlank() || _uiState.value.isCancelling || _uiState.value.status.isTerminal) return

        viewModelScope.launch {
            _uiState.update { it.copy(isCancelling = true, cancelError = null) }
            when (val result = analysisRepository.cancelAnalysisRequest(requestId)) {
                is AnalysisCallResult.Success -> {
                    stopPollingLoop()
                    analysisRepository.clearActiveRequest()
                    _uiState.update {
                        it.copy(
                            isCancelling = false,
                            isPolling = false,
                            status = result.data
                        )
                    }
                }
                is AnalysisCallResult.Failure -> {
                    if (result.error is AnalysisError.Api && result.error.isConflict) {
                        // 409: Job may already be terminal (including ok/partial). Fetch latest state first.
                        _uiState.update { it.copy(isCancelling = false) }
                        pollOnce()
                    } else {
                        _uiState.update {
                            it.copy(
                                isCancelling = false,
                                cancelError = result.error
                            )
                        }
                    }
                }
            }
        }
    }

    private fun startPollingLoop() {
        if (pollingJob?.isActive == true) return
        val requestId = _uiState.value.requestId
        if (requestId.isBlank() || _uiState.value.status.isTerminal) return

        pollingJob = viewModelScope.launch {
            _uiState.update { it.copy(isPolling = true) }
            while (isActive && isForeground && !_uiState.value.status.isTerminal) {
                val delayMs = pollOnce()
                if (!isActive || !isForeground || _uiState.value.status.isTerminal) break
                if (delayMs > 0L) {
                    delay(delayMs)
                }
            }
            _uiState.update { it.copy(isPolling = false) }
        }
    }

    private fun stopPollingLoop() {
        pollingJob?.cancel()
        pollingJob = null
        _uiState.update { it.copy(isPolling = false) }
    }

    internal suspend fun pollOnce(): Long {
        val requestId = _uiState.value.requestId
        if (requestId.isBlank()) return 0L

        return when (val result = analysisRepository.pollAnalysisRequest(requestId)) {
            is AnalysisCallResult.Success -> {
                consecutiveFailures = 0
                val poll = result.data
                applyPollState(poll)
            }
            is AnalysisCallResult.Failure -> {
                val error = result.error
                if (error is AnalysisError.Api && error.isNotFound) {
                    // Confirmed stale/unknown request: clear persisted tracking.
                    analysisRepository.clearActiveRequest()
                    _uiState.update {
                        it.copy(
                            status = AnalysisJobStatus.FAILED,
                            transportError = error,
                            isPolling = false
                        )
                    }
                    0L
                } else if (error is AnalysisError.Api && error.isRateLimited) {
                    val retryAfterMs = (error.retryAfterSeconds ?: 2L).coerceAtLeast(1L) * 1000L
                    _uiState.update { it.copy(transportError = error) }
                    retryAfterMs
                } else {
                    consecutiveFailures++
                    val backoffMs = computeBackoffMs(consecutiveFailures)
                    _uiState.update { it.copy(transportError = error) }
                    backoffMs
                }
            }
        }
    }

    private suspend fun applyPollState(poll: AnalysisPollState): Long {
        if (poll.status.isTerminal) {
            stopPollingLoop()
            analysisRepository.clearActiveRequest()
        }
        _uiState.update {
            it.copy(
                status = poll.status,
                analysisId = poll.analysisId ?: it.analysisId,
                warnings = poll.warnings,
                degradedMode = poll.degradedMode,
                pollErrorInfo = poll.error,
                transportError = null
            )
        }
        if (poll.status.isTerminal) {
            return 0L
        }
        val retryAfterMs = poll.retryAfterSeconds?.times(1000L) ?: 0L
        val bodyIntervalMs = poll.pollIntervalMs ?: _uiState.value.lastPollIntervalMs
        val nextDelay = maxOf(retryAfterMs, bodyIntervalMs).coerceAtLeast(0L)
        _uiState.update { it.copy(lastPollIntervalMs = nextDelay) }
        return nextDelay
    }

    private fun computeBackoffMs(failures: Int): Long {
        val shift = (failures - 1).coerceIn(0, 4)
        return (2000L shl shift).coerceAtMost(15_000L)
    }

    override fun onCleared() {
        super.onCleared()
        stopPollingLoop()
    }
}

