package com.example.myapplication.core.network

import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.serialization.json.Json
import retrofit2.HttpException

sealed class ApiCallFailure(message: String, cause: Throwable? = null) : Exception(message, cause) {
    class ApiError(
        val httpStatus: Int,
        val errorCode: String?,
        override val message: String,
        val requestId: String? = null
    ) : ApiCallFailure(message)

    class NetworkError(
        override val message: String,
        cause: Throwable? = null
    ) : ApiCallFailure(message, cause)
}

@Singleton
class ApiErrorParser @Inject constructor(
    private val json: Json
) {
    fun toFailure(throwable: Throwable): ApiCallFailure {
        return when (throwable) {
            is ApiCallFailure -> throwable
            is HttpException -> parseHttpException(throwable)
            is IOException -> ApiCallFailure.NetworkError(
                message = throwable.localizedMessage ?: "Network connection unavailable",
                cause = throwable
            )
            else -> ApiCallFailure.NetworkError(
                message = throwable.localizedMessage ?: "Unexpected communication error",
                cause = throwable
            )
        }
    }

    fun parseHttpException(exception: HttpException): ApiCallFailure.ApiError {
        val status = exception.code()
        val rawBody = try {
            exception.response()?.errorBody()?.string()
        } catch (_: Exception) {
            null
        }
        return parseErrorBody(status, rawBody, exception.message())
    }

    fun parseErrorBody(
        httpStatus: Int,
        rawBody: String?,
        fallbackMessage: String? = null
    ): ApiCallFailure.ApiError {
        if (!rawBody.isNullOrBlank()) {
            try {
                val envelope = json.decodeFromString<ErrorEnvelopeDto>(rawBody)
                return ApiCallFailure.ApiError(
                    httpStatus = httpStatus,
                    errorCode = envelope.error.code,
                    message = envelope.error.message,
                    requestId = envelope.error.requestId
                )
            } catch (_: Exception) {
                // Fall through to generic HTTP error if body is not an ErrorEnvelope
            }
        }
        return ApiCallFailure.ApiError(
            httpStatus = httpStatus,
            errorCode = null,
            message = fallbackMessage?.takeIf { it.isNotBlank() } ?: "HTTP $httpStatus"
        )
    }
}

