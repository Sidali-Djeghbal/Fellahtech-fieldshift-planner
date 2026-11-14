package com.example.myapplication.core.designsystem.component

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme

data class FieldShiftBottomNavItem(
    val route: String,
    val label: String,
    val icon: ImageVector
)

/**
 * Top App Bar matching Stitch screens (`Dashboard`, `Analysis Configuration`, `Parcel Detail`).
 */
@Composable
fun FieldShiftTopBar(
    title: String,
    modifier: Modifier = Modifier,
    subtitle: String? = null,
    statusBadgeText: String? = null,
    leadingIcon: ImageVector? = null,
    onLeadingClick: (() -> Unit)? = null,
    actions: @Composable RowScope.() -> Unit = {}
) {
    val colors = FieldShiftTheme.colors
    Surface(
        modifier = modifier.fillMaxWidth(),
        color = FieldShiftTheme.colorScheme.surface.copy(alpha = 0.92f)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .windowInsetsPadding(WindowInsets.statusBars)
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(FieldShiftTheme.spacing.topBarHeight)
                    .padding(horizontal = FieldShiftTheme.spacing.marginMobile),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.weight(1f)
                ) {
                    if (leadingIcon != null) {
                        if (onLeadingClick != null) {
                            IconButton(onClick = onLeadingClick) {
                                Icon(
                                    imageVector = leadingIcon,
                                    contentDescription = null,
                                    tint = colors.textPrimary
                                )
                            }
                        } else {
                            Box(
                                modifier = Modifier
                                    .size(40.dp)
                                    .clip(FieldShiftTheme.shapes.cardBase)
                                    .background(colors.surfaceContainerHigh),
                                contentAlignment = Alignment.Center
                            ) {
                                Icon(
                                    imageVector = leadingIcon,
                                    contentDescription = null,
                                    tint = colors.primaryAmberOchre,
                                    modifier = Modifier.size(22.dp)
                                )
                            }
                            Spacer(modifier = Modifier.width(FieldShiftTheme.spacing.spaceSm))
                        }
                    }
                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = title,
                                style = FieldShiftTheme.typography.headlineSm,
                                color = colors.textPrimary
                            )
                            if (!statusBadgeText.isNullOrBlank()) {
                                Spacer(modifier = Modifier.width(6.dp))
                                FieldShiftStatusChip(
                                    text = statusBadgeText,
                                    tone = AgronomicStatusTone.NominalFoliage
                                )
                            }
                        }
                        if (!subtitle.isNullOrBlank()) {
                            Text(
                                text = subtitle,
                                style = FieldShiftTheme.typography.labelSm,
                                color = colors.textTertiary
                            )
                        }
                    }
                }
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    content = actions
                )
            }
            HorizontalDivider(
                thickness = 1.dp,
                color = colors.bottomNavTopDivider
            )
        }
    }
}

/**
 * Bottom Navigation Bar from `docs/stitch/DESIGN.md`:
 * - Anchored to bottom with background `#0B0F0C` elevated via a top divider of `1dp` solid `rgba(255, 255, 255, 0.06)`.
 * - Active item indicator: Horizontal pill capsule in `rgba(234, 179, 77, 0.18)` containing the active icon colored in `#EAB34D`.
 * - Inactive items rendered in `#65776A` with typography in `label-sm`.
 */
@Composable
fun FieldShiftBottomBar(
    items: List<FieldShiftBottomNavItem>,
    currentRoute: String?,
    onItemSelected: (FieldShiftBottomNavItem) -> Unit,
    modifier: Modifier = Modifier
) {
    val colors = FieldShiftTheme.colors
    Surface(
        modifier = modifier.fillMaxWidth(),
        color = colors.surfaceCanvas
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .windowInsetsPadding(WindowInsets.navigationBars)
        ) {
            HorizontalDivider(
                thickness = 1.dp,
                color = colors.bottomNavTopDivider
            )
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(FieldShiftTheme.spacing.bottomBarHeight)
                    .padding(horizontal = FieldShiftTheme.spacing.spaceXs),
                horizontalArrangement = Arrangement.SpaceAround,
                verticalAlignment = Alignment.CenterVertically
            ) {
                items.forEach { item ->
                    val isSelected = item.route == currentRoute
                    val iconTint = if (isSelected) colors.primaryAmberOchre else colors.textTertiary
                    val labelColor = if (isSelected) colors.textPrimary else colors.textTertiary

                    Column(
                        modifier = Modifier
                            .defaultMinSize(minWidth = 56.dp, minHeight = 44.dp)
                            .clip(FieldShiftTheme.shapes.cardBase)
                            .clickable { onItemSelected(item) }
                            .padding(vertical = 4.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        Box(
                            modifier = Modifier
                                .clip(FieldShiftTheme.shapes.pill)
                                .background(
                                    if (isSelected) colors.bottomNavActivePill else Color.Transparent
                                )
                                .padding(horizontal = 16.dp, vertical = 4.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                imageVector = item.icon,
                                contentDescription = item.label,
                                tint = iconTint,
                                modifier = Modifier.size(22.dp)
                            )
                        }
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = item.label,
                            style = FieldShiftTheme.typography.labelSm.copy(
                                fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Normal
                            ),
                            color = labelColor
                        )
                    }
                }
            }
        }
    }
}

