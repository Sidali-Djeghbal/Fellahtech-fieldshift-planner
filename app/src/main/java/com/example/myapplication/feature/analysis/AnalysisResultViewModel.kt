package com.example.myapplication.feature.analysis

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.myapplication.core.common.UiState
import com.example.myapplication.domain.analysis.AnalysisCallResult
import com.example.myapplication.domain.analysis.AnalysisError
import com.example.myapplication.domain.analysis.AnalysisRepository
import com.example.myapplication.domain.analysis.AnalysisResultEnvelope
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class AnalysisResultUiState(
    val envelopeState: UiState<AnalysisResultEnvelope> = UiState.Loading,
    val error: AnalysisError? = null
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
}

