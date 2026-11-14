package com.example.myapplication.feature.fields

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.myapplication.core.common.UiState
import com.example.myapplication.domain.field.FieldError
import com.example.myapplication.domain.field.FieldRepository
import com.example.myapplication.domain.field.FieldResult
import com.example.myapplication.domain.field.FieldSummary
import com.example.myapplication.domain.field.SoilType
import com.example.myapplication.domain.field.WaterAvailability
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class FieldsListUiState(
    val farmId: String = "",
    val fieldsState: UiState<List<FieldSummary>> = UiState.Loading,
    val selectedSoilFilter: SoilType? = null,
    val selectedWaterFilter: WaterAvailability? = null,
    val isRefreshing: Boolean = false,
    val isLoadingMore: Boolean = false,
    val nextCursor: String? = null,
    val hasMore: Boolean = false,
    val paginationError: FieldError? = null,
    val lastError: FieldError? = null
)

@HiltViewModel
class FieldsListViewModel @Inject constructor(
    private val fieldRepository: FieldRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(FieldsListUiState())
    val uiState: StateFlow<FieldsListUiState> = _uiState.asStateFlow()

    private var initializedFarmId: String? = null

    fun initialize(farmId: String) {
        if (initializedFarmId == farmId && _uiState.value.fieldsState !is UiState.Error) return
        initializedFarmId = farmId
        _uiState.update { it.copy(farmId = farmId) }
        loadFields(farmId)
    }

    fun loadFields(farmId: String = _uiState.value.farmId) {
        if (farmId.isBlank()) return
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    farmId = farmId,
                    fieldsState = UiState.Loading,
                    isRefreshing = false,
                    isLoadingMore = false,
                    paginationError = null,
                    lastError = null
                )
            }
            fetchFirstPage(farmId = farmId, isRefresh = false)
        }
    }

    fun refresh() {
        val farmId = _uiState.value.farmId
        if (farmId.isBlank() || _uiState.value.isRefreshing) return
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isRefreshing = true,
                    paginationError = null,
                    lastError = null
                )
            }
            fetchFirstPage(farmId = farmId, isRefresh = true)
        }
    }

    fun setSoilFilter(soilType: SoilType?) {
        _uiState.update { it.copy(selectedSoilFilter = soilType) }
        loadFields()
    }

    fun loadMore() {
        val current = _uiState.value
        val cursor = current.nextCursor
        if (current.farmId.isBlank() || !current.hasMore || cursor.isNullOrBlank() || current.isLoadingMore) return

        val existing = (current.fieldsState as? UiState.Success)?.data ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isLoadingMore = true, paginationError = null) }
            when (
                val result = fieldRepository.listFields(
                    farmId = current.farmId,
                    cursor = cursor,
                    soilType = current.selectedSoilFilter,
                    waterAvailability = current.selectedWaterFilter
                )
            ) {
                is FieldResult.Success -> {
                    val combined = (existing + result.data.items).distinctBy { it.fieldId }
                    _uiState.update {
                        it.copy(
                            fieldsState = if (combined.isEmpty()) UiState.Empty else UiState.Success(combined),
                            isLoadingMore = false,
                            nextCursor = result.data.nextCursor,
                            hasMore = result.data.hasMore
                        )
                    }
                }
                is FieldResult.Failure -> {
                    _uiState.update {
                        it.copy(
                            isLoadingMore = false,
                            paginationError = result.error
                        )
                    }
                }
            }
        }
    }

    fun onFieldSaved(field: FieldSummary) {
        if (field.farmId != _uiState.value.farmId) return
        _uiState.update { current ->
            val existing = (current.fieldsState as? UiState.Success)?.data.orEmpty()
            val updated = if (existing.any { it.fieldId == field.fieldId }) {
                existing.map { if (it.fieldId == field.fieldId) field else it }
            } else {
                listOf(field) + existing
            }
            current.copy(
                fieldsState = UiState.Success(updated),
                lastError = null
            )
        }
    }

    fun onFieldDeleted(fieldId: String) {
        _uiState.update { current ->
            val existing = (current.fieldsState as? UiState.Success)?.data ?: return@update current
            val remaining = existing.filterNot { it.fieldId == fieldId }
            current.copy(
                fieldsState = if (remaining.isEmpty()) UiState.Empty else UiState.Success(remaining)
            )
        }
    }

    private suspend fun fetchFirstPage(farmId: String, isRefresh: Boolean) {
        val current = _uiState.value
        when (
            val result = fieldRepository.listFields(
                farmId = farmId,
                soilType = current.selectedSoilFilter,
                waterAvailability = current.selectedWaterFilter
            )
        ) {
            is FieldResult.Success -> {
                val page = result.data
                _uiState.update {
                    it.copy(
                        fieldsState = if (page.items.isEmpty()) UiState.Empty else UiState.Success(page.items),
                        isRefreshing = false,
                        nextCursor = page.nextCursor,
                        hasMore = page.hasMore,
                        lastError = null
                    )
                }
            }
            is FieldResult.Failure -> {
                _uiState.update { state ->
                    val keepExisting = isRefresh && state.fieldsState is UiState.Success
                    state.copy(
                        fieldsState = if (keepExisting) state.fieldsState else UiState.Error(result.error.message),
                        isRefreshing = false,
                        lastError = result.error
                    )
                }
            }
        }
    }
}

