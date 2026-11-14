package com.example.myapplication.core.designsystem.component

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.Icon
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme

enum class AgronomicStatusTone {
    NominalFoliage,
    HarvestOchre,
    MoistureDeficitAlert,
    TelemetryCyan
}

/**
 * NDVI / Crop Status Chip from `docs/stitch/DESIGN.md`:
 * Pill container with 32dp height. Background `#131814` with dynamic 1dp border matching health status.
 */
@Composable
fun FieldShiftStatusChip(
    text: String,
    modifier: Modifier = Modifier,
    tone: AgronomicStatusTone = AgronomicStatusTone.NominalFoliage,
    showStatusDot: Boolean = true
) {
    val colors = FieldShiftTheme.colors
    val accentColor: Color = when (tone) {
        AgronomicStatusTone.NominalFoliage -> colors.foliageGreenBright
        AgronomicStatusTone.HarvestOchre -> colors.primaryAmberOchre
        AgronomicStatusTone.MoistureDeficitAlert -> colors.erosionAlert
        AgronomicStatusTone.TelemetryCyan -> colors.telemetryCyan
    }

    Surface(
        modifier = modifier.defaultMinSize(minHeight = FieldShiftTheme.spacing.chipHeight),
        shape = FieldShiftTheme.shapes.pill,
        color = colors.surfaceContainer,
        border = BorderStroke(1.dp, accentColor.copy(alpha = 0.45f))
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.Center
        ) {
            if (showStatusDot) {
                Box(
                    modifier = Modifier
                        .size(6.dp)
                        .background(accentColor, CircleShape)
                )
                Spacer(modifier = Modifier.width(6.dp))
            }
            Text(
                text = text,
                style = FieldShiftTheme.typography.labelSm,
                color = accentColor
            )
        }
    }
}

/**
 * Filter Chip from `docs/stitch/DESIGN.md`:
 * Pill shape with muted inactive border (`rgba(255, 255, 255, 0.08)`).
 * When selected, container fills with `rgba(234, 179, 77, 0.15)` with amber borders and check indicator.
 */
@Composable
fun FieldShiftFilterChip(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val colors = FieldShiftTheme.colors
    val containerColor = if (selected) colors.filterChipSelectedFill else colors.surfaceContainerHigh
    val borderColor = if (selected) colors.primaryAmberOchre else colors.surfaceBorder
    val contentColor = if (selected) colors.primaryAmberOchre else colors.textSecondary

    Surface(
        onClick = onClick,
        modifier = modifier.defaultMinSize(minHeight = FieldShiftTheme.spacing.chipHeight),
        shape = FieldShiftTheme.shapes.pill,
        color = containerColor,
        border = BorderStroke(1.dp, borderColor)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (selected) {
                Icon(
                    imageVector = Icons.Default.Check,
                    contentDescription = null,
                    tint = contentColor,
                    modifier = Modifier.size(14.dp)
                )
                Spacer(modifier = Modifier.width(6.dp))
            }
            Text(
                text = label,
                style = FieldShiftTheme.typography.labelMd,
                color = contentColor
            )
        }
    }
}

/**
 * Monospaced Coordinate Badge from `docs/stitch/DESIGN.md`:
 * Compact rectangular badge with 4dp corner radius.
 * Background `#0E1713` with 1dp border in `rgba(56, 189, 248, 0.30)`.
 * Typography: `Space Mono` 11sp in `#38BDF8`.
 */
@Composable
fun FieldShiftCoordinateBadge(
    coordinatesText: String,
    modifier: Modifier = Modifier,
    leadingIcon: ImageVector? = null
) {
    val colors = FieldShiftTheme.colors
    Surface(
        modifier = modifier,
        shape = FieldShiftTheme.shapes.coordinateBadge,
        color = colors.coordinateBadgeBackground,
        border = BorderStroke(1.dp, colors.coordinateBadgeBorder)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (leadingIcon != null) {
                Icon(
                    imageVector = leadingIcon,
                    contentDescription = null,
                    tint = colors.telemetryCyan,
                    modifier = Modifier.size(13.dp)
                )
                Spacer(modifier = Modifier.width(4.dp))
            }
            Text(
                text = coordinatesText,
                style = FieldShiftTheme.typography.labelMd,
                color = colors.telemetryCyan
            )
        }
    }
}

/**
 * Telemetry Card from `docs/stitch/DESIGN.md`:
 * Surface `#131814` with internal 1dp border in `rgba(255, 255, 255, 0.08)`.
 * Header houses the coordinate or parcel identifier in `label-sm` (`Space Mono`) with `#A3B3A7`.
 * Body displays large metric typography (`headline-md` / `headline-sm`) with spectral accent.
 */
@Composable
fun FieldShiftTelemetryCard(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    unit: String? = null,
    subtitle: String? = null,
    valueAccentColor: Color = FieldShiftTheme.colors.textPrimary,
    trailingIcon: ImageVector? = null,
    iconTint: Color = FieldShiftTheme.colors.foliageGreenBright
) {
    val colors = FieldShiftTheme.colors
    FieldShiftCard(
        modifier = modifier,
        contentPadding = PaddingValues(12.dp)
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                text = label.uppercase(),
                style = FieldShiftTheme.typography.labelSm,
                color = colors.textSecondary,
                modifier = Modifier.weight(1f, fill = false)
            )
            if (trailingIcon != null) {
                Spacer(modifier = Modifier.width(4.dp))
                Icon(
                    imageVector = trailingIcon,
                    contentDescription = null,
                    tint = iconTint,
                    modifier = Modifier.size(15.dp)
                )
            }
        }
        Row(
            verticalAlignment = Alignment.Bottom,
            modifier = Modifier.padding(top = 4.dp)
        ) {
            Text(
                text = value,
                style = FieldShiftTheme.typography.headlineSm,
                color = valueAccentColor
            )
            if (!unit.isNullOrBlank()) {
                Spacer(modifier = Modifier.width(4.dp))
                Text(
                    text = unit,
                    style = FieldShiftTheme.typography.labelSm,
                    color = colors.textSecondary
                )
            }
        }
        if (!subtitle.isNullOrBlank()) {
            Text(
                text = subtitle,
                style = FieldShiftTheme.typography.labelSm,
                color = colors.textSecondary,
                modifier = Modifier.padding(top = 2.dp)
            )
        }
    }
}

