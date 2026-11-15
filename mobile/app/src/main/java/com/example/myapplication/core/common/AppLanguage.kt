package com.example.myapplication.core.common

import androidx.compose.ui.unit.LayoutDirection
import java.util.Locale

/**
 * Supported application locales for FieldShift Planner (English, French, Arabic)
 * with explicit RTL layout direction metadata.
 */
enum class AppLanguage(
    val languageTag: String,
    val displayName: String,
    val layoutDirection: LayoutDirection
) {
    ENGLISH(
        languageTag = "en",
        displayName = "English",
        layoutDirection = LayoutDirection.Ltr
    ),
    FRENCH(
        languageTag = "fr",
        displayName = "Français",
        layoutDirection = LayoutDirection.Ltr
    ),
    ARABIC(
        languageTag = "ar",
        displayName = "العربية",
        layoutDirection = LayoutDirection.Rtl
    );

    companion object {
        fun fromLanguageTag(tag: String?): AppLanguage {
            val normalized = tag?.lowercase(Locale.ROOT)?.substringBefore('-')
            return entries.firstOrNull { it.languageTag == normalized } ?: ENGLISH
        }
    }
}

