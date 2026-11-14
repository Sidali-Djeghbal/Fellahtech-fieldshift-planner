package com.example.myapplication.navigation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.myapplication.domain.auth.AuthRepository
import com.example.myapplication.domain.auth.SessionState
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

@HiltViewModel
class SessionViewModel @Inject constructor(
    private val authRepository: AuthRepository
) : ViewModel() {

    val sessionState: StateFlow<SessionState> = authRepository.sessionState

    init {
        restoreSession()
    }

    fun restoreSession() {
        viewModelScope.launch {
            authRepository.restoreSession()
        }
    }

    fun clearSessionLocally() {
        viewModelScope.launch {
            authRepository.clearSessionLocally()
        }
    }
}

