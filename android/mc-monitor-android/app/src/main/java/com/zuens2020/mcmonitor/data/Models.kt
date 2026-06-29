package com.zuens2020.mcmonitor.data

import org.json.JSONObject

private fun JSONObject.jsonStr(key: String): String {
    if (!has(key) || isNull(key)) return "-"
    return get(key).toString()
}

data class MonitorStatus(
    val updated: Long,
    val mc: McInfo?,
    val alerts: List<Alert>,
    val summary: Summary?,
    val sys: SysInfo?,
    val mcPlayers: List<PlayerInfo>?,
    val groups: List<ServiceGroup>,
    val mcPerf: McPerf?,
) {
    companion object {
        fun fromJson(raw: String): MonitorStatus {
            val o = JSONObject(raw)
            val mc = o.optJSONObject("mc")?.let { McInfo.from(it) }
            val alerts = buildList {
                val arr = o.optJSONArray("alerts") ?: return@buildList
                for (i in 0 until arr.length()) {
                    add(Alert.from(arr.getJSONObject(i)))
                }
            }
            val summary = o.optJSONObject("summary")?.let { Summary.from(it) }
            val sys = o.optJSONObject("sys")?.let { SysInfo.from(it) }
            val players = o.optJSONArray("mc_players")?.let { arr ->
                buildList {
                    for (i in 0 until arr.length()) {
                        add(PlayerInfo.from(arr.getJSONObject(i)))
                    }
                }
            }
            val groups = buildList {
                val arr = o.optJSONArray("groups") ?: return@buildList
                for (i in 0 until arr.length()) {
                    add(ServiceGroup.from(arr.getJSONObject(i)))
                }
            }
            val mcPerf = o.optJSONObject("mc_perf")?.let { McPerf.from(it) }
            return MonitorStatus(
                updated = o.optLong("updated"),
                mc = mc,
                alerts = alerts,
                summary = summary,
                sys = sys,
                mcPlayers = players,
                groups = groups,
                mcPerf = mcPerf,
            )
        }
    }
}

data class McInfo(
    val online: Boolean,
    val players: String,
    val tps: String,
    val mspt: String,
    val mem: String,
    val uptime: String,
    val connect: String,
    val tunnel: String,
    val version: String,
    val difficulty: String,
    val viewdist: String,
) {
    companion object {
        fun from(o: JSONObject) = McInfo(
            online = o.optBoolean("online"),
            players = o.jsonStr("players"),
            tps = o.jsonStr("tps"),
            mspt = o.jsonStr("mspt"),
            mem = o.jsonStr("mem"),
            uptime = o.jsonStr("uptime"),
            connect = o.jsonStr("connect"),
            tunnel = o.jsonStr("tunnel"),
            version = o.jsonStr("version"),
            difficulty = o.jsonStr("difficulty"),
            viewdist = o.jsonStr("viewdist"),
        )
    }
}

data class McPerf(val tps1m: Double?, val msptAvg: Double?, val msptMax: Double?) {
    companion object {
        fun from(o: JSONObject) = McPerf(
            tps1m = o.optDouble("tps_1m").takeIf { !it.isNaN() },
            msptAvg = o.optDouble("mspt_avg").takeIf { o.has("mspt_avg") && !o.isNull("mspt_avg") },
            msptMax = o.optDouble("mspt_max").takeIf { o.has("mspt_max") && !o.isNull("mspt_max") },
        )
    }
}

data class Alert(
    val level: String,
    val key: String,
    val msg: String,
    val since: String,
) {
    companion object {
        fun from(o: JSONObject) = Alert(
            level = o.optString("level", "info"),
            key = o.optString("key", ""),
            msg = o.optString("msg", ""),
            since = o.optString("since", ""),
        )
    }
}

data class Summary(val up: Int, val warn: Int, val down: Int, val total: Int) {
    companion object {
        fun from(o: JSONObject) = Summary(
            up = o.optInt("up"),
            warn = o.optInt("warn"),
            down = o.optInt("down"),
            total = o.optInt("total"),
        )
    }
}

data class SysInfo(val cpu: String, val mem: String, val disk: String, val load: String) {
    companion object {
        fun from(o: JSONObject) = SysInfo(
            cpu = o.opt("cpu")?.let { "${it}%" } ?: "-",
            mem = if (o.has("mem_pct")) "${o.optDouble("mem_pct")}% (${o.optDouble("mem_used")}/${o.optDouble("mem_total")}G)" else "-",
            disk = if (o.has("disk_pct")) "${o.optDouble("disk_pct")}%" else "-",
            load = o.optJSONArray("load")?.let { arr ->
                (0 until arr.length()).joinToString(", ") { arr.getString(it) }
            } ?: "-",
        )
    }
}

data class ServiceGroup(val title: String, val items: List<ServiceItem>) {
    companion object {
        fun from(o: JSONObject) = ServiceGroup(
            title = o.optString("title", ""),
            items = buildList {
                val arr = o.optJSONArray("items") ?: return@buildList
                for (i in 0 until arr.length()) {
                    add(ServiceItem.from(arr.getJSONObject(i)))
                }
            },
        )
    }
}

data class ServiceItem(
    val id: String,
    val name: String,
    val group: String,
    val sub: String,
    val level: String,
    val detail: String,
    val cpu: String,
    val mem: String,
) {
    companion object {
        fun from(o: JSONObject) = ServiceItem(
            id = o.optString("id", ""),
            name = o.optString("name", "?"),
            group = o.optString("group", ""),
            sub = o.optString("sub", ""),
            level = o.optString("level", "down"),
            detail = o.optString("detail", ""),
            cpu = o.optString("cpu", ""),
            mem = o.optString("mem", ""),
        )
    }
}

data class PlayerInfo(
    val name: String,
    val hp: String,
    val dim: String,
    val pos: String,
    val food: String = "-",
    val xp: String = "-",
    val mode: String = "-",
    val armor: List<String> = emptyList(),
    val onlineFor: String = "-",
    val place: Int = 0,
) {
    companion object {
        fun from(o: JSONObject) = PlayerInfo(
            name = o.optString("name", "?"),
            hp = o.opt("hp")?.toString() ?: "-",
            dim = o.optString("dim", "-"),
            pos = o.optString("pos", "-"),
            food = o.optString("food", "-"),
            xp = o.optString("xp", "-"),
            mode = o.optString("mode", "-"),
            armor = o.optJSONArray("armor")?.let { arr ->
                buildList {
                    for (i in 0 until arr.length()) {
                        val v = arr.optString(i)
                        if (!v.isNullOrBlank() && v != "null") add(v)
                    }
                }
            } ?: emptyList(),
            onlineFor = o.optString("online_for", "-"),
            place = o.optInt("place", 0),
        )
    }
}

data class PlayersResponse(val players: List<PlayerInfo>, val perf: McPerf?) {
    companion object {
        fun fromJson(raw: String): PlayersResponse {
            val o = JSONObject(raw)
            val players = buildList {
                val arr = o.optJSONArray("players") ?: return@buildList
                for (i in 0 until arr.length()) {
                    add(PlayerInfo.from(arr.getJSONObject(i)))
                }
            }
            val perf = o.optJSONObject("perf")?.let { McPerf.from(it) }
            return PlayersResponse(players, perf)
        }
    }
}

data class DetailTile(val key: String, val value: String) {
    companion object {
        fun from(o: JSONObject) = DetailTile(
            key = o.optString("k", ""),
            value = o.optString("v", "-"),
        )
    }
}

data class GrimFlag(val player: String, val check: String, val vl: Int) {
    companion object {
        fun from(o: JSONObject) = GrimFlag(
            player = o.optString("player", ""),
            check = o.optString("check", ""),
            vl = o.optInt("vl", 0),
        )
    }
}

data class ServiceDetail(
    val id: String,
    val name: String,
    val group: String,
    val sub: String,
    val level: String,
    val tiles: List<DetailTile>,
    val hasLog: Boolean,
    val players: List<PlayerInfo>?,
    val securityPlaces: List<Pair<String, Int>>,
    val grimFlags: List<GrimFlag>,
    val securityLog: String?,
    val error: String?,
) {
    companion object {
        fun fromJson(raw: String): ServiceDetail {
            val o = JSONObject(raw)
            if (o.has("error")) {
                return ServiceDetail(
                    id = "", name = "", group = "", sub = "", level = "down",
                    tiles = emptyList(), hasLog = false, players = null,
                    securityPlaces = emptyList(), grimFlags = emptyList(),
                    securityLog = null, error = o.optString("error"),
                )
            }
            val tiles = buildList {
                val arr = o.optJSONArray("tiles") ?: return@buildList
                for (i in 0 until arr.length()) {
                    add(DetailTile.from(arr.getJSONObject(i)))
                }
            }
            val players = o.optJSONArray("players")?.let { arr ->
                buildList {
                    for (i in 0 until arr.length()) {
                        add(PlayerInfo.from(arr.getJSONObject(i)))
                    }
                }
            }
            val sec = o.optJSONObject("security")
            val places = sec?.optJSONArray("places")?.let { arr ->
                buildList {
                    for (i in 0 until arr.length()) {
                        val row = arr.getJSONArray(i)
                        add(row.getString(0) to row.getInt(1))
                    }
                }
            } ?: emptyList()
            val grim = sec?.optJSONArray("grim")?.let { arr ->
                buildList {
                    for (i in 0 until arr.length()) {
                        add(GrimFlag.from(arr.getJSONObject(i)))
                    }
                }
            } ?: emptyList()
            return ServiceDetail(
                id = o.optString("id", ""),
                name = o.optString("name", ""),
                group = o.optString("group", ""),
                sub = o.optString("sub", ""),
                level = o.optString("level", "down"),
                tiles = tiles,
                hasLog = o.optBoolean("has_log"),
                players = players,
                securityPlaces = places,
                grimFlags = grim,
                securityLog = sec?.optString("log"),
                error = null,
            )
        }
    }
}

data class HistoryData(
    val labels: List<String>,
    val cpu: List<Float?>,
    val mem: List<Float?>,
    val load: List<Float?>,
    val source: String,
) {
    companion object {
        fun fromJson(raw: String): HistoryData {
            val o = JSONObject(raw)
            fun numArr(key: String): List<Float?> {
                val arr = o.optJSONArray(key) ?: return emptyList()
                return buildList {
                    for (i in 0 until arr.length()) {
                        val v = arr.opt(i)
                        add(when (v) {
                            null, JSONObject.NULL -> null
                            is Number -> v.toFloat()
                            else -> v.toString().toFloatOrNull()
                        })
                    }
                }
            }
            val labels = buildList {
                val arr = o.optJSONArray("t") ?: return@buildList
                for (i in 0 until arr.length()) add(arr.getString(i))
            }
            return HistoryData(
                labels = labels,
                cpu = numArr("cpu"),
                mem = numArr("mem"),
                load = numArr("load"),
                source = o.optString("source", "live"),
            )
        }
    }
}
