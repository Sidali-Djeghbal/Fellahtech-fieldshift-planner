package com.example.myapplication.data.field

import com.example.myapplication.core.network.ApiErrorParser
import com.example.myapplication.core.network.FieldApiService
import com.example.myapplication.domain.field.FieldDetail
import com.example.myapplication.domain.field.FieldPage
import com.example.myapplication.domain.field.FieldRepository
import com.example.myapplication.domain.field.FieldResult
import com.example.myapplication.domain.field.FieldSummary
import com.example.myapplication.domain.field.FieldWriteInput
import com.example.myapplication.domain.field.SoilType
import com.example.myapplication.domain.field.WaterAvailability
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CancellationException
import retrofit2.HttpException

@Singleton
class FieldRepositoryImpl @Inject constructor(
    private val fieldApiService: FieldApiService,
    private val errorParser: ApiErrorParser
) : FieldRepository {

    override suspend fun listFields(
        farmId: String,
        limit: Int,
        cursor: String?,
        soilType: SoilType?,
        waterAvailability: WaterAvailability?
    ): FieldResult<FieldPage> = safeCall {
        fieldApiService.listFields(
            farmId = farmId,
            limit = limit.coerceIn(1, 100),
            cursor = cursor?.takeIf { it.isNotBlank() },
            soilType = soilType?.apiValue,
            waterAvailability = waterAvailability?.apiValue
        ).toDomain()
    }

    override suspend fun getField(farmId: String, fieldId: String): FieldResult<FieldDetail> =
        safeCall {
            fieldApiService.getField(farmId = farmId, fieldId = fieldId).toDomain()
        }

    override suspend fun createField(
        farmId: String,
        input: FieldWriteInput
    ): FieldResult<FieldSummary> = safeCall {
        fieldApiService.createField(
            farmId = farmId,
            request = input.toWriteRequestDto()
        ).toDomain()
    }

    override suspend fun updateField(
        farmId: String,
        fieldId: String,
        input: FieldWriteInput
    ): FieldResult<FieldDetail> = safeCall {
        fieldApiService.replaceField(
            farmId = farmId,
            fieldId = fieldId,
            request = input.toWriteRequestDto()
        ).toDomain()
    }

    override suspend fun deleteField(farmId: String, fieldId: String): FieldResult<Unit> =
        safeCall {
            val response = fieldApiService.deleteField(farmId = farmId, fieldId = fieldId)
            if (!response.isSuccessful) {
                throw HttpException(response)
            }
        }

    private suspend inline fun <T> safeCall(crossinline block: suspend () -> T): FieldResult<T> {
        return try {
            FieldResult.Success(block())
        } catch (ce: CancellationException) {
            throw ce
        } catch (t: Throwable) {
            FieldResult.Failure(errorParser.toFailure(t).toFieldError())
        }
    }
}

