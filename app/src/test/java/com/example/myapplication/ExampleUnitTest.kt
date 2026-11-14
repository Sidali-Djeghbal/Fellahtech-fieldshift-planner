package com.example.myapplication

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.LayoutDirection
import com.example.myapplication.core.common.AppLanguage
import com.example.myapplication.core.common.UiState
import com.example.myapplication.core.designsystem.theme.FieldShiftPalette
import com.example.myapplication.core.location.CoordinatesFormatter
import com.example.myapplication.core.network.ApiEndpointConfig
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ExampleUnitTest {

    @Test
    fun apiEndpointConfig_normalizesTrailingSlash() {
        val withoutSlash = ApiEndpointConfig("http://10.0.2.2:8000/api/v1")
        assertTrue(withoutSlash.isConfigured)
        assertEquals("http://10.0.2.2:8000/api/v1/", withoutSlash.normalizedBaseUrl)

        val withSlash = ApiEndpointConfig("http://10.0.2.2:8000/api/v1/")
        assertEquals("http://10.0.2.2:8000/api/v1/", withSlash.normalizedBaseUrl)

        val emptyConfig = ApiEndpointConfig("   ")
        assertFalse(emptyConfig.isConfigured)
        assertEquals("", emptyConfig.normalizedBaseUrl)
    }

    @Test
    fun appLanguage_resolvesRtlAndLtrCorrectly() {
        assertEquals(LayoutDirection.Rtl, AppLanguage.fromLanguageTag("ar-DZ").layoutDirection)
        assertEquals(LayoutDirection.Ltr, AppLanguage.fromLanguageTag("fr-DZ").layoutDirection)
        assertEquals(LayoutDirection.Ltr, AppLanguage.fromLanguageTag("en-US").layoutDirection)
        assertEquals(AppLanguage.ENGLISH, AppLanguage.fromLanguageTag(null))
    }

    @Test
    fun coordinatesFormatter_preservesLtrIsolationAndHemispheres() {
        val formatted = CoordinatesFormatter.formatDecimal(36.7266, 3.4837)
        assertTrue(formatted.startsWith("\u2066"))
        assertTrue(formatted.endsWith("\u2069"))
        assertTrue(formatted.contains("36.7266° N · 3.4837° E"))
    }

    @Test
    fun fieldShiftPalette_matchesDesignMdSpecifications() {
        assertEquals(Color(0xFF0C1511), FieldShiftPalette.Surface)
        assertEquals(Color(0xFFEAB34D), FieldShiftPalette.PrimaryContainer)
        assertEquals(Color(0xFF66BB6A), FieldShiftPalette.FoliageGreenBright)
        assertEquals(Color(0xFF38BDF8), FieldShiftPalette.TelemetryCyan)
        assertEquals(Color(0xFFF97316), FieldShiftPalette.ErosionAlert)
    }

    @Test
    fun uiState_supportsAllRequiredStates() {
        val loading: UiState<String> = UiState.Loading
        val empty: UiState<String> = UiState.Empty
        val success: UiState<String> = UiState.Success(data = "ok", isRefreshing = true)
        val error: UiState<String> = UiState.Error(message = "Network error", code = 503)

        assertTrue(loading is UiState.Loading)
        assertTrue(empty is UiState.Empty)
        assertTrue((success as UiState.Success).isRefreshing)
        assertEquals(503, (error as UiState.Error).code)
    }
}
