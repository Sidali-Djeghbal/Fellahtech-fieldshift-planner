package com.example.myapplication.core.designsystem.theme

import androidx.compose.material3.Typography
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp

/**
 * Typography system from `docs/stitch/DESIGN.md`:
 * - Headlines: Space Grotesk (display proportions for instrumentation)
 * - Body & Instructional Copy: Inter (neutral sans-serif for outdoor readability)
 * - Data, Coordinates & Telemetry: Space Mono (tabular alignment for GIS & sensors)
 */
val SpaceGroteskFontFamily: FontFamily = FontFamily.SansSerif
val InterFontFamily: FontFamily = FontFamily.SansSerif
val SpaceMonoFontFamily: FontFamily = FontFamily.Monospace

@Immutable
data class FieldShiftTypographyTokens(
    val headlineLg: TextStyle = TextStyle(
        fontFamily = SpaceGroteskFontFamily,
        fontWeight = FontWeight.Bold,
        fontSize = 32.sp,
        lineHeight = 40.sp,
        letterSpacing = (-0.02).em
    ),
    val headlineLgMobile: TextStyle = TextStyle(
        fontFamily = SpaceGroteskFontFamily,
        fontWeight = FontWeight.Bold,
        fontSize = 26.sp,
        lineHeight = 32.sp,
        letterSpacing = (-0.01).em
    ),
    val headlineMd: TextStyle = TextStyle(
        fontFamily = SpaceGroteskFontFamily,
        fontWeight = FontWeight.SemiBold,
        fontSize = 22.sp,
        lineHeight = 28.sp
    ),
    val headlineSm: TextStyle = TextStyle(
        fontFamily = SpaceGroteskFontFamily,
        fontWeight = FontWeight.SemiBold,
        fontSize = 18.sp,
        lineHeight = 24.sp
    ),
    val bodyLg: TextStyle = TextStyle(
        fontFamily = InterFontFamily,
        fontWeight = FontWeight.Normal,
        fontSize = 16.sp,
        lineHeight = 24.sp
    ),
    val bodyMd: TextStyle = TextStyle(
        fontFamily = InterFontFamily,
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        lineHeight = 20.sp
    ),
    val bodySm: TextStyle = TextStyle(
        fontFamily = InterFontFamily,
        fontWeight = FontWeight.Normal,
        fontSize = 12.sp,
        lineHeight = 16.sp
    ),
    val labelLg: TextStyle = TextStyle(
        fontFamily = SpaceMonoFontFamily,
        fontWeight = FontWeight.Medium,
        fontSize = 13.sp,
        lineHeight = 16.sp,
        letterSpacing = 0.02.em
    ),
    val labelMd: TextStyle = TextStyle(
        fontFamily = SpaceMonoFontFamily,
        fontWeight = FontWeight.Medium,
        fontSize = 11.sp,
        lineHeight = 14.sp,
        letterSpacing = 0.04.em
    ),
    val labelSm: TextStyle = TextStyle(
        fontFamily = SpaceMonoFontFamily,
        fontWeight = FontWeight.Normal,
        fontSize = 10.sp,
        lineHeight = 12.sp,
        letterSpacing = 0.06.em
    )
)

private val DefaultTokens = FieldShiftTypographyTokens()

val FieldShiftMaterialTypography = Typography(
    displayLarge = DefaultTokens.headlineLg,
    displayMedium = DefaultTokens.headlineLgMobile,
    headlineLarge = DefaultTokens.headlineLg,
    headlineMedium = DefaultTokens.headlineMd,
    headlineSmall = DefaultTokens.headlineSm,
    titleLarge = DefaultTokens.headlineMd,
    titleMedium = DefaultTokens.headlineSm,
    titleSmall = DefaultTokens.bodyLg.copy(fontWeight = FontWeight.SemiBold),
    bodyLarge = DefaultTokens.bodyLg,
    bodyMedium = DefaultTokens.bodyMd,
    bodySmall = DefaultTokens.bodySm,
    labelLarge = DefaultTokens.labelLg,
    labelMedium = DefaultTokens.labelMd,
    labelSmall = DefaultTokens.labelSm
)

val LocalFieldShiftTypography = staticCompositionLocalOf { DefaultTokens }

