package com.zuens2020.mcmonitor.ui.screens

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.zuens2020.mcmonitor.data.ServiceDetail
import com.zuens2020.mcmonitor.ui.components.ErrorPane
import com.zuens2020.mcmonitor.ui.components.LevelDot
import com.zuens2020.mcmonitor.ui.components.MetricRow
import com.zuens2020.mcmonitor.ui.components.PlayerCard
import com.zuens2020.mcmonitor.ui.components.ScreenList

@Composable
fun ServiceDetailScreen(
    detail: ServiceDetail?,
    loading: Boolean,
    error: String?,
    onRetry: () -> Unit,
    onOpenLogs: () -> Unit,
) {
    when {
        loading -> {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        }
        error != null -> ErrorPane(error, onRetry)
        detail != null -> ScreenList {
            item {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    LevelDot(detail.level)
                    Text(
                        detail.name,
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(start = 8.dp),
                    )
                }
                if (detail.sub.isNotBlank()) {
                    Text(detail.sub, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            if (detail.hasLog) {
                item {
                    FilledTonalButton(onClick = onOpenLogs, modifier = Modifier.fillMaxWidth()) {
                        Text("查看日志")
                    }
                }
            }
            items(detail.tiles, key = { it.key }) { tile ->
                Card(Modifier.fillMaxWidth()) {
                    MetricRow(tile.key, tile.value, modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp))
                }
            }
            detail.players?.takeIf { it.isNotEmpty() }?.let { players ->
                item {
                    Text("玩家详情", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                }
                items(players, key = { it.name }) { PlayerCard(it, detailed = true) }
            }
            if (detail.securityPlaces.isNotEmpty()) {
                item {
                    Text("CoreProtect 放置 (1min)", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                }
                items(detail.securityPlaces, key = { it.first }) { (name, count) ->
                    Card(Modifier.fillMaxWidth()) {
                        MetricRow(name, "$count 块/分", modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp))
                    }
                }
            }
            if (detail.grimFlags.isNotEmpty()) {
                item {
                    Text("GrimAC 近期标记", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                }
                items(detail.grimFlags, key = { "${it.player}-${it.check}" }) { g ->
                    Card(Modifier.fillMaxWidth()) {
                        Text("${g.player} · ${g.check} (vl ${g.vl})", modifier = Modifier.padding(12.dp))
                    }
                }
            }
            item { Spacer(Modifier.height(32.dp)) }
        }
    }
}
