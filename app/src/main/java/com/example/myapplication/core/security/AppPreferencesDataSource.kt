package com.example.myapplication.core.security

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.fieldShiftPreferencesDataStore: DataStore<Preferences> by preferencesDataStore(
    name = "fieldshift_preferences"
)

/**
 * DataStore-backed local preferences store for session/configuration state.
 * Prepared for authentication/guest tokens and active farm/analysis context in subsequent phases.
 */
@Singleton
class AppPreferencesDataSource @Inject constructor(
    private val dataStore: DataStore<Preferences>
) {
    val preferredLanguageTag: Flow<String?> = dataStore.data.map { prefs ->
        prefs[KEY_LANGUAGE_TAG]
    }

    val customApiBaseUrl: Flow<String?> = dataStore.data.map { prefs ->
        prefs[KEY_CUSTOM_API_BASE_URL]
    }

    suspend fun setPreferredLanguageTag(languageTag: String) {
        dataStore.edit { prefs ->
            prefs[KEY_LANGUAGE_TAG] = languageTag
        }
    }

    suspend fun setCustomApiBaseUrl(baseUrl: String?) {
        dataStore.edit { prefs ->
            if (baseUrl.isNullOrBlank()) {
                prefs.remove(KEY_CUSTOM_API_BASE_URL)
            } else {
                prefs[KEY_CUSTOM_API_BASE_URL] = baseUrl.trim()
            }
        }
    }

    private companion object {
        val KEY_LANGUAGE_TAG = stringPreferencesKey("preferred_language_tag")
        val KEY_CUSTOM_API_BASE_URL = stringPreferencesKey("custom_api_base_url")
    }
}

@Module
@InstallIn(SingletonComponent::class)
object DataStoreModule {
    @Provides
    @Singleton
    fun providePreferencesDataStore(
        @ApplicationContext context: Context
    ): DataStore<Preferences> = context.fieldShiftPreferencesDataStore
}

