package com.example.myapplication.data.farm

import com.example.myapplication.core.network.ApiErrorParser
import com.example.myapplication.core.network.FarmApiService
import com.example.myapplication.domain.farm.Farm
import com.example.myapplication.domain.farm.FarmError
import com.example.myapplication.domain.farm.FarmPage
import com.example.myapplication.domain.farm.FarmRepository
import com.example.myapplication.domain.farm.FarmResult
import com.example.myapplication.domain.farm.FarmWriteInput
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CancellationException
import retrofit2.HttpException

@Singleton
class FarmRepositoryImpl @Inject constructor(
    private val farmApiService: FarmApiService,
    private val errorParser: ApiErrorParser
) : FarmRepository {

    override suspend fun listFarms(
        limit: Int,
        cursor: String?,
        country: String?,
        region: String?,
        search: String?
    ): FarmResult<FarmPage> {
        return safeCall {
            farmApiService.listFarms(
                limit = limit.coerceIn(1, 100),
                cursor = cursor?.takeIf { it.isNotBlank() },
                country = country?.trim()?.takeIf { it.isNotEmpty() },
                region = region?.trim()?.takeIf { it.isNotEmpty() },
                search = search?.trim()?.takeIf { it.isNotEmpty() }
            ).toDomain()
        }
    }

    override suspend fun getFarm(farmId: String): FarmResult<Farm> {
        return safeCall {
            farmApiService.getFarm(farmId).toDomain()
        }
    }

    override suspend fun createFarm(input: FarmWriteInput): FarmResult<Farm> {
        return safeCall {
            farmApiService.createFarm(input.toWriteRequestDto()).toDomain()
        }
    }

    override suspend fun updateFarm(farmId: String, input: FarmWriteInput): FarmResult<Farm> {
        return safeCall {
            farmApiService.replaceFarm(farmId, input.toWriteRequestDto()).toDomain()
        }
    }

    override suspend fun deleteFarm(farmId: String): FarmResult<Unit> {
        return safeCall {
            val response = farmApiService.deleteFarm(farmId)
            if (!response.isSuccessful) {
                throw HttpException(response)
            }
        }
    }

    private suspend inline fun <T> safeCall(crossinline block: suspend () -> T): FarmResult<T> {
        return try {
            FarmResult.Success(block())
        } catch (ce: CancellationException) {
            throw ce
        } catch (t: Throwable) {
            val failure = errorParser.toFailure(t)
            FarmResult.Failure(failure.toFarmError())
        }
    }
}

