#!/usr/bin/env bash
set -euo pipefail

if ! command -v n8n >/dev/null 2>&1; then
  echo "n8n no esta instalado en PATH." >&2
  exit 1
fi

export N8N_PORT=5111
export N8N_HOST=0.0.0.0
export N8N_PROTOCOL=http
export N8N_SECURE_COOKIE=false
export N8N_DIAGNOSTICS_ENABLED=false

echo "Iniciando n8n en http://127.0.0.1:${N8N_PORT}"
exec n8n start
