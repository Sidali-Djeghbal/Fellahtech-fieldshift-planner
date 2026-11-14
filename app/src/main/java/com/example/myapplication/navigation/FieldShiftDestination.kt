package com.example.myapplication.navigation

import androidx.annotation.StringRes
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Agriculture
import androidx.compose.material.icons.outlined.Dashboard
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.ManageAccounts
import androidx.compose.material.icons.outlined.Science
import androidx.compose.ui.graphics.vector.ImageVector
import com.example.myapplication.R

enum class FieldShiftTopLevelDestination(
    val route: String,
    @StringRes val labelResId: Int,
    @StringRes val titleResId: Int,
    val icon: ImageVector
) {
    DASHBOARD(
        route = "dashboard",
        labelResId = R.string.nav_home,
        titleResId = R.string.screen_title_dashboard,
        icon = Icons.Outlined.Dashboard
    ),
    FARMS(
        route = "farms",
        labelResId = R.string.nav_farms,
        titleResId = R.string.screen_title_farms,
        icon = Icons.Outlined.Agriculture
    ),
    ANALYSIS(
        route = "analysis",
        labelResId = R.string.nav_analysis,
        titleResId = R.string.screen_title_analysis,
        icon = Icons.Outlined.Science
    ),
    HISTORY(
        route = "history",
        labelResId = R.string.nav_history,
        titleResId = R.string.screen_title_history,
        icon = Icons.Outlined.History
    ),
    PROFILE(
        route = "profile",
        labelResId = R.string.nav_profile,
        titleResId = R.string.screen_title_profile,
        icon = Icons.Outlined.ManageAccounts
    )
}

object FarmRoutes {
    const val ARG_FARM_ID = "farmId"
    const val CREATE = "farms/create"
    const val DETAIL = "farms/detail/{$ARG_FARM_ID}"
    const val EDIT = "farms/edit/{$ARG_FARM_ID}"

    fun detail(farmId: String): String = "farms/detail/$farmId"
    fun edit(farmId: String): String = "farms/edit/$farmId"
}

object FieldRoutes {
    const val ARG_FARM_ID = "farmId"
    const val ARG_FIELD_ID = "fieldId"
    const val LIST = "farms/{$ARG_FARM_ID}/fields"
    const val CREATE = "farms/{$ARG_FARM_ID}/fields/create"
    const val DETAIL = "farms/{$ARG_FARM_ID}/fields/detail/{$ARG_FIELD_ID}"
    const val EDIT = "farms/{$ARG_FARM_ID}/fields/edit/{$ARG_FIELD_ID}"

    fun list(farmId: String): String = "farms/$farmId/fields"
    fun create(farmId: String): String = "farms/$farmId/fields/create"
    fun detail(farmId: String, fieldId: String): String = "farms/$farmId/fields/detail/$fieldId"
    fun edit(farmId: String, fieldId: String): String = "farms/$farmId/fields/edit/$fieldId"
}

