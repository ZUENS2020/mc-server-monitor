package com.zuens2020.mcmonitor.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

private val Context.dataStore by preferencesDataStore("settings")

class SettingsRepository(private val context: Context) {
    private val baseUrlKey = stringPreferencesKey("base_url")
    private val historyRangeKey = intPreferencesKey("history_range")

    val baseUrl: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[baseUrlKey] ?: DEFAULT_URL
    }

    val historyRange: Flow<Int> = context.dataStore.data.map { prefs ->
        prefs[historyRangeKey] ?: 60
    }

    suspend fun setBaseUrl(url: String) {
        context.dataStore.edit { it[baseUrlKey] = url.trim().trimEnd('/') }
    }

    suspend fun setHistoryRange(minutes: Int) {
        context.dataStore.edit { it[historyRangeKey] = minutes.coerceIn(10, 360) }
    }

    companion object {
        const val DEFAULT_URL = "https://monitor.zuens2020.work"
    }
}

class MonitorRepository {
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()

    suspend fun fetchStatus(baseUrl: String): Result<MonitorStatus> = getJson(baseUrl, "/api/status") {
        MonitorStatus.fromJson(it)
    }

    suspend fun fetchPlayers(baseUrl: String): Result<PlayersResponse> = getJson(baseUrl, "/api/players") {
        PlayersResponse.fromJson(it)
    }

    suspend fun fetchDetail(baseUrl: String, id: String): Result<ServiceDetail> =
        getJson(baseUrl, "/api/detail?id=$id") { ServiceDetail.fromJson(it) }

    suspend fun fetchLogs(baseUrl: String, id: String, tail: Int = 400): Result<String> = withContext(Dispatchers.IO) {
        runCatching {
            val body = requestText(baseUrl, "/api/logs?id=$id&tail=$tail")
            JSONObject(body).optString("text", "(无日志)")
        }
    }

    suspend fun fetchHistory(baseUrl: String, rangeMinutes: Int): Result<HistoryData> =
        getJson(baseUrl, "/api/history?range=$rangeMinutes") { HistoryData.fromJson(it) }

    suspend fun fetchAlertLog(baseUrl: String, tail: Int = 200): Result<String> = withContext(Dispatchers.IO) {
        runCatching {
            val body = requestText(baseUrl, "/api/alertlog?tail=$tail")
            JSONObject(body).optString("text", "(暂无报警记录)")
        }
    }

    suspend fun fetchCrafty(baseUrl: String): Result<CraftyInfo> =
        getJson(baseUrl, "/api/crafty") { CraftyInfo.fromJson(it) }

    suspend fun craftyAction(baseUrl: String, action: String): Result<CraftyActionResult> =
        withContext(Dispatchers.IO) {
            runCatching {
                val url = baseUrl.trimEnd('/') + "/api/crafty/action"
                val json = """{"action":"$action"}"""
                val req = Request.Builder()
                    .url(url)
                    .header("User-Agent", "McMonitor-Android/1.2")
                    .post(json.toRequestBody("application/json".toMediaType()))
                    .build()
                client.newCall(req).execute().use { resp ->
                    val body = resp.body?.string() ?: error("empty body")
                    if (!resp.isSuccessful) error("HTTP ${resp.code}: ${body.take(120)}")
                    CraftyActionResult.fromJson(ensureJson(body, "/api/crafty/action"))
                }
            }
        }

    suspend fun dismissAlert(baseUrl: String, key: String): Result<Boolean> = withContext(Dispatchers.IO) {
        runCatching {
            val url = baseUrl.trimEnd('/') + "/api/alerts/dismiss"
            val json = """{"key":"${key.replace("\"", "\\\"")}"}"""
            val req = Request.Builder()
                .url(url)
                .header("User-Agent", "McMonitor-Android/1.1")
                .post(json.toRequestBody("application/json".toMediaType()))
                .build()
            client.newCall(req).execute().use { resp ->
                val body = resp.body?.string() ?: error("empty body")
                if (!resp.isSuccessful) error("HTTP ${resp.code}")
                JSONObject(body).optBoolean("ok", false)
            }
        }
    }

    private suspend inline fun <T> getJson(
        baseUrl: String,
        path: String,
        crossinline parse: (String) -> T,
    ): Result<T> = withContext(Dispatchers.IO) {
        runCatching {
            parse(requestText(baseUrl, path))
        }
    }

    private fun requestText(baseUrl: String, path: String): String {
        val url = baseUrl.trimEnd('/') + path
        val req = Request.Builder()
            .url(url)
            .header("User-Agent", "McMonitor-Android/1.2.1")
            .header("Accept", "application/json")
            .get()
            .build()
        return client.newCall(req).execute().use { resp ->
            val body = resp.body?.string() ?: error("empty body")
            if (!resp.isSuccessful) error("HTTP ${resp.code}: ${body.take(120)}")
            ensureJson(body, path)
        }
    }

    private fun ensureJson(body: String, path: String): String {
        val trimmed = body.trimStart()
        if (trimmed.startsWith("<!") || trimmed.startsWith("<html", ignoreCase = true)) {
            error("接口 $path 未就绪，请更新并重启 dashboard 服务")
        }
        return body
    }
}
