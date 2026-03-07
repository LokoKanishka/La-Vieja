#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/lucy/Escritorio/La Vieja"))
N8N_DB = PROJECT_ROOT / "n8n" / "data" / "database.sqlite"
MEMORY_DIR = PROJECT_ROOT / "memory"


def run_cmd(cmd: list[str]) -> dict:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=60)
        return {"ok": proc.returncode == 0, "code": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
    except Exception as exc:
        return {"ok": False, "code": -1, "stdout": "", "stderr": str(exc)}


def make_server(mode: str) -> FastMCP:
    mcp = FastMCP(f"local-ops-{mode}")

    if mode in ("all", "ops"):
        @mcp.tool(description="Estado rapido de CPU/RAM/disco/procesos.")
        def machine_status() -> str:
            df = run_cmd(["df", "-h", "/"])
            mem = run_cmd(["free", "-h"])
            up = run_cmd(["uptime"])
            ps = run_cmd(["sh", "-lc", "ps -eo pid,comm,%mem,%cpu --sort=-%mem | head -n 12"])
            return json.dumps({"df": df, "mem": mem, "uptime": up, "top": ps}, ensure_ascii=True)

        @mcp.tool(description="Limpieza segura de cache/temporales de usuario (sin sudo).")
        def cleanup_safe_user() -> str:
            commands = [
                ["sh", "-lc", "find /tmp -mindepth 1 -xdev -mtime +1 -delete 2>/dev/null || true"],
                ["sh", "-lc", "rm -rf ~/.cache/thumbnails ~/.cache/fontconfig ~/.cache/mesa_shader_cache ~/.cache/mesa_shader_cache_db ~/.cache/gstreamer-1.0 2>/dev/null || true"],
                ["sh", "-lc", "rm -rf ~/.config/Code/CachedExtensionVSIXs 2>/dev/null || true"],
                ["sync"],
            ]
            out = [run_cmd(c) for c in commands]
            final_mem = run_cmd(["free", "-h"])
            return json.dumps({"steps": out, "mem_after": final_mem}, ensure_ascii=True)

    if mode in ("all", "memory"):
        @mcp.tool(description="Guardar nota en memoria diaria indexada.")
        def memory_add(summary: str, details: str = "", tags: str = "general") -> str:
            script = PROJECT_ROOT / "scripts" / "n8n_memory_add.sh"
            res = run_cmd(["sh", str(script), summary, details, tags])
            return json.dumps(res, ensure_ascii=True)

        @mcp.tool(description="Buscar texto/tag en memoria indexada.")
        def memory_find(query: str) -> str:
            script = PROJECT_ROOT / "scripts" / "n8n_memory_find.sh"
            res = run_cmd(["sh", str(script), query])
            return json.dumps(res, ensure_ascii=True)

        @mcp.tool(description="Leer memorias recientes por cantidad de dias.")
        def memory_recent(days: int = 2) -> str:
            script = PROJECT_ROOT / "scripts" / "n8n_memory_recent.sh"
            res = run_cmd(["sh", str(script), str(days)])
            return json.dumps(res, ensure_ascii=True)

    if mode in ("all", "n8n"):
        @mcp.tool(description="Estado basico de n8n local en puerto 5111.")
        def n8n_status() -> str:
            root = run_cmd(["curl", "-sS", "-m", "3", "http://127.0.0.1:5111/rest/settings"])
            return json.dumps({"settings": root}, ensure_ascii=True)

        @mcp.tool(description="Lista rutas webhook registradas en base n8n.")
        def n8n_webhooks() -> str:
            if not N8N_DB.exists():
                return json.dumps({"ok": False, "error": f"no db: {N8N_DB}"}, ensure_ascii=True)
            try:
                con = sqlite3.connect(str(N8N_DB))
                cur = con.cursor()
                rows = cur.execute(
                    "select method, webhookPath, workflowId from webhook_entity order by method, webhookPath"
                ).fetchall()
                con.close()
                urls = [{"method": m, "path": p, "url": f"http://127.0.0.1:5111/webhook/{p}", "workflowId": w} for m, p, w in rows]
                return json.dumps({"ok": True, "count": len(urls), "webhooks": urls}, ensure_ascii=True)
            except Exception as exc:
                return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True)

    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(description="Local MCP ops server")
    parser.add_argument("--mode", default="all", choices=["all", "ops", "memory", "n8n"])
    args = parser.parse_args()
    server = make_server(args.mode)
    server.run("stdio")


if __name__ == "__main__":
    main()

