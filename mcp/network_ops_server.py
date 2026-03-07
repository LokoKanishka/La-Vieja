#!/usr/bin/env python3
import json
import os
import socket
import urllib.error
import urllib.request

from mcp.server.fastmcp import FastMCP


TIMEOUT = float(os.environ.get("NET_TIMEOUT", "8"))
MAX_CHARS = int(os.environ.get("NET_MAX_CHARS", "8000"))

mcp = FastMCP("network-ops")


@mcp.tool(description="HTTP HEAD request a URL.")
def url_head(url: str) -> str:
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.dumps({"ok": True, "status": r.status, "headers": dict(r.headers)}, ensure_ascii=True)
    except urllib.error.HTTPError as e:
        return json.dumps({"ok": False, "status": e.code, "error": str(e)}, ensure_ascii=True)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=True)


@mcp.tool(description="HTTP GET text from URL (truncated).")
def url_get(url: str) -> str:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = r.read(MAX_CHARS).decode("utf-8", errors="replace")
            return json.dumps({"ok": True, "status": r.status, "body": data}, ensure_ascii=True)
    except urllib.error.HTTPError as e:
        return json.dumps({"ok": False, "status": e.code, "error": str(e)}, ensure_ascii=True)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=True)


@mcp.tool(description="DNS lookup (A/AAAA) by hostname.")
def dns_lookup(host: str) -> str:
    try:
        infos = socket.getaddrinfo(host, None)
        ips = sorted({info[4][0] for info in infos})
        return json.dumps({"ok": True, "host": host, "ips": ips}, ensure_ascii=True)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=True)


@mcp.tool(description="TCP connectivity check host:port.")
def tcp_check(host: str, port: int) -> str:
    s = socket.socket()
    s.settimeout(TIMEOUT)
    try:
        s.connect((host, int(port)))
        s.close()
        return json.dumps({"ok": True, "host": host, "port": int(port)}, ensure_ascii=True)
    except Exception as e:
        return json.dumps({"ok": False, "host": host, "port": int(port), "error": str(e)}, ensure_ascii=True)


if __name__ == "__main__":
    mcp.run("stdio")

