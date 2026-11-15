package com.example.myapplication.core.common

/**
 * Standard repository/screen state wrapper required by Section 6 of the architecture spec.
 * Every backend-driven screen must support Loading, Success, Empty, Error, and Refreshing.
 */
sealed interface UiState<out T> {
    data object Loading : UiState<Nothing>
    data object Empty : UiState<Nothing>
    data class Success<T>(
        val data: T,
        val isRefreshing: Boolean = false
    ) : UiState<T>
    data class Error(
        val message: String,
        val code: Int? = null,
        val cause: Throwable? = null
    ) : UiState<Nothing>
}

