package com.example.myapplication.feature.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.myapplication.core.common.AppLanguage
import com.example.myapplication.core.common.UiState
import com.example.myapplication.domain.auth.AuthRepository
import com.example.myapplication.domain.auth.AuthResult
import com.example.myapplication.domain.auth.DemoLocation
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class AuthEntryTab {
    LOGIN,
    REGISTER,
    GUEST
}

enum class AuthValidationError {
    INVALID_EMAIL,
    PASSWORD_REQUIRED,
    PASSWORD_TOO_SHORT,
    NAME_REQUIRED,
    DEMO_LOCATION_REQUIRED
}

data class AuthUiState(
    val activeTab: AuthEntryTab = AuthEntryTab.LOGIN,
    val email: String = "",
    val password: String = "",
    val fullName: String = "",
    val preferredLanguage: AppLanguage = AppLanguage.ENGLISH,
    val demoLocationsState: UiState<List<DemoLocation>> = UiState.Empty,
    val selectedDemoLocationId: Int? = null,
    val isSubmitting: Boolean = false,
    val validationError: AuthValidationError? = null,
    val errorMessage: String? = null
)

@HiltViewModel
class AuthViewModel @Inject constructor(
    private val authRepository: AuthRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(AuthUiState())
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    fun selectTab(tab: AuthEntryTab) {
        _uiState.update {
            it.copy(
                activeTab = tab,
                validationError = null,
                errorMessage = null
            )
        }
        if (tab == AuthEntryTab.GUEST && _uiState.value.demoLocationsState is UiState.Empty) {
            loadDemoLocations()
        }
    }

    fun onEmailChanged(value: String) {
        _uiState.update { it.copy(email = value, validationError = null, errorMessage = null) }
    }

    fun onPasswordChanged(value: String) {
        _uiState.update { it.copy(password = value, validationError = null, errorMessage = null) }
    }

    fun onFullNameChanged(value: String) {
        _uiState.update { it.copy(fullName = value, validationError = null, errorMessage = null) }
    }

    fun onPreferredLanguageChanged(language: AppLanguage) {
        _uiState.update { it.copy(preferredLanguage = language) }
    }

    fun onDemoLocationSelected(locationId: Int) {
        _uiState.update {
            it.copy(
                selectedDemoLocationId = locationId,
                validationError = null,
                errorMessage = null
            )
        }
    }

    fun loadDemoLocations() {
        viewModelScope.launch {
            _uiState.update { it.copy(demoLocationsState = UiState.Loading, errorMessage = null) }
            when (val result = authRepository.fetchDemoLocations()) {
                is AuthResult.Success -> {
                    val locations = result.data
                    _uiState.update { state ->
                        val nextSelected = state.selectedDemoLocationId
                            ?.takeIf { id -> locations.any { it.id == id } }
                            ?: locations.firstOrNull()?.id
                        state.copy(
                            demoLocationsState = if (locations.isEmpty()) {
                                UiState.Empty
                            } else {
                                UiState.Success(locations)
                            },
                            selectedDemoLocationId = nextSelected
                        )
                    }
                }
                is AuthResult.Failure -> {
                    _uiState.update {
                        it.copy(
                            demoLocationsState = UiState.Error(result.failure.message.orEmpty())
                        )
                    }
                }
            }
        }
    }

    fun submitLogin() {
        val current = _uiState.value
        if (current.isSubmitting) return

        val email = current.email.trim()
        if (!isValidEmail(email)) {
            _uiState.update { it.copy(validationError = AuthValidationError.INVALID_EMAIL) }
            return
        }
        if (current.password.isEmpty()) {
            _uiState.update { it.copy(validationError = AuthValidationError.PASSWORD_REQUIRED) }
            return
        }

        viewModelScope.launch {
            _uiState.update { it.copy(isSubmitting = true, validationError = null, errorMessage = null) }
            when (val result = authRepository.login(email = email, password = current.password)) {
                is AuthResult.Success -> {
                    _uiState.update { it.copy(isSubmitting = false, password = "") }
                }
                is AuthResult.Failure -> {
                    _uiState.update {
                        it.copy(isSubmitting = false, errorMessage = result.failure.message)
                    }
                }
            }
        }
    }

    fun submitRegister() {
        val current = _uiState.value
        if (current.isSubmitting) return

        val email = current.email.trim()
        val fullName = current.fullName.trim()

        when {
            fullName.isEmpty() -> {
                _uiState.update { it.copy(validationError = AuthValidationError.NAME_REQUIRED) }
                return
            }
            !isValidEmail(email) -> {
                _uiState.update { it.copy(validationError = AuthValidationError.INVALID_EMAIL) }
                return
            }
            current.password.length < 8 -> {
                _uiState.update { it.copy(validationError = AuthValidationError.PASSWORD_TOO_SHORT) }
                return
            }
        }

        viewModelScope.launch {
            _uiState.update { it.copy(isSubmitting = true, validationError = null, errorMessage = null) }
            val result = authRepository.register(
                email = email,
                password = current.password,
                fullName = fullName,
                preferredLanguage = current.preferredLanguage
            )
            when (result) {
                is AuthResult.Success -> {
                    _uiState.update { it.copy(isSubmitting = false, password = "") }
                }
                is AuthResult.Failure -> {
                    _uiState.update {
                        it.copy(isSubmitting = false, errorMessage = result.failure.message)
                    }
                }
            }
        }
    }

    fun submitGuestSession() {
        val current = _uiState.value
        if (current.isSubmitting) return

        val locationId = current.selectedDemoLocationId
        if (locationId == null || locationId < 1) {
            _uiState.update { it.copy(validationError = AuthValidationError.DEMO_LOCATION_REQUIRED) }
            return
        }

        viewModelScope.launch {
            _uiState.update { it.copy(isSubmitting = true, validationError = null, errorMessage = null) }
            when (val result = authRepository.startGuestSession(locationId)) {
                is AuthResult.Success -> {
                    _uiState.update { it.copy(isSubmitting = false) }
                }
                is AuthResult.Failure -> {
                    _uiState.update {
                        it.copy(isSubmitting = false, errorMessage = result.failure.message)
                    }
                }
            }
        }
    }

    private fun isValidEmail(email: String): Boolean {
        return email.isNotEmpty() &&
            email.length <= 254 &&
            EMAIL_REGEX.matches(email)
    }

    private companion object {
        val EMAIL_REGEX = Regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")
    }
}

