package com.example.myapplication.feature.fields

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.myapplication.R
import com.example.myapplication.core.common.UiState
import com.example.myapplication.core.designsystem.component.AgronomicStatusTone
import com.example.myapplication.core.designsystem.component.FieldShiftCard
import com.example.myapplication.core.designsystem.component.FieldShiftOutlinedButton
import com.example.myapplication.core.designsystem.component.FieldShiftPrimaryButton
import com.example.myapplication.core.designsystem.component.FieldShiftStatusChip
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme
import com.example.myapplication.domain.field.FieldDetail

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FieldDetailScreen(
    farmId: String,
    fieldId: String,
    viewModel: FieldDetailViewModel,
    onBackClick: () -> Unit,
    onEditClick: () -> Unit,
    onDeleted: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val colors = FieldShiftTheme.colors

    LaunchedEffect(farmId, fieldId) {
        viewModel.loadField(farmId = farmId, fieldId = fieldId)
    }

    LaunchedEffect(uiState.deletedSuccessfully) {
        if (uiState.deletedSuccessfully) {
            onDeleted(fieldId)
        }
    }

    if (uiState.showDeleteConfirmation) {
        val displayName = (uiState.fieldState as? UiState.Success)?.data?.fieldName ?: fieldId
        AlertDialog(
            onDismissRequest = viewModel::dismissDelete,
            title = { Text(stringResource(R.string.field_delete_confirm_title)) },
            text = { Text(stringResource(R.string.field_delete_confirm_body, displayName)) },
            confirmButton = {
                TextButton(
                    onClick = { viewModel.confirmDelete(farmId, fieldId) },
                    enabled = !uiState.isDeleting
                ) {
                    Text(
                        text = stringResource(R.string.field_delete_confirm_action),
                        color = colors.erosionAlert
                    )
                }
            },
            dismissButton = {
                TextButton(
                    onClick = viewModel::dismissDelete,
                    enabled = !uiState.isDeleting
                ) {
                    Text(stringResource(R.string.profile_cancel))
                }
            }
        )
    }

    Scaffold(
        modifier = modifier,
        containerColor = colors.surfaceCanvas,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = stringResource(R.string.field_detail_title),
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
            when (val state = uiState.fieldState) {
                is UiState.Loading -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator(color = colors.primaryAmberOchre)
                    }
                }

                is UiState.Empty,
                is UiState.Error -> {
                    val errorMsg = uiState.fieldError?.let { formatFieldErrorMessage(it) }
                        ?: (state as? UiState.Error)?.message
                        ?: stringResource(R.string.fields_error_not_found)
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                            Text(
                                text = errorMsg,
                                style = FieldShiftTheme.typography.bodyMd,
                                color = colors.erosionAlert
                            )
                            Spacer(modifier = Modifier.height(12.dp))
                            FieldShiftOutlinedButton(
                                text = stringResource(R.string.farms_error_retry),
                                onClick = {
                                    viewModel.loadField(
                                        farmId = farmId,
                                        fieldId = fieldId,
                                        forceRefresh = true
                                    )
                                },
                                modifier = Modifier.fillMaxWidth()
                            )
                        }
                    }
                }

                is UiState.Success -> {
                    FieldDetailContent(
                        detail = state.data,
                        deleteError = uiState.deleteError?.let { formatFieldErrorMessage(it) },
                        isDeleting = uiState.isDeleting,
                        onEditClick = onEditClick,
                        onDeleteClick = viewModel::requestDelete
                    )
                }
            }
        }
    }
}

@Composable
private fun FieldDetailContent(
    detail: FieldDetail,
    deleteError: String?,
    isDeleting: Boolean,
    onEditClick: () -> Unit,
    onDeleteClick: () -> Unit
) {
    val colors = FieldShiftTheme.colors
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        if (detail.warnings.isNotEmpty()) {
            FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = stringResource(R.string.fields_warning_banner_title),
                    style = FieldShiftTheme.typography.labelLg.copy(fontWeight = FontWeight.SemiBold),
                    color = colors.primaryAmberOchre
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = detail.warnings.joinToString("\n") { "${it.code}: ${it.message}" },
                    style = FieldShiftTheme.typography.bodySm,
                    color = colors.textPrimary
                )
            }
        }

        if (deleteError != null) {
            FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = deleteError,
                    style = FieldShiftTheme.typography.bodyMd,
                    color = colors.erosionAlert
                )
            }
        }

        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = detail.fieldName,
                        style = FieldShiftTheme.typography.headlineMd,
                        color = colors.textPrimary
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = detail.fieldId,
                        style = FieldShiftTheme.typography.labelMd,
                        color = colors.textSecondary
                    )
                }
                FieldShiftStatusChip(
                    text = stringResource(R.string.fields_area_ha, detail.areaHectares),
                    tone = AgronomicStatusTone.NominalFoliage
                )
            }

            Spacer(modifier = Modifier.height(12.dp))

            DetailRow(
                label = stringResource(R.string.field_detail_gps_label),
                value = stringResource(
                    R.string.fields_coords_fmt,
                    detail.location.latitude,
                    detail.location.longitude
                )
            )

            detail.elevationM?.let { elevation ->
                DetailRow(
                    label = stringResource(R.string.field_detail_elevation_label),
                    value = stringResource(R.string.field_detail_elevation_m, elevation)
                )
            }
        }

        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = stringResource(R.string.field_detail_soil_section),
                style = FieldShiftTheme.typography.headlineSm,
                color = colors.textPrimary
            )
            Spacer(modifier = Modifier.height(8.dp))
            DetailRow(
                label = stringResource(R.string.field_detail_soil_type),
                value = detail.soil.soilType.label()
            )
            DetailRow(
                label = stringResource(R.string.field_detail_soil_source),
                value = detail.soil.source.apiValue
            )
            detail.soil.soilPh?.let { ph ->
                DetailRow(
                    label = stringResource(R.string.field_detail_soil_ph),
                    value = ph.toString()
                )
            }
            detail.soil.organicMatterPercent?.let { om ->
                DetailRow(
                    label = stringResource(R.string.field_detail_soil_om),
                    value = "$om%"
                )
            }
            detail.soil.soilTestDate?.let { date ->
                DetailRow(
                    label = stringResource(R.string.field_detail_soil_test_date),
                    value = date
                )
            }
        }

        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = stringResource(R.string.field_detail_water_section),
                style = FieldShiftTheme.typography.headlineSm,
                color = colors.textPrimary
            )
            Spacer(modifier = Modifier.height(8.dp))
            DetailRow(
                label = stringResource(R.string.field_detail_water_availability),
                value = detail.water.availability.label()
            )
            DetailRow(
                label = stringResource(R.string.field_detail_water_source),
                value = detail.water.sourceOther?.takeIf { it.isNotBlank() }
                    ?: detail.water.source.label()
            )
            DetailRow(
                label = stringResource(R.string.field_detail_irrigation),
                value = detail.water.irrigationSystem.label()
            )
        }

        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = stringResource(
                    R.string.field_detail_crop_history_section,
                    detail.cropHistory.size
                ),
                style = FieldShiftTheme.typography.headlineSm,
                color = colors.textPrimary
            )
            Spacer(modifier = Modifier.height(8.dp))
            detail.cropHistory.forEachIndexed { index, entry ->
                if (index > 0) {
                    HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
                }
                val cropLabel = entry.cropNameRaw?.takeIf { it.isNotBlank() }
                    ?: entry.cropId
                    ?: "-"
                Text(
                    text = "$cropLabel • ${entry.season.label()} ${entry.year}",
                    style = FieldShiftTheme.typography.bodyMd.copy(fontWeight = FontWeight.Medium),
                    color = colors.textPrimary
                )
                entry.yieldTonsPerHectare?.let { y ->
                    Text(
                        text = "$y t/ha",
                        style = FieldShiftTheme.typography.bodySm,
                        color = colors.textSecondary
                    )
                }
                entry.notes?.takeIf { it.isNotBlank() }?.let { notes ->
                    Text(
                        text = notes,
                        style = FieldShiftTheme.typography.bodySm,
                        color = colors.textSecondary
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(4.dp))

        FieldShiftPrimaryButton(
            text = stringResource(R.string.field_detail_edit),
            onClick = onEditClick,
            enabled = !isDeleting,
            modifier = Modifier.fillMaxWidth()
        )

        FieldShiftOutlinedButton(
            text = stringResource(R.string.field_detail_delete),
            onClick = onDeleteClick,
            enabled = !isDeleting,
            modifier = Modifier.fillMaxWidth()
        )
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    val colors = FieldShiftTheme.colors
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = label,
            style = FieldShiftTheme.typography.bodySm,
            color = colors.textSecondary
        )
        Text(
            text = value,
            style = FieldShiftTheme.typography.bodyMd,
            color = colors.textPrimary
        )
    }
}
