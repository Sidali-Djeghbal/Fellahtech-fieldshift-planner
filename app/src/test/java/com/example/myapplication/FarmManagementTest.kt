package com.example.myapplication

import com.example.myapplication.core.common.UiState
import com.example.myapplication.core.network.ApiErrorParser
import com.example.myapplication.core.network.FarmApiService
import com.example.myapplication.core.network.FarmPageDto
import com.example.myapplication.core.network.FarmPatchRequestDto
import com.example.myapplication.core.network.FarmPublicDto
import com.example.myapplication.core.network.FarmWriteRequestDto
import com.example.myapplication.data.farm.FarmRepositoryImpl
import com.example.myapplication.data.farm.toDomain
import com.example.myapplication.data.farm.toWriteRequestDto
import com.example.myapplication.domain.auth.AuthRepository
import com.example.myapplication.domain.auth.AuthResult
import com.example.myapplication.domain.auth.DemoLocation
import com.example.myapplication.domain.auth.DemoParcel
import com.example.myapplication.domain.auth.GuestSessionInfo
import com.example.myapplication.domain.auth.GuestSessionLimits
import com.example.myapplication.domain.auth.GuestSessionUsage
import com.example.myapplication.domain.auth.SessionState
import com.example.myapplication.domain.auth.UserProfile
import com.example.myapplication.domain.farm.Farm
import com.example.myapplication.domain.farm.FarmError
import com.example.myapplication.domain.farm.FarmResult
import com.example.myapplication.domain.farm.FarmWriteInput
import com.example.myapplication.feature.farms.FarmDetailViewModel
import com.example.myapplication.feature.farms.FarmFieldError
import com.example.myapplication.feature.farms.FarmFormViewModel
import com.example.myapplication.feature.farms.FarmsListViewModel
import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
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
class FarmManagementTest {

    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        encodeDefaults = true
    }

    @Test
    fun `farm DTOs serialize and deserialize exact OpenAPI v3_2 fields`() {
        val writeDto = FarmWriteRequestDto(
            farmName = "Atlas Olive Grove",
            country = "Morocco",
            region = "Fes-Meknes",
            commune = "Ain Taoujdate"
        )
        val encoded = json.encodeToString(writeDto)
        assertTrue(encoded.contains(""""farm_name":"Atlas Olive Grove""""))
        assertTrue(encoded.contains(""""commune":"Ain Taoujdate""""))

        val pageJson = """
            {
              "items": [
                {
                  "farm_id": "farm_12",
                  "farm_name": "Saiss Cereal Plot",
                  "country": "Morocco",
                  "region": "Fes-Meknes",
                  "commune": null,
                  "field_count": 3,
                  "created_at": "2026-04-01T09:30:00Z"
                }
              ],
              "next_cursor": "cursor-next",
              "has_more": true
            }
        """.trimIndent()
        val pageDto = json.decodeFromString<FarmPageDto>(pageJson)
        assertEquals(1, pageDto.items.size)
        val farmDto = pageDto.items.first()
        assertEquals("farm_12", farmDto.farmId)
        assertEquals("Saiss Cereal Plot", farmDto.farmName)
        assertNull(farmDto.commune)
        assertEquals(3, farmDto.fieldCount)
        assertEquals("cursor-next", pageDto.nextCursor)
        assertTrue(pageDto.hasMore)

        val domainFarm = farmDto.toDomain()
        assertEquals("farm_12", domainFarm.id)
        assertEquals("Saiss Cereal Plot", domainFarm.name)
        assertEquals(3, domainFarm.fieldCount)

        val mappedWrite = FarmWriteInput(
            name = "  Oasis Dates  ",
            country = " Morocco ",
            region = " Draa-Tafilalet ",
            commune = "   "
        ).toWriteRequestDto()
        assertEquals("Oasis Dates", mappedWrite.farmName)
        assertEquals("Morocco", mappedWrite.country)
        assertEquals("Draa-Tafilalet", mappedWrite.region)
        assertNull(mappedWrite.commune)
    }

    @Test
    fun `farmRepositoryImpl handles CRUD, 404 foreign resource, 403 guest limit, and network errors`() = runTest {
        val api = FakeFarmApiService()
        val repo = FarmRepositoryImpl(api, ApiErrorParser(json))

        // Create
        val created = repo.createFarm(FarmWriteInput("Farm A", "MA", "Fes-Meknes", null))
        assertTrue(created is FarmResult.Success)
        assertEquals("farm_1", (created as FarmResult.Success).data.id)

        // List
        val listed = repo.listFarms()
        assertTrue(listed is FarmResult.Success)
        assertEquals(1, (listed as FarmResult.Success).data.items.size)

        // Update
        val updated = repo.updateFarm("farm_1", FarmWriteInput("Farm A Updated", "MA", "Fes-Meknes", "Meknes"))
        assertTrue(updated is FarmResult.Success)
        assertEquals("Farm A Updated", (updated as FarmResult.Success).data.name)

        // 404 Not Found (foreign-owner resource)
        api.nextGetError = httpException(404, "NOT_FOUND", "Farm not found", "req-404")
        val notFound = repo.getFarm("farm_999")
        assertTrue(notFound is FarmResult.Failure)
        val notFoundErr = (notFound as FarmResult.Failure).error as FarmError.Api
        assertTrue(notFoundErr.isNotFound)
        assertEquals("req-404", notFoundErr.requestId)

        // 403 GUEST_LIMIT_REACHED
        api.nextCreateError = httpException(403, "GUEST_LIMIT_REACHED", "Max guest farms reached", "req-403")
        val guestLimit = repo.createFarm(FarmWriteInput("Farm B", "MA", "Rabat", null))
        assertTrue(guestLimit is FarmResult.Failure)
        val guestErr = (guestLimit as FarmResult.Failure).error as FarmError.Api
        assertTrue(guestErr.isGuestLimitReached)
        assertEquals("GUEST_LIMIT_REACHED", guestErr.errorCode)
        assertEquals("req-403", guestErr.requestId)

        // Delete 204
        val deleted = repo.deleteFarm("farm_1")
        assertTrue(deleted is FarmResult.Success)

        // Network error
        api.nextListError = IOException("Connection reset")
        val netErr = repo.listFarms()
        assertTrue(netErr is FarmResult.Failure)
        assertTrue((netErr as FarmResult.Failure).error is FarmError.Network)
    }

    @Test
    fun `farmsListViewModel manages loading, empty, pagination, refresh, and in-memory updates`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val api = FakeFarmApiService()
            val repo = FarmRepositoryImpl(api, ApiErrorParser(json))
            val authRepo = FakeAuthRepository(guestSession())

            // Initial empty state
            val vm = FarmsListViewModel(repo, authRepo)
            advanceUntilIdle()
            assertTrue(vm.uiState.value.farmsState is UiState.Empty)

            // Upsert farm in memory without full reload
            val newFarm = Farm("farm_10", "Demo Olive", "MA", "Fes", null, 1, "2026-04-01T10:00:00Z")
            vm.onFarmSaved(newFarm)
            val afterSave = vm.uiState.value.farmsState
            assertTrue(afterSave is UiState.Success)
            assertEquals(1, (afterSave as UiState.Success).data.size)

            // Delete in memory
            vm.onFarmDeleted("farm_10")
            assertTrue(vm.uiState.value.farmsState is UiState.Empty)

            // Pagination across 2 pages
            api.pages["first"] = FarmPageDto(
                items = listOf(FarmPublicDto("farm_1", "Page 1 Farm", "MA", "Rabat", null, 0, "2026-04-01T10:00:00Z")),
                nextCursor = "c2",
                hasMore = true
            )
            api.pages["c2"] = FarmPageDto(
                items = listOf(FarmPublicDto("farm_2", "Page 2 Farm", "MA", "Souss", null, 2, "2026-04-01T10:00:00Z")),
                nextCursor = null,
                hasMore = false
            )
            vm.loadFarms()
            advanceUntilIdle()
            assertTrue(vm.uiState.value.hasMore)
            assertEquals(1, (vm.uiState.value.farmsState as UiState.Success).data.size)

            vm.loadMore()
            advanceUntilIdle()
            assertFalse(vm.uiState.value.hasMore)
            assertEquals(2, (vm.uiState.value.farmsState as UiState.Success).data.size)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `farmFormViewModel validates constraints, handles edit load, and surfaces guest limit`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val api = FakeFarmApiService()
            val repo = FarmRepositoryImpl(api, ApiErrorParser(json))

            // Create validation
            val createVm = FarmFormViewModel(repo)
            createVm.initialize(null)
            createVm.submit()
            assertEquals(FarmFieldError.REQUIRED, createVm.uiState.value.nameError)
            assertEquals(FarmFieldError.REQUIRED, createVm.uiState.value.countryError)
            assertEquals(FarmFieldError.REQUIRED, createVm.uiState.value.regionError)

            createVm.onNameChanged("A".repeat(121))
            createVm.onCountryChanged("MA")
            createVm.onRegionChanged("Fes")
            createVm.onCommuneChanged("B".repeat(121))
            createVm.submit()
            assertEquals(FarmFieldError.TOO_LONG, createVm.uiState.value.nameError)
            assertEquals(FarmFieldError.TOO_LONG, createVm.uiState.value.communeError)

            // Guest limit reached on create
            api.nextCreateError = httpException(403, "GUEST_LIMIT_REACHED", "Guest limit", "req-g1")
            createVm.onNameChanged("Valid Farm")
            createVm.onCommuneChanged("")
            createVm.submit()
            advanceUntilIdle()
            val submitErr = createVm.uiState.value.submitError as? FarmError.Api
            assertNotNull(submitErr)
            assertTrue(submitErr!!.isGuestLimitReached)

            // Edit mode loads existing farm and submits update
            api.stored["farm_5"] = FarmPublicDto(
                farmId = "farm_5",
                farmName = "Existing Farm",
                country = "Morocco",
                region = "Oriental",
                commune = "Berkane",
                fieldCount = 2,
                createdAt = "2026-04-01T10:00:00Z"
            )
            val editVm = FarmFormViewModel(repo)
            editVm.initialize("farm_5")
            advanceUntilIdle()
            assertEquals("Existing Farm", editVm.uiState.value.name)
            assertEquals("Berkane", editVm.uiState.value.commune)

            editVm.onNameChanged("Renamed Farm")
            editVm.submit()
            advanceUntilIdle()
            assertEquals("Renamed Farm", editVm.uiState.value.savedFarm?.name)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test
    fun `farmDetailViewModel handles 404, delete confirmation, success, and failure preservation`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        try {
            val api = FakeFarmApiService()
            api.stored["farm_7"] = FarmPublicDto(
                farmId = "farm_7",
                farmName = "Detail Farm",
                country = "Morocco",
                region = "Souss-Massa",
                commune = null,
                fieldCount = 0,
                createdAt = "2026-04-01T10:00:00Z"
            )
            val repo = FarmRepositoryImpl(api, ApiErrorParser(json))
            val vm = FarmDetailViewModel(repo)

            vm.loadFarm("farm_7")
            advanceUntilIdle()
            assertTrue(vm.uiState.value.farmState is UiState.Success)

            // Delete failure preserves screen and exposes error
            api.nextDeleteError = httpException(401, "UNAUTHORIZED", "Expired", "req-del")
            vm.requestDelete()
            assertTrue(vm.uiState.value.showDeleteConfirmation)
            vm.confirmDelete("farm_7")
            advanceUntilIdle()
            assertFalse(vm.uiState.value.deletedSuccessfully)
            assertNotNull(vm.uiState.value.deleteError)

            // Delete success
            vm.confirmDelete("farm_7")
            advanceUntilIdle()
            assertTrue(vm.uiState.value.deletedSuccessfully)
        } finally {
            Dispatchers.resetMain()
        }
    }

    private fun httpException(
        status: Int,
        code: String,
        message: String,
        requestId: String
    ): HttpException {
        val body = """{"error":{"code":"$code","message":"$message","details":[],"request_id":"$requestId"}}"""
            .toResponseBody("application/json".toMediaType())
        return HttpException(Response.error<Any>(status, body))
    }

    private fun guestSession(): SessionState.GuestSession {
        return SessionState.GuestSession(
            GuestSessionInfo(
                demoLocation = DemoLocation(1, "meknes", "Meknes", "MA", "Fes-Meknes"),
                demoParcel = DemoParcel("f1", "Demo", 33.8, -5.5, 4.0, true, emptyList()),
                createdAt = "2026-04-01T00:00:00Z",
                expiresAt = "2026-04-02T00:00:00Z",
                limits = GuestSessionLimits(1, 1, 3, 4),
                usage = GuestSessionUsage(0, 0, 0, 0.0)
            )
        )
    }

    private class FakeFarmApiService : FarmApiService {
        val stored = linkedMapOf<String, FarmPublicDto>()
        val pages = mutableMapOf<String, FarmPageDto>()
        var nextId = 1
        var nextListError: Throwable? = null
        var nextGetError: Throwable? = null
        var nextCreateError: Throwable? = null
        var nextDeleteError: Throwable? = null

        override suspend fun listFarms(
            limit: Int,
            cursor: String?,
            country: String?,
            region: String?,
            search: String?
        ): FarmPageDto {
            nextListError?.let {
                nextListError = null
                throw it
            }
            if (pages.isNotEmpty()) {
                val key = cursor ?: "first"
                return pages[key] ?: FarmPageDto(emptyList(), null, false)
            }
            return FarmPageDto(
                items = stored.values.toList(),
                nextCursor = null,
                hasMore = false
            )
        }

        override suspend fun createFarm(request: FarmWriteRequestDto): FarmPublicDto {
            nextCreateError?.let {
                nextCreateError = null
                throw it
            }
            val id = "farm_${nextId++}"
            val dto = FarmPublicDto(
                farmId = id,
                farmName = request.farmName,
                country = request.country,
                region = request.region,
                commune = request.commune,
                fieldCount = 0,
                createdAt = "2026-04-01T10:00:00Z"
            )
            stored[id] = dto
            return dto
        }

        override suspend fun getFarm(farmId: String): FarmPublicDto {
            nextGetError?.let {
                nextGetError = null
                throw it
            }
            return stored[farmId] ?: throw HttpException(
                Response.error<Any>(
                    404,
                    """{"error":{"code":"NOT_FOUND","message":"Not found","details":[]}}"""
                        .toResponseBody("application/json".toMediaType())
                )
            )
        }

        override suspend fun replaceFarm(farmId: String, request: FarmWriteRequestDto): FarmPublicDto {
            val existing = getFarm(farmId)
            val updated = existing.copy(
                farmName = request.farmName,
                country = request.country,
                region = request.region,
                commune = request.commune
            )
            stored[farmId] = updated
            return updated
        }

        override suspend fun patchFarm(farmId: String, request: FarmPatchRequestDto): FarmPublicDto {
            val existing = getFarm(farmId)
            val updated = existing.copy(
                farmName = request.farmName ?: existing.farmName,
                country = request.country ?: existing.country,
                region = request.region ?: existing.region,
                commune = request.commune ?: existing.commune
            )
            stored[farmId] = updated
            return updated
        }

        override suspend fun deleteFarm(farmId: String): Response<Unit> {
            nextDeleteError?.let {
                nextDeleteError = null
                throw it
            }
            stored.remove(farmId)
            return Response.success(Unit)
        }
    }

    private class FakeAuthRepository(initialState: SessionState) : AuthRepository {
        override val sessionState: StateFlow<SessionState> = MutableStateFlow(initialState)
        override suspend fun restoreSession() = Unit
        override suspend fun login(email: String, password: String): AuthResult<UserProfile> =
            throw UnsupportedOperationException()
        override suspend fun register(
            email: String,
            password: String,
            fullName: String,
            preferredLanguage: com.example.myapplication.core.common.AppLanguage?
        ): AuthResult<UserProfile> = throw UnsupportedOperationException()
        override suspend fun fetchDemoLocations(limit: Int, cursor: String?): AuthResult<List<DemoLocation>> =
            throw UnsupportedOperationException()
        override suspend fun startGuestSession(demoLocationId: Int): AuthResult<GuestSessionInfo> =
            throw UnsupportedOperationException()
        override suspend fun refreshGuestSessionInfo(): AuthResult<GuestSessionInfo> =
            throw UnsupportedOperationException()
        override suspend fun logout(): AuthResult<Unit> = throw UnsupportedOperationException()
        override suspend fun deleteAccount(): AuthResult<Unit> = throw UnsupportedOperationException()
        override suspend fun exitGuestSession(): AuthResult<Unit> = throw UnsupportedOperationException()
        override suspend fun clearSessionLocally() = Unit
    }
}

