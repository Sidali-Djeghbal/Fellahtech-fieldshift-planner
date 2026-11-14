package com.example.myapplication.core.designsystem.theme

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

/**
 * Authoritative palette for the "FieldShift Earth Observation" design system
 * from `docs/stitch/DESIGN.md`.
 */
object FieldShiftPalette {
    // M3 Surface & Canvas Tiers
    val Surface = Color(0xFF0C1511)
    val SurfaceDim = Color(0xFF0C1511)
    val SurfaceBright = Color(0xFF323B36)
    val SurfaceContainerLowest = Color(0xFF07100C)
    val SurfaceContainerLow = Color(0xFF141D19)
    val SurfaceContainer = Color(0xFF131814)
    val SurfaceContainerM3 = Color(0xFF18221D)
    val SurfaceContainerHigh = Color(0xFF1C241E)
    val SurfaceContainerHighM3 = Color(0xFF232C27)
    val SurfaceContainerHighest = Color(0xFF2D3732)
    val SurfaceVariant = Color(0xFF2D3732)
    val SurfaceCanvas = Color(0xFF0B0F0C)

    // On-Surface & Text Hierarchy
    val OnSurface = Color(0xFFDBE5DE)
    val OnSurfaceVariant = Color(0xFFD3C4B0)
    val InverseSurface = Color(0xFFDBE5DE)
    val InverseOnSurface = Color(0xFF29322E)
    val TextPrimary = Color(0xFFF4F7F4)
    val TextSecondary = Color(0xFFA3B3A7)
    val TextTertiary = Color(0xFF65776A)

    // Outlines & Structural Borders
    val Outline = Color(0xFF9C8F7D)
    val OutlineVariant = Color(0xFF4F4536)
    val SurfaceBorder = Color(0x14FFFFFF) // rgba(255, 255, 255, 0.08)
    val SurfaceBorderElevated = Color(0x1FFFFFFF) // rgba(255, 255, 255, 0.12)
    val OutlinedButtonBorder = Color(0x29FFFFFF) // rgba(255, 255, 255, 0.16)
    val SurfaceBorderActiveAmber = Color(0x40EAB34D) // rgba(234, 179, 77, 0.25)
    val SpectralGlowAmber = Color(0x33EAB34D) // rgba(234, 179, 77, 0.20)
    val BottomNavTopDivider = Color(0x0FFFFFFF) // rgba(255, 255, 255, 0.06)
    val BottomNavActivePill = Color(0x2EEAB34D) // rgba(234, 179, 77, 0.18)
    val FilterChipSelectedFill = Color(0x26EAB34D) // rgba(234, 179, 77, 0.15)
    val CoordinateBadgeBackground = Color(0xFF0E1713)
    val CoordinateBadgeBorder = Color(0x4D38BDF8) // rgba(56, 189, 248, 0.30)

    // Primary — Amber-Ochre Harvest Tone
    val SurfaceTint = Color(0xFFF5BD56)
    val Primary = Color(0xFFFFD183)
    val OnPrimary = Color(0xFF422C00)
    val PrimaryContainer = Color(0xFFEAB34D)
    val OnPrimaryContainer = Color(0xFF654600)
    val InversePrimary = Color(0xFF7D5700)
    val PrimaryFixed = Color(0xFFFFDEAA)
    val PrimaryFixedDim = Color(0xFFF5BD56)
    val OnPrimaryFixed = Color(0xFF271900)
    val OnPrimaryFixedVariant = Color(0xFF5F4100)

    // Secondary — Crop Foliage Green
    val Secondary = Color(0xFF78DC77)
    val OnSecondary = Color(0xFF00390A)
    val SecondaryContainer = Color(0xFF00761F)
    val OnSecondaryContainer = Color(0xFF95FB92)
    val SecondaryFixed = Color(0xFF94F990)
    val SecondaryFixedDim = Color(0xFF78DC77)
    val OnSecondaryFixed = Color(0xFF002204)
    val OnSecondaryFixedVariant = Color(0xFF005313)
    val FoliageGreenBright = Color(0xFF66BB6A)
    val FoliageGreenDeep = Color(0xFF4D5432)

    // Tertiary — Radar Hydrology / Telemetry Cyan
    val Tertiary = Color(0xFFAADEFF)
    val OnTertiary = Color(0xFF00354A)
    val TertiaryContainer = Color(0xFF56C7FF)
    val OnTertiaryContainer = Color(0xFF00516F)
    val TertiaryFixed = Color(0xFFC4E7FF)
    val TertiaryFixedDim = Color(0xFF7BD0FF)
    val OnTertiaryFixed = Color(0xFF001E2C)
    val OnTertiaryFixedVariant = Color(0xFF004C69)
    val TelemetryCyan = Color(0xFF38BDF8)
    val SpectralDeepSea = Color(0xFF183A41)

    // Alert / Degradation & Error
    val ErosionAlert = Color(0xFFF97316)
    val Error = Color(0xFFFFB4AB)
    val OnError = Color(0xFF690005)
    val ErrorContainer = Color(0xFF93000A)
    val OnErrorContainer = Color(0xFFFFDAD6)

    // Background
    val Background = Color(0xFF0C1511)
    val OnBackground = Color(0xFFDBE5DE)
}

val FieldShiftDarkColorScheme: ColorScheme = darkColorScheme(
    primary = FieldShiftPalette.Primary,
    onPrimary = FieldShiftPalette.OnPrimary,
    primaryContainer = FieldShiftPalette.PrimaryContainer,
    onPrimaryContainer = FieldShiftPalette.OnPrimaryContainer,
    inversePrimary = FieldShiftPalette.InversePrimary,
    secondary = FieldShiftPalette.Secondary,
    onSecondary = FieldShiftPalette.OnSecondary,
    secondaryContainer = FieldShiftPalette.SecondaryContainer,
    onSecondaryContainer = FieldShiftPalette.OnSecondaryContainer,
    tertiary = FieldShiftPalette.Tertiary,
    onTertiary = FieldShiftPalette.OnTertiary,
    tertiaryContainer = FieldShiftPalette.TertiaryContainer,
    onTertiaryContainer = FieldShiftPalette.OnTertiaryContainer,
    background = FieldShiftPalette.Background,
    onBackground = FieldShiftPalette.OnBackground,
    surface = FieldShiftPalette.Surface,
    onSurface = FieldShiftPalette.OnSurface,
    surfaceVariant = FieldShiftPalette.SurfaceVariant,
    onSurfaceVariant = FieldShiftPalette.OnSurfaceVariant,
    surfaceTint = FieldShiftPalette.SurfaceTint,
    inverseSurface = FieldShiftPalette.InverseSurface,
    inverseOnSurface = FieldShiftPalette.InverseOnSurface,
    error = FieldShiftPalette.Error,
    onError = FieldShiftPalette.OnError,
    errorContainer = FieldShiftPalette.ErrorContainer,
    onErrorContainer = FieldShiftPalette.OnErrorContainer,
    outline = FieldShiftPalette.Outline,
    outlineVariant = FieldShiftPalette.OutlineVariant,
    surfaceBright = FieldShiftPalette.SurfaceBright,
    surfaceDim = FieldShiftPalette.SurfaceDim,
    surfaceContainer = FieldShiftPalette.SurfaceContainer,
    surfaceContainerHigh = FieldShiftPalette.SurfaceContainerHigh,
    surfaceContainerHighest = FieldShiftPalette.SurfaceContainerHighest,
    surfaceContainerLow = FieldShiftPalette.SurfaceContainerLow,
    surfaceContainerLowest = FieldShiftPalette.SurfaceContainerLowest
)

@Immutable
data class FieldShiftExtendedColors(
    val surfaceCanvas: Color = FieldShiftPalette.SurfaceCanvas,
    val surfaceContainer: Color = FieldShiftPalette.SurfaceContainer,
    val surfaceContainerLow: Color = FieldShiftPalette.SurfaceContainerLow,
    val surfaceContainerHigh: Color = FieldShiftPalette.SurfaceContainerHigh,
    val surfaceContainerHighest: Color = FieldShiftPalette.SurfaceContainerHighest,
    val surfaceBorder: Color = FieldShiftPalette.SurfaceBorder,
    val surfaceBorderElevated: Color = FieldShiftPalette.SurfaceBorderElevated,
    val outlinedButtonBorder: Color = FieldShiftPalette.OutlinedButtonBorder,
    val surfaceBorderActiveAmber: Color = FieldShiftPalette.SurfaceBorderActiveAmber,
    val spectralGlowAmber: Color = FieldShiftPalette.SpectralGlowAmber,
    val bottomNavTopDivider: Color = FieldShiftPalette.BottomNavTopDivider,
    val bottomNavActivePill: Color = FieldShiftPalette.BottomNavActivePill,
    val filterChipSelectedFill: Color = FieldShiftPalette.FilterChipSelectedFill,
    val coordinateBadgeBackground: Color = FieldShiftPalette.CoordinateBadgeBackground,
    val coordinateBadgeBorder: Color = FieldShiftPalette.CoordinateBadgeBorder,
    val primaryAmberOchre: Color = FieldShiftPalette.PrimaryContainer,
    val foliageGreenBright: Color = FieldShiftPalette.FoliageGreenBright,
    val foliageGreenDeep: Color = FieldShiftPalette.FoliageGreenDeep,
    val telemetryCyan: Color = FieldShiftPalette.TelemetryCyan,
    val erosionAlert: Color = FieldShiftPalette.ErosionAlert,
    val spectralDeepSea: Color = FieldShiftPalette.SpectralDeepSea,
    val textPrimary: Color = FieldShiftPalette.TextPrimary,
    val textSecondary: Color = FieldShiftPalette.TextSecondary,
    val textTertiary: Color = FieldShiftPalette.TextTertiary
)

val LocalFieldShiftColors = staticCompositionLocalOf { FieldShiftExtendedColors() }

