package com.zuens2020.mcmonitor.ui.screens

import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.zuens2020.mcmonitor.data.MonitorStatus
import com.zuens2020.mcmonitor.ui.components.AlertCard
import com.zuens2020.mcmonitor.ui.components.McCard
import com.zuens2020.mcmonitor.ui.components.PerfCard
import com.zuens2020.mcmonitor.ui.components.ScreenList
import com.zuens2020.mcmonitor.ui.components.SummaryCard
import com.zuens2020.mcmonitor.ui.components.SysCard
import com.zuens2020.mcmonitor.ui.components.UpdatedLabel

@Composable
fun OverviewScreen(
    status: MonitorStatus?,
    baseUrl: String,
    error: String?,
    onDismissAlert: (String) -> Unit,
) {
    ScreenList {
        if (error != null) {
            item {
                Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
            }
        }
        item { UpdatedLabel(status?.updated ?: 0, baseUrl) }
        status?.summary?.let { s -> item { SummaryCard(s.up, s.warn, s.down) } }
        status?.mc?.let { mc -> item { McCard(mc) } }
        status?.mcPerf?.let { perf -> item { PerfCard(perf) } }
        status?.sys?.let { sys -> item { SysCard(sys) } }
        status?.alerts?.takeIf { it.isNotEmpty() }?.let { alerts ->
            item {
                Text("活跃预警", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            }
            items(alerts, key = { it.key.ifBlank { it.msg } }) { a ->
                AlertCard(a, onDismiss = if (a.key.isNotBlank() && a.level != "info") {
                    { onDismissAlert(a.key) }
                } else null)
            }
        }
        item { Spacer(Modifier.height(32.dp)) }
    }
}
