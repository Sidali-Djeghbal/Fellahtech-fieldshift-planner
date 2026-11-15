package com.example.myapplication.data.auth

import com.example.myapplication.core.common.AppLanguage
import com.example.myapplication.core.network.ApiCallFailure
import com.example.myapplication.core.network.ApiErrorParser
import com.example.myapplication.core.network.AuthApiService
import com.example.myapplication.core.network.CredentialStore
import com.example.myapplication.core.network.GuestSessionStartRequestDto
import com.example.myapplication.core.network.LoginRequestDto
import com.example.myapplication.core.network.LogoutRequestDto
import com.example.myapplication.core.network.RegisterRequestDto
import com.example.myapplication.core.security.SecureSessionStore
import com.example.myapplication.domain.auth.AuthRepository
import com.example.myapplication.domain.auth.AuthResult
import com.example.myapplication.domain.auth.DemoLocation
import com.example.myapplication.domain.auth.GuestSessionInfo
import com.example.myapplication.domain.auth.SessionState
import com.example.myapplication.domain.auth.UserProfile
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

@Singleton
class AuthRepositoryImpl @Inject constructor(
    private val authApiService: AuthApiService,
    private val credentialStore: CredentialStore,
    private val errorParser: ApiErrorParser
) : AuthRepository {

    private val _sessionState = MutableStateFlow<SessionState>(SessionState.Initializing)
    override val sessionState: StateFlow<SessionState> = _sessionState.asStateFlow()

    private val restoreMutex = Mutex()

    override suspend fun restoreSession() {
        restoreMutex.withLock {
            _sessionState.value = SessionState.Initializing
            if (credentialStore is SecureSessionStore) {
                credentialStore.warmUp()
            }

            val accessToken = credentialStore.getAccessToken()
            val refreshToken = credentialStore.getRefreshToken()
            val guestToken = credentialStore.getGuestToken()

            when {
                !accessToken.isNullOrBlank() || !refreshToken.isNullOrBlank() -> {
                    restoreBearerSession()
                }
                !guestToken.isNullOrBlank() -> {
                    restoreGuestSession()
                }
                else -> {
                    _sessionState.value = SessionState.Unauthenticated
                }
            }
        }
    }

    private suspend fun restoreBearerSession() {
        try {
            val profile = authApiService.getMe().toDomain()
            _sessionState.value = SessionState.Authenticated(profile)
        } catch (ce: CancellationException) {
            throw ce
        } catch (t: Throwable) {
            when (val failure = errorParser.toFailure(t)) {
                is ApiCallFailure.ApiError -> {
                    if (failure.httpStatus == 401) {
                        credentialStore.clearBearerTokens()
                        _sessionState.value = SessionState.Unauthenticated
                    } else {
                        _sessionState.value = SessionState.RecoverableError(failure.message)
                    }
                }
                is ApiCallFailure.NetworkError -> {
                    // Never silently treat network errors as logout; preserve credentials for retry.
                    _sessionState.value = SessionState.RecoverableError(failure.message)
                }
            }
        }
    }

    private suspend fun restoreGuestSession() {
        try {
            val info = authApiService.getDemoSession().toDomain()
            _sessionState.value = SessionState.GuestSession(info)
        } catch (ce: CancellationException) {
            throw ce
        } catch (t: Throwable) {
            when (val failure = errorParser.toFailure(t)) {
                is ApiCallFailure.ApiError -> {
                    if (failure.httpStatus == 401) {
                        credentialStore.clearGuestToken()
                        _sessionState.value = SessionState.Unauthenticated
                    } else {
                        _sessionState.value = SessionState.RecoverableError(failure.message)
                    }
                }
                is ApiCallFailure.NetworkError -> {
                    _sessionState.value = SessionState.RecoverableError(failure.message)
                }
            }
        }
    }

    override suspend fun login(email: String, password: String): AuthResult<UserProfile> {
        return try {
            val tokens = authApiService.login(
                LoginRequestDto(email = email.trim(), password = password)
            )
            credentialStore.saveBearerTokens(
                accessToken = tokens.accessToken,
                refreshToken = tokens.refreshToken,
                expiresInSeconds = tokens.expiresIn
            )
            val profile = authApiService.getMe().toDomain()
            _sessionState.value = SessionState.Authenticated(profile)
            AuthResult.Success(profile)
        } catch (ce: CancellationException) {
            throw ce
        } catch (t: Throwable) {
            val failure = errorParser.toFailure(t)
            if (failure is ApiCallFailure.ApiError && failure.httpStatus == 401) {
                credentialStore.clearBearerTokens()
            }
            AuthResult.Failure(failure)
        }
    }

    override suspend fun register(
        email: String,
        password: String,
        fullName: String,
        preferredLanguage: AppLanguage?
    ): AuthResult<UserProfile> {
        return try {
            val response = authApiService.register(
                RegisterRequestDto(
                    email = email.trim(),
                    password = password,
                    fullName = fullName.trim(),
                    preferredLang = preferredLanguage?.languageTag
                )
            )
            credentialStore.saveBearerTokens(
                accessToken = response.accessToken,
                refreshToken = response.refreshToken,
                expiresInSeconds = response.expiresIn
            )
            val profile = response.user.toDomain()
            _sessionState.value = SessionState.Authenticated(profile)
            AuthResult.Success(profile)
        } catch (ce: CancellationException) {
            throw ce
        } catch (t: Throwable) {
            AuthResult.Failure(errorParser.toFailure(t))
        }
    }

    override suspend fun fetchDemoLocations(
        limit: Int,
        cursor: String?
    ): AuthResult<List<DemoLocation>> {
        return try {
            val page = authApiService.getDemoLocations(limit = limit, cursor = cursor)
            AuthResult.Success(page.items.map { it.toDomain() })
        } catch (ce: CancellationException) {
            throw ce
        } catch (t: Throwable) {
            AuthResult.Failure(errorParser.toFailure(t))
        }
    }

    override suspend fun startGuestSession(demoLocationId: Int): AuthResult<GuestSessionInfo> {
        return try {
            val started = authApiService.startGuestSession(
                GuestSessionStartRequestDto(demoLocationId = demoLocationId)
            )
            credentialStore.saveGuestToken(
                guestToken = started.guestToken,
                expiresAtIso = started.expiresAt
            )
            val detailedInfo = try {
                authApiService.getDemoSession().toDomain()
            } catch (_: Exception) {
                started.toDomain()
            }
            _sessionState.value = SessionState.GuestSession(detailedInfo)
            AuthResult.Success(detailedInfo)
        } catch (ce: CancellationException) {
            throw ce
        } catch (t: Throwable) {
            AuthResult.Failure(errorParser.toFailure(t))
        }
    }

    override suspend fun refreshGuestSessionInfo(): AuthResult<GuestSessionInfo> {
        return try {
            val info = authApiService.getDemoSession().toDomain()
            _sessionState.value = SessionState.GuestSession(info)
            AuthResult.Success(info)
        } catch (ce: CancellationException) {
            throw ce
        } catch (t: Throwable) {
            val failure = errorParser.toFailure(t)
            if (failure is ApiCallFailure.ApiError && failure.httpStatus == 401) {
                credentialStore.clearGuestToken()
                _sessionState.value = SessionState.Unauthenticated
            }
            AuthResult.Failure(failure)
        }
    }

    override suspend fun logout(): AuthResult<Unit> {
        val refreshToken = credentialStore.getRefreshToken()
        return try {
            val response = authApiService.logout(LogoutRequestDto(refreshToken = refreshToken))
            if (response.isSuccessful || response.code() == 401) {
                credentialStore.clearBearerTokens()
                _sessionState.value = SessionState.Unauthenticated
                AuthResult.Success(Unit)
            } else {
                val errBody = response.errorBody()?.string()
                AuthResult.Failure(errorParser.parseErrorBody(response.code(), errBody, response.message()))
            }
        } catch (ce: CancellationException) {
            throw ce
        } catch (t: Throwable) {
            val failure = errorParser.toFailure(t)
            if (failure is ApiCallFailure.ApiError && failure.httpStatus == 401) {
                credentialStore.clearBearerTokens()
                _sessionState.value = SessionState.Unauthenticated
                AuthResult.Success(Unit)
            } else {
                AuthResult.Failure(failure)
            }
        }
    }

    override suspend fun deleteAccount(): AuthResult<Unit> {
        return try {
            val response = authApiService.deleteMe()
            if (response.isSuccessful) {
                credentialStore.clearAll()
                _sessionState.value = SessionState.Unauthenticated
                AuthResult.Success(Unit)
            } else {
                val errBody = response.errorBody()?.string()
                val failure = errorParser.parseErrorBody(response.code(), errBody, response.message())
                if (failure.httpStatus == 401) {
                    credentialStore.clearBearerTokens()
                    _sessionState.value = SessionState.Unauthenticated
                }
                AuthResult.Failure(failure)
            }
        } catch (ce: CancellationException) {
            throw ce
        } catch (t: Throwable) {
            AuthResult.Failure(errorParser.toFailure(t))
        }
    }

    override suspend fun exitGuestSession(): AuthResult<Unit> {
        return try {
            val response = authApiService.deleteDemoSession()
            if (response.isSuccessful || response.code() == 401) {
                credentialStore.clearGuestToken()
                _sessionState.value = SessionState.Unauthenticated
                AuthResult.Success(Unit)
            } else {
                val errBody = response.errorBody()?.string()
                AuthResult.Failure(errorParser.parseErrorBody(response.code(), errBody, response.message()))
            }
        } catch (ce: CancellationException) {
            throw ce
        } catch (t: Throwable) {
            val failure = errorParser.toFailure(t)
            if (failure is ApiCallFailure.ApiError && failure.httpStatus == 401) {
                credentialStore.clearGuestToken()
                _sessionState.value = SessionState.Unauthenticated
                AuthResult.Success(Unit)
            } else {
                AuthResult.Failure(failure)
            }
        }
    }

    override suspend fun clearSessionLocally() {
        credentialStore.clearAll()
        _sessionState.value = SessionState.Unauthenticated
    }
}

