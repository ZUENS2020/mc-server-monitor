package com.zuens2020.mcmonitor.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.zuens2020.mcmonitor.data.AlertLogEntry
import com.zuens2020.mcmonitor.ui.components.ErrorPane
import com.zuens2020.mcmonitor.ui.components.ScreenList

private enum class AlertLogFilter(val label: String) {
    All("全部"),
    Critical("严重"),
    Warn("警告"),
    Resolved("解除"),
}

@Composable
fun AlertLogScreen(
    entries: List<AlertLogEntry>,
    loading: Boolean,
    error: String?,
    onRetry: () -> Unit,
) {
    var filter by remember { mutableStateOf(AlertLogFilter.All) }

    when {
        loading && entries.isEmpty() -> {
            ScreenList {
                item { Text("加载预警日志…", color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
        }
        error != null && entries.isEmpty() -> ErrorPane(error, onRetry)
        else -> ScreenList {
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    AlertLogFilter.entries.forEach { f ->
                        FilterChip(
                            selected = filter == f,
                            onClick = { filter = f },
                            label = { Text(f.label) },
                        )
                    }
                }
            }
            val filtered = entries.filter { e ->
                when (filter) {
                    AlertLogFilter.All -> true
                    AlertLogFilter.Critical -> e.level.equals("CRITICAL", true)
                    AlertLogFilter.Warn -> e.level.equals("WARN", true) || e.level.equals("WARNING", true)
                    AlertLogFilter.Resolved -> e.isResolved
                }
            }
            if (filtered.isEmpty()) {
                item { Text("无匹配记录", color = MaterialTheme.colorScheme.onSurfaceVariant) }
            } else {
                items(filtered, key = { "${it.timestamp}-${it.message}" }) { entry ->
                    AlertLogEntryCard(entry)
                }
            }
            item { Spacer(Modifier.height(32.dp)) }
        }
    }
}

@Composable
private fun AlertLogEntryCard(entry: AlertLogEntry) {
    val container = when {
        entry.isResolved -> MaterialTheme.colorScheme.surfaceVariant
        entry.level.equals("CRITICAL", true) -> MaterialTheme.colorScheme.errorContainer
        entry.level.equals("WARN", true) || entry.level.equals("WARNING", true) ->
            MaterialTheme.colorScheme.tertiaryContainer
        else -> MaterialTheme.colorScheme.surfaceContainerHigh
    }
    val fg = when {
        entry.isResolved -> MaterialTheme.colorScheme.onSurfaceVariant
        entry.level.equals("CRITICAL", true) -> MaterialTheme.colorScheme.onErrorContainer
        entry.level.equals("WARN", true) || entry.level.equals("WARNING", true) ->
            MaterialTheme.colorScheme.onTertiaryContainer
        else -> MaterialTheme.colorScheme.onSurface
    }
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(entry.level, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold, color = fg)
                if (entry.timestamp.isNotBlank()) {
                    Text(entry.timestamp, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Text(entry.message, style = MaterialTheme.typography.bodyMedium, color = fg)
        }
    }
}
