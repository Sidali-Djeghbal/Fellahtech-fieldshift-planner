package com.example.myapplication.feature.fields

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
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
import com.example.myapplication.domain.field.FieldSummary
import com.example.myapplication.domain.field.SoilType

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FieldsListScreen(
    farmId: String,
    viewModel: FieldsListViewModel,
    onBackClick: () -> Unit,
    onFieldClick: (String) -> Unit,
    onCreateFieldClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val colors = FieldShiftTheme.colors

    LaunchedEffect(farmId) {
        viewModel.initialize(farmId)
    }

    Scaffold(
        modifier = modifier,
        containerColor = colors.surfaceCanvas,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = stringResource(R.string.fields_list_title),
                        style = FieldShiftTheme.typography.headlineSm,
                        color = colors.textPrimary
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBackClick) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.farm_detail_back),
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
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 16.dp)
        ) {
            Spacer(modifier = Modifier.height(8.dp))

            FieldShiftPrimaryButton(
                text = stringResource(R.string.fields_create_action),
                onClick = onCreateFieldClick,
                leadingIcon = Icons.Default.Add,
                modifier = Modifier.fillMaxWidth()
            )

            Spacer(modifier = Modifier.height(12.dp))

            SoilFilterRow(
                selectedSoil = uiState.selectedSoilFilter,
                onSelectSoil = viewModel::setSoilFilter
            )

            Spacer(modifier = Modifier.height(8.dp))

            PullToRefreshBox(
                isRefreshing = uiState.isRefreshing,
                onRefresh = viewModel::refresh,
                modifier = Modifier.fillMaxSize()
            ) {
                when (val state = uiState.fieldsState) {
                    is UiState.Loading -> {
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center
                        ) {
                            CircularProgressIndicator(color = colors.primaryAmberOchre)
                        }
                    }

                    is UiState.Error -> {
                        val message = uiState.lastError?.let { formatFieldErrorMessage(it) }
                            ?: state.message
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center
                        ) {
                            FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                                Text(
                                    text = message,
                                    style = FieldShiftTheme.typography.bodyMd,
                                    color = colors.erosionAlert
                                )
                                Spacer(modifier = Modifier.height(12.dp))
                                FieldShiftOutlinedButton(
                                    text = stringResource(R.string.farms_error_retry),
                                    onClick = { viewModel.loadFields(farmId) },
                                    modifier = Modifier.fillMaxWidth()
                                )
                            }
                        }
                    }

                    is UiState.Empty -> {
                        FieldsEmptyState()
                    }

                    is UiState.Success -> {
                        val fields = state.data
                        if (fields.isEmpty()) {
                            FieldsEmptyState()
                        } else {
                            LazyColumn(
                                modifier = Modifier.fillMaxSize(),
                                contentPadding = PaddingValues(vertical = 8.dp),
                                verticalArrangement = Arrangement.spacedBy(12.dp)
                            ) {
                                items(
                                    items = fields,
                                    key = { it.fieldId }
                                ) { field ->
                                    FieldSummaryCard(
                                        field = field,
                                        onClick = { onFieldClick(field.fieldId) }
                                    )
                                }

                                if (uiState.paginationError != null) {
                                    item(key = "pagination_error") {
                                        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                                            Text(
                                                text = formatFieldErrorMessage(uiState.paginationError!!),
                                                style = FieldShiftTheme.typography.bodySm,
                                                color = colors.erosionAlert
                                            )
                                            Spacer(modifier = Modifier.height(8.dp))
                                            FieldShiftOutlinedButton(
                                                text = stringResource(R.string.farms_error_retry),
                                                onClick = viewModel::loadMore,
                                                modifier = Modifier.fillMaxWidth()
                                            )
                                        }
                                    }
                                } else if (uiState.hasMore) {
                                    item(key = "load_more") {
                                        if (uiState.isLoadingMore) {
                                            Box(
                                                modifier = Modifier
                                                    .fillMaxWidth()
                                                    .padding(vertical = 12.dp),
                                                contentAlignment = Alignment.Center
                                            ) {
                                                CircularProgressIndicator(
                                                    modifier = Modifier.size(28.dp),
                                                    color = colors.primaryAmberOchre
                                                )
                                            }
                                        } else {
                                            FieldShiftOutlinedButton(
                                                text = stringResource(R.string.fields_load_more),
                                                onClick = viewModel::loadMore,
                                                modifier = Modifier.fillMaxWidth()
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun FieldsEmptyState() {
    val colors = FieldShiftTheme.colors
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = stringResource(R.string.fields_empty_title),
                style = FieldShiftTheme.typography.headlineSm,
                color = colors.textPrimary
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = stringResource(R.string.fields_empty_body),
                style = FieldShiftTheme.typography.bodyMd,
                color = colors.textSecondary
            )
        }
    }
}

@Composable
private fun SoilFilterRow(
    selectedSoil: SoilType?,
    onSelectSoil: (SoilType?) -> Unit
) {
    LazyRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        item(key = "all") {
            FilterChip(
                selected = selectedSoil == null,
                onClick = { onSelectSoil(null) },
                label = { Text(stringResource(R.string.fields_filter_soil_all)) }
            )
        }
        items(SoilType.entries, key = { it.apiValue }) { soil ->
            FilterChip(
                selected = selectedSoil == soil,
                onClick = { onSelectSoil(soil) },
                label = { Text(soil.label()) }
            )
        }
    }
}

@Composable
private fun FieldSummaryCard(
    field: FieldSummary,
    onClick: () -> Unit
) {
    val colors = FieldShiftTheme.colors
    FieldShiftCard(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = field.fieldName,
                    style = FieldShiftTheme.typography.headlineSm.copy(fontWeight = FontWeight.SemiBold),
                    color = colors.textPrimary
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = field.fieldId,
                    style = FieldShiftTheme.typography.labelMd,
                    color = colors.textSecondary
                )
            }
            FieldShiftStatusChip(
                text = stringResource(R.string.fields_area_ha, field.areaHectares),
                tone = AgronomicStatusTone.NominalFoliage
            )
        }

        Spacer(modifier = Modifier.height(10.dp))

        Text(
            text = stringResource(
                R.string.fields_coords_fmt,
                field.location.latitude,
                field.location.longitude
            ),
            style = FieldShiftTheme.typography.bodySm,
            color = colors.textSecondary
        )

        Spacer(modifier = Modifier.height(6.dp))

        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            FieldShiftStatusChip(
                text = field.soil.soilType.label(),
                tone = AgronomicStatusTone.TelemetryCyan
            )
            FieldShiftStatusChip(
                text = field.water.availability.label(),
                tone = AgronomicStatusTone.HarvestOchre
            )
        }

        if (field.warnings.isNotEmpty()) {
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = field.warnings.joinToString("\n") { "${it.code}: ${it.message}" },
                style = FieldShiftTheme.typography.bodySm,
                color = colors.primaryAmberOchre
            )
        }
    }
}
