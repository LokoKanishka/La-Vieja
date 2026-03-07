#!/usr/bin/env bash
set -euo pipefail

# Configura MCPs cloud solo si existen variables de entorno requeridas.
# No rompe si faltan credenciales: simplemente salta.

add_or_replace() {
  local name="$1"
  shift
  codex mcp remove "$name" >/dev/null 2>&1 || true
  codex mcp add "$name" -- "$@"
}

if [[ -n "${NOTION_TOKEN:-}" ]]; then
  add_or_replace "notion_cloud" /home/lucy/.local/bin/mcp-server-notion
fi

if [[ -n "${JIRA_BASE_URL:-}" ]]; then
  args=(/home/lucy/.local/bin/mcp-server-jira --jira-base-url "${JIRA_BASE_URL}")
  if [[ -n "${JIRA_TOKEN:-}" ]]; then
    args+=(--jira-token "${JIRA_TOKEN}")
  fi
  add_or_replace "jira_cloud_real" "${args[@]}"
fi

if [[ -n "${SENTRY_AUTH_TOKEN:-}" ]]; then
  add_or_replace "sentry_cloud_real" /home/lucy/.local/bin/mcp-server-sentry --auth-token "${SENTRY_AUTH_TOKEN}"
fi

if [[ -n "${BRAVE_API_KEY:-}" ]]; then
  # El paquete brave-search de esta version no expone binario directo estable.
  # Reservado para una version futura / wrapper custom.
  echo "BRAVE_API_KEY detectado, pero mcp-server-brave-search no tiene launcher CLI util en esta build."
fi

codex mcp list

