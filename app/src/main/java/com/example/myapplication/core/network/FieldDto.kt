package com.example.myapplication.core.network

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class FieldLocationDto(
    @SerialName("latitude") val latitude: Double,
    @SerialName("longitude") val longitude: Double,
    @SerialName("boundary") val boundary: JsonObject? = null
)

@Serializable
data class FieldSoilWriteDto(
    @SerialName("soil_type") val soilType: String,
    @SerialName("soil_ph") val soilPh: Double? = null,
    @SerialName("organic_matter_percent") val organicMatterPercent: Double? = null,
    @SerialName("soil_test_date") val soilTestDate: String? = null
)

@Serializable
data class FieldSoilPublicDto(
    @SerialName("soil_type") val soilType: String,
    @SerialName("source") val source: String,
    @SerialName("soil_ph") val soilPh: Double? = null,
    @SerialName("organic_matter_percent") val organicMatterPercent: Double? = null,
    @SerialName("soil_test_date") val soilTestDate: String? = null
)

@Serializable
data class FieldWaterDto(
    @SerialName("availability") val availability: String,
    @SerialName("source") val source: String,
    @SerialName("source_other") val sourceOther: String? = null,
    @SerialName("irrigation_system") val irrigationSystem: String
)

@Serializable
data class CropHistoryWriteItemDto(
    @SerialName("season") val season: String,
    @SerialName("year") val year: Int,
    @SerialName("planting_month") val plantingMonth: Int? = null,
    @SerialName("crop_id") val cropId: String? = null,
    @SerialName("crop_name_raw") val cropNameRaw: String? = null,
    @SerialName("yield_tons_per_hectare") val yieldTonsPerHectare: Double? = null,
    @SerialName("notes") val notes: String? = null
)

@Serializable
data class FieldWriteRequestDto(
    @SerialName("field_id") val fieldId: String,
    @SerialName("field_name") val fieldName: String,
    @SerialName("is_unverified_demo_parcel") val isUnverifiedDemoParcel: Boolean = false,
    @SerialName("location") val location: FieldLocationDto,
    @SerialName("area_hectares") val areaHectares: Double,
    @SerialName("elevation_m") val elevationM: Double? = null,
    @SerialName("soil") val soil: FieldSoilWriteDto,
    @SerialName("water") val water: FieldWaterDto,
    @SerialName("crop_history") val cropHistory: List<CropHistoryWriteItemDto>
)

@Serializable
data class FieldPatchRequestDto(
    @SerialName("field_name") val fieldName: String? = null,
    @SerialName("is_unverified_demo_parcel") val isUnverifiedDemoParcel: Boolean? = null,
    @SerialName("location") val location: FieldLocationDto? = null,
    @SerialName("area_hectares") val areaHectares: Double? = null,
    @SerialName("elevation_m") val elevationM: Double? = null,
    @SerialName("soil") val soil: FieldSoilWriteDto? = null,
    @SerialName("water") val water: FieldWaterDto? = null,
    @SerialName("crop_history") val cropHistory: List<CropHistoryWriteItemDto>? = null
)

@Serializable
data class FieldPublicDto(
    @SerialName("farm_id") val farmId: String,
    @SerialName("field_id") val fieldId: String,
    @SerialName("field_name") val fieldName: String,
    @SerialName("is_unverified_demo_parcel") val isUnverifiedDemoParcel: Boolean,
    @SerialName("location") val location: FieldLocationDto,
    @SerialName("area_hectares") val areaHectares: Double,
    @SerialName("elevation_m") val elevationM: Double? = null,
    @SerialName("soil") val soil: FieldSoilPublicDto,
    @SerialName("water") val water: FieldWaterDto,
    @SerialName("warnings") val warnings: List<WarningNoticeDto> = emptyList()
)

@Serializable
data class FieldDetailPublicDto(
    @SerialName("farm_id") val farmId: String,
    @SerialName("field_id") val fieldId: String,
    @SerialName("field_name") val fieldName: String,
    @SerialName("is_unverified_demo_parcel") val isUnverifiedDemoParcel: Boolean,
    @SerialName("location") val location: FieldLocationDto,
    @SerialName("area_hectares") val areaHectares: Double,
    @SerialName("elevation_m") val elevationM: Double? = null,
    @SerialName("soil") val soil: FieldSoilPublicDto,
    @SerialName("water") val water: FieldWaterDto,
    @SerialName("crop_history") val cropHistory: List<CropHistoryWriteItemDto>,
    @SerialName("warnings") val warnings: List<WarningNoticeDto> = emptyList()
)

@Serializable
data class FieldPageDto(
    @SerialName("items") val items: List<FieldPublicDto>,
    @SerialName("next_cursor") val nextCursor: String? = null,
    @SerialName("has_more") val hasMore: Boolean
)

