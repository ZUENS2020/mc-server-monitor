package com.zuens2020.mcmonitor

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.lifecycle.viewmodel.compose.viewModel
import com.zuens2020.mcmonitor.ui.MainScreen
import com.zuens2020.mcmonitor.ui.MainViewModel
import com.zuens2020.mcmonitor.ui.theme.McMonitorTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val app = application as McMonitorApp
        setContent {
            McMonitorTheme(darkTheme = isSystemInDarkTheme()) {
                val vm: MainViewModel = viewModel(
                    factory = MainViewModel.factory(app.settings, app.monitor)
                )
                MainScreen(vm)
            }
        }
    }
}
