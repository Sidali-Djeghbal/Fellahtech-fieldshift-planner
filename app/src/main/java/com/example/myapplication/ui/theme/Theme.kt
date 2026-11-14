package com.example.myapplication.ui.theme

import androidx.compose.runtime.Composable
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme

@Composable
fun MyApplicationTheme(
    content: @Composable () -> Unit
) {
    FieldShiftTheme(content = content)
}
