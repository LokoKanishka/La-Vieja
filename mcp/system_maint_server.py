#!/usr/bin/env python3
import json
import os
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/lucy/Escritorio/La Vieja"))
CLEAN_LEVEL = os.environ.get("CLEAN_LEVEL", "normal")

mcp = FastMCP("system-maint")


def run(cmd: list[str]) -> dict:
    try:
        p = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=90)
        return {"ok": p.returncode == 0, "code": p.returncode, "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}
    except Exception as e:
        return {"ok": False, "code": -1, "stderr": str(e)}


@mcp.tool(description="Estado rapido de disco y RAM.")
def health() -> str:
    return json.dumps(
        {
            "df": run(["df", "-h", "/"]),
            "mem": run(["free", "-h"]),
            "uptime": run(["uptime"]),
            "top_mem": run(["sh", "-lc", "ps -eo pid,comm,%mem,%cpu --sort=-%mem | head -n 12"]),
        },
        ensure_ascii=True,
    )


@mcp.tool(description="Limpieza segura de usuario (sin sudo).")
def cleanup_user() -> str:
    steps = []
    steps.append(run(["sh", "-lc", "find /tmp -mindepth 1 -xdev -mtime +1 -delete 2>/dev/null || true"]))
    steps.append(run(["sh", "-lc", "rm -rf ~/.cache/thumbnails ~/.cache/fontconfig ~/.cache/mesa_shader_cache ~/.cache/mesa_shader_cache_db ~/.cache/gstreamer-1.0 2>/dev/null || true"]))
    steps.append(run(["sh", "-lc", "rm -rf ~/.config/Code/CachedExtensionVSIXs 2>/dev/null || true"]))
    if CLEAN_LEVEL == "aggressive":
        steps.append(run(["sh", "-lc", "rm -rf ~/.cache/mozilla ~/.config/Code/Cache ~/.config/Code/CachedData 2>/dev/null || true"]))
    steps.append(run(["sync"]))
    return json.dumps({"ok": True, "clean_level": CLEAN_LEVEL, "steps": steps, "mem_after": run(["free", "-h"])}, ensure_ascii=True)


@mcp.tool(description="Uso de disco por carpeta (top).")
def disk_hotspots(path: str = "/home/lucy", depth: int = 2) -> str:
    depth = max(1, min(int(depth), 4))
    cmd = ["sh", "-lc", f"du -h --max-depth={depth} '{path}' 2>/dev/null | sort -h | tail -n 40"]
    return json.dumps(run(cmd), ensure_ascii=True)


if __name__ == "__main__":
    mcp.run("stdio")

