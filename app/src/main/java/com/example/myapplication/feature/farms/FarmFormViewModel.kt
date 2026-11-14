package com.example.myapplication.feature.farms

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.myapplication.domain.farm.Farm
import com.example.myapplication.domain.farm.FarmError
import com.example.myapplication.domain.farm.FarmRepository
import com.example.myapplication.domain.farm.FarmResult
import com.example.myapplication.domain.farm.FarmWriteInput
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class FarmFieldError {
    REQUIRED,
    TOO_LONG
}

data class FarmFormUiState(
    val isEditMode: Boolean = false,
    val farmId: String? = null,
    val isLoadingExisting: Boolean = false,
    val loadError: FarmError? = null,
    val name: String = "",
    val country: String = "",
    val region: String = "",
    val commune: String = "",
    val nameError: FarmFieldError? = null,
    val countryError: FarmFieldError? = null,
    val regionError: FarmFieldError? = null,
    val communeError: FarmFieldError? = null,
    val isSubmitting: Boolean = false,
    val submitError: FarmError? = null,
    val savedFarm: Farm? = null
)

@HiltViewModel
class FarmFormViewModel @Inject constructor(
    private val farmRepository: FarmRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(FarmFormUiState())
    val uiState: StateFlow<FarmFormUiState> = _uiState.asStateFlow()

    private var initializedForId: String? = "__UNINITIALIZED__"

    fun initialize(farmId: String?) {
        if (initializedForId == farmId) return
        initializedForId = farmId
        if (farmId == null) {
            _uiState.value = FarmFormUiState(isEditMode = false, farmId = null)
        } else {
            loadExistingFarm(farmId)
        }
    }

    fun retryLoadExisting() {
        val id = _uiState.value.farmId ?: return
        loadExistingFarm(id)
    }

    private fun loadExistingFarm(farmId: String) {
        viewModelScope.launch {
            _uiState.value = FarmFormUiState(
                isEditMode = true,
                farmId = farmId,
                isLoadingExisting = true
            )
            when (val result = farmRepository.getFarm(farmId)) {
                is FarmResult.Success -> {
                    val farm = result.data
                    _uiState.update {
                        it.copy(
                            isLoadingExisting = false,
                            loadError = null,
                            name = farm.name,
                            country = farm.country,
                            region = farm.region,
                            commune = farm.commune.orEmpty()
                        )
                    }
                }
                is FarmResult.Failure -> {
                    _uiState.update {
                        it.copy(
                            isLoadingExisting = false,
                            loadError = result.error
                        )
                    }
                }
            }
        }
    }

    fun onNameChanged(value: String) {
        _uiState.update { it.copy(name = value, nameError = null, submitError = null) }
    }

    fun onCountryChanged(value: String) {
        _uiState.update { it.copy(country = value, countryError = null, submitError = null) }
    }

    fun onRegionChanged(value: String) {
        _uiState.update { it.copy(region = value, regionError = null, submitError = null) }
    }

    fun onCommuneChanged(value: String) {
        _uiState.update { it.copy(commune = value, communeError = null, submitError = null) }
    }

    fun submit() {
        val current = _uiState.value
        if (current.isSubmitting || current.isLoadingExisting) return

        val trimmedName = current.name.trim()
        val trimmedCountry = current.country.trim()
        val trimmedRegion = current.region.trim()
        val trimmedCommune = current.commune.trim()

        val nameError = when {
            trimmedName.isEmpty() -> FarmFieldError.REQUIRED
            trimmedName.length > MAX_NAME_LENGTH -> FarmFieldError.TOO_LONG
            else -> null
        }
        val countryError = when {
            trimmedCountry.isEmpty() -> FarmFieldError.REQUIRED
            trimmedCountry.length > MAX_COUNTRY_LENGTH -> FarmFieldError.TOO_LONG
            else -> null
        }
        val regionError = when {
            trimmedRegion.isEmpty() -> FarmFieldError.REQUIRED
            trimmedRegion.length > MAX_REGION_LENGTH -> FarmFieldError.TOO_LONG
            else -> null
        }
        val communeError = if (trimmedCommune.length > MAX_COMMUNE_LENGTH) {
            FarmFieldError.TOO_LONG
        } else {
            null
        }

        if (nameError != null || countryError != null || regionError != null || communeError != null) {
            _uiState.update {
                it.copy(
                    nameError = nameError,
                    countryError = countryError,
                    regionError = regionError,
                    communeError = communeError
                )
            }
            return
        }

        val input = FarmWriteInput(
            name = trimmedName,
            country = trimmedCountry,
            region = trimmedRegion,
            commune = trimmedCommune.takeIf { it.isNotEmpty() }
        )

        viewModelScope.launch {
            _uiState.update { it.copy(isSubmitting = true, submitError = null) }
            val result = if (current.isEditMode && current.farmId != null) {
                farmRepository.updateFarm(current.farmId, input)
            } else {
                farmRepository.createFarm(input)
            }
            when (result) {
                is FarmResult.Success -> {
                    _uiState.update {
                        it.copy(
                            isSubmitting = false,
                            savedFarm = result.data
                        )
                    }
                }
                is FarmResult.Failure -> {
                    _uiState.update {
                        it.copy(
                            isSubmitting = false,
                            submitError = result.error
                        )
                    }
                }
            }
        }
    }

    companion object {
        const val MAX_NAME_LENGTH = 120
        const val MAX_COUNTRY_LENGTH = 80
        const val MAX_REGION_LENGTH = 80
        const val MAX_COMMUNE_LENGTH = 120
    }
}

