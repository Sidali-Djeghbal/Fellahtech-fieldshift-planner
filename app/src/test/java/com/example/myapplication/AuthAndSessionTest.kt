package com.example.myapplication

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import com.example.myapplication.core.common.UiState
import com.example.myapplication.core.network.ApiCallFailure
import com.example.myapplication.core.network.ApiEndpointConfig
import com.example.myapplication.core.network.ApiErrorParser
import com.example.myapplication.core.network.AuthApiService
import com.example.myapplication.core.network.AuthInterceptor
import com.example.myapplication.core.network.CredentialStore
import com.example.myapplication.core.network.DemoLocationPageDto
import com.example.myapplication.core.network.DemoLocationSummaryDto
import com.example.myapplication.core.network.DemoParcelPreviewDto
import com.example.myapplication.core.network.ErrorEnvelopeDto
import com.example.myapplication.core.network.GeoLocationPointDto
import com.example.myapplication.core.network.GuestSessionInfoDto
import com.example.myapplication.core.network.GuestSessionLimitsDto
import com.example.myapplication.core.network.GuestSessionStartRequestDto
import com.example.myapplication.core.network.GuestSessionStartResponseDto
import com.example.myapplication.core.network.GuestSessionUsageDto
import com.example.myapplication.core.network.LoginRequestDto
import com.example.myapplication.core.network.LogoutRequestDto
import com.example.myapplication.core.network.RefreshRequestDto
import com.example.myapplication.core.network.RegisterRequestDto
import com.example.myapplication.core.network.RegisterResponseDto
import com.example.myapplication.core.network.TokenPairResponseDto
import com.example.myapplication.core.network.TokenRefreshApiService
import com.example.myapplication.core.network.TokenRefreshAuthenticator
import com.example.myapplication.core.network.UserProfileDto
import com.example.myapplication.core.network.WarningNoticeDto
import com.example.myapplication.core.security.KeystoreCryptoManager
import com.example.myapplication.core.security.SecureSessionStore
import com.example.myapplication.data.auth.AuthRepositoryImpl
import com.example.myapplication.domain.auth.AuthResult
import com.example.myapplication.domain.auth.SessionState
import com.example.myapplication.feature.auth.AuthEntryTab
import com.example.myapplication.feature.auth.AuthValidationError
import com.example.myapplication.feature.auth.AuthViewModel
import com.example.myapplication.feature.profile.ProfileViewModel
import java.io.File
import java.io.IOException
import java.security.InvalidKeyException
import java.util.concurrent.TimeUnit
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.inject.Provider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.serialization.json.Json
import okhttp3.Call
import okhttp3.Connection
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import okio.Timeout
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.Callback
import retrofit2.HttpException

@OptIn(ExperimentalCoroutinesApi::class)
class AuthAndSessionTest {

    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        encodeDefaults = true
    }

    @Test
    fun `openApi auth and demo DTOs deserialize exact contract fields`() {
        val registerJson = """
            {
              "user": {
                "id": 123,
                "email": "farmer@fieldshift.ag",
                "full_name": "Amina Mansouri",
                "preferred_lang": "fr",
                "created_at": "2026-03-01T10:00:00Z"
              },
              "access_token": "acc-1",
              "refresh_token": "ref-1",
              "token_type": "bearer",
              "expires_in": 3600
            }
        """.trimIndent()
        val registerDto = json.decodeFromString<RegisterResponseDto>(registerJson)
        assertEquals(123, registerDto.user.id)
        assertEquals("Amina Mansouri", registerDto.user.fullName)
        assertEquals("fr", registerDto.user.preferredLang)
        assertEquals("bearer", registerDto.tokenType)
        assertEquals(3600, registerDto.expiresIn)

        val demoPageJson = """
            {
              "items": [
                {
                  "id": 42,
                  "code": "meknes-01",
                  "name": "Meknes Olive & Wheat Plot",
                  "country": "MA",
                  "region": "Fes-Meknes"
                }
              ],
              "next_cursor": "cursor-2",
              "has_more": true
            }
        """.trimIndent()
        val demoPage = json.decodeFromString<DemoLocationPageDto>(demoPageJson)
        assertEquals(1, demoPage.items.size)
        assertEquals(42, demoPage.items.first().id)
        assertEquals("meknes-01", demoPage.items.first().code)
        assertEquals("Fes-Meknes", demoPage.items.first().region)
        assertEquals("cursor-2", demoPage.nextCursor)
        assertTrue(demoPage.hasMore)

        val guestStartJson = """
            {
              "guest_token": "gst-xyz",
              "expires_at": "2026-03-02T10:00:00Z",
              "demo_location": {
                "id": 42,
                "code": "meknes-01",
                "name": "Meknes Plot",
                "country": "MA",
                "region": "Fes-Meknes"
              },
              "demo_parcel": {
                "field_id": "p-9",
                "field_name": "Meknes Demo Parcel",
                "location": { "latitude": 33.8935, "longitude": -5.5473 },
                "area_hectares": 4.5,
                "is_unverified_demo_parcel": true,
                "warnings": [
                  { "code": "DEMO_PARCEL", "message": "Preset demo parcel" }
                ]
              }
            }
        """.trimIndent()
        val guestStart = json.decodeFromString<GuestSessionStartResponseDto>(guestStartJson)
        assertEquals("gst-xyz", guestStart.guestToken)
        assertEquals(33.8935, guestStart.demoParcel.location.latitude, 0.0001)
        assertTrue(guestStart.demoParcel.isUnverifiedDemoParcel)
        assertEquals("DEMO_PARCEL", guestStart.demoParcel.warnings.first().code)

        val errorJson = """
            {
              "error": {
                "code": "AUTH_INVALID_CREDENTIALS",
                "message": "Invalid email or password",
                "request_id": "req-99"
              }
            }
        """.trimIndent()
        val errorEnvelope = json.decodeFromString<ErrorEnvelopeDto>(errorJson)
        assertEquals("AUTH_INVALID_CREDENTIALS", errorEnvelope.error.code)
        assertEquals("req-99", errorEnvelope.error.requestId)
    }

    @Test
    fun `apiErrorParser parses envelope and preserves network error distinction`() {
        val parser = ApiErrorParser(json)

        val apiErr = parser.parseErrorBody(
            httpStatus = 401,
            rawBody = """{"error":{"code":"TOKEN_EXPIRED","message":"Session expired","request_id":"r-1"}}"""
        )
        assertEquals(401, apiErr.httpStatus)
        assertEquals("TOKEN_EXPIRED", apiErr.errorCode)
        assertEquals("Session expired", apiErr.message)
        assertEquals("r-1", apiErr.requestId)

        val fallbackErr = parser.parseErrorBody(httpStatus = 502, rawBody = "Bad Gateway")
        assertEquals(502, fallbackErr.httpStatus)
        assertNull(fallbackErr.errorCode)
        assertEquals("HTTP 502", fallbackErr.message)

        val networkErr = parser.toFailure(IOException("Timeout"))
        assertTrue(networkErr is ApiCallFailure.NetworkError)
    }

    @Test
    fun `authInterceptor injects correct header on same-origin requests`() {
        val store = FakeCredentialStore(
            access = "access-123",
            refresh = "refresh-123",
            guest = "guest-123"
        )
        val endpointConfig = ApiEndpointConfig(rawBaseUrl = "http://localhost/api/v1/")
        val interceptor = AuthInterceptor(store, endpointConfig)

        val loginReq = captureInterceptedRequest(interceptor, "http://localhost/api/v1/auth/login")
        assertNull(loginReq.header(AuthInterceptor.HEADER_AUTHORIZATION))
        assertNull(loginReq.header(AuthInterceptor.HEADER_GUEST_TOKEN))

        val demoLocReq = captureInterceptedRequest(interceptor, "http://localhost/api/v1/demo/locations?limit=20")
        assertNull(demoLocReq.header(AuthInterceptor.HEADER_AUTHORIZATION))
        assertNull(demoLocReq.header(AuthInterceptor.HEADER_GUEST_TOKEN))

        val meReq = captureInterceptedRequest(interceptor, "http://localhost/api/v1/auth/me")
        assertEquals("Bearer access-123", meReq.header(AuthInterceptor.HEADER_AUTHORIZATION))
        assertNull(meReq.header(AuthInterceptor.HEADER_GUEST_TOKEN))

        val demoSessionReq = captureInterceptedRequest(interceptor, "http://localhost/api/v1/demo/session")
        assertEquals("guest-123", demoSessionReq.header(AuthInterceptor.HEADER_GUEST_TOKEN))
        assertNull(demoSessionReq.header(AuthInterceptor.HEADER_AUTHORIZATION))

        val sharedReq = captureInterceptedRequest(interceptor, "http://localhost/api/v1/farms")
        assertEquals("Bearer access-123", sharedReq.header(AuthInterceptor.HEADER_AUTHORIZATION))
    }

    @Test
    fun `authInterceptor never transmits credentials to different host, port, or scheme`() {
        val store = FakeCredentialStore(
            access = "super-secret-access",
            refresh = "super-secret-refresh",
            guest = "guest-secret-token"
        )
        val endpointConfig = ApiEndpointConfig(rawBaseUrl = "http://localhost:8000/api/v1/")
        val interceptor = AuthInterceptor(store, endpointConfig)

        // 1. Different host
        val untrustedHostReq = captureInterceptedRequest(interceptor, "http://attacker.com/api/v1/auth/me")
        assertNull(untrustedHostReq.header(AuthInterceptor.HEADER_AUTHORIZATION))
        assertNull(untrustedHostReq.header(AuthInterceptor.HEADER_GUEST_TOKEN))

        // 2. Different port
        val untrustedPortReq = captureInterceptedRequest(interceptor, "http://localhost:9000/api/v1/auth/me")
        assertNull(untrustedPortReq.header(AuthInterceptor.HEADER_AUTHORIZATION))
        assertNull(untrustedPortReq.header(AuthInterceptor.HEADER_GUEST_TOKEN))

        // 3. Different scheme (https vs http)
        val untrustedSchemeReq = captureInterceptedRequest(interceptor, "https://localhost:8000/api/v1/auth/me")
        assertNull(untrustedSchemeReq.header(AuthInterceptor.HEADER_AUTHORIZATION))
        assertNull(untrustedSchemeReq.header(AuthInterceptor.HEADER_GUEST_TOKEN))

        // 4. Guest endpoint on different host
        val untrustedGuestReq = captureInterceptedRequest(interceptor, "http://attacker.com/api/v1/demo/session")
        assertNull(untrustedGuestReq.header(AuthInterceptor.HEADER_GUEST_TOKEN))

        // 5. Matching origin succeeds
        val trustedReq = captureInterceptedRequest(interceptor, "http://localhost:8000/api/v1/auth/me")
        assertEquals("Bearer super-secret-access", trustedReq.header(AuthInterceptor.HEADER_AUTHORIZATION))
    }

    @Test
    fun `keystoreCryptoManager recovers from invalidated key without crash or data leak`() {
        val crypto = InvalidationRecoveryCryptoManager()
        val plaintext = """{"accessToken":"test-token","refreshToken":"ref-token"}"""

        // First encrypt attempt hits invalidated key, catches it, calls deleteKey(), generates fresh key, and succeeds.
        val encrypted = crypto.encrypt(plaintext)
        assertNotNull(encrypted)
        assertTrue(encrypted.isNotBlank())
        assertEquals(1, crypto.deleteKeyCallCount)

        // Decrypt using the new key yields original plaintext
        val decrypted = crypto.decrypt(encrypted)
        assertEquals(plaintext, decrypted)

        // Decrypt on corrupted payload returns null safely
        assertNull(crypto.decrypt("not-a-valid-base64-or-iv-payload"))
    }

    @Test
    fun `secureSessionStore safe initialization and corrupted payload cleanup`() = runTest {
        val tempDir = java.nio.file.Files.createTempDirectory("fieldshift_test_session").toFile()
        try {
            val testDataStore = PreferenceDataStoreFactory.create(
                produceFile = { File(tempDir, "test.preferences_pb") }
            )
            val crypto = TestCryptoManager()
            val store = SecureSessionStore(testDataStore, crypto, json)

            // Save tokens -> encrypted
            store.saveBearerTokens("acc-1", "ref-1", 3600)
            assertEquals("acc-1", store.getAccessToken())
            assertEquals("ref-1", store.getRefreshToken())

            // Corrupt the stored data in dataStore
            val key = stringPreferencesKey("encrypted_credentials_v1")
            testDataStore.edit { prefs ->
                prefs[key] = "corrupted-unusable-ciphertext"
            }

            // A new store instance warming up with corrupted payload clears dataStore safely without throwing
            val store2 = SecureSessionStore(testDataStore, crypto, json)
            val restored = store2.warmUp()
            assertNull(restored.accessToken)
            assertNull(store2.getAccessToken())
        } finally {
            tempDir.deleteRecursively()
        }
    }

    @Test
    fun `tokenRefreshAuthenticator rotates once and prevents loops and network wipes`() {
        val store = FakeCredentialStore(access = "old-acc", refresh = "old-ref")
        var refreshCallCount = 0
        val refreshApi = object : TokenRefreshApiService {
            override fun refreshTokenCall(request: RefreshRequestDto): retrofit2.Call<TokenPairResponseDto> {
                refreshCallCount++
                return FakeCall {
                    retrofit2.Response.success(
                        TokenPairResponseDto(
                            accessToken = "new-acc",
                            refreshToken = "new-ref",
                            tokenType = "bearer",
                            expiresIn = 3600
                        )
                    )
                }
            }
        }
        val authenticator = TokenRefreshAuthenticator(store, Provider { refreshApi })

        val failedResponse = build401Response("http://localhost/api/v1/auth/me", "Bearer old-acc")
        val retried = authenticator.authenticate(null, failedResponse)
        assertNotNull(retried)
        assertEquals("Bearer new-acc", retried?.header(AuthInterceptor.HEADER_AUTHORIZATION))
        assertEquals("1", retried?.header(HEADER_REFRESH_ATTEMPT))
        assertEquals(1, refreshCallCount)
        assertEquals("new-acc", store.getAccessToken())

        // A second 401 that already carries the retry header must NOT loop.
        val retriedAgainResponse = build401Response(
            url = "http://localhost/api/v1/auth/me",
            authHeader = "Bearer new-acc",
            refreshAttempt = "1"
        )
        assertNull(authenticator.authenticate(null, retriedAgainResponse))

        // Concurrent 401 with stale token reuses already rotated token without calling refresh again.
        val staleConcurrent401 = build401Response("http://localhost/api/v1/farms", "Bearer old-acc")
        val concurrentRetry = authenticator.authenticate(null, staleConcurrent401)
        assertEquals("Bearer new-acc", concurrentRetry?.header(AuthInterceptor.HEADER_AUTHORIZATION))
        assertEquals(1, refreshCallCount)

        // Network failure during refresh must NOT clear credentials.
        val ioFailureApi = object : TokenRefreshApiService {
            override fun refreshTokenCall(request: RefreshRequestDto): retrofit2.Call<TokenPairResponseDto> {
                return FakeCall { throw IOException("No network") }
            }
        }
        val ioAuth = TokenRefreshAuthenticator(store, Provider { ioFailureApi })
        assertNull(ioAuth.authenticate(null, build401Response("http://localhost/api/v1/auth/me", "Bearer new-acc")))
        assertEquals("new-acc", store.getAccessToken())
        assertEquals("new-ref", store.getRefreshToken())

        // 401 from refresh endpoint MUST clear Bearer credentials.
        val unauthorizedRefreshApi = object : TokenRefreshApiService {
            override fun refreshTokenCall(request: RefreshRequestDto): retrofit2.Call<TokenPairResponseDto> {
                return FakeCall {
                    retrofit2.Response.error(
                        401,
                        """{"error":{"code":"REFRESH_REVOKED","message":"Revoked"}}""".toResponseBody("application/json".toMediaType())
                    )
                }
            }
        }
        val revokedAuth = TokenRefreshAuthenticator(store, Provider { unauthorizedRefreshApi })
        assertNull(revokedAuth.authenticate(null, build401Response("http://localhost/api/v1/auth/me", "Bearer new-acc")))
        assertNull(store.getAccessToken())
        assertNull(store.getRefreshToken())
    }

    @Test
    fun `authRepositoryImpl restores, logs in, starts guest session, and clears appropriately`() = runTest {
        val store = FakeCredentialStore()
        val fakeApi = FakeAuthApiService()
        val repo = AuthRepositoryImpl(fakeApi, store, ApiErrorParser(json))

        // 1. No credentials -> Unauthenticated
        repo.restoreSession()
        assertEquals(SessionState.Unauthenticated, repo.sessionState.value)

        // 2. Start guest session -> GuestSession + token persisted
        val guestResult = repo.startGuestSession(demoLocationId = 42)
        assertTrue(guestResult is AuthResult.Success)
        assertTrue(repo.sessionState.value is SessionState.GuestSession)
        assertEquals("gst-1", store.getGuestToken())

        // 3. Exit guest session -> Unauthenticated + guest token cleared
        val exitResult = repo.exitGuestSession()
        assertTrue(exitResult is AuthResult.Success)
        assertEquals(SessionState.Unauthenticated, repo.sessionState.value)
        assertNull(store.getGuestToken())

        // 4. Restore Bearer session with network error -> RecoverableError + tokens preserved
        store.saveBearerTokens("acc-valid", "ref-valid", 3600)
        fakeApi.getMeResult = { throw IOException("Offline") }
        repo.restoreSession()
        assertTrue(repo.sessionState.value is SessionState.RecoverableError)
        assertEquals("acc-valid", store.getAccessToken())

        // 5. Restore Bearer session with 401 -> Unauthenticated + tokens cleared
        fakeApi.getMeResult = { throw httpException(401) }
        repo.restoreSession()
        assertEquals(SessionState.Unauthenticated, repo.sessionState.value)
        assertNull(store.getAccessToken())

        // 6. Login -> Authenticated
        fakeApi.getMeResult = {
            UserProfileDto(
                id = 1,
                email = "user@fieldshift.ag",
                fullName = "Field Engineer",
                preferredLang = "en",
                createdAt = "2026-03-01T10:00:00Z"
            )
        }
        val loginResult = repo.login("user@fieldshift.ag", "secret1234")
        assertTrue(loginResult is AuthResult.Success)
        assertTrue(repo.sessionState.value is SessionState.Authenticated)
        assertEquals("acc-login", store.getAccessToken())

        // 7. Logout -> Unauthenticated + tokens cleared
        val logoutResult = repo.logout()
        assertTrue(logoutResult is AuthResult.Success)
        assertEquals(SessionState.Unauthenticated, repo.sessionState.value)
        assertNull(store.getAccessToken())
    }

    @Test
    fun `authViewModel and profileViewModel manage validation, demo locations, and profile actions`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val store = FakeCredentialStore()
            val fakeApi = FakeAuthApiService()
            val repo = AuthRepositoryImpl(fakeApi, store, ApiErrorParser(json))

            val authVm = AuthViewModel(repo)
            authVm.onEmailChanged("bad-email")
            authVm.submitLogin()
            assertEquals(AuthValidationError.INVALID_EMAIL, authVm.uiState.value.validationError)

            authVm.selectTab(AuthEntryTab.GUEST)
            advanceUntilIdle()
            val demoState = authVm.uiState.value.demoLocationsState
            assertTrue(demoState is UiState.Success)
            assertEquals(42, authVm.uiState.value.selectedDemoLocationId)

            authVm.submitGuestSession()
            advanceUntilIdle()
            assertTrue(repo.sessionState.value is SessionState.GuestSession)

            val profileVm = ProfileViewModel(repo)
            profileVm.requestDeleteAccount()
            assertTrue(profileVm.uiState.value.showDeleteConfirmation)
            profileVm.dismissDeleteConfirmation()
            assertFalse(profileVm.uiState.value.showDeleteConfirmation)

            profileVm.exitGuestSession()
            advanceUntilIdle()
            assertEquals(SessionState.Unauthenticated, repo.sessionState.value)
        } finally {
            Dispatchers.resetMain()
        }
    }

    private fun captureInterceptedRequest(interceptor: AuthInterceptor, url: String): Request {
        var captured: Request? = null
        val request = Request.Builder().url(url).build()
        val chain = object : Interceptor.Chain {
            override fun request(): Request = request
            override fun proceed(request: Request): Response {
                captured = request
                return Response.Builder()
                    .request(request)
                    .protocol(Protocol.HTTP_1_1)
                    .code(200)
                    .message("OK")
                    .body("{}".toResponseBody("application/json".toMediaType()))
                    .build()
            }
            override fun connection(): Connection? = null
            override fun call(): Call = throw UnsupportedOperationException()
            override fun connectTimeoutMillis(): Int = 0
            override fun withConnectTimeout(timeout: Int, unit: TimeUnit): Interceptor.Chain = this
            override fun readTimeoutMillis(): Int = 0
            override fun withReadTimeout(timeout: Int, unit: TimeUnit): Interceptor.Chain = this
            override fun writeTimeoutMillis(): Int = 0
            override fun withWriteTimeout(timeout: Int, unit: TimeUnit): Interceptor.Chain = this
        }
        interceptor.intercept(chain)
        return requireNotNull(captured)
    }

    private fun build401Response(
        url: String,
        authHeader: String,
        refreshAttempt: String? = null
    ): Response {
        val reqBuilder = Request.Builder()
            .url(url)
            .header(AuthInterceptor.HEADER_AUTHORIZATION, authHeader)
        if (refreshAttempt != null) {
            reqBuilder.header(HEADER_REFRESH_ATTEMPT, refreshAttempt)
        }
        return Response.Builder()
            .request(reqBuilder.build())
            .protocol(Protocol.HTTP_1_1)
            .code(401)
            .message("Unauthorized")
            .body("{}".toResponseBody("application/json".toMediaType()))
            .build()
    }

    private fun httpException(code: Int): HttpException {
        val errorBody = """{"error":{"code":"ERR_$code","message":"HTTP $code"}}"""
            .toResponseBody("application/json".toMediaType())
        return HttpException(retrofit2.Response.error<Any>(code, errorBody))
    }

    private class InvalidationRecoveryCryptoManager : KeystoreCryptoManager() {
        var deleteKeyCallCount = 0
        var shouldFailInitialKey = true
        private val key1 = generateJvmAesKey()
        private val key2 = generateJvmAesKey()

        override fun getOrCreateSecretKey(): SecretKey {
            return if (shouldFailInitialKey) key1 else key2
        }

        override fun generateNewSecretKey(): SecretKey {
            shouldFailInitialKey = false
            return key2
        }

        override fun deleteKey() {
            deleteKeyCallCount++
        }

        override fun encryptWithKey(plaintext: String, secretKey: SecretKey): String {
            if (secretKey == key1 && shouldFailInitialKey) {
                throw InvalidKeyException("KeyPermanentlyInvalidatedException: Key invalidated due to biometric/lock change")
            }
            return super.encryptWithKey(plaintext, secretKey)
        }

        private fun generateJvmAesKey(): SecretKey {
            val kg = KeyGenerator.getInstance("AES")
            kg.init(256)
            return kg.generateKey()
        }
    }

    private class TestCryptoManager : KeystoreCryptoManager() {
        private val key = KeyGenerator.getInstance("AES").apply { init(256) }.generateKey()

        override fun getOrCreateSecretKey(): SecretKey = key
        override fun generateNewSecretKey(): SecretKey = key
        override fun deleteKey() = Unit
    }

    private class FakeCredentialStore(
        @Volatile private var access: String? = null,
        @Volatile private var refresh: String? = null,
        @Volatile private var guest: String? = null
    ) : CredentialStore {
        override fun getAccessToken(): String? = access
        override fun getRefreshToken(): String? = refresh
        override fun getGuestToken(): String? = guest

        override suspend fun saveBearerTokens(
            accessToken: String,
            refreshToken: String,
            expiresInSeconds: Int
        ) {
            access = accessToken
            refresh = refreshToken
        }

        override suspend fun saveGuestToken(guestToken: String, expiresAtIso: String) {
            guest = guestToken
        }

        override suspend fun clearBearerTokens() {
            access = null
            refresh = null
        }

        override suspend fun clearGuestToken() {
            guest = null
        }

        override suspend fun clearAll() {
            access = null
            refresh = null
            guest = null
        }
    }

    private class FakeAuthApiService : AuthApiService {
        private val demoLocation = DemoLocationSummaryDto(
            id = 42,
            code = "meknes-01",
            name = "Meknes Plot",
            country = "MA",
            region = "Fes-Meknes"
        )
        private val demoParcel = DemoParcelPreviewDto(
            fieldId = "p-42",
            fieldName = "Meknes Demo Parcel",
            location = GeoLocationPointDto(33.8935, -5.5473),
            areaHectares = 4.5,
            isUnverifiedDemoParcel = true,
            warnings = listOf(WarningNoticeDto(code = "DEMO_PARCEL", message = "Demo only"))
        )

        var getMeResult: () -> UserProfileDto = {
            UserProfileDto(
                id = 1,
                email = "user@fieldshift.ag",
                fullName = "Field Engineer",
                preferredLang = "en",
                createdAt = "2026-03-01T10:00:00Z"
            )
        }

        override suspend fun startGuestSession(
            request: GuestSessionStartRequestDto
        ): GuestSessionStartResponseDto {
            return GuestSessionStartResponseDto(
                guestToken = "gst-1",
                expiresAt = "2026-03-02T10:00:00Z",
                demoLocation = demoLocation,
                demoParcel = demoParcel
            )
        }

        override suspend fun register(request: RegisterRequestDto): RegisterResponseDto {
            return RegisterResponseDto(
                user = UserProfileDto(
                    id = 2,
                    email = request.email,
                    fullName = request.fullName,
                    preferredLang = request.preferredLang ?: "en",
                    createdAt = "2026-03-01T10:00:00Z"
                ),
                accessToken = "acc-reg",
                refreshToken = "ref-reg",
                tokenType = "bearer",
                expiresIn = 3600
            )
        }

        override suspend fun login(request: LoginRequestDto): TokenPairResponseDto {
            return TokenPairResponseDto(
                accessToken = "acc-login",
                refreshToken = "ref-login",
                tokenType = "bearer",
                expiresIn = 3600
            )
        }

        override suspend fun logout(request: LogoutRequestDto?): retrofit2.Response<Unit> =
            retrofit2.Response.success(Unit)

        override suspend fun getMe(): UserProfileDto = getMeResult()

        override suspend fun deleteMe(): retrofit2.Response<Unit> =
            retrofit2.Response.success(Unit)

        override suspend fun getDemoLocations(limit: Int, cursor: String?): DemoLocationPageDto {
            return DemoLocationPageDto(
                items = listOf(demoLocation),
                nextCursor = null,
                hasMore = false
            )
        }

        override suspend fun getDemoSession(): GuestSessionInfoDto {
            return GuestSessionInfoDto(
                demoLocation = demoLocation,
                demoParcel = demoParcel,
                createdAt = "2026-03-01T10:00:00Z",
                expiresAt = "2026-03-02T10:00:00Z",
                limits = GuestSessionLimitsDto(
                    maxFarms = 1,
                    maxFieldsPerFarm = 1,
                    maxAnalyses = 3,
                    maxAnalysisQuarters = 4
                ),
                usage = GuestSessionUsageDto(
                    farms = 1,
                    fields = 1,
                    analysisQuarters = 0,
                    analyses = 0.0
                )
            )
        }

        override suspend fun deleteDemoSession(): retrofit2.Response<Unit> =
            retrofit2.Response.success(Unit)
    }

    private class FakeCall<T>(
        private val block: () -> retrofit2.Response<T>
    ) : retrofit2.Call<T> {
        override fun execute(): retrofit2.Response<T> = block()
        override fun enqueue(callback: Callback<T>) = throw UnsupportedOperationException()
        override fun isExecuted(): Boolean = false
        override fun clone(): retrofit2.Call<T> = FakeCall(block)
        override fun isCanceled(): Boolean = false
        override fun cancel() = Unit
        override fun request(): Request = Request.Builder().url("http://localhost/").build()
        override fun timeout(): Timeout = Timeout.NONE
    }

    private companion object {
        const val HEADER_REFRESH_ATTEMPT = "X-FieldShift-Refresh-Attempt"
    }
}
