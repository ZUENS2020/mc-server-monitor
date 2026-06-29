package com.zuens2020.mcmonitor.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.zuens2020.mcmonitor.data.Alert
import com.zuens2020.mcmonitor.data.CraftyInfo
import com.zuens2020.mcmonitor.data.ServiceGroup
import com.zuens2020.mcmonitor.ui.components.AlertCard
import com.zuens2020.mcmonitor.ui.components.ScreenList
import com.zuens2020.mcmonitor.ui.components.ServiceItemCard
import com.zuens2020.mcmonitor.ui.components.StatusChip

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ControlScreen(
    crafty: CraftyInfo?,
    craftyLoading: Boolean,
    craftyError: String?,
    craftyActionRunning: String?,
    craftyMessage: String?,
    alerts: List<Alert>,
    groups: List<ServiceGroup>,
    onCraftyAction: (String) -> Unit,
    onLoadCrafty: () -> Unit,
    onDismissAlert: (String) -> Unit,
    onOpenAlertLog: () -> Unit,
    onServiceClick: (String) -> Unit,
) {
    ScreenList {
        item {
            Text("Crafty 控制", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            CraftyPanel(
                crafty = crafty,
                loading = craftyLoading,
                error = craftyError,
                actionRunning = craftyActionRunning,
                message = craftyMessage,
                onAction = onCraftyAction,
                onRefresh = onLoadCrafty,
            )
        }
        item {
            RowActions(onOpenAlertLog)
        }
        if (alerts.isNotEmpty()) {
            item {
                Text("活跃预警", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            }
            items(alerts, key = { it.key.ifBlank { it.msg } }) { a ->
                AlertCard(a, onDismiss = if (a.key.isNotBlank() && a.level != "info") {
                    { onDismissAlert(a.key) }
                } else null)
            }
        }
        item {
            Text("服务", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        }
        if (groups.isEmpty()) {
            item { Text("暂无服务数据", color = MaterialTheme.colorScheme.onSurfaceVariant) }
        } else {
            groups.forEach { group ->
                item {
                    Text(group.title, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                items(group.items, key = { it.id }) { item ->
                    ServiceItemCard(item) { onServiceClick(item.id) }
                }
            }
        }
        item { Spacer(Modifier.height(32.dp)) }
    }
}

@Composable
private fun RowActions(onOpenAlertLog: () -> Unit) {
    FilledTonalButton(onClick = onOpenAlertLog, modifier = Modifier.fillMaxWidth()) {
        Text("预警历史日志")
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun CraftyPanel(
    crafty: CraftyInfo?,
    loading: Boolean,
    error: String?,
    actionRunning: String?,
    message: String?,
    onAction: (String) -> Unit,
    onRefresh: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            when {
                loading && crafty == null -> Text("连接 Crafty…", color = MaterialTheme.colorScheme.onSurfaceVariant)
                crafty == null || !crafty.enabled -> Text(
                    error ?: "Crafty 未配置。若按钮无响应，请更新 NEC 上的 dashboard.py 并重启监控服务。",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                else -> {
                    androidx.compose.foundation.layout.Row(
                        verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text(crafty.serverName, fontWeight = FontWeight.Bold)
                        StatusChip(if (crafty.mcOnline) "运行中" else "已停止", crafty.mcOnline)
                    }
                    Text(
                        "玩家 ${crafty.players} · 上次备份 ${crafty.lastBackupAgo ?: "未知"}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    if (!crafty.authenticated) {
                        Text("Crafty 认证失败，请检查凭据", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                    }
                    if (!crafty.backupEnabled) {
                        Text("自动备份已关闭，手动备份仍可用", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        if ("start_server" in crafty.actions) CraftyButton("启动", "start_server", actionRunning, onAction)
                        if ("stop_server" in crafty.actions) CraftyButton("停止", "stop_server", actionRunning, onAction)
                        if ("restart_server" in crafty.actions) CraftyButton("重启", "restart_server", actionRunning, onAction)
                        if ("backup_server" in crafty.actions) CraftyButton("备份", "backup_server", actionRunning, onAction)
                    }
                }
            }
            if (message != null) {
                Text(message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
            }
            OutlinedButton(onClick = onRefresh, enabled = actionRunning == null) {
                Text("刷新状态")
            }
        }
    }
}

@Composable
private fun CraftyButton(label: String, action: String, running: String?, onAction: (String) -> Unit) {
    val busy = running == action
    Button(onClick = { onAction(action) }, enabled = running == null) {
        Text(if (busy) "…" else label)
    }
}
