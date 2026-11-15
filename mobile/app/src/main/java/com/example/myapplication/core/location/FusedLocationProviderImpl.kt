package com.example.myapplication.core.location

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import androidx.core.content.ContextCompat
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.google.android.gms.tasks.CancellationTokenSource
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withTimeoutOrNull

@Singleton
class FusedLocationProviderImpl @Inject constructor(
    @param:ApplicationContext private val context: Context
) : LocationProvider {

    private val fusedClient by lazy {
        LocationServices.getFusedLocationProviderClient(context)
    }

    override fun hasLocationPermission(): Boolean {
        val fineGranted = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED
        val coarseGranted = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_COARSE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED
        return fineGranted || coarseGranted
    }

    @SuppressLint("MissingPermission")
    override suspend fun getCurrentCoordinates(): GpsLocationResult {
        if (!hasLocationPermission()) {
            return GpsLocationResult.PermissionDenied
        }

        val cancellationTokenSource = CancellationTokenSource()
        return try {
            val location = withTimeoutOrNull(LOCATION_TIMEOUT_MS) {
                fusedClient.getCurrentLocation(
                    Priority.PRIORITY_HIGH_ACCURACY,
                    cancellationTokenSource.token
                ).await()
            } ?: return GpsLocationResult.Timeout

            GpsLocationResult.Success(
                latitude = location.latitude,
                longitude = location.longitude,
                accuracyMeters = if (location.hasAccuracy()) location.accuracy else null
            )
        } catch (ce: CancellationException) {
            throw ce
        } catch (se: SecurityException) {
            GpsLocationResult.PermissionDenied
        } catch (t: Throwable) {
            val msg = t.localizedMessage
            if (msg.isNullOrBlank()) {
                GpsLocationResult.LocationUnavailable
            } else {
                GpsLocationResult.Error(msg)
            }
        } finally {
            cancellationTokenSource.cancel()
        }
    }

    private companion object {
        const val LOCATION_TIMEOUT_MS = 15_000L
    }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class LocationModule {

    @Binds
    @Singleton
    abstract fun bindLocationProvider(impl: FusedLocationProviderImpl): LocationProvider
}

