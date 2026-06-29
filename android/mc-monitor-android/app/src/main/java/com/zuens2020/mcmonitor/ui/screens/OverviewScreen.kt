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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.zuens2020.mcmonitor.data.MonitorStatus
import com.zuens2020.mcmonitor.data.PlayerInfo
import com.zuens2020.mcmonitor.ui.components.AlertCard
import com.zuens2020.mcmonitor.ui.components.NavLinkCard
import com.zuens2020.mcmonitor.ui.components.PlayerCard
import com.zuens2020.mcmonitor.ui.components.ScreenList
import com.zuens2020.mcmonitor.ui.components.StatGrid
import com.zuens2020.mcmonitor.ui.components.StatusChip
import com.zuens2020.mcmonitor.ui.components.SummaryCard
import com.zuens2020.mcmonitor.ui.components.UpdatedLabel

@Composable
fun OverviewScreen(
    status: MonitorStatus?,
    players: List<PlayerInfo>?,
    baseUrl: String,
    error: String?,
    onDismissAlert: (String) -> Unit,
    onOpenPlayers: () -> Unit,
    onOpenPerformance: () -> Unit,
    onOpenAlertLog: () -> Unit,
    onOpenControl: () -> Unit,
) {
    val mc = status?.mc
    val perf = status?.mcPerf
    val sys = status?.sys
    val previewPlayers = players ?: status?.mcPlayers

    ScreenList {
        if (error != null) {
            item {
                Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
            }
        }
        item { UpdatedLabel(status?.updated ?: 0, baseUrl) }
        status?.summary?.let { s -> item { SummaryCard(s.up, s.warn, s.down) } }

        item {
            Text("实时概览", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            StatGrid(
                listOf(
                    "TPS" to (perf?.tps1m?.let { "%.1f".format(it) } ?: mc?.tps ?: "-"),
                    "MSPT" to (perf?.msptAvg?.let { "%.1f".format(it) } ?: mc?.mspt ?: "-"),
                    "玩家" to (mc?.players ?: "-"),
                    "CPU" to (sys?.cpu ?: "-"),
                    "内存" to (sys?.mem ?: "-"),
                    "磁盘" to (sys?.disk ?: "-"),
                ),
            )
        }

        if (mc != null) {
            item {
                Card(Modifier.fillMaxWidth()) {
                    Row(
                        Modifier.fillMaxWidth().padding(14.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column {
                            Text("Pure Survive", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                            Text(
                                "${mc.version} · ${mc.connect} · ${mc.tunnel}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        StatusChip(if (mc.online) "在线" else "离线", mc.online)
                    }
                }
            }
        }

        item {
            NavLinkCard("性能详情与趋势", "TPS / MSPT / 主机图表", onOpenPerformance)
        }
        item {
            NavLinkCard("服务器控制", "Crafty 启停 / 备份 / 服务", onOpenControl)
        }

        previewPlayers?.takeIf { it.isNotEmpty() }?.let { list ->
            item {
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("在线玩家", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text("${list.size} 人", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                }
            }
            items(list.take(4), key = { it.name }) { PlayerCard(it, detailed = true) }
            if (list.size > 4) {
                item { NavLinkCard("查看全部玩家", "共 ${list.size} 人", onOpenPlayers) }
            }
        } ?: item {
            NavLinkCard("在线玩家", "暂无在线", onOpenPlayers)
        }

        val alerts = status?.alerts.orEmpty()
        item {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("预警", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                if (alerts.isNotEmpty()) {
                    Text("${alerts.size} 条活跃", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.tertiary)
                }
            }
        }
        if (alerts.isEmpty()) {
            item { Text("当前无活跃预警", color = MaterialTheme.colorScheme.onSurfaceVariant) }
        } else {
            items(alerts.take(2), key = { it.key.ifBlank { it.msg } }) { a ->
                AlertCard(a, onDismiss = if (a.key.isNotBlank() && a.level != "info") {
                    { onDismissAlert(a.key) }
                } else null)
            }
            if (alerts.size > 2) {
                item { NavLinkCard("还有 ${alerts.size - 2} 条预警", "前往控制页管理", onOpenControl) }
            }
        }
        item { NavLinkCard("预警历史日志", "按级别筛选浏览", onOpenAlertLog) }

        item { Spacer(Modifier.height(32.dp)) }
    }
}
