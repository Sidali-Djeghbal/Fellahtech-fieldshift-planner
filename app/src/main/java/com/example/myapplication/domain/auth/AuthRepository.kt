package com.example.myapplication.domain.auth

import com.example.myapplication.core.common.AppLanguage
import kotlinx.coroutines.flow.StateFlow

interface AuthRepository {
    val sessionState: StateFlow<SessionState>

    suspend fun restoreSession()
    suspend fun login(email: String, password: String): AuthResult<UserProfile>
    suspend fun register(
        email: String,
        password: String,
        fullName: String,
        preferredLanguage: AppLanguage?
    ): AuthResult<UserProfile>
    suspend fun fetchDemoLocations(limit: Int = 20, cursor: String? = null): AuthResult<List<DemoLocation>>
    suspend fun startGuestSession(demoLocationId: Int): AuthResult<GuestSessionInfo>
    suspend fun refreshGuestSessionInfo(): AuthResult<GuestSessionInfo>
    suspend fun logout(): AuthResult<Unit>
    suspend fun deleteAccount(): AuthResult<Unit>
    suspend fun exitGuestSession(): AuthResult<Unit>
    suspend fun clearSessionLocally()
}

