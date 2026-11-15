package com.example.myapplication.feature.fields

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.myapplication.core.location.GpsLocationResult
import com.example.myapplication.core.location.LocationProvider
import com.example.myapplication.data.field.toSummary
import com.example.myapplication.domain.field.CropHistoryEntry
import com.example.myapplication.domain.field.FieldError
import com.example.myapplication.domain.field.FieldLocation
import com.example.myapplication.domain.field.FieldRepository
import com.example.myapplication.domain.field.FieldResult
import com.example.myapplication.domain.field.FieldSummary
import com.example.myapplication.domain.field.FieldWriteInput
import com.example.myapplication.domain.field.IrrigationSystem
import com.example.myapplication.domain.field.Season
import com.example.myapplication.domain.field.SoilType
import com.example.myapplication.domain.field.WaterAvailability
import com.example.myapplication.domain.field.WaterSource
import dagger.hilt.android.lifecycle.HiltViewModel
import java.util.UUID
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class GpsCaptureStatus {
    IDLE,
    ACQUIRING,
    CAPTURED,
    PERMISSION_DENIED,
    UNAVAILABLE,
    TIMEOUT,
    ERROR
}

enum class FieldFormValidationError {
    FIELD_ID_INVALID,
    FIELD_NAME_INVALID,
    LATITUDE_INVALID,
    LONGITUDE_INVALID,
    AREA_INVALID,
    ELEVATION_INVALID,
    SOIL_PH_INVALID,
    ORGANIC_MATTER_INVALID,
    SOIL_TEST_DATE_INVALID,
    CROP_HISTORY_COUNT_INVALID,
    CROP_HISTORY_YEAR_INVALID,
    CROP_HISTORY_CROP_INVALID
}

data class CropHistoryFormRow(
    val rowId: String = UUID.randomUUID().toString(),
    val season: Season = Season.SPRING,
    val yearText: String = "2025",
    val cropNameRaw: String = "",
    val cropId: String = "",
    val yieldText: String = "",
    val notes: String = ""
)

data class FieldFormUiState(
    val isEditMode: Boolean = false,
    val farmId: String = "",
    val fieldId: String = "",
    val isLoadingExisting: Boolean = false,
    val loadError: FieldError? = null,
    val fieldName: String = "",
    val isUnverifiedDemoParcel: Boolean = false,
    val latitudeText: String = "",
    val longitudeText: String = "",
    val gpsStatus: GpsCaptureStatus = GpsCaptureStatus.IDLE,
    val gpsAccuracyMeters: Float? = null,
    val gpsErrorMessage: String? = null,
    val areaText: String = "",
    val elevationText: String = "",
    val soilType: SoilType = SoilType.LOAMY,
    val soilPhText: String = "",
    val organicMatterText: String = "",
    val soilTestDateText: String = "",
    val waterAvailability: WaterAvailability = WaterAvailability.MODERATE,
    val waterSource: WaterSource = WaterSource.WELL,
    val waterSourceOtherText: String = "",
    val irrigationSystem: IrrigationSystem = IrrigationSystem.DRIP,
    val cropHistory: List<CropHistoryFormRow> = listOf(CropHistoryFormRow()),
    val validationError: FieldFormValidationError? = null,
    val isSubmitting: Boolean = false,
    val submitError: FieldError? = null,
    val savedField: FieldSummary? = null
)

@HiltViewModel
class FieldFormViewModel @Inject constructor(
    private val fieldRepository: FieldRepository,
    private val locationProvider: LocationProvider
) : ViewModel() {

    private val _uiState = MutableStateFlow(FieldFormUiState())
    val uiState: StateFlow<FieldFormUiState> = _uiState.asStateFlow()

    private var initializedKey: String? = null

    fun initialize(farmId: String, fieldId: String?) {
        val key = "$farmId/${fieldId ?: "__CREATE__"}"
        if (initializedKey == key) return
        initializedKey = key

        if (fieldId == null) {
            val generatedId = "field_${UUID.randomUUID().toString().replace("-", "").take(8)}"
            _uiState.value = FieldFormUiState(
                isEditMode = false,
                farmId = farmId,
                fieldId = generatedId
            )
        } else {
            loadExistingField(farmId, fieldId)
        }
    }

    fun retryLoadExisting() {
        val current = _uiState.value
        if (current.isEditMode && current.fieldId.isNotBlank()) {
            loadExistingField(current.farmId, current.fieldId)
        }
    }

    private fun loadExistingField(farmId: String, fieldId: String) {
        viewModelScope.launch {
            _uiState.value = FieldFormUiState(
                isEditMode = true,
                farmId = farmId,
                fieldId = fieldId,
                isLoadingExisting = true
            )
            when (val result = fieldRepository.getField(farmId, fieldId)) {
                is FieldResult.Success -> {
                    val d = result.data
                    _uiState.update {
                        it.copy(
                            isLoadingExisting = false,
                            loadError = null,
                            fieldName = d.fieldName,
                            isUnverifiedDemoParcel = d.isUnverifiedDemoParcel,
                            latitudeText = d.location.latitude.toString(),
                            longitudeText = d.location.longitude.toString(),
                            areaText = d.areaHectares.toString(),
                            elevationText = d.elevationM?.toString().orEmpty(),
                            soilType = d.soil.soilType,
                            soilPhText = d.soil.soilPh?.toString().orEmpty(),
                            organicMatterText = d.soil.organicMatterPercent?.toString().orEmpty(),
                            soilTestDateText = d.soil.soilTestDate.orEmpty(),
                            waterAvailability = d.water.availability,
                            waterSource = d.water.source,
                            waterSourceOtherText = d.water.sourceOther.orEmpty(),
                            irrigationSystem = d.water.irrigationSystem,
                            cropHistory = if (d.cropHistory.isEmpty()) {
                                listOf(CropHistoryFormRow())
                            } else {
                                d.cropHistory.map { entry ->
                                    CropHistoryFormRow(
                                        season = entry.season,
                                        yearText = entry.year.toString(),
                                        cropNameRaw = entry.cropNameRaw.orEmpty(),
                                        cropId = entry.cropId.orEmpty(),
                                        yieldText = entry.yieldTonsPerHectare?.toString().orEmpty(),
                                        notes = entry.notes.orEmpty()
                                    )
                                }
                            }
                        )
                    }
                }
                is FieldResult.Failure -> {
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

    fun hasLocationPermission(): Boolean = locationProvider.hasLocationPermission()

    fun onLocationPermissionDenied() {
        _uiState.update {
            it.copy(
                gpsStatus = GpsCaptureStatus.PERMISSION_DENIED,
                gpsErrorMessage = null
            )
        }
    }

    fun captureDeviceGps() {
        if (_uiState.value.gpsStatus == GpsCaptureStatus.ACQUIRING) return
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    gpsStatus = GpsCaptureStatus.ACQUIRING,
                    gpsErrorMessage = null
                )
            }
            when (val result = locationProvider.getCurrentCoordinates()) {
                is GpsLocationResult.Success -> {
                    _uiState.update {
                        it.copy(
                            latitudeText = result.latitude.toString(),
                            longitudeText = result.longitude.toString(),
                            gpsStatus = GpsCaptureStatus.CAPTURED,
                            gpsAccuracyMeters = result.accuracyMeters,
                            gpsErrorMessage = null,
                            validationError = null
                        )
                    }
                }
                is GpsLocationResult.PermissionDenied -> {
                    _uiState.update {
                        it.copy(gpsStatus = GpsCaptureStatus.PERMISSION_DENIED)
                    }
                }
                is GpsLocationResult.LocationUnavailable -> {
                    _uiState.update {
                        it.copy(gpsStatus = GpsCaptureStatus.UNAVAILABLE)
                    }
                }
                is GpsLocationResult.Timeout -> {
                    _uiState.update {
                        it.copy(gpsStatus = GpsCaptureStatus.TIMEOUT)
                    }
                }
                is GpsLocationResult.Error -> {
                    _uiState.update {
                        it.copy(
                            gpsStatus = GpsCaptureStatus.ERROR,
                            gpsErrorMessage = result.message
                        )
                    }
                }
            }
        }
    }

    fun onFieldIdChanged(v: String) = _uiState.update { it.copy(fieldId = v, validationError = null, submitError = null) }
    fun onFieldNameChanged(v: String) = _uiState.update { it.copy(fieldName = v, validationError = null, submitError = null) }
    fun onLatitudeChanged(v: String) = _uiState.update { it.copy(latitudeText = v, validationError = null, submitError = null) }
    fun onLongitudeChanged(v: String) = _uiState.update { it.copy(longitudeText = v, validationError = null, submitError = null) }
    fun onAreaChanged(v: String) = _uiState.update { it.copy(areaText = v, validationError = null, submitError = null) }
    fun onElevationChanged(v: String) = _uiState.update { it.copy(elevationText = v, validationError = null, submitError = null) }
    fun onSoilTypeChanged(v: SoilType) = _uiState.update { it.copy(soilType = v, submitError = null) }
    fun onSoilPhChanged(v: String) = _uiState.update { it.copy(soilPhText = v, validationError = null, submitError = null) }
    fun onOrganicMatterChanged(v: String) = _uiState.update { it.copy(organicMatterText = v, validationError = null, submitError = null) }
    fun onSoilTestDateChanged(v: String) = _uiState.update { it.copy(soilTestDateText = v, validationError = null, submitError = null) }
    fun onWaterAvailabilityChanged(v: WaterAvailability) = _uiState.update { it.copy(waterAvailability = v, submitError = null) }
    fun onWaterSourceChanged(v: WaterSource) = _uiState.update { it.copy(waterSource = v, submitError = null) }
    fun onWaterSourceOtherChanged(v: String) = _uiState.update { it.copy(waterSourceOtherText = v, submitError = null) }
    fun onIrrigationSystemChanged(v: IrrigationSystem) = _uiState.update { it.copy(irrigationSystem = v, submitError = null) }

    fun addCropHistoryRow() {
        _uiState.update { state ->
            if (state.cropHistory.size >= MAX_CROP_HISTORY) return@update state
            state.copy(
                cropHistory = state.cropHistory + CropHistoryFormRow(),
                validationError = null
            )
        }
    }

    fun removeCropHistoryRow(rowId: String) {
        _uiState.update { state ->
            if (state.cropHistory.size <= 1) return@update state
            state.copy(
                cropHistory = state.cropHistory.filterNot { it.rowId == rowId },
                validationError = null
            )
        }
    }

    fun updateCropHistoryRow(rowId: String, transform: (CropHistoryFormRow) -> CropHistoryFormRow) {
        _uiState.update { state ->
            state.copy(
                cropHistory = state.cropHistory.map { if (it.rowId == rowId) transform(it) else it },
                validationError = null,
                submitError = null
            )
        }
    }

    fun submit() {
        val current = _uiState.value
        if (current.isSubmitting || current.isLoadingExisting) return

        val trimmedId = current.fieldId.trim()
        if (trimmedId.isEmpty() || trimmedId.length > 64) {
            _uiState.update { it.copy(validationError = FieldFormValidationError.FIELD_ID_INVALID) }
            return
        }

        val trimmedName = current.fieldName.trim()
        if (trimmedName.isEmpty() || trimmedName.length > 120) {
            _uiState.update { it.copy(validationError = FieldFormValidationError.FIELD_NAME_INVALID) }
            return
        }

        val lat = current.latitudeText.trim().toDoubleOrNull()
        if (lat == null || lat < -90.0 || lat > 90.0) {
            _uiState.update { it.copy(validationError = FieldFormValidationError.LATITUDE_INVALID) }
            return
        }

        val lon = current.longitudeText.trim().toDoubleOrNull()
        if (lon == null || lon < -180.0 || lon > 180.0) {
            _uiState.update { it.copy(validationError = FieldFormValidationError.LONGITUDE_INVALID) }
            return
        }

        val area = current.areaText.trim().toDoubleOrNull()
        if (area == null || area <= 0.0 || area > 10_000.0) {
            _uiState.update { it.copy(validationError = FieldFormValidationError.AREA_INVALID) }
            return
        }

        val elevation = current.elevationText.trim().takeIf { it.isNotEmpty() }?.let { raw ->
            val parsed = raw.toDoubleOrNull()
            if (parsed == null || parsed < -500.0 || parsed > 9000.0) {
                _uiState.update { it.copy(validationError = FieldFormValidationError.ELEVATION_INVALID) }
                return
            }
            parsed
        }

        val soilPh = current.soilPhText.trim().takeIf { it.isNotEmpty() }?.let { raw ->
            val parsed = raw.toDoubleOrNull()
            if (parsed == null || parsed < 3.0 || parsed > 11.0) {
                _uiState.update { it.copy(validationError = FieldFormValidationError.SOIL_PH_INVALID) }
                return
            }
            parsed
        }

        val omPercent = current.organicMatterText.trim().takeIf { it.isNotEmpty() }?.let { raw ->
            val parsed = raw.toDoubleOrNull()
            if (parsed == null || parsed < 0.0 || parsed > 100.0) {
                _uiState.update { it.copy(validationError = FieldFormValidationError.ORGANIC_MATTER_INVALID) }
                return
            }
            parsed
        }

        val soilDate = current.soilTestDateText.trim().takeIf { it.isNotEmpty() }?.also { raw ->
            if (!DATE_REGEX.matches(raw)) {
                _uiState.update { it.copy(validationError = FieldFormValidationError.SOIL_TEST_DATE_INVALID) }
                return
            }
        }

        if (current.cropHistory.isEmpty() || current.cropHistory.size > MAX_CROP_HISTORY) {
            _uiState.update { it.copy(validationError = FieldFormValidationError.CROP_HISTORY_COUNT_INVALID) }
            return
        }

        val parsedHistory = mutableListOf<CropHistoryEntry>()
        for (row in current.cropHistory) {
            val year = row.yearText.trim().toIntOrNull()
            if (year == null || year < 1980 || year > 2100) {
                _uiState.update { it.copy(validationError = FieldFormValidationError.CROP_HISTORY_YEAR_INVALID) }
                return
            }
            val cropName = row.cropNameRaw.trim().takeIf { it.isNotEmpty() }
            val cropId = row.cropId.trim().takeIf { it.isNotEmpty() }
            if (cropName == null && cropId == null) {
                _uiState.update { it.copy(validationError = FieldFormValidationError.CROP_HISTORY_CROP_INVALID) }
                return
            }
            val yieldVal = row.yieldText.trim().toDoubleOrNull()?.takeIf { it >= 0.0 }
            parsedHistory.add(
                CropHistoryEntry(
                    season = row.season,
                    year = year,
                    cropId = cropId,
                    cropNameRaw = cropName,
                    yieldTonsPerHectare = yieldVal,
                    notes = row.notes.trim().takeIf { it.isNotEmpty() }
                )
            )
        }

        val input = FieldWriteInput(
            fieldId = trimmedId,
            fieldName = trimmedName,
            isUnverifiedDemoParcel = current.isUnverifiedDemoParcel,
            location = FieldLocation(latitude = lat, longitude = lon),
            areaHectares = area,
            elevationM = elevation,
            soilType = current.soilType,
            soilPh = soilPh,
            organicMatterPercent = omPercent,
            soilTestDate = soilDate,
            waterAvailability = current.waterAvailability,
            waterSource = current.waterSource,
            waterSourceOther = current.waterSourceOtherText.trim().takeIf { it.isNotEmpty() },
            irrigationSystem = current.irrigationSystem,
            cropHistory = parsedHistory
        )

        viewModelScope.launch {
            _uiState.update { it.copy(isSubmitting = true, submitError = null) }
            val result: FieldResult<FieldSummary> = if (current.isEditMode) {
                when (val r = fieldRepository.updateField(current.farmId, current.fieldId, input)) {
                    is FieldResult.Success -> FieldResult.Success(r.data.toSummary())
                    is FieldResult.Failure -> FieldResult.Failure(r.error)
                }
            } else {
                fieldRepository.createField(current.farmId, input)
            }

            when (result) {
                is FieldResult.Success -> {
                    _uiState.update {
                        it.copy(
                            isSubmitting = false,
                            savedField = result.data
                        )
                    }
                }
                is FieldResult.Failure -> {
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

    private companion object {
        const val MAX_CROP_HISTORY = 30
        val DATE_REGEX = Regex("""^\d{4}-\d{2}-\d{2}$""")
    }
}

