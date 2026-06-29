package com.zuens2020.mcmonitor.ui.screens

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import com.zuens2020.mcmonitor.ui.components.ErrorPane
import com.zuens2020.mcmonitor.ui.components.LogText
import com.zuens2020.mcmonitor.ui.components.ScreenList

@Composable
fun LogsScreen(
    logs: String?,
    loading: Boolean,
    error: String?,
    onRetry: () -> Unit,
) {
    when {
        loading -> {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        }
        error != null -> ErrorPane(error, onRetry)
        logs != null -> ScreenList {
            item { LogText(logs) }
        }
    }
}
