package com.example.myapplication.domain.field

interface FieldRepository {
    suspend fun listFields(
        farmId: String,
        limit: Int = 20,
        cursor: String? = null,
        soilType: SoilType? = null,
        waterAvailability: WaterAvailability? = null
    ): FieldResult<FieldPage>

    suspend fun getField(farmId: String, fieldId: String): FieldResult<FieldDetail>

    suspend fun createField(farmId: String, input: FieldWriteInput): FieldResult<FieldSummary>

    suspend fun updateField(
        farmId: String,
        fieldId: String,
        input: FieldWriteInput
    ): FieldResult<FieldDetail>

    suspend fun deleteField(farmId: String, fieldId: String): FieldResult<Unit>
}

