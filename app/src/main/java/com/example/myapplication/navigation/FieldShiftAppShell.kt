package com.example.myapplication.navigation

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Eco
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.example.myapplication.R
import com.example.myapplication.core.common.AppLanguage
import com.example.myapplication.core.designsystem.component.AgronomicStatusTone
import com.example.myapplication.core.designsystem.component.FieldShiftBottomBar
import com.example.myapplication.core.designsystem.component.FieldShiftBottomNavItem
import com.example.myapplication.core.designsystem.component.FieldShiftCard
import com.example.myapplication.core.designsystem.component.FieldShiftFilterChip
import com.example.myapplication.core.designsystem.component.FieldShiftOutlinedButton
import com.example.myapplication.core.designsystem.component.FieldShiftPrimaryButton
import com.example.myapplication.core.designsystem.component.FieldShiftStatusChip
import com.example.myapplication.core.designsystem.component.FieldShiftTopBar
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme
import com.example.myapplication.core.network.ApiEndpointConfig
import com.example.myapplication.domain.auth.SessionState
import com.example.myapplication.feature.analysis.AnalysisConfigScreen
import com.example.myapplication.feature.analysis.AnalysisConfigViewModel
import com.example.myapplication.feature.analysis.AnalysisProgressScreen
import com.example.myapplication.feature.analysis.AnalysisProgressViewModel
import com.example.myapplication.feature.analysis.AnalysisResultScreen
import com.example.myapplication.feature.analysis.AnalysisResultViewModel
import com.example.myapplication.feature.auth.AuthEntryScreen
import com.example.myapplication.feature.farms.FarmDetailScreen
import com.example.myapplication.feature.farms.FarmFormScreen
import com.example.myapplication.feature.farms.FarmsListScreen
import com.example.myapplication.feature.fields.FieldDetailScreen
import com.example.myapplication.feature.fields.FieldDetailViewModel
import com.example.myapplication.feature.fields.FieldFormScreen
import com.example.myapplication.feature.fields.FieldFormViewModel
import com.example.myapplication.feature.fields.FieldsListScreen
import com.example.myapplication.feature.fields.FieldsListViewModel
import com.example.myapplication.feature.farms.FarmsListViewModel
import com.example.myapplication.feature.profile.ProfileScreen

@Composable
fun FieldShiftAppShell(
    apiEndpointConfig: ApiEndpointConfig,
    modifier: Modifier = Modifier,
    sessionViewModel: SessionViewModel = hiltViewModel()
) {
    val sessionState by sessionViewModel.sessionState.collectAsStateWithLifecycle()
    var selectedLanguage by rememberSaveable { mutableStateOf(AppLanguage.ENGLISH) }

    LaunchedEffect(sessionState) {
        val authenticated = sessionState as? SessionState.Authenticated
        if (authenticated != null) {
            selectedLanguage = authenticated.user.preferredLanguage
        }
    }

    CompositionLocalProvider(LocalLayoutDirection provides selectedLanguage.layoutDirection) {
        when (val state = sessionState) {
            is SessionState.Initializing -> {
                SessionInitializingScreen(modifier = modifier)
            }
            is SessionState.RecoverableError -> {
                SessionRecoverableErrorScreen(
                    message = state.message,
                    onRetry = sessionViewModel::restoreSession,
                    onSwitchAccount = sessionViewModel::clearSessionLocally,
                    modifier = modifier
                )
            }
            is SessionState.Unauthenticated -> {
                AuthEntryScreen(
                    selectedLanguage = selectedLanguage,
                    onLanguageSelected = { selectedLanguage = it },
                    modifier = modifier
                )
            }
            is SessionState.Authenticated,
            is SessionState.GuestSession -> {
                AuthenticatedAppScaffold(
                    sessionState = state,
                    apiEndpointConfig = apiEndpointConfig,
                    selectedLanguage = selectedLanguage,
                    onLanguageSelected = { selectedLanguage = it },
                    modifier = modifier
                )
            }
        }
    }
}

@Composable
private fun SessionInitializingScreen(modifier: Modifier = Modifier) {
    val colors = FieldShiftTheme.colors
    val spacing = FieldShiftTheme.spacing
    Scaffold(
        modifier = modifier.fillMaxSize(),
        containerColor = FieldShiftTheme.colorScheme.background
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
            contentAlignment = Alignment.Center
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(spacing.spaceMd)
            ) {
                CircularProgressIndicator(
                    modifier = Modifier.size(36.dp),
                    color = colors.primaryAmberOchre
                )
                Text(
                    text = stringResource(id = R.string.session_restoring),
                    style = FieldShiftTheme.typography.bodyMd,
                    color = colors.textSecondary
                )
            }
        }
    }
}

@Composable
private fun SessionRecoverableErrorScreen(
    message: String,
    onRetry: () -> Unit,
    onSwitchAccount: () -> Unit,
    modifier: Modifier = Modifier
) {
    val colors = FieldShiftTheme.colors
    val spacing = FieldShiftTheme.spacing
    Scaffold(
        modifier = modifier.fillMaxSize(),
        containerColor = FieldShiftTheme.colorScheme.background
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = spacing.marginMobile),
            contentAlignment = Alignment.Center
        ) {
            FieldShiftCard(modifier = Modifier.fillMaxWidth(), elevated = true) {
                FieldShiftStatusChip(
                    text = stringResource(id = R.string.session_error_title),
                    tone = AgronomicStatusTone.MoistureDeficitAlert
                )
                Spacer(modifier = Modifier.height(spacing.spaceSm))
                Text(
                    text = message,
                    style = FieldShiftTheme.typography.bodyMd,
                    color = colors.textPrimary
                )
                Spacer(modifier = Modifier.height(spacing.spaceMd))
                FieldShiftPrimaryButton(
                    text = stringResource(id = R.string.session_error_retry),
                    onClick = onRetry,
                    modifier = Modifier.fillMaxWidth(),
                    leadingIcon = Icons.Outlined.Refresh
                )
                Spacer(modifier = Modifier.height(spacing.spaceSm))
                FieldShiftOutlinedButton(
                    text = stringResource(id = R.string.session_error_switch_account),
                    onClick = onSwitchAccount,
                    modifier = Modifier.fillMaxWidth()
                )
            }
        }
    }
}

@Composable
private fun AuthenticatedAppScaffold(
    sessionState: SessionState,
    apiEndpointConfig: ApiEndpointConfig,
    selectedLanguage: AppLanguage,
    onLanguageSelected: (AppLanguage) -> Unit,
    modifier: Modifier = Modifier
) {
    val navController = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route
        ?: FieldShiftTopLevelDestination.DASHBOARD.route
    val farmsListViewModel: FarmsListViewModel = hiltViewModel()
    val fieldsListViewModel: FieldsListViewModel = hiltViewModel()

    val bottomNavItems = FieldShiftTopLevelDestination.entries.map { destination ->
        FieldShiftBottomNavItem(
            route = destination.route,
            label = stringResource(id = destination.labelResId),
            icon = destination.icon
        )
    }

    val activeDestination = when {
        currentRoute.startsWith(FieldShiftTopLevelDestination.FARMS.route) ->
            FieldShiftTopLevelDestination.FARMS
        currentRoute.startsWith(FieldShiftTopLevelDestination.ANALYSIS.route) ->
            FieldShiftTopLevelDestination.ANALYSIS
        else -> FieldShiftTopLevelDestination.entries.firstOrNull {
            it.route == currentRoute
        } ?: FieldShiftTopLevelDestination.DASHBOARD
    }

    val statusBadge = when (sessionState) {
        is SessionState.GuestSession -> stringResource(id = R.string.profile_badge_guest)
        is SessionState.Authenticated -> stringResource(id = R.string.profile_badge_authenticated)
        else -> null
    }

    Scaffold(
        modifier = modifier.fillMaxSize(),
        containerColor = FieldShiftTheme.colorScheme.background,
        topBar = {
            FieldShiftTopBar(
                title = stringResource(id = activeDestination.titleResId),
                subtitle = stringResource(id = R.string.app_tagline),
                statusBadgeText = statusBadge,
                leadingIcon = Icons.Outlined.Eco
            )
        },
        bottomBar = {
            FieldShiftBottomBar(
                items = bottomNavItems,
                currentRoute = activeDestination.route,
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
                    when (destination) {
                        FieldShiftTopLevelDestination.FARMS -> {
                            FarmsListScreen(
                                viewModel = farmsListViewModel,
                                onCreateFarmClick = { navController.navigate(FarmRoutes.CREATE) },
                                onFarmClick = { farmId ->
                                    navController.navigate(FarmRoutes.detail(farmId))
                                }
                            )
                        }
                        FieldShiftTopLevelDestination.ANALYSIS -> {
                            val configViewModel: AnalysisConfigViewModel = hiltViewModel()
                            AnalysisConfigScreen(
                                language = selectedLanguage,
                                viewModel = configViewModel,
                                onJobQueued = { requestId ->
                                    navController.navigate(AnalysisRoutes.progress(requestId))
                                },
                                onResumeActiveRequest = { requestId ->
                                    navController.navigate(AnalysisRoutes.progress(requestId))
                                }
                            )
                        }
                        FieldShiftTopLevelDestination.PROFILE -> {
                            ProfileScreen(
                                selectedLanguage = selectedLanguage,
                                onLanguageSelected = onLanguageSelected
                            )
                        }
                        else -> {
                            FoundationSectionEmptyScreen(
                                destination = destination,
                                apiEndpointConfig = apiEndpointConfig,
                                selectedLanguage = selectedLanguage,
                                onLanguageSelected = onLanguageSelected
                            )
                        }
                    }
                }
            }

            composable(route = FarmRoutes.CREATE) {
                FarmFormScreen(
                    farmId = null,
                    onSaved = { farm ->
                        farmsListViewModel.onFarmSaved(farm)
                        navController.navigate(FarmRoutes.detail(farm.id)) {
                            popUpTo(FarmRoutes.CREATE) { inclusive = true }
                        }
                    },
                    onBack = { navController.popBackStack() }
                )
            }

            composable(
                route = FarmRoutes.DETAIL,
                arguments = listOf(navArgument(FarmRoutes.ARG_FARM_ID) { type = NavType.StringType })
            ) { backStackEntry ->
                val farmId = backStackEntry.arguments?.getString(FarmRoutes.ARG_FARM_ID)
                    .orEmpty()
                FarmDetailScreen(
                    farmId = farmId,
                    onViewFieldsClick = { id -> navController.navigate(FieldRoutes.list(id)) },
                    onEditClick = { id -> navController.navigate(FarmRoutes.edit(id)) },
                    onDeleted = { deletedId ->
                        farmsListViewModel.onFarmDeleted(deletedId)
                        navController.popBackStack()
                    },
                    onBack = { navController.popBackStack() }
                )
            }

            composable(
                route = FarmRoutes.EDIT,
                arguments = listOf(navArgument(FarmRoutes.ARG_FARM_ID) { type = NavType.StringType })
            ) { backStackEntry ->
                val farmId = backStackEntry.arguments?.getString(FarmRoutes.ARG_FARM_ID)
                    .orEmpty()
                FarmFormScreen(
                    farmId = farmId,
                    onSaved = { updatedFarm ->
                        farmsListViewModel.onFarmSaved(updatedFarm)
                        navController.navigate(FarmRoutes.detail(updatedFarm.id)) {
                            popUpTo(FarmRoutes.detail(updatedFarm.id)) { inclusive = true }
                        }
                    },
                    onBack = { navController.popBackStack() }
                )
            }

            composable(
                route = FieldRoutes.LIST,
                arguments = listOf(navArgument(FieldRoutes.ARG_FARM_ID) { type = NavType.StringType })
            ) { backStackEntry ->
                val farmId = backStackEntry.arguments?.getString(FieldRoutes.ARG_FARM_ID)
                    .orEmpty()
                FieldsListScreen(
                    farmId = farmId,
                    viewModel = fieldsListViewModel,
                    onBackClick = { navController.popBackStack() },
                    onFieldClick = { fieldId ->
                        navController.navigate(FieldRoutes.detail(farmId, fieldId))
                    },
                    onCreateFieldClick = {
                        navController.navigate(FieldRoutes.create(farmId))
                    }
                )
            }

            composable(
                route = FieldRoutes.CREATE,
                arguments = listOf(navArgument(FieldRoutes.ARG_FARM_ID) { type = NavType.StringType })
            ) { backStackEntry ->
                val farmId = backStackEntry.arguments?.getString(FieldRoutes.ARG_FARM_ID)
                    .orEmpty()
                val formViewModel: FieldFormViewModel = hiltViewModel()
                FieldFormScreen(
                    farmId = farmId,
                    fieldId = null,
                    viewModel = formViewModel,
                    onBackClick = { navController.popBackStack() },
                    onSaved = { saved ->
                        fieldsListViewModel.onFieldSaved(saved)
                        navController.navigate(FieldRoutes.detail(farmId, saved.fieldId)) {
                            popUpTo(FieldRoutes.create(farmId)) { inclusive = true }
                        }
                    }
                )
            }

            composable(
                route = FieldRoutes.DETAIL,
                arguments = listOf(
                    navArgument(FieldRoutes.ARG_FARM_ID) { type = NavType.StringType },
                    navArgument(FieldRoutes.ARG_FIELD_ID) { type = NavType.StringType }
                )
            ) { backStackEntry ->
                val farmId = backStackEntry.arguments?.getString(FieldRoutes.ARG_FARM_ID)
                    .orEmpty()
                val fieldId = backStackEntry.arguments?.getString(FieldRoutes.ARG_FIELD_ID)
                    .orEmpty()
                val detailViewModel: FieldDetailViewModel = hiltViewModel()
                FieldDetailScreen(
                    farmId = farmId,
                    fieldId = fieldId,
                    viewModel = detailViewModel,
                    onBackClick = { navController.popBackStack() },
                    onEditClick = {
                        navController.navigate(FieldRoutes.edit(farmId, fieldId))
                    },
                    onDeleted = { deletedId ->
                        fieldsListViewModel.onFieldDeleted(deletedId)
                        navController.popBackStack()
                    }
                )
            }

            composable(
                route = FieldRoutes.EDIT,
                arguments = listOf(
                    navArgument(FieldRoutes.ARG_FARM_ID) { type = NavType.StringType },
                    navArgument(FieldRoutes.ARG_FIELD_ID) { type = NavType.StringType }
                )
            ) { backStackEntry ->
                val farmId = backStackEntry.arguments?.getString(FieldRoutes.ARG_FARM_ID)
                    .orEmpty()
                val fieldId = backStackEntry.arguments?.getString(FieldRoutes.ARG_FIELD_ID)
                    .orEmpty()
                val formViewModel: FieldFormViewModel = hiltViewModel()
                FieldFormScreen(
                    farmId = farmId,
                    fieldId = fieldId,
                    viewModel = formViewModel,
                    onBackClick = { navController.popBackStack() },
                    onSaved = { saved ->
                        fieldsListViewModel.onFieldSaved(saved)
                        navController.navigate(FieldRoutes.detail(farmId, saved.fieldId)) {
                            popUpTo(FieldRoutes.detail(farmId, saved.fieldId)) { inclusive = true }
                        }
                    }
                )
            }

            composable(
                route = AnalysisRoutes.PROGRESS,
                arguments = listOf(navArgument(AnalysisRoutes.ARG_REQUEST_ID) { type = NavType.StringType })
            ) { backStackEntry ->
                val requestId = backStackEntry.arguments?.getString(AnalysisRoutes.ARG_REQUEST_ID)
                    .orEmpty()
                val progressViewModel: AnalysisProgressViewModel = hiltViewModel()
                AnalysisProgressScreen(
                    requestId = requestId,
                    viewModel = progressViewModel,
                    onBackClick = { navController.popBackStack() },
                    onResultReady = { analysisId ->
                        navController.navigate(AnalysisRoutes.result(analysisId)) {
                            popUpTo(AnalysisRoutes.progress(requestId)) { inclusive = true }
                        }
                    }
                )
            }

            composable(
                route = AnalysisRoutes.RESULT,
                arguments = listOf(navArgument(AnalysisRoutes.ARG_ANALYSIS_ID) { type = NavType.StringType })
            ) { backStackEntry ->
                val analysisId = backStackEntry.arguments?.getString(AnalysisRoutes.ARG_ANALYSIS_ID)
                    .orEmpty()
                val resultViewModel: AnalysisResultViewModel = hiltViewModel()
                AnalysisResultScreen(
                    analysisId = analysisId,
                    viewModel = resultViewModel,
                    onBackClick = { navController.popBackStack() }
                )
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
