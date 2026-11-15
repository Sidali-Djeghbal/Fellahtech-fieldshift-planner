package com.example.myapplication.core.designsystem.theme

import android.app.Activity
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

/**
 * Root theme for FieldShift Planner ("FieldShift Earth Observation" design system).
 * Always uses the high-contrast dark agronomic palette defined in `docs/stitch/DESIGN.md`.
 */
@Composable
fun FieldShiftTheme(
    content: @Composable () -> Unit
) {
    val extendedColors = FieldShiftExtendedColors()
    val typographyTokens = FieldShiftTypographyTokens()
    val shapeTokens = FieldShiftShapeTokens()
    val spacingTokens = FieldShiftSpacing()

    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as? Activity)?.window
            if (window != null) {
                val insetsController = WindowCompat.getInsetsController(window, view)
                insetsController.isAppearanceLightStatusBars = false
                insetsController.isAppearanceLightNavigationBars = false
            }
        }
    }

    CompositionLocalProvider(
        LocalFieldShiftColors provides extendedColors,
        LocalFieldShiftTypography provides typographyTokens,
        LocalFieldShiftShapes provides shapeTokens,
        LocalFieldShiftSpacing provides spacingTokens
    ) {
        MaterialTheme(
            colorScheme = FieldShiftDarkColorScheme,
            typography = FieldShiftMaterialTypography,
            shapes = FieldShiftMaterialShapes,
            content = content
        )
    }
}

object FieldShiftTheme {
    val colors: FieldShiftExtendedColors
        @Composable
        @ReadOnlyComposable
        get() = LocalFieldShiftColors.current

    val colorScheme: ColorScheme
        @Composable
        @ReadOnlyComposable
        get() = MaterialTheme.colorScheme

    val typography: FieldShiftTypographyTokens
        @Composable
        @ReadOnlyComposable
        get() = LocalFieldShiftTypography.current

    val shapes: FieldShiftShapeTokens
        @Composable
        @ReadOnlyComposable
        get() = LocalFieldShiftShapes.current

    val spacing: FieldShiftSpacing
        @Composable
        @ReadOnlyComposable
        get() = LocalFieldShiftSpacing.current
}

