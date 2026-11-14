package com.example.myapplication.core.network

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Request body for `POST /api/v1/farms` and `PUT /api/v1/farms/{farm_id}`
 * matching `FarmWriteRequest` in `docs/openapi-v3.2.yaml`.
 */
@Serializable
data class FarmWriteRequestDto(
    @SerialName("farm_name") val farmName: String,
    @SerialName("country") val country: String,
    @SerialName("region") val region: String,
    @SerialName("commune") val commune: String? = null
)

/**
 * Request body for `PATCH /api/v1/farms/{farm_id}`
 * matching `FarmPatchRequest` in `docs/openapi-v3.2.yaml`.
 */
@Serializable
data class FarmPatchRequestDto(
    @SerialName("farm_name") val farmName: String? = null,
    @SerialName("country") val country: String? = null,
    @SerialName("region") val region: String? = null,
    @SerialName("commune") val commune: String? = null
)

/**
 * Farm representation returned by `/api/v1/farms` endpoints
 * matching `FarmPublic` in `docs/openapi-v3.2.yaml`.
 */
@Serializable
data class FarmPublicDto(
    @SerialName("farm_id") val farmId: String,
    @SerialName("farm_name") val farmName: String,
    @SerialName("country") val country: String,
    @SerialName("region") val region: String,
    @SerialName("commune") val commune: String? = null,
    @SerialName("field_count") val fieldCount: Int,
    @SerialName("created_at") val createdAt: String
)

/**
 * Cursor-paginated list of farms matching `FarmPage` in `docs/openapi-v3.2.yaml`.
 */
@Serializable
data class FarmPageDto(
    @SerialName("items") val items: List<FarmPublicDto>,
    @SerialName("next_cursor") val nextCursor: String? = null,
    @SerialName("has_more") val hasMore: Boolean
)

