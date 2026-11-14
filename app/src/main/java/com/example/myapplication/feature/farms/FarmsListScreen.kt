package com.example.myapplication.feature.farms

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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.Agriculture
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.myapplication.R
import com.example.myapplication.core.common.UiState
import com.example.myapplication.core.designsystem.component.AgronomicStatusTone
import com.example.myapplication.core.designsystem.component.FieldShiftCard
import com.example.myapplication.core.designsystem.component.FieldShiftOutlinedButton
import com.example.myapplication.core.designsystem.component.FieldShiftPrimaryButton
import com.example.myapplication.core.designsystem.component.FieldShiftStatusChip
import com.example.myapplication.core.designsystem.component.FieldShiftTextField
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme
import com.example.myapplication.domain.auth.SessionState
import com.example.myapplication.domain.farm.Farm

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FarmsListScreen(
    viewModel: FarmsListViewModel,
    onCreateFarmClick: () -> Unit,
    onFarmClick: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val sessionState by viewModel.sessionState.collectAsStateWithLifecycle()
    val spacing = FieldShiftTheme.spacing
    val colors = FieldShiftTheme.colors

    PullToRefreshBox(
        isRefreshing = uiState.isRefreshing,
        onRefresh = viewModel::refresh,
        modifier = modifier.fillMaxSize()
    ) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(
                horizontal = spacing.marginMobile,
                vertical = spacing.spaceMd
            ),
            verticalArrangement = Arrangement.spacedBy(spacing.spaceMd)
        ) {
            if (sessionState is SessionState.GuestSession) {
                item(key = "guest_banner") {
                    FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                        FieldShiftStatusChip(
                            text = stringResource(id = R.string.profile_badge_guest),
                            tone = AgronomicStatusTone.HarvestOchre
                        )
                        Spacer(modifier = Modifier.height(spacing.spaceXs))
                        Text(
                            text = stringResource(id = R.string.farms_guest_banner),
                            style = FieldShiftTheme.typography.bodySm,
                            color = colors.textSecondary
                        )
                    }
                }
            }

            item(key = "search_and_create") {
                Column(verticalArrangement = Arrangement.spacedBy(spacing.spaceSm)) {
                    FieldShiftTextField(
                        value = uiState.searchQuery,
                        onValueChange = viewModel::onSearchQueryChanged,
                        label = stringResource(id = R.string.farms_search_label),
                        placeholder = stringResource(id = R.string.farms_search_placeholder),
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                        keyboardActions = KeyboardActions(onSearch = { viewModel.submitSearch() }),
                        trailingIcon = {
                            IconButton(onClick = viewModel::submitSearch) {
                                Icon(
                                    imageVector = Icons.Outlined.Search,
                                    contentDescription = stringResource(id = R.string.farms_search_label),
                                    tint = colors.primaryAmberOchre
                                )
                            }
                        }
                    )
                    FieldShiftPrimaryButton(
                        text = stringResource(id = R.string.farms_create_action),
                        onClick = onCreateFarmClick,
                        modifier = Modifier.fillMaxWidth(),
                        leadingIcon = Icons.Outlined.Add
                    )
                }
            }

            if (uiState.lastError != null && uiState.farmsState is UiState.Success) {
                item(key = "refresh_error") {
                    val err = uiState.lastError!!
                    FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                        Text(
                            text = formatFarmErrorMessage(err),
                            style = FieldShiftTheme.typography.bodySm,
                            color = colors.erosionAlert
                        )
                    }
                }
            }

            when (val farmsState = uiState.farmsState) {
                is UiState.Loading -> {
                    item(key = "loading") {
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
                }

                is UiState.Empty -> {
                    item(key = "empty") {
                        FieldShiftCard(modifier = Modifier.fillMaxWidth(), elevated = true) {
                            Icon(
                                imageVector = Icons.Outlined.Agriculture,
                                contentDescription = null,
                                tint = colors.primaryAmberOchre,
                                modifier = Modifier.size(28.dp)
                            )
                            Spacer(modifier = Modifier.height(spacing.spaceSm))
                            Text(
                                text = stringResource(id = R.string.farms_empty_title),
                                style = FieldShiftTheme.typography.headlineSm,
                                color = colors.textPrimary
                            )
                            Spacer(modifier = Modifier.height(spacing.spaceXs))
                            Text(
                                text = if (uiState.searchQuery.isBlank()) {
                                    stringResource(id = R.string.farms_empty_body)
                                } else {
                                    stringResource(id = R.string.farms_empty_search_body)
                                },
                                style = FieldShiftTheme.typography.bodyMd,
                                color = colors.textSecondary
                            )
                        }
                    }
                }

                is UiState.Error -> {
                    item(key = "error") {
                        FieldShiftCard(modifier = Modifier.fillMaxWidth(), elevated = true) {
                            Text(
                                text = uiState.lastError?.let { formatFarmErrorMessage(it) }
                                    ?: farmsState.message,
                                style = FieldShiftTheme.typography.bodyMd,
                                color = colors.erosionAlert
                            )
                            Spacer(modifier = Modifier.height(spacing.spaceMd))
                            FieldShiftOutlinedButton(
                                text = stringResource(id = R.string.farms_error_retry),
                                onClick = viewModel::loadFarms,
                                modifier = Modifier.fillMaxWidth(),
                                leadingIcon = Icons.Outlined.Refresh
                            )
                        }
                    }
                }

                is UiState.Success -> {
                    items(items = farmsState.data, key = { it.id }) { farm ->
                        FarmSummaryCard(
                            farm = farm,
                            onClick = { onFarmClick(farm.id) }
                        )
                    }

                    if (uiState.hasMore) {
                        item(key = "load_more") {
                            Column(verticalArrangement = Arrangement.spacedBy(spacing.spaceXs)) {
                                if (uiState.paginationError != null) {
                                    Text(
                                        text = formatFarmErrorMessage(uiState.paginationError!!),
                                        style = FieldShiftTheme.typography.bodySm,
                                        color = colors.erosionAlert
                                    )
                                }
                                if (uiState.isLoadingMore) {
                                    Box(
                                        modifier = Modifier.fillMaxWidth(),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        CircularProgressIndicator(
                                            modifier = Modifier.size(24.dp),
                                            color = colors.primaryAmberOchre
                                        )
                                    }
                                } else {
                                    FieldShiftOutlinedButton(
                                        text = stringResource(id = R.string.farms_load_more),
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

@Composable
private fun FarmSummaryCard(
    farm: Farm,
    onClick: () -> Unit
) {
    val spacing = FieldShiftTheme.spacing
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
            Text(
                text = farm.name,
                style = FieldShiftTheme.typography.headlineSm,
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
        Spacer(modifier = Modifier.height(spacing.spaceXs))
        val locationLine = buildString {
            append(farm.region)
            append(", ")
            append(farm.country)
            if (!farm.commune.isNullOrBlank()) {
                append(" • ")
                append(farm.commune)
            }
        }
        Text(
            text = locationLine,
            style = FieldShiftTheme.typography.bodyMd,
            color = colors.textSecondary
        )
        Spacer(modifier = Modifier.height(spacing.spaceXs))
        Text(
            text = stringResource(id = R.string.farms_created_at, farm.createdAtIso),
            style = FieldShiftTheme.typography.bodySm,
            color = colors.textTertiary
        )
    }
}
