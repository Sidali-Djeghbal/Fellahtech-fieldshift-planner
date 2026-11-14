package com.example.myapplication.core.designsystem.theme

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * 8dp structural grid and micro-increments from `docs/stitch/DESIGN.md`.
 */
@Immutable
data class FieldShiftSpacing(
    val spaceXs: Dp = 4.dp,
    val spaceSm: Dp = 8.dp,
    val gutterMobile: Dp = 12.dp,
    val gutter: Dp = 16.dp,
    val marginMobile: Dp = 16.dp,
    val margin: Dp = 20.dp,
    val marginTablet: Dp = 24.dp,
    val spaceMd: Dp = 16.dp,
    val spaceLg: Dp = 24.dp,
    val spaceXl: Dp = 32.dp,
    val minTouchTarget: Dp = 48.dp,
    val chipHeight: Dp = 32.dp,
    val bottomBarHeight: Dp = 64.dp,
    val topBarHeight: Dp = 64.dp
)

val LocalFieldShiftSpacing = staticCompositionLocalOf { FieldShiftSpacing() }

