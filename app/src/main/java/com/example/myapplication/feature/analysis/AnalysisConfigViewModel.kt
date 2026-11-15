package com.example.myapplication.feature.analysis

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.myapplication.core.common.AppLanguage
import com.example.myapplication.domain.analysis.ActiveAnalysisRequest
import com.example.myapplication.domain.analysis.AnalysisCallResult
import com.example.myapplication.domain.analysis.AnalysisError
import com.example.myapplication.domain.analysis.AnalysisQueuedJob
import com.example.myapplication.domain.analysis.AnalysisRepository
import com.example.myapplication.domain.analysis.AnalysisSubmitInput
import com.example.myapplication.domain.analysis.CropCatalogItem
import com.example.myapplication.domain.analysis.CycleMode
import com.example.myapplication.domain.analysis.MarketPreference
import com.example.myapplication.domain.analysis.PlanningConfig
import com.example.myapplication.domain.analysis.PriorityWeights
import com.example.myapplication.domain.analysis.ScenarioOverrides
import com.example.myapplication.domain.farm.Farm
import com.example.myapplication.domain.farm.FarmRepository
import com.example.myapplication.domain.farm.FarmResult
import com.example.myapplication.domain.field.FieldRepository
import com.example.myapplication.domain.field.FieldResult
import com.example.myapplication.domain.field.FieldSummary
import com.example.myapplication.domain.field.Season
import dagger.hilt.android.lifecycle.HiltViewModel
import java.util.UUID
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class AnalysisValidationError {
    FARM_REQUIRED,
    FIELDS_COUNT_INVALID,
    START_YEAR_INVALID,
    HORIZON_INVALID,
    WEIGHTS_INVALID,
    CROP_OVERLAP
}

data class AnalysisConfigUiState(
    val language: AppLanguage = AppLanguage.ENGLISH,
    val isLoadingInitial: Boolean = true,
    val farms: List<Farm> = emptyList(),
    val selectedFarmId: String? = null,
    val fields: List<FieldSummary> = emptyList(),
    val isLoadingFields: Boolean = false,
    val selectedFieldIds: Set<String> = emptySet(),
    val catalogItems: List<CropCatalogItem> = emptyList(),
    val isLoadingCatalog: Boolean = false,
    val startSeason: Season = Season.AUTUMN,
    val startYearText: String = "2026",
    val horizonSeasons: Int = 3,
    val cycleMode: CycleMode = CycleMode.ANNUAL_ROTATION,
    val droughtSimulationEnabled: Boolean = false,
    val weights: PriorityWeights = PriorityWeights(),
    val marketPreference: MarketPreference = MarketPreference.MIXED,
    val targetCropIds: Set<String> = emptySet(),
    val excludedCropIds: Set<String> = emptySet(),
    val equipmentConstraintsText: String = "",
    val activeRequestToResume: ActiveAnalysisRequest? = null,
    val validationError: AnalysisValidationError? = null,
    val isSubmitting: Boolean = false,
    val submitError: AnalysisError? = null,
    val queuedJob: AnalysisQueuedJob? = null
)

@HiltViewModel
class AnalysisConfigViewModel @Inject constructor(
    private val farmRepository: FarmRepository,
    private val fieldRepository: FieldRepository,
    private val analysisRepository: AnalysisRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(AnalysisConfigUiState())
    val uiState: StateFlow<AnalysisConfigUiState> = _uiState.asStateFlow()

    private var initialized = false
    private var currentIdempotencyKey: String? = null

    fun initialize(language: AppLanguage) {
        if (initialized && _uiState.value.language == language) {
            refreshActiveRequestBanner()
            return
        }
        if (initialized && _uiState.value.language != language) {
            invalidateIdempotencyKey()
        }
        initialized = true
        _uiState.update { it.copy(language = language) }
        loadInitialData(language)
    }

    fun refreshActiveRequestBanner() {
        viewModelScope.launch {
            val active = analysisRepository.getActiveRequest()
            _uiState.update { it.copy(activeRequestToResume = active) }
        }
    }

    fun reloadCatalog(language: AppLanguage = _uiState.value.language) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoadingCatalog = true) }
            when (val res = analysisRepository.getCatalog(language = language, limit = 50)) {
                is AnalysisCallResult.Success -> {
                    _uiState.update {
                        it.copy(
                            isLoadingCatalog = false,
                            catalogItems = res.data.items
                        )
                    }
                }
                is AnalysisCallResult.Failure -> {
                    _uiState.update { it.copy(isLoadingCatalog = false) }
                }
            }
        }
    }

    private fun loadInitialData(language: AppLanguage) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoadingInitial = true) }
            val active = analysisRepository.getActiveRequest()
            val farmsResult = farmRepository.listFarms(limit = 50)
            val farms = when (farmsResult) {
                is FarmResult.Success -> farmsResult.data.items
                is FarmResult.Failure -> emptyList()
            }
            val defaultFarmId = _uiState.value.selectedFarmId
                ?.takeIf { id -> farms.any { it.id == id } }
                ?: farms.firstOrNull()?.id

            _uiState.update {
                it.copy(
                    isLoadingInitial = false,
                    farms = farms,
                    selectedFarmId = defaultFarmId,
                    activeRequestToResume = active
                )
            }

            if (defaultFarmId != null) {
                loadFieldsForFarm(defaultFarmId)
            }
            reloadCatalog(language)
        }
    }

    fun selectFarm(farmId: String) {
        if (_uiState.value.selectedFarmId == farmId) return
        invalidateIdempotencyKey()
        _uiState.update {
            it.copy(
                selectedFarmId = farmId,
                selectedFieldIds = emptySet(),
                validationError = null,
                submitError = null
            )
        }
        loadFieldsForFarm(farmId)
    }

    private fun loadFieldsForFarm(farmId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoadingFields = true) }
            when (val res = fieldRepository.listFields(farmId = farmId, limit = 50)) {
                is FieldResult.Success -> {
                    val fields = res.data.items
                    val autoSelected = if (fields.size == 1) {
                        setOf(fields.first().fieldId)
                    } else {
                        emptySet()
                    }
                    _uiState.update {
                        it.copy(
                            isLoadingFields = false,
                            fields = fields,
                            selectedFieldIds = autoSelected
                        )
                    }
                }
                is FieldResult.Failure -> {
                    _uiState.update {
                        it.copy(
                            isLoadingFields = false,
                            fields = emptyList(),
                            selectedFieldIds = emptySet()
                        )
                    }
                }
            }
        }
    }

    fun toggleFieldSelection(fieldId: String) {
        invalidateIdempotencyKey()
        _uiState.update { state ->
            val updated = state.selectedFieldIds.toMutableSet()
            if (!updated.add(fieldId)) {
                updated.remove(fieldId)
            } else if (updated.size > 10) {
                return@update state.copy(validationError = AnalysisValidationError.FIELDS_COUNT_INVALID)
            }
            state.copy(selectedFieldIds = updated, validationError = null, submitError = null)
        }
    }

    fun onStartSeasonChanged(season: Season) {
        invalidateIdempotencyKey()
        _uiState.update { it.copy(startSeason = season, validationError = null, submitError = null) }
    }

    fun onStartYearChanged(value: String) {
        invalidateIdempotencyKey()
        _uiState.update { it.copy(startYearText = value, validationError = null, submitError = null) }
    }

    fun onHorizonChanged(horizon: Int) {
        invalidateIdempotencyKey()
        _uiState.update {
            it.copy(
                horizonSeasons = horizon.coerceIn(1, 6),
                validationError = null,
                submitError = null
            )
        }
    }

    fun onCycleModeChanged(mode: CycleMode) {
        invalidateIdempotencyKey()
        _uiState.update { it.copy(cycleMode = mode, validationError = null, submitError = null) }
    }

    fun onDroughtSimulationToggled(enabled: Boolean) {
        invalidateIdempotencyKey()
        _uiState.update {
            it.copy(
                droughtSimulationEnabled = enabled,
                validationError = null,
                submitError = null
            )
        }
    }

    fun updateWeights(transform: (PriorityWeights) -> PriorityWeights) {
        invalidateIdempotencyKey()
        _uiState.update {
            it.copy(
                weights = transform(it.weights),
                validationError = null,
                submitError = null
            )
        }
    }

    fun onMarketPreferenceChanged(pref: MarketPreference) {
        invalidateIdempotencyKey()
        _uiState.update { it.copy(marketPreference = pref, validationError = null, submitError = null) }
    }

    fun toggleTargetCrop(cropId: String) {
        invalidateIdempotencyKey()
        _uiState.update { state ->
            val targets = state.targetCropIds.toMutableSet()
            val excluded = state.excludedCropIds.toMutableSet()
            if (!targets.add(cropId)) {
                targets.remove(cropId)
            } else {
                excluded.remove(cropId)
            }
            state.copy(
                targetCropIds = targets.take(20).toSet(),
                excludedCropIds = excluded,
                validationError = null,
                submitError = null
            )
        }
    }

    fun toggleExcludedCrop(cropId: String) {
        invalidateIdempotencyKey()
        _uiState.update { state ->
            val excluded = state.excludedCropIds.toMutableSet()
            val targets = state.targetCropIds.toMutableSet()
            if (!excluded.add(cropId)) {
                excluded.remove(cropId)
            } else {
                targets.remove(cropId)
            }
            state.copy(
                excludedCropIds = excluded.take(20).toSet(),
                targetCropIds = targets,
                validationError = null,
                submitError = null
            )
        }
    }

    fun onEquipmentConstraintsChanged(value: String) {
        invalidateIdempotencyKey()
        _uiState.update {
            it.copy(
                equipmentConstraintsText = value,
                validationError = null,
                submitError = null
            )
        }
    }

    fun consumeQueuedJob() {
        _uiState.update { it.copy(queuedJob = null) }
    }

    fun submit() {
        val state = _uiState.value
        if (state.isSubmitting) return

        val farmId = state.selectedFarmId?.takeIf { it.isNotBlank() }
        if (farmId == null) {
            _uiState.update { it.copy(validationError = AnalysisValidationError.FARM_REQUIRED) }
            return
        }
        if (state.selectedFieldIds.isEmpty() || state.selectedFieldIds.size > 10) {
            _uiState.update { it.copy(validationError = AnalysisValidationError.FIELDS_COUNT_INVALID) }
            return
        }
        val startYear = state.startYearText.trim().toIntOrNull()
        if (startYear == null || startYear !in 2020..2100) {
            _uiState.update { it.copy(validationError = AnalysisValidationError.START_YEAR_INVALID) }
            return
        }
        if (state.horizonSeasons !in 1..6) {
            _uiState.update { it.copy(validationError = AnalysisValidationError.HORIZON_INVALID) }
            return
        }
        val w = state.weights
        if (w.waterSaving !in 0..100 ||
            w.soilImprovement !in 0..100 ||
            w.income !in 0..100 ||
            w.riskReduction !in 0..100 ||
            w.forageValue !in 0..100
        ) {
            _uiState.update { it.copy(validationError = AnalysisValidationError.WEIGHTS_INVALID) }
            return
        }
        if (state.targetCropIds.intersect(state.excludedCropIds).isNotEmpty()) {
            _uiState.update { it.copy(validationError = AnalysisValidationError.CROP_OVERLAP) }
            return
        }

        val equipment = state.equipmentConstraintsText
            .split(',')
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .take(20)

        val scenarioOverrides = if (state.droughtSimulationEnabled) {
            ScenarioOverrides(tempDeltaC = 0.0, precipPctDelta = -20.0)
        } else {
            null
        }

        val input = AnalysisSubmitInput(
            farmId = farmId,
            language = state.language,
            planning = PlanningConfig(
                startSeason = state.startSeason,
                startYear = startYear,
                horizonSeasons = state.horizonSeasons,
                cycleMode = state.cycleMode,
                scenarioOverrides = scenarioOverrides
            ),
            weights = w,
            marketPreference = state.marketPreference,
            targetCropIds = state.targetCropIds.toList(),
            excludedCropIds = state.excludedCropIds.toList(),
            equipmentConstraints = equipment,
            fieldIds = state.selectedFieldIds.toList()
        )

        val idempotencyKey = currentIdempotencyKey ?: UUID.randomUUID().toString().also {
            currentIdempotencyKey = it
        }

        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isSubmitting = true,
                    validationError = null,
                    submitError = null
                )
            }
            when (val result = analysisRepository.submitAnalysis(input, idempotencyKey)) {
                is AnalysisCallResult.Success -> {
                    val job = result.data
                    val active = ActiveAnalysisRequest(
                        requestId = job.requestId,
                        farmId = farmId,
                        pollIntervalMs = job.pollIntervalMs,
                        createdAtEpochMs = System.currentTimeMillis()
                    )
                    analysisRepository.saveActiveRequest(active)
                    currentIdempotencyKey = null
                    _uiState.update {
                        it.copy(
                            isSubmitting = false,
                            activeRequestToResume = active,
                            queuedJob = job
                        )
                    }
                }
                is AnalysisCallResult.Failure -> {
                    if (result.error is AnalysisError.Api && result.error.isCatalogMismatch) {
                        reloadCatalog(state.language)
                    }
                    // Preserve currentIdempotencyKey on transient errors so retries reuse the same key.
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

    private fun invalidateIdempotencyKey() {
        currentIdempotencyKey = null
    }
}

