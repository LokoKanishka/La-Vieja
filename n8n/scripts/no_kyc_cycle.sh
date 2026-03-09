#!/usr/bin/env sh
set -eu

ROOT_DIR="/home/lucy/Escritorio/La Vieja"

"${ROOT_DIR}/n8n/scripts/no_kyc_lockdown.sh" >/dev/null

health="$(curl -fsS http://127.0.0.1:8100/health)"
reconcile="$(curl -fsS -X POST http://127.0.0.1:8100/reconcile -H 'Content-Type: application/json' -d '{}')"
alerts="$(curl -fsS -X POST http://127.0.0.1:8100/alerts/evaluate -H 'Content-Type: application/json' -d '{"persist":true,"include_snapshot":true}')"
gonogo="$(curl -fsS -X POST http://127.0.0.1:8100/paper/go-no-go -H 'Content-Type: application/json' -d '{"lookback_days":14,"persist":true,"include_scorecard":true}')"

printf 'health=%s\n' "${health}"
printf 'reconcile=%s\n' "${reconcile}"
printf 'alerts=%s\n' "${alerts}"
printf 'go_no_go=%s\n' "${gonogo}"
