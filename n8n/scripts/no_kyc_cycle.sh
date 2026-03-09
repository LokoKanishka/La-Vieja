#!/usr/bin/env sh
set -eu

ROOT_DIR="/home/lucy/Escritorio/La Vieja"

"${ROOT_DIR}/n8n/scripts/no_kyc_lockdown.sh" >/dev/null

health="$(curl -fsS http://127.0.0.1:8100/health)"
reconcile="$(curl -fsS -X POST http://127.0.0.1:8100/reconcile -H 'Content-Type: application/json' -d '{}')"
alerts="$(curl -fsS -X POST http://127.0.0.1:8100/alerts/evaluate -H 'Content-Type: application/json' -d '{"persist":true,"include_snapshot":true}')"
intents_reconcile="$(curl -fsS -X POST http://127.0.0.1:8100/execution/intents/reconcile-electrum -H 'Content-Type: application/json' -d '{"limit":25}')"
intents_open="$(curl -fsS 'http://127.0.0.1:8100/execution/intents?status=open&limit=20')"
forecast_due="$(curl -fsS -X POST http://127.0.0.1:8100/forecast/evaluate-due -H 'Content-Type: application/json' -d '{"limit":300,"max_resolution_lag_minutes":20,"persist_events":true}')"
forecast_score="$(curl -fsS 'http://127.0.0.1:8100/forecast/scorecard?lookback_days=7&horizon_minutes=10&timeframe=5m')"
hybrid_score="$(curl -fsS 'http://127.0.0.1:8100/hybrid/scorecard?lookback_days=7&mode=shadow&horizon_minutes=10&timeframe=5m')"
hybrid_alerts="$(curl -fsS -X POST http://127.0.0.1:8100/hybrid/alerts/evaluate -H 'Content-Type: application/json' -d '{"lookback_days":7,"mode":"shadow","horizon_minutes":10,"timeframe":"5m","persist":true,"include_scorecard":false}')"
gonogo="$(curl -fsS -X POST http://127.0.0.1:8100/paper/go-no-go -H 'Content-Type: application/json' -d '{"lookback_days":14,"persist":true,"include_scorecard":true}')"

printf 'health=%s\n' "${health}"
printf 'reconcile=%s\n' "${reconcile}"
printf 'alerts=%s\n' "${alerts}"
printf 'intents_reconcile=%s\n' "${intents_reconcile}"
printf 'intents_open=%s\n' "${intents_open}"
printf 'forecast_due=%s\n' "${forecast_due}"
printf 'forecast_score=%s\n' "${forecast_score}"
printf 'hybrid_score=%s\n' "${hybrid_score}"
printf 'hybrid_alerts=%s\n' "${hybrid_alerts}"
printf 'go_no_go=%s\n' "${gonogo}"
