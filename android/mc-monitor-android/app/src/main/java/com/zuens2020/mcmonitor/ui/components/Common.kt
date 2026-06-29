package com.zuens2020.mcmonitor.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
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
import androidx.compose.material3.LinearProgressIndicator
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
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
    val hp = p.hp.toFloatOrNull() ?: 0f
    val food = p.food.toFloatOrNull() ?: 0f
    val hpRatio = (hp / 20f).coerceIn(0f, 1f)
    val foodRatio = (food / 20f).coerceIn(0f, 1f)
    val danger = hp in 1f..9f || food in 1f..9f
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = if (danger) MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.35f)
            else MaterialTheme.colorScheme.surfaceContainerHigh,
        ),
    ) {
        Row(Modifier.padding(12.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            AsyncImage(
                model = "https://minotar.net/helm/${p.name}/56.png",
                contentDescription = p.name,
                modifier = Modifier.size(56.dp).clip(RoundedCornerShape(8.dp)),
                contentScale = ContentScale.Crop,
            )
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text(p.name, fontWeight = FontWeight.Bold)
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                        if (p.mode.isNotBlank() && p.mode != "-") {
                            Text(p.mode, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                        }
                        if (p.onlineFor.isNotBlank() && p.onlineFor != "-") {
                            Text(p.onlineFor, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        if (p.place >= 400) {
                            PlaceBadge(p.place, critical = p.place >= 800)
                        }
                    }
                }
                PlayerBar("HP", hpRatio, MaterialTheme.colorScheme.primary)
                if (detailed) {
                    PlayerBar("饱食", foodRatio, MaterialTheme.colorScheme.tertiary)
                }
                Text(
                    "${p.dim} · Lv.${p.xp} · ${p.pos}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (detailed) {
                    ArmorSlotsRow(p.armorSlots)
                }
            }
        }
    }
}

@Composable
private fun PlayerBar(label: String, ratio: Float, color: Color) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        LinearProgressIndicator(
            progress = { ratio },
            modifier = Modifier.fillMaxWidth().height(8.dp).clip(RoundedCornerShape(4.dp)),
            color = color,
            trackColor = MaterialTheme.colorScheme.surfaceVariant,
        )
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun PlaceBadge(place: Int, critical: Boolean) {
    val bg = if (critical) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.tertiary
    Text(
        "▲${place}/m",
        modifier = Modifier
            .background(bg.copy(alpha = 0.25f), RoundedCornerShape(4.dp))
            .padding(horizontal = 6.dp, vertical = 2.dp),
        style = MaterialTheme.typography.labelSmall,
        color = bg,
        fontWeight = FontWeight.Bold,
    )
}

@Composable
fun ArmorSlotsRow(slots: List<String?>) {
    Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        val items = if (slots.size >= 4) slots.take(4) else slots + List(4 - slots.size) { null }
        items.forEach { piece ->
            val color = armorColor(piece)
            Box(
                Modifier
                    .size(width = 16.dp, height = 14.dp)
                    .clip(RoundedCornerShape(2.dp))
                    .then(
                        if (color != null) Modifier.background(color)
                        else Modifier.border(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.4f), RoundedCornerShape(2.dp)),
                    ),
            )
        }
    }
}

private fun armorColor(piece: String?): Color? {
    if (piece.isNullOrBlank()) return null
    return when {
        piece.startsWith("netherite_") -> Color(0xFF4A443F)
        piece.startsWith("diamond_") -> Color(0xFF2F8E84)
        piece.startsWith("iron_") -> Color(0xFF9A9C9C)
        piece.startsWith("golden_") -> Color(0xFF9C7D22)
        piece.startsWith("chainmail_") -> Color(0xFF6A6C6E)
        piece.startsWith("leather_") -> Color(0xFF7A5430)
        piece == "turtle_helmet" -> Color(0xFF45824A)
        piece == "elytra" -> Color(0xFF8A7E9A)
        else -> Color(0xFF777A7D)
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

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun StatGrid(stats: List<Pair<String, String>>, modifier: Modifier = Modifier) {
    FlowRow(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        maxItemsInEachRow = 3,
    ) {
        stats.forEach { (label, value) -> StatTile(label, value) }
    }
}

@Composable
fun StatTile(label: String, value: String, modifier: Modifier = Modifier) {
    Card(modifier = modifier.padding(0.dp)) {
        Column(Modifier.padding(horizontal = 12.dp, vertical = 10.dp)) {
            Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(value, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NavLinkCard(title: String, subtitle: String, onClick: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth(), onClick = onClick) {
        Row(
            Modifier.fillMaxWidth().padding(14.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text(title, fontWeight = FontWeight.SemiBold)
                Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text("›", style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
fun HistoryChart(data: HistoryData) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(
                "主机趋势 · 近 ${data.rangeMinutes} 分钟 (${data.source})",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                "${data.labels.size} 个采样点",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
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
