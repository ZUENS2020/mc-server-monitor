package com.zuens2020.mcmonitor.ui.screens

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.zuens2020.mcmonitor.data.PlayersResponse
import com.zuens2020.mcmonitor.ui.components.ErrorPane
import com.zuens2020.mcmonitor.ui.components.PerfCard
import com.zuens2020.mcmonitor.ui.components.PlayerCard
import com.zuens2020.mcmonitor.ui.components.ScreenList

@Composable
fun PlayersScreen(
    data: PlayersResponse?,
    loading: Boolean,
    error: String?,
    onRetry: () -> Unit,
) {
    when {
        loading && data == null -> {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        }
        error != null && data == null -> ErrorPane(error, onRetry)
        else -> ScreenList {
            data?.perf?.let { item { PerfCard(it) } }
            item {
                Text(
                    "在线 ${data?.players?.size ?: 0} 人",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            if (data?.players.isNullOrEmpty()) {
                item { Text("暂无在线玩家", color = MaterialTheme.colorScheme.onSurfaceVariant) }
            } else {
                items(data!!.players, key = { it.name }) { p ->
                    PlayerCard(p, detailed = true)
                }
            }
            item { Spacer(Modifier.height(32.dp)) }
        }
    }
}
