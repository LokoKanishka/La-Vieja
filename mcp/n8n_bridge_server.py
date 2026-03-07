#!/usr/bin/env python3
import json
import os
import sqlite3
import urllib.parse
import urllib.request
from pathlib import Path

from mcp.server.fastmcp import FastMCP


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/lucy/Escritorio/La Vieja"))
N8N_BASE = os.environ.get("N8N_BASE", "http://127.0.0.1:5111")
N8N_DB = PROJECT_ROOT / "n8n" / "data" / "database.sqlite"

mcp = FastMCP("n8n-bridge")


def get_webhook_path(method: str, suffix: str) -> str | None:
    if not N8N_DB.exists():
        return None
    con = sqlite3.connect(str(N8N_DB))
    cur = con.cursor()
    row = cur.execute(
        "select webhookPath from webhook_entity where method=? and webhookPath like ? order by rowid desc limit 1",
        (method.upper(), f"%{suffix}"),
    ).fetchone()
    con.close()
    return row[0] if row else None


def call_get(path: str, query: dict[str, str] | None = None) -> dict:
    qs = urllib.parse.urlencode(query or {})
    url = f"{N8N_BASE}/webhook/{path}" + (f"?{qs}" if qs else "")
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return {"ok": True, "status": r.status, "url": url, "body": r.read().decode("utf-8", errors="replace")}
    except Exception as e:
        return {"ok": False, "url": url, "error": str(e)}


def call_post(path: str, payload: dict) -> dict:
    url = f"{N8N_BASE}/webhook/{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, method="POST", data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return {"ok": True, "status": r.status, "url": url, "body": r.read().decode("utf-8", errors="replace")}
    except Exception as e:
        return {"ok": False, "url": url, "error": str(e)}


@mcp.tool(description="Lista webhooks memory registrados en n8n.")
def webhooks_memory() -> str:
    if not N8N_DB.exists():
        return json.dumps({"ok": False, "error": f"no db: {N8N_DB}"}, ensure_ascii=True)
    con = sqlite3.connect(str(N8N_DB))
    cur = con.cursor()
    rows = cur.execute(
        "select method, webhookPath from webhook_entity where webhookPath like '%memory/%' order by method, webhookPath"
    ).fetchall()
    con.close()
    return json.dumps({"ok": True, "count": len(rows), "items": [{"method": m, "url": f"{N8N_BASE}/webhook/{p}"} for m, p in rows]}, ensure_ascii=True)


@mcp.tool(description="n8n memory recent (dias).")
def memory_recent(days: int = 1) -> str:
    path = get_webhook_path("GET", "/memory/recent")
    if not path:
        return json.dumps({"ok": False, "error": "webhook recent no encontrado"}, ensure_ascii=True)
    return json.dumps(call_get(path, {"days": str(days)}), ensure_ascii=True)


@mcp.tool(description="n8n memory find por texto.")
def memory_find(query: str) -> str:
    path = get_webhook_path("GET", "/memory/find")
    if not path:
        return json.dumps({"ok": False, "error": "webhook find no encontrado"}, ensure_ascii=True)
    return json.dumps(call_get(path, {"query": query}), ensure_ascii=True)


@mcp.tool(description="n8n memory add.")
def memory_add(summary: str, details: str = "", tags: str = "general") -> str:
    path = get_webhook_path("POST", "/memory/add")
    if not path:
        return json.dumps({"ok": False, "error": "webhook add no encontrado"}, ensure_ascii=True)
    return json.dumps(call_post(path, {"summary": summary, "details": details, "tags": tags}), ensure_ascii=True)


if __name__ == "__main__":
    mcp.run("stdio")

