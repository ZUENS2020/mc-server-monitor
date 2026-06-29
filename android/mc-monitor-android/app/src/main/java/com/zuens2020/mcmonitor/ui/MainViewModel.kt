package com.zuens2020.mcmonitor.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.zuens2020.mcmonitor.data.CraftyInfo
import com.zuens2020.mcmonitor.data.HistoryData
import com.zuens2020.mcmonitor.data.MonitorRepository
import com.zuens2020.mcmonitor.data.MonitorStatus
import com.zuens2020.mcmonitor.data.PlayersResponse
import com.zuens2020.mcmonitor.data.ServiceDetail
import com.zuens2020.mcmonitor.data.SettingsRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

data class UiState(
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val baseUrl: String = SettingsRepository.DEFAULT_URL,
    val status: MonitorStatus? = null,
    val error: String? = null,
    val players: PlayersResponse? = null,
    val playersLoading: Boolean = false,
    val playersError: String? = null,
    val detail: ServiceDetail? = null,
    val detailLoading: Boolean = false,
    val detailError: String? = null,
    val logs: String? = null,
    val logsLoading: Boolean = false,
    val logsError: String? = null,
    val history: HistoryData? = null,
    val historyLoading: Boolean = false,
    val historyError: String? = null,
    val historyRange: Int = 60,
    val alertLog: String? = null,
    val alertLogLoading: Boolean = false,
    val alertLogError: String? = null,
    val dismissingKeys: Set<String> = emptySet(),
    val crafty: CraftyInfo? = null,
    val craftyLoading: Boolean = false,
    val craftyError: String? = null,
    val craftyActionRunning: String? = null,
    val craftyMessage: String? = null,
)

class MainViewModel(
    private val settings: SettingsRepository,
    private val monitor: MonitorRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()

    private var pollJob: Job? = null
    private var playersPollJob: Job? = null

    init {
        viewModelScope.launch {
            settings.baseUrl.collect { url ->
                _state.update { it.copy(baseUrl = url) }
                restartPolling()
            }
        }
        viewModelScope.launch {
            settings.historyRange.collect { range ->
                _state.update { it.copy(historyRange = range) }
            }
        }
    }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(refreshing = true, error = null) }
            loadStatus()
            loadPlayers()
            _state.update { it.copy(refreshing = false, loading = false) }
        }
    }

    fun saveBaseUrl(url: String) {
        viewModelScope.launch { settings.setBaseUrl(url) }
    }

    fun saveHistoryRange(minutes: Int) {
        viewModelScope.launch {
            settings.setHistoryRange(minutes)
            _state.update { it.copy(historyRange = minutes, history = null, historyLoading = true, historyError = null) }
            loadHistory(minutes)
        }
    }

    fun refreshPlayers() {
        viewModelScope.launch { loadPlayers() }
    }

    fun startPlayersPolling() {
        if (playersPollJob?.isActive == true) return
        playersPollJob = viewModelScope.launch {
            while (isActive) {
                loadPlayers()
                delay(3_000)
            }
        }
    }

    fun stopPlayersPolling() {
        playersPollJob?.cancel()
        playersPollJob = null
    }

    fun loadDetail(id: String) {
        viewModelScope.launch {
            _state.update { it.copy(detailLoading = true, detailError = null, detail = null) }
            val url = settings.baseUrl.first()
            monitor.fetchDetail(url, id)
                .onSuccess { detail -> _state.update { it.copy(detail = detail, detailLoading = false) } }
                .onFailure { e ->
                    _state.update {
                        it.copy(detailLoading = false, detailError = e.message ?: "加载失败")
                    }
                }
        }
    }

    fun loadLogs(id: String) {
        viewModelScope.launch {
            _state.update { it.copy(logsLoading = true, logsError = null, logs = null) }
            val url = settings.baseUrl.first()
            monitor.fetchLogs(url, id)
                .onSuccess { text -> _state.update { it.copy(logs = text, logsLoading = false) } }
                .onFailure { e ->
                    _state.update { it.copy(logsLoading = false, logsError = e.message ?: "加载失败") }
                }
        }
    }

    fun loadHistory(range: Int = _state.value.historyRange) {
        viewModelScope.launch {
            _state.update { it.copy(historyLoading = true, historyError = null, historyRange = range) }
            val url = settings.baseUrl.first()
            monitor.fetchHistory(url, range)
                .onSuccess { data ->
                    _state.update { it.copy(history = data, historyLoading = false, historyRange = data.rangeMinutes) }
                }
                .onFailure { e ->
                    _state.update { it.copy(historyLoading = false, historyError = e.message ?: "加载失败") }
                }
        }
    }

    fun loadAlertLog() {
        viewModelScope.launch {
            _state.update { it.copy(alertLogLoading = true, alertLogError = null) }
            val url = settings.baseUrl.first()
            monitor.fetchAlertLog(url, tail = 300)
                .onSuccess { text -> _state.update { it.copy(alertLog = text, alertLogLoading = false) } }
                .onFailure { e ->
                    _state.update { it.copy(alertLogLoading = false, alertLogError = e.message ?: "加载失败") }
                }
        }
    }

    fun loadCrafty() {
        viewModelScope.launch {
            _state.update { it.copy(craftyLoading = true, craftyError = null) }
            val url = settings.baseUrl.first()
            monitor.fetchCrafty(url)
                .onSuccess { info -> _state.update { it.copy(crafty = info, craftyLoading = false) } }
                .onFailure { e ->
                    _state.update { it.copy(craftyLoading = false, craftyError = e.message ?: "加载失败") }
                }
        }
    }

    fun runCraftyAction(action: String) {
        if (_state.value.craftyActionRunning != null) return
        viewModelScope.launch {
            _state.update { it.copy(craftyActionRunning = action, craftyMessage = null) }
            val url = settings.baseUrl.first()
            monitor.craftyAction(url, action)
                .onSuccess { result ->
                    _state.update {
                        it.copy(
                            craftyActionRunning = null,
                            craftyMessage = if (result.ok) actionLabel(action) + " 已发送" else (result.error ?: "操作失败"),
                        )
                    }
                    delay(1500)
                    loadCrafty()
                    loadStatus()
                }
                .onFailure { e ->
                    _state.update {
                        it.copy(craftyActionRunning = null, craftyMessage = e.message ?: "操作失败")
                    }
                }
        }
    }

    private fun actionLabel(action: String) = when (action) {
        "start_server" -> "启动"
        "stop_server" -> "停止"
        "restart_server" -> "重启"
        "backup_server" -> "备份"
        else -> action
    }

    fun dismissAlert(key: String) {
        if (key.isBlank() || _state.value.dismissingKeys.contains(key)) return
        viewModelScope.launch {
            _state.update { it.copy(dismissingKeys = it.dismissingKeys + key) }
            val url = settings.baseUrl.first()
            monitor.dismissAlert(url, key)
                .onSuccess {
                    _state.update { s ->
                        s.copy(
                            status = s.status?.let { st ->
                                st.copy(alerts = st.alerts.filter { it.key != key })
                            },
                            dismissingKeys = s.dismissingKeys - key,
                        )
                    }
                }
                .onFailure {
                    _state.update { it.copy(dismissingKeys = it.dismissingKeys - key) }
                }
        }
    }

    private fun restartPolling() {
        pollJob?.cancel()
        pollJob = viewModelScope.launch {
            _state.update { it.copy(loading = true) }
            loadStatus()
            _state.update { it.copy(loading = false) }
            while (isActive) {
                delay(5_000)
                loadStatus()
            }
        }
    }

    private suspend fun loadStatus() {
        val url = settings.baseUrl.first()
        monitor.fetchStatus(url)
            .onSuccess { status -> _state.update { it.copy(status = status, error = null) } }
            .onFailure { e ->
                val msg = e.message?.takeIf { it.isNotBlank() } ?: e.javaClass.simpleName
                _state.update { it.copy(error = msg) }
            }
    }

    private suspend fun loadPlayers() {
        _state.update { it.copy(playersLoading = it.players == null) }
        val url = settings.baseUrl.first()
        monitor.fetchPlayers(url)
            .onSuccess { data ->
                _state.update { it.copy(players = data, playersLoading = false, playersError = null) }
            }
            .onFailure { e ->
                _state.update {
                    it.copy(
                        playersLoading = false,
                        playersError = e.message ?: "加载失败",
                    )
                }
            }
    }

    companion object {
        fun factory(
            settings: SettingsRepository,
            monitor: MonitorRepository,
        ) = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return MainViewModel(settings, monitor) as T
            }
        }
    }
}
