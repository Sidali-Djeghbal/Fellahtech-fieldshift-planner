package com.example.myapplication.feature.farms

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material.icons.outlined.Edit
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.myapplication.R
import com.example.myapplication.core.common.UiState
import com.example.myapplication.core.designsystem.component.AgronomicStatusTone
import com.example.myapplication.core.designsystem.component.FieldShiftCard
import com.example.myapplication.core.designsystem.component.FieldShiftOutlinedButton
import com.example.myapplication.core.designsystem.component.FieldShiftPrimaryButton
import com.example.myapplication.core.designsystem.component.FieldShiftStatusChip
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme
import com.example.myapplication.domain.farm.Farm
import com.example.myapplication.domain.farm.FarmError

@Composable
fun FarmDetailScreen(
    farmId: String,
    onEditClick: (String) -> Unit,
    onDeleted: (String) -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: FarmDetailViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val spacing = FieldShiftTheme.spacing
    val colors = FieldShiftTheme.colors

    LaunchedEffect(farmId) {
        viewModel.loadFarm(farmId)
    }

    LaunchedEffect(uiState.deletedSuccessfully) {
        if (uiState.deletedSuccessfully) {
            onDeleted(farmId)
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = spacing.marginMobile, vertical = spacing.spaceMd),
        verticalArrangement = Arrangement.spacedBy(spacing.spaceMd)
    ) {
        FieldShiftOutlinedButton(
            text = stringResource(id = R.string.farm_detail_back),
            onClick = onBack,
            leadingIcon = Icons.AutoMirrored.Outlined.ArrowBack
        )

        when (val farmState = uiState.farmState) {
            is UiState.Loading -> {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = spacing.spaceXl),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(32.dp),
                        color = colors.primaryAmberOchre
                    )
                }
            }

            is UiState.Empty,
            is UiState.Error -> {
                val error = uiState.farmError
                val isNotFound = (error as? FarmError.Api)?.isNotFound == true
                FieldShiftCard(modifier = Modifier.fillMaxWidth(), elevated = true) {
                    Text(
                        text = error?.let { formatFarmErrorMessage(it) }
                            ?: (farmState as? UiState.Error)?.message
                            ?: stringResource(id = R.string.farms_error_not_found),
                        style = FieldShiftTheme.typography.bodyMd,
                        color = colors.erosionAlert
                    )
                    if (!isNotFound) {
                        Spacer(modifier = Modifier.height(spacing.spaceMd))
                        FieldShiftOutlinedButton(
                            text = stringResource(id = R.string.farms_error_retry),
                            onClick = { viewModel.loadFarm(farmId, forceRefresh = true) },
                            modifier = Modifier.fillMaxWidth(),
                            leadingIcon = Icons.Outlined.Refresh
                        )
                    }
                }
            }

            is UiState.Success -> {
                val farm = farmState.data
                FarmDetailCard(farm = farm)

                if (uiState.deleteError != null) {
                    FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                        Text(
                            text = formatFarmErrorMessage(uiState.deleteError!!),
                            style = FieldShiftTheme.typography.bodySm,
                            color = colors.erosionAlert
                        )
                    }
                }

                if (uiState.isDeleting) {
                    Box(
                        modifier = Modifier.fillMaxWidth(),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(28.dp),
                            color = colors.primaryAmberOchre
                        )
                    }
                } else {
                    FieldShiftPrimaryButton(
                        text = stringResource(id = R.string.farm_detail_edit),
                        onClick = { onEditClick(farm.id) },
                        modifier = Modifier.fillMaxWidth(),
                        leadingIcon = Icons.Outlined.Edit
                    )
                    FieldShiftOutlinedButton(
                        text = stringResource(id = R.string.farm_detail_delete),
                        onClick = viewModel::requestDelete,
                        modifier = Modifier.fillMaxWidth(),
                        leadingIcon = Icons.Outlined.Delete
                    )
                }

                if (uiState.showDeleteConfirmation) {
                    AlertDialog(
                        onDismissRequest = viewModel::dismissDelete,
                        title = {
                            Text(
                                text = stringResource(id = R.string.farm_delete_confirm_title),
                                style = FieldShiftTheme.typography.headlineSm
                            )
                        },
                        text = {
                            Text(
                                text = stringResource(id = R.string.farm_delete_confirm_body, farm.name),
                                style = FieldShiftTheme.typography.bodyMd
                            )
                        },
                        confirmButton = {
                            TextButton(onClick = { viewModel.confirmDelete(farm.id) }) {
                                Text(
                                    text = stringResource(id = R.string.farm_delete_confirm_action),
                                    color = colors.erosionAlert
                                )
                            }
                        },
                        dismissButton = {
                            TextButton(onClick = viewModel::dismissDelete) {
                                Text(text = stringResource(id = R.string.profile_cancel))
                            }
                        }
                    )
                }
            }
        }
    }
}

@Composable
private fun FarmDetailCard(farm: Farm) {
    val spacing = FieldShiftTheme.spacing
    val colors = FieldShiftTheme.colors
    FieldShiftCard(modifier = Modifier.fillMaxWidth(), elevated = true) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = farm.name,
                style = FieldShiftTheme.typography.headlineMd,
                color = colors.textPrimary,
                modifier = Modifier.weight(1f)
            )
            FieldShiftStatusChip(
                text = if (farm.fieldCount == 1) {
                    stringResource(id = R.string.farms_field_count_one, farm.fieldCount)
                } else {
                    stringResource(id = R.string.farms_field_count_many, farm.fieldCount)
                },
                tone = AgronomicStatusTone.NominalFoliage
            )
        }

        Spacer(modifier = Modifier.height(spacing.spaceMd))
        DetailRow(
            label = stringResource(id = R.string.farm_detail_id_label),
            value = farm.id
        )
        Spacer(modifier = Modifier.height(spacing.spaceSm))
        DetailRow(
            label = stringResource(id = R.string.farm_detail_location_label),
            value = "${farm.region}, ${farm.country}"
        )
        if (!farm.commune.isNullOrBlank()) {
            Spacer(modifier = Modifier.height(spacing.spaceSm))
            DetailRow(
                label = stringResource(id = R.string.farm_detail_commune_label),
                value = farm.commune
            )
        }
        Spacer(modifier = Modifier.height(spacing.spaceSm))
        DetailRow(
            label = stringResource(id = R.string.farm_detail_created_label),
            value = farm.createdAtIso
        )
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    val colors = FieldShiftTheme.colors
    Column {
        Text(
            text = label,
            style = FieldShiftTheme.typography.bodySm,
            color = colors.textTertiary
        )
        Text(
            text = value,
            style = FieldShiftTheme.typography.bodyMd,
            color = colors.textPrimary
        )
    }
}
