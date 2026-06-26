#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NEC 服务聚合监控面板 v3 — Crafty 风格 / 全直角 / 整机总览 / 日志高亮。纯标准库。"""
import glob, json, os, re, shutil, socket, ssl, struct, subprocess, threading, time
import urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8765
REFRESH = 5

ENV = dict(os.environ)
ENV.setdefault("XDG_RUNTIME_DIR", "/run/user/%d" % os.getuid())


def _mc_log():
    g = sorted(glob.glob(os.path.expanduser("~/crafty/servers/*/logs/latest.log")),
               key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0, reverse=True)
    return g[0] if g else ""


MC_LOG = _mc_log()

SERVICES = {
    "mihomo":      {"name": "mihomo 代理",  "group": "代理 · 穿透 · Cloudflare", "kind": "systemd", "unit": "mihomo", "sub": "TUN 全局代理",        "log": ("journal_user", "mihomo")},
    "frpc":        {"name": "frpc 樱花穿透", "group": "代理 · 穿透 · Cloudflare", "kind": "systemd", "unit": "frpc",   "sub": "frp-top.com:18650",   "log": ("journal_user", "frpc")},
    "cloudflared": {"name": "cloudflared",  "group": "代理 · 穿透 · Cloudflare", "kind": "proc",    "proc": "cloudflared", "sub": "Cloudflare 隧道", "log": ("journal_sys", "cloudflared")},
    "redis":       {"name": "Redis",        "group": "数据库", "kind": "container", "container": "redis",      "sub": "内网 6379",         "log": ("docker", "redis")},
    "mongo":       {"name": "MongoDB",      "group": "数据库", "kind": "container", "container": "mongo",      "sub": "内网 27017",        "log": ("docker", "mongo")},
    "postgres":    {"name": "PostgreSQL",   "group": "数据库", "kind": "container", "container": "litellm_db", "sub": "litellm_db · 5432", "log": ("docker", "litellm_db")},
    "mc":          {"name": "MC 服务器",     "group": "应用服务", "kind": "port",    "port": 25565,             "sub": "Paper 1.21.10 · 25565", "log": ("file", MC_LOG)},
    "sillytavern": {"name": "SillyTavern",  "group": "应用服务", "kind": "container", "container": "sillytavern", "port": 8000, "sub": "AI 对话 · 8000", "log": ("docker", "sillytavern")},
    "litellm":     {"name": "LiteLLM",      "group": "应用服务", "kind": "container", "container": "litellm-litellm-1", "port": 4000, "sub": "LLM 网关 · 4000", "log": ("docker", "litellm-litellm-1")},
    "opendesign":  {"name": "open-design",  "group": "应用服务", "kind": "container", "container": "open-design", "port": 7456, "sub": "7456",          "log": ("docker", "open-design")},
    "searxng":     {"name": "SearXNG",      "group": "应用服务", "kind": "container", "container": "searxng",    "port": 8080, "sub": "聚合搜索 · 8080", "log": ("docker", "searxng")},
    "n8n":         {"name": "n8n",          "group": "应用服务", "kind": "container", "container": "n8n",        "sub": "工作流自动化",       "log": ("docker", "n8n")},
}
ORDER = ["mihomo", "frpc", "cloudflared", "redis", "mongo", "postgres",
         "mc", "sillytavern", "litellm", "opendesign", "searxng", "n8n"]
GROUP_ORDER = ["代理 · 穿透 · Cloudflare", "数据库", "应用服务"]

_lock = threading.Lock()
_state = {"groups": [], "sys": {}, "alerts": [], "mc_players": None, "mc_perf": None, "updated": 0, "summary": {"up": 0, "warn": 0, "down": 0, "total": 0}}
_prev = {"cpu": None, "net": None, "t": None}


def sh(args, timeout=12):
    try:
        return subprocess.run(args, capture_output=True, text=True, env=ENV, timeout=timeout).stdout
    except Exception:
        return ""


def docker_ps():
    out = sh(["docker", "ps", "-a", "--format", "{{.Names}}\t{{.State}}\t{{.Status}}"])
    d = {}
    for line in out.splitlines():
        p = line.split("\t")
        if len(p) >= 3:
            h = ""
            m = re.search(r"\((healthy|unhealthy|health: starting)\)", p[2])
            if m:
                h = m.group(1)
            d[p[0]] = {"state": p[1], "status": p[2], "health": h}
    return d


def docker_stats():
    out = sh(["docker", "stats", "--no-stream", "--format", "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"], 15)
    d = {}
    for line in out.splitlines():
        p = line.split("\t")
        if len(p) >= 3:
            d[p[0]] = {"cpu": p[1].strip(), "mem": p[2].split("/")[0].strip()}
    return d


def systemd_active(unit):
    return sh(["systemctl", "--user", "is-active", unit]).strip() == "active"


def pid_of(svc):
    if svc["kind"] == "systemd":
        v = sh(["systemctl", "--user", "show", "-p", "MainPID", "--value", svc["unit"]]).strip()
        return v if v and v != "0" else ""
    if svc["kind"] == "proc":
        try:
            o = subprocess.run(["pgrep", "-x", svc["proc"]], capture_output=True, text=True, env=ENV, timeout=5).stdout
            return o.split()[0] if o.split() else ""
        except Exception:
            return ""
    return ""


def ps_info(pid):
    if not pid:
        return {}
    o = sh(["ps", "-o", "etimes=,rss=,pcpu=", "-p", str(pid)]).strip()
    try:
        et, rss, cpu = o.split()
        return {"uptime": fmt_dur(int(et)), "mem": fmt_mb(int(rss) / 1024.0), "cpu": cpu + "%"}
    except Exception:
        return {}


def fmt_dur(s):
    s = int(s)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, _ = divmod(s, 60)
    if d:
        return "%dd %dh %dm" % (d, h, m)
    if h:
        return "%dh %dm" % (h, m)
    return "%dm" % m


def fmt_mb(mb):
    return "%.0f MiB" % mb if mb < 1024 else "%.2f GiB" % (mb / 1024.0)


def tcp_open(port, host="127.0.0.1", t=1.2):
    try:
        socket.create_connection((host, port), t).close()
        return True
    except Exception:
        return False


# ---------- Minecraft Server List Ping(查在线人数,无需认证) ----------
def _wv(n):
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        out += bytes([b | 0x80]) if n else bytes([b])
        if not n:
            return out


def _rv(sock):
    num = shift = 0
    while True:
        d = sock.recv(1)
        if not d:
            raise EOFError
        b = d[0]
        num |= (b & 0x7F) << shift
        if not b & 0x80:
            return num
        shift += 7


def _recvn(sock, n):
    buf = b""
    while len(buf) < n:
        d = sock.recv(n - len(buf))
        if not d:
            raise EOFError
        buf += d
    return buf


def _motd(desc):
    if isinstance(desc, str):
        return desc
    if isinstance(desc, dict):
        t = desc.get("text", "")
        for e in desc.get("extra", []):
            t += _motd(e)
        return t
    return ""


def mc_status(host="127.0.0.1", port=25565, timeout=2):
    try:
        s = socket.create_connection((host, port), timeout)
        s.settimeout(timeout)
        hb = host.encode()
        hs = _wv(47) + _wv(len(hb)) + hb + struct.pack(">H", port) + _wv(1)
        body = b"\x00" + hs
        s.sendall(_wv(len(body)) + body)   # 握手
        s.sendall(_wv(1) + b"\x00")         # 状态请求
        _rv(s)                              # 包长度
        _rv(s)                              # 包 ID
        raw = _recvn(s, _rv(s))             # JSON 字符串
        s.close()
        d = json.loads(raw.decode("utf-8", "replace"))
        pl = d.get("players", {}) or {}
        names = [p.get("name", "") for p in (pl.get("sample") or [])]
        return {"online": pl.get("online", 0), "max": pl.get("max", 0),
                "names": [n for n in names if n],
                "version": (d.get("version", {}) or {}).get("name", ""),
                "motd": _motd(d.get("description", "")).strip()[:80]}
    except Exception:
        return None


# ---------- RCON:读每个玩家实时状态 ----------
def mc_props():
    p = os.path.expanduser("~/crafty/servers/%s/server.properties" % crafty_sid())
    d = {}
    try:
        for line in open(p):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                d[k] = v
    except Exception:
        pass
    return d


def _rcon_pkt(rid, ptype, body):
    data = struct.pack("<ii", rid, ptype) + body.encode() + b"\x00\x00"
    return struct.pack("<i", len(data)) + data


def _rcon_read(s):
    ln = struct.unpack("<i", _recvn(s, 4))[0]
    data = _recvn(s, ln)
    rid, ptype = struct.unpack("<ii", data[:8])
    return rid, ptype, data[8:-2].decode("utf-8", "replace")


def rcon_exec(cmds, port, password, host="127.0.0.1", timeout=3):
    try:
        s = socket.create_connection((host, port), timeout)
        s.settimeout(timeout)
        s.sendall(_rcon_pkt(1, 3, password))
        rid, _, _ = _rcon_read(s)
        if rid == -1:
            s.close()
            return None
        out = []
        for c in cmds:
            s.sendall(_rcon_pkt(2, 2, c))
            _, _, body = _rcon_read(s)
            out.append(body)
        s.close()
        return out
    except Exception:
        return None


_DIM = {"minecraft:overworld": "主世界", "minecraft:the_nether": "下界", "minecraft:the_end": "末地"}
_GAMET = {"0": "生存", "1": "创造", "2": "冒险", "3": "旁观"}


def _after(s):
    m = re.search(r"data:\s*(.*)$", s.strip())
    return m.group(1).strip() if m else ""


def mc_players_detail():
    props = mc_props()
    if props.get("enable-rcon", "") != "true":
        return None
    pw = props.get("rcon.password", "")
    try:
        port = int(props.get("rcon.port", "25575"))
    except Exception:
        port = 25575
    if not pw:
        return None
    lst = rcon_exec(["list"], port, pw)   # RCON 连不上(未重启/服务挂)→ None
    if lst is None:
        return None
    m = re.search(r"online:?\s*(.*)$", lst[0].strip())
    names = [x.strip() for x in m.group(1).split(",")] if (m and m.group(1).strip()) else []
    names = [n for n in names if n]
    if not names:
        return []
    fields = ["Health", "Pos", "Dimension", "foodLevel", "XpLevel", "playerGameType"]
    cmds = ["data get entity %s %s" % (n, f) for n in names for f in fields]
    res = rcon_exec(cmds, port, pw)
    if res is None:
        return None
    players = []
    for i, n in enumerate(names):
        c = res[i * 6:(i + 1) * 6]
        if len(c) < 6:
            continue
        try:
            hp = round(float(_after(c[0]).rstrip("f") or 0))
        except Exception:
            hp = "-"
        nums = re.findall(r"-?\d+\.?\d*", _after(c[1]))[:3]
        coord = "%d, %d, %d" % tuple(int(float(x)) for x in nums) if len(nums) == 3 else "-"
        dim = _after(c[2]).strip('"')
        food = _after(c[3]) or "-"
        xp = _after(c[4]) or "-"
        mode = _GAMET.get(_after(c[5]), _after(c[5]) or "-")
        players.append({"name": n, "hp": hp, "pos": coord,
                        "dim": _DIM.get(dim, dim or "-"), "food": food, "xp": xp, "mode": mode})
    return players


def read_cpu():
    with open("/proc/stat") as f:
        v = list(map(int, f.readline().split()[1:]))
    return sum(v), v[3] + v[4]


def read_net():
    rx = tx = 0
    with open("/proc/net/dev") as f:
        for line in f.readlines()[2:]:
            name, data = line.split(":")
            if name.strip() in ("lo",) or name.strip().startswith(("docker", "br-", "veth", "Meta")):
                continue
            d = data.split()
            rx += int(d[0]); tx += int(d[8])
    return rx, tx


def sysstat():
    now = time.time()
    total, idle = read_cpu()
    cpu = 0.0
    if _prev["cpu"]:
        dt, di = total - _prev["cpu"][0], idle - _prev["cpu"][1]
        if dt > 0:
            cpu = round((1 - di / dt) * 100, 1)
    _prev["cpu"] = (total, idle)
    mem = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, _, v = line.partition(":")
            mem[k] = int(v.strip().split()[0])
    mt = mem["MemTotal"] / 1048576.0
    ma = mem.get("MemAvailable", 0) / 1048576.0
    swt = mem.get("SwapTotal", 0) / 1048576.0
    swf = mem.get("SwapFree", 0) / 1048576.0
    du = shutil.disk_usage("/")
    rx, tx = read_net()
    rxr = txr = 0
    if _prev["net"] and _prev["t"]:
        dtt = now - _prev["t"]
        if dtt > 0:
            rxr = max(0, (rx - _prev["net"][0]) / dtt)
            txr = max(0, (tx - _prev["net"][1]) / dtt)
    _prev["net"], _prev["t"] = (rx, tx), now
    with open("/proc/loadavg") as f:
        la = f.read().split()[:3]
    with open("/proc/uptime") as f:
        up = float(f.read().split()[0])
    return {"cpu": cpu, "ncpu": os.cpu_count(),
            "mem_used": round(mt - ma, 1), "mem_total": round(mt, 1),
            "mem_pct": round((mt - ma) / mt * 100, 1) if mt else 0,
            "swap_used": round(swt - swf, 1), "swap_total": round(swt, 1),
            "disk_used": du.used, "disk_total": du.total,
            "disk_pct": round(du.used / du.total * 100, 1),
            "net_rx": int(rxr), "net_tx": int(txr), "load": la, "uptime": fmt_dur(up)}


def eval_item(sid, ps, stats):
    svc = SERVICES[sid]
    level, detail, cpu, mem = "down", "", "", ""
    k = svc["kind"]
    if k == "systemd":
        ok = systemd_active(svc["unit"])
        level, detail = ("up", "active") if ok else ("down", "stopped")
    elif k == "proc":
        ok = bool(pid_of(svc))
        level, detail = ("up", "running") if ok else ("down", "not found")
    elif k == "port":
        st = mc_status("127.0.0.1", svc["port"])
        if st:
            level, detail = "up", "在线 %d / %d" % (st["online"], st["max"])
        elif tcp_open(svc["port"]):
            level, detail = "up", "监听中(启动中)"
        else:
            level, detail = "down", "无连接"
    elif k == "container":
        c = ps.get(svc["container"])
        if not c:
            level, detail = "down", "不存在"
        elif c["state"] != "running":
            level, detail = "down", c["state"]
        else:
            if c["health"] == "unhealthy":
                level, detail = "warn", "unhealthy"
            elif c["health"] == "health: starting":
                level, detail = "warn", "starting"
            else:
                level, detail = "up", "running"
            if svc.get("port") and not tcp_open(svc["port"]) and level == "up":
                level, detail = "warn", "端口未通"
            st = stats.get(svc["container"])
            if st:
                cpu, mem = st["cpu"], st["mem"]
    return {"id": sid, "name": svc["name"], "group": svc["group"], "sub": svc.get("sub", ""),
            "level": level, "detail": detail, "cpu": cpu, "mem": mem}


_probe = {"direct": True, "proxy": True, "frp": True}
_seen = {}
_alert_since = {}


def do_probe():
    def http(url):
        try:
            urllib.request.urlopen(url, timeout=6)
            return True
        except urllib.error.HTTPError:
            return True
        except Exception:
            return False
    _probe["direct"] = http("https://www.cloudflare.com")          # 直连(ISP)
    _probe["proxy"] = http("https://www.gstatic.com/generate_204")  # 代理出口(mihomo 同款健康检查)
    _probe["frp"] = tcp_open(18650, "frp-top.com", 3)    # MC 隧道


def prober_loop():
    while True:
        try:
            do_probe()
        except Exception:
            pass
        time.sleep(25)


def sustained(key, active, secs):
    now = time.time()
    if active:
        _seen.setdefault(key, now)
        return now - _seen[key] >= secs
    _seen.pop(key, None)
    return False


def mk(level, key, msg):
    now = time.time()
    _alert_since.setdefault(key, now)
    dur = int(now - _alert_since[key])
    return {"level": level, "key": key, "msg": msg, "since": (fmt_dur(dur) if dur >= 60 else "刚刚")}


def build_alerts(items, sysd):
    a, keys = [], set()

    def add(level, key, msg):
        keys.add(key)
        a.append(mk(level, key, msg))
    d = sysd.get("disk_pct", 0)
    if d >= 90:
        add("critical", "disk", "磁盘空间严重不足 %.0f%%,请尽快清理" % d)
    elif d >= 80:
        add("warning", "disk", "磁盘使用偏高 %.0f%%" % d)
    m = sysd.get("mem_pct", 0)
    if m >= 92:
        add("critical", "mem", "内存接近耗尽 %.0f%%,有 OOM 风险" % m)
    elif m >= 85:
        add("warning", "mem", "内存使用偏高 %.0f%%" % m)
    st, sw = sysd.get("swap_total", 0), sysd.get("swap_used", 0)
    if st and sw / st >= 0.85:
        add("warning", "swap", "Swap 占用 %.0f%%,内存压力较大" % (sw / st * 100))
    if sustained("cpu", sysd.get("cpu", 0) >= 90, 60):
        add("warning", "cpu", "CPU 持续满载(≥90%% 超过 1 分钟)")
    try:
        l1 = float((sysd.get("load") or ["0"])[0])
        if l1 > NCPU * 2:
            add("warning", "load", "系统负载过高 %.2f(共 %d 核)" % (l1, NCPU))
    except Exception:
        pass
    if not _probe["frp"]:
        add("critical", "frp", "MC 隧道 frp-top.com:18650 不可达,朋友可能无法连入服务器")
    if not _probe["direct"]:
        add("critical", "net", "外网直连中断,疑似网络 / ISP 异常")
    if not _probe["proxy"]:
        add("warning", "proxy", "代理出口不通,依赖外网 API 的服务(LiteLLM / SillyTavern 等)可能失效")
    perf = mc_perf_cached()
    if perf and perf.get("tps_1m") is not None:
        t = perf["tps_1m"]
        if t < 14:
            add("critical", "tps", "MC 服务器严重卡顿,TPS %.1f(正常 20)" % t)
        elif t < 18:
            add("warning", "tps", "MC 服务器 TPS 偏低 %.1f(正常 20)" % t)
    for it in items:
        if it["level"] == "down":
            add("critical", "svc_" + it["id"], "%s 已停止运行" % it["name"])
        elif it["level"] == "warn":
            add("warning", "svc_" + it["id"], "%s 异常:%s" % (it["name"], it["detail"]))
    for k in list(_alert_since):
        if k not in keys:
            del _alert_since[k]
    a.sort(key=lambda x: {"critical": 0, "warning": 1}.get(x["level"], 2))
    return a


# ---------- 预警自动备份 ----------
CRAFTY_CRED = os.path.expanduser("~/crafty/config/default-creds.txt")
BACKUP_TRIGGER = ("mem", "swap", "cpu", "load", "svc_mc")  # 这些预警触发备份
BACKUP_COOLDOWN = 3 * 3600
_backup = {"last": 0, "token": "", "token_t": 0}
_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE


def crafty_sid():
    d = sorted(glob.glob(os.path.expanduser("~/crafty/servers/*/")), key=os.path.getmtime, reverse=True)
    return os.path.basename(d[0].rstrip("/")) if d else ""


def crafty_token():
    now = time.time()
    if _backup["token"] and now - _backup["token_t"] < 1800:
        return _backup["token"]
    try:
        pw = json.load(open(CRAFTY_CRED))["password"]
        req = urllib.request.Request("https://127.0.0.1:8443/api/v2/auth/login",
                                     data=json.dumps({"username": "admin", "password": pw}).encode(),
                                     headers={"Content-Type": "application/json"})
        tok = json.load(urllib.request.urlopen(req, timeout=8, context=_SSL))["data"]["token"]
        _backup.update(token=tok, token_t=now)
        return tok
    except Exception:
        return ""


def crafty_backup():
    sid, tok = crafty_sid(), crafty_token()
    if not sid or not tok:
        return
    try:
        req = urllib.request.Request("https://127.0.0.1:8443/api/v2/servers/%s/action/backup_server" % sid,
                                     data=b"", method="POST", headers={"Authorization": "Bearer " + tok})
        urllib.request.urlopen(req, timeout=20, context=_SSL)
    except Exception:
        pass


def do_alert_backup(alerts):
    now = time.time()
    keys = {a["key"] for a in alerts}
    if any(k in keys for k in BACKUP_TRIGGER) and now - _backup["last"] >= BACKUP_COOLDOWN:
        _backup["last"] = now
        threading.Thread(target=crafty_backup, daemon=True).start()


_pcache = {"t": 0, "data": None}
_plock = threading.Lock()


def players_cached():
    # 1 秒缓存,供 /api/players(高频)与 collect 共用,避免重复打 RCON
    with _plock:
        if _pcache["t"] and time.time() - _pcache["t"] < 1.0:
            return _pcache["data"]
        _pcache["data"] = mc_players_detail()
        _pcache["t"] = time.time()
        return _pcache["data"]


_perfcache = {"t": 0, "data": None}
_perflock = threading.Lock()


def mc_perf():
    props = mc_props()
    if props.get("enable-rcon", "") != "true":
        return None
    pw = props.get("rcon.password", "")
    try:
        port = int(props.get("rcon.port", "25575"))
    except Exception:
        port = 25575
    if not pw:
        return None
    res = rcon_exec(["tps", "mspt"], port, pw)
    if not res or len(res) < 2:
        return None

    def vals(s):
        s = re.sub("§.", "", s)
        after = s.split(":", 1)[1] if ":" in s else s
        return [float(x) for x in re.findall(r"\d+\.?\d*", after)]
    tps, mspt = vals(res[0]), vals(res[1])
    if not tps:
        return None
    return {"tps_1m": round(tps[0], 1),
            "mspt_avg": round(mspt[0], 1) if mspt else None,
            "mspt_max": round(mspt[8], 1) if len(mspt) >= 9 else (round(max(mspt), 1) if mspt else None)}


def mc_perf_cached():
    with _perflock:
        if _perfcache["t"] and time.time() - _perfcache["t"] < 3.0:
            return _perfcache["data"]
        _perfcache["data"] = mc_perf()
        _perfcache["t"] = time.time()
        return _perfcache["data"]


def collect():
    ps, stats = docker_ps(), docker_stats()
    items = {sid: eval_item(sid, ps, stats) for sid in ORDER}
    up = sum(1 for i in items.values() if i["level"] == "up")
    warn = sum(1 for i in items.values() if i["level"] == "warn")
    down = sum(1 for i in items.values() if i["level"] == "down")
    groups = [{"title": g, "items": [items[s] for s in ORDER if SERVICES[s]["group"] == g]} for g in GROUP_ORDER]
    try:
        sysd = sysstat()
    except Exception:
        sysd = {}
    alerts = build_alerts(list(items.values()), sysd)
    try:
        do_alert_backup(alerts)
    except Exception:
        pass
    if _backup["last"] and time.time() - _backup["last"] < 900:
        dur = int(time.time() - _backup["last"])
        alerts.append({"level": "info", "key": "autobackup",
                       "msg": "检测到系统预警,已自动触发一次世界备份",
                       "since": fmt_dur(dur) if dur >= 60 else "刚刚"})
    try:
        mcp = players_cached()
    except Exception:
        mcp = None
    with _lock:
        _state["groups"] = groups
        _state["sys"] = sysd
        _state["alerts"] = alerts
        _state["mc_players"] = mcp
        _state["mc_perf"] = mc_perf_cached()
        _state["updated"] = int(time.time())
        _state["summary"] = {"up": up, "warn": warn, "down": down, "total": up + warn + down}


def refresher():
    while True:
        try:
            collect()
        except Exception:
            pass
        time.sleep(REFRESH)


def detail(sid):
    if sid not in SERVICES:
        return {"error": "unknown"}
    svc = SERVICES[sid]
    ps, stats = docker_ps(), docker_stats()
    base = eval_item(sid, ps, stats)
    tiles = []
    k = svc["kind"]
    if k == "container":
        name = svc["container"]
        ins = sh(["docker", "inspect", name, "--format",
                  "{{.Config.Image}}\t{{.State.StartedAt}}\t{{.RestartCount}}\t{{.State.Health.Status}}"]).strip()
        img, started, restarts, health = (ins.split("\t") + ["", "", "", ""])[:4]
        uptime = ""
        try:
            st = datetime.fromisoformat(started.replace("Z", "+00:00"))
            uptime = fmt_dur((datetime.now(timezone.utc) - st).total_seconds())
        except Exception:
            pass
        ports = sh(["docker", "port", name]).replace("\n", "  ").strip() or "内网"
        tiles = [("状态", base["detail"]), ("健康", health if health and health != "<no value>" else "无检查"),
                 ("运行时长", uptime or "-"), ("CPU", base["cpu"] or "-"), ("内存", base["mem"] or "-"),
                 ("重启次数", restarts or "0"), ("镜像", img.split("@")[0]), ("端口", ports)]
    elif k in ("systemd", "proc"):
        pid = pid_of(svc)
        info = ps_info(pid)
        tiles = [("状态", base["detail"]), ("主 PID", pid or "-"), ("运行时长", info.get("uptime", "-")),
                 ("CPU", info.get("cpu", "-")), ("内存", info.get("mem", "-")),
                 ("类型", "systemd 用户服务" if k == "systemd" else "系统进程")]
    elif k == "port":
        st = mc_status("127.0.0.1", svc["port"])
        tiles = [("状态", base["detail"]), ("端口", str(svc["port"]))]
        perf = mc_perf_cached()
        if perf:
            tiles.append(("TPS (1m)", "%.1f" % perf["tps_1m"]))
            if perf.get("mspt_avg") is not None:
                tiles.append(("MSPT 平均", "%.1f ms" % perf["mspt_avg"]))
            if perf.get("mspt_max") is not None:
                tiles.append(("MSPT 峰值", "%.1f ms" % perf["mspt_max"]))
        if st:
            tiles += [("在线人数", "%d / %d" % (st["online"], st["max"])),
                      ("版本", st.get("version") or "-"),
                      ("在线玩家", ", ".join(st.get("names") or []) or "(无)"),
                      ("MOTD", st.get("motd") or "-")]
        else:
            tiles += [("类型", "Minecraft Java"), ("核心", "Paper 1.21.10")]
    out = {"id": sid, "name": svc["name"], "group": svc["group"], "sub": svc.get("sub", ""),
           "level": base["level"], "tiles": [{"k": a, "v": b} for a, b in tiles],
           "has_log": svc["log"][0] != "none"}
    if sid == "mc":
        out["players"] = mc_players_detail()
    return out


def get_logs(sid, tail=400):
    if sid not in SERVICES:
        return "unknown service"
    kind, tgt = SERVICES[sid]["log"]
    tail = max(20, min(int(tail), 1000))
    if kind == "docker":
        r = subprocess.run(["docker", "logs", "--tail", str(tail), tgt],
                           capture_output=True, text=True, env=ENV, timeout=15)
        return (r.stdout + r.stderr) or "(无日志输出)"
    if kind == "journal_user":
        return sh(["journalctl", "--user", "-u", tgt, "-n", str(tail), "--no-pager", "-o", "short-iso"], 15) or "(无日志)"
    if kind == "journal_sys":
        o = sh(["journalctl", "-u", tgt, "-n", str(tail), "--no-pager", "-o", "short-iso"], 15)
        return o or "(无法读取系统日志,需要权限)"
    if kind == "file":
        if not tgt or not os.path.exists(tgt):
            return "(日志文件不存在,服务器可能未启动)"
        try:
            with open(tgt, "r", errors="replace") as f:
                return "".join(f.readlines()[-tail:]) or "(空)"
        except Exception as e:
            return "读取失败: %s" % e
    return "(该服务无日志源)"


NCPU = os.cpu_count() or 1
_hist = {"t": 0, "range": 0, "data": None}


def newest_archive():
    # 返回最近两个归档(逗号合并),以便跨午夜/跨轮转也能取满时间窗
    g = glob.glob("/var/log/pcp/pmlogger/*/*.index")
    g.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return ",".join(p[:-6] for p in g[:2]) if g else ""


def _num(s):
    try:
        return float(s.strip().strip('"'))
    except Exception:
        return None


def history(rng="60"):
    try:
        rng = max(10, min(int(rng), 360))
    except Exception:
        rng = 60
    now = time.time()
    if _hist["data"] and _hist["range"] == rng and now - _hist["t"] < 25:
        return _hist["data"]
    arch = newest_archive()
    interval = max(30, rng * 60 // 60)
    out = {"t": [], "cpu": [], "mem": [], "load": []}
    if arch:
        csv = sh(["pmrep", "-a", arch, "-o", "csv", "-S", "-%dm" % rng, "-T", "now",
                  "-t", "%ds" % interval, "kernel.all.cpu.idle", "mem.util.available",
                  "mem.physmem", "kernel.all.load"], 20)
        for line in csv.splitlines()[1:]:
            p = line.split(",")
            if len(p) < 7:
                continue
            idle, avail, phys, l1 = _num(p[1]), _num(p[2]), _num(p[3]), _num(p[4])
            cpu = round(max(0, min(100, 100 * (1 - idle / (NCPU * 1000.0)))), 1) if idle is not None else None
            mem = round(100 * (1 - avail / phys), 1) if (avail is not None and phys) else None
            out["t"].append(p[0][11:16])
            out["cpu"].append(cpu)
            out["mem"].append(mem)
            out["load"].append(l1)
    _hist.update(t=now, range=rng, data=out)
    return out


HTML = r"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>NEC 监控</title><style>
*{margin:0;padding:0;box-sizing:border-box;border-radius:0!important}
:root{--bg:#0b0e13;--side:#11151c;--panel:#161b22;--panel2:#1b212b;--card:#161b22;
--bd:#242b36;--bd2:#30bcb0;--tx:#e6edf3;--tx2:#8b949e;--tx3:#677183;
--grn:#3fb950;--yel:#d29922;--red:#f85149;--teal:#2dd4bf;--ac:#30bcb0}
html,body{height:100%}
body{background:var(--bg);color:var(--tx);font-family:-apple-system,"PingFang SC","Microsoft YaHei",system-ui,sans-serif;overflow:hidden}
.app{display:flex;height:100vh}
/* sidebar */
.side{width:226px;flex:0 0 226px;background:var(--side);border-right:1px solid var(--bd);display:flex;flex-direction:column;overflow:hidden}
.logo{padding:16px 18px;border-bottom:1px solid var(--bd);display:flex;align-items:center;gap:11px}
.logo .mk{width:30px;height:30px;background:linear-gradient(135deg,#30bcb0,#3fb950);display:flex;align-items:center;justify-content:center;font-weight:800;color:#06120f}
.logo b{font-size:15px;letter-spacing:.5px}.logo span{display:block;font-size:11px;color:var(--tx3);font-weight:400}
.nav{flex:1;overflow:auto;padding:8px 0}
.nav .it{display:flex;align-items:center;gap:10px;padding:9px 18px;font-size:14px;color:var(--tx2);cursor:pointer;border-left:3px solid transparent}
.nav .it:hover{background:#1a202a;color:var(--tx)}
.nav .it.on{background:#1a202a;color:var(--tx);border-left-color:var(--ac)}
.nav .it .ic{width:15px;text-align:center;opacity:.8}
.nav .glabel{padding:14px 18px 6px;font-size:11px;color:var(--tx3);text-transform:uppercase;letter-spacing:1.3px}
.nav .sv{display:flex;align-items:center;gap:9px;padding:7px 18px;font-size:13.5px;color:var(--tx2);cursor:pointer;border-left:3px solid transparent}
.nav .sv:hover{background:#1a202a;color:var(--tx)}
.nav .sv.on{background:#1f2630;color:#fff;border-left-color:var(--ac)}
.dot{width:8px;height:8px;flex:0 0 auto}
.dot.up{background:var(--grn)}.dot.warn{background:var(--yel);animation:bl 1.3s infinite}.dot.down{background:var(--red);animation:bl 1.3s infinite}
@keyframes bl{50%{opacity:.3}}
.sfoot{border-top:1px solid var(--bd);padding:11px 18px;font-size:12px;color:var(--tx3);font-variant-numeric:tabular-nums}
/* content */
.content{display:flex;flex-direction:column;height:100vh;min-width:0}
.top .ti{display:flex;align-items:center;gap:10px}
.top .mk{width:26px;height:26px;background:linear-gradient(135deg,#30bcb0,#3fb950);display:flex;align-items:center;justify-content:center;font-weight:800;color:#06120f;font-size:14px}
.sysmeta{color:var(--tx3);font-size:12.5px;font-variant-numeric:tabular-nums}
.back{display:inline-flex;align-items:center;gap:6px;color:var(--tx2);font-size:13.5px;cursor:pointer;margin-bottom:14px;border:1px solid var(--bd);padding:5px 11px;width:fit-content}
.back:hover{color:var(--tx);background:var(--panel)}
.top{height:54px;flex:0 0 54px;border-bottom:1px solid var(--bd);background:var(--panel);display:flex;align-items:center;justify-content:space-between;padding:0 22px}
.top .ti{font-size:16px;font-weight:600}
.top .r{display:flex;align-items:center;gap:16px;font-size:13px;color:var(--tx2)}
.pills{display:flex;gap:8px}
.pill{padding:4px 11px;font-size:13px;font-weight:600;display:flex;align-items:center;gap:6px;border:1px solid var(--bd)}
.pill .d{width:8px;height:8px}
.pill.up{color:var(--grn)}.pill.up .d{background:var(--grn)}
.pill.warn{color:var(--yel)}.pill.warn .d{background:var(--yel)}
.pill.down{color:var(--red)}.pill.down .d{background:var(--red)}
#clock{font-weight:600;color:#adbac7;font-variant-numeric:tabular-nums}
main{flex:1;min-height:0;overflow:hidden;padding:16px 22px;display:flex;flex-direction:column}
#view>.sysrow,#view>.sec,#view>.secrow{flex:0 0 auto}
#pwall{flex:1 1 0;min-height:130px;display:flex;flex-direction:column;overflow:hidden;margin-top:12px}
#pwall .psec-home{flex:1;display:flex;flex-direction:column;min-height:0;margin-top:0}
#pwall .pcards{flex:1;overflow:auto;align-content:start;min-height:0;padding-right:4px}
/* system overview */
.sysrow{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:8px}
.stat{background:var(--panel);border:1px solid var(--bd);padding:13px 15px}
.stat .l{font-size:11.5px;color:var(--tx3);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;display:flex;justify-content:space-between}
.stat .big{font-size:22px;font-weight:700;font-variant-numeric:tabular-nums;margin-bottom:3px}
.stat .sm{font-size:12px;color:var(--tx2);font-variant-numeric:tabular-nums}
.bar{height:6px;background:#0c1016;border:1px solid var(--bd);margin-top:9px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--teal);transition:width .6s}
.bar i.w{background:var(--yel)}.bar i.c{background:var(--red)}
/* charts */
.charts{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.chart{background:var(--panel);border:1px solid var(--bd);padding:13px 15px}
.ch-h{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:9px;font-size:13px;color:var(--tx2)}
.ch-h b{font-size:19px;font-weight:700;font-variant-numeric:tabular-nums}
.ch-svg{width:100%;height:76px;display:block}
.ch-f{display:flex;justify-content:space-between;font-size:11px;color:var(--tx3);margin-top:6px;font-variant-numeric:tabular-nums}
/* sections + cards */
.secrow{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
.sec{}.sec.full{grid-column:1/-1}
.sec h2{font-size:12px;font-weight:700;color:var(--tx2);margin:6px 0 11px;text-transform:uppercase;letter-spacing:1.4px;display:flex;align-items:center;gap:9px}
.sec h2 .bar2{width:4px;height:13px;background:var(--ac)}
.grid{display:grid;gap:11px;grid-template-columns:repeat(auto-fill,minmax(225px,1fr))}
.card{background:var(--card);border:1px solid var(--bd);border-left:3px solid var(--bd);padding:13px 15px;cursor:pointer;transition:.12s;position:relative}
.card:hover{background:var(--panel2)}
.card.up{border-left-color:var(--grn)}.card.warn{border-left-color:var(--yel)}.card.down{border-left-color:var(--red)}
.card .top2{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}
.card .nm{font-size:15.5px;font-weight:600}
.card .st{width:10px;height:10px}
.card.up .st{background:var(--grn)}.card.warn .st{background:var(--yel);animation:bl 1.3s infinite}.card.down .st{background:var(--red);animation:bl 1.3s infinite}
.card .sub{font-size:12px;color:var(--tx3);margin-bottom:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.met{display:flex;gap:7px}
.met .chip{flex:1;background:#0e131a;border:1px solid var(--bd);padding:5px 8px;font-size:12px;color:var(--tx2);font-variant-numeric:tabular-nums}
.met .chip b{display:block;color:#adbac7;font-size:13px;font-weight:600}
.card .detail{font-size:12.5px;font-weight:600;padding:4px 0}
.card.up .detail{color:var(--grn)}.card.warn .detail{color:var(--yel)}.card.down .detail{color:var(--red)}
/* detail */
.dhead{display:flex;align-items:center;gap:13px;margin-bottom:16px}
.dhead .st{width:13px;height:13px}
.dhead.up .st{background:var(--grn)}.dhead.warn .st{background:var(--yel)}.dhead.down .st{background:var(--red)}
.dhead h1{font-size:23px;font-weight:700}
.dhead .grp{font-size:12px;color:var(--tx3);background:var(--panel);border:1px solid var(--bd);padding:3px 10px}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(175px,1fr));gap:11px;margin-bottom:16px}
.tile{background:var(--panel);border:1px solid var(--bd);padding:11px 14px}
.tile .k{font-size:11px;color:var(--tx3);text-transform:uppercase;letter-spacing:.8px;margin-bottom:6px}
.tile .v{font-size:16px;font-weight:600;word-break:break-all;font-variant-numeric:tabular-nums}
.logwrap{height:calc(100vh - 320px);min-height:240px;display:flex;flex-direction:column;background:#06090d;border:1px solid var(--bd)}
.logbar{flex:0 0 auto;display:flex;align-items:center;justify-content:space-between;padding:9px 15px;background:var(--panel);border-bottom:1px solid var(--bd);font-size:13px;color:var(--tx2)}
.logbar .left{display:flex;align-items:center;gap:8px;font-weight:600}
.logbar .live{width:7px;height:7px;background:var(--grn);animation:bl 1.2s infinite}
.logbar .right{display:flex;align-items:center;gap:14px}
.logbar a{color:var(--tx3);cursor:pointer}.logbar a:hover{color:var(--tx)}
.log{flex:1;overflow:auto;padding:10px 14px;font-family:"SF Mono","JetBrains Mono",Consolas,monospace;font-size:12.5px;line-height:1.6}
.ln{white-space:pre-wrap;word-break:break-word;padding:0 0 0 0;color:#bcc6d2}
.ln .ts{color:#4d586a}
.ln.err{color:#ff7b72}.ln.warn{color:#e3b341}.ln.ok{color:#56d364}.ln.info{color:#a9b4c2}
.log::-webkit-scrollbar,main::-webkit-scrollbar,.nav::-webkit-scrollbar{width:9px}
.log::-webkit-scrollbar-thumb,main::-webkit-scrollbar-thumb,.nav::-webkit-scrollbar-thumb{background:#222a35}
.empty{color:var(--tx3);padding:20px}
/* player table */
.psec{margin-top:18px}
.psec h3{font-size:14px;color:var(--tx2);margin-bottom:11px;font-weight:600;display:flex;align-items:center;gap:8px}
.ptab{width:100%;border-collapse:collapse;font-size:13.5px;border:1px solid var(--bd)}
.ptab th{text-align:left;color:var(--tx3);font-weight:600;padding:9px 13px;border-bottom:1px solid var(--bd);background:var(--panel);font-size:12px;letter-spacing:.4px}
.ptab td{padding:9px 13px;border-bottom:1px solid var(--bd);color:var(--tx);font-variant-numeric:tabular-nums}
.ptab tbody tr:hover td{background:var(--panel)}
.ptab .mono{font-family:"SF Mono",Consolas,monospace;color:var(--tx2)}
.phint{color:var(--tx3);font-size:13px;padding:14px;border:1px dashed var(--bd);background:var(--panel);margin-top:16px}
/* 首页玩家墙 */
.psec-home{margin-top:18px}
.pcards{display:grid;gap:12px}
.pcard{display:flex;gap:11px;align-items:center;background:var(--card);border:1px solid var(--bd);border-left:3px solid var(--grn);padding:10px 13px}
.pcard.danger{border-left-color:var(--yel)}
.pcard.dead{border-left-color:var(--red);animation:bl 1.2s infinite}
.pav{width:46px;height:46px;flex:0 0 auto;image-rendering:pixelated;background:#0e131a;border:1px solid var(--bd)}
.pinfo{flex:1;min-width:0}
.pname{font-size:15px;font-weight:600;margin-bottom:6px;display:flex;align-items:center;gap:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pmode{font-size:11px;color:var(--tx3);border:1px solid var(--bd);padding:1px 7px;font-weight:400;flex:0 0 auto}
.pbar{position:relative;height:14px;background:#0c1016;border:1px solid var(--bd);margin-bottom:4px;overflow:hidden}
.pbar i{display:block;height:100%;transition:width .5s}
.pbar.hp i{background:#d23b3b}.pbar.food i{background:#c8862f}
.pbar span{position:absolute;left:8px;top:0;line-height:16px;font-size:11px;color:#fff;text-shadow:0 1px 2px #000;font-variant-numeric:tabular-nums}
.pmeta{font-size:11.5px;color:var(--tx3);margin-top:7px;font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
/* alerts */
.alertbar{flex:0 0 auto;display:none}
.alert{display:flex;align-items:center;gap:10px;padding:8px 22px;font-size:13.5px;border-bottom:1px solid var(--bd);border-left:4px solid}
.alert.critical{background:rgba(248,81,73,.13);color:#ff9a93;border-left-color:var(--red)}
.alert.warning{background:rgba(210,153,34,.1);color:#e3b341;border-left-color:var(--yel)}
.alert.info{background:rgba(48,188,176,.1);color:#5fd9cb;border-left-color:var(--ac)}
.alert .ai{font-size:14px;flex:0 0 auto}
.alert .at{margin-left:auto;color:var(--tx3);font-size:12px;flex:0 0 auto}
</style></head><body>
<div class="content">
  <div class="top">
    <div class="ti"><span class="mk">⬡</span><span id="title">总览</span></div>
    <div class="r"><div class="pills" id="pills"></div><div class="sysmeta" id="sysmeta"></div><div id="clock"></div></div>
  </div>
  <div class="alertbar" id="alertbar"></div>
  <main id="view"></main>
</div>
<script>
let DATA=null,timer=null,HIST=null;
function tick(){document.getElementById('clock').textContent=new Date().toLocaleTimeString('zh-CN',{hour12:false})}
setInterval(tick,1000);tick();
function esc(s){return(s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function fb(n){if(!n)return'0 B/s';const u=['B','KB','MB','GB'];let i=0;while(n>=1024&&i<3){n/=1024;i++}return n.toFixed(i?1:0)+' '+u[i]+'/s'}
function fg(b){const u=['B','KB','MB','GB','TB'];let i=0;while(b>=1024&&i<4){b/=1024;i++}return b.toFixed(1)+' '+u[i]}
function lvlc(p){return p>=90?'c':p>=70?'w':''}

function curRoute(){return location.hash.startsWith('#/s/')?location.hash.slice(4):''}
async function poll(){
  try{DATA=await(await fetch('/api/status',{cache:'no-store'})).json();}catch(e){return}
  renderChrome();const id=curRoute();
  if(!id)renderOverview();
}
function renderChrome(){
  const s=DATA.summary;
  document.getElementById('pills').innerHTML=
    `<span class="pill up"><span class="d"></span>${s.up}</span>`+
    `<span class="pill warn"><span class="d"></span>${s.warn}</span>`+
    `<span class="pill down"><span class="d"></span>${s.down}</span>`;
  const sy=DATA.sys||{};
  document.getElementById('sysmeta').textContent=`运行 ${sy.uptime||'-'} · 负载 ${(sy.load||[]).join(' ')}`;
  const al=DATA.alerts||[],ab=document.getElementById('alertbar');
  if(ab){
    if(al.length){ab.style.display='block';ab.innerHTML=al.map(a=>
      `<div class="alert ${a.level}"><span class="ai">${a.level=='critical'?'⛔':a.level=='info'?'⚙':'⚠'}</span><span>${a.msg}</span><span class="at">${a.since}</span></div>`).join('')}
    else{ab.style.display='none';ab.innerHTML=''}
  }
  document.title=(al.some(x=>x.level=='critical')?'⛔ ':(al.length?'⚠ ':''))+'NEC 监控';
}
function renderOverview(){
  document.getElementById('title').textContent='总览';
  const sy=DATA.sys||{};
  const sys=`<div class="sysrow">
    ${statBar('CPU',sy.cpu+' %',(sy.ncpu||'')+' 核',sy.cpu)}
    ${statBar('内存',sy.mem_pct+' %',fg((sy.mem_used||0)*1073741824)+' / '+fg((sy.mem_total||0)*1073741824),sy.mem_pct)}
    ${statBar('磁盘 /',sy.disk_pct+' %',fg(sy.disk_used||0)+' / '+fg(sy.disk_total||0),sy.disk_pct)}
    ${statBar('Swap',sy.swap_total?Math.round(sy.swap_used/sy.swap_total*100)+' %':'0 %',fg((sy.swap_used||0)*1073741824)+' / '+fg((sy.swap_total||0)*1073741824),sy.swap_total?sy.swap_used/sy.swap_total*100:0)}
    ${statPlain('网络','↓ '+fb(sy.net_rx),'↑ '+fb(sy.net_tx))}
    ${statPlain('系统负载',(sy.load||['-'])[0],'1 / 5 / 15 min')}
  </div>`;
  let secs='<div class="secrow">';
  DATA.groups.forEach((g,i)=>{
    secs+=`<section class="sec ${i===2?'full':''}"><h2><span class="bar2"></span>${g.title}</h2><div class="grid">${g.items.map(cardHTML).join('')}</div></section>`;
  });
  secs+='</div>';
  let charts='';
  if(HIST&&HIST.t&&HIST.t.length){
    charts=`<section class="sec full" style="margin-top:18px"><h2><span class="bar2"></span>性能趋势 · 近 60 分钟(PCP）</h2>
      <div class="charts">${chart('CPU 使用率',HIST.cpu,'%','#30bcb0',100)}${chart('内存使用率',HIST.mem,'%','#8957e5',100)}${chart('系统负载 1m',HIST.load,'','#d29922',null)}</div></section>`;
  }
  document.getElementById('view').innerHTML=sys+charts+secs+'<div id="pwall"></div>';
  renderPwall(DATA.mc_players,DATA.mc_perf);
}
function pcols(n){return n<=1?1:n<=2?2:n<=3?3:n<=8?4:n<=15?5:6}
function tpsColor(t){return t>=19?'#3fb950':t>=15?'#d29922':'#f85149'}
function perfHtml(pf){
  if(!pf||pf.tps_1m==null)return'';
  return ` · <span style="color:${tpsColor(pf.tps_1m)}">TPS ${pf.tps_1m}</span><span style="color:var(--tx3)"> · MSPT ${pf.mspt_avg==null?'-':pf.mspt_avg+'ms'}</span>`;
}
function renderPwall(ps,pf){
  const el=document.getElementById('pwall');if(!el)return;
  const h=perfHtml(pf);
  if(ps&&ps.length){
    const cols=pcols(ps.length);
    el.innerHTML=`<section class="sec full psec-home"><h2><span class="bar2"></span>在线玩家 · ${ps.length} 人${h}</h2>
      <div class="pcards" style="grid-template-columns:repeat(${cols},1fr)">${ps.map(pcard).join('')}</div></section>`;
  } else if(ps&&ps.length===0){
    el.innerHTML=`<section class="sec full psec-home"><h2><span class="bar2"></span>在线玩家 · 0 人${h}</h2><div class="phint">当前无玩家在线</div></section>`;
  } else { el.innerHTML=''; }
}
async function pollPlayers(){
  if(curRoute())return;
  try{const j=await(await fetch('/api/players',{cache:'no-store'})).json();
    if(DATA){DATA.mc_players=j.players;DATA.mc_perf=j.perf;}
    renderPwall(j.players,j.perf);
  }catch(e){}
}
setInterval(pollPlayers,2000);
function pcard(p){
  const valid=typeof p.hp==='number';
  const hp=valid?p.hp:0;
  const fn=parseInt(p.food),fvalid=!isNaN(fn),food=fvalid?fn:0;
  const cls=!valid?'':hp<=0?'dead':((hp<10)||(fvalid&&fn<10))?'danger':'';
  const nm=encodeURIComponent(p.name);
  return `<div class="pcard ${cls}">
    <img class="pav" src="https://minotar.net/helm/${nm}/56.png" onerror="this.onerror=null;this.src='https://minotar.net/helm/MHF_Steve/56.png'">
    <div class="pinfo">
      <div class="pname">${esc(p.name)}<span class="pmode">${esc(p.mode)}</span></div>
      <div class="pbar hp"><i style="width:${Math.max(0,Math.min(100,hp/20*100))}%"></i><span>HP ${hp} / 20</span></div>
      <div class="pbar food"><i style="width:${Math.max(0,Math.min(100,food/20*100))}%"></i><span>FOOD ${food} / 20</span></div>
      <div class="pmeta">${esc(p.dim)} · Lv.${esc(String(p.xp))} · ${esc(p.pos)}</div>
    </div></div>`;
}
function chart(title,arr,unit,color,fixedMax){
  arr=(arr||[]).slice();let last=null;let f=arr.map(v=>{if(v==null)return last;last=v;return v});
  let first=f.find(v=>v!=null);f=f.map(v=>v==null?(first||0):v);
  const n=f.length;if(!n)return'';
  const W=320,H=98,p=6,max=fixedMax||Math.max(...f,0.1)*1.25;
  const X=i=>p+(n<=1?0:(i/(n-1))*(W-2*p)),Y=v=>H-p-(Math.max(0,Math.min(v,max))/max)*(H-2*p);
  const line='M'+f.map((v,i)=>X(i).toFixed(1)+' '+Y(v).toFixed(1)).join(' L');
  const area=line+` L${X(n-1).toFixed(1)} ${H-p} L${X(0).toFixed(1)} ${H-p} Z`;
  const cur=f[n-1],curtxt=(unit=='%'?cur.toFixed(0)+'%':cur.toFixed(2));
  const gid='g'+Math.random().toString(36).slice(2,7);
  let grid='';[.25,.5,.75].forEach(r=>{const y=(H-p-r*(H-2*p)).toFixed(1);grid+=`<line x1="${p}" y1="${y}" x2="${W-p}" y2="${y}" stroke="#1b232e" stroke-width="1"/>`});
  return `<div class="chart"><div class="ch-h"><span>${title}</span><b style="color:${color}">${curtxt}</b></div>
    <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" class="ch-svg">
    <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".32"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
    ${grid}<path d="${area}" fill="url(#${gid})"/><path d="${line}" fill="none" stroke="${color}" stroke-width="1.6"/></svg>
    <div class="ch-f"><span>${(HIST.t[0]||'')}</span><span>${unit=='%'?'峰值轴 '+max.toFixed(0)+'%':'峰值轴 '+max.toFixed(1)}</span><span>${(HIST.t[n-1]||'现在')}</span></div></div>`;
}
function statBar(l,big,sm,pct){pct=Math.max(0,Math.min(100,pct||0));
  return `<div class="stat"><div class="l"><span>${l}</span></div><div class="big">${big}</div><div class="sm">${sm}</div>
  <div class="bar"><i class="${lvlc(pct)}" style="width:${pct}%"></i></div></div>`}
function statPlain(l,big,sm){return `<div class="stat"><div class="l"><span>${l}</span></div><div class="big">${big}</div><div class="sm">${sm}</div></div>`}
function cardHTML(it){
  let body=(it.cpu||it.mem)?`<div class="met"><div class="chip">CPU<b>${it.cpu||'-'}</b></div><div class="chip">内存<b>${it.mem||'-'}</b></div></div>`
    :`<div class="detail">${it.detail||''}</div>`;
  return `<div class="card ${it.level}" onclick="location.hash='#/s/${it.id}'">
    <div class="top2"><span class="nm">${it.name}</span><span class="st"></span></div>
    <div class="sub">${it.sub||''}</div>${body}</div>`;
}

function fmtLog(t){
  return t.split('\n').map(line=>{
    if(!line)return'<div class="ln">&nbsp;</div>';
    let cls='';
    if(/(ERROR|CRITICAL|FATAL|Exception|Traceback|\bfail|\bFail|denied|panic|致命|错误|失败)/.test(line))cls='err';
    else if(/(WARN|warning|Warning|警告|deprecat)/.test(line))cls='warn';
    else if(/(\bstarted\b|成功|joined the game|启动成功| 200 |connected|listening|监听)/i.test(line))cls='ok';
    else if(/\bINFO\b|\binfo\b/.test(line))cls='info';
    let h=esc(line).replace(/^(\s*\[?\d[\d\-:T\. ]{5,}\]?|\s*\w{3} \d{4}-\d\d-\d\d[ T][\d:\+]+)/,'<span class="ts">$1</span>');
    return `<div class="ln ${cls}">${h}</div>`;
  }).join('');
}
async function detailView(id){
  const view=document.getElementById('view');
  async function meta(){
    const d=await(await fetch('/api/detail?id='+id,{cache:'no-store'})).json();
    if(d.error){view.innerHTML='<div class="empty">未知服务</div>';return null}
    document.getElementById('title').textContent=d.name;
    if(!document.getElementById('log')){
      view.innerHTML=`<div class="back" onclick="location.hash=''">‹ 返回总览</div><div class="dhead ${d.level}"><span class="st"></span><h1>${d.name}</h1><span class="grp">${d.group}</span>
        <span style="color:var(--tx3);font-size:13px">${d.sub||''}</span></div>
        <div class="tiles" id="tiles"></div>
        <div id="players"></div>
        ${d.has_log?`<div class="logwrap"><div class="logbar"><div class="left"><span class="live"></span>实时日志</div>
        <div class="right"><label style="display:flex;gap:6px;align-items:center"><input type="checkbox" id="auto" checked>自动滚动</label>
        <a onclick="var l=document.getElementById('log');l.scrollTop=l.scrollHeight">↓ 底部</a></div></div>
        <div class="log" id="log">加载中…</div></div>`:'<div class="empty">该服务无日志源</div>'}`;
    }
    const dh=document.querySelector('.dhead');if(dh)dh.className='dhead '+d.level;
    document.getElementById('tiles').innerHTML=d.tiles.map(t=>`<div class="tile"><div class="k">${t.k}</div><div class="v">${esc(t.v)||'-'}</div></div>`).join('');
    const pe=document.getElementById('players');
    if(pe&&'players' in d){
      if(d.players===null)pe.innerHTML='<div class="phint">⚙ RCON 未启用或未连接 —— 重启服务器后,这里显示每个在线玩家的血量 / 坐标 / 维度 / 饥饿 / 经验 / 模式</div>';
      else if(d.players.length===0)pe.innerHTML='<div class="phint">当前无玩家在线</div>';
      else pe.innerHTML=`<div class="psec"><h3>在线玩家状态 · RCON 实时</h3><table class="ptab">
        <thead><tr><th>玩家</th><th>血量</th><th>维度</th><th>坐标 (X Y Z)</th><th>饥饿</th><th>经验</th><th>模式</th></tr></thead>
        <tbody>${d.players.map(p=>`<tr><td><b>${esc(p.name)}</b></td><td>${p.hp} / 20</td><td>${esc(p.dim)}</td><td class="mono">${esc(p.pos)}</td><td>${p.food} / 20</td><td>Lv.${p.xp}</td><td>${esc(p.mode)}</td></tr>`).join('')}</tbody></table></div>`;
    }
    return d;
  }
  async function logs(){
    const el=document.getElementById('log');if(!el)return;
    try{const j=await(await fetch('/api/logs?id='+id+'&tail=400',{cache:'no-store'})).json();
      const a=document.getElementById('auto'),atb=a&&a.checked;
      el.innerHTML=fmtLog(j.text);if(atb)el.scrollTop=el.scrollHeight;}catch(e){}
  }
  const d=await meta();if(!d)return;if(d.has_log)await logs();
  timer=setInterval(()=>{meta();if(d.has_log)logs();},3000);
}
function route(){
  if(timer){clearInterval(timer);timer=null}
  const id=curRoute();
  if(DATA)renderChrome();
  if(id)detailView(id);else if(DATA)renderOverview();else document.getElementById('view').innerHTML='<div class="empty">加载中…</div>';
}
window.addEventListener('hashchange',route);
async function pollHist(){try{HIST=await(await fetch('/api/history?range=60',{cache:'no-store'})).json()}catch(e){}if(!curRoute()&&DATA)renderOverview()}
poll().then(route);setInterval(poll,5000);
pollHist();setInterval(pollHist,30000);
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype="application/json; charset=utf-8"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/api/status":
            with _lock:
                self._send(json.dumps(_state))
        elif u.path == "/api/detail":
            self._send(json.dumps(detail(q.get("id", [""])[0])))
        elif u.path == "/api/logs":
            self._send(json.dumps({"text": get_logs(q.get("id", [""])[0], q.get("tail", ["400"])[0])}))
        elif u.path == "/api/history":
            self._send(json.dumps(history(q.get("range", ["60"])[0])))
        elif u.path == "/api/players":
            self._send(json.dumps({"players": players_cached(), "perf": mc_perf_cached()}))
        else:
            self._send(HTML, "text/html; charset=utf-8")


if __name__ == "__main__":
    collect()
    threading.Thread(target=prober_loop, daemon=True).start()
    threading.Thread(target=refresher, daemon=True).start()
    print("dashboard v3 on :%d" % PORT, flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
