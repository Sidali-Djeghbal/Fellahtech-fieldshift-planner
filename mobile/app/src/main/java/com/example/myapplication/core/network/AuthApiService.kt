package com.example.myapplication.core.network

import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query

/**
 * Retrofit service for FieldShift Planner Authentication and Demo endpoints
 * matching `docs/openapi-v3.2.yaml` (OpenAPI v3.2, base path `/api/v1`).
 */
interface AuthApiService {

    @POST("auth/guest")
    suspend fun startGuestSession(
        @Body request: GuestSessionStartRequestDto
    ): GuestSessionStartResponseDto

    @POST("auth/register")
    suspend fun register(
        @Body request: RegisterRequestDto
    ): RegisterResponseDto

    @POST("auth/login")
    suspend fun login(
        @Body request: LoginRequestDto
    ): TokenPairResponseDto

    @POST("auth/logout")
    suspend fun logout(
        @Body request: LogoutRequestDto? = null
    ): Response<Unit>

    @GET("auth/me")
    suspend fun getMe(): UserProfileDto

    @DELETE("auth/me")
    suspend fun deleteMe(): Response<Unit>

    @GET("demo/locations")
    suspend fun getDemoLocations(
        @Query("limit") limit: Int = 20,
        @Query("cursor") cursor: String? = null
    ): DemoLocationPageDto

    @GET("demo/session")
    suspend fun getDemoSession(): GuestSessionInfoDto

    @DELETE("demo/session")
    suspend fun deleteDemoSession(): Response<Unit>
}

/**
 * Dedicated unauthenticated Retrofit service for `POST /auth/refresh` so that
 * `TokenRefreshAuthenticator` can rotate tokens synchronously without triggering
 * recursive 401 interception.
 */
interface TokenRefreshApiService {

    @POST("auth/refresh")
    fun refreshTokenCall(
        @Body request: RefreshRequestDto
    ): retrofit2.Call<TokenPairResponseDto>
}

