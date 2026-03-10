#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/lucy/Escritorio/La Vieja"
BASE_URL="${BASE_URL:-http://127.0.0.1:8100}"
LOG_DIR="${ROOT_DIR}/n8n/logs"
LOCK_DIR="/tmp/no_kyc_guardian.lock"
MODE="${1:-}"

mkdir -p "${LOG_DIR}"

if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  echo "skip: guardian already running"
  exit 0
fi

cleanup() {
  rmdir "${LOCK_DIR}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

timestamp() {
  date +"%Y-%m-%d %H:%M:%S"
}

containers_up() {
  local missing=0
  local name
  for name in btc_strategy_service n8n_trading btc_postgres; do
    if ! docker ps --format '{{.Names}}' | grep -qx "${name}"; then
      missing=1
    fi
  done
  return "${missing}"
}

wait_health() {
  local i
  for i in $(seq 1 45); do
    if curl -fsS "${BASE_URL}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

echo "[$(timestamp)] guardian start mode=${MODE:-cron}"

if [ "${MODE}" = "--boot" ]; then
  bash "${ROOT_DIR}/n8n/scripts/no_kyc_lockdown.sh" >/dev/null
fi

if ! containers_up; then
  echo "[$(timestamp)] containers down, starting trading stack"
  sh "${ROOT_DIR}/n8n/scripts/trading_up.sh" >/dev/null
fi

if ! wait_health; then
  echo "[$(timestamp)] health down, applying lockdown recovery"
  bash "${ROOT_DIR}/n8n/scripts/no_kyc_lockdown.sh" >/dev/null
fi

if NO_KYC_SKIP_LOCKDOWN=1 BASE_URL="${BASE_URL}" sh "${ROOT_DIR}/n8n/scripts/no_kyc_cycle.sh"; then
  echo "[$(timestamp)] cycle ok"
  exit 0
fi

echo "[$(timestamp)] cycle failed, retrying after lockdown"
bash "${ROOT_DIR}/n8n/scripts/no_kyc_lockdown.sh" >/dev/null
NO_KYC_SKIP_LOCKDOWN=1 BASE_URL="${BASE_URL}" sh "${ROOT_DIR}/n8n/scripts/no_kyc_cycle.sh"
echo "[$(timestamp)] cycle recovered"
