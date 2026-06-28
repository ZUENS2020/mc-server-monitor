#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minecraft 服务器监控面板 — Crafty 风格 / 全直角 / 可配置 / Docker 就绪。纯标准库。"""
import glob, json, os, re, shutil, socket, sqlite3, ssl, struct, subprocess, threading, time
import urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone, date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _env(key, default=""):
    return os.environ.get(key, default).strip()


def _env_bool(key, default=True):
    v = _env(key, str(default).lower())
    return v.lower() in ("1", "true", "yes", "on")


def _env_int(key, default):
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _env_auto(key, default=True):
    v = _env(key, "auto").lower()
    if v == "auto":
        return None
    return v in ("1", "true", "yes", "on")


def _expand(path):
    return os.path.expanduser(path) if path else ""


def load_config():
    data_dir = _expand(_env("DATA_DIR", "/data"))
    crafty_data = _expand(_env("CRAFTY_DATA_DIR", os.path.join(os.path.expanduser("~"), "crafty")))
    alert_log = _expand(_env("ALERT_LOG_PATH", "")) or os.path.join(data_dir, "alerts.log")
    creds_file = _expand(_env("CRAFTY_CREDS_FILE", "")) or os.path.join(crafty_data, "config", "default-creds.txt")
    return {
        "port": _env_int("DASHBOARD_PORT", 8765),
        "refresh": _env_int("DASHBOARD_REFRESH", 5),
        "title": _env("DASHBOARD_TITLE", "MC 监控"),
        "data_dir": data_dir,
        "crafty_data_dir": crafty_data,
        "crafty_url": _env("CRAFTY_URL", "https://127.0.0.1:8443").rstrip("/"),
        "crafty_user": _env("CRAFTY_USERNAME", "admin"),
        "crafty_password": _env("CRAFTY_PASSWORD", ""),
        "crafty_creds_file": creds_file,
        "crafty_server_id": _env("CRAFTY_SERVER_ID", ""),
        "crafty_tls_verify": _env_bool("CRAFTY_TLS_VERIFY", False),
        "mc_host": _env("MC_HOST", "127.0.0.1"),
        "mc_rcon_host": _env("MC_RCON_HOST", "") or _env("MC_HOST", "127.0.0.1"),
        "mc_port": _env_int("MC_PORT", 25565),
        "mc_connect": _env("MC_CONNECT_ADDRESS", ""),
        "mc_service_name": _env("MC_SERVICE_NAME", "MC 服务器"),
        "mc_version_label": _env("MC_VERSION_LABEL", "Paper"),
        "tunnel_enabled": _env_bool("TUNNEL_ENABLED", False),
        "tunnel_name": _env("TUNNEL_NAME", "隧道"),
        "tunnel_host": _env("TUNNEL_HOST", ""),
        "tunnel_port": _env_int("TUNNEL_PORT", 25565),
        "tunnel_check": _env("TUNNEL_CHECK", "auto").lower(),  # auto | systemd | tcp | none
        "tunnel_systemd_unit": _env("TUNNEL_SYSTEMD_UNIT", "frpc"),
        "enable_host_metrics": _env_bool("ENABLE_HOST_METRICS", True),
        "enable_pcp": _env_auto("ENABLE_PCP", True),
        "enable_coreprotect": _env_auto("ENABLE_COREPROTECT", True),
        "enable_grimac": _env_auto("ENABLE_GRIMAC", True),
        "enable_rcon": _env_auto("ENABLE_RCON", True),
        "enable_crafty_backup": _env_bool("ENABLE_CRAFTY_BACKUP", True),
        "enable_connectivity_probe": _env_bool("ENABLE_CONNECTIVITY_PROBE", True),
        "enable_systemd_logs": _env_bool("ENABLE_SYSTEMD_LOGS", True),
        "pcp_log_dir": _expand(_env("PCP_LOG_DIR", "/var/log/pcp/pmlogger")),
        "proc_root": _expand(_env("PROC_ROOT", "/proc")),
        "alert_log": alert_log,
        "backup_cooldown": _env_int("BACKUP_COOLDOWN_HOURS", 3) * 3600,
        "probe_direct_url": _env("PROBE_DIRECT_URL", "https://www.cloudflare.com"),
        "probe_proxy_url": _env("PROBE_PROXY_URL", "https://www.gstatic.com/generate_204"),
        "log_tz": _env("LOG_TZ", ""),
    }


CFG = load_config()
if CFG["log_tz"]:
    os.environ["TZ"] = CFG["log_tz"]
    if hasattr(time, "tzset"):
        time.tzset()
PORT = CFG["port"]
REFRESH = CFG["refresh"]

ENV = dict(os.environ)
if os.getuid() != 0:
    ENV.setdefault("XDG_RUNTIME_DIR", "/run/user/%d" % os.getuid())


def sh(args, timeout=12):
    try:
        return subprocess.run(args, capture_output=True, text=True, env=ENV, timeout=timeout).stdout
    except Exception:
        return ""


_SSL = ssl.create_default_context()
if not CFG["crafty_tls_verify"]:
    _SSL.check_hostname = False
    _SSL.verify_mode = ssl.CERT_NONE


def _proc(path):
    root = CFG["proc_root"] or "/proc"
    return os.path.join(root, path.lstrip("/"))


def server_dir():
    if CFG["crafty_server_id"]:
        return os.path.join(CFG["crafty_data_dir"], "servers", CFG["crafty_server_id"])
    g = sorted(glob.glob(os.path.join(CFG["crafty_data_dir"], "servers", "*", "")),
               key=os.path.getmtime, reverse=True)
    return g[0].rstrip("/") if g else ""


def crafty_sid():
    if CFG["crafty_server_id"]:
        return CFG["crafty_server_id"]
    d = server_dir()
    return os.path.basename(d) if d else ""


def mc_log_path():
    d = server_dir()
    if not d:
        return ""
    p = os.path.join(d, "logs", "latest.log")
    return p if os.path.exists(p) else ""


def _user_systemd_ok():
    if not CFG["enable_systemd_logs"] or not shutil.which("systemctl"):
        return False
    st = sh(["systemctl", "--user", "is-system-running"], timeout=3).strip()
    return st in ("running", "degraded")


def _tunnel_check_mode():
    mode = CFG["tunnel_check"]
    if mode == "auto":
        return "systemd" if _user_systemd_ok() else "tcp"
    return mode


def _tunnel_sub():
    addr = CFG["mc_connect"] or "%s:%d" % (CFG["tunnel_host"], CFG["tunnel_port"])
    return addr


def build_services():
    mc_log = mc_log_path()
    mc_sub = "%s · %d" % (CFG["mc_version_label"], CFG["mc_port"])
    svcs = {
        "mc": {"name": CFG["mc_service_name"], "group": "Minecraft", "kind": "port",
               "host": CFG["mc_host"], "port": CFG["mc_port"], "sub": mc_sub,
               "log": ("file", mc_log) if mc_log else ("none", "")},
    }
    if CFG["tunnel_enabled"]:
        tmode = _tunnel_check_mode()
        if tmode == "systemd":
            unit = CFG["tunnel_systemd_unit"]
            log = ("journal_user", unit) if CFG["enable_systemd_logs"] else ("none", "")
            svcs["frpc"] = {"name": CFG["tunnel_name"], "group": "Minecraft", "kind": "systemd",
                            "unit": unit, "sub": _tunnel_sub(), "log": log}
        elif tmode == "tcp":
            svcs["frpc"] = {"name": CFG["tunnel_name"], "group": "Minecraft", "kind": "remote_tcp",
                            "host": CFG["tunnel_host"], "port": CFG["tunnel_port"],
                            "sub": _tunnel_sub(), "log": ("none", "")}
    return svcs


SERVICES = build_services()
ORDER = list(SERVICES.keys())
GROUP_ORDER = ["Minecraft"]

_lock = threading.Lock()
_state = {"groups": [], "sys": {}, "alerts": [], "mc_players": None, "mc_perf": None, "mc": None, "updated": 0, "summary": {"up": 0, "warn": 0, "down": 0, "total": 0}}
_prev = {"cpu": None, "net": None, "t": None}


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
    p = os.path.join(server_dir(), "server.properties")
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


_rconc = {"sock": None}
_rconlock = threading.Lock()


def _rcon_open(host, port, password, timeout):
    s = socket.create_connection((host, port), timeout)
    s.settimeout(timeout)
    s.sendall(_rcon_pkt(1, 3, password))
    rid, _, _ = _rcon_read(s)
    if rid == -1:
        s.close()
        raise RuntimeError("rcon auth failed")
    return s


def rcon_exec(cmds, port, password, host=None, timeout=3):
    host = host or CFG["mc_rcon_host"]
    # 持久连接:开一次反复用,断了才重连 —— 避免每次都连/断刷爆服务器日志
    with _rconlock:
        for _ in range(2):
            try:
                if _rconc["sock"] is None:
                    _rconc["sock"] = _rcon_open(host, port, password, timeout)
                s = _rconc["sock"]
                out = []
                for c in cmds:
                    s.sendall(_rcon_pkt(2, 2, c))
                    _, _, body = _rcon_read(s)
                    out.append(body)
                return out
            except Exception:
                try:
                    _rconc["sock"].close()
                except Exception:
                    pass
                _rconc["sock"] = None
        return None


_DIM = {"minecraft:overworld": "主世界", "minecraft:the_nether": "下界", "minecraft:the_end": "末地"}
_GAMET = {"0": "生存", "1": "创造", "2": "冒险", "3": "旁观"}

_session = {}  # 玩家名 -> 本次上线 unix 时间
_sessionlock = threading.Lock()


def fmt_session(s):
    s = int(s)
    if s < 45:
        return "刚刚"
    return fmt_dur(s)


def _logtime_to_unix(h, mi, se, ref=None):
    # latest.log 只有 HH:MM:SS,无日期 —— 在 today/yesterday 中选不超过 ref 的最近时刻
    ref = ref or time.time()
    lt = time.localtime(ref)
    base = date(lt.tm_year, lt.tm_mon, lt.tm_mday)
    best = None
    for delta in range(0, 3):
        d = base - timedelta(days=delta)
        ts = time.mktime((d.year, d.month, d.day, h, mi, se, 0, 0, -1))
        if ts <= ref + 15 and (best is None or ts > best):
            best = ts
    if best is not None:
        return best
    d = base - timedelta(days=1)
    return time.mktime((d.year, d.month, d.day, h, mi, se, 0, 0, -1))


def _session_start_from_log(name, ref=None):
    log = mc_log_path()
    if not log:
        return None
    ref = ref or time.time()
    try:
        with open(log, errors="replace") as f:
            lines = f.readlines()[-1200:]
    except Exception:
        return None
    join_pat = re.compile(r"\[(\d\d):(\d\d):(\d\d)\].*?" + re.escape(name) + r" joined the game")
    leave_pat = re.compile(r"\[(\d\d):(\d\d):(\d\d)\].*?" + re.escape(name) + r" left the game")
    session_start = None
    for ln in lines:
        m = join_pat.search(ln)
        if m:
            h, mi, se = map(int, m.groups())
            session_start = _logtime_to_unix(h, mi, se, ref)
            continue
        m = leave_pat.search(ln)
        if m:
            session_start = None
    return session_start


def touch_player_sessions(names):
    now = time.time()
    cur = set(names)
    with _sessionlock:
        for n in list(_session):
            if n not in cur:
                del _session[n]
        for n in names:
            ts = _session_start_from_log(n, now)
            if ts is not None:
                _session[n] = ts
            elif n not in _session:
                _session[n] = now
        return {n: max(0, int(now - _session[n])) for n in names}


def _after(s):
    m = re.search(r"data:\s*(.*)$", s.strip())
    return m.group(1).strip() if m else ""


def mc_players_detail():
    if CFG["enable_rcon"] is False:
        return None
    props = mc_props()
    if CFG["enable_rcon"] is None and not os.path.exists(os.path.join(server_dir(), "server.properties")):
        return None
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
        touch_player_sessions([])
        return []
    fields = ["Health", "Pos", "Dimension", "foodLevel", "XpLevel", "playerGameType"]
    eq = ["head", "chest", "legs", "feet"]  # 头 胸 腿 脚(1.21 穿戴的甲在 equipment 字段,不在 Inventory 槽)
    cmds = []
    for n in names:
        cmds += ["data get entity %s %s" % (n, f) for f in fields]
        cmds += ["data get entity %s equipment.%s.id" % (n, e) for e in eq]
    res = rcon_exec(cmds, port, pw)
    if res is None:
        return None
    per = len(fields) + len(eq)  # 10
    players = []
    for i, n in enumerate(names):
        c = res[i * per:(i + 1) * per]
        if len(c) < per:
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
        armor = []
        for a in c[6:10]:
            m = re.search(r'"minecraft:([a-z_]+)"', a)
            armor.append(m.group(1) if m else None)
        players.append({"name": n, "hp": hp, "pos": coord,
                        "dim": _DIM.get(dim, dim or "-"), "food": food, "xp": xp,
                        "mode": mode, "armor": armor})
    sess = touch_player_sessions(names)
    for p in players:
        p["online_secs"] = sess.get(p["name"], 0)
        p["online_for"] = fmt_session(sess.get(p["name"], 0))
    sec = security_snapshot()
    for p in players:
        p["place"] = sec["places"].get(p["name"], 0)
    return players


def read_cpu():
    with open(_proc("stat")) as f:
        v = list(map(int, f.readline().split()[1:]))
    return sum(v), v[3] + v[4]


def read_net():
    rx = tx = 0
    with open(_proc("net/dev")) as f:
        for line in f.readlines()[2:]:
            name, data = line.split(":")
            if name.strip() in ("lo",) or name.strip().startswith(("docker", "br-", "veth", "Meta")):
                continue
            d = data.split()
            rx += int(d[0]); tx += int(d[8])
    return rx, tx


def sysstat():
    if not CFG["enable_host_metrics"]:
        return {}
    now = time.time()
    total, idle = read_cpu()
    cpu = 0.0
    if _prev["cpu"]:
        dt, di = total - _prev["cpu"][0], idle - _prev["cpu"][1]
        if dt > 0:
            cpu = round((1 - di / dt) * 100, 1)
    _prev["cpu"] = (total, idle)
    mem = {}
    with open(_proc("meminfo")) as f:
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
    with open(_proc("loadavg")) as f:
        la = f.read().split()[:3]
    with open(_proc("uptime")) as f:
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
        host = svc.get("host", "127.0.0.1")
        st = mc_status(host, svc["port"])
        if st:
            level, detail = "up", "在线 %d / %d" % (st["online"], st["max"])
        elif tcp_open(svc["port"], host):
            level, detail = "up", "监听中(启动中)"
        else:
            level, detail = "down", "无连接"
    elif k == "remote_tcp":
        host, port = svc.get("host", "127.0.0.1"), svc["port"]
        if tcp_open(port, host, 3):
            level, detail = "up", "%s:%d 可达" % (host, port)
        else:
            level, detail = "down", "%s:%d 不可达" % (host, port)
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
    if not CFG["enable_connectivity_probe"]:
        _probe.update(direct=True, proxy=True, frp=True)
        return

    def http(url):
        try:
            urllib.request.urlopen(url, timeout=6)
            return True
        except urllib.error.HTTPError:
            return True
        except Exception:
            return False
    _probe["direct"] = http(CFG["probe_direct_url"])
    _probe["proxy"] = http(CFG["probe_proxy_url"])
    if CFG["tunnel_enabled"]:
        _probe["frp"] = tcp_open(CFG["tunnel_port"], CFG["tunnel_host"], 3)
    else:
        _probe["frp"] = True


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
    if CFG["tunnel_enabled"] and not _probe["frp"]:
        addr = CFG["mc_connect"] or "%s:%d" % (CFG["tunnel_host"], CFG["tunnel_port"])
        add("critical", "frp", "MC 隧道 %s 不可达,朋友可能无法连入服务器" % addr)
    if not _probe["direct"]:
        add("critical", "net", "外网直连中断,疑似网络 / ISP 异常")
    perf = mc_perf_cached()
    if perf and perf.get("tps_1m") is not None:
        t = perf["tps_1m"]
        if t < 14:
            add("critical", "tps", "MC 服务器严重卡顿,TPS %.1f(正常 20)" % t)
        elif t < 18:
            add("warning", "tps", "MC 服务器 TPS 偏低 %.1f(正常 20)" % t)
    sec = security_snapshot()
    for name, rate in sec["places"].items():
        if rate >= 500:
            add("critical", "place_" + name, "%s 放置 %d 块/分,高度疑似自动搭建/打印机" % (name, rate))
        elif rate >= 200:
            add("warning", "place_" + name, "%s 放置 %d 块/分,疑似自动搭建" % (name, rate))
    for f in sec["grim"]:
        add("warning", "grim_%s_%s" % (f["player"], f["check"]),
            "GrimAC:%s 触发 %s (x%d)" % (f["player"], f["check"], f["vl"]))
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
BACKUP_TRIGGER = ("mem", "swap", "cpu", "load", "svc_mc")
_backup = {"last": 0, "token": "", "token_t": 0}


def crafty_password():
    if CFG["crafty_password"]:
        return CFG["crafty_password"]
    try:
        return json.load(open(CFG["crafty_creds_file"]))["password"]
    except Exception:
        return ""


def crafty_token():
    now = time.time()
    if _backup["token"] and now - _backup["token_t"] < 1800:
        return _backup["token"]
    pw = crafty_password()
    if not pw:
        return ""
    try:
        req = urllib.request.Request("%s/api/v2/auth/login" % CFG["crafty_url"],
                                     data=json.dumps({"username": CFG["crafty_user"], "password": pw}).encode(),
                                     headers={"Content-Type": "application/json"})
        tok = json.load(urllib.request.urlopen(req, timeout=8, context=_SSL))["data"]["token"]
        _backup.update(token=tok, token_t=now)
        return tok
    except Exception:
        return ""


def crafty_backup():
    if not CFG["enable_crafty_backup"]:
        return
    sid, tok = crafty_sid(), crafty_token()
    if not sid or not tok:
        return
    try:
        req = urllib.request.Request("%s/api/v2/servers/%s/action/backup_server" % (CFG["crafty_url"], sid),
                                     data=b"", method="POST", headers={"Authorization": "Bearer " + tok})
        urllib.request.urlopen(req, timeout=20, context=_SSL)
    except Exception:
        pass


def do_alert_backup(alerts):
    if not CFG["enable_crafty_backup"]:
        return
    now = time.time()
    keys = {a["key"] for a in alerts}
    if any(k in keys for k in BACKUP_TRIGGER) and now - _backup["last"] >= CFG["backup_cooldown"]:
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
    if CFG["enable_rcon"] is False:
        return None
    props = mc_props()
    if CFG["enable_rcon"] is None and not props:
        return None
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


_mcinfo = {"t": 0, "data": None}
_mcilock = threading.Lock()


def _paper_process():
    # 优先 pgrep；Docker 等精简环境无 procps 时回退扫 /proc(需 pid:host)
    try:
        o = subprocess.run(["pgrep", "-af", "paper.jar"], capture_output=True, text=True, timeout=4, env=ENV)
        if o.stdout.strip():
            line = o.stdout.strip().split("\n", 1)[0]
            pid = line.split(None, 1)[0]
            return pid, line
    except Exception:
        pass
    root = _proc("")
    try:
        for name in os.listdir(root):
            if not name.isdigit():
                continue
            try:
                with open(os.path.join(root, name, "cmdline"), "rb") as f:
                    raw = f.read()
                if b"paper.jar" not in raw:
                    continue
                cmd = raw.decode("utf-8", "replace").replace("\x00", " ")
                return name, cmd
            except OSError:
                pass
    except Exception:
        pass
    return "", ""


def _paper_mem_uptime(pid, cmd):
    if not pid:
        return "-", "-"
    try:
        with open(_proc("%s/status" % pid)) as f:
            rss_kb = 0
            for line in f:
                if line.startswith("VmRSS:"):
                    rss_kb = int(line.split()[1])
                    break
        with open(_proc("%s/stat" % pid)) as f:
            st = f.read().split()
        with open(_proc("uptime")) as f:
            host_up = float(f.read().split()[0])
        clk = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
        et = max(0, int(host_up - int(st[21]) / clk))
        rss_g = rss_kb / 1048576.0
        mm = re.search(r"-Xmx(\d+)([MmGg])", cmd or "")
        xmx_g = (int(mm.group(1)) / 1024.0 if mm.group(2).upper() == "M" else float(mm.group(1))) if mm else None
        mem = ("%.2f / %.1f GiB" % (rss_g, xmx_g)) if xmx_g else ("%.2f GiB" % rss_g)
        return mem, fmt_dur(et)
    except Exception:
        return "-", "-"


def mc_info():
    with _mcilock:
        if _mcinfo["t"] and time.time() - _mcinfo["t"] < 5:
            return _mcinfo["data"]
        st = mc_status(CFG["mc_host"], CFG["mc_port"])
        perf = mc_perf_cached()
        props = mc_props()
        pid, cmd = _paper_process()
        mem, uptime = _paper_mem_uptime(pid, cmd)
        connect = CFG["mc_connect"] or ("%s:%d" % (CFG["tunnel_host"], CFG["tunnel_port"]) if CFG["tunnel_enabled"] else "%s:%d" % (CFG["mc_host"], CFG["mc_port"]))
        tunnel_up = False
        if CFG["tunnel_enabled"]:
            tmode = _tunnel_check_mode()
            if tmode == "systemd":
                tunnel_up = systemd_active(CFG["tunnel_systemd_unit"])
            elif tmode == "tcp":
                tunnel_up = tcp_open(CFG["tunnel_port"], CFG["tunnel_host"], 3)
        d = {"online": bool(st) or tcp_open(CFG["mc_port"], CFG["mc_host"]),
             "players": ("%d / %d" % (st["online"], st["max"])) if st else "-",
             "tps": perf["tps_1m"] if perf else None,
             "mspt": perf["mspt_avg"] if perf else None,
             "version": (st.get("version") if st and st.get("version") else CFG["mc_version_label"]),
             "difficulty": props.get("difficulty", "-"),
             "viewdist": props.get("view-distance", "-"),
             "mem": mem, "uptime": uptime,
             "connect": connect,
             "tunnel": tunnel_up if CFG["tunnel_enabled"] else None,
             "onlinemode": props.get("online-mode", "true"),
             "motd": (st.get("motd") if st else "") or ""}
        _mcinfo["data"] = d
        _mcinfo["t"] = time.time()
        return d


# ---------- 安全检测:放置速率(CoreProtect)+ Grim 违规 ----------
_seccache = {"t": 0, "data": None}
_seclock = threading.Lock()


def cp_db():
    d = server_dir()
    if not d:
        return ""
    g = glob.glob(os.path.join(d, "plugins", "CoreProtect", "*.db"))
    return g[0] if g else ""


def grim_flags():
    if CFG["enable_grimac"] is False:
        return []
    log = mc_log_path()
    if not log or not os.path.exists(log):
        return []
    try:
        with open(log, errors="replace") as f:
            lines = f.readlines()[-300:]
    except Exception:
        return []
    t = time.localtime()
    nowsec = t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec
    seen = {}
    for ln in lines:
        s = re.sub("§.", "", ln)
        m = re.search(r"\[(\d\d):(\d\d):(\d\d)\].*?(\w+) failed (\w[\w/]*) \(x(\d+)\)", s)
        if not m:
            continue
        h, mi, se, player, check, vl = m.groups()
        ts = int(h) * 3600 + int(mi) * 60 + int(se)
        if 0 <= nowsec - ts <= 180:   # 近 3 分钟
            seen[(player, check)] = {"player": player, "check": check, "vl": int(vl)}
    return list(seen.values())


def security_snapshot():
    with _seclock:
        if _seccache["t"] and time.time() - _seccache["t"] < 5:
            return _seccache["data"]
        places = {}
        use_cp = CFG["enable_coreprotect"] is not False
        db = cp_db() if use_cp else ""
        if use_cp and CFG["enable_coreprotect"] is None and not db:
            use_cp = False
        if use_cp and db:
            try:
                c = sqlite3.connect("file:%s?mode=ro" % db, uri=True, timeout=2)
                cut = int(time.time()) - 60
                for name, cnt in c.execute(
                        "select u.user,count(*) from co_block b join co_user u on b.user=u.id "
                        "where b.action=1 and b.time>? and u.user not like '#%' group by b.user", (cut,)):
                    places[name] = cnt
                c.close()
            except Exception:
                pass
        out = {"places": places, "grim": grim_flags()}
        _seccache["data"] = out
        _seccache["t"] = time.time()
        return out


ALERT_LOG = CFG["alert_log"]
_alertlogged = {}   # 当前活跃且已记录的告警 key -> message


def log_alerts(alerts):
    # 每条告警:首次触发记一行,解除时再记一行(去重,避免每 5s 重复)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    cur = {a["key"]: a for a in alerts}
    lines = []
    for k, a in cur.items():
        if k not in _alertlogged:
            lines.append("[%s] [%s] %s" % (ts, a["level"].upper(), a["msg"]))
            _alertlogged[k] = a["msg"]
    for k in list(_alertlogged):
        if k not in cur:
            lines.append("[%s] [RESOLVED] 解除: %s" % (ts, _alertlogged[k]))
            del _alertlogged[k]
    if lines:
        try:
            with open(ALERT_LOG, "a") as fh:
                fh.write("\n".join(lines) + "\n")
        except Exception:
            pass


def read_alertlog(tail=40):
    try:
        with open(ALERT_LOG) as f:
            return "".join(f.readlines()[-int(tail):]) or "(暂无报警记录)"
    except Exception:
        return "(暂无报警记录)"


# ---------- 性能趋势:PCP 优先,否则内存环形缓冲(Docker 无 pmrep 时) ----------
_ring = {"t": [], "cpu": [], "mem": [], "load": [], "last": 0, "interval": 30, "max": 120}
_RING_FILE = os.path.join(CFG["data_dir"], "metrics_ring.json")


def _load_metric_ring():
    try:
        d = json.load(open(_RING_FILE))
        for k in ("t", "cpu", "mem", "load"):
            _ring[k] = (d.get(k) or [])[-_ring["max"]:]
        _ring["last"] = d.get("last", 0)
    except Exception:
        pass


def _save_metric_ring():
    try:
        json.dump({k: _ring[k] for k in ("t", "cpu", "mem", "load")} | {"last": _ring["last"]},
                  open(_RING_FILE, "w"))
    except Exception:
        pass


def record_metric_ring(sysd):
    if not CFG["enable_host_metrics"] or not sysd:
        return
    now = time.time()
    if _ring["t"] and now - _ring["last"] < _ring["interval"]:
        return
    _ring["last"] = now
    _ring["t"].append(time.strftime("%H:%M"))
    _ring["cpu"].append(sysd.get("cpu", 0))
    _ring["mem"].append(sysd.get("mem_pct", 0))
    try:
        _ring["load"].append(float((sysd.get("load") or [0])[0]))
    except (TypeError, ValueError, IndexError):
        _ring["load"].append(0.0)
    for k in ("t", "cpu", "mem", "load"):
        if len(_ring[k]) > _ring["max"]:
            _ring[k] = _ring[k][-_ring["max"]:]
    _save_metric_ring()


def _history_from_pcp(rng):
    arch = newest_archive()
    if not arch:
        return None
    interval = max(30, rng * 60 // 60)
    out = {"t": [], "cpu": [], "mem": [], "load": [], "source": "pcp"}
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
    return out if out["t"] else None


def _seed_ring_from_pcp():
    if _ring["t"] or not _pcp_enabled():
        return False
    d = _history_from_pcp(60)
    if not d or not d.get("t"):
        return False
    n = _ring["max"]
    for k in ("t", "cpu", "mem", "load"):
        _ring[k] = d[k][-n:]
    _ring["last"] = time.time()
    _save_metric_ring()
    return True


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
    try:
        record_metric_ring(sysd)
    except Exception:
        pass
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
        log_alerts(alerts)
    except Exception:
        pass
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
        _state["mc"] = mc_info()
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
        host = svc.get("host", CFG["mc_host"])
        st = mc_status(host, svc["port"])
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
            tiles += [("类型", "Minecraft Java"), ("核心", CFG["mc_version_label"])]
    out = {"id": sid, "name": svc["name"], "group": svc["group"], "sub": svc.get("sub", ""),
           "level": base["level"], "tiles": [{"k": a, "v": b} for a, b in tiles],
           "has_log": svc["log"][0] != "none"}
    if sid == "mc":
        out["players"] = mc_players_detail()
        sec = security_snapshot()
        out["security"] = {
            "places": sorted([[k, v] for k, v in sec["places"].items()], key=lambda x: -x[1])[:8],
            "grim": sec["grim"], "log": read_alertlog(40)}
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
                lines = f.readlines()[-max(tail * 6, 4000):]
            lines = [l for l in lines if "RCON Client" not in l and "RCON Listener" not in l]
            return "".join(lines[-tail:]) or "(空)"
        except Exception as e:
            return "读取失败: %s" % e
    return "(该服务无日志源)"


NCPU = os.cpu_count() or 1
_hist = {"t": 0, "range": 0, "data": None}


def newest_archive():
    if not _pcp_enabled():
        return ""
    g = glob.glob(os.path.join(CFG["pcp_log_dir"], "*", "*.index"))
    g.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return ",".join(p[:-6] for p in g[:2]) if g else ""


def _pcp_enabled():
    if CFG["enable_pcp"] is False:
        return False
    if not shutil.which("pmrep"):
        return False
    return os.path.isdir(CFG["pcp_log_dir"])


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
    out = None
    if _pcp_enabled():
        try:
            out = _history_from_pcp(rng)
        except Exception:
            out = None
    if not out or not out.get("t"):
        out = {"t": _ring["t"][:], "cpu": _ring["cpu"][:], "mem": _ring["mem"][:],
               "load": _ring["load"][:], "source": "live"}
    _hist.update(t=now, range=rng, data=out)
    return out


HTML = r"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__DASHBOARD_TITLE__</title><style>
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
.backendmeta{font-size:12.5px;font-variant-numeric:tabular-nums;color:var(--tx3)}
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
.histbtn{padding:4px 11px;font-size:13px;border:1px solid var(--bd);color:var(--tx2);cursor:pointer;user-select:none}
.histbtn:hover{color:var(--tx);background:var(--panel2);border-color:var(--bd2)}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.62);z-index:50;align-items:center;justify-content:center}
.modal.on{display:flex}
.modal-box{width:min(920px,92vw);max-height:82vh;background:var(--panel);border:1px solid var(--bd2);display:flex;flex-direction:column}
.modal-h{flex:0 0 auto;display:flex;align-items:center;justify-content:space-between;padding:13px 18px;border-bottom:1px solid var(--bd);font-size:15px;font-weight:600}
.modal-x{font-size:13px;color:var(--tx2);cursor:pointer;font-weight:400}
.modal-x:hover{color:var(--tx)}
.modal-log{flex:1;overflow:auto;padding:14px 18px;font-family:"SF Mono",Consolas,monospace;font-size:12.5px;line-height:1.7;background:#06090d;white-space:pre-wrap;word-break:break-word}
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
/* MC 状态面板 */
.mcrow{display:grid;grid-template-columns:repeat(6,1fr);gap:12px}
.mctile{background:var(--panel);border:1px solid var(--bd);padding:11px 14px}
.mctile .k{font-size:11.5px;color:var(--tx3);text-transform:uppercase;letter-spacing:.8px;margin-bottom:7px}
.mctile .v{font-size:17px;font-weight:600;font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
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
.gflag{margin-top:10px;padding:9px 13px;font-size:13px;color:#ff9a93;background:rgba(248,81,73,.12);border:1px solid rgba(248,81,73,.3);font-weight:600}
.seclog{margin-top:14px}
.seclog-h{font-size:12px;color:var(--tx3);text-transform:uppercase;letter-spacing:.8px;margin-bottom:7px;display:flex;align-items:center;justify-content:space-between;gap:10px}
.seclog-h .r{display:flex;align-items:center;gap:12px;font-size:12px;font-weight:400;color:var(--tx3);text-transform:none;letter-spacing:0}
.seclog-h a{cursor:pointer;color:var(--tx3)}.seclog-h a:hover{color:var(--tx)}
.seclog pre{background:#06090d;border:1px solid var(--bd);padding:11px 14px;max-height:200px;overflow:auto;font-family:"SF Mono",Consolas,monospace;font-size:12px;line-height:1.6;color:#bcc6d2;white-space:pre-wrap;word-break:break-word}
/* 首页玩家墙 */
.psec-home{margin-top:18px}
.pcards{display:grid;gap:12px}
.pcard{display:flex;gap:11px;align-items:center;background:var(--card);border:1px solid var(--bd);border-left:3px solid var(--grn);padding:10px 13px}
.pcard.danger{border-left-color:var(--yel)}
.pcard.dead{border-left-color:var(--red);animation:bl 1.2s infinite}
.pav{width:46px;height:46px;flex:0 0 auto;image-rendering:pixelated;background:#0e131a;border:1px solid var(--bd)}
.pinfo{flex:1;min-width:0}
.pname{font-size:15px;font-weight:600;margin-bottom:6px;display:flex;align-items:center;gap:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pflag{font-size:10px;font-weight:700;padding:1px 5px;margin-left:auto;flex:0 0 auto}
.pflag.w{background:rgba(210,153,34,.18);color:#e3b341}
.pflag.c{background:rgba(248,81,73,.2);color:#ff7b72}
.pmode{font-size:11px;color:var(--tx3);border:1px solid var(--bd);padding:1px 7px;font-weight:400;flex:0 0 auto}
.psess{font-size:11px;color:var(--tx3);border:1px solid var(--bd);padding:1px 7px;font-weight:400;flex:0 0 auto;font-variant-numeric:tabular-nums}
.pbar{position:relative;height:14px;background:#0c1016;border:1px solid var(--bd);margin-bottom:4px;overflow:hidden}
.pbar i{display:block;height:100%;transition:width .5s}
.pbar.hp i{background:#d23b3b}.pbar.food i{background:#c8862f}
.pbar span{position:absolute;left:8px;top:0;line-height:16px;font-size:11px;color:#fff;text-shadow:0 1px 2px #000;font-variant-numeric:tabular-nums}
.pmeta{font-size:11.5px;color:var(--tx3);margin-top:7px;font-variant-numeric:tabular-nums;display:flex;align-items:center;justify-content:space-between;gap:8px}
.pcoord{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.parmor{display:grid;grid-template-columns:repeat(4,13px);gap:3px;flex:0 0 59px;width:59px;height:13px;align-items:center}
.aslot{width:13px;height:13px;min-width:13px;max-width:13px;min-height:13px;max-height:13px;border:1px solid var(--bd);box-sizing:border-box;display:block;line-height:0;overflow:hidden;padding:0;margin:0}
.aslot.empty{background:rgba(255,255,255,.04);border:1px solid #4d5159}
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
    <div class="ti"><span id="title">总览</span></div>
    <div class="r"><div class="pills" id="pills"></div><div class="sysmeta" id="sysmeta"></div><div class="backendmeta" id="backendmeta">后端 检测中</div><div id="clock"></div></div>
  </div>
  <div class="alertbar" id="alertbar"></div>
  <main id="view"></main>
  <div class="modal" id="alogmodal" onclick="if(event.target===this)closeAlog()">
    <div class="modal-box">
      <div class="modal-h"><span>报警历史 · alerts.log</span><div class="r" style="display:flex;align-items:center;gap:14px;font-size:12px;font-weight:400;color:var(--tx3)"><label style="display:flex;gap:6px;align-items:center"><input type="checkbox" id="alogmodalauto" checked>自动滚动</label><a class="modal-x" onclick="scrollAlog()">↓ 底部</a><a class="modal-x" onclick="closeAlog()">✕ 关闭</a></div></div>
      <div class="modal-log" id="alogtext"></div>
    </div>
  </div>
</div>
<script>
let DATA=null,timer=null,HIST=null,BACKEND={ok:null,latency:null,failCount:0};
function tick(){document.getElementById('clock').textContent=new Date().toLocaleTimeString('zh-CN',{hour12:false})}
setInterval(tick,1000);tick();
function esc(s){return(s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function scrollAlog(){const el=document.getElementById('alogtext');if(el)el.scrollTop=el.scrollHeight;}
async function openAlog(){
  const m=document.getElementById('alogmodal');m.classList.add('on');
  const el=document.getElementById('alogtext');el.innerHTML='加载中…';
  try{
    const j=await(await fetch('/api/alertlog?tail=300',{cache:'no-store'})).json();
    const t=j.text||'';
    if(!t.trim()){el.innerHTML='<div style="color:var(--tx3)">暂无报警记录</div>';return;}
    el.innerHTML=t.split('\n').map(l=>{
      let c='#bcc6d2';
      if(l.indexOf('[CRITICAL]')>=0)c='#ff7b72';
      else if(l.indexOf('[WARNING]')>=0)c='#e3b341';
      else if(l.indexOf('[RESOLVED]')>=0)c='#56d364';
      else if(l.indexOf('[INFO]')>=0)c='#5fd9cb';
      return `<div style="color:${c}">${esc(l)||'&nbsp;'}</div>`;
    }).join('');
    const a=document.getElementById('alogmodalauto');if(!a||a.checked)scrollAlog();
  }catch(e){el.innerHTML='<div style="color:var(--red)">加载失败</div>';}
}
function closeAlog(){document.getElementById('alogmodal').classList.remove('on');}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeAlog();});
function fb(n){if(!n)return'0 B/s';const u=['B','KB','MB','GB'];let i=0;while(n>=1024&&i<3){n/=1024;i++}return n.toFixed(i?1:0)+' '+u[i]+'/s'}
function fg(b){const u=['B','KB','MB','GB','TB'];let i=0;while(b>=1024&&i<4){b/=1024;i++}return b.toFixed(1)+' '+u[i]}
function lvlc(p){return p>=90?'c':p>=70?'w':''}

function curRoute(){return location.hash.startsWith('#/s/')?location.hash.slice(4):''}
function refreshBackendMeta(){
  const el=document.getElementById('backendmeta');if(!el)return;
  const b=BACKEND;
  if(b.ok===null){el.textContent='后端 检测中';el.style.color='var(--tx3)';return;}
  if(b.ok){el.textContent='后端 正常 · '+b.latency+' ms';el.style.color='var(--grn)';return;}
  el.textContent='后端 断开'+(b.failCount?' · 失败 '+b.failCount+' 次':'');
  el.style.color='var(--red)';
}
async function poll(){
  const t0=performance.now();
  try{
    const r=await fetch('/api/status',{cache:'no-store'});
    const latency=Math.round(performance.now()-t0);
    if(!r.ok)throw new Error(String(r.status));
    DATA=await r.json();
    BACKEND={ok:true,latency,failCount:0};
  }catch(e){
    BACKEND={...BACKEND,ok:false,failCount:(BACKEND.failCount||0)+1};
    refreshBackendMeta();
    return;
  }
  renderChrome();const id=curRoute();
  if(!id)renderOverview();
}
function renderChrome(){
  const alz=DATA.alerts||[];
  const crit=alz.filter(a=>a.level==='critical').length, warn=alz.filter(a=>a.level==='warning').length;
  let ph='';
  if(crit)ph+=`<span class="pill down"><span class="d"></span>${crit} 故障</span>`;
  if(warn)ph+=`<span class="pill warn"><span class="d"></span>${warn} 警告</span>`;
  if(!ph)ph=`<span class="pill up"><span class="d"></span>运行正常</span>`;
  document.getElementById('pills').innerHTML=ph;
  document.getElementById('sysmeta').textContent=`服务器 ${(DATA.sys||{}).uptime||'-'}`;
  refreshBackendMeta();
  const al=DATA.alerts||[],ab=document.getElementById('alertbar');
  if(ab){
    if(al.length){ab.style.display='block';ab.innerHTML=al.map(a=>
      `<div class="alert ${a.level}"><span class="ai">${a.level=='critical'?'⛔':a.level=='info'?'⚙':'⚠'}</span><span>${a.msg}</span><span class="at">${a.since}</span></div>`).join('')}
    else{ab.style.display='none';ab.innerHTML=''}
  }
  document.title=(al.some(x=>x.level=='critical')?'⛔ ':(al.length?'⚠ ':''))+'__DASHBOARD_TITLE__';
}
function renderOverview(){
  document.getElementById('title').textContent='总览';
  const sy=DATA.sys||{};
  const sys=`<section class="sec full" style="margin-top:16px"><h2><span class="bar2"></span>整机资源</h2><div class="sysrow">
    ${statBar('CPU',sy.cpu+' %',(sy.ncpu||'')+' 核',sy.cpu)}
    ${statBar('内存',sy.mem_pct+' %',fg((sy.mem_used||0)*1073741824)+' / '+fg((sy.mem_total||0)*1073741824),sy.mem_pct)}
    ${statBar('磁盘 /',sy.disk_pct+' %',fg(sy.disk_used||0)+' / '+fg(sy.disk_total||0),sy.disk_pct)}
    ${statBar('Swap',sy.swap_total?Math.round(sy.swap_used/sy.swap_total*100)+' %':'0 %',fg((sy.swap_used||0)*1073741824)+' / '+fg((sy.swap_total||0)*1073741824),sy.swap_total?sy.swap_used/sy.swap_total*100:0)}
    ${statPlain('网络','↓ '+fb(sy.net_rx),'↑ '+fb(sy.net_tx))}
    ${statPlain('系统负载',(sy.load||['-'])[0],'1 / 5 / 15 min')}
  </div></section>`;
  let charts='';
  if(HIST&&HIST.t&&HIST.t.length){
    const src=HIST.source==='pcp'?'PCP':'实时采样';
    charts=`<section class="sec full" style="margin-top:18px"><h2><span class="bar2"></span>性能趋势 · 近 60 分钟（${src}）</h2>
      <div class="charts">${chart('CPU 使用率',HIST.cpu,'%','#30bcb0',100)}${chart('内存使用率',HIST.mem,'%','#8957e5',100)}${chart('系统负载 1m',HIST.load,'','#d29922',null)}</div></section>`;
  }
  document.getElementById('view').innerHTML=mcPanel(DATA.mc||{})+sys+charts+'<div id="pwall"></div>';
  renderPwall(DATA.mc_players,DATA.mc_perf);
}
function mcTile(k,v,col){return `<div class="mctile"><div class="k">${k}</div><div class="v" style="${col?'color:'+col:''}">${esc(String(v))}</div></div>`}
function mcPanel(m){
  const onl=!!m.online;
  const tcol=(m.tps==null)?'var(--tx2)':tpsColor(m.tps);
  return `<section class="sec full"><h2><span class="bar2"></span>Minecraft 服务器<a class="histbtn" style="margin-left:auto;font-size:12px" onclick="location.hash='#/s/mc'">详情 / 日志 ›</a></h2>
    <div class="mcrow">
      ${mcTile('状态',onl?'在线':'离线',onl?'var(--grn)':'var(--red)')}
      ${mcTile('在线人数',m.players||'-')}
      ${mcTile('TPS',(m.tps==null?'-':m.tps),tcol)}
      ${mcTile('MSPT',(m.mspt==null?'-':m.mspt+' ms'))}
      ${mcTile('已占用内存',m.mem||'-')}
      ${mcTile('运行时长',m.uptime||'-')}
      ${mcTile('难度',m.difficulty||'-')}
      ${mcTile('视距',m.viewdist||'-')}
      ${mcTile('验证',m.onlinemode==='false'?'离线':'正版')}
      ${mcTile('版本',m.version||'-')}
      ${mcTile('隧道',m.tunnel===null?'-':(m.tunnel?'正常':'断开'),m.tunnel===null?'var(--tx2)':(m.tunnel?'var(--grn)':'var(--red)'))}
      ${mcTile('连接地址',m.connect||'-')}
    </div></section>`;
}
function pcols(n){return n<=1?1:n<=2?2:n<=3?3:n<=8?4:n<=15?5:6}
function armorMat(it){
  if(!it)return null;
  if(it.startsWith('netherite_'))return '#4a443f';
  if(it.startsWith('diamond_'))return '#2f8e84';
  if(it.startsWith('iron_'))return '#9a9c9c';
  if(it.startsWith('golden_'))return '#9c7d22';
  if(it.startsWith('chainmail_'))return '#6a6c6e';
  if(it.startsWith('leather_'))return '#7a5430';
  if(it==='turtle_helmet')return '#45824a';
  if(it==='elytra')return '#8a7e9a';
  return '#777a7d';
}
function armorSlotsHtml(armor){
  return (armor||[null,null,null,null]).map(it=>{
    const c=armorMat(it);
    return c?`<span class="aslot" style="background:${c}"></span>`:`<span class="aslot empty"></span>`;
  }).join('');
}
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
  const pl=p.place||0;
  const pbadge=pl>=500?`<span class="pflag c">▲${pl}/m</span>`:pl>=200?`<span class="pflag w">▲${pl}/m</span>`:'';
  return `<div class="pcard ${cls}">
    <img class="pav" src="https://minotar.net/helm/${nm}/56.png" onerror="this.onerror=null;this.src='https://minotar.net/helm/MHF_Steve/56.png'">
    <div class="pinfo">
      <div class="pname">${esc(p.name)}<span class="pmode">${esc(p.mode)}</span><span class="psess">${esc(p.online_for||'-')}</span>${pbadge}</div>
      <div class="pbar hp"><i style="width:${Math.max(0,Math.min(100,hp/20*100))}%"></i><span>HP ${hp} / 20</span></div>
      <div class="pbar food"><i style="width:${Math.max(0,Math.min(100,food/20*100))}%"></i><span>FOOD ${food} / 20</span></div>
      <div class="pmeta"><span class="pcoord">${esc(p.dim)} · Lv.${esc(String(p.xp))} · ${esc(p.pos)}</span><span class="parmor">${armorSlotsHtml(p.armor)}</span></div>
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
        <div id="secsec"></div>
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
        <thead><tr><th>玩家</th><th>血量</th><th>维度</th><th>坐标 (X Y Z)</th><th>饥饿</th><th>经验</th><th>模式</th><th>在线时长</th><th>护甲</th></tr></thead>
        <tbody>${d.players.map(p=>`<tr><td><b>${esc(p.name)}</b></td><td>${p.hp} / 20</td><td>${esc(p.dim)}</td><td class="mono">${esc(p.pos)}</td><td>${p.food} / 20</td><td>Lv.${p.xp}</td><td>${esc(p.mode)}</td><td>${esc(p.online_for||'-')}</td><td><span class="parmor">${armorSlotsHtml(p.armor)}</span></td></tr>`).join('')}</tbody></table></div>`;
    }
    const se=document.getElementById('secsec');
    if(se&&d.security){
      const pls=d.security.places||[],gr=d.security.grim||[];
      const alogAuto=!document.getElementById('alogauto')||document.getElementById('alogauto').checked;
      let h='<div class="psec"><h3>安全检测 · 放置速率(近1分钟) / GrimAC 违规</h3>';
      if(pls.length){h+='<table class="ptab"><thead><tr><th>玩家</th><th>放置 / 分钟</th></tr></thead><tbody>'+pls.map(r=>`<tr><td>${esc(r[0])}</td><td style="color:${r[1]>=500?'#ff7b72':r[1]>=200?'#e3b341':'#bcc6d2'};font-weight:600">${r[1]}</td></tr>`).join('')+'</tbody></table>';}
      else h+='<div class="phint">近 1 分钟无方块放置记录</div>';
      h+=gr.length?('<div class="gflag">GrimAC 违规:'+gr.map(f=>`${esc(f.player)} → ${esc(f.check)} (x${f.vl})`).join(' · ')+'</div>'):'<div class="phint" style="margin-top:8px">GrimAC:近 3 分钟无违规</div>';
      if(d.security.log!=null){h+=`<div class="seclog"><div class="seclog-h"><span>报警历史(全部 · 持久化 alerts.log)</span><div class="r"><label style="display:flex;gap:6px;align-items:center"><input type="checkbox" id="alogauto"${alogAuto?' checked':''}>自动滚动</label><a onclick="var p=document.getElementById('alogpre');if(p)p.scrollTop=p.scrollHeight">↓ 底部</a></div></div><pre id="alogpre">${esc(d.security.log)}</pre></div>`;}
      h+='</div>';
      se.innerHTML=h;
      if(alogAuto){const p=document.getElementById('alogpre');if(p)p.scrollTop=p.scrollHeight;}
    } else if(se){se.innerHTML='';}
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
poll().then(()=>{route();pollHist();});setInterval(poll,5000);
setInterval(pollHist,30000);
</script></body></html>"""


def page_html():
    return HTML.replace("__DASHBOARD_TITLE__", CFG["title"])


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
        elif u.path == "/api/alertlog":
            self._send(json.dumps({"text": read_alertlog(q.get("tail", ["80"])[0])}))
        else:
            self._send(page_html(), "text/html; charset=utf-8")


if __name__ == "__main__":
    import sys
    os.makedirs(CFG["data_dir"], exist_ok=True)
    ad = os.path.dirname(CFG["alert_log"])
    if ad:
        os.makedirs(ad, exist_ok=True)
    _load_metric_ring()
    if len(sys.argv) > 1 and sys.argv[1] == "--seed-history":
        ok = _seed_ring_from_pcp()
        print("seeded %d points from PCP" % len(_ring["t"]) if ok else "seed skipped (no PCP data)")
        sys.exit(0)
    if not _ring["t"]:
        _seed_ring_from_pcp()
    collect()
    threading.Thread(target=prober_loop, daemon=True).start()
    threading.Thread(target=refresher, daemon=True).start()
    print("dashboard on :%d (%s)" % (PORT, CFG["title"]), flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
