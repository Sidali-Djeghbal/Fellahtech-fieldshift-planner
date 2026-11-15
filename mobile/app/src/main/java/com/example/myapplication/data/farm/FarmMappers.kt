package com.example.myapplication.data.farm

import com.example.myapplication.core.network.ApiCallFailure
import com.example.myapplication.core.network.FarmPageDto
import com.example.myapplication.core.network.FarmPublicDto
import com.example.myapplication.core.network.FarmWriteRequestDto
import com.example.myapplication.domain.farm.Farm
import com.example.myapplication.domain.farm.FarmError
import com.example.myapplication.domain.farm.FarmPage
import com.example.myapplication.domain.farm.FarmWriteInput

fun FarmPublicDto.toDomain(): Farm {
    return Farm(
        id = farmId,
        name = farmName,
        country = country,
        region = region,
        commune = commune,
        fieldCount = fieldCount,
        createdAtIso = createdAt
    )
}

fun FarmPageDto.toDomain(): FarmPage {
    return FarmPage(
        items = items.map { it.toDomain() },
        nextCursor = nextCursor,
        hasMore = hasMore
    )
}

fun FarmWriteInput.toWriteRequestDto(): FarmWriteRequestDto {
    val trimmedCommune = commune?.trim()?.takeIf { it.isNotEmpty() }
    return FarmWriteRequestDto(
        farmName = name.trim(),
        country = country.trim(),
        region = region.trim(),
        commune = trimmedCommune
    )
}

fun ApiCallFailure.toFarmError(): FarmError {
    return when (this) {
        is ApiCallFailure.ApiError -> FarmError.Api(
            httpStatus = httpStatus,
            errorCode = errorCode,
            message = message,
            requestId = requestId
        )
        is ApiCallFailure.NetworkError -> FarmError.Network(
            message = message
        )
    }
}

