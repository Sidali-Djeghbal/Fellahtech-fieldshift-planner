package com.example.myapplication.core.network

/**
 * Abstraction over persisted credentials used by OkHttp interceptors and authenticators.
 * Lives in `core/network` so network infrastructure does not depend on Android Keystore directly
 * and can be unit-tested with an in-memory implementation.
 */
interface CredentialStore {
    fun getAccessToken(): String?
    fun getRefreshToken(): String?
    fun getGuestToken(): String?

    suspend fun saveBearerTokens(accessToken: String, refreshToken: String, expiresInSeconds: Int)
    suspend fun saveGuestToken(guestToken: String, expiresAtIso: String)
    suspend fun clearBearerTokens()
    suspend fun clearGuestToken()
    suspend fun clearAll()
}

