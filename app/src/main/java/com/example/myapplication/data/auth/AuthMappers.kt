package com.example.myapplication.data.auth

import com.example.myapplication.core.common.AppLanguage
import com.example.myapplication.core.network.DemoLocationSummaryDto
import com.example.myapplication.core.network.DemoParcelPreviewDto
import com.example.myapplication.core.network.GuestSessionInfoDto
import com.example.myapplication.core.network.GuestSessionLimitsDto
import com.example.myapplication.core.network.GuestSessionStartResponseDto
import com.example.myapplication.core.network.GuestSessionUsageDto
import com.example.myapplication.core.network.UserProfileDto
import com.example.myapplication.core.network.WarningNoticeDto
import com.example.myapplication.domain.auth.DemoLocation
import com.example.myapplication.domain.auth.DemoParcel
import com.example.myapplication.domain.auth.GuestSessionInfo
import com.example.myapplication.domain.auth.GuestSessionLimits
import com.example.myapplication.domain.auth.GuestSessionUsage
import com.example.myapplication.domain.auth.UserProfile
import com.example.myapplication.domain.auth.WarningNotice

fun UserProfileDto.toDomain(): UserProfile {
    return UserProfile(
        id = id,
        email = email,
        fullName = fullName,
        preferredLanguage = AppLanguage.fromLanguageTag(preferredLang),
        createdAt = createdAt
    )
}

fun DemoLocationSummaryDto.toDomain(): DemoLocation {
    return DemoLocation(
        id = id,
        code = code,
        name = name,
        country = country,
        region = region
    )
}

fun WarningNoticeDto.toDomain(): WarningNotice {
    return WarningNotice(
        code = code,
        message = message,
        fields = fields.orEmpty()
    )
}

fun DemoParcelPreviewDto.toDomain(): DemoParcel {
    return DemoParcel(
        fieldId = fieldId,
        fieldName = fieldName,
        latitude = location.latitude,
        longitude = location.longitude,
        areaHectares = areaHectares,
        isUnverifiedDemoParcel = isUnverifiedDemoParcel,
        warnings = warnings.map { it.toDomain() }
    )
}

fun GuestSessionStartResponseDto.toDomain(): GuestSessionInfo {
    return GuestSessionInfo(
        demoLocation = demoLocation.toDomain(),
        demoParcel = demoParcel.toDomain(),
        createdAt = null,
        expiresAt = expiresAt,
        limits = null,
        usage = null
    )
}

fun GuestSessionLimitsDto.toDomain(): GuestSessionLimits {
    return GuestSessionLimits(
        maxFarms = maxFarms,
        maxFieldsPerFarm = maxFieldsPerFarm,
        maxAnalyses = maxAnalyses,
        maxAnalysisQuarters = maxAnalysisQuarters
    )
}

fun GuestSessionUsageDto.toDomain(): GuestSessionUsage {
    return GuestSessionUsage(
        farms = farms,
        fields = fields,
        analysisQuarters = analysisQuarters,
        analyses = analyses
    )
}

fun GuestSessionInfoDto.toDomain(): GuestSessionInfo {
    return GuestSessionInfo(
        demoLocation = demoLocation.toDomain(),
        demoParcel = demoParcel.toDomain(),
        createdAt = createdAt,
        expiresAt = expiresAt,
        limits = limits.toDomain(),
        usage = usage.toDomain()
    )
}

