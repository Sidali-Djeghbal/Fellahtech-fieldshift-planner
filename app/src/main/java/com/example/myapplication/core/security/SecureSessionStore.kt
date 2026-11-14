package com.example.myapplication.core.security

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.example.myapplication.core.network.CredentialStore
import dagger.Binds
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import java.util.concurrent.atomic.AtomicReference
import javax.inject.Inject
import javax.inject.Qualifier
import javax.inject.Singleton
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

private val Context.secureSessionDataStore: DataStore<Preferences> by preferencesDataStore(
    name = "fieldshift_secure_session"
)

@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class SecureSessionDataStore

@Serializable
data class PersistedCredentials(
    val accessToken: String? = null,
    val refreshToken: String? = null,
    val accessExpiresAtEpochMs: Long? = null,
    val guestToken: String? = null,
    val guestExpiresAtIso: String? = null
)

/**
 * Keystore-encrypted DataStore implementation of [CredentialStore].
 *
 * All sensitive credentials (`access_token`, `refresh_token`, `guest_token`) are serialized
 * and encrypted with [KeystoreCryptoManager] before being written to DataStore Preferences.
 * An in-memory [AtomicReference] provides lock-free synchronous reads for OkHttp interceptors
 * after [warmUp] completes at startup.
 */
@Singleton
class SecureSessionStore @Inject constructor(
    @SecureSessionDataStore private val dataStore: DataStore<Preferences>,
    private val cryptoManager: KeystoreCryptoManager,
    private val json: Json
) : CredentialStore {

    private val writeMutex = Mutex()
    private val cached = AtomicReference(PersistedCredentials())
    @Volatile
    private var isWarmedUp = false

    suspend fun warmUp(): PersistedCredentials {
        if (isWarmedUp) return cached.get()
        return writeMutex.withLock {
            if (isWarmedUp) return@withLock cached.get()
            val prefs = dataStore.data.first()
            val encryptedBlob = prefs[KEY_ENCRYPTED_CREDENTIALS]
            val restored = if (!encryptedBlob.isNullOrBlank()) {
                cryptoManager.decrypt(encryptedBlob)?.let { plaintext ->
                    try {
                        json.decodeFromString<PersistedCredentials>(plaintext)
                    } catch (_: Exception) {
                        PersistedCredentials()
                    }
                } ?: PersistedCredentials()
            } else {
                PersistedCredentials()
            }
            cached.set(restored)
            isWarmedUp = true
            restored
        }
    }

    override fun getAccessToken(): String? = cached.get().accessToken

    override fun getRefreshToken(): String? = cached.get().refreshToken

    override fun getGuestToken(): String? = cached.get().guestToken

    override suspend fun saveBearerTokens(
        accessToken: String,
        refreshToken: String,
        expiresInSeconds: Int
    ) {
        updateCredentials { current ->
            current.copy(
                accessToken = accessToken,
                refreshToken = refreshToken,
                accessExpiresAtEpochMs = System.currentTimeMillis() + (expiresInSeconds * 1000L),
                guestToken = null,
                guestExpiresAtIso = null
            )
        }
    }

    override suspend fun saveGuestToken(guestToken: String, expiresAtIso: String) {
        updateCredentials { current ->
            current.copy(
                accessToken = null,
                refreshToken = null,
                accessExpiresAtEpochMs = null,
                guestToken = guestToken,
                guestExpiresAtIso = expiresAtIso
            )
        }
    }

    override suspend fun clearBearerTokens() {
        updateCredentials { current ->
            current.copy(
                accessToken = null,
                refreshToken = null,
                accessExpiresAtEpochMs = null
            )
        }
    }

    override suspend fun clearGuestToken() {
        updateCredentials { current ->
            current.copy(
                guestToken = null,
                guestExpiresAtIso = null
            )
        }
    }

    override suspend fun clearAll() {
        writeMutex.withLock {
            cached.set(PersistedCredentials())
            isWarmedUp = true
            dataStore.edit { prefs ->
                prefs.remove(KEY_ENCRYPTED_CREDENTIALS)
            }
        }
    }

    private suspend fun updateCredentials(transform: (PersistedCredentials) -> PersistedCredentials) {
        writeMutex.withLock {
            val next = transform(cached.get())
            cached.set(next)
            isWarmedUp = true
            val serialized = json.encodeToString(next)
            val encrypted = cryptoManager.encrypt(serialized)
            dataStore.edit { prefs ->
                prefs[KEY_ENCRYPTED_CREDENTIALS] = encrypted
            }
        }
    }

    private companion object {
        val KEY_ENCRYPTED_CREDENTIALS = stringPreferencesKey("encrypted_credentials_v1")
    }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class SecurityBindingModule {
    @Binds
    @Singleton
    abstract fun bindCredentialStore(impl: SecureSessionStore): CredentialStore
}

@Module
@InstallIn(SingletonComponent::class)
object SecurityProviderModule {
    @Provides
    @Singleton
    @SecureSessionDataStore
    fun provideSecureSessionDataStore(
        @ApplicationContext context: Context
    ): DataStore<Preferences> = context.secureSessionDataStore
}

