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
 * Retrofit service for FieldShift Planner Farm Management endpoints
 * matching `docs/openapi-v3.2.yaml` (base path `/api/v1`).
 */
interface FarmApiService {

    @GET("farms")
    suspend fun listFarms(
        @Query("limit") limit: Int = 20,
        @Query("cursor") cursor: String? = null,
        @Query("country") country: String? = null,
        @Query("region") region: String? = null,
        @Query("search") search: String? = null
    ): FarmPageDto

    @POST("farms")
    suspend fun createFarm(
        @Body request: FarmWriteRequestDto
    ): FarmPublicDto

    @GET("farms/{farm_id}")
    suspend fun getFarm(
        @Path("farm_id") farmId: String
    ): FarmPublicDto

    @PUT("farms/{farm_id}")
    suspend fun replaceFarm(
        @Path("farm_id") farmId: String,
        @Body request: FarmWriteRequestDto
    ): FarmPublicDto

    @PATCH("farms/{farm_id}")
    suspend fun patchFarm(
        @Path("farm_id") farmId: String,
        @Body request: FarmPatchRequestDto
    ): FarmPublicDto

    @DELETE("farms/{farm_id}")
    suspend fun deleteFarm(
        @Path("farm_id") farmId: String
    ): Response<Unit>
}

