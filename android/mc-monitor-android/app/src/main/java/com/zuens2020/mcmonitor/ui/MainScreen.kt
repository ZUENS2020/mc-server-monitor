package com.zuens2020.mcmonitor.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.ShowChart
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.zuens2020.mcmonitor.data.AlertLogEntry
import com.zuens2020.mcmonitor.ui.components.ErrorPane
import com.zuens2020.mcmonitor.ui.screens.AlertLogScreen
import com.zuens2020.mcmonitor.ui.screens.ControlScreen
import com.zuens2020.mcmonitor.ui.screens.LogsScreen
import com.zuens2020.mcmonitor.ui.screens.OverviewScreen
import com.zuens2020.mcmonitor.ui.screens.PerformanceScreen
import com.zuens2020.mcmonitor.ui.screens.PlayersScreen
import com.zuens2020.mcmonitor.ui.screens.ServiceDetailScreen

private object Routes {
    const val Overview = "overview"
    const val Players = "players"
    const val Performance = "performance"
    const val Control = "control"
    const val AlertLog = "alertlog"
    const val Detail = "detail/{id}"
    const val Logs = "logs/{id}"

    fun detail(id: String) = "detail/$id"
    fun logs(id: String) = "logs/$id"
}

private data class Tab(val route: String, val label: String, val icon: androidx.compose.ui.graphics.vector.ImageVector)

private val tabs = listOf(
    Tab(Routes.Overview, "概览", Icons.Default.Home),
    Tab(Routes.Players, "玩家", Icons.Default.People),
    Tab(Routes.Performance, "性能", Icons.Default.ShowChart),
    Tab(Routes.Control, "控制", Icons.Default.Tune),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(vm: MainViewModel) {
    val ui by vm.state.collectAsStateWithLifecycle()
    val nav = rememberNavController()
    val backStack by nav.currentBackStackEntryAsState()
    val currentRoute = backStack?.destination?.route
    var urlDraft by remember(ui.baseUrl) { mutableStateOf(ui.baseUrl) }
    var showSettings by remember { mutableStateOf(false) }

    val isSubScreen = currentRoute?.startsWith("detail/") == true ||
        currentRoute?.startsWith("logs/") == true ||
        currentRoute == Routes.AlertLog
    val showBottomBar = !isSubScreen

    LaunchedEffect(currentRoute) {
        when (currentRoute) {
            Routes.Overview, Routes.Players -> vm.startPlayersPolling()
            else -> vm.stopPlayersPolling()
        }
        when (currentRoute) {
            Routes.Performance, Routes.Overview -> vm.loadHistory()
            Routes.Control -> vm.loadCrafty()
            Routes.AlertLog -> vm.loadAlertLog()
        }
    }

    DisposableEffect(Unit) {
        onDispose { vm.stopPlayersPolling() }
    }

    if (showSettings) {
        AlertDialog(
            onDismissRequest = { showSettings = false },
            title = { Text("服务器地址") },
            text = {
                OutlinedTextField(
                    value = urlDraft,
                    onValueChange = { urlDraft = it },
                    label = { Text("监控面板 URL") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    vm.saveBaseUrl(urlDraft)
                    showSettings = false
                }) { Text("保存") }
            },
            dismissButton = {
                TextButton(onClick = { showSettings = false }) { Text("取消") }
            },
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        when {
                            currentRoute == Routes.AlertLog -> "预警日志"
                            currentRoute?.startsWith("detail/") == true -> ui.detail?.name ?: "服务详情"
                            currentRoute?.startsWith("logs/") == true -> "服务日志"
                            else -> tabs.find { it.route == currentRoute }?.label ?: "MC 监控"
                        },
                    )
                },
                navigationIcon = {
                    if (isSubScreen) {
                        IconButton(onClick = { nav.popBackStack() }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                        }
                    }
                },
                actions = {
                    IconButton(onClick = { vm.refresh() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "刷新")
                    }
                    IconButton(onClick = {
                        urlDraft = ui.baseUrl
                        showSettings = true
                    }) {
                        Icon(Icons.Default.Settings, contentDescription = "设置")
                    }
                },
            )
        },
        bottomBar = {
            if (showBottomBar) {
                NavigationBar {
                    tabs.forEach { tab ->
                        NavigationBarItem(
                            selected = currentRoute == tab.route,
                            onClick = {
                                nav.navigate(tab.route) {
                                    popUpTo(nav.graph.findStartDestination().id) { saveState = true }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            icon = { Icon(tab.icon, contentDescription = tab.label) },
                            label = { Text(tab.label) },
                        )
                    }
                }
            }
        },
    ) { padding ->
        PullToRefreshBox(
            isRefreshing = ui.refreshing,
            onRefresh = { vm.refresh() },
            modifier = Modifier.fillMaxSize().padding(padding),
        ) {
            when {
                ui.loading && ui.status == null && currentRoute == Routes.Overview -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
                ui.error != null && ui.status == null && currentRoute == Routes.Overview -> {
                    ErrorPane(ui.error!!) { vm.refresh() }
                }
                else -> {
                    val alertEntries = remember(ui.alertLog) {
                        ui.alertLog?.let { AlertLogEntry.parse(it) } ?: emptyList()
                    }
                    NavHost(nav, startDestination = Routes.Overview, modifier = Modifier.fillMaxSize()) {
                        composable(Routes.Overview) {
                            OverviewScreen(
                                status = ui.status,
                                players = ui.players?.players,
                                baseUrl = ui.baseUrl,
                                error = ui.error,
                                onDismissAlert = vm::dismissAlert,
                                onOpenPlayers = { nav.navigate(Routes.Players) },
                                onOpenPerformance = { nav.navigate(Routes.Performance) },
                                onOpenAlertLog = { nav.navigate(Routes.AlertLog) },
                                onOpenControl = { nav.navigate(Routes.Control) },
                            )
                        }
                        composable(Routes.Players) {
                            PlayersScreen(
                                data = ui.players,
                                loading = ui.playersLoading,
                                error = ui.playersError,
                                onRetry = vm::refreshPlayers,
                            )
                        }
                        composable(Routes.Performance) {
                            PerformanceScreen(
                                mc = ui.status?.mc,
                                mcPerf = ui.status?.mcPerf,
                                playersPerf = ui.players?.perf,
                                sys = ui.status?.sys,
                                history = ui.history,
                                historyLoading = ui.historyLoading,
                                historyError = ui.historyError,
                                historyRange = ui.historyRange,
                                onLoadHistory = vm::saveHistoryRange,
                            )
                        }
                        composable(Routes.Control) {
                            ControlScreen(
                                crafty = ui.crafty,
                                craftyLoading = ui.craftyLoading,
                                craftyError = ui.craftyError,
                                craftyActionRunning = ui.craftyActionRunning,
                                craftyMessage = ui.craftyMessage,
                                alerts = ui.status?.alerts ?: emptyList(),
                                groups = ui.status?.groups ?: emptyList(),
                                onCraftyAction = vm::runCraftyAction,
                                onLoadCrafty = vm::loadCrafty,
                                onDismissAlert = vm::dismissAlert,
                                onOpenAlertLog = { nav.navigate(Routes.AlertLog) },
                                onServiceClick = { id -> nav.navigate(Routes.detail(id)) },
                            )
                        }
                        composable(Routes.AlertLog) {
                            AlertLogScreen(
                                entries = alertEntries,
                                loading = ui.alertLogLoading,
                                error = ui.alertLogError,
                                onRetry = vm::loadAlertLog,
                            )
                        }
                        composable(
                            route = Routes.Detail,
                            arguments = listOf(navArgument("id") { type = NavType.StringType }),
                        ) { entry ->
                            val id = entry.arguments?.getString("id") ?: return@composable
                            LaunchedEffect(id) { vm.loadDetail(id) }
                            ServiceDetailScreen(
                                detail = ui.detail,
                                loading = ui.detailLoading,
                                error = ui.detailError,
                                onRetry = { vm.loadDetail(id) },
                                onOpenLogs = { nav.navigate(Routes.logs(id)) },
                            )
                        }
                        composable(
                            route = Routes.Logs,
                            arguments = listOf(navArgument("id") { type = NavType.StringType }),
                        ) { entry ->
                            val id = entry.arguments?.getString("id") ?: return@composable
                            LaunchedEffect(id) { vm.loadLogs(id) }
                            LogsScreen(
                                logs = ui.logs,
                                loading = ui.logsLoading,
                                error = ui.logsError,
                                onRetry = { vm.loadLogs(id) },
                            )
                        }
                    }
                }
            }
        }
    }
}
