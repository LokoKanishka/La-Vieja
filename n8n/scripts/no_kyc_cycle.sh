#!/usr/bin/env sh
set -eu

ROOT_DIR="/home/lucy/Escritorio/La Vieja"
BASE_URL="${BASE_URL:-http://127.0.0.1:8100}"
NO_KYC_SYMBOL="${NO_KYC_SYMBOL:-BTCUSD}"
NO_KYC_TIMEFRAME="${NO_KYC_TIMEFRAME:-5m}"
NO_KYC_FEATURE_LOOKBACK="${NO_KYC_FEATURE_LOOKBACK:-96}"

if [ "${NO_KYC_SKIP_LOCKDOWN:-0}" != "1" ]; then
  "${ROOT_DIR}/n8n/scripts/no_kyc_lockdown.sh" >/dev/null
fi

features_build="$(curl -fsS -X POST "${BASE_URL}/features/build" -H 'Content-Type: application/json' -d "{\"symbol\":\"${NO_KYC_SYMBOL}\",\"timeframe\":\"${NO_KYC_TIMEFRAME}\",\"lookback\":${NO_KYC_FEATURE_LOOKBACK}}")"
health="$(curl -fsS "${BASE_URL}/health")"
reconcile="$(curl -fsS -X POST "${BASE_URL}/reconcile" -H 'Content-Type: application/json' -d '{}')"
alerts="$(curl -fsS -X POST "${BASE_URL}/alerts/evaluate" -H 'Content-Type: application/json' -d '{"persist":true,"include_snapshot":true}')"
intents_reconcile="$(curl -fsS -X POST "${BASE_URL}/execution/intents/reconcile-electrum" -H 'Content-Type: application/json' -d '{"limit":25}')"
intents_open="$(curl -fsS "${BASE_URL}/execution/intents?status=open&limit=20")"
forecast_due="$(curl -fsS -X POST "${BASE_URL}/forecast/evaluate-due" -H 'Content-Type: application/json' -d '{"limit":300,"max_resolution_lag_minutes":20,"persist_events":true}')"
forecast_score="$(curl -fsS "${BASE_URL}/forecast/scorecard?lookback_days=7&horizon_minutes=10&timeframe=5m")"
hybrid_score="$(curl -fsS "${BASE_URL}/hybrid/scorecard?lookback_days=7&mode=shadow&horizon_minutes=10&timeframe=5m")"
hybrid_alerts="$(curl -fsS -X POST "${BASE_URL}/hybrid/alerts/evaluate" -H 'Content-Type: application/json' -d '{"lookback_days":7,"mode":"shadow","horizon_minutes":10,"timeframe":"5m","persist":true,"include_scorecard":false}')"
gonogo="$(curl -fsS -X POST "${BASE_URL}/paper/go-no-go" -H 'Content-Type: application/json' -d '{"lookback_days":14,"persist":true,"include_scorecard":true}')"

printf 'features_build=%s\n' "${features_build}"
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
