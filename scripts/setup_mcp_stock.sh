#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/lucy/Escritorio/La Vieja"
PY="/usr/bin/python3"

add_or_replace() {
  local name="$1"
  shift
  codex mcp remove "$name" >/dev/null 2>&1 || true
  codex mcp add "$name" -- "$@"
}

add_or_replace_env() {
  local name="$1"
  local env1="$2"
  local env2="$3"
  local env3="$4"
  local env4="$5"
  shift 5
  codex mcp remove "$name" >/dev/null 2>&1 || true
  codex mcp add "$name" --env "$env1" --env "$env2" --env "$env3" --env "$env4" -- "$@"
}

add_or_replace_env1() {
  local name="$1"
  local env1="$2"
  shift 2
  codex mcp remove "$name" >/dev/null 2>&1 || true
  codex mcp add "$name" --env "$env1" -- "$@"
}

mkdir -p "${PROJECT_ROOT}/memory"
touch "${PROJECT_ROOT}/memory/memory.sqlite"
touch "${PROJECT_ROOT}/memory/analytics.duckdb"

chmod +x "${PROJECT_ROOT}/mcp/local_ops_server.py" || true
chmod +x "${PROJECT_ROOT}/mcp/network_ops_server.py" || true
chmod +x "${PROJECT_ROOT}/mcp/system_maint_server.py" || true
chmod +x "${PROJECT_ROOT}/mcp/file_ops_server.py" || true
chmod +x "${PROJECT_ROOT}/mcp/n8n_bridge_server.py" || true

# Web / fetch
add_or_replace "fetch" /home/lucy/.local/bin/mcp-server-fetch
add_or_replace "fetch_loose" /home/lucy/.local/bin/mcp-server-fetch --ignore-robots-txt
add_or_replace "fetch_mobile" /home/lucy/.local/bin/mcp-server-fetch --user-agent "Mozilla/5.0 (Android 14; Mobile)"
add_or_replace "fetch_desktop" /home/lucy/.local/bin/mcp-server-fetch --user-agent "Mozilla/5.0 (X11; Linux x86_64)"
add_or_replace "fetch_firefox" /home/lucy/.local/bin/mcp-server-fetch --user-agent "Mozilla/5.0 Firefox/124.0"
add_or_replace "fetch_chrome" /home/lucy/.local/bin/mcp-server-fetch --user-agent "Mozilla/5.0 Chrome/124.0"

# Git scopes
add_or_replace "git_lavieja" /home/lucy/.local/bin/mcp-server-git -r "${PROJECT_ROOT}"
add_or_replace "git_n8n" /home/lucy/.local/bin/mcp-server-git -r "${PROJECT_ROOT}/n8n"
add_or_replace "git_home" /home/lucy/.local/bin/mcp-server-git -r "/home/lucy"
add_or_replace "git_codex" /home/lucy/.local/bin/mcp-server-git -r "/home/lucy/.codex"
add_or_replace "git_desktop" /home/lucy/.local/bin/mcp-server-git -r "/home/lucy/Escritorio"
add_or_replace "git_memories" /home/lucy/.local/bin/mcp-server-git -r "/home/lucy/.codex/memories"
add_or_replace "git_skills" /home/lucy/.local/bin/mcp-server-git -r "/home/lucy/.codex/skills"

# Time
add_or_replace "time_sp" /home/lucy/.local/bin/mcp-server-time --local-timezone "America/Sao_Paulo"
add_or_replace "time_utc" /home/lucy/.local/bin/mcp-server-time --local-timezone "UTC"
add_or_replace "time_ny" /home/lucy/.local/bin/mcp-server-time --local-timezone "America/New_York"
add_or_replace "time_london" /home/lucy/.local/bin/mcp-server-time --local-timezone "Europe/London"
add_or_replace "time_tokyo" /home/lucy/.local/bin/mcp-server-time --local-timezone "Asia/Tokyo"
add_or_replace "time_berlin" /home/lucy/.local/bin/mcp-server-time --local-timezone "Europe/Berlin"
add_or_replace "time_madrid" /home/lucy/.local/bin/mcp-server-time --local-timezone "Europe/Madrid"
add_or_replace "time_mexico" /home/lucy/.local/bin/mcp-server-time --local-timezone "America/Mexico_City"
add_or_replace "time_ba" /home/lucy/.local/bin/mcp-server-time --local-timezone "America/Argentina/Buenos_Aires"
add_or_replace "time_sydney" /home/lucy/.local/bin/mcp-server-time --local-timezone "Australia/Sydney"
add_or_replace "time_singapore" /home/lucy/.local/bin/mcp-server-time --local-timezone "Asia/Singapore"

# SQL/DB
add_or_replace "sqlite_n8n" /home/lucy/.local/bin/mcp-server-sqlite --db-path "${PROJECT_ROOT}/n8n/data/database.sqlite"
add_or_replace "sqlite_memory" /home/lucy/.local/bin/mcp-server-sqlite --db-path "${PROJECT_ROOT}/memory/memory.sqlite"
add_or_replace "sqlite_codex_state" /home/lucy/.local/bin/mcp-server-sqlite --db-path "/home/lucy/.codex/state_5.sqlite"
add_or_replace "sqlite_codex_models_cache" /home/lucy/.local/bin/mcp-server-sqlite --db-path "/home/lucy/.codex/state_5.sqlite"
add_or_replace "duckdb_analytics" /home/lucy/.local/bin/mcp-server-duckdb --db-path "${PROJECT_ROOT}/memory/analytics.duckdb"
add_or_replace "duckdb_analytics_ro" /home/lucy/.local/bin/mcp-server-duckdb --db-path "${PROJECT_ROOT}/memory/analytics.duckdb" --readonly
add_or_replace "duckdb_analytics_keep" /home/lucy/.local/bin/mcp-server-duckdb --db-path "${PROJECT_ROOT}/memory/analytics.duckdb" --keep-connection

# Optional local services
add_or_replace_env "redis_local" "REDIS_HOST=127.0.0.1" "REDIS_PORT=6379" "REDIS_DB=0" "REDIS_PASSWORD=" /home/lucy/.local/bin/mcp-server-redis
add_or_replace "qdrant_local" /home/lucy/.local/bin/mcp-server-qdrant

# External APIs (enabled; require tokens at use time/config)
add_or_replace "notion" /home/lucy/.local/bin/mcp-server-notion
add_or_replace "jira_cloud" /home/lucy/.local/bin/mcp-server-jira --jira-base-url "https://example.atlassian.net"
add_or_replace "sentry_api" /home/lucy/.local/bin/mcp-server-sentry --auth-token "dummy"

# Local custom ops MCP
add_or_replace "local_ops_all" "${PY}" "${PROJECT_ROOT}/mcp/local_ops_server.py" --mode all
add_or_replace "local_ops_memory" "${PY}" "${PROJECT_ROOT}/mcp/local_ops_server.py" --mode memory
add_or_replace "local_ops_n8n" "${PY}" "${PROJECT_ROOT}/mcp/local_ops_server.py" --mode n8n
add_or_replace "local_ops_maintenance" "${PY}" "${PROJECT_ROOT}/mcp/local_ops_server.py" --mode ops
add_or_replace_env1 "local_ops_home" "PROJECT_ROOT=/home/lucy" "${PY}" "${PROJECT_ROOT}/mcp/local_ops_server.py" --mode ops
add_or_replace_env1 "local_ops_codex" "PROJECT_ROOT=/home/lucy/.codex" "${PY}" "${PROJECT_ROOT}/mcp/local_ops_server.py" --mode ops

# Network MCP (custom)
add_or_replace "net_ops_default" "${PY}" "${PROJECT_ROOT}/mcp/network_ops_server.py"
add_or_replace_env1 "net_ops_fast" "NET_TIMEOUT=4" "${PY}" "${PROJECT_ROOT}/mcp/network_ops_server.py"
add_or_replace_env1 "net_ops_deep" "NET_MAX_CHARS=20000" "${PY}" "${PROJECT_ROOT}/mcp/network_ops_server.py"
add_or_replace_env1 "net_ops_slowtimeout" "NET_TIMEOUT=20" "${PY}" "${PROJECT_ROOT}/mcp/network_ops_server.py"

# Maintenance MCP (custom)
add_or_replace "maint_normal" "${PY}" "${PROJECT_ROOT}/mcp/system_maint_server.py"
add_or_replace_env1 "maint_aggressive" "CLEAN_LEVEL=aggressive" "${PY}" "${PROJECT_ROOT}/mcp/system_maint_server.py"
add_or_replace_env1 "maint_home" "PROJECT_ROOT=/home/lucy" "${PY}" "${PROJECT_ROOT}/mcp/system_maint_server.py"

# File MCP (custom)
add_or_replace "file_ops_project" "${PY}" "${PROJECT_ROOT}/mcp/file_ops_server.py"
add_or_replace_env1 "file_ops_n8n" "FILE_OPS_ROOT=${PROJECT_ROOT}/n8n" "${PY}" "${PROJECT_ROOT}/mcp/file_ops_server.py"
add_or_replace_env1 "file_ops_codex" "FILE_OPS_ROOT=/home/lucy/.codex" "${PY}" "${PROJECT_ROOT}/mcp/file_ops_server.py"
add_or_replace_env1 "file_ops_home" "FILE_OPS_ROOT=/home/lucy" "${PY}" "${PROJECT_ROOT}/mcp/file_ops_server.py"

# n8n bridge MCP (custom)
add_or_replace "n8n_bridge" "${PY}" "${PROJECT_ROOT}/mcp/n8n_bridge_server.py"
add_or_replace_env1 "n8n_bridge_project" "PROJECT_ROOT=${PROJECT_ROOT}" "${PY}" "${PROJECT_ROOT}/mcp/n8n_bridge_server.py"
add_or_replace_env1 "n8n_bridge_localhost" "N8N_BASE=http://127.0.0.1:5111" "${PY}" "${PROJECT_ROOT}/mcp/n8n_bridge_server.py"

codex mcp list
