package com.example.myapplication.feature.fields

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.myapplication.R
import com.example.myapplication.core.designsystem.component.FieldShiftCard
import com.example.myapplication.core.designsystem.component.FieldShiftOutlinedButton
import com.example.myapplication.core.designsystem.component.FieldShiftPrimaryButton
import com.example.myapplication.core.designsystem.component.FieldShiftTextField
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme
import com.example.myapplication.domain.field.FieldSummary
import com.example.myapplication.domain.field.IrrigationSystem
import com.example.myapplication.domain.field.Season
import com.example.myapplication.domain.field.SoilType
import com.example.myapplication.domain.field.WaterAvailability
import com.example.myapplication.domain.field.WaterSource

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun FieldFormScreen(
    farmId: String,
    fieldId: String?,
    viewModel: FieldFormViewModel,
    onBackClick: () -> Unit,
    onSaved: (FieldSummary) -> Unit,
    modifier: Modifier = Modifier
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val colors = FieldShiftTheme.colors

    LaunchedEffect(farmId, fieldId) {
        viewModel.initialize(farmId = farmId, fieldId = fieldId)
    }

    LaunchedEffect(uiState.savedField) {
        val saved = uiState.savedField
        if (saved != null) {
            onSaved(saved)
        }
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val granted = permissions[Manifest.permission.ACCESS_FINE_LOCATION] == true ||
            permissions[Manifest.permission.ACCESS_COARSE_LOCATION] == true
        if (granted) {
            viewModel.captureDeviceGps()
        } else {
            viewModel.onLocationPermissionDenied()
        }
    }

    val titleRes = if (fieldId == null) {
        R.string.field_form_create_title
    } else {
        R.string.field_form_edit_title
    }

    Scaffold(
        modifier = modifier,
        containerColor = colors.surfaceCanvas,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = stringResource(titleRes),
                        style = FieldShiftTheme.typography.headlineSm,
                        color = colors.textPrimary
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBackClick) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.field_detail_back),
                            tint = colors.textPrimary
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = colors.surfaceCanvas
                )
            )
        }
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 16.dp)
        ) {
            when {
                uiState.isLoadingExisting -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator(color = colors.primaryAmberOchre)
                    }
                }

                uiState.loadError != null -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                            Text(
                                text = formatFieldErrorMessage(uiState.loadError!!),
                                style = FieldShiftTheme.typography.bodyMd,
                                color = colors.erosionAlert
                            )
                            Spacer(modifier = Modifier.height(12.dp))
                            FieldShiftOutlinedButton(
                                text = stringResource(R.string.farms_error_retry),
                                onClick = viewModel::retryLoadExisting,
                                modifier = Modifier.fillMaxWidth()
                            )
                        }
                    }
                }

                else -> {
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .verticalScroll(rememberScrollState())
                            .padding(vertical = 12.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        uiState.submitError?.let { error ->
                            FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                                Text(
                                    text = formatFieldErrorMessage(error),
                                    style = FieldShiftTheme.typography.bodyMd,
                                    color = colors.erosionAlert
                                )
                            }
                        }

                        uiState.validationError?.let { validationError ->
                            FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                                Text(
                                    text = validationErrorMessage(validationError),
                                    style = FieldShiftTheme.typography.bodyMd,
                                    color = colors.erosionAlert
                                )
                            }
                        }

                        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                            FieldShiftTextField(
                                value = uiState.fieldId,
                                onValueChange = viewModel::onFieldIdChanged,
                                label = stringResource(R.string.field_form_id_label),
                                enabled = !uiState.isEditMode && !uiState.isSubmitting,
                                singleLine = true,
                                modifier = Modifier.fillMaxWidth()
                            )

                            Spacer(modifier = Modifier.height(10.dp))

                            FieldShiftTextField(
                                value = uiState.fieldName,
                                onValueChange = viewModel::onFieldNameChanged,
                                label = stringResource(R.string.field_form_name_label),
                                placeholder = stringResource(R.string.field_form_name_placeholder),
                                enabled = !uiState.isSubmitting,
                                singleLine = true,
                                modifier = Modifier.fillMaxWidth()
                            )

                            Spacer(modifier = Modifier.height(10.dp))

                            FieldShiftTextField(
                                value = uiState.areaText,
                                onValueChange = viewModel::onAreaChanged,
                                label = stringResource(R.string.field_form_area_label),
                                enabled = !uiState.isSubmitting,
                                singleLine = true,
                                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                                modifier = Modifier.fillMaxWidth()
                            )
                        }

                        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                            Text(
                                text = stringResource(R.string.field_form_gps_section),
                                style = FieldShiftTheme.typography.headlineSm,
                                color = colors.textPrimary
                            )
                            Spacer(modifier = Modifier.height(8.dp))

                            FieldShiftOutlinedButton(
                                text = if (uiState.gpsStatus == GpsCaptureStatus.ACQUIRING) {
                                    stringResource(R.string.field_form_capturing_gps)
                                } else {
                                    stringResource(R.string.field_form_capture_gps)
                                },
                                onClick = {
                                    if (viewModel.hasLocationPermission()) {
                                        viewModel.captureDeviceGps()
                                    } else {
                                        permissionLauncher.launch(
                                            arrayOf(
                                                Manifest.permission.ACCESS_FINE_LOCATION,
                                                Manifest.permission.ACCESS_COARSE_LOCATION
                                            )
                                        )
                                    }
                                },
                                enabled = uiState.gpsStatus != GpsCaptureStatus.ACQUIRING && !uiState.isSubmitting,
                                leadingIcon = Icons.Default.LocationOn,
                                modifier = Modifier.fillMaxWidth()
                            )

                            val gpsStatusText: String? = when (uiState.gpsStatus) {
                                GpsCaptureStatus.IDLE -> null
                                GpsCaptureStatus.ACQUIRING -> stringResource(R.string.field_form_capturing_gps)
                                GpsCaptureStatus.CAPTURED -> {
                                    val acc = uiState.gpsAccuracyMeters ?: 0f
                                    stringResource(R.string.field_form_gps_accuracy, acc)
                                }
                                GpsCaptureStatus.PERMISSION_DENIED -> stringResource(R.string.field_form_gps_permission_denied)
                                GpsCaptureStatus.UNAVAILABLE -> stringResource(R.string.field_form_gps_unavailable)
                                GpsCaptureStatus.TIMEOUT -> stringResource(R.string.field_form_gps_timeout)
                                GpsCaptureStatus.ERROR -> uiState.gpsErrorMessage
                                    ?: stringResource(R.string.field_form_gps_unavailable)
                            }
                            if (gpsStatusText != null) {
                                Spacer(modifier = Modifier.height(6.dp))
                                Text(
                                    text = gpsStatusText,
                                    style = FieldShiftTheme.typography.bodySm,
                                    color = when (uiState.gpsStatus) {
                                        GpsCaptureStatus.CAPTURED -> colors.foliageGreenBright
                                        GpsCaptureStatus.PERMISSION_DENIED,
                                        GpsCaptureStatus.UNAVAILABLE,
                                        GpsCaptureStatus.TIMEOUT,
                                        GpsCaptureStatus.ERROR -> colors.erosionAlert
                                        else -> colors.textSecondary
                                    }
                                )
                            }

                            Spacer(modifier = Modifier.height(10.dp))

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                FieldShiftTextField(
                                    value = uiState.latitudeText,
                                    onValueChange = viewModel::onLatitudeChanged,
                                    label = stringResource(R.string.field_form_lat_label),
                                    enabled = !uiState.isSubmitting,
                                    singleLine = true,
                                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                                    modifier = Modifier.weight(1f)
                                )
                                FieldShiftTextField(
                                    value = uiState.longitudeText,
                                    onValueChange = viewModel::onLongitudeChanged,
                                    label = stringResource(R.string.field_form_lon_label),
                                    enabled = !uiState.isSubmitting,
                                    singleLine = true,
                                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                                    modifier = Modifier.weight(1f)
                                )
                            }

                            Spacer(modifier = Modifier.height(10.dp))

                            FieldShiftTextField(
                                value = uiState.elevationText,
                                onValueChange = viewModel::onElevationChanged,
                                label = stringResource(R.string.field_form_elevation_label),
                                enabled = !uiState.isSubmitting,
                                singleLine = true,
                                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                                modifier = Modifier.fillMaxWidth()
                            )
                        }

                        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                            Text(
                                text = stringResource(R.string.field_detail_soil_section),
                                style = FieldShiftTheme.typography.headlineSm,
                                color = colors.textPrimary
                            )
                            Spacer(modifier = Modifier.height(8.dp))

                            FlowRow(
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                verticalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                SoilType.entries.forEach { soil ->
                                    FilterChip(
                                        selected = uiState.soilType == soil,
                                        onClick = { viewModel.onSoilTypeChanged(soil) },
                                        enabled = !uiState.isSubmitting,
                                        label = { Text(soil.label()) }
                                    )
                                }
                            }

                            Spacer(modifier = Modifier.height(10.dp))

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                FieldShiftTextField(
                                    value = uiState.soilPhText,
                                    onValueChange = viewModel::onSoilPhChanged,
                                    label = stringResource(R.string.field_form_soil_ph_label),
                                    enabled = !uiState.isSubmitting,
                                    singleLine = true,
                                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                                    modifier = Modifier.weight(1f)
                                )
                                FieldShiftTextField(
                                    value = uiState.organicMatterText,
                                    onValueChange = viewModel::onOrganicMatterChanged,
                                    label = stringResource(R.string.field_form_soil_om_label),
                                    enabled = !uiState.isSubmitting,
                                    singleLine = true,
                                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                                    modifier = Modifier.weight(1f)
                                )
                            }

                            Spacer(modifier = Modifier.height(10.dp))

                            FieldShiftTextField(
                                value = uiState.soilTestDateText,
                                onValueChange = viewModel::onSoilTestDateChanged,
                                label = stringResource(R.string.field_form_soil_date_label),
                                enabled = !uiState.isSubmitting,
                                singleLine = true,
                                modifier = Modifier.fillMaxWidth()
                            )
                        }

                        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                            Text(
                                text = stringResource(R.string.field_detail_water_section),
                                style = FieldShiftTheme.typography.headlineSm,
                                color = colors.textPrimary
                            )
                            Spacer(modifier = Modifier.height(8.dp))

                            Text(
                                text = stringResource(R.string.field_detail_water_availability),
                                style = FieldShiftTheme.typography.labelMd,
                                color = colors.textSecondary
                            )
                            FlowRow(
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                verticalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                WaterAvailability.entries.forEach { avail ->
                                    FilterChip(
                                        selected = uiState.waterAvailability == avail,
                                        onClick = { viewModel.onWaterAvailabilityChanged(avail) },
                                        enabled = !uiState.isSubmitting,
                                        label = { Text(avail.label()) }
                                    )
                                }
                            }

                            Spacer(modifier = Modifier.height(8.dp))

                            Text(
                                text = stringResource(R.string.field_detail_water_source),
                                style = FieldShiftTheme.typography.labelMd,
                                color = colors.textSecondary
                            )
                            FlowRow(
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                verticalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                WaterSource.entries.forEach { source ->
                                    FilterChip(
                                        selected = uiState.waterSource == source,
                                        onClick = { viewModel.onWaterSourceChanged(source) },
                                        enabled = !uiState.isSubmitting,
                                        label = { Text(source.label()) }
                                    )
                                }
                            }

                            if (uiState.waterSource == WaterSource.OTHER) {
                                Spacer(modifier = Modifier.height(8.dp))
                                FieldShiftTextField(
                                    value = uiState.waterSourceOtherText,
                                    onValueChange = viewModel::onWaterSourceOtherChanged,
                                    label = stringResource(R.string.field_form_water_other_label),
                                    enabled = !uiState.isSubmitting,
                                    singleLine = true,
                                    modifier = Modifier.fillMaxWidth()
                                )
                            }

                            Spacer(modifier = Modifier.height(8.dp))

                            Text(
                                text = stringResource(R.string.field_detail_irrigation),
                                style = FieldShiftTheme.typography.labelMd,
                                color = colors.textSecondary
                            )
                            FlowRow(
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                verticalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                IrrigationSystem.entries.forEach { sys ->
                                    FilterChip(
                                        selected = uiState.irrigationSystem == sys,
                                        onClick = { viewModel.onIrrigationSystemChanged(sys) },
                                        enabled = !uiState.isSubmitting,
                                        label = { Text(sys.label()) }
                                    )
                                }
                            }
                        }

                        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = stringResource(
                                        R.string.field_detail_crop_history_section,
                                        uiState.cropHistory.size
                                    ),
                                    style = FieldShiftTheme.typography.headlineSm,
                                    color = colors.textPrimary
                                )
                                FieldShiftOutlinedButton(
                                    text = stringResource(R.string.field_form_history_add),
                                    onClick = viewModel::addCropHistoryRow,
                                    enabled = uiState.cropHistory.size < 30 && !uiState.isSubmitting,
                                    leadingIcon = Icons.Default.Add
                                )
                            }

                            Spacer(modifier = Modifier.height(8.dp))

                            uiState.cropHistory.forEachIndexed { index, row ->
                                if (index > 0) {
                                    HorizontalDivider(modifier = Modifier.padding(vertical = 10.dp))
                                }

                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = "#${index + 1}",
                                        style = FieldShiftTheme.typography.labelLg.copy(fontWeight = FontWeight.SemiBold),
                                        color = colors.textPrimary
                                    )
                                    if (uiState.cropHistory.size > 1) {
                                        IconButton(
                                            onClick = { viewModel.removeCropHistoryRow(row.rowId) },
                                            enabled = !uiState.isSubmitting
                                        ) {
                                            Icon(
                                                imageVector = Icons.Default.Delete,
                                                contentDescription = stringResource(R.string.field_form_history_remove),
                                                tint = colors.erosionAlert
                                            )
                                        }
                                    }
                                }

                                FlowRow(
                                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                                    verticalArrangement = Arrangement.spacedBy(6.dp)
                                ) {
                                    Season.entries.forEach { season ->
                                        FilterChip(
                                            selected = row.season == season,
                                            onClick = {
                                                viewModel.updateCropHistoryRow(row.rowId) {
                                                    it.copy(season = season)
                                                }
                                            },
                                            enabled = !uiState.isSubmitting,
                                            label = { Text(season.label()) }
                                        )
                                    }
                                }

                                Spacer(modifier = Modifier.height(8.dp))

                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    FieldShiftTextField(
                                        value = row.yearText,
                                        onValueChange = { value ->
                                            viewModel.updateCropHistoryRow(row.rowId) {
                                                it.copy(yearText = value)
                                            }
                                        },
                                        label = stringResource(R.string.field_form_history_year_label),
                                        enabled = !uiState.isSubmitting,
                                        singleLine = true,
                                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                                        modifier = Modifier.weight(1f)
                                    )
                                    FieldShiftTextField(
                                        value = row.yieldText,
                                        onValueChange = { value ->
                                            viewModel.updateCropHistoryRow(row.rowId) {
                                                it.copy(yieldText = value)
                                            }
                                        },
                                        label = stringResource(R.string.field_form_history_yield_label),
                                        enabled = !uiState.isSubmitting,
                                        singleLine = true,
                                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                                        modifier = Modifier.weight(1f)
                                    )
                                }

                                Spacer(modifier = Modifier.height(8.dp))

                                FieldShiftTextField(
                                    value = row.cropNameRaw,
                                    onValueChange = { value ->
                                        viewModel.updateCropHistoryRow(row.rowId) {
                                            it.copy(cropNameRaw = value)
                                        }
                                    },
                                    label = stringResource(R.string.field_form_history_crop_name_label),
                                    enabled = !uiState.isSubmitting,
                                    singleLine = true,
                                    modifier = Modifier.fillMaxWidth()
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(4.dp))

                        FieldShiftPrimaryButton(
                            text = if (uiState.isEditMode) {
                                stringResource(R.string.field_form_submit_save)
                            } else {
                                stringResource(R.string.field_form_submit_create)
                            },
                            onClick = viewModel::submit,
                            enabled = !uiState.isSubmitting,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun validationErrorMessage(error: FieldFormValidationError): String {
    return when (error) {
        FieldFormValidationError.FIELD_ID_INVALID -> stringResource(R.string.field_val_id_required)
        FieldFormValidationError.FIELD_NAME_INVALID -> stringResource(R.string.field_val_name_required)
        FieldFormValidationError.LATITUDE_INVALID -> stringResource(R.string.field_val_lat_invalid)
        FieldFormValidationError.LONGITUDE_INVALID -> stringResource(R.string.field_val_lon_invalid)
        FieldFormValidationError.AREA_INVALID -> stringResource(R.string.field_val_area_invalid)
        FieldFormValidationError.ELEVATION_INVALID -> stringResource(R.string.field_val_elevation_invalid)
        FieldFormValidationError.SOIL_PH_INVALID -> stringResource(R.string.field_val_ph_invalid)
        FieldFormValidationError.ORGANIC_MATTER_INVALID -> stringResource(R.string.field_val_om_invalid)
        FieldFormValidationError.SOIL_TEST_DATE_INVALID -> stringResource(R.string.field_val_date_invalid)
        FieldFormValidationError.CROP_HISTORY_COUNT_INVALID -> stringResource(R.string.field_val_history_count)
        FieldFormValidationError.CROP_HISTORY_YEAR_INVALID -> stringResource(R.string.field_val_history_year)
        FieldFormValidationError.CROP_HISTORY_CROP_INVALID -> stringResource(R.string.field_val_history_crop)
    }
}
