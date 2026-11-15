package com.example.myapplication.feature.analysis

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.myapplication.domain.analysis.AnalysisCallResult
import com.example.myapplication.domain.analysis.AnalysisError
import com.example.myapplication.domain.analysis.AnalysisJobStatus
import com.example.myapplication.domain.analysis.AnalysisRepository
import com.example.myapplication.domain.analysis.FarmAnalysisSummary
import com.example.myapplication.domain.farm.Farm
import com.example.myapplication.domain.farm.FarmRepository
import com.example.myapplication.domain.farm.FarmResult
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

sealed interface HistoryItemAction {
    data class OpenResult(val analysisId: String) : HistoryItemAction
    data class OpenProgress(val requestId: String) : HistoryItemAction
    data object Unavailable : HistoryItemAction
}

data class AnalysisHistoryUiState(
    val isLoadingFarms: Boolean = true,
    val farms: List<Farm> = emptyList(),
    val farmsError: String? = null,
    val selectedFarmId: String? = null,
    val selectedStatusFilter: AnalysisJobStatus? = null,
    val isLoadingHistory: Boolean = false,
    val isRefreshing: Boolean = false,
    val isLoadingMore: Boolean = false,
    val historyError: AnalysisError? = null,
    val loadMoreError: AnalysisError? = null,
    val items: List<FarmAnalysisSummary> = emptyList(),
    val nextCursor: String? = null,
    val hasMore: Boolean = false
)

@HiltViewModel
class AnalysisHistoryViewModel @Inject constructor(
    private val farmRepository: FarmRepository,
    private val analysisRepository: AnalysisRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(AnalysisHistoryUiState())
    val uiState: StateFlow<AnalysisHistoryUiState> = _uiState.asStateFlow()

    private var initialized = false
    private var historyJob: Job? = null

    fun initialize() {
        if (initialized) return
        initialized = true
        loadFarmsInternal()
    }

    fun retryFarms() {
        loadFarmsInternal()
    }

    fun selectFarm(farmId: String) {
        val current = _uiState.value
        if (farmId == current.selectedFarmId && (current.items.isNotEmpty() || current.isLoadingHistory)) {
            return
        }
        _uiState.update {
            it.copy(
                selectedFarmId = farmId,
                items = emptyList(),
                nextCursor = null,
                hasMore = false,
                historyError = null,
                loadMoreError = null,
                isLoadingMore = false,
                isRefreshing = false
            )
        }
        loadFirstPage(farmId = farmId, status = _uiState.value.selectedStatusFilter, isRefresh = false)
    }

    fun selectStatusFilter(status: AnalysisJobStatus?) {
        val current = _uiState.value
        if (status == current.selectedStatusFilter) return
        _uiState.update {
            it.copy(
                selectedStatusFilter = status,
                items = emptyList(),
                nextCursor = null,
                hasMore = false,
                historyError = null,
                loadMoreError = null,
                isLoadingMore = false,
                isRefreshing = false
            )
        }
        val farmId = current.selectedFarmId ?: return
        loadFirstPage(farmId = farmId, status = status, isRefresh = false)
    }

    fun refresh() {
        val current = _uiState.value
        val farmId = current.selectedFarmId
        if (farmId == null) {
            loadFarmsInternal()
            return
        }
        loadFirstPage(farmId = farmId, status = current.selectedStatusFilter, isRefresh = true)
    }

    fun retryHistory() {
        val current = _uiState.value
        val farmId = current.selectedFarmId
        if (farmId == null) {
            loadFarmsInternal()
            return
        }
        loadFirstPage(farmId = farmId, status = current.selectedStatusFilter, isRefresh = false)
    }

    fun loadMore() {
        val current = _uiState.value
        val farmId = current.selectedFarmId ?: return
        val cursor = current.nextCursor?.takeIf { it.isNotBlank() } ?: return
        if (current.isLoadingHistory || current.isRefreshing || current.isLoadingMore || !current.hasMore) {
            return
        }

        val status = current.selectedStatusFilter
        _uiState.update { it.copy(isLoadingMore = true, loadMoreError = null) }

        historyJob?.cancel()
        historyJob = viewModelScope.launch {
            when (
                val result = analysisRepository.listFarmAnalyses(
                    farmId = farmId,
                    limit = PAGE_LIMIT,
                    cursor = cursor,
                    status = status
                )
            ) {
                is AnalysisCallResult.Success -> {
                    val page = result.data
                    _uiState.update { state ->
                        if (state.selectedFarmId != farmId || state.selectedStatusFilter != status) {
                            state
                        } else {
                            val merged = (state.items + page.items).distinctBy { it.requestId }
                            val next = page.nextCursor?.takeIf { it.isNotBlank() }
                            state.copy(
                                isLoadingMore = false,
                                loadMoreError = null,
                                items = merged,
                                nextCursor = next,
                                hasMore = page.hasMore && next != null
                            )
                        }
                    }
                }
                is AnalysisCallResult.Failure -> {
                    _uiState.update { state ->
                        if (state.selectedFarmId != farmId || state.selectedStatusFilter != status) {
                            state
                        } else {
                            state.copy(
                                isLoadingMore = false,
                                loadMoreError = result.error
                            )
                        }
                    }
                }
            }
        }
    }

    fun resolveItemAction(item: FarmAnalysisSummary): HistoryItemAction {
        val analysisId = item.analysisId?.trim()
        if (!analysisId.isNullOrEmpty() && item.status.isSuccessTerminal && ANALYSIS_ID_REGEX.matches(analysisId)) {
            return HistoryItemAction.OpenResult(analysisId)
        }
        if (!item.status.isTerminal && item.requestId.isNotBlank()) {
            return HistoryItemAction.OpenProgress(item.requestId)
        }
        return HistoryItemAction.Unavailable
    }

    private fun loadFarmsInternal() {
        historyJob?.cancel()
        _uiState.update {
            it.copy(
                isLoadingFarms = true,
                farmsError = null
            )
        }
        viewModelScope.launch {
            when (val result = farmRepository.listFarms(limit = FARMS_LIMIT)) {
                is FarmResult.Success -> {
                    val farms = result.data.items
                    val currentSelected = _uiState.value.selectedFarmId
                    val targetFarmId = currentSelected?.takeIf { id -> farms.any { it.id == id } }
                        ?: farms.firstOrNull()?.id
                    _uiState.update {
                        it.copy(
                            isLoadingFarms = false,
                            farms = farms,
                            farmsError = null,
                            selectedFarmId = targetFarmId
                        )
                    }
                    if (targetFarmId != null) {
                        loadFirstPage(
                            farmId = targetFarmId,
                            status = _uiState.value.selectedStatusFilter,
                            isRefresh = false
                        )
                    }
                }
                is FarmResult.Failure -> {
                    _uiState.update {
                        it.copy(
                            isLoadingFarms = false,
                            farmsError = result.error.message
                        )
                    }
                }
            }
        }
    }

    private fun loadFirstPage(
        farmId: String,
        status: AnalysisJobStatus?,
        isRefresh: Boolean
    ) {
        historyJob?.cancel()
        _uiState.update {
            it.copy(
                isLoadingHistory = !isRefresh && it.items.isEmpty(),
                isRefreshing = isRefresh,
                isLoadingMore = false,
                historyError = null,
                loadMoreError = null
            )
        }
        historyJob = viewModelScope.launch {
            when (
                val result = analysisRepository.listFarmAnalyses(
                    farmId = farmId,
                    limit = PAGE_LIMIT,
                    cursor = null,
                    status = status
                )
            ) {
                is AnalysisCallResult.Success -> {
                    val page = result.data
                    _uiState.update { state ->
                        if (state.selectedFarmId != farmId || state.selectedStatusFilter != status) {
                            state
                        } else {
                            val next = page.nextCursor?.takeIf { it.isNotBlank() }
                            state.copy(
                                isLoadingHistory = false,
                                isRefreshing = false,
                                historyError = null,
                                loadMoreError = null,
                                items = page.items.distinctBy { it.requestId },
                                nextCursor = next,
                                hasMore = page.hasMore && next != null
                            )
                        }
                    }
                }
                is AnalysisCallResult.Failure -> {
                    _uiState.update { state ->
                        if (state.selectedFarmId != farmId || state.selectedStatusFilter != status) {
                            state
                        } else {
                            state.copy(
                                isLoadingHistory = false,
                                isRefreshing = false,
                                historyError = result.error
                            )
                        }
                    }
                }
            }
        }
    }

    companion object {
        const val PAGE_LIMIT = 20
        private const val FARMS_LIMIT = 50
        private val ANALYSIS_ID_REGEX = Regex("^analysis_[0-9a-f]{12}$")
    }
}
