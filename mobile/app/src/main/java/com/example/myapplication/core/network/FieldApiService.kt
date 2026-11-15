package com.example.myapplication.core.network

import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Retrofit service for FieldShift Planner Field Management endpoints
 * matching `docs/openapi-v3.2.yaml` (base path `/api/v1`).
 */
interface FieldApiService {

    @GET("farms/{farm_id}/fields")
    suspend fun listFields(
        @Path("farm_id") farmId: String,
        @Query("limit") limit: Int = 20,
        @Query("cursor") cursor: String? = null,
        @Query("soil_type") soilType: String? = null,
        @Query("water_availability") waterAvailability: String? = null
    ): FieldPageDto

    @POST("farms/{farm_id}/fields")
    suspend fun createField(
        @Path("farm_id") farmId: String,
        @Body request: FieldWriteRequestDto
    ): FieldPublicDto

    @GET("farms/{farm_id}/fields/{field_id}")
    suspend fun getField(
        @Path("farm_id") farmId: String,
        @Path("field_id") fieldId: String
    ): FieldDetailPublicDto

    @PUT("farms/{farm_id}/fields/{field_id}")
    suspend fun replaceField(
        @Path("farm_id") farmId: String,
        @Path("field_id") fieldId: String,
        @Body request: FieldWriteRequestDto
    ): FieldDetailPublicDto

    @PATCH("farms/{farm_id}/fields/{field_id}")
    suspend fun patchField(
        @Path("farm_id") farmId: String,
        @Path("field_id") fieldId: String,
        @Body request: FieldPatchRequestDto
    ): FieldDetailPublicDto

    @DELETE("farms/{farm_id}/fields/{field_id}")
    suspend fun deleteField(
        @Path("farm_id") farmId: String,
        @Path("field_id") fieldId: String
    ): Response<Unit>
}

