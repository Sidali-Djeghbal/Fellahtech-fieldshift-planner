package com.example.myapplication.feature.profile

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
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
import androidx.compose.material.icons.automirrored.outlined.Logout
import androidx.compose.material.icons.outlined.DeleteForever
import androidx.compose.material.icons.outlined.PinDrop
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.myapplication.R
import com.example.myapplication.core.common.AppLanguage
import com.example.myapplication.core.designsystem.component.AgronomicStatusTone
import com.example.myapplication.core.designsystem.component.FieldShiftCard
import com.example.myapplication.core.designsystem.component.FieldShiftCoordinateBadge
import com.example.myapplication.core.designsystem.component.FieldShiftFilterChip
import com.example.myapplication.core.designsystem.component.FieldShiftOutlinedButton
import com.example.myapplication.core.designsystem.component.FieldShiftPrimaryButton
import com.example.myapplication.core.designsystem.component.FieldShiftStatusChip
import com.example.myapplication.core.designsystem.component.FieldShiftTonalSensorButton
import com.example.myapplication.core.designsystem.component.SensorAccentTone
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme
import com.example.myapplication.core.location.CoordinatesFormatter
import com.example.myapplication.domain.auth.GuestSessionInfo
import com.example.myapplication.domain.auth.SessionState
import com.example.myapplication.domain.auth.UserProfile

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ProfileScreen(
    selectedLanguage: AppLanguage,
    onLanguageSelected: (AppLanguage) -> Unit,
    modifier: Modifier = Modifier,
    viewModel: ProfileViewModel = hiltViewModel()
) {
    val sessionState by viewModel.sessionState.collectAsStateWithLifecycle()
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val spacing = FieldShiftTheme.spacing
    val colors = FieldShiftTheme.colors

    if (uiState.showDeleteConfirmation) {
        AlertDialog(
            onDismissRequest = viewModel::dismissDeleteConfirmation,
            containerColor = colors.surfaceContainerHigh,
            titleContentColor = colors.textPrimary,
            textContentColor = colors.textSecondary,
            title = { Text(text = stringResource(id = R.string.profile_delete_confirm_title)) },
            text = { Text(text = stringResource(id = R.string.profile_delete_confirm_body)) },
            confirmButton = {
                TextButton(onClick = viewModel::confirmDeleteAccount) {
                    Text(
                        text = stringResource(id = R.string.profile_delete_confirm_action),
                        color = colors.erosionAlert
                    )
                }
            },
            dismissButton = {
                TextButton(onClick = viewModel::dismissDeleteConfirmation) {
                    Text(
                        text = stringResource(id = R.string.profile_cancel),
                        color = colors.textPrimary
                    )
                }
            }
        )
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = spacing.marginMobile, vertical = spacing.spaceMd),
        verticalArrangement = Arrangement.spacedBy(spacing.spaceMd)
    ) {
        if (!uiState.errorMessage.isNullOrBlank()) {
            FieldShiftCard(modifier = Modifier.fillMaxWidth(), active = true) {
                Text(
                    text = uiState.errorMessage.orEmpty(),
                    style = FieldShiftTheme.typography.bodyMd,
                    color = colors.erosionAlert
                )
            }
        }

        when (val state = sessionState) {
            is SessionState.Authenticated -> {
                AuthenticatedProfileCard(
                    user = state.user,
                    isBusy = uiState.isBusy,
                    onLogout = viewModel::logout,
                    onDeleteAccount = viewModel::requestDeleteAccount
                )
            }
            is SessionState.GuestSession -> {
                GuestProfileCard(
                    info = state.info,
                    isBusy = uiState.isBusy,
                    onRefresh = viewModel::refreshGuestSession,
                    onExitGuest = viewModel::exitGuestSession
                )
            }
            else -> Unit
        }

        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = stringResource(id = R.string.localization_preview_title),
                style = FieldShiftTheme.typography.headlineSm,
                color = colors.textPrimary
            )
            Spacer(modifier = Modifier.height(spacing.spaceSm))
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(spacing.spaceSm),
                verticalArrangement = Arrangement.spacedBy(spacing.spaceSm)
            ) {
                AppLanguage.entries.forEach { language ->
                    FieldShiftFilterChip(
                        label = language.displayName,
                        selected = language == selectedLanguage,
                        onClick = { onLanguageSelected(language) }
                    )
                }
            }
        }
    }
}

@Composable
private fun AuthenticatedProfileCard(
    user: UserProfile,
    isBusy: Boolean,
    onLogout: () -> Unit,
    onDeleteAccount: () -> Unit
) {
    val spacing = FieldShiftTheme.spacing
    val colors = FieldShiftTheme.colors

    FieldShiftCard(modifier = Modifier.fillMaxWidth(), elevated = true) {
        FieldShiftStatusChip(
            text = stringResource(id = R.string.profile_badge_authenticated),
            tone = AgronomicStatusTone.NominalFoliage
        )
        Spacer(modifier = Modifier.height(spacing.spaceSm))
        Text(
            text = user.fullName,
            style = FieldShiftTheme.typography.headlineMd,
            color = colors.textPrimary
        )
        Text(
            text = user.email,
            style = FieldShiftTheme.typography.bodyMd,
            color = colors.telemetryCyan
        )
        Spacer(modifier = Modifier.height(spacing.spaceXs))
        Text(
            text = stringResource(id = R.string.profile_member_since, user.createdAt),
            style = FieldShiftTheme.typography.labelSm,
            color = colors.textSecondary
        )
        Spacer(modifier = Modifier.height(spacing.spaceMd))

        if (isBusy) {
            CircularProgressIndicator(
                modifier = Modifier.size(28.dp),
                color = colors.primaryAmberOchre
            )
        } else {
            FieldShiftPrimaryButton(
                text = stringResource(id = R.string.profile_logout),
                onClick = onLogout,
                modifier = Modifier.fillMaxWidth(),
                leadingIcon = Icons.AutoMirrored.Outlined.Logout
            )
            Spacer(modifier = Modifier.height(spacing.spaceSm))
            FieldShiftOutlinedButton(
                text = stringResource(id = R.string.profile_delete_account),
                onClick = onDeleteAccount,
                modifier = Modifier.fillMaxWidth(),
                leadingIcon = Icons.Outlined.DeleteForever
            )
        }
    }
}

@Composable
private fun GuestProfileCard(
    info: GuestSessionInfo,
    isBusy: Boolean,
    onRefresh: () -> Unit,
    onExitGuest: () -> Unit
) {
    val spacing = FieldShiftTheme.spacing
    val colors = FieldShiftTheme.colors

    FieldShiftCard(modifier = Modifier.fillMaxWidth(), elevated = true) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            FieldShiftStatusChip(
                text = stringResource(id = R.string.profile_badge_guest),
                tone = AgronomicStatusTone.HarvestOchre
            )
            FieldShiftTonalSensorButton(
                text = stringResource(id = R.string.guest_demo_refresh),
                onClick = onRefresh,
                leadingIcon = Icons.Outlined.Refresh,
                accentTone = SensorAccentTone.TelemetryCyan,
                enabled = !isBusy
            )
        }
        Spacer(modifier = Modifier.height(spacing.spaceSm))
        Text(
            text = info.demoLocation.name,
            style = FieldShiftTheme.typography.headlineMd,
            color = colors.textPrimary
        )
        Text(
            text = "${info.demoLocation.region}, ${info.demoLocation.country} (${info.demoLocation.code})",
            style = FieldShiftTheme.typography.bodySm,
            color = colors.textSecondary
        )
        Spacer(modifier = Modifier.height(spacing.spaceXs))
        Text(
            text = stringResource(id = R.string.guest_demo_expires, info.expiresAt),
            style = FieldShiftTheme.typography.labelSm,
            color = colors.textTertiary
        )
    }

    info.demoParcel?.let { demoParcel ->
        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = stringResource(id = R.string.guest_demo_parcel_title),
                    style = FieldShiftTheme.typography.headlineSm,
                    color = colors.textPrimary
                )
                if (demoParcel.isUnverifiedDemoParcel) {
                    FieldShiftStatusChip(
                        text = stringResource(id = R.string.guest_demo_unverified_badge),
                        tone = AgronomicStatusTone.MoistureDeficitAlert
                    )
                }
            }
            Spacer(modifier = Modifier.height(spacing.spaceXs))
            Text(
                text = demoParcel.fieldName,
                style = FieldShiftTheme.typography.bodyLg,
                color = colors.textPrimary
            )
            Spacer(modifier = Modifier.height(spacing.spaceXs))
            Row(
                horizontalArrangement = Arrangement.spacedBy(spacing.spaceSm),
                verticalAlignment = Alignment.CenterVertically
            ) {
                FieldShiftCoordinateBadge(
                    coordinatesText = CoordinatesFormatter.formatDecimal(
                        latitude = demoParcel.latitude,
                        longitude = demoParcel.longitude
                    ),
                    leadingIcon = Icons.Outlined.PinDrop
                )
                Text(
                    text = stringResource(id = R.string.guest_demo_area_ha, demoParcel.areaHectares),
                    style = FieldShiftTheme.typography.labelMd,
                    color = colors.textSecondary
                )
            }
            demoParcel.warnings.forEach { warning ->
                Spacer(modifier = Modifier.height(spacing.spaceXs))
                Text(
                    text = warning.message,
                    style = FieldShiftTheme.typography.bodySm,
                    color = colors.erosionAlert
                )
            }
        }
    }

    if (info.limits != null && info.usage != null) {
        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = stringResource(id = R.string.guest_demo_limits_title),
                style = FieldShiftTheme.typography.headlineSm,
                color = colors.textPrimary
            )
            Spacer(modifier = Modifier.height(spacing.spaceXs))
            Text(
                text = stringResource(
                    id = R.string.guest_usage_farms,
                    info.usage.farms,
                    info.limits.maxFarms
                ),
                style = FieldShiftTheme.typography.labelMd,
                color = colors.textSecondary
            )
            Text(
                text = stringResource(
                    id = R.string.guest_usage_fields,
                    info.usage.fields,
                    info.limits.maxFieldsPerFarm
                ),
                style = FieldShiftTheme.typography.labelMd,
                color = colors.textSecondary
            )
            Text(
                text = stringResource(
                    id = R.string.guest_usage_analyses,
                    info.usage.analyses,
                    info.limits.maxAnalyses
                ),
                style = FieldShiftTheme.typography.labelMd,
                color = colors.textSecondary
            )
        }
    }

    if (isBusy) {
        CircularProgressIndicator(
            modifier = Modifier.size(28.dp),
            color = colors.primaryAmberOchre
        )
    } else {
        FieldShiftOutlinedButton(
            text = stringResource(id = R.string.guest_demo_exit),
            onClick = onExitGuest,
            modifier = Modifier.fillMaxWidth(),
            leadingIcon = Icons.AutoMirrored.Outlined.Logout
        )
    }
}

