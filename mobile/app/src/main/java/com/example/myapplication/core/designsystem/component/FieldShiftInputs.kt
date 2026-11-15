package com.example.myapplication.core.designsystem.component

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.VisualTransformation
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme

/**
 * Input Field from `docs/stitch/DESIGN.md`:
 * Filled container style using `#1C241E`. Bottom active indicator line in `#EAB34D`.
 * Floating label rendered in `body-sm` (`Inter`).
 * Input text rendered in `#F4F7F4`, placeholder text in `#65776A`.
 */
@Composable
fun FieldShiftTextField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    placeholder: String? = null,
    singleLine: Boolean = true,
    enabled: Boolean = true,
    isError: Boolean = false,
    visualTransformation: VisualTransformation = VisualTransformation.None,
    keyboardOptions: KeyboardOptions = KeyboardOptions.Default,
    keyboardActions: KeyboardActions = KeyboardActions.Default,
    leadingIcon: @Composable (() -> Unit)? = null,
    trailingIcon: @Composable (() -> Unit)? = null
) {
    val colors = FieldShiftTheme.colors
    TextField(
        value = value,
        onValueChange = onValueChange,
        modifier = modifier.fillMaxWidth(),
        enabled = enabled,
        singleLine = singleLine,
        isError = isError,
        textStyle = FieldShiftTheme.typography.bodyMd.copy(color = colors.textPrimary),
        label = {
            Text(
                text = label,
                style = FieldShiftTheme.typography.bodySm
            )
        },
        placeholder = placeholder?.let {
            {
                Text(
                    text = it,
                    style = FieldShiftTheme.typography.bodyMd,
                    color = colors.textTertiary
                )
            }
        },
        leadingIcon = leadingIcon,
        trailingIcon = trailingIcon,
        visualTransformation = visualTransformation,
        keyboardOptions = keyboardOptions,
        keyboardActions = keyboardActions,
        shape = FieldShiftTheme.shapes.cardBase,
        colors = TextFieldDefaults.colors(
            focusedContainerColor = colors.surfaceContainerHigh,
            unfocusedContainerColor = colors.surfaceContainerHigh,
            disabledContainerColor = colors.surfaceContainerLow,
            errorContainerColor = colors.surfaceContainerHigh,
            focusedIndicatorColor = colors.primaryAmberOchre,
            unfocusedIndicatorColor = colors.surfaceBorder,
            disabledIndicatorColor = Color.Transparent,
            errorIndicatorColor = FieldShiftTheme.colorScheme.error,
            focusedLabelColor = colors.primaryAmberOchre,
            unfocusedLabelColor = colors.textSecondary,
            focusedTextColor = colors.textPrimary,
            unfocusedTextColor = colors.textPrimary,
            cursorColor = colors.primaryAmberOchre
        )
    )
}

