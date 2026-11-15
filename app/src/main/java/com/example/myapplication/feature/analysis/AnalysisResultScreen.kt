package com.example.myapplication.feature.analysis

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.myapplication.R
import com.example.myapplication.core.common.UiState
import com.example.myapplication.core.designsystem.component.AgronomicStatusTone
import com.example.myapplication.core.designsystem.component.FieldShiftCard
import com.example.myapplication.core.designsystem.component.FieldShiftOutlinedButton
import com.example.myapplication.core.designsystem.component.FieldShiftStatusChip
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme
import com.example.myapplication.domain.analysis.AnalysisJobStatus
import com.example.myapplication.domain.analysis.AnalysisResultEnvelope
import com.example.myapplication.domain.analysis.FieldPlan
import com.example.myapplication.domain.analysis.Strategy
import com.example.myapplication.feature.fields.label

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AnalysisResultScreen(
    analysisId: String,
    viewModel: AnalysisResultViewModel,
    onBackClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val colors = FieldShiftTheme.colors

    LaunchedEffect(analysisId) {
        viewModel.loadResult(analysisId)
    }

    Scaffold(
        modifier = modifier,
        containerColor = colors.surfaceCanvas,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = stringResource(R.string.analysis_result_title),
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
                .padding(horizontal = 16.dp)
        ) {
            when (val state = uiState.envelopeState) {
                is UiState.Loading -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator(color = colors.primaryAmberOchre)
                    }
                }

                is UiState.Empty,
                is UiState.Error -> {
                    val message = uiState.error?.let { formatAnalysisErrorMessage(it) }
                        ?: (state as? UiState.Error)?.message
                        ?: stringResource(R.string.analysis_error_not_found)
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                            Text(
                                text = message,
                                style = FieldShiftTheme.typography.bodyMd,
                                color = colors.erosionAlert
                            )
                            Spacer(modifier = Modifier.height(12.dp))
                            FieldShiftOutlinedButton(
                                text = stringResource(R.string.farms_error_retry),
                                onClick = { viewModel.loadResult(analysisId, forceRefresh = true) },
                                modifier = Modifier.fillMaxWidth()
                            )
                        }
                    }
                }

                is UiState.Success -> {
                    AnalysisResultContent(envelope = state.data)
                }
            }
        }
    }
}

@Composable
private fun AnalysisResultContent(envelope: AnalysisResultEnvelope) {
    val colors = FieldShiftTheme.colors
    val result = envelope.result

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        envelope.degradedMode?.let { degraded ->
            FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = stringResource(
                        R.string.analysis_degraded_banner,
                        degraded.datasetVersion,
                        degraded.ageSeconds
                    ),
                    style = FieldShiftTheme.typography.labelLg.copy(fontWeight = FontWeight.SemiBold),
                    color = colors.erosionAlert
                )
            }
        }

        if (envelope.warnings.isNotEmpty()) {
            FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = stringResource(R.string.fields_warning_banner_title),
                    style = FieldShiftTheme.typography.labelLg.copy(fontWeight = FontWeight.SemiBold),
                    color = colors.primaryAmberOchre
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = envelope.warnings.joinToString("\n") { "${it.code}: ${it.message}" },
                    style = FieldShiftTheme.typography.bodySm,
                    color = colors.textPrimary
                )
            }
        }

        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = stringResource(R.string.analysis_overall_summary),
                    style = FieldShiftTheme.typography.headlineSm,
                    color = colors.textPrimary
                )
                FieldShiftStatusChip(
                    text = envelope.status.label(),
                    tone = if (envelope.status == AnalysisJobStatus.PARTIAL) {
                        AgronomicStatusTone.HarvestOchre
                    } else {
                        AgronomicStatusTone.NominalFoliage
                    }
                )
            }
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = result.overallSummary,
                style = FieldShiftTheme.typography.bodyMd,
                color = colors.textPrimary
            )
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = "${result.datasetVersionUsed} • ${result.mlEngineVersion}",
                style = FieldShiftTheme.typography.labelMd,
                color = colors.textSecondary
            )
        }

        result.fieldPlans.forEach { fieldPlan ->
            FieldPlanCard(fieldPlan = fieldPlan)
        }

        FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = stringResource(R.string.analysis_disclaimer_title),
                style = FieldShiftTheme.typography.labelLg.copy(fontWeight = FontWeight.SemiBold),
                color = colors.textSecondary
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = result.disclaimer,
                style = FieldShiftTheme.typography.bodySm,
                color = colors.textSecondary
            )
        }
    }
}

@Composable
private fun FieldPlanCard(fieldPlan: FieldPlan) {
    val colors = FieldShiftTheme.colors
    FieldShiftCard(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = fieldPlan.fieldName,
                style = FieldShiftTheme.typography.headlineMd,
                color = colors.textPrimary,
                modifier = Modifier.weight(1f)
            )
            FieldShiftStatusChip(
                text = fieldPlan.status.label(),
                tone = if (fieldPlan.status == AnalysisJobStatus.PARTIAL) {
                    AgronomicStatusTone.HarvestOchre
                } else {
                    AgronomicStatusTone.NominalFoliage
                }
            )
        }

        fieldPlan.partialReason?.takeIf { it.isNotBlank() }?.let { reason ->
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = stringResource(R.string.analysis_partial_reason, reason),
                style = FieldShiftTheme.typography.bodySm,
                color = colors.erosionAlert
            )
        }

        Spacer(modifier = Modifier.height(6.dp))
        Text(
            text = fieldPlan.climateTrendSummary,
            style = FieldShiftTheme.typography.bodySm,
            color = colors.textSecondary
        )

        fieldPlan.strategies.forEach { strategy ->
            Spacer(modifier = Modifier.height(10.dp))
            HorizontalDivider()
            Spacer(modifier = Modifier.height(10.dp))
            StrategySection(
                strategy = strategy,
                isSuggested = strategy.strategyId == fieldPlan.suggestedStrategyId
            )
        }
    }
}

@Composable
private fun StrategySection(
    strategy: Strategy,
    isSuggested: Boolean
) {
    val colors = FieldShiftTheme.colors
    Column(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = strategy.name,
                style = FieldShiftTheme.typography.headlineSm,
                color = colors.textPrimary,
                modifier = Modifier.weight(1f)
            )
            FieldShiftStatusChip(
                text = stringResource(R.string.analysis_priority_fit, strategy.scores.priorityFit),
                tone = if (isSuggested) AgronomicStatusTone.NominalFoliage else AgronomicStatusTone.TelemetryCyan
            )
        }

        if (isSuggested || strategy.isExistingRotation) {
            Spacer(modifier = Modifier.height(4.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (isSuggested) {
                    FieldShiftStatusChip(
                        text = stringResource(R.string.analysis_suggested_badge),
                        tone = AgronomicStatusTone.NominalFoliage
                    )
                }
                if (strategy.isExistingRotation) {
                    FieldShiftStatusChip(
                        text = stringResource(R.string.analysis_existing_badge),
                        tone = AgronomicStatusTone.HarvestOchre
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(6.dp))
        Text(
            text = strategy.description,
            style = FieldShiftTheme.typography.bodySm,
            color = colors.textSecondary
        )

        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = stringResource(R.string.analysis_rotation_sequence),
            style = FieldShiftTheme.typography.labelMd.copy(fontWeight = FontWeight.SemiBold),
            color = colors.primaryAmberOchre
        )
        strategy.seasons.forEach { step ->
            Text(
                text = "${step.order}. ${step.cropName} — ${step.season.label()} ${step.year} (${step.role})",
                style = FieldShiftTheme.typography.bodySm,
                color = colors.textPrimary
            )
        }

        if (strategy.explanation.reasons.isNotEmpty() || strategy.explanation.risks.isNotEmpty()) {
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = stringResource(R.string.analysis_why_recommended),
                style = FieldShiftTheme.typography.labelMd.copy(fontWeight = FontWeight.SemiBold),
                color = colors.telemetryCyan
            )
            strategy.explanation.reasons.forEach { reason ->
                Text(
                    text = "• ${reason.text}",
                    style = FieldShiftTheme.typography.bodySm,
                    color = colors.textSecondary
                )
            }
            strategy.explanation.risks.forEach { risk ->
                Text(
                    text = "! ${risk.title}: ${risk.description}",
                    style = FieldShiftTheme.typography.bodySm,
                    color = colors.erosionAlert
                )
            }
        }
    }
}

