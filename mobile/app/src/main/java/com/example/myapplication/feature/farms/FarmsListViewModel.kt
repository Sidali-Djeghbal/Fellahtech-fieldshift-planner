package com.example.myapplication.feature.farms

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.myapplication.core.common.UiState
import com.example.myapplication.domain.auth.AuthRepository
import com.example.myapplication.domain.auth.SessionState
import com.example.myapplication.domain.farm.Farm
import com.example.myapplication.domain.farm.FarmError
import com.example.myapplication.domain.farm.FarmRepository
import com.example.myapplication.domain.farm.FarmResult
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class FarmsListUiState(
    val farmsState: UiState<List<Farm>> = UiState.Loading,
    val searchQuery: String = "",
    val isRefreshing: Boolean = false,
    val isLoadingMore: Boolean = false,
    val nextCursor: String? = null,
    val hasMore: Boolean = false,
    val paginationError: FarmError? = null,
    val lastError: FarmError? = null
)

@HiltViewModel
class FarmsListViewModel @Inject constructor(
    private val farmRepository: FarmRepository,
    authRepository: AuthRepository
) : ViewModel() {

    val sessionState: StateFlow<SessionState> = authRepository.sessionState

    private val _uiState = MutableStateFlow(FarmsListUiState())
    val uiState: StateFlow<FarmsListUiState> = _uiState.asStateFlow()

    init {
        loadFarms()
    }

    fun loadFarms() {
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    farmsState = UiState.Loading,
                    isRefreshing = false,
                    isLoadingMore = false,
                    paginationError = null,
                    lastError = null
                )
            }
            fetchFirstPage(isRefresh = false)
        }
    }

    fun refresh() {
        if (_uiState.value.isRefreshing) return
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isRefreshing = true,
                    paginationError = null,
                    lastError = null
                )
            }
            fetchFirstPage(isRefresh = true)
        }
    }

    fun onSearchQueryChanged(query: String) {
        _uiState.update { it.copy(searchQuery = query) }
    }

    fun submitSearch() {
        loadFarms()
    }

    fun loadMore() {
        val current = _uiState.value
        val cursor = current.nextCursor
        if (!current.hasMore || cursor.isNullOrBlank() || current.isLoadingMore) return

        val existingItems = (current.farmsState as? UiState.Success)?.data ?: return

        viewModelScope.launch {
            _uiState.update { it.copy(isLoadingMore = true, paginationError = null) }
            when (val result = farmRepository.listFarms(
                cursor = cursor,
                search = current.searchQuery
            )) {
                is FarmResult.Success -> {
                    val combined = (existingItems + result.data.items).distinctBy { it.id }
                    _uiState.update {
                        it.copy(
                            farmsState = if (combined.isEmpty()) UiState.Empty else UiState.Success(combined),
                            isLoadingMore = false,
                            nextCursor = result.data.nextCursor,
                            hasMore = result.data.hasMore
                        )
                    }
                }
                is FarmResult.Failure -> {
                    _uiState.update {
                        it.copy(
                            isLoadingMore = false,
                            paginationError = result.error
                        )
                    }
                }
            }
        }
    }

    fun onFarmSaved(farm: Farm) {
        _uiState.update { current ->
            val existing = (current.farmsState as? UiState.Success)?.data.orEmpty()
            val updated = if (existing.any { it.id == farm.id }) {
                existing.map { if (it.id == farm.id) farm else it }
            } else {
                listOf(farm) + existing
            }
            current.copy(
                farmsState = UiState.Success(updated),
                lastError = null
            )
        }
    }

    fun onFarmDeleted(farmId: String) {
        _uiState.update { current ->
            val existing = (current.farmsState as? UiState.Success)?.data ?: return@update current
            val remaining = existing.filterNot { it.id == farmId }
            current.copy(
                farmsState = if (remaining.isEmpty()) UiState.Empty else UiState.Success(remaining)
            )
        }
    }

    private suspend fun fetchFirstPage(isRefresh: Boolean) {
        val query = _uiState.value.searchQuery
        when (val result = farmRepository.listFarms(search = query)) {
            is FarmResult.Success -> {
                val page = result.data
                _uiState.update {
                    it.copy(
                        farmsState = if (page.items.isEmpty()) UiState.Empty else UiState.Success(page.items),
                        isRefreshing = false,
                        nextCursor = page.nextCursor,
                        hasMore = page.hasMore,
                        lastError = null
                    )
                }
            }
            is FarmResult.Failure -> {
                _uiState.update { current ->
                    val keepExisting = isRefresh && current.farmsState is UiState.Success
                    current.copy(
                        farmsState = if (keepExisting) current.farmsState else UiState.Error(result.error.message),
                        isRefreshing = false,
                        lastError = result.error
                    )
                }
            }
        }
    }
}

