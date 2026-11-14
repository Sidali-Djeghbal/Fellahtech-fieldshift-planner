package com.example.myapplication.feature.farms

import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.example.myapplication.R
import com.example.myapplication.domain.farm.FarmError

@Composable
fun formatFarmErrorMessage(error: FarmError): String {
    val baseMessage = when (error) {
        is FarmError.Api -> when {
            error.isGuestLimitReached -> stringResource(id = R.string.farms_error_guest_limit)
            error.isUnauthorized -> stringResource(id = R.string.farms_error_unauthorized)
            error.isNotFound -> stringResource(id = R.string.farms_error_not_found)
            else -> error.message
        }
        is FarmError.Network -> error.message
    }

    val requestId = (error as? FarmError.Api)?.requestId
    return if (!requestId.isNullOrBlank()) {
        "$baseMessage\n${stringResource(id = R.string.farms_error_request_id, requestId)}"
    } else {
        baseMessage
    }
}

