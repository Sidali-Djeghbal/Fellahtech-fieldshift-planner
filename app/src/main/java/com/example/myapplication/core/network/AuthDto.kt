package com.example.myapplication.core.network

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class GuestSessionStartRequestDto(
    @SerialName("demo_location_id") val demoLocationId: Int
)

@Serializable
data class RegisterRequestDto(
    @SerialName("email") val email: String,
    @SerialName("password") val password: String,
    @SerialName("full_name") val fullName: String,
    @SerialName("preferred_lang") val preferredLang: String? = null
)

@Serializable
data class LoginRequestDto(
    @SerialName("email") val email: String,
    @SerialName("password") val password: String
)

@Serializable
data class RefreshRequestDto(
    @SerialName("refresh_token") val refreshToken: String
)

@Serializable
data class LogoutRequestDto(
    @SerialName("refresh_token") val refreshToken: String? = null
)

@Serializable
data class UserProfileDto(
    @SerialName("id") val id: Int,
    @SerialName("email") val email: String,
    @SerialName("full_name") val fullName: String,
    @SerialName("preferred_lang") val preferredLang: String,
    @SerialName("created_at") val createdAt: String
)

@Serializable
data class RegisterResponseDto(
    @SerialName("user") val user: UserProfileDto,
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    @SerialName("token_type") val tokenType: String,
    @SerialName("expires_in") val expiresIn: Int
)

@Serializable
data class TokenPairResponseDto(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    @SerialName("token_type") val tokenType: String,
    @SerialName("expires_in") val expiresIn: Int
)

@Serializable
data class DemoLocationSummaryDto(
    @SerialName("id") val id: Int,
    @SerialName("code") val code: String,
    @SerialName("name") val name: String,
    @SerialName("country") val country: String,
    @SerialName("region") val region: String
)

@Serializable
data class DemoLocationPageDto(
    @SerialName("items") val items: List<DemoLocationSummaryDto>,
    @SerialName("next_cursor") val nextCursor: String? = null,
    @SerialName("has_more") val hasMore: Boolean
)

@Serializable
data class GeoLocationPointDto(
    @SerialName("latitude") val latitude: Double,
    @SerialName("longitude") val longitude: Double
)

@Serializable
data class WarningNoticeDto(
    @SerialName("code") val code: String,
    @SerialName("message") val message: String,
    @SerialName("fields") val fields: List<String>? = null
)

@Serializable
data class DemoParcelPreviewDto(
    @SerialName("field_id") val fieldId: String,
    @SerialName("field_name") val fieldName: String,
    @SerialName("location") val location: GeoLocationPointDto,
    @SerialName("area_hectares") val areaHectares: Double,
    @SerialName("is_unverified_demo_parcel") val isUnverifiedDemoParcel: Boolean,
    @SerialName("warnings") val warnings: List<WarningNoticeDto>
)

@Serializable
data class GuestSessionStartResponseDto(
    @SerialName("guest_token") val guestToken: String,
    @SerialName("expires_at") val expiresAt: String,
    @SerialName("demo_location") val demoLocation: DemoLocationSummaryDto,
    @SerialName("demo_parcel") val demoParcel: DemoParcelPreviewDto
)

@Serializable
data class GuestSessionLimitsDto(
    @SerialName("max_farms") val maxFarms: Int,
    @SerialName("max_fields_per_farm") val maxFieldsPerFarm: Int,
    @SerialName("max_analyses") val maxAnalyses: Int,
    @SerialName("max_analysis_quarters") val maxAnalysisQuarters: Int
)

@Serializable
data class GuestSessionUsageDto(
    @SerialName("farms") val farms: Int,
    @SerialName("fields") val fields: Int,
    @SerialName("analysis_quarters") val analysisQuarters: Int,
    @SerialName("analyses") val analyses: Double
)

@Serializable
data class GuestSessionInfoDto(
    @SerialName("demo_location") val demoLocation: DemoLocationSummaryDto,
    @SerialName("demo_parcel") val demoParcel: DemoParcelPreviewDto,
    @SerialName("created_at") val createdAt: String,
    @SerialName("expires_at") val expiresAt: String,
    @SerialName("limits") val limits: GuestSessionLimitsDto,
    @SerialName("usage") val usage: GuestSessionUsageDto
)

@Serializable
data class ErrorDetailDto(
    @SerialName("code") val code: String,
    @SerialName("message") val message: String,
    @SerialName("details") val details: List<JsonObject> = emptyList(),
    @SerialName("request_id") val requestId: String? = null
)

@Serializable
data class ErrorEnvelopeDto(
    @SerialName("error") val error: ErrorDetailDto
)

