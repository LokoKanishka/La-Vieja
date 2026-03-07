#!/usr/bin/env python3
import json
import os
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP


ROOT = Path(os.environ.get("FILE_OPS_ROOT", "/home/lucy/Escritorio/La Vieja"))

mcp = FastMCP("file-ops")


def run(cmd: list[str]) -> dict:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(ROOT))
        return {"ok": p.returncode == 0, "code": p.returncode, "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}
    except Exception as e:
        return {"ok": False, "code": -1, "stderr": str(e)}


@mcp.tool(description="Lista archivos en root actual.")
def files_list(max_entries: int = 200) -> str:
    max_entries = max(20, min(int(max_entries), 1000))
    return json.dumps(run(["sh", "-lc", f"find . -maxdepth 4 -type f | sort | head -n {max_entries}"]), ensure_ascii=True)


@mcp.tool(description="Buscar texto en root actual.")
def files_search(query: str) -> str:
    if not query.strip():
        return json.dumps({"ok": False, "error": "query vacia"}, ensure_ascii=True)
    return json.dumps(run(["sh", "-lc", f"rg -n --hidden --glob '!.git' {query!r} . || true"]), ensure_ascii=True)


@mcp.tool(description="Leer archivo texto (truncado).")
def file_read(path: str, max_chars: int = 12000) -> str:
    p = (ROOT / path).resolve()
    try:
        if not str(p).startswith(str(ROOT.resolve())):
            return json.dumps({"ok": False, "error": "path fuera de root"}, ensure_ascii=True)
        data = p.read_text(errors="replace")[: max(200, min(int(max_chars), 50000))]
        return json.dumps({"ok": True, "path": str(p), "content": data}, ensure_ascii=True)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=True)


if __name__ == "__main__":
    mcp.run("stdio")

