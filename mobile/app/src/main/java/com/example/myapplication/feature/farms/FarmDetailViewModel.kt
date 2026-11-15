package com.example.myapplication.feature.farms

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.myapplication.core.common.UiState
import com.example.myapplication.domain.farm.Farm
import com.example.myapplication.domain.farm.FarmError
import com.example.myapplication.domain.farm.FarmRepository
import com.example.myapplication.domain.farm.FarmResult
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class FarmDetailUiState(
    val farmState: UiState<Farm> = UiState.Loading,
    val farmError: FarmError? = null,
    val showDeleteConfirmation: Boolean = false,
    val isDeleting: Boolean = false,
    val deleteError: FarmError? = null,
    val deletedSuccessfully: Boolean = false
)

@HiltViewModel
class FarmDetailViewModel @Inject constructor(
    private val farmRepository: FarmRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(FarmDetailUiState())
    val uiState: StateFlow<FarmDetailUiState> = _uiState.asStateFlow()

    private var loadedFarmId: String? = null

    fun loadFarm(farmId: String, forceRefresh: Boolean = false) {
        if (!forceRefresh && loadedFarmId == farmId && _uiState.value.farmState is UiState.Success) {
            return
        }
        loadedFarmId = farmId
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    farmState = UiState.Loading,
                    farmError = null,
                    deleteError = null
                )
            }
            when (val result = farmRepository.getFarm(farmId)) {
                is FarmResult.Success -> {
                    _uiState.update {
                        it.copy(
                            farmState = UiState.Success(result.data),
                            farmError = null
                        )
                    }
                }
                is FarmResult.Failure -> {
                    _uiState.update {
                        it.copy(
                            farmState = UiState.Error(result.error.message),
                            farmError = result.error
                        )
                    }
                }
            }
        }
    }

    fun requestDelete() {
        _uiState.update { it.copy(showDeleteConfirmation = true, deleteError = null) }
    }

    fun dismissDelete() {
        _uiState.update { it.copy(showDeleteConfirmation = false) }
    }

    fun confirmDelete(farmId: String) {
        if (_uiState.value.isDeleting) return
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isDeleting = true,
                    showDeleteConfirmation = false,
                    deleteError = null
                )
            }
            when (val result = farmRepository.deleteFarm(farmId)) {
                is FarmResult.Success -> {
                    _uiState.update {
                        it.copy(
                            isDeleting = false,
                            deletedSuccessfully = true
                        )
                    }
                }
                is FarmResult.Failure -> {
                    _uiState.update {
                        it.copy(
                            isDeleting = false,
                            deleteError = result.error
                        )
                    }
                }
            }
        }
    }
}

