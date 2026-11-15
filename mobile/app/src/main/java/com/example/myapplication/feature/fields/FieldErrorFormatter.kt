package com.example.myapplication.feature.fields

import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.example.myapplication.R
import com.example.myapplication.domain.field.FieldError
import com.example.myapplication.domain.field.IrrigationSystem
import com.example.myapplication.domain.field.Season
import com.example.myapplication.domain.field.SoilType
import com.example.myapplication.domain.field.WaterAvailability
import com.example.myapplication.domain.field.WaterSource

@Composable
fun formatFieldErrorMessage(error: FieldError): String {
    val baseMessage = when (error) {
        is FieldError.Api -> when {
            error.isOutsideDemoBoundary -> stringResource(id = R.string.fields_error_outside_demo_boundary)
            error.isGuestLimitReached -> stringResource(id = R.string.fields_error_guest_limit)
            error.isUnauthorized -> stringResource(id = R.string.farms_error_unauthorized)
            error.isNotFound -> stringResource(id = R.string.fields_error_not_found)
            error.isConflict -> stringResource(id = R.string.fields_error_conflict)
            else -> error.message
        }
        is FieldError.Network -> error.message
    }

    val requestId = (error as? FieldError.Api)?.requestId
    return if (!requestId.isNullOrBlank()) {
        "$baseMessage\n${stringResource(id = R.string.farms_error_request_id, requestId)}"
    } else {
        baseMessage
    }
}

@Composable
fun SoilType.label(): String = stringResource(
    id = when (this) {
        SoilType.SANDY -> R.string.soil_sandy
        SoilType.CLAY -> R.string.soil_clay
        SoilType.LOAMY -> R.string.soil_loamy
        SoilType.SILTY -> R.string.soil_silty
        SoilType.UNKNOWN -> R.string.soil_unknown
    }
)

@Composable
fun WaterAvailability.label(): String = stringResource(
    id = when (this) {
        WaterAvailability.ABUNDANT -> R.string.water_abundant
        WaterAvailability.MODERATE -> R.string.water_moderate
        WaterAvailability.LIMITED -> R.string.water_limited
        WaterAvailability.VERY_LIMITED -> R.string.water_very_limited
        WaterAvailability.RAINFED_ONLY -> R.string.water_rainfed_only
    }
)

@Composable
fun WaterSource.label(): String = stringResource(
    id = when (this) {
        WaterSource.RAINWATER -> R.string.wsource_rainwater
        WaterSource.GROUNDWATER -> R.string.wsource_groundwater
        WaterSource.WELL -> R.string.wsource_well
        WaterSource.DAM_RESERVOIR -> R.string.wsource_dam_reservoir
        WaterSource.IRRIGATION_NETWORK -> R.string.wsource_irrigation_network
        WaterSource.OTHER -> R.string.wsource_other
        WaterSource.UNKNOWN -> R.string.wsource_unknown
    }
)

@Composable
fun IrrigationSystem.label(): String = stringResource(
    id = when (this) {
        IrrigationSystem.RAINFED -> R.string.irrig_rainfed
        IrrigationSystem.DRIP -> R.string.irrig_drip
        IrrigationSystem.SPRINKLER -> R.string.irrig_sprinkler
        IrrigationSystem.FLOOD -> R.string.irrig_flood
        IrrigationSystem.OTHER -> R.string.irrig_other
        IrrigationSystem.UNKNOWN -> R.string.irrig_unknown
    }
)

@Composable
fun Season.label(): String = stringResource(
    id = when (this) {
        Season.SPRING -> R.string.season_spring
        Season.SUMMER -> R.string.season_summer
        Season.AUTUMN -> R.string.season_autumn
        Season.WINTER -> R.string.season_winter
    }
)

