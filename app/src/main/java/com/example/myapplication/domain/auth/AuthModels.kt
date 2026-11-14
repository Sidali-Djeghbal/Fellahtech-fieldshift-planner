package com.example.myapplication.domain.auth

import com.example.myapplication.core.common.AppLanguage
import com.example.myapplication.core.network.ApiCallFailure

data class UserProfile(
    val id: Int,
    val email: String,
    val fullName: String,
    val preferredLanguage: AppLanguage,
    val createdAt: String
)

data class DemoLocation(
    val id: Int,
    val code: String,
    val name: String,
    val country: String,
    val region: String
)

data class WarningNotice(
    val code: String,
    val message: String,
    val fields: List<String>
)

data class DemoParcel(
    val fieldId: String,
    val fieldName: String,
    val latitude: Double,
    val longitude: Double,
    val areaHectares: Double,
    val isUnverifiedDemoParcel: Boolean,
    val warnings: List<WarningNotice>
)

data class GuestSessionLimits(
    val maxFarms: Int,
    val maxFieldsPerFarm: Int,
    val maxAnalyses: Int,
    val maxAnalysisQuarters: Int
)

data class GuestSessionUsage(
    val farms: Int,
    val fields: Int,
    val analysisQuarters: Int,
    val analyses: Double
)

data class GuestSessionInfo(
    val demoLocation: DemoLocation,
    val demoParcel: DemoParcel,
    val createdAt: String?,
    val expiresAt: String,
    val limits: GuestSessionLimits?,
    val usage: GuestSessionUsage?
)

/**
 * Single source of truth for the application's authentication and guest session lifecycle.
 */
sealed interface SessionState {
    data object Initializing : SessionState
    data object Unauthenticated : SessionState
    data class Authenticated(val user: UserProfile) : SessionState
    data class GuestSession(val info: GuestSessionInfo) : SessionState
    data class RecoverableError(val message: String) : SessionState
}

sealed interface AuthResult<out T> {
    data class Success<T>(val data: T) : AuthResult<T>
    data class Failure(val failure: ApiCallFailure) : AuthResult<Nothing>
}

