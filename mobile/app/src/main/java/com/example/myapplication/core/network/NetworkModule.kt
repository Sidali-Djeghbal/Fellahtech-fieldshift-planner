package com.example.myapplication.core.network

import com.example.myapplication.BuildConfig
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import java.util.concurrent.TimeUnit
import javax.inject.Qualifier
import javax.inject.Singleton
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class RefreshClient

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    private const val CONNECT_TIMEOUT_SECONDS = 15L
    private const val READ_TIMEOUT_SECONDS = 30L
    private const val WRITE_TIMEOUT_SECONDS = 30L

    @Provides
    @Singleton
    fun provideApiEndpointConfig(): ApiEndpointConfig {
        return ApiEndpointConfig(rawBaseUrl = BuildConfig.API_BASE_URL)
    }

    @Provides
    @Singleton
    fun provideJson(): Json {
        return Json {
            ignoreUnknownKeys = true
            explicitNulls = false
            coerceInputValues = true
            isLenient = false
        }
    }

    @Provides
    @Singleton
    @RefreshClient
    fun provideRefreshOkHttpClient(): OkHttpClient {
        // Dedicated client without AuthInterceptor/TokenRefreshAuthenticator to prevent
        // recursive 401 handling and ensure zero token logging.
        return OkHttpClient.Builder()
            .connectTimeout(CONNECT_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .readTimeout(READ_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .writeTimeout(WRITE_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .build()
    }

    @Provides
    @Singleton
    fun provideOkHttpClient(
        authInterceptor: AuthInterceptor,
        tokenRefreshAuthenticator: TokenRefreshAuthenticator
    ): OkHttpClient {
        // Never attach HttpLoggingInterceptor with BODY/HEADERS to avoid leaking tokens/passwords.
        return OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .authenticator(tokenRefreshAuthenticator)
            .connectTimeout(CONNECT_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .readTimeout(READ_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .writeTimeout(WRITE_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .build()
    }

    @Provides
    @Singleton
    fun provideRetrofitBuilder(
        okHttpClient: OkHttpClient,
        json: Json
    ): Retrofit.Builder {
        val contentType = "application/json".toMediaType()
        return Retrofit.Builder()
            .client(okHttpClient)
            .addConverterFactory(json.asConverterFactory(contentType))
    }

    @Provides
    @Singleton
    fun provideRetrofit(
        retrofitBuilder: Retrofit.Builder,
        endpointConfig: ApiEndpointConfig
    ): Retrofit {
        require(endpointConfig.isConfigured) {
            "API_BASE_URL is not configured. Set fieldshift.api.baseUrl in local.properties."
        }
        return retrofitBuilder
            .baseUrl(endpointConfig.normalizedBaseUrl)
            .build()
    }

    @Provides
    @Singleton
    fun provideTokenRefreshApiService(
        @RefreshClient refreshOkHttpClient: OkHttpClient,
        json: Json,
        endpointConfig: ApiEndpointConfig
    ): TokenRefreshApiService {
        require(endpointConfig.isConfigured) {
            "API_BASE_URL is not configured. Set fieldshift.api.baseUrl in local.properties."
        }
        val contentType = "application/json".toMediaType()
        return Retrofit.Builder()
            .baseUrl(endpointConfig.normalizedBaseUrl)
            .client(refreshOkHttpClient)
            .addConverterFactory(json.asConverterFactory(contentType))
            .build()
            .create(TokenRefreshApiService::class.java)
    }

    @Provides
    @Singleton
    fun provideAuthApiService(retrofit: Retrofit): AuthApiService {
        return retrofit.create(AuthApiService::class.java)
    }

    @Provides
    @Singleton
    fun provideFarmApiService(retrofit: Retrofit): FarmApiService {
        return retrofit.create(FarmApiService::class.java)
    }

    @Provides
    @Singleton
    fun provideFieldApiService(retrofit: Retrofit): FieldApiService {
        return retrofit.create(FieldApiService::class.java)
    }

    @Provides
    @Singleton
    fun provideAnalysisApiService(retrofit: Retrofit): AnalysisApiService {
        return retrofit.create(AnalysisApiService::class.java)
    }
}
