package com.example.myapplication.data.analysis

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.example.myapplication.domain.analysis.ActiveAnalysisRequest
import javax.inject.Inject
import javax.inject.Qualifier
import javax.inject.Singleton
import kotlinx.coroutines.flow.first
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

private val Context.activeAnalysisDataStore: DataStore<Preferences> by preferencesDataStore(
    name = "fieldshift_active_analysis"
)

@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class ActiveAnalysisDataStore

@Serializable
private data class PersistedActiveAnalysis(
    val requestId: String,
    val farmId: String,
    val pollIntervalMs: Long,
    val createdAtEpochMs: Long
)

interface ActiveAnalysisStore {
    suspend fun getActiveRequest(): ActiveAnalysisRequest?
    suspend fun saveActiveRequest(request: ActiveAnalysisRequest)
    suspend fun clearActiveRequest()
}

@Singleton
class DataStoreActiveAnalysisStore @Inject constructor(
    @param:ActiveAnalysisDataStore private val dataStore: DataStore<Preferences>,
    private val json: Json
) : ActiveAnalysisStore {

    override suspend fun getActiveRequest(): ActiveAnalysisRequest? {
        val raw = dataStore.data.first()[KEY_ACTIVE_REQUEST] ?: return null
        return try {
            val dto = json.decodeFromString<PersistedActiveAnalysis>(raw)
            ActiveAnalysisRequest(
                requestId = dto.requestId,
                farmId = dto.farmId,
                pollIntervalMs = dto.pollIntervalMs,
                createdAtEpochMs = dto.createdAtEpochMs
            )
        } catch (_: Exception) {
            clearActiveRequest()
            null
        }
    }

    override suspend fun saveActiveRequest(request: ActiveAnalysisRequest) {
        val encoded = json.encodeToString(
            PersistedActiveAnalysis(
                requestId = request.requestId,
                farmId = request.farmId,
                pollIntervalMs = request.pollIntervalMs,
                createdAtEpochMs = request.createdAtEpochMs
            )
        )
        dataStore.edit { prefs ->
            prefs[KEY_ACTIVE_REQUEST] = encoded
        }
    }

    override suspend fun clearActiveRequest() {
        dataStore.edit { prefs ->
            prefs.remove(KEY_ACTIVE_REQUEST)
        }
    }

    companion object {
        private val KEY_ACTIVE_REQUEST = stringPreferencesKey("active_analysis_request")

        fun createDataStore(context: Context): DataStore<Preferences> =
            context.activeAnalysisDataStore
    }
}

