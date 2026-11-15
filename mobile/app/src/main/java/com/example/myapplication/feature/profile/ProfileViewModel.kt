package com.example.myapplication.feature.profile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.myapplication.domain.auth.AuthRepository
import com.example.myapplication.domain.auth.AuthResult
import com.example.myapplication.domain.auth.SessionState
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ProfileUiState(
    val isBusy: Boolean = false,
    val showDeleteConfirmation: Boolean = false,
    val errorMessage: String? = null
)

@HiltViewModel
class ProfileViewModel @Inject constructor(
    private val authRepository: AuthRepository
) : ViewModel() {

    val sessionState: StateFlow<SessionState> = authRepository.sessionState

    private val _uiState = MutableStateFlow(ProfileUiState())
    val uiState: StateFlow<ProfileUiState> = _uiState.asStateFlow()

    fun logout() {
        if (_uiState.value.isBusy) return
        viewModelScope.launch {
            _uiState.update { it.copy(isBusy = true, errorMessage = null) }
            when (val result = authRepository.logout()) {
                is AuthResult.Success -> _uiState.update { it.copy(isBusy = false) }
                is AuthResult.Failure -> _uiState.update {
                    it.copy(isBusy = false, errorMessage = result.failure.message)
                }
            }
        }
    }

    fun requestDeleteAccount() {
        _uiState.update { it.copy(showDeleteConfirmation = true, errorMessage = null) }
    }

    fun dismissDeleteConfirmation() {
        _uiState.update { it.copy(showDeleteConfirmation = false) }
    }

    fun confirmDeleteAccount() {
        if (_uiState.value.isBusy) return
        viewModelScope.launch {
            _uiState.update {
                it.copy(isBusy = true, showDeleteConfirmation = false, errorMessage = null)
            }
            when (val result = authRepository.deleteAccount()) {
                is AuthResult.Success -> _uiState.update { it.copy(isBusy = false) }
                is AuthResult.Failure -> _uiState.update {
                    it.copy(isBusy = false, errorMessage = result.failure.message)
                }
            }
        }
    }

    fun refreshGuestSession() {
        if (_uiState.value.isBusy) return
        viewModelScope.launch {
            _uiState.update { it.copy(isBusy = true, errorMessage = null) }
            when (val result = authRepository.refreshGuestSessionInfo()) {
                is AuthResult.Success -> _uiState.update { it.copy(isBusy = false) }
                is AuthResult.Failure -> _uiState.update {
                    it.copy(isBusy = false, errorMessage = result.failure.message)
                }
            }
        }
    }

    fun exitGuestSession() {
        if (_uiState.value.isBusy) return
        viewModelScope.launch {
            _uiState.update { it.copy(isBusy = true, errorMessage = null) }
            when (val result = authRepository.exitGuestSession()) {
                is AuthResult.Success -> _uiState.update { it.copy(isBusy = false) }
                is AuthResult.Failure -> _uiState.update {
                    it.copy(isBusy = false, errorMessage = result.failure.message)
                }
            }
        }
    }
}

