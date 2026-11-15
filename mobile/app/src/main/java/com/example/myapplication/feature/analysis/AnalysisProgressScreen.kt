package com.example.myapplication.feature.analysis

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.myapplication.R
import com.example.myapplication.core.designsystem.component.AgronomicStatusTone
import com.example.myapplication.core.designsystem.component.FieldShiftCard
import com.example.myapplication.core.designsystem.component.FieldShiftOutlinedButton
import com.example.myapplication.core.designsystem.component.FieldShiftPrimaryButton
import com.example.myapplication.core.designsystem.component.FieldShiftStatusChip
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme
import com.example.myapplication.domain.analysis.AnalysisJobStatus

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AnalysisProgressScreen(
    requestId: String,
    viewModel: AnalysisProgressViewModel,
    onBackClick: () -> Unit,
    onResultReady: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val colors = FieldShiftTheme.colors
    val lifecycleOwner = LocalLifecycleOwner.current

    LaunchedEffect(requestId) {
        viewModel.initialize(requestId)
    }

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> viewModel.setForegroundActive(true)
                Lifecycle.Event.ON_STOP -> viewModel.setForegroundActive(false)
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        if (lifecycleOwner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) {
            viewModel.setForegroundActive(true)
        }
        onDispose {
            viewModel.setForegroundActive(false)
            lifecycleOwner.lifecycle.removeObserver(observer)
        }
    }

    LaunchedEffect(uiState.status, uiState.analysisId) {
        val analysisId = uiState.analysisId
        if (uiState.status.isSuccessTerminal && !analysisId.isNullOrBlank()) {
            onResultReady(analysisId)
        }
    }

    Scaffold(
        modifier = modifier,
        containerColor = colors.surfaceCanvas,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = stringResource(R.string.analysis_progress_title),
                        style = FieldShiftTheme.typography.headlineSm,
                        color = colors.textPrimary
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBackClick) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.farm_detail_back),
                            tint = colors.textPrimary
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = colors.surfaceCanvas
                )
            )
        }
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 16.dp),
            contentAlignment = Alignment.Center
        ) {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                    FieldShiftStatusChip(
                        text = uiState.status.label(),
                        tone = when (uiState.status) {
                            AnalysisJobStatus.OK -> AgronomicStatusTone.NominalFoliage
                            AnalysisJobStatus.PARTIAL -> AgronomicStatusTone.HarvestOchre
                            AnalysisJobStatus.FAILED,
                            AnalysisJobStatus.CANCELLED -> AgronomicStatusTone.MoistureDeficitAlert
                            else -> AgronomicStatusTone.TelemetryCyan
                        }
                    )

                    Spacer(modifier = Modifier.height(10.dp))

                    Text(
                        text = stringResource(R.string.analysis_request_id_label, uiState.requestId),
                        style = FieldShiftTheme.typography.bodySm,
                        color = colors.textSecondary
                    )

                    if (!uiState.status.isTerminal) {
                        Spacer(modifier = Modifier.height(16.dp))
                        Box(
                            modifier = Modifier.fillMaxWidth(),
                            contentAlignment = Alignment.Center
                        ) {
                            CircularProgressIndicator(color = colors.primaryAmberOchre)
                        }
                    }

                    uiState.pollErrorInfo?.let { err ->
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = "${err.code}: ${err.message}",
                            style = FieldShiftTheme.typography.bodyMd,
                            color = colors.erosionAlert
                        )
                    }

                    uiState.transportError?.let { err ->
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = formatAnalysisErrorMessage(err),
                            style = FieldShiftTheme.typography.bodySm,
                            color = colors.erosionAlert
                        )
                        if (!uiState.status.isTerminal) {
                            Spacer(modifier = Modifier.height(8.dp))
                            FieldShiftOutlinedButton(
                                text = stringResource(R.string.farms_error_retry),
                                onClick = viewModel::retryPolling,
                                modifier = Modifier.fillMaxWidth()
                            )
                        }
                    }

                    uiState.cancelError?.let { err ->
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = formatAnalysisErrorMessage(err),
                            style = FieldShiftTheme.typography.bodySm,
                            color = colors.erosionAlert
                        )
                    }
                }

                if (!uiState.status.isTerminal) {
                    FieldShiftOutlinedButton(
                        text = if (uiState.isCancelling) {
                            stringResource(R.string.analysis_cancelling)
                        } else {
                            stringResource(R.string.analysis_cancel_action)
                        },
                        onClick = viewModel::cancelAnalysis,
                        enabled = !uiState.isCancelling,
                        modifier = Modifier.fillMaxWidth()
                    )
                } else if (uiState.status.isSuccessTerminal && !uiState.analysisId.isNullOrBlank()) {
                    FieldShiftPrimaryButton(
                        text = stringResource(R.string.analysis_view_result),
                        onClick = { onResultReady(uiState.analysisId!!) },
                        modifier = Modifier.fillMaxWidth()
                    )
                } else {
                    FieldShiftPrimaryButton(
                        text = stringResource(R.string.analysis_back_to_config),
                        onClick = onBackClick,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            }
        }
    }
}

