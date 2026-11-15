package com.example.myapplication.core.designsystem.component

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme

enum class SensorAccentTone {
    FoliageGreen,
    TelemetryCyan,
    AmberOchre
}

/**
 * Primary Filled Button from `docs/stitch/DESIGN.md`:
 * Container in Amber-Ochre (`#EAB34D`), content in Deep Canvas (`#0B0F0C`) with bold Space Grotesk 14sp.
 * Minimum touch target height of 48dp.
 */
@Composable
fun FieldShiftPrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    leadingIcon: ImageVector? = null,
    trailingIcon: ImageVector? = null
) {
    val colors = FieldShiftTheme.colors
    Button(
        onClick = onClick,
        modifier = modifier.defaultMinSize(minHeight = FieldShiftTheme.spacing.minTouchTarget),
        enabled = enabled,
        shape = FieldShiftTheme.shapes.cardBase,
        colors = ButtonDefaults.buttonColors(
            containerColor = colors.primaryAmberOchre,
            contentColor = colors.surfaceCanvas,
            disabledContainerColor = colors.surfaceContainerHighest,
            disabledContentColor = colors.textTertiary
        ),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp)
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.Center
        ) {
            if (leadingIcon != null) {
                Icon(
                    imageVector = leadingIcon,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
            }
            Text(
                text = text,
                style = FieldShiftTheme.typography.headlineSm.copy(
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold
                )
            )
            if (trailingIcon != null) {
                Spacer(modifier = Modifier.width(8.dp))
                Icon(
                    imageVector = trailingIcon,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp)
                )
            }
        }
    }
}

/**
 * Secondary Outlined Button from `docs/stitch/DESIGN.md`:
 * Transparent fill with 1dp border (`rgba(255, 255, 255, 0.16)`), content in `#F4F7F4`.
 */
@Composable
fun FieldShiftOutlinedButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    leadingIcon: ImageVector? = null
) {
    val colors = FieldShiftTheme.colors
    OutlinedButton(
        onClick = onClick,
        modifier = modifier.defaultMinSize(minHeight = FieldShiftTheme.spacing.minTouchTarget),
        enabled = enabled,
        shape = FieldShiftTheme.shapes.cardBase,
        border = BorderStroke(1.dp, colors.outlinedButtonBorder),
        colors = ButtonDefaults.outlinedButtonColors(
            containerColor = Color.Transparent,
            contentColor = colors.textPrimary,
            disabledContentColor = colors.textTertiary
        ),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp)
    ) {
        if (leadingIcon != null) {
            Icon(
                imageVector = leadingIcon,
                contentDescription = null,
                modifier = Modifier.size(18.dp)
            )
            Spacer(modifier = Modifier.width(8.dp))
        }
        Text(
            text = text,
            style = FieldShiftTheme.typography.headlineSm.copy(fontSize = 14.sp)
        )
    }
}

/**
 * Tonal Sensor Trigger from `docs/stitch/DESIGN.md`:
 * Container `#1C241E`, leading icon tinted in Foliage Green (`#66BB6A`) or Telemetry Cyan (`#38BDF8`),
 * text in `#F4F7F4`.
 */
@Composable
fun FieldShiftTonalSensorButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    leadingIcon: ImageVector? = null,
    accentTone: SensorAccentTone = SensorAccentTone.TelemetryCyan,
    enabled: Boolean = true
) {
    val colors = FieldShiftTheme.colors
    val iconTint = when (accentTone) {
        SensorAccentTone.FoliageGreen -> colors.foliageGreenBright
        SensorAccentTone.TelemetryCyan -> colors.telemetryCyan
        SensorAccentTone.AmberOchre -> colors.primaryAmberOchre
    }

    Button(
        onClick = onClick,
        modifier = modifier.defaultMinSize(minHeight = 40.dp),
        enabled = enabled,
        shape = FieldShiftTheme.shapes.pill,
        border = BorderStroke(1.dp, colors.surfaceBorder),
        colors = ButtonDefaults.buttonColors(
            containerColor = colors.surfaceContainerHigh,
            contentColor = colors.textPrimary
        ),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp)
    ) {
        if (leadingIcon != null) {
            Icon(
                imageVector = leadingIcon,
                contentDescription = null,
                tint = iconTint,
                modifier = Modifier.size(18.dp)
            )
            Spacer(modifier = Modifier.width(8.dp))
        }
        Text(
            text = text,
            style = FieldShiftTheme.typography.labelMd,
            color = colors.textPrimary
        )
    }
}

