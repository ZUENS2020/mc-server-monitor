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
import com.zuens2020.mcmonitor.data.ServiceGroup
import com.zuens2020.mcmonitor.ui.components.ScreenList
import com.zuens2020.mcmonitor.ui.components.ServiceItemCard

@Composable
fun ServicesScreen(
    groups: List<ServiceGroup>,
    onServiceClick: (String) -> Unit,
) {
    if (groups.isEmpty()) {
        ScreenList {
            item { Text("暂无服务数据", color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
        return
    }
    ScreenList {
        groups.forEach { group ->
            item {
                Text(group.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            }
            items(group.items, key = { it.id }) { item ->
                ServiceItemCard(item) { onServiceClick(item.id) }
            }
        }
        item { Spacer(Modifier.height(32.dp)) }
    }
}
