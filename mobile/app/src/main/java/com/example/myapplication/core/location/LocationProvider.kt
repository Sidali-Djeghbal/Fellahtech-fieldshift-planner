package com.example.myapplication.core.location

sealed interface GpsLocationResult {
    data class Success(
        val latitude: Double,
        val longitude: Double,
        val accuracyMeters: Float? = null
    ) : GpsLocationResult

    data object PermissionDenied : GpsLocationResult

    data object LocationUnavailable : GpsLocationResult

    data object Timeout : GpsLocationResult

    data class Error(val message: String) : GpsLocationResult
}

interface LocationProvider {
    fun hasLocationPermission(): Boolean
    suspend fun getCurrentCoordinates(): GpsLocationResult
}

