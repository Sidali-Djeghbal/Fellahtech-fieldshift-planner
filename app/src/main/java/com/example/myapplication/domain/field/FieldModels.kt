package com.example.myapplication.domain.field

import com.example.myapplication.domain.auth.WarningNotice

enum class SoilType(val apiValue: String) {
    SANDY("sandy"),
    CLAY("clay"),
    LOAMY("loamy"),
    SILTY("silty"),
    UNKNOWN("unknown");

    companion object {
        fun fromApi(value: String): SoilType =
            entries.firstOrNull { it.apiValue == value } ?: UNKNOWN
    }
}

enum class SoilSource(val apiValue: String) {
    FARMER("farmer"),
    UNKNOWN("unknown");

    companion object {
        fun fromApi(value: String): SoilSource =
            entries.firstOrNull { it.apiValue == value } ?: UNKNOWN
    }
}

enum class WaterAvailability(val apiValue: String) {
    ABUNDANT("abundant"),
    MODERATE("moderate"),
    LIMITED("limited"),
    VERY_LIMITED("very_limited"),
    RAINFED_ONLY("rainfed_only");

    companion object {
        fun fromApi(value: String): WaterAvailability =
            entries.firstOrNull { it.apiValue == value } ?: MODERATE
    }
}

enum class WaterSource(val apiValue: String) {
    RAINWATER("rainwater"),
    GROUNDWATER("groundwater"),
    WELL("well"),
    DAM_RESERVOIR("dam_reservoir"),
    IRRIGATION_NETWORK("irrigation_network"),
    OTHER("other"),
    UNKNOWN("unknown");

    companion object {
        fun fromApi(value: String): WaterSource =
            entries.firstOrNull { it.apiValue == value } ?: UNKNOWN
    }
}

enum class IrrigationSystem(val apiValue: String) {
    RAINFED("rainfed"),
    DRIP("drip"),
    SPRINKLER("sprinkler"),
    FLOOD("flood"),
    OTHER("other"),
    UNKNOWN("unknown");

    companion object {
        fun fromApi(value: String): IrrigationSystem =
            entries.firstOrNull { it.apiValue == value } ?: UNKNOWN
    }
}

enum class Season(val apiValue: String) {
    SPRING("spring"),
    SUMMER("summer"),
    AUTUMN("autumn"),
    WINTER("winter");

    companion object {
        fun fromApi(value: String): Season =
            entries.firstOrNull { it.apiValue == value } ?: SPRING
    }
}

data class FieldLocation(
    val latitude: Double,
    val longitude: Double
)

data class FieldSoil(
    val soilType: SoilType,
    val source: SoilSource = SoilSource.FARMER,
    val soilPh: Double? = null,
    val organicMatterPercent: Double? = null,
    val soilTestDate: String? = null
)

data class FieldWater(
    val availability: WaterAvailability,
    val source: WaterSource,
    val sourceOther: String? = null,
    val irrigationSystem: IrrigationSystem
)

data class CropHistoryEntry(
    val season: Season,
    val year: Int,
    val plantingMonth: Int? = null,
    val cropId: String? = null,
    val cropNameRaw: String? = null,
    val yieldTonsPerHectare: Double? = null,
    val notes: String? = null
)

data class FieldSummary(
    val farmId: String,
    val fieldId: String,
    val fieldName: String,
    val isUnverifiedDemoParcel: Boolean,
    val location: FieldLocation,
    val areaHectares: Double,
    val elevationM: Double?,
    val soil: FieldSoil,
    val water: FieldWater,
    val warnings: List<WarningNotice>
)

data class FieldDetail(
    val farmId: String,
    val fieldId: String,
    val fieldName: String,
    val isUnverifiedDemoParcel: Boolean,
    val location: FieldLocation,
    val areaHectares: Double,
    val elevationM: Double?,
    val soil: FieldSoil,
    val water: FieldWater,
    val cropHistory: List<CropHistoryEntry>,
    val warnings: List<WarningNotice>
)

data class FieldPage(
    val items: List<FieldSummary>,
    val nextCursor: String?,
    val hasMore: Boolean
)

data class FieldWriteInput(
    val fieldId: String,
    val fieldName: String,
    val isUnverifiedDemoParcel: Boolean = false,
    val location: FieldLocation,
    val areaHectares: Double,
    val elevationM: Double? = null,
    val soilType: SoilType,
    val soilPh: Double? = null,
    val organicMatterPercent: Double? = null,
    val soilTestDate: String? = null,
    val waterAvailability: WaterAvailability,
    val waterSource: WaterSource,
    val waterSourceOther: String? = null,
    val irrigationSystem: IrrigationSystem,
    val cropHistory: List<CropHistoryEntry>
)

sealed interface FieldError {
    val message: String

    data class Api(
        val httpStatus: Int,
        val errorCode: String?,
        override val message: String,
        val requestId: String? = null
    ) : FieldError {
        val isUnauthorized: Boolean
            get() = httpStatus == 401 || errorCode == "UNAUTHORIZED"

        val isNotFound: Boolean
            get() = httpStatus == 404 || errorCode == "NOT_FOUND"

        val isGuestLimitReached: Boolean
            get() = httpStatus == 403 && errorCode == "GUEST_LIMIT_REACHED"

        val isConflict: Boolean
            get() = httpStatus == 409 || errorCode == "CONFLICT"

        val isOutsideDemoBoundary: Boolean
            get() = httpStatus == 422 || errorCode == "OUTSIDE_DEMO_BOUNDARY"

        val isValidationError: Boolean
            get() = httpStatus == 400 || errorCode == "INVALID_INPUT"
    }

    data class Network(
        override val message: String
    ) : FieldError
}

sealed interface FieldResult<out T> {
    data class Success<T>(val data: T) : FieldResult<T>
    data class Failure(val error: FieldError) : FieldResult<Nothing>
}

