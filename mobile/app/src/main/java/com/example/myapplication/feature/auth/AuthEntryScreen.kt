package com.example.myapplication.feature.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Login
import androidx.compose.material.icons.outlined.Eco
import androidx.compose.material.icons.outlined.Explore
import androidx.compose.material.icons.outlined.PersonAdd
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.myapplication.R
import com.example.myapplication.core.common.AppLanguage
import com.example.myapplication.core.common.UiState
import com.example.myapplication.core.designsystem.component.AgronomicStatusTone
import com.example.myapplication.core.designsystem.component.FieldShiftCard
import com.example.myapplication.core.designsystem.component.FieldShiftFilterChip
import com.example.myapplication.core.designsystem.component.FieldShiftOutlinedButton
import com.example.myapplication.core.designsystem.component.FieldShiftPrimaryButton
import com.example.myapplication.core.designsystem.component.FieldShiftStatusChip
import com.example.myapplication.core.designsystem.component.FieldShiftTextField
import com.example.myapplication.core.designsystem.component.FieldShiftTonalSensorButton
import com.example.myapplication.core.designsystem.component.SensorAccentTone
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme
import com.example.myapplication.domain.auth.DemoLocation

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun AuthEntryScreen(
    selectedLanguage: AppLanguage,
    onLanguageSelected: (AppLanguage) -> Unit,
    modifier: Modifier = Modifier,
    viewModel: AuthViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val colors = FieldShiftTheme.colors
    val spacing = FieldShiftTheme.spacing

    Scaffold(
        modifier = modifier.fillMaxSize(),
        containerColor = FieldShiftTheme.colorScheme.background
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .windowInsetsPadding(WindowInsets.statusBars)
                .windowInsetsPadding(WindowInsets.navigationBars)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = spacing.marginMobile, vertical = spacing.spaceMd),
            verticalArrangement = Arrangement.spacedBy(spacing.spaceMd)
        ) {
            // Header & Language Switcher
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                FieldShiftStatusChip(
                    text = stringResource(id = R.string.auth_badge),
                    tone = AgronomicStatusTone.HarvestOchre
                )
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    AppLanguage.entries.forEach { language ->
                        FieldShiftFilterChip(
                            label = language.languageTag.uppercase(),
                            selected = language == selectedLanguage,
                            onClick = {
                                onLanguageSelected(language)
                                viewModel.onPreferredLanguageChanged(language)
                            }
                        )
                    }
                }
            }

            // Hero Card
            FieldShiftCard(
                modifier = Modifier.fillMaxWidth(),
                elevated = true
            ) {
                Text(
                    text = stringResource(id = R.string.auth_headline),
                    style = FieldShiftTheme.typography.headlineLgMobile,
                    color = colors.textPrimary
                )
                Spacer(modifier = Modifier.height(spacing.spaceXs))
                Text(
                    text = stringResource(id = R.string.auth_subhead),
                    style = FieldShiftTheme.typography.bodyMd,
                    color = colors.textSecondary
                )
            }

            // Mode Selector Chips
            FlowRow(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(spacing.spaceSm),
                verticalArrangement = Arrangement.spacedBy(spacing.spaceSm)
            ) {
                FieldShiftFilterChip(
                    label = stringResource(id = R.string.auth_tab_login),
                    selected = uiState.activeTab == AuthEntryTab.LOGIN,
                    onClick = { viewModel.selectTab(AuthEntryTab.LOGIN) }
                )
                FieldShiftFilterChip(
                    label = stringResource(id = R.string.auth_tab_register),
                    selected = uiState.activeTab == AuthEntryTab.REGISTER,
                    onClick = { viewModel.selectTab(AuthEntryTab.REGISTER) }
                )
                FieldShiftFilterChip(
                    label = stringResource(id = R.string.auth_tab_guest),
                    selected = uiState.activeTab == AuthEntryTab.GUEST,
                    onClick = { viewModel.selectTab(AuthEntryTab.GUEST) }
                )
            }

            // Validation or API Error Banner
            val validationText = uiState.validationError?.let { error ->
                when (error) {
                    AuthValidationError.INVALID_EMAIL ->
                        stringResource(id = R.string.auth_validation_email_invalid)
                    AuthValidationError.PASSWORD_REQUIRED ->
                        stringResource(id = R.string.auth_validation_password_required)
                    AuthValidationError.PASSWORD_TOO_SHORT ->
                        stringResource(id = R.string.auth_validation_password_min)
                    AuthValidationError.NAME_REQUIRED ->
                        stringResource(id = R.string.auth_validation_name_required)
                    AuthValidationError.DEMO_LOCATION_REQUIRED ->
                        stringResource(id = R.string.auth_validation_demo_required)
                }
            }
            val bannerMessage = validationText ?: uiState.errorMessage
            if (!bannerMessage.isNullOrBlank()) {
                FieldShiftCard(
                    modifier = Modifier.fillMaxWidth(),
                    active = true
                ) {
                    Text(
                        text = bannerMessage,
                        style = FieldShiftTheme.typography.bodyMd,
                        color = colors.erosionAlert
                    )
                }
            }

            // Active Form Content
            when (uiState.activeTab) {
                AuthEntryTab.LOGIN -> LoginFormCard(
                    uiState = uiState,
                    onEmailChange = viewModel::onEmailChanged,
                    onPasswordChange = viewModel::onPasswordChanged,
                    onSubmit = viewModel::submitLogin
                )
                AuthEntryTab.REGISTER -> RegisterFormCard(
                    uiState = uiState,
                    onFullNameChange = viewModel::onFullNameChanged,
                    onEmailChange = viewModel::onEmailChanged,
                    onPasswordChange = viewModel::onPasswordChanged,
                    onLanguageChange = { lang ->
                        viewModel.onPreferredLanguageChanged(lang)
                        onLanguageSelected(lang)
                    },
                    onSubmit = viewModel::submitRegister
                )
                AuthEntryTab.GUEST -> GuestDemoCard(
                    uiState = uiState,
                    onReloadLocations = viewModel::loadDemoLocations,
                    onSelectLocation = viewModel::onDemoLocationSelected,
                    onStartGuest = viewModel::submitGuestSession
                )
            }
        }
    }
}

@Composable
private fun LoginFormCard(
    uiState: AuthUiState,
    onEmailChange: (String) -> Unit,
    onPasswordChange: (String) -> Unit,
    onSubmit: () -> Unit
) {
    val spacing = FieldShiftTheme.spacing
    FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
        FieldShiftTextField(
            value = uiState.email,
            onValueChange = onEmailChange,
            label = stringResource(id = R.string.auth_email_label),
            placeholder = stringResource(id = R.string.auth_email_placeholder),
            enabled = !uiState.isSubmitting,
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Email,
                imeAction = ImeAction.Next
            )
        )
        Spacer(modifier = Modifier.height(spacing.spaceSm))
        FieldShiftTextField(
            value = uiState.password,
            onValueChange = onPasswordChange,
            label = stringResource(id = R.string.auth_password_label),
            placeholder = stringResource(id = R.string.auth_password_placeholder),
            enabled = !uiState.isSubmitting,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Password,
                imeAction = ImeAction.Done
            )
        )
        Spacer(modifier = Modifier.height(spacing.spaceMd))
        if (uiState.isSubmitting) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Center
            ) {
                CircularProgressIndicator(
                    modifier = Modifier.size(28.dp),
                    color = FieldShiftTheme.colors.primaryAmberOchre
                )
            }
        } else {
            FieldShiftPrimaryButton(
                text = stringResource(id = R.string.auth_action_login),
                onClick = onSubmit,
                modifier = Modifier.fillMaxWidth(),
                leadingIcon = Icons.AutoMirrored.Outlined.Login
            )
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun RegisterFormCard(
    uiState: AuthUiState,
    onFullNameChange: (String) -> Unit,
    onEmailChange: (String) -> Unit,
    onPasswordChange: (String) -> Unit,
    onLanguageChange: (AppLanguage) -> Unit,
    onSubmit: () -> Unit
) {
    val spacing = FieldShiftTheme.spacing
    val colors = FieldShiftTheme.colors
    FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
        FieldShiftTextField(
            value = uiState.fullName,
            onValueChange = onFullNameChange,
            label = stringResource(id = R.string.auth_full_name_label),
            placeholder = stringResource(id = R.string.auth_full_name_placeholder),
            enabled = !uiState.isSubmitting,
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next)
        )
        Spacer(modifier = Modifier.height(spacing.spaceSm))
        FieldShiftTextField(
            value = uiState.email,
            onValueChange = onEmailChange,
            label = stringResource(id = R.string.auth_email_label),
            placeholder = stringResource(id = R.string.auth_email_placeholder),
            enabled = !uiState.isSubmitting,
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Email,
                imeAction = ImeAction.Next
            )
        )
        Spacer(modifier = Modifier.height(spacing.spaceSm))
        FieldShiftTextField(
            value = uiState.password,
            onValueChange = onPasswordChange,
            label = stringResource(id = R.string.auth_password_label),
            placeholder = stringResource(id = R.string.auth_password_placeholder),
            enabled = !uiState.isSubmitting,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Password,
                imeAction = ImeAction.Done
            )
        )
        Spacer(modifier = Modifier.height(spacing.spaceSm))
        Text(
            text = stringResource(id = R.string.auth_preferred_lang_label),
            style = FieldShiftTheme.typography.bodySm,
            color = colors.textSecondary
        )
        Spacer(modifier = Modifier.height(spacing.spaceXs))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(spacing.spaceSm)) {
            AppLanguage.entries.forEach { language ->
                FieldShiftFilterChip(
                    label = language.displayName,
                    selected = uiState.preferredLanguage == language,
                    onClick = { onLanguageChange(language) }
                )
            }
        }
        Spacer(modifier = Modifier.height(spacing.spaceMd))
        if (uiState.isSubmitting) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Center
            ) {
                CircularProgressIndicator(
                    modifier = Modifier.size(28.dp),
                    color = colors.primaryAmberOchre
                )
            }
        } else {
            FieldShiftPrimaryButton(
                text = stringResource(id = R.string.auth_action_register),
                onClick = onSubmit,
                modifier = Modifier.fillMaxWidth(),
                leadingIcon = Icons.Outlined.PersonAdd
            )
        }
    }
}

@Composable
private fun GuestDemoCard(
    uiState: AuthUiState,
    onReloadLocations: () -> Unit,
    onSelectLocation: (Int) -> Unit,
    onStartGuest: () -> Unit
) {
    val spacing = FieldShiftTheme.spacing
    val colors = FieldShiftTheme.colors

    FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = stringResource(id = R.string.demo_locations_title),
                style = FieldShiftTheme.typography.headlineSm,
                color = colors.textPrimary
            )
            FieldShiftTonalSensorButton(
                text = stringResource(id = R.string.demo_locations_reload),
                onClick = onReloadLocations,
                leadingIcon = Icons.Outlined.Refresh,
                accentTone = SensorAccentTone.TelemetryCyan,
                enabled = !uiState.isSubmitting
            )
        }
        Spacer(modifier = Modifier.height(spacing.spaceSm))

        when (val locationsState = uiState.demoLocationsState) {
            is UiState.Loading -> {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = spacing.spaceMd),
                    horizontalArrangement = Arrangement.spacedBy(spacing.spaceSm),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        color = colors.telemetryCyan
                    )
                    Text(
                        text = stringResource(id = R.string.demo_locations_loading),
                        style = FieldShiftTheme.typography.bodyMd,
                        color = colors.textSecondary
                    )
                }
            }
            is UiState.Empty -> {
                Text(
                    text = stringResource(id = R.string.demo_locations_empty),
                    style = FieldShiftTheme.typography.bodyMd,
                    color = colors.textSecondary
                )
            }
            is UiState.Error -> {
                Text(
                    text = locationsState.message.ifBlank {
                        stringResource(id = R.string.demo_locations_empty)
                    },
                    style = FieldShiftTheme.typography.bodyMd,
                    color = colors.erosionAlert
                )
                Spacer(modifier = Modifier.height(spacing.spaceSm))
                FieldShiftOutlinedButton(
                    text = stringResource(id = R.string.demo_locations_reload),
                    onClick = onReloadLocations,
                    modifier = Modifier.fillMaxWidth()
                )
            }
            is UiState.Success -> {
                Column(verticalArrangement = Arrangement.spacedBy(spacing.spaceSm)) {
                    locationsState.data.forEach { location: DemoLocation ->
                        val isSelected = location.id == uiState.selectedDemoLocationId
                        FieldShiftCard(
                            modifier = Modifier.fillMaxWidth(),
                            active = isSelected,
                            elevated = isSelected,
                            onClick = { onSelectLocation(location.id) }
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = location.name,
                                        style = FieldShiftTheme.typography.headlineSm,
                                        color = colors.textPrimary
                                    )
                                    Text(
                                        text = "${location.region}, ${location.country}",
                                        style = FieldShiftTheme.typography.bodySm,
                                        color = colors.textSecondary
                                    )
                                }
                                FieldShiftStatusChip(
                                    text = location.code,
                                    tone = if (isSelected) {
                                        AgronomicStatusTone.HarvestOchre
                                    } else {
                                        AgronomicStatusTone.TelemetryCyan
                                    },
                                    showStatusDot = isSelected
                                )
                            }
                        }
                    }
                }
                Spacer(modifier = Modifier.height(spacing.spaceMd))
                if (uiState.isSubmitting) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.Center
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(28.dp),
                            color = colors.primaryAmberOchre
                        )
                    }
                } else {
                    FieldShiftPrimaryButton(
                        text = stringResource(id = R.string.auth_action_start_guest),
                        onClick = onStartGuest,
                        modifier = Modifier.fillMaxWidth(),
                        enabled = uiState.selectedDemoLocationId != null,
                        leadingIcon = Icons.Outlined.Explore
                    )
                }
            }
        }
    }
}
