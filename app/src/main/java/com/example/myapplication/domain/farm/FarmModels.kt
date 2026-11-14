package com.example.myapplication.domain.farm

data class Farm(
    val id: String,
    val name: String,
    val country: String,
    val region: String,
    val commune: String?,
    val fieldCount: Int,
    val createdAtIso: String
)

data class FarmPage(
    val items: List<Farm>,
    val nextCursor: String?,
    val hasMore: Boolean
)

data class FarmWriteInput(
    val name: String,
    val country: String,
    val region: String,
    val commune: String?
)

sealed interface FarmError {
    val message: String

    data class Api(
        val httpStatus: Int,
        val errorCode: String?,
        override val message: String,
        val requestId: String? = null
    ) : FarmError {
        val isUnauthorized: Boolean
            get() = httpStatus == 401 || errorCode == "UNAUTHORIZED"

        val isNotFound: Boolean
            get() = httpStatus == 404 || errorCode == "NOT_FOUND"

        val isGuestLimitReached: Boolean
            get() = httpStatus == 403 && errorCode == "GUEST_LIMIT_REACHED"

        val isConflict: Boolean
            get() = httpStatus == 409 || errorCode == "CONFLICT"

        val isValidationError: Boolean
            get() = httpStatus == 400 || errorCode == "INVALID_INPUT"
    }

    data class Network(
        override val message: String
    ) : FarmError
}

sealed interface FarmResult<out T> {
    data class Success<T>(val data: T) : FarmResult<T>
    data class Failure(val error: FarmError) : FarmResult<Nothing>
}

