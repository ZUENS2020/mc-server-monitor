package com.zuens2020.mcmonitor.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.ManageAccounts
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.ViewList
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
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
import androidx.navigation.navArgument
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.zuens2020.mcmonitor.ui.components.ErrorPane
import com.zuens2020.mcmonitor.ui.screens.LogsScreen
import com.zuens2020.mcmonitor.ui.screens.ManageScreen
import com.zuens2020.mcmonitor.ui.screens.OverviewScreen
import com.zuens2020.mcmonitor.ui.screens.PlayersScreen
import com.zuens2020.mcmonitor.ui.screens.ServiceDetailScreen
import com.zuens2020.mcmonitor.ui.screens.ServicesScreen

private object Routes {
    const val Overview = "overview"
    const val Players = "players"
    const val Services = "services"
    const val Manage = "manage"
    const val Detail = "detail/{id}"
    const val Logs = "logs/{id}"

    fun detail(id: String) = "detail/$id"
    fun logs(id: String) = "logs/$id"
}

private data class Tab(val route: String, val label: String, val icon: androidx.compose.ui.graphics.vector.ImageVector)

private val tabs = listOf(
    Tab(Routes.Overview, "概览", Icons.Default.Home),
    Tab(Routes.Players, "玩家", Icons.Default.People),
    Tab(Routes.Services, "服务", Icons.Default.ViewList),
    Tab(Routes.Manage, "管理", Icons.Default.ManageAccounts),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(vm: MainViewModel) {
    val ui by vm.state.collectAsStateWithLifecycle()
    val nav = rememberNavController()
    val backStack by nav.currentBackStackEntryAsState()
    val currentRoute = backStack?.destination?.route
    var urlDraft by remember(ui.baseUrl) { mutableStateOf(ui.baseUrl) }

    val isSubScreen = currentRoute?.startsWith("detail/") == true || currentRoute?.startsWith("logs/") == true
    val showBottomBar = !isSubScreen

    LaunchedEffect(currentRoute) {
        if (currentRoute == Routes.Players) vm.startPlayersPolling() else vm.stopPlayersPolling()
        if (currentRoute == Routes.Manage) {
            vm.loadHistory()
            vm.loadAlertLog()
        }
    }

    DisposableEffect(Unit) {
        onDispose { vm.stopPlayersPolling() }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        when {
                            currentRoute?.startsWith("detail/") == true -> ui.detail?.name ?: "服务详情"
                            currentRoute?.startsWith("logs/") == true -> "服务日志"
                            else -> tabs.find { it.route == currentRoute }?.label ?: "MC 监控"
                        }
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
                    NavHost(nav, startDestination = Routes.Overview, modifier = Modifier.fillMaxSize()) {
                        composable(Routes.Overview) {
                            OverviewScreen(
                                status = ui.status,
                                baseUrl = ui.baseUrl,
                                error = ui.error,
                                onDismissAlert = vm::dismissAlert,
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
                        composable(Routes.Services) {
                            ServicesScreen(
                                groups = ui.status?.groups ?: emptyList(),
                                onServiceClick = { id -> nav.navigate(Routes.detail(id)) },
                            )
                        }
                        composable(Routes.Manage) {
                            ManageScreen(
                                alerts = ui.status?.alerts ?: emptyList(),
                                history = ui.history,
                                historyLoading = ui.historyLoading,
                                historyError = ui.historyError,
                                historyRange = ui.historyRange,
                                alertLog = ui.alertLog,
                                alertLogLoading = ui.alertLogLoading,
                                baseUrl = ui.baseUrl,
                                urlDraft = urlDraft,
                                onUrlDraftChange = { urlDraft = it },
                                onSaveUrl = { vm.saveBaseUrl(urlDraft) },
                                onDismissAlert = vm::dismissAlert,
                                onLoadHistory = vm::saveHistoryRange,
                                onLoadAlertLog = vm::loadAlertLog,
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
