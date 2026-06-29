package com.zuens2020.mcmonitor.ui.screens

import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.zuens2020.mcmonitor.data.Alert
import com.zuens2020.mcmonitor.data.HistoryData
import com.zuens2020.mcmonitor.ui.components.AlertCard
import com.zuens2020.mcmonitor.ui.components.HistoryChart
import com.zuens2020.mcmonitor.ui.components.LogText
import com.zuens2020.mcmonitor.ui.components.ScreenList
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row

@Composable
fun ManageScreen(
    alerts: List<Alert>,
    history: HistoryData?,
    historyLoading: Boolean,
    historyError: String?,
    historyRange: Int,
    alertLog: String?,
    alertLogLoading: Boolean,
    baseUrl: String,
    urlDraft: String,
    onUrlDraftChange: (String) -> Unit,
    onSaveUrl: () -> Unit,
    onDismissAlert: (String) -> Unit,
    onLoadHistory: (Int) -> Unit,
    onLoadAlertLog: () -> Unit,
) {
    ScreenList {
        item {
            Text("服务器设置", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            OutlinedTextField(
                value = urlDraft,
                onValueChange = onUrlDraftChange,
                label = { Text("监控面板 URL") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            androidx.compose.material3.FilledTonalButton(onClick = onSaveUrl, modifier = Modifier.fillMaxWidth()) {
                Text("保存地址")
            }
        }
        item {
            Text("预警管理", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        }
        if (alerts.isEmpty()) {
            item { Text("当前无活跃预警", color = MaterialTheme.colorScheme.onSurfaceVariant) }
        } else {
            items(alerts, key = { it.key.ifBlank { it.msg } }) { a ->
                AlertCard(a, onDismiss = if (a.key.isNotBlank() && a.level != "info") {
                    { onDismissAlert(a.key) }
                } else null)
            }
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilledTonalIconButton(onLoadAlertLog, alertLogLoading, "刷新预警历史")
            }
        }
        if (alertLog != null) {
            item { LogText(alertLog) }
        }
        item {
            Text("主机趋势", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(30, 60, 120).forEach { range ->
                    FilterChip(
                        selected = historyRange == range,
                        onClick = { onLoadHistory(range) },
                        label = { Text("${range}分") },
                    )
                }
            }
        }
        when {
            historyLoading -> item { Text("加载趋势…", color = MaterialTheme.colorScheme.onSurfaceVariant) }
            historyError != null -> item { Text(historyError, color = MaterialTheme.colorScheme.error) }
            history != null -> item { HistoryChart(history) }
        }
        item { Spacer(Modifier.height(32.dp)) }
    }
}

@Composable
private fun FilledTonalIconButton(onClick: () -> Unit, loading: Boolean, label: String) {
    androidx.compose.material3.FilledTonalButton(onClick = onClick, enabled = !loading) {
        Text(if (loading) "加载中…" else label)
    }
}
