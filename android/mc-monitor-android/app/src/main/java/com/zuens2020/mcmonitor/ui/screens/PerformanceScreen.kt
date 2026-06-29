package com.zuens2020.mcmonitor.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
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
import com.zuens2020.mcmonitor.ui.components.LiveMetricGrid
import com.zuens2020.mcmonitor.ui.components.MetricRow
import com.zuens2020.mcmonitor.ui.components.ScreenList

@Composable
fun PerformanceScreen(
    mc: McInfo?,
    mcPerf: McPerf?,
    playersPerf: McPerf?,
    sys: SysInfo?,
    history: HistoryData?,
    historyLoading: Boolean,
    historyError: String?,
) {
    val perf = playersPerf ?: mcPerf
    ScreenList {
        item {
            Column(Modifier.fillMaxWidth()) {
                Text("实时指标", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(8.dp))
                LiveMetricGrid(mc = mc, perf = perf, sys = sys)
            }
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
                        perf?.msptMax?.let { MetricRow("MSPT 峰值", "%.1f".format(it)) }
                    }
                }
            }
        }
        if (sys != null) {
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("主机", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                        MetricRow("负载", sys.load)
                    }
                }
            }
        }
        item {
            Text("趋势图 · 近 60 分钟", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        }
        when {
            historyLoading -> item { Text("加载趋势…", color = MaterialTheme.colorScheme.onSurfaceVariant) }
            historyError != null -> item { Text(historyError, color = MaterialTheme.colorScheme.error) }
            history != null -> item { HistoryChart(history) }
        }
        item { Spacer(Modifier.height(32.dp)) }
    }
}
