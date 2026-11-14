package com.example.myapplication.navigation

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Eco
import androidx.compose.material.icons.outlined.Language
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.res.stringResource
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.example.myapplication.R
import com.example.myapplication.core.common.AppLanguage
import com.example.myapplication.core.designsystem.component.AgronomicStatusTone
import com.example.myapplication.core.designsystem.component.FieldShiftBottomBar
import com.example.myapplication.core.designsystem.component.FieldShiftBottomNavItem
import com.example.myapplication.core.designsystem.component.FieldShiftCard
import com.example.myapplication.core.designsystem.component.FieldShiftFilterChip
import com.example.myapplication.core.designsystem.component.FieldShiftStatusChip
import com.example.myapplication.core.designsystem.component.FieldShiftTopBar
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme
import com.example.myapplication.core.network.ApiEndpointConfig

@Composable
fun FieldShiftAppShell(
    apiEndpointConfig: ApiEndpointConfig,
    modifier: Modifier = Modifier
) {
    val navController = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route
        ?: FieldShiftTopLevelDestination.DASHBOARD.route

    var selectedLanguage by rememberSaveable { mutableStateOf(AppLanguage.ENGLISH) }

    val bottomNavItems = FieldShiftTopLevelDestination.entries.map { destination ->
        FieldShiftBottomNavItem(
            route = destination.route,
            label = stringResource(id = destination.labelResId),
            icon = destination.icon
        )
    }

    val activeDestination = FieldShiftTopLevelDestination.entries.firstOrNull {
        it.route == currentRoute
    } ?: FieldShiftTopLevelDestination.DASHBOARD

    CompositionLocalProvider(LocalLayoutDirection provides selectedLanguage.layoutDirection) {
        Scaffold(
            modifier = modifier.fillMaxSize(),
            containerColor = FieldShiftTheme.colorScheme.background,
            topBar = {
                FieldShiftTopBar(
                    title = stringResource(id = activeDestination.titleResId),
                    subtitle = stringResource(id = R.string.app_tagline),
                    leadingIcon = Icons.Outlined.Eco
                )
            },
            bottomBar = {
                FieldShiftBottomBar(
                    items = bottomNavItems,
                    currentRoute = currentRoute,
                    onItemSelected = { item ->
                        navController.navigate(item.route) {
                            popUpTo(navController.graph.findStartDestination().id) {
                                saveState = true
                            }
                            launchSingleTop = true
                            restoreState = true
                        }
                    }
                )
            }
        ) { innerPadding ->
            NavHost(
                navController = navController,
                startDestination = FieldShiftTopLevelDestination.DASHBOARD.route,
                modifier = Modifier.padding(innerPadding)
            ) {
                FieldShiftTopLevelDestination.entries.forEach { destination ->
                    composable(route = destination.route) {
                        FoundationSectionEmptyScreen(
                            destination = destination,
                            apiEndpointConfig = apiEndpointConfig,
                            selectedLanguage = selectedLanguage,
                            onLanguageSelected = { selectedLanguage = it }
                        )
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun FoundationSectionEmptyScreen(
    destination: FieldShiftTopLevelDestination,
    apiEndpointConfig: ApiEndpointConfig,
    selectedLanguage: AppLanguage,
    onLanguageSelected: (AppLanguage) -> Unit
) {
    val spacing = FieldShiftTheme.spacing
    val colors = FieldShiftTheme.colors

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(
                horizontal = spacing.marginMobile,
                vertical = spacing.spaceMd
            ),
        verticalArrangement = Arrangement.spacedBy(spacing.spaceMd)
    ) {
        FieldShiftCard(
            modifier = Modifier.fillMaxWidth(),
            elevated = true
        ) {
            FieldShiftStatusChip(
                text = stringResource(id = R.string.foundation_ready_badge),
                tone = AgronomicStatusTone.NominalFoliage
            )
            Spacer(modifier = Modifier.height(spacing.spaceSm))
            Text(
                text = stringResource(id = destination.titleResId),
                style = FieldShiftTheme.typography.headlineMd,
                color = colors.textPrimary
            )
            Spacer(modifier = Modifier.height(spacing.spaceXs))
            Text(
                text = stringResource(id = R.string.foundation_empty_state_message),
                style = FieldShiftTheme.typography.bodyMd,
                color = colors.textSecondary
            )
        }

        FieldShiftCard(
            modifier = Modifier.fillMaxWidth()
        ) {
            Text(
                text = stringResource(id = R.string.network_config_title),
                style = FieldShiftTheme.typography.headlineSm,
                color = colors.textPrimary
            )
            Spacer(modifier = Modifier.height(spacing.spaceXs))
            Text(
                text = if (apiEndpointConfig.isConfigured) {
                    apiEndpointConfig.normalizedBaseUrl
                } else {
                    stringResource(id = R.string.network_config_unset)
                },
                style = FieldShiftTheme.typography.labelLg,
                color = colors.telemetryCyan
            )
        }

        FieldShiftCard(
            modifier = Modifier.fillMaxWidth()
        ) {
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

