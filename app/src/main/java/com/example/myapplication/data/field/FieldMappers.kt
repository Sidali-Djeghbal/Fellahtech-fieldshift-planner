package com.example.myapplication.data.field

import com.example.myapplication.core.network.ApiCallFailure
import com.example.myapplication.core.network.CropHistoryWriteItemDto
import com.example.myapplication.core.network.FieldDetailPublicDto
import com.example.myapplication.core.network.FieldLocationDto
import com.example.myapplication.core.network.FieldPageDto
import com.example.myapplication.core.network.FieldPublicDto
import com.example.myapplication.core.network.FieldSoilPublicDto
import com.example.myapplication.core.network.FieldSoilWriteDto
import com.example.myapplication.core.network.FieldWaterDto
import com.example.myapplication.core.network.FieldWriteRequestDto
import com.example.myapplication.data.auth.toDomain
import com.example.myapplication.domain.field.CropHistoryEntry
import com.example.myapplication.domain.field.FieldDetail
import com.example.myapplication.domain.field.FieldError
import com.example.myapplication.domain.field.FieldLocation
import com.example.myapplication.domain.field.FieldPage
import com.example.myapplication.domain.field.FieldSoil
import com.example.myapplication.domain.field.FieldSummary
import com.example.myapplication.domain.field.FieldWater
import com.example.myapplication.domain.field.FieldWriteInput
import com.example.myapplication.domain.field.IrrigationSystem
import com.example.myapplication.domain.field.Season
import com.example.myapplication.domain.field.SoilSource
import com.example.myapplication.domain.field.SoilType
import com.example.myapplication.domain.field.WaterAvailability
import com.example.myapplication.domain.field.WaterSource

fun FieldLocationDto.toDomain(): FieldLocation =
    FieldLocation(latitude = latitude, longitude = longitude)

fun FieldSoilPublicDto.toDomain(): FieldSoil = FieldSoil(
    soilType = SoilType.fromApi(soilType),
    source = SoilSource.fromApi(source),
    soilPh = soilPh,
    organicMatterPercent = organicMatterPercent,
    soilTestDate = soilTestDate
)

fun FieldWaterDto.toDomain(): FieldWater = FieldWater(
    availability = WaterAvailability.fromApi(availability),
    source = WaterSource.fromApi(source),
    sourceOther = sourceOther,
    irrigationSystem = IrrigationSystem.fromApi(irrigationSystem)
)

fun CropHistoryWriteItemDto.toDomain(): CropHistoryEntry = CropHistoryEntry(
    season = Season.fromApi(season),
    year = year,
    plantingMonth = plantingMonth,
    cropId = cropId,
    cropNameRaw = cropNameRaw,
    yieldTonsPerHectare = yieldTonsPerHectare,
    notes = notes
)

fun FieldPublicDto.toDomain(): FieldSummary = FieldSummary(
    farmId = farmId,
    fieldId = fieldId,
    fieldName = fieldName,
    isUnverifiedDemoParcel = isUnverifiedDemoParcel,
    location = location.toDomain(),
    areaHectares = areaHectares,
    elevationM = elevationM,
    soil = soil.toDomain(),
    water = water.toDomain(),
    warnings = warnings.map { it.toDomain() }
)

fun FieldDetailPublicDto.toDomain(): FieldDetail = FieldDetail(
    farmId = farmId,
    fieldId = fieldId,
    fieldName = fieldName,
    isUnverifiedDemoParcel = isUnverifiedDemoParcel,
    location = location.toDomain(),
    areaHectares = areaHectares,
    elevationM = elevationM,
    soil = soil.toDomain(),
    water = water.toDomain(),
    cropHistory = cropHistory.map { it.toDomain() },
    warnings = warnings.map { it.toDomain() }
)

fun FieldDetail.toSummary(): FieldSummary = FieldSummary(
    farmId = farmId,
    fieldId = fieldId,
    fieldName = fieldName,
    isUnverifiedDemoParcel = isUnverifiedDemoParcel,
    location = location,
    areaHectares = areaHectares,
    elevationM = elevationM,
    soil = soil,
    water = water,
    warnings = warnings
)

fun FieldPageDto.toDomain(): FieldPage = FieldPage(
    items = items.map { it.toDomain() },
    nextCursor = nextCursor,
    hasMore = hasMore
)

fun CropHistoryEntry.toDto(): CropHistoryWriteItemDto = CropHistoryWriteItemDto(
    season = season.apiValue,
    year = year,
    plantingMonth = plantingMonth,
    cropId = cropId?.trim()?.takeIf { it.isNotEmpty() },
    cropNameRaw = cropNameRaw?.trim()?.takeIf { it.isNotEmpty() },
    yieldTonsPerHectare = yieldTonsPerHectare,
    notes = notes?.trim()?.takeIf { it.isNotEmpty() }
)

fun FieldWriteInput.toWriteRequestDto(): FieldWriteRequestDto = FieldWriteRequestDto(
    fieldId = fieldId.trim(),
    fieldName = fieldName.trim(),
    isUnverifiedDemoParcel = isUnverifiedDemoParcel,
    location = FieldLocationDto(
        latitude = location.latitude,
        longitude = location.longitude,
        boundary = null
    ),
    areaHectares = areaHectares,
    elevationM = elevationM,
    soil = FieldSoilWriteDto(
        soilType = soilType.apiValue,
        soilPh = soilPh,
        organicMatterPercent = organicMatterPercent,
        soilTestDate = soilTestDate?.trim()?.takeIf { it.isNotEmpty() }
    ),
    water = FieldWaterDto(
        availability = waterAvailability.apiValue,
        source = waterSource.apiValue,
        sourceOther = waterSourceOther?.trim()?.takeIf { it.isNotEmpty() },
        irrigationSystem = irrigationSystem.apiValue
    ),
    cropHistory = cropHistory.map { it.toDto() }
)

fun ApiCallFailure.toFieldError(): FieldError = when (this) {
    is ApiCallFailure.ApiError -> FieldError.Api(
        httpStatus = httpStatus,
        errorCode = errorCode,
        message = message,
        requestId = requestId
    )
    is ApiCallFailure.NetworkError -> FieldError.Network(message = message)
}

