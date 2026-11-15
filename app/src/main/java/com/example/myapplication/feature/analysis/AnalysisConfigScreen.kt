package com.example.myapplication.feature.analysis

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
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
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
import com.example.myapplication.core.common.AppLanguage
import com.example.myapplication.core.designsystem.component.FieldShiftCard
import com.example.myapplication.core.designsystem.component.FieldShiftOutlinedButton
import com.example.myapplication.core.designsystem.component.FieldShiftPrimaryButton
import com.example.myapplication.core.designsystem.component.FieldShiftTextField
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme
import com.example.myapplication.domain.analysis.CycleMode
import com.example.myapplication.domain.analysis.MarketPreference
import com.example.myapplication.domain.field.Season
import com.example.myapplication.feature.fields.label

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun AnalysisConfigScreen(
    language: AppLanguage,
    viewModel: AnalysisConfigViewModel,
    onJobQueued: (String) -> Unit,
    onResumeActiveRequest: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val colors = FieldShiftTheme.colors

    LaunchedEffect(language) {
        viewModel.initialize(language)
    }

    LaunchedEffect(uiState.queuedJob) {
        val job = uiState.queuedJob
        if (job != null) {
            viewModel.consumeQueuedJob()
            onJobQueued(job.requestId)
        }
    }

    if (uiState.isLoadingInitial) {
        Box(
            modifier = modifier.fillMaxSize(),
            contentAlignment = Alignment.Center
        ) {
            CircularProgressIndicator(color = colors.primaryAmberOchre)
        }
        return
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        uiState.activeRequestToResume?.let { active ->
            FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = stringResource(R.string.analysis_active_resume_banner),
                    style = FieldShiftTheme.typography.bodyMd,
                    color = colors.primaryAmberOchre
                )
                Spacer(modifier = Modifier.height(8.dp))
                FieldShiftOutlinedButton(
                    text = stringResource(R.string.analysis_active_resume_action),
                    onClick = { onResumeActiveRequest(active.requestId) },
                    modifier = Modifier.fillMaxWidth()
                )
            }
        }

        uiState.submitError?.let { error ->
            FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = formatAnalysisErrorMessage(error),
                    style = FieldShiftTheme.typography.bodyMd,
                    color = colors.erosionAlert
                )
            }
        }

        uiState.validationError?.let { valError ->
            FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = analysisValidationMessage(valError),
                    style = FieldShiftTheme.typography.bodyMd,
                    color = colors.erosionAlert
                )
            }
        }

        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = stringResource(R.string.analysis_section_farm_fields),
                style = FieldShiftTheme.typography.headlineSm,
                color = colors.textPrimary
            )
            Spacer(modifier = Modifier.height(8.dp))

            if (uiState.farms.isEmpty()) {
                Text(
                    text = stringResource(R.string.analysis_no_farms),
                    style = FieldShiftTheme.typography.bodySm,
                    color = colors.textSecondary
                )
            } else {
                Text(
                    text = stringResource(R.string.analysis_select_farm),
                    style = FieldShiftTheme.typography.labelMd,
                    color = colors.textSecondary
                )
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    uiState.farms.forEach { farm ->
                        FilterChip(
                            selected = uiState.selectedFarmId == farm.id,
                            onClick = { viewModel.selectFarm(farm.id) },
                            enabled = !uiState.isSubmitting,
                            label = { Text(farm.name) }
                        )
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                Text(
                    text = stringResource(R.string.analysis_select_fields),
                    style = FieldShiftTheme.typography.labelMd,
                    color = colors.textSecondary
                )
                if (uiState.isLoadingFields) {
                    CircularProgressIndicator(color = colors.primaryAmberOchre)
                } else if (uiState.fields.isEmpty()) {
                    Text(
                        text = stringResource(R.string.analysis_no_fields),
                        style = FieldShiftTheme.typography.bodySm,
                        color = colors.textSecondary
                    )
                } else {
                    FlowRow(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        uiState.fields.forEach { field ->
                            FilterChip(
                                selected = field.fieldId in uiState.selectedFieldIds,
                                onClick = { viewModel.toggleFieldSelection(field.fieldId) },
                                enabled = !uiState.isSubmitting,
                                label = { Text(field.fieldName) }
                            )
                        }
                    }
                }
            }
        }

        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = stringResource(R.string.analysis_section_planning),
                style = FieldShiftTheme.typography.headlineSm,
                color = colors.textPrimary
            )
            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = stringResource(R.string.analysis_start_season),
                style = FieldShiftTheme.typography.labelMd,
                color = colors.textSecondary
            )
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Season.entries.forEach { season ->
                    FilterChip(
                        selected = uiState.startSeason == season,
                        onClick = { viewModel.onStartSeasonChanged(season) },
                        enabled = !uiState.isSubmitting,
                        label = { Text(season.label()) }
                    )
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            FieldShiftTextField(
                value = uiState.startYearText,
                onValueChange = viewModel::onStartYearChanged,
                label = stringResource(R.string.analysis_start_year),
                enabled = !uiState.isSubmitting,
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth()
            )

            Spacer(modifier = Modifier.height(10.dp))

            Text(
                text = stringResource(R.string.analysis_horizon_label, uiState.horizonSeasons),
                style = FieldShiftTheme.typography.labelMd.copy(fontWeight = FontWeight.SemiBold),
                color = colors.primaryAmberOchre
            )
            Slider(
                value = uiState.horizonSeasons.toFloat(),
                onValueChange = { viewModel.onHorizonChanged(it.toInt()) },
                valueRange = 1f..6f,
                steps = 4,
                enabled = !uiState.isSubmitting
            )

            Spacer(modifier = Modifier.height(6.dp))

            Text(
                text = stringResource(R.string.analysis_cycle_mode),
                style = FieldShiftTheme.typography.labelMd,
                color = colors.textSecondary
            )
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                CycleMode.entries.forEach { mode ->
                    FilterChip(
                        selected = uiState.cycleMode == mode,
                        onClick = { viewModel.onCycleModeChanged(mode) },
                        enabled = !uiState.isSubmitting,
                        label = { Text(mode.label()) }
                    )
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = stringResource(R.string.analysis_drought_sim),
                    style = FieldShiftTheme.typography.bodyMd,
                    color = colors.textPrimary,
                    modifier = Modifier.weight(1f)
                )
                Switch(
                    checked = uiState.droughtSimulationEnabled,
                    onCheckedChange = viewModel::onDroughtSimulationToggled,
                    enabled = !uiState.isSubmitting
                )
            }
        }

        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = stringResource(R.string.analysis_section_priorities),
                style = FieldShiftTheme.typography.headlineSm,
                color = colors.textPrimary
            )
            Spacer(modifier = Modifier.height(8.dp))

            WeightSliderRow(
                label = stringResource(R.string.analysis_weight_water, uiState.weights.waterSaving),
                value = uiState.weights.waterSaving,
                enabled = !uiState.isSubmitting,
                onValueChange = { v -> viewModel.updateWeights { it.copy(waterSaving = v) } }
            )
            WeightSliderRow(
                label = stringResource(R.string.analysis_weight_soil, uiState.weights.soilImprovement),
                value = uiState.weights.soilImprovement,
                enabled = !uiState.isSubmitting,
                onValueChange = { v -> viewModel.updateWeights { it.copy(soilImprovement = v) } }
            )
            WeightSliderRow(
                label = stringResource(R.string.analysis_weight_income, uiState.weights.income),
                value = uiState.weights.income,
                enabled = !uiState.isSubmitting,
                onValueChange = { v -> viewModel.updateWeights { it.copy(income = v) } }
            )
            WeightSliderRow(
                label = stringResource(R.string.analysis_weight_risk, uiState.weights.riskReduction),
                value = uiState.weights.riskReduction,
                enabled = !uiState.isSubmitting,
                onValueChange = { v -> viewModel.updateWeights { it.copy(riskReduction = v) } }
            )
            WeightSliderRow(
                label = stringResource(R.string.analysis_weight_forage, uiState.weights.forageValue),
                value = uiState.weights.forageValue,
                enabled = !uiState.isSubmitting,
                onValueChange = { v -> viewModel.updateWeights { it.copy(forageValue = v) } }
            )
        }

        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = stringResource(R.string.analysis_section_market),
                style = FieldShiftTheme.typography.headlineSm,
                color = colors.textPrimary
            )
            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = stringResource(R.string.analysis_market_preference),
                style = FieldShiftTheme.typography.labelMd,
                color = colors.textSecondary
            )
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                MarketPreference.entries.forEach { pref ->
                    FilterChip(
                        selected = uiState.marketPreference == pref,
                        onClick = { viewModel.onMarketPreferenceChanged(pref) },
                        enabled = !uiState.isSubmitting,
                        label = { Text(pref.label()) }
                    )
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            if (uiState.isLoadingCatalog) {
                Text(
                    text = stringResource(R.string.analysis_catalog_loading),
                    style = FieldShiftTheme.typography.bodySm,
                    color = colors.textSecondary
                )
            } else if (uiState.catalogItems.isNotEmpty()) {
                Text(
                    text = stringResource(R.string.analysis_target_crops),
                    style = FieldShiftTheme.typography.labelMd,
                    color = colors.textSecondary
                )
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    uiState.catalogItems.forEach { crop ->
                        FilterChip(
                            selected = crop.cropId in uiState.targetCropIds,
                            onClick = { viewModel.toggleTargetCrop(crop.cropId) },
                            enabled = !uiState.isSubmitting,
                            label = { Text(crop.localizedName(language)) }
                        )
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))

                Text(
                    text = stringResource(R.string.analysis_excluded_crops),
                    style = FieldShiftTheme.typography.labelMd,
                    color = colors.textSecondary
                )
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    uiState.catalogItems.forEach { crop ->
                        FilterChip(
                            selected = crop.cropId in uiState.excludedCropIds,
                            onClick = { viewModel.toggleExcludedCrop(crop.cropId) },
                            enabled = !uiState.isSubmitting,
                            label = { Text(crop.localizedName(language)) }
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            FieldShiftTextField(
                value = uiState.equipmentConstraintsText,
                onValueChange = viewModel::onEquipmentConstraintsChanged,
                label = stringResource(R.string.analysis_equipment_label),
                enabled = !uiState.isSubmitting,
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
        }

        FieldShiftPrimaryButton(
            text = if (uiState.isSubmitting) {
                stringResource(R.string.analysis_submitting)
            } else {
                stringResource(R.string.analysis_submit_action)
            },
            onClick = viewModel::submit,
            enabled = !uiState.isSubmitting && uiState.farms.isNotEmpty(),
            modifier = Modifier.fillMaxWidth()
        )

        Text(
            text = stringResource(R.string.analysis_async_note),
            style = FieldShiftTheme.typography.bodySm,
            color = colors.textSecondary
        )
    }
}

@Composable
private fun WeightSliderRow(
    label: String,
    value: Int,
    enabled: Boolean,
    onValueChange: (Int) -> Unit
) {
    val colors = FieldShiftTheme.colors
    Column(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = label,
            style = FieldShiftTheme.typography.labelMd,
            color = colors.textPrimary
        )
        Slider(
            value = value.toFloat(),
            onValueChange = { onValueChange(it.toInt().coerceIn(0, 100)) },
            valueRange = 0f..100f,
            enabled = enabled
        )
    }
}

@Composable
private fun analysisValidationMessage(error: AnalysisValidationError): String = when (error) {
    AnalysisValidationError.FARM_REQUIRED -> stringResource(R.string.analysis_val_farm_required)
    AnalysisValidationError.FIELDS_COUNT_INVALID -> stringResource(R.string.analysis_val_fields_count)
    AnalysisValidationError.START_YEAR_INVALID -> stringResource(R.string.analysis_val_year_invalid)
    AnalysisValidationError.HORIZON_INVALID -> stringResource(R.string.analysis_val_horizon_invalid)
    AnalysisValidationError.WEIGHTS_INVALID -> stringResource(R.string.analysis_val_weights_invalid)
    AnalysisValidationError.CROP_OVERLAP -> stringResource(R.string.analysis_val_crop_overlap)
}

