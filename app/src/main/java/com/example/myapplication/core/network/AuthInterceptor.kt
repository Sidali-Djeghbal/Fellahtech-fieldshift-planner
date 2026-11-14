package com.example.myapplication.core.network

import javax.inject.Inject
import javax.inject.Singleton
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.Response

/**
 * Injects the appropriate authentication header per `docs/openapi-v3.2.yaml` security declarations:
 * - Validates that request origin matches the configured API base URL before attaching credentials.
 * - Never transmits credentials to untrusted origins or third-party hosts.
 * - Unauthenticated endpoints (`/auth/login`, `/auth/register`, `/auth/refresh`, `/auth/guest`, `/demo/locations`):
 *   no credential header added.
 * - Guest-only endpoints (`/demo/session`): `X-Guest-Token`.
 * - Registered-only endpoints (`/auth/me`, `/auth/logout`): `Authorization: Bearer <access_token>`.
 * - Shared resource endpoints (farms, fields, analysis, etc. in later phases): prefers Bearer if present,
 *   otherwise falls back to `X-Guest-Token`.
 */
@Singleton
class AuthInterceptor @Inject constructor(
    private val credentialStore: CredentialStore,
    private val endpointConfig: ApiEndpointConfig
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()

        // Enforce origin validation: never send credentials to an unrelated host, scheme, or port.
        if (!isTargetOrigin(original.url)) {
            return chain.proceed(original)
        }

        val path = original.url.encodedPath

        if (isPublicPath(path)) {
            return chain.proceed(original)
        }

        val builder = original.newBuilder()

        when {
            isGuestOnlyPath(path) -> {
                credentialStore.getGuestToken()?.let { guestToken ->
                    builder.header(HEADER_GUEST_TOKEN, guestToken)
                }
            }
            isBearerOnlyPath(path) -> {
                credentialStore.getAccessToken()?.let { accessToken ->
                    builder.header(HEADER_AUTHORIZATION, "Bearer $accessToken")
                }
            }
            else -> {
                val accessToken = credentialStore.getAccessToken()
                val guestToken = credentialStore.getGuestToken()
                when {
                    !accessToken.isNullOrBlank() -> {
                        builder.header(HEADER_AUTHORIZATION, "Bearer $accessToken")
                    }
                    !guestToken.isNullOrBlank() -> {
                        builder.header(HEADER_GUEST_TOKEN, guestToken)
                    }
                }
            }
        }

        return chain.proceed(builder.build())
    }

    private fun isTargetOrigin(requestUrl: HttpUrl): Boolean {
        val configuredBase = endpointConfig.normalizedBaseUrl
            .takeIf { it.isNotBlank() }
            ?.toHttpUrlOrNull() ?: return false

        return requestUrl.scheme.equals(configuredBase.scheme, ignoreCase = true) &&
            requestUrl.host.equals(configuredBase.host, ignoreCase = true) &&
            requestUrl.port == configuredBase.port
    }

    private fun isPublicPath(path: String): Boolean {
        return path.endsWith("/auth/login") ||
            path.endsWith("/auth/register") ||
            path.endsWith("/auth/refresh") ||
            path.endsWith("/auth/guest") ||
            path.contains("/demo/locations")
    }

    private fun isGuestOnlyPath(path: String): Boolean {
        return path.endsWith("/demo/session")
    }

    private fun isBearerOnlyPath(path: String): Boolean {
        return path.endsWith("/auth/me") || path.endsWith("/auth/logout")
    }

    companion object {
        const val HEADER_AUTHORIZATION = "Authorization"
        const val HEADER_GUEST_TOKEN = "X-Guest-Token"
    }
}

