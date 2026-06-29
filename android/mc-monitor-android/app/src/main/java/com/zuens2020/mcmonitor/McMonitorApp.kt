package com.zuens2020.mcmonitor

import android.app.Application
import com.zuens2020.mcmonitor.data.MonitorRepository
import com.zuens2020.mcmonitor.data.SettingsRepository

class McMonitorApp : Application() {
    val settings by lazy { SettingsRepository(this) }
    val monitor by lazy { MonitorRepository() }
}
