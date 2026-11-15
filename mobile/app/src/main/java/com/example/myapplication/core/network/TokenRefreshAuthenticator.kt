package com.example.myapplication.core.network

import javax.inject.Inject
import javax.inject.Provider
import javax.inject.Singleton
import kotlinx.coroutines.runBlocking
import okhttp3.Authenticator
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route

/**
 * Handles `401 Unauthorized` responses for Bearer-authenticated requests by rotating the
 * refresh token via `POST /api/v1/auth/refresh`.
 *
 * Safeguards:
 * - Synchronized via `refreshLock` so concurrent 401s perform only one refresh call.
 * - Compares the failed request's Bearer token with the currently stored access token so
 *   queued 401s reuse the newly refreshed token instead of refreshing again.
 * - Limits retries via [HEADER_REFRESH_ATTEMPT] so an infinite refresh loop is impossible.
 * - Clears Bearer credentials ONLY when refresh fails with an HTTP 401/4xx rejection,
 *   never on transient `IOException` network errors.
 */
@Singleton
class TokenRefreshAuthenticator @Inject constructor(
    private val credentialStore: CredentialStore,
    private val refreshApiProvider: Provider<TokenRefreshApiService>
) : Authenticator {

    private val refreshLock = Any()

    override fun authenticate(route: Route?, response: Response): Request? {
        val request = response.request
        val path = request.url.encodedPath

        // Never attempt Bearer refresh for public endpoints, /auth/refresh itself, or guest-only requests.
        if (path.endsWith("/auth/login") ||
            path.endsWith("/auth/register") ||
            path.endsWith("/auth/refresh") ||
            path.endsWith("/auth/guest") ||
            path.endsWith("/demo/session") ||
            request.header(AuthInterceptor.HEADER_GUEST_TOKEN) != null
        ) {
            return null
        }

        // Prevent infinite loops if a retried request still receives 401.
        if (request.header(HEADER_REFRESH_ATTEMPT) != null) {
            return null
        }

        val failedBearerHeader = request.header(AuthInterceptor.HEADER_AUTHORIZATION) ?: return null
        val failedAccessToken = failedBearerHeader.removePrefix("Bearer ").trim()

        synchronized(refreshLock) {
            val latestAccessToken = credentialStore.getAccessToken()
            // Another concurrent request already rotated the token; retry with the new token.
            if (!latestAccessToken.isNullOrBlank() && latestAccessToken != failedAccessToken) {
                return request.newBuilder()
                    .header(AuthInterceptor.HEADER_AUTHORIZATION, "Bearer $latestAccessToken")
                    .header(HEADER_REFRESH_ATTEMPT, "1")
                    .build()
            }

            val refreshToken = credentialStore.getRefreshToken()
            if (refreshToken.isNullOrBlank()) {
                return null
            }

            return try {
                val refreshResponse = refreshApiProvider.get()
                    .refreshTokenCall(RefreshRequestDto(refreshToken = refreshToken))
                    .execute()

                if (refreshResponse.isSuccessful) {
                    val body = refreshResponse.body() ?: return null
                    runBlocking {
                        credentialStore.saveBearerTokens(
                            accessToken = body.accessToken,
                            refreshToken = body.refreshToken,
                            expiresInSeconds = body.expiresIn
                        )
                    }
                    request.newBuilder()
                        .header(AuthInterceptor.HEADER_AUTHORIZATION, "Bearer ${body.accessToken}")
                        .header(HEADER_REFRESH_ATTEMPT, "1")
                        .build()
                } else {
                    if (refreshResponse.code() == 401 || refreshResponse.code() == 400) {
                        runBlocking {
                            credentialStore.clearBearerTokens()
                        }
                    }
                    null
                }
            } catch (_: Exception) {
                // Network or IO failure: do NOT clear credentials; caller handles recoverable network error.
                null
            }
        }
    }

    private companion object {
        const val HEADER_REFRESH_ATTEMPT = "X-FieldShift-Refresh-Attempt"
    }
}

