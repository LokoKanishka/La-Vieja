#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/lucy/Escritorio/La Vieja"
cd "${ROOT_DIR}"

ENV_FILE="n8n/.env.trading"
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "BLOCKED: falta ${ENV_FILE}"
  exit 1
fi

env_get() {
  local key="$1"
  local line
  line="$(grep -E "^${key}=" "${ENV_FILE}" | tail -n 1 || true)"
  printf '%s' "${line#*=}"
}

TRADING_MODE_V="$(env_get TRADING_MODE)"
EXCHANGE_ADAPTER_V="$(env_get EXCHANGE_ADAPTER)"
EXCHANGE_API_KEY_V="$(env_get EXCHANGE_API_KEY)"
EXCHANGE_API_SECRET_V="$(env_get EXCHANGE_API_SECRET)"
EXCHANGE_SANDBOX_V="$(env_get EXCHANGE_SANDBOX)"

fail=0
warn=0

check_ok() {
  echo "OK: $1"
}

check_warn() {
  echo "WARN: $1"
  warn=$((warn + 1))
}

check_blocked() {
  echo "BLOCKED: $1"
  fail=$((fail + 1))
}

if docker ps --format '{{.Names}}' | grep -qx 'btc_strategy_service'; then
  check_ok "btc_strategy_service activo"
else
  check_blocked "btc_strategy_service no activo"
fi

if docker ps --format '{{.Names}}' | grep -qx 'n8n_trading'; then
  check_ok "n8n_trading activo"
else
  check_blocked "n8n_trading no activo"
fi

if docker ps --format '{{.Names}}' | grep -qx 'btc_postgres'; then
  check_ok "btc_postgres activo"
else
  check_blocked "btc_postgres no activo"
fi

if curl -fsS http://127.0.0.1:8100/health >/dev/null; then
  check_ok "health strategy_service responde"
else
  check_blocked "health strategy_service no responde"
fi

go_json="$(curl -fsS -X POST http://127.0.0.1:8100/paper/go-no-go -H 'Content-Type: application/json' -d '{"lookback_days":14,"persist":false}')"
go_decision="$(printf '%s' "${go_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("decision",""))')"
if [[ "${go_decision}" == "go" ]]; then
  check_ok "paper go/no-go = GO"
else
  check_blocked "paper go/no-go != GO (${go_decision})"
fi

if [[ "${TRADING_MODE_V:-paper}" == "paper" ]]; then
  check_ok "TRADING_MODE en paper (esperado antes de live)"
else
  check_warn "TRADING_MODE no esta en paper"
fi

if [[ "${EXCHANGE_ADAPTER_V:-}" == "ccxt" ]]; then
  check_ok "EXCHANGE_ADAPTER=ccxt"
else
  check_blocked "EXCHANGE_ADAPTER debe ser ccxt para pre-live real"
fi

if [[ -n "${EXCHANGE_API_KEY_V:-}" && -n "${EXCHANGE_API_SECRET_V:-}" ]]; then
  check_ok "Credenciales de exchange presentes"
else
  check_blocked "Faltan EXCHANGE_API_KEY/EXCHANGE_API_SECRET"
fi

if [[ "${EXCHANGE_SANDBOX_V:-false}" == "true" ]]; then
  check_ok "EXCHANGE_SANDBOX=true"
else
  check_warn "EXCHANGE_SANDBOX no esta en true"
fi

echo "----"
echo "Resumen: blocked=${fail} warn=${warn}"
if [[ "${fail}" -gt 0 ]]; then
  exit 2
fi
exit 0
