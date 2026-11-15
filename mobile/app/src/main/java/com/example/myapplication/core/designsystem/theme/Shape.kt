package com.example.myapplication.core.designsystem.theme

import androidx.compose.foundation.shape.CornerBasedShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.unit.dp

/**
 * Shape system from `docs/stitch/DESIGN.md`:
 * - sm / Coordinate Badges: 4.dp (0.25rem)
 * - DEFAULT / Base Cards, Buttons, Inputs: 8.dp (0.5rem)
 * - md / Elevated Modules: 12.dp (0.75rem)
 * - lg / Modal Sheets & Overlays: 16.dp (1rem)
 * - xl: 24.dp (1.5rem)
 * - full / Interactive Badges & Agronomic Stat Chips: 9999.dp pill
 */
@Immutable
data class FieldShiftShapeTokens(
    val coordinateBadge: CornerBasedShape = RoundedCornerShape(4.dp),
    val cardBase: CornerBasedShape = RoundedCornerShape(8.dp),
    val cardElevated: CornerBasedShape = RoundedCornerShape(12.dp),
    val modalSheet: CornerBasedShape = RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp),
    val largeOverlay: CornerBasedShape = RoundedCornerShape(16.dp),
    val extraLarge: CornerBasedShape = RoundedCornerShape(24.dp),
    val pill: CornerBasedShape = RoundedCornerShape(percent = 50)
)

val FieldShiftMaterialShapes = Shapes(
    extraSmall = RoundedCornerShape(4.dp),
    small = RoundedCornerShape(8.dp),
    medium = RoundedCornerShape(12.dp),
    large = RoundedCornerShape(16.dp),
    extraLarge = RoundedCornerShape(24.dp)
)

val LocalFieldShiftShapes = staticCompositionLocalOf { FieldShiftShapeTokens() }

