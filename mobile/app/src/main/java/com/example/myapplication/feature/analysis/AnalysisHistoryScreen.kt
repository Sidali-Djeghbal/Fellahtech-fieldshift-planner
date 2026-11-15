package com.example.myapplication.feature.analysis

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.myapplication.R
import com.example.myapplication.core.designsystem.component.AgronomicStatusTone
import com.example.myapplication.core.designsystem.component.FieldShiftCard
import com.example.myapplication.core.designsystem.component.FieldShiftFilterChip
import com.example.myapplication.core.designsystem.component.FieldShiftOutlinedButton
import com.example.myapplication.core.designsystem.component.FieldShiftPrimaryButton
import com.example.myapplication.core.designsystem.component.FieldShiftStatusChip
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme
import com.example.myapplication.domain.analysis.AnalysisJobStatus
import com.example.myapplication.domain.analysis.FarmAnalysisSummary
import com.example.myapplication.domain.farm.Farm

@Composable
fun AnalysisHistoryScreen(
    viewModel: AnalysisHistoryViewModel,
    onOpenResult: (String) -> Unit,
    onOpenProgress: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(Unit) {
        viewModel.initialize()
    }

    val colors = FieldShiftTheme.colors
    val typography = FieldShiftTheme.typography

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        HistoryHeaderCard(
            isRefreshing = state.isRefreshing,
            canRefresh = !state.isLoadingFarms && !state.isLoadingHistory && !state.isRefreshing,
            onRefresh = viewModel::refresh
        )

        when {
            state.isLoadingFarms -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        CircularProgressIndicator(color = colors.primaryAmberOchre)
                        Text(
                            text = stringResource(R.string.analysis_history_loading_farms),
                            style = typography.bodyMd,
                            color = colors.textSecondary
                        )
                    }
                }
            }
            state.farmsError != null -> {
                FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text(
                            text = state.farmsError.orEmpty(),
                            style = typography.bodyMd,
                            color = colors.erosionAlert
                        )
                        FieldShiftOutlinedButton(
                            text = stringResource(R.string.analysis_history_retry),
                            onClick = viewModel::retryFarms,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                }
            }
            state.farms.isEmpty() -> {
                FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                    Text(
                        text = stringResource(R.string.analysis_history_no_farms),
                        style = typography.bodyMd,
                        color = colors.textSecondary
                    )
                }
            }
            else -> {
                FarmSelectorRow(
                    farms = state.farms,
                    selectedFarmId = state.selectedFarmId,
                    onSelectFarm = viewModel::selectFarm
                )

                StatusFilterRow(
                    selectedStatus = state.selectedStatusFilter,
                    onSelectStatus = viewModel::selectStatusFilter
                )

                if (state.isRefreshing) {
                    LinearProgressIndicator(
                        modifier = Modifier.fillMaxWidth(),
                        color = colors.primaryAmberOchre,
                        trackColor = colors.surfaceContainerHigh
                    )
                }

                when {
                    state.isLoadingHistory && state.items.isEmpty() -> {
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center
                        ) {
                            Column(
                                horizontalAlignment = Alignment.CenterHorizontally,
                                verticalArrangement = Arrangement.spacedBy(12.dp)
                            ) {
                                CircularProgressIndicator(color = colors.primaryAmberOchre)
                                Text(
                                    text = stringResource(R.string.analysis_history_loading),
                                    style = typography.bodyMd,
                                    color = colors.textSecondary
                                )
                            }
                        }
                    }
                    state.historyError != null && state.items.isEmpty() -> {
                        val error = state.historyError!!
                        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                Text(
                                    text = formatAnalysisErrorMessage(error),
                                    style = typography.bodyMd,
                                    color = colors.erosionAlert
                                )
                                FieldShiftOutlinedButton(
                                    text = stringResource(R.string.analysis_history_retry),
                                    onClick = viewModel::retryHistory,
                                    modifier = Modifier.fillMaxWidth()
                                )
                            }
                        }
                    }
                    state.items.isEmpty() -> {
                        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                            Text(
                                text = stringResource(
                                    if (state.selectedStatusFilter == null) {
                                        R.string.analysis_history_empty
                                    } else {
                                        R.string.analysis_history_empty_filtered
                                    }
                                ),
                                style = typography.bodyMd,
                                color = colors.textSecondary
                            )
                        }
                    }
                    else -> {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            contentPadding = PaddingValues(bottom = 24.dp),
                            verticalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            state.historyError?.let { inlineError ->
                                item(key = "history-refresh-error") {
                                    FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                                        Text(
                                            text = formatAnalysisErrorMessage(inlineError),
                                            style = typography.bodySm,
                                            color = colors.erosionAlert
                                        )
                                    }
                                }
                            }

                            items(
                                items = state.items,
                                key = { it.requestId }
                            ) { item ->
                                val action = viewModel.resolveItemAction(item)
                                AnalysisHistoryItemCard(
                                    item = item,
                                    action = action,
                                    onOpenResult = onOpenResult,
                                    onOpenProgress = onOpenProgress
                                )
                            }

                            if (state.loadMoreError != null) {
                                val loadMoreError = state.loadMoreError!!
                                item(key = "load-more-error") {
                                    FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                            Text(
                                                text = formatAnalysisErrorMessage(loadMoreError),
                                                style = typography.bodySm,
                                                color = colors.erosionAlert
                                            )
                                            FieldShiftOutlinedButton(
                                                text = stringResource(R.string.analysis_history_retry),
                                                onClick = viewModel::loadMore,
                                                modifier = Modifier.fillMaxWidth()
                                            )
                                        }
                                    }
                                }
                            } else if (state.hasMore) {
                                item(key = "load-more") {
                                    FieldShiftOutlinedButton(
                                        text = stringResource(
                                            if (state.isLoadingMore) {
                                                R.string.analysis_history_loading_more
                                            } else {
                                                R.string.analysis_history_load_more
                                            }
                                        ),
                                        onClick = viewModel::loadMore,
                                        enabled = !state.isLoadingMore,
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

@Composable
private fun HistoryHeaderCard(
    isRefreshing: Boolean,
    canRefresh: Boolean,
    onRefresh: () -> Unit
) {
    val colors = FieldShiftTheme.colors
    val typography = FieldShiftTheme.typography

    FieldShiftCard(modifier = Modifier.fillMaxWidth(), elevated = true) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(
                modifier = Modifier
                    .weight(1f)
                    .padding(end = 12.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                Text(
                    text = stringResource(R.string.analysis_history_title),
                    style = typography.headlineMd,
                    color = colors.textPrimary
                )
                Text(
                    text = stringResource(R.string.analysis_history_subtitle),
                    style = typography.bodySm,
                    color = colors.textSecondary
                )
            }
            FieldShiftOutlinedButton(
                text = stringResource(R.string.analysis_history_refresh),
                onClick = onRefresh,
                enabled = canRefresh,
                leadingIcon = if (isRefreshing) null else Icons.Outlined.Refresh
            )
        }
    }
}

@Composable
private fun FarmSelectorRow(
    farms: List<Farm>,
    selectedFarmId: String?,
    onSelectFarm: (String) -> Unit
) {
    val colors = FieldShiftTheme.colors
    val typography = FieldShiftTheme.typography

    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(
            text = stringResource(R.string.analysis_history_farm_label),
            style = typography.labelSm,
            color = colors.textSecondary
        )
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            items(farms, key = { it.id }) { farm ->
                FieldShiftFilterChip(
                    label = farm.name,
                    selected = farm.id == selectedFarmId,
                    onClick = { onSelectFarm(farm.id) }
                )
            }
        }
    }
}

@Composable
private fun StatusFilterRow(
    selectedStatus: AnalysisJobStatus?,
    onSelectStatus: (AnalysisJobStatus?) -> Unit
) {
    val colors = FieldShiftTheme.colors
    val typography = FieldShiftTheme.typography

    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(
            text = stringResource(R.string.analysis_history_status_label),
            style = typography.labelSm,
            color = colors.textSecondary
        )
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            item(key = "all") {
                FieldShiftFilterChip(
                    label = stringResource(R.string.analysis_history_filter_all),
                    selected = selectedStatus == null,
                    onClick = { onSelectStatus(null) }
                )
            }
            items(AnalysisJobStatus.entries, key = { it.apiValue }) { status ->
                FieldShiftFilterChip(
                    label = status.label(),
                    selected = selectedStatus == status,
                    onClick = { onSelectStatus(status) }
                )
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun AnalysisHistoryItemCard(
    item: FarmAnalysisSummary,
    action: HistoryItemAction,
    onOpenResult: (String) -> Unit,
    onOpenProgress: (String) -> Unit
) {
    val colors = FieldShiftTheme.colors
    val typography = FieldShiftTheme.typography

    FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                FieldShiftStatusChip(
                    text = item.status.label(),
                    tone = item.status.toTone()
                )
                Text(
                    text = item.createdAt,
                    style = typography.labelSm,
                    color = colors.textSecondary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }

            Text(
                text = item.analysisId ?: item.requestId,
                style = typography.headlineSm,
                color = colors.textPrimary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )

            if (item.analysisId != null) {
                Text(
                    text = item.requestId,
                    style = typography.labelSm,
                    color = colors.textTertiary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }

            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                Text(
                    text = stringResource(
                        R.string.analysis_history_language_label,
                        item.language.languageTag.uppercase()
                    ),
                    style = typography.bodySm,
                    color = colors.textSecondary
                )
                Text(
                    text = stringResource(R.string.analysis_history_catalog_label, item.catalogVersion),
                    style = typography.bodySm,
                    color = colors.textSecondary
                )
                item.durationMs?.let { durationMs ->
                    Text(
                        text = stringResource(R.string.analysis_history_duration_ms, durationMs),
                        style = typography.bodySm,
                        color = colors.textSecondary
                    )
                }
                if (item.warnings.isNotEmpty()) {
                    Text(
                        text = stringResource(R.string.analysis_history_warnings_count, item.warnings.size),
                        style = typography.bodySm,
                        color = colors.primaryAmberOchre
                    )
                }
            }

            Spacer(modifier = Modifier.height(2.dp))

            when (action) {
                is HistoryItemAction.OpenResult -> {
                    FieldShiftPrimaryButton(
                        text = stringResource(R.string.analysis_history_open_result),
                        onClick = { onOpenResult(action.analysisId) },
                        modifier = Modifier.fillMaxWidth()
                    )
                }
                is HistoryItemAction.OpenProgress -> {
                    FieldShiftOutlinedButton(
                        text = stringResource(R.string.analysis_history_open_progress),
                        onClick = { onOpenProgress(action.requestId) },
                        modifier = Modifier.fillMaxWidth()
                    )
                }
                HistoryItemAction.Unavailable -> {
                    Text(
                        text = stringResource(R.string.analysis_history_result_unavailable),
                        style = typography.labelSm,
                        color = colors.textTertiary
                    )
                }
            }
        }
    }
}

private fun AnalysisJobStatus.toTone(): AgronomicStatusTone = when (this) {
    AnalysisJobStatus.OK -> AgronomicStatusTone.NominalFoliage
    AnalysisJobStatus.PARTIAL -> AgronomicStatusTone.HarvestOchre
    AnalysisJobStatus.FAILED,
    AnalysisJobStatus.CANCELLED -> AgronomicStatusTone.MoistureDeficitAlert
    AnalysisJobStatus.PENDING,
    AnalysisJobStatus.RUNNING -> AgronomicStatusTone.TelemetryCyan
}
