package com.example.myapplication.domain.farm

interface FarmRepository {
    suspend fun listFarms(
        limit: Int = 20,
        cursor: String? = null,
        country: String? = null,
        region: String? = null,
        search: String? = null
    ): FarmResult<FarmPage>

    suspend fun getFarm(farmId: String): FarmResult<Farm>

    suspend fun createFarm(input: FarmWriteInput): FarmResult<Farm>

    suspend fun updateFarm(farmId: String, input: FarmWriteInput): FarmResult<Farm>

    suspend fun deleteFarm(farmId: String): FarmResult<Unit>
}

