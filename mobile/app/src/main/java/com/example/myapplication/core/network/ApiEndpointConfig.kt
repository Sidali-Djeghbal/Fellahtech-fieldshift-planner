package com.example.myapplication.core.network

/**
 * Holds the configurable FieldShift REST API base URL.
 *
 * Rules:
 * - Never hardcoded inside repository implementations.
 * - Sourced from `BuildConfig.API_BASE_URL` or local configuration override.
 * - Normalizes non-empty URLs to end with `/` for Retrofit compatibility.
 */
data class ApiEndpointConfig(
    val rawBaseUrl: String
) {
    val isConfigured: Boolean
        get() = rawBaseUrl.isNotBlank()

    val normalizedBaseUrl: String
        get() {
            val trimmed = rawBaseUrl.trim()
            if (trimmed.isEmpty()) return ""
            return if (trimmed.endsWith("/")) trimmed else "$trimmed/"
        }
}

