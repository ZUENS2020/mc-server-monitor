package com.zuens2020.mcmonitor.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.zuens2020.mcmonitor.data.Alert
import com.zuens2020.mcmonitor.data.HistoryData
import com.zuens2020.mcmonitor.data.McInfo
import com.zuens2020.mcmonitor.data.McPerf
import com.zuens2020.mcmonitor.data.PlayerInfo
import com.zuens2020.mcmonitor.data.ServiceItem
import com.zuens2020.mcmonitor.data.SysInfo
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun ErrorPane(message: String, onRetry: () -> Unit) {
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(Icons.Default.Warning, null, tint = MaterialTheme.colorScheme.error, modifier = Modifier.size(48.dp))
        Spacer(Modifier.height(12.dp))
        Text(message, style = MaterialTheme.typography.bodyLarge)
        Spacer(Modifier.height(16.dp))
        FilledTonalButton(onClick = onRetry) { Text("重试") }
    }
}

@Composable
fun UpdatedLabel(updated: Long, baseUrl: String) {
    Text(
        baseUrl,
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    if (updated > 0) {
        val fmt = SimpleDateFormat("HH:mm:ss", Locale.getDefault())
        Text(
            "更新于 ${fmt.format(Date(updated * 1000))}",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
fun McCard(mc: McInfo, title: String = "Pure Survive") {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Spacer(Modifier.width(8.dp))
                StatusChip(if (mc.online) "在线" else "离线", mc.online)
            }
            MetricRow("玩家", mc.players)
            MetricRow("TPS", mc.tps)
            MetricRow("MSPT", mc.mspt)
            MetricRow("内存", mc.mem)
            MetricRow("运行", mc.uptime)
            MetricRow("隧道", mc.tunnel)
            MetricRow("连接", mc.connect)
            MetricRow("版本", mc.version)
            MetricRow("难度 / 视距", "${mc.difficulty} / ${mc.viewdist}")
        }
    }
}

@Composable
fun PerfCard(perf: McPerf) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("实时性能", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            perf.tps1m?.let { MetricRow("TPS (1m)", "%.1f".format(it)) }
            perf.msptAvg?.let { MetricRow("MSPT 平均", "%.1f ms".format(it)) }
            perf.msptMax?.let { MetricRow("MSPT 峰值", "%.1f ms".format(it)) }
        }
    }
}

@Composable
fun SysCard(sys: SysInfo) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("主机", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            MetricRow("CPU", sys.cpu)
            MetricRow("内存", sys.mem)
            MetricRow("磁盘", sys.disk)
            MetricRow("负载", sys.load)
        }
    }
}

@Composable
fun SummaryCard(up: Int, warn: Int, down: Int) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            Modifier.fillMaxWidth().padding(16.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            SummaryChip("正常", up, MaterialTheme.colorScheme.primary)
            SummaryChip("警告", warn, MaterialTheme.colorScheme.tertiary)
            SummaryChip("异常", down, MaterialTheme.colorScheme.error)
        }
    }
}

@Composable
private fun SummaryChip(label: String, count: Int, color: Color) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text("$count", style = MaterialTheme.typography.headlineSmall, color = color, fontWeight = FontWeight.Bold)
        Text(label, style = MaterialTheme.typography.labelMedium)
    }
}

@Composable
fun PlayerCard(p: PlayerInfo, detailed: Boolean = false) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(p.name, fontWeight = FontWeight.Medium)
                Text("${p.hp} HP", style = MaterialTheme.typography.bodySmall)
            }
            Text("${p.dim} · ${p.pos}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (detailed) {
                Text("饱食 ${p.food} · 等级 ${p.xp} · ${p.mode}", style = MaterialTheme.typography.bodySmall)
                if (p.onlineFor != "-") {
                    Text("在线 ${p.onlineFor}", style = MaterialTheme.typography.labelSmall)
                }
                if (p.armor.isNotEmpty()) {
                    Text("装备 ${p.armor.joinToString(", ")}", style = MaterialTheme.typography.labelSmall)
                }
                if (p.place > 0) {
                    Text("近 1 分钟放置 ${p.place} 块", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.tertiary)
                }
            }
        }
    }
}

@Composable
fun AlertCard(a: Alert, onDismiss: (() -> Unit)? = null) {
    val container = when (a.level) {
        "critical" -> MaterialTheme.colorScheme.errorContainer
        "warn", "warning" -> MaterialTheme.colorScheme.tertiaryContainer
        else -> MaterialTheme.colorScheme.surfaceVariant
    }
    Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = container)) {
        Column(Modifier.padding(12.dp)) {
            Text(a.msg, style = MaterialTheme.typography.bodyMedium)
            if (a.since.isNotBlank()) {
                Text(a.since, style = MaterialTheme.typography.labelSmall)
            }
            if (onDismiss != null && a.key.isNotBlank() && a.level != "info") {
                Spacer(Modifier.height(8.dp))
                FilledTonalButton(onClick = onDismiss, modifier = Modifier.fillMaxWidth()) {
                    Text("关闭预警")
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ServiceItemCard(item: ServiceItem, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        onClick = onClick,
        shape = RoundedCornerShape(12.dp),
    ) {
        Row(
            Modifier.fillMaxWidth().padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            LevelDot(item.level)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(item.name, fontWeight = FontWeight.SemiBold)
                if (item.sub.isNotBlank()) {
                    Text(item.sub, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Text(item.detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (item.cpu.isNotBlank() || item.mem.isNotBlank()) {
                Column(horizontalAlignment = Alignment.End) {
                    if (item.cpu.isNotBlank()) Text(item.cpu, style = MaterialTheme.typography.labelSmall)
                    if (item.mem.isNotBlank()) Text(item.mem, style = MaterialTheme.typography.labelSmall)
                }
            }
        }
    }
}

@Composable
fun LevelDot(level: String) {
    val color = when (level) {
        "up" -> MaterialTheme.colorScheme.primary
        "warn" -> MaterialTheme.colorScheme.tertiary
        else -> MaterialTheme.colorScheme.error
    }
    Canvas(Modifier.size(10.dp)) {
        drawCircle(color = color)
    }
}

@Composable
fun MetricRow(label: String, value: String, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, fontWeight = FontWeight.Medium)
    }
}

@Composable
fun StatusChip(text: String, ok: Boolean) {
    val bg = if (ok) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.errorContainer
    val fg = if (ok) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onErrorContainer
    Card(colors = CardDefaults.cardColors(containerColor = bg)) {
        Text(text, modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp), color = fg, style = MaterialTheme.typography.labelLarge)
    }
}

@Composable
fun HistoryChart(data: HistoryData) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(
                "主机趋势 (${data.source})",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Sparkline("CPU %", data.cpu, MaterialTheme.colorScheme.primary)
            Sparkline("内存 %", data.mem, MaterialTheme.colorScheme.tertiary)
            Sparkline("负载", data.load, MaterialTheme.colorScheme.secondary)
            if (data.labels.isNotEmpty()) {
                Text(
                    "${data.labels.first()} — ${data.labels.last()}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun Sparkline(label: String, values: List<Float?>, color: Color) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        val nums = values.filterNotNull()
        val latest = nums.lastOrNull()
        val peak = nums.maxOrNull()
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(label, style = MaterialTheme.typography.labelMedium)
            Text(
                buildString {
                    latest?.let { append("当前 %.1f".format(it)) }
                    peak?.let { if (isNotEmpty()) append(" · "); append("峰值 %.1f".format(it)) }
                },
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        val outlineColor = MaterialTheme.colorScheme.outline.copy(alpha = 0.3f)
        Canvas(Modifier.fillMaxWidth().height(48.dp)) {
            if (nums.size < 2) return@Canvas
            val maxV = (nums.maxOrNull() ?: 1f).coerceAtLeast(1f)
            val stepX = size.width / (nums.size - 1).coerceAtLeast(1)
            val path = Path()
            nums.forEachIndexed { i, v ->
                val x = i * stepX
                val y = size.height - (v / maxV) * size.height * 0.9f - size.height * 0.05f
                if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
            }
            drawPath(path, color, style = Stroke(width = 3f))
            drawLine(
                color = outlineColor,
                start = Offset(0f, size.height),
                end = Offset(size.width, size.height),
                strokeWidth = 1f,
            )
        }
    }
}

@Composable
fun LogText(text: String) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Text(
            text.trimEnd(),
            modifier = Modifier.padding(12.dp),
            style = MaterialTheme.typography.bodySmall,
            fontFamily = FontFamily.Monospace,
        )
    }
}

@Composable
fun ScreenList(content: LazyListScope.() -> Unit) {
    LazyColumn(
        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 16.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        content = content,
    )
}
