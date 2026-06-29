package com.zuens2020.mcmonitor.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.zuens2020.mcmonitor.data.HistoryData
import com.zuens2020.mcmonitor.data.McInfo
import com.zuens2020.mcmonitor.data.McPerf
import com.zuens2020.mcmonitor.data.SysInfo
import com.zuens2020.mcmonitor.ui.components.HistoryChart
import com.zuens2020.mcmonitor.ui.components.MetricRow
import com.zuens2020.mcmonitor.ui.components.ScreenList
import com.zuens2020.mcmonitor.ui.components.StatGrid

@Composable
fun PerformanceScreen(
    mc: McInfo?,
    mcPerf: McPerf?,
    playersPerf: McPerf?,
    sys: SysInfo?,
    history: HistoryData?,
    historyLoading: Boolean,
    historyError: String?,
    historyRange: Int,
    onLoadHistory: (Int) -> Unit,
) {
    val perf = playersPerf ?: mcPerf
    ScreenList {
        item {
            Text("实时指标", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            StatGrid(
                listOf(
                    "TPS" to (perf?.tps1m?.let { "%.1f".format(it) } ?: mc?.tps ?: "-"),
                    "MSPT 均" to (perf?.msptAvg?.let { "%.1f".format(it) } ?: "-"),
                    "MSPT 峰" to (perf?.msptMax?.let { "%.1f".format(it) } ?: mc?.mspt ?: "-"),
                    "玩家" to (mc?.players ?: "-"),
                    "CPU" to (sys?.cpu ?: "-"),
                    "内存" to (sys?.mem ?: "-"),
                ),
            )
        }
        if (mc != null) {
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("服务器", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                        MetricRow("JVM 内存", mc.mem)
                        MetricRow("运行时长", mc.uptime)
                        MetricRow("连接", mc.connect)
                        MetricRow("隧道", mc.tunnel)
                    }
                }
            }
        }
        if (sys != null) {
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("主机", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                        MetricRow("磁盘", sys.disk)
                        MetricRow("负载", sys.load)
                    }
                }
            }
        }
        item {
            Text("趋势图", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
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
