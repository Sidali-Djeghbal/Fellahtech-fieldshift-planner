package com.example.myapplication

import com.example.myapplication.core.common.UiState
import com.example.myapplication.core.location.GpsLocationResult
import com.example.myapplication.core.location.LocationProvider
import com.example.myapplication.core.network.ApiErrorParser
import com.example.myapplication.core.network.CropHistoryWriteItemDto
import com.example.myapplication.core.network.FieldApiService
import com.example.myapplication.core.network.FieldDetailPublicDto
import com.example.myapplication.core.network.FieldLocationDto
import com.example.myapplication.core.network.FieldPageDto
import com.example.myapplication.core.network.FieldPatchRequestDto
import com.example.myapplication.core.network.FieldPublicDto
import com.example.myapplication.core.network.FieldSoilPublicDto
import com.example.myapplication.core.network.FieldSoilWriteDto
import com.example.myapplication.core.network.FieldWaterDto
import com.example.myapplication.core.network.FieldWriteRequestDto
import com.example.myapplication.data.field.FieldRepositoryImpl
import com.example.myapplication.data.field.toDomain
import com.example.myapplication.data.field.toWriteRequestDto
import com.example.myapplication.domain.auth.WarningNotice
import com.example.myapplication.domain.field.CropHistoryEntry
import com.example.myapplication.domain.field.FieldDetail
import com.example.myapplication.domain.field.FieldError
import com.example.myapplication.domain.field.FieldLocation
import com.example.myapplication.domain.field.FieldPage
import com.example.myapplication.domain.field.FieldRepository
import com.example.myapplication.domain.field.FieldResult
import com.example.myapplication.domain.field.FieldSoil
import com.example.myapplication.domain.field.FieldSummary
import com.example.myapplication.domain.field.FieldWater
import com.example.myapplication.domain.field.FieldWriteInput
import com.example.myapplication.domain.field.IrrigationSystem
import com.example.myapplication.domain.field.Season
import com.example.myapplication.domain.field.SoilSource
import com.example.myapplication.domain.field.SoilType
import com.example.myapplication.domain.field.WaterAvailability
import com.example.myapplication.domain.field.WaterSource
import com.example.myapplication.feature.fields.FieldDetailViewModel
import com.example.myapplication.feature.fields.FieldFormValidationError
import com.example.myapplication.feature.fields.FieldFormViewModel
import com.example.myapplication.feature.fields.FieldsListViewModel
import com.example.myapplication.feature.fields.GpsCaptureStatus
import java.io.IOException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response

@OptIn(ExperimentalCoroutinesApi::class)
class FieldManagementTest {

    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        encodeDefaults = true
    }

    @Test
    fun `field DTOs serialize and deserialize exact OpenAPI v3_2 fields`() {
        val writeDto = FieldWriteRequestDto(
            fieldId = "field_north_01",
            fieldName = "North Olive Parcel",
            isUnverifiedDemoParcel = false,
            location = FieldLocationDto(
                latitude = 35.67,
                longitude = -5.89
            ),
            areaHectares = 4.5,
            elevationM = 120.0,
            soil = FieldSoilWriteDto(
                soilType = "loamy",
                soilPh = 6.8,
                organicMatterPercent = 2.4,
                soilTestDate = "2026-03-01"
            ),
            water = FieldWaterDto(
                availability = "moderate",
                source = "well",
                sourceOther = null,
                irrigationSystem = "drip"
            ),
            cropHistory = listOf(
                CropHistoryWriteItemDto(
                    season = "spring",
                    year = 2025,
                    cropNameRaw = "Tomatoes",
                    yieldTonsPerHectare = 18.0
                )
            )
        )

        val encoded = json.encodeToString(writeDto)
        assertTrue(encoded.contains("\"field_id\":\"field_north_01\""))
        assertTrue(encoded.contains("\"area_hectares\":4.5"))
        assertTrue(encoded.contains("\"soil_type\":\"loamy\""))
        assertFalse(encoded.contains("\"source\":\"farmer\""))
        assertTrue(encoded.contains("\"crop_history\""))

        val detailPayload = """
            {
              "field_id": "field_north_01",
              "farm_id": "farm_1",
              "field_name": "North Olive Parcel",
              "is_unverified_demo_parcel": false,
              "location": {"latitude": 35.67, "longitude": -5.89},
              "area_hectares": 4.5,
              "elevation_m": 120.0,
              "soil": {"soil_type": "loamy", "source": "farmer", "soil_ph": 6.8, "organic_matter_percent": 2.4, "soil_test_date": "2026-03-01"},
              "water": {"availability": "moderate", "source": "well", "irrigation_system": "drip"},
              "warnings": [{"code": "MVP_OUTSIDE_COVERAGE", "message": "Field lies outside MVP coverage"}],
              "crop_history": [{"season": "spring", "year": 2025, "crop_id": "tomato", "crop_name_raw": "Tomatoes", "yield_tons_per_hectare": 18.0}]
            }
        """.trimIndent()

        val decoded = json.decodeFromString<FieldDetailPublicDto>(detailPayload).toDomain()
        assertEquals("field_north_01", decoded.fieldId)
        assertEquals(120.0, decoded.elevationM ?: 0.0, 0.01)
        assertEquals(SoilType.LOAMY, decoded.soil.soilType)
        assertEquals(SoilSource.FARMER, decoded.soil.source)
        assertEquals(WaterAvailability.MODERATE, decoded.water.availability)
        assertEquals(WaterSource.WELL, decoded.water.source)
        assertEquals(IrrigationSystem.DRIP, decoded.water.irrigationSystem)
        assertEquals(1, decoded.cropHistory.size)
        assertEquals(Season.SPRING, decoded.cropHistory.first().season)
        assertEquals(1, decoded.warnings.size)
        assertEquals("MVP_OUTSIDE_COVERAGE", decoded.warnings.first().code)
    }

    @Test
    fun `field write input mapper omits soil source and preserves water source_other`() {
        val input = FieldWriteInput(
            fieldId = "field_a",
            fieldName = "Parcel A",
            isUnverifiedDemoParcel = false,
            location = FieldLocation(latitude = 33.9, longitude = -5.5),
            areaHectares = 2.0,
            soilType = SoilType.CLAY,
            soilPh = 7.1,
            organicMatterPercent = 3.0,
            soilTestDate = "2026-01-15",
            waterAvailability = WaterAvailability.LIMITED,
            waterSource = WaterSource.OTHER,
            waterSourceOther = "Canal",
            irrigationSystem = IrrigationSystem.RAINFED,
            cropHistory = listOf(
                CropHistoryEntry(
                    season = Season.WINTER,
                    year = 2025,
                    cropNameRaw = "Wheat"
                )
            )
        )

        val dto = input.toWriteRequestDto()
        assertEquals("clay", dto.soil.soilType)
        assertEquals("other", dto.water.source)
        assertEquals("Canal", dto.water.sourceOther)
        assertEquals("winter", dto.cropHistory.first().season)
    }

    @Test
    fun `FieldRepositoryImpl maps 403 GUEST_LIMIT_REACHED 404 409 422 OUTSIDE_DEMO_BOUNDARY and IOException`() = runTest {
        val api = FakeFieldApiService()
        val repo = FieldRepositoryImpl(api, ApiErrorParser(json))
        val input = sampleFieldWriteInput()

        api.createException = httpException(
            403,
            """{"error":{"code":"GUEST_LIMIT_REACHED","message":"Guest field limit reached"}}"""
        )
        val guestLimit = repo.createField("farm_1", input)
        assertTrue(guestLimit is FieldResult.Failure)
        assertTrue(((guestLimit as FieldResult.Failure).error as FieldError.Api).isGuestLimitReached)

        api.createException = httpException(
            409,
            """{"error":{"code":"CONFLICT","message":"Field id already exists"}}"""
        )
        val conflict = repo.createField("farm_1", input)
        assertTrue(conflict is FieldResult.Failure)
        assertTrue(((conflict as FieldResult.Failure).error as FieldError.Api).isConflict)

        api.createException = httpException(
            422,
            """{"error":{"code":"OUTSIDE_DEMO_BOUNDARY","message":"Coordinates outside demo parcel"}}"""
        )
        val outsideBoundary = repo.createField("farm_1", input)
        assertTrue(outsideBoundary is FieldResult.Failure)
        assertTrue(((outsideBoundary as FieldResult.Failure).error as FieldError.Api).isOutsideDemoBoundary)

        api.getException = httpException(
            404,
            """{"error":{"code":"NOT_FOUND","message":"Field not found"}}"""
        )
        val notFound = repo.getField("farm_1", "missing")
        assertTrue(notFound is FieldResult.Failure)
        assertTrue(((notFound as FieldResult.Failure).error as FieldError.Api).isNotFound)

        api.listException = IOException("Offline")
        val networkErr = repo.listFields("farm_1")
        assertTrue(networkErr is FieldResult.Failure)
        assertTrue((networkErr as FieldResult.Failure).error is FieldError.Network)
    }

    @Test
    fun `FieldsListViewModel supports loading, empty, pagination, soil filter, and in-memory updates`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val repo = FakeFieldRepository()
            repo.pageResponses["null"] = FieldResult.Success(
                FieldPage(
                    items = listOf(sampleFieldSummary("f1", "Parcel 1")),
                    nextCursor = "cursor_2",
                    hasMore = true
                )
            )
            repo.pageResponses["cursor_2"] = FieldResult.Success(
                FieldPage(
                    items = listOf(sampleFieldSummary("f2", "Parcel 2")),
                    nextCursor = null,
                    hasMore = false
                )
            )

            val vm = FieldsListViewModel(repo)
            vm.initialize("farm_1")
            advanceUntilIdle()

            val firstState = vm.uiState.value.fieldsState as UiState.Success
            assertEquals(1, firstState.data.size)
            assertTrue(vm.uiState.value.hasMore)

            vm.loadMore()
            advanceUntilIdle()
            val secondState = vm.uiState.value.fieldsState as UiState.Success
            assertEquals(2, secondState.data.size)
            assertFalse(vm.uiState.value.hasMore)

            vm.onFieldSaved(sampleFieldSummary("f3", "Parcel 3"))
            val afterSave = vm.uiState.value.fieldsState as UiState.Success
            assertEquals(3, afterSave.data.size)
            assertEquals("f3", afterSave.data.first().fieldId)

            vm.onFieldDeleted("f3")
            val afterDelete = vm.uiState.value.fieldsState as UiState.Success
            assertEquals(2, afterDelete.data.size)

            repo.pageResponses["null"] = FieldResult.Success(
                FieldPage(items = emptyList(), nextCursor = null, hasMore = false)
            )
            vm.setSoilFilter(SoilType.SANDY)
            advanceUntilIdle()
            assertTrue(vm.uiState.value.fieldsState is UiState.Empty)
            assertEquals(SoilType.SANDY, repo.lastSoilFilter)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `FieldDetailViewModel loads field, handles 404, and handles delete confirmation and failure`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val repo = FakeFieldRepository()
            val vm = FieldDetailViewModel(repo)

            repo.getResult = FieldResult.Failure(
                FieldError.Api(httpStatus = 404, errorCode = "NOT_FOUND", message = "Field not found")
            )
            vm.loadField("farm_1", "f1")
            advanceUntilIdle()
            assertTrue(vm.uiState.value.fieldState is UiState.Error)
            assertTrue((vm.uiState.value.fieldError as FieldError.Api).isNotFound)

            repo.getResult = FieldResult.Success(sampleFieldDetail("f1", "Parcel 1"))
            vm.loadField("farm_1", "f1", forceRefresh = true)
            advanceUntilIdle()
            assertTrue(vm.uiState.value.fieldState is UiState.Success)

            vm.requestDelete()
            assertTrue(vm.uiState.value.showDeleteConfirmation)

            repo.deleteResult = FieldResult.Failure(FieldError.Network("No internet"))
            vm.confirmDelete("farm_1", "f1")
            advanceUntilIdle()
            assertFalse(vm.uiState.value.deletedSuccessfully)
            assertNotNull(vm.uiState.value.deleteError)

            repo.deleteResult = FieldResult.Success(Unit)
            vm.confirmDelete("farm_1", "f1")
            advanceUntilIdle()
            assertTrue(vm.uiState.value.deletedSuccessfully)
            assertNull(vm.uiState.value.deleteError)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `FieldFormViewModel validates inputs, handles GPS states, prevents duplicate submit, and preserves warnings`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val repo = FakeFieldRepository()
            val locationProvider = FakeLocationProvider()
            val vm = FieldFormViewModel(repo, locationProvider)

            vm.initialize("farm_1", null)
            vm.onFieldIdChanged("field_01")
            vm.onFieldNameChanged("South Plot")
            vm.onLatitudeChanged("35.5")
            vm.onLongitudeChanged("-5.8")
            vm.onAreaChanged("-1")
            vm.updateCropHistoryRow(vm.uiState.value.cropHistory.first().rowId) {
                it.copy(cropNameRaw = "Barley", yearText = "2025")
            }
            vm.submit()
            assertEquals(FieldFormValidationError.AREA_INVALID, vm.uiState.value.validationError)

            vm.onAreaChanged("10001")
            vm.submit()
            assertEquals(FieldFormValidationError.AREA_INVALID, vm.uiState.value.validationError)

            vm.onAreaChanged("3.5")
            vm.onSoilPhChanged("12.0")
            vm.submit()
            assertEquals(FieldFormValidationError.SOIL_PH_INVALID, vm.uiState.value.validationError)

            vm.onSoilPhChanged("6.5")
            vm.onSoilTestDateChanged("2026/01/01")
            vm.submit()
            assertEquals(FieldFormValidationError.SOIL_TEST_DATE_INVALID, vm.uiState.value.validationError)

            vm.onSoilTestDateChanged("2026-01-01")

            vm.onLocationPermissionDenied()
            assertEquals(GpsCaptureStatus.PERMISSION_DENIED, vm.uiState.value.gpsStatus)

            locationProvider.nextResult = GpsLocationResult.Timeout
            vm.captureDeviceGps()
            advanceUntilIdle()
            assertEquals(GpsCaptureStatus.TIMEOUT, vm.uiState.value.gpsStatus)

            locationProvider.nextResult = GpsLocationResult.LocationUnavailable
            vm.captureDeviceGps()
            advanceUntilIdle()
            assertEquals(GpsCaptureStatus.UNAVAILABLE, vm.uiState.value.gpsStatus)

            locationProvider.nextResult = GpsLocationResult.Success(34.02, -6.84, 8.5f)
            vm.captureDeviceGps()
            advanceUntilIdle()
            assertEquals(GpsCaptureStatus.CAPTURED, vm.uiState.value.gpsStatus)
            assertEquals("34.02", vm.uiState.value.latitudeText)
            assertEquals("-6.84", vm.uiState.value.longitudeText)

            val gate = CompletableDeferred<FieldResult<FieldSummary>>()
            repo.deferredCreate = gate
            vm.submit()
            advanceUntilIdle()
            assertTrue(vm.uiState.value.isSubmitting)
            vm.submit()
            assertEquals(1, repo.createCalls)

            gate.complete(
                FieldResult.Failure(
                    FieldError.Api(422, "OUTSIDE_DEMO_BOUNDARY", "Outside demo parcel")
                )
            )
            advanceUntilIdle()
            assertFalse(vm.uiState.value.isSubmitting)
            assertNotNull(vm.uiState.value.submitError)
            assertEquals("South Plot", vm.uiState.value.fieldName)

            repo.deferredCreate = null
            val warning = WarningNotice("MVP_OUTSIDE_COVERAGE", "Field lies outside MVP coverage", emptyList())
            repo.createResult = FieldResult.Success(
                sampleFieldSummary(
                    fieldId = "field_01",
                    fieldName = "South Plot",
                    warnings = listOf(warning)
                )
            )
            vm.submit()
            advanceUntilIdle()
            assertEquals("field_01", vm.uiState.value.savedField?.fieldId)
            assertEquals(listOf(warning), vm.uiState.value.savedField?.warnings)
        } finally {
            Dispatchers.resetMain()
        }
    }

    private fun httpException(code: Int, body: String): HttpException {
        val responseBody = body.toResponseBody("application/json".toMediaType())
        return HttpException(Response.error<Any>(code, responseBody))
    }

    private fun sampleFieldWriteInput() = FieldWriteInput(
        fieldId = "field_01",
        fieldName = "North Field",
        isUnverifiedDemoParcel = false,
        location = FieldLocation(35.6, -5.9),
        areaHectares = 5.0,
        elevationM = 100.0,
        soilType = SoilType.LOAMY,
        waterAvailability = WaterAvailability.MODERATE,
        waterSource = WaterSource.WELL,
        waterSourceOther = null,
        irrigationSystem = IrrigationSystem.DRIP,
        cropHistory = listOf(CropHistoryEntry(Season.SPRING, 2025, cropNameRaw = "Tomatoes"))
    )

    private fun sampleFieldSummary(
        fieldId: String,
        fieldName: String,
        warnings: List<WarningNotice> = emptyList()
    ) = FieldSummary(
        farmId = "farm_1",
        fieldId = fieldId,
        fieldName = fieldName,
        isUnverifiedDemoParcel = false,
        location = FieldLocation(35.6, -5.9),
        areaHectares = 5.0,
        elevationM = 100.0,
        soil = FieldSoil(SoilType.LOAMY, SoilSource.FARMER),
        water = FieldWater(WaterAvailability.MODERATE, WaterSource.WELL, null, IrrigationSystem.DRIP),
        warnings = warnings
    )

    private fun sampleFieldDetail(fieldId: String, fieldName: String) = FieldDetail(
        farmId = "farm_1",
        fieldId = fieldId,
        fieldName = fieldName,
        isUnverifiedDemoParcel = false,
        location = FieldLocation(35.6, -5.9),
        areaHectares = 5.0,
        elevationM = 100.0,
        soil = FieldSoil(SoilType.LOAMY, SoilSource.FARMER),
        water = FieldWater(WaterAvailability.MODERATE, WaterSource.WELL, null, IrrigationSystem.DRIP),
        cropHistory = listOf(CropHistoryEntry(Season.SPRING, 2025, cropNameRaw = "Tomatoes")),
        warnings = emptyList()
    )

    private class FakeLocationProvider : LocationProvider {
        var permissionGranted: Boolean = true
        var nextResult: GpsLocationResult = GpsLocationResult.Success(34.0, -6.8, 10f)
        override fun hasLocationPermission(): Boolean = permissionGranted
        override suspend fun getCurrentCoordinates(): GpsLocationResult = nextResult
    }

    private class FakeFieldRepository : FieldRepository {
        val pageResponses = mutableMapOf<String, FieldResult<FieldPage>>()
        var lastSoilFilter: SoilType? = null
        var getResult: FieldResult<FieldDetail> = FieldResult.Failure(FieldError.Network("unset"))
        var createResult: FieldResult<FieldSummary> = FieldResult.Failure(FieldError.Network("unset"))
        var updateResult: FieldResult<FieldDetail> = FieldResult.Failure(FieldError.Network("unset"))
        var deleteResult: FieldResult<Unit> = FieldResult.Success(Unit)
        var deferredCreate: CompletableDeferred<FieldResult<FieldSummary>>? = null
        var createCalls: Int = 0

        override suspend fun listFields(
            farmId: String,
            limit: Int,
            cursor: String?,
            soilType: SoilType?,
            waterAvailability: WaterAvailability?
        ): FieldResult<FieldPage> {
            lastSoilFilter = soilType
            return pageResponses[cursor ?: "null"]
                ?: FieldResult.Success(FieldPage(emptyList(), null, false))
        }

        override suspend fun getField(farmId: String, fieldId: String): FieldResult<FieldDetail> =
            getResult

        override suspend fun createField(
            farmId: String,
            input: FieldWriteInput
        ): FieldResult<FieldSummary> {
            createCalls++
            return deferredCreate?.await() ?: createResult
        }

        override suspend fun updateField(
            farmId: String,
            fieldId: String,
            input: FieldWriteInput
        ): FieldResult<FieldDetail> = updateResult

        override suspend fun deleteField(farmId: String, fieldId: String): FieldResult<Unit> =
            deleteResult
    }

    private class FakeFieldApiService : FieldApiService {
        var listException: Throwable? = null
        var createException: Throwable? = null
        var getException: Throwable? = null

        override suspend fun listFields(
            farmId: String,
            limit: Int,
            cursor: String?,
            soilType: String?,
            waterAvailability: String?
        ): FieldPageDto {
            listException?.let { throw it }
            return FieldPageDto(items = emptyList(), nextCursor = null, hasMore = false)
        }

        override suspend fun createField(farmId: String, request: FieldWriteRequestDto): FieldPublicDto {
            createException?.let { throw it }
            return FieldPublicDto(
                farmId = farmId,
                fieldId = request.fieldId,
                fieldName = request.fieldName,
                isUnverifiedDemoParcel = request.isUnverifiedDemoParcel,
                location = request.location,
                areaHectares = request.areaHectares,
                elevationM = request.elevationM,
                soil = FieldSoilPublicDto(soilType = request.soil.soilType, source = "farmer"),
                water = request.water
            )
        }

        override suspend fun getField(farmId: String, fieldId: String): FieldDetailPublicDto {
            getException?.let { throw it }
            return FieldDetailPublicDto(
                farmId = farmId,
                fieldId = fieldId,
                fieldName = "Test",
                isUnverifiedDemoParcel = false,
                location = FieldLocationDto(35.0, -5.0),
                areaHectares = 2.0,
                elevationM = 50.0,
                soil = FieldSoilPublicDto(soilType = "loamy", source = "farmer"),
                water = FieldWaterDto("moderate", "well", null, "drip"),
                cropHistory = listOf(CropHistoryWriteItemDto(season = "spring", year = 2025, cropNameRaw = "Wheat"))
            )
        }

        override suspend fun replaceField(
            farmId: String,
            fieldId: String,
            request: FieldWriteRequestDto
        ): FieldDetailPublicDto = getField(farmId, fieldId)

        override suspend fun patchField(
            farmId: String,
            fieldId: String,
            request: FieldPatchRequestDto
        ): FieldDetailPublicDto = getField(farmId, fieldId)

        override suspend fun deleteField(farmId: String, fieldId: String): Response<Unit> =
            Response.success(Unit)
    }
}
