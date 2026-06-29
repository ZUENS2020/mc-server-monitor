#!/usr/bin/env python3
"""Generate NPM proxy_host nginx configs from database.sqlite."""
import sqlite3
import os
import sys

DB = os.environ.get("NPM_DB", "/home/zuens2020/nginx-proxy-manager/data/database.sqlite")
OUT = os.environ.get("NPM_CONF_DIR", "/home/zuens2020/nginx-proxy-manager/data/nginx/proxy_host")


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        """
        SELECT id, domain_names, forward_host, forward_port, forward_scheme, certificate_id,
               ssl_forced
        FROM proxy_host ORDER BY id
        """
    ).fetchall()

    for pid, domains, host, port, scheme, cert_id, ssl_forced in rows:
        domain = domains.strip("[]").split(",")[0].strip().strip('"')
        cert_id = cert_id or 0
        listen443 = ""
        if cert_id > 0:
            listen443 = f"""
  listen 443 ssl http2;
  listen [::]:443 ssl http2;
  ssl_certificate /data/custom_ssl/npm-{cert_id}/fullchain.pem;
  ssl_certificate_key /data/custom_ssl/npm-{cert_id}/privkey.pem;"""
        ssl_block = ""
        if ssl_forced:
            ssl_block = """
  if ($scheme != "https") {
    return 301 https://$host$request_uri;
  }"""

        conf = f"""# {domain}
server {{
  set $forward_scheme {scheme};
  set $server         "{esc(host)}";
  set $port           {port};

  listen 80;
  listen [::]:80;{listen443}
  server_name {domain};

  include conf.d/include/letsencrypt-acme-challenge.conf;
  include conf.d/include/block-exploits.conf;
  access_log /data/logs/proxy-host-{pid}_access.log proxy;
  error_log /data/logs/proxy-host-{pid}_error.log warn;
{ssl_block}
  location / {{
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $http_connection;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_http_version 1.1;
    proxy_pass $forward_scheme://$server:$port$request_uri;
  }}
}}
"""
        path = os.path.join(OUT, f"{pid}.conf")
        with open(path, "w", encoding="utf-8") as f:
            f.write(conf)
        print(f"Wrote {path} ({domain} -> {scheme}://{host}:{port})")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
