package com.example.myapplication.core.location

import java.util.Locale
import kotlin.math.abs

/**
 * Formats geospatial coordinates for `FieldShiftCoordinateBadge` using tabular ASCII digits.
 * Wraps output in Unicode Left-to-Right Isolate (`\u2066...\u2069`) so coordinates remain
 * strictly LTR even when the surrounding UI layout is in Arabic (RTL).
 */
object CoordinatesFormatter {
    private const val LRI = '\u2066'
    private const val PDI = '\u2069'

    fun formatDecimal(latitude: Double, longitude: Double): String {
        val latHemisphere = if (latitude >= 0.0) "N" else "S"
        val lonHemisphere = if (longitude >= 0.0) "E" else "W"
        val formatted = String.format(
            Locale.US,
            "%.4f° %s · %.4f° %s",
            abs(latitude),
            latHemisphere,
            abs(longitude),
            lonHemisphere
        )
        return "$LRI$formatted$PDI"
    }
}

