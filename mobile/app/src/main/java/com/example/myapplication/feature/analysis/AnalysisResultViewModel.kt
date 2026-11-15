package com.example.myapplication.feature.analysis

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.myapplication.core.common.UiState
import com.example.myapplication.domain.analysis.AnalysisCallResult
import com.example.myapplication.domain.analysis.AnalysisError
import com.example.myapplication.domain.analysis.AnalysisRepository
import com.example.myapplication.domain.analysis.AnalysisResultEnvelope
import com.example.myapplication.domain.analysis.StrategyDisplaySelection
import com.example.myapplication.domain.analysis.StrategySelectionResult
import com.example.myapplication.domain.analysis.StrategySelectionStatus
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class AnalysisResultUiState(
    val envelopeState: UiState<AnalysisResultEnvelope> = UiState.Loading,
    val error: AnalysisError? = null,
    val mutatingFieldIds: Set<String> = emptySet(),
    val mutatingStrategyKey: String? = null,
    val selectionError: AnalysisError? = null
)

@HiltViewModel
class AnalysisResultViewModel @Inject constructor(
    private val analysisRepository: AnalysisRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(AnalysisResultUiState())
    val uiState: StateFlow<AnalysisResultUiState> = _uiState.asStateFlow()

    private var loadedAnalysisId: String? = null

    fun loadResult(analysisId: String, forceRefresh: Boolean = false) {
        if (!forceRefresh && loadedAnalysisId == analysisId && _uiState.value.envelopeState is UiState.Success) {
            return
        }
        loadedAnalysisId = analysisId
        viewModelScope.launch {
            _uiState.update { it.copy(envelopeState = UiState.Loading, error = null) }
            when (val res = analysisRepository.getAnalysisResult(analysisId)) {
                is AnalysisCallResult.Success -> {
                    _uiState.update {
                        it.copy(
                            envelopeState = UiState.Success(res.data),
                            error = null
                        )
                    }
                }
                is AnalysisCallResult.Failure -> {
                    _uiState.update {
                        it.copy(
                            envelopeState = UiState.Error(res.error.message),
                            error = res.error
                        )
                    }
                }
            }
        }
    }

    fun updateStrategySelection(
        fieldId: String,
        strategyId: String,
        status: StrategySelectionStatus
    ) {
        val currentState = _uiState.value
        val currentEnvelope = (currentState.envelopeState as? UiState.Success)?.data ?: return
        if (fieldId in currentState.mutatingFieldIds) return

        val targetStrategy = currentEnvelope.result.fieldPlans
            .firstOrNull { it.fieldId == fieldId }
            ?.strategies
            ?.firstOrNull { it.strategyId == strategyId }
            ?: return

        val alreadyMatches = when (status) {
            StrategySelectionStatus.SELECTED ->
                targetStrategy.displaySelectionStatus == StrategyDisplaySelection.SELECTED
            StrategySelectionStatus.REJECTED ->
                targetStrategy.displaySelectionStatus == StrategyDisplaySelection.REJECTED
        }
        if (alreadyMatches) return

        val strategyKey = "$fieldId:$strategyId"
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    mutatingFieldIds = it.mutatingFieldIds + fieldId,
                    mutatingStrategyKey = strategyKey,
                    selectionError = null
                )
            }
            when (
                val res = analysisRepository.updateStrategySelection(
                    analysisId = currentEnvelope.analysisId,
                    fieldId = fieldId,
                    strategyId = strategyId,
                    selectionStatus = status
                )
            ) {
                is AnalysisCallResult.Success -> {
                    val updatedLocal = applySelectionResult(currentEnvelope, res.data)
                    val syncedEnvelope = when (
                        val refresh = analysisRepository.getAnalysisResult(currentEnvelope.analysisId)
                    ) {
                        is AnalysisCallResult.Success -> refresh.data
                        is AnalysisCallResult.Failure -> updatedLocal
                    }
                    _uiState.update {
                        it.copy(
                            envelopeState = UiState.Success(syncedEnvelope),
                            mutatingFieldIds = it.mutatingFieldIds - fieldId,
                            mutatingStrategyKey = null,
                            selectionError = null
                        )
                    }
                }
                is AnalysisCallResult.Failure -> {
                    _uiState.update {
                        it.copy(
                            mutatingFieldIds = it.mutatingFieldIds - fieldId,
                            mutatingStrategyKey = null,
                            selectionError = res.error
                        )
                    }
                }
            }
        }
    }

    fun dismissSelectionError() {
        _uiState.update { it.copy(selectionError = null) }
    }

    private fun applySelectionResult(
        envelope: AnalysisResultEnvelope,
        selection: StrategySelectionResult
    ): AnalysisResultEnvelope {
        val updatedPlans = envelope.result.fieldPlans.map { plan ->
            if (plan.fieldId != selection.fieldId) {
                plan
            } else {
                val updatedStrategies = plan.strategies.map { strategy ->
                    when {
                        strategy.strategyId == selection.strategyId -> {
                            strategy.copy(
                                seasons = strategy.seasons.map {
                                    it.copy(selectionStatus = selection.selectionStatus.apiValue)
                                }
                            )
                        }
                        selection.selectionStatus == StrategySelectionStatus.SELECTED &&
                            strategy.displaySelectionStatus == StrategyDisplaySelection.SELECTED -> {
                            // Selecting a new strategy clears the previous selection back to "suggested"
                            // matching backend `upsert_analysis_selection` + `merge_selections_into_result`.
                            strategy.copy(
                                seasons = strategy.seasons.map {
                                    it.copy(selectionStatus = "suggested")
                                }
                            )
                        }
                        else -> strategy
                    }
                }
                plan.copy(strategies = updatedStrategies)
            }
        }
        return envelope.copy(
            result = envelope.result.copy(fieldPlans = updatedPlans)
        )
    }
}

