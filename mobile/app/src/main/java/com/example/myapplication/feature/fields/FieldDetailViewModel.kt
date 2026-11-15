package com.example.myapplication.feature.fields

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.myapplication.core.common.UiState
import com.example.myapplication.domain.field.FieldDetail
import com.example.myapplication.domain.field.FieldError
import com.example.myapplication.domain.field.FieldRepository
import com.example.myapplication.domain.field.FieldResult
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class FieldDetailUiState(
    val fieldState: UiState<FieldDetail> = UiState.Loading,
    val fieldError: FieldError? = null,
    val showDeleteConfirmation: Boolean = false,
    val isDeleting: Boolean = false,
    val deleteError: FieldError? = null,
    val deletedSuccessfully: Boolean = false
)

@HiltViewModel
class FieldDetailViewModel @Inject constructor(
    private val fieldRepository: FieldRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(FieldDetailUiState())
    val uiState: StateFlow<FieldDetailUiState> = _uiState.asStateFlow()

    private var loadedKey: String? = null

    fun loadField(farmId: String, fieldId: String, forceRefresh: Boolean = false) {
        val key = "$farmId/$fieldId"
        if (!forceRefresh && loadedKey == key && _uiState.value.fieldState is UiState.Success) {
            return
        }
        loadedKey = key
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    fieldState = UiState.Loading,
                    fieldError = null,
                    deleteError = null
                )
            }
            when (val result = fieldRepository.getField(farmId, fieldId)) {
                is FieldResult.Success -> {
                    _uiState.update {
                        it.copy(
                            fieldState = UiState.Success(result.data),
                            fieldError = null
                        )
                    }
                }
                is FieldResult.Failure -> {
                    _uiState.update {
                        it.copy(
                            fieldState = UiState.Error(result.error.message),
                            fieldError = result.error
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

    fun confirmDelete(farmId: String, fieldId: String) {
        if (_uiState.value.isDeleting) return
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isDeleting = true,
                    showDeleteConfirmation = false,
                    deleteError = null
                )
            }
            when (val result = fieldRepository.deleteField(farmId, fieldId)) {
                is FieldResult.Success -> {
                    _uiState.update {
                        it.copy(
                            isDeleting = false,
                            deletedSuccessfully = true
                        )
                    }
                }
                is FieldResult.Failure -> {
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

