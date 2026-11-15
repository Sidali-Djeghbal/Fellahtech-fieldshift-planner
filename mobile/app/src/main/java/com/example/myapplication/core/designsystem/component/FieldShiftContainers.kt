package com.example.myapplication.core.designsystem.component

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.unit.dp
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme

/**
 * Container Level 1 (`#131814`) with a 1dp structural border (`rgba(255, 255, 255, 0.08)`),
 * or Container Level 2 (`#1C241E`) when [elevated] or [active] is true, matching `docs/stitch/DESIGN.md`.
 */
@Composable
fun FieldShiftCard(
    modifier: Modifier = Modifier,
    elevated: Boolean = false,
    active: Boolean = false,
    shape: Shape = if (elevated) FieldShiftTheme.shapes.cardElevated else FieldShiftTheme.shapes.cardBase,
    contentPadding: PaddingValues = PaddingValues(FieldShiftTheme.spacing.spaceMd),
    onClick: (() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit
) {
    val colors = FieldShiftTheme.colors
    val containerColor: Color = when {
        elevated || active -> colors.surfaceContainerHigh
        else -> colors.surfaceContainer
    }
    val borderColor: Color = when {
        active -> colors.surfaceBorderActiveAmber
        elevated -> colors.surfaceBorderElevated
        else -> colors.surfaceBorder
    }

    if (onClick != null) {
        Surface(
            onClick = onClick,
            modifier = modifier,
            shape = shape,
            color = containerColor,
            contentColor = colors.textPrimary,
            border = BorderStroke(1.dp, borderColor)
        ) {
            Column(
                modifier = Modifier.padding(contentPadding),
                content = content
            )
        }
    } else {
        Surface(
            modifier = modifier,
            shape = shape,
            color = containerColor,
            contentColor = colors.textPrimary,
            border = BorderStroke(1.dp, borderColor)
        ) {
            Column(
                modifier = Modifier.padding(contentPadding),
                content = content
            )
        }
    }
}

