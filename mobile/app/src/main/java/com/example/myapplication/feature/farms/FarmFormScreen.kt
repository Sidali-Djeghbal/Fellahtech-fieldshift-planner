package com.example.myapplication.feature.farms

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.Check
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.myapplication.R
import com.example.myapplication.core.designsystem.component.FieldShiftCard
import com.example.myapplication.core.designsystem.component.FieldShiftOutlinedButton
import com.example.myapplication.core.designsystem.component.FieldShiftPrimaryButton
import com.example.myapplication.core.designsystem.component.FieldShiftTextField
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme
import com.example.myapplication.domain.farm.Farm
import com.example.myapplication.domain.farm.FarmError

@Composable
fun FarmFormScreen(
    farmId: String?,
    onSaved: (Farm) -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: FarmFormViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val spacing = FieldShiftTheme.spacing
    val colors = FieldShiftTheme.colors

    LaunchedEffect(farmId) {
        viewModel.initialize(farmId)
    }

    LaunchedEffect(uiState.savedFarm) {
        uiState.savedFarm?.let(onSaved)
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

        Text(
            text = if (uiState.isEditMode) {
                stringResource(id = R.string.farm_form_edit_title)
            } else {
                stringResource(id = R.string.farm_form_create_title)
            },
            style = FieldShiftTheme.typography.headlineMd,
            color = colors.textPrimary
        )

        when {
            uiState.isLoadingExisting -> {
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

            uiState.loadError != null -> {
                val loadError = uiState.loadError!!
                val isNotFound = (loadError as? FarmError.Api)?.isNotFound == true
                FieldShiftCard(modifier = Modifier.fillMaxWidth(), elevated = true) {
                    Text(
                        text = formatFarmErrorMessage(loadError),
                        style = FieldShiftTheme.typography.bodyMd,
                        color = colors.erosionAlert
                    )
                    if (!isNotFound) {
                        Spacer(modifier = Modifier.height(spacing.spaceMd))
                        FieldShiftOutlinedButton(
                            text = stringResource(id = R.string.farms_error_retry),
                            onClick = viewModel::retryLoadExisting,
                            modifier = Modifier.fillMaxWidth(),
                            leadingIcon = Icons.Outlined.Refresh
                        )
                    }
                }
            }

            else -> {
                FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                    FieldShiftTextField(
                        value = uiState.name,
                        onValueChange = viewModel::onNameChanged,
                        label = stringResource(id = R.string.farm_form_name_label),
                        placeholder = stringResource(id = R.string.farm_form_name_placeholder),
                        enabled = !uiState.isSubmitting,
                        isError = uiState.nameError != null,
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next)
                    )
                    uiState.nameError?.let { err ->
                        Spacer(modifier = Modifier.height(spacing.spaceXs))
                        Text(
                            text = when (err) {
                                FarmFieldError.REQUIRED -> stringResource(id = R.string.farm_validation_name_required)
                                FarmFieldError.TOO_LONG -> stringResource(id = R.string.farm_validation_name_too_long)
                            },
                            style = FieldShiftTheme.typography.bodySm,
                            color = colors.erosionAlert
                        )
                    }

                    Spacer(modifier = Modifier.height(spacing.spaceSm))
                    FieldShiftTextField(
                        value = uiState.country,
                        onValueChange = viewModel::onCountryChanged,
                        label = stringResource(id = R.string.farm_form_country_label),
                        placeholder = stringResource(id = R.string.farm_form_country_placeholder),
                        enabled = !uiState.isSubmitting,
                        isError = uiState.countryError != null,
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next)
                    )
                    uiState.countryError?.let { err ->
                        Spacer(modifier = Modifier.height(spacing.spaceXs))
                        Text(
                            text = when (err) {
                                FarmFieldError.REQUIRED -> stringResource(id = R.string.farm_validation_country_required)
                                FarmFieldError.TOO_LONG -> stringResource(id = R.string.farm_validation_country_too_long)
                            },
                            style = FieldShiftTheme.typography.bodySm,
                            color = colors.erosionAlert
                        )
                    }

                    Spacer(modifier = Modifier.height(spacing.spaceSm))
                    FieldShiftTextField(
                        value = uiState.region,
                        onValueChange = viewModel::onRegionChanged,
                        label = stringResource(id = R.string.farm_form_region_label),
                        placeholder = stringResource(id = R.string.farm_form_region_placeholder),
                        enabled = !uiState.isSubmitting,
                        isError = uiState.regionError != null,
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next)
                    )
                    uiState.regionError?.let { err ->
                        Spacer(modifier = Modifier.height(spacing.spaceXs))
                        Text(
                            text = when (err) {
                                FarmFieldError.REQUIRED -> stringResource(id = R.string.farm_validation_region_required)
                                FarmFieldError.TOO_LONG -> stringResource(id = R.string.farm_validation_region_too_long)
                            },
                            style = FieldShiftTheme.typography.bodySm,
                            color = colors.erosionAlert
                        )
                    }

                    Spacer(modifier = Modifier.height(spacing.spaceSm))
                    FieldShiftTextField(
                        value = uiState.commune,
                        onValueChange = viewModel::onCommuneChanged,
                        label = stringResource(id = R.string.farm_form_commune_label),
                        placeholder = stringResource(id = R.string.farm_form_commune_placeholder),
                        enabled = !uiState.isSubmitting,
                        isError = uiState.communeError != null,
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done)
                    )
                    uiState.communeError?.let {
                        Spacer(modifier = Modifier.height(spacing.spaceXs))
                        Text(
                            text = stringResource(id = R.string.farm_validation_commune_too_long),
                            style = FieldShiftTheme.typography.bodySm,
                            color = colors.erosionAlert
                        )
                    }

                    uiState.submitError?.let { error ->
                        Spacer(modifier = Modifier.height(spacing.spaceMd))
                        Text(
                            text = formatFarmErrorMessage(error),
                            style = FieldShiftTheme.typography.bodySm,
                            color = colors.erosionAlert
                        )
                    }

                    Spacer(modifier = Modifier.height(spacing.spaceMd))
                    if (uiState.isSubmitting) {
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
                            text = if (uiState.isEditMode) {
                                stringResource(id = R.string.farm_form_submit_save)
                            } else {
                                stringResource(id = R.string.farm_form_submit_create)
                            },
                            onClick = viewModel::submit,
                            modifier = Modifier.fillMaxWidth(),
                            leadingIcon = Icons.Outlined.Check
                        )
                    }
                }
            }
        }
    }
}

