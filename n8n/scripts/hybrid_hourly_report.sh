#!/usr/bin/env sh
set -eu

BASE_URL="${BASE_URL:-http://127.0.0.1:8100}"

hybrid_score="$(curl -fsS "${BASE_URL}/hybrid/scorecard?lookback_days=7&mode=shadow&horizon_minutes=10&timeframe=5m")"
hybrid_alerts="$(curl -fsS -X POST "${BASE_URL}/hybrid/alerts/evaluate" -H 'Content-Type: application/json' -d '{"lookback_days":7,"mode":"shadow","horizon_minutes":10,"timeframe":"5m","persist":true,"include_scorecard":true}')"
forecast_score="$(curl -fsS "${BASE_URL}/forecast/scorecard?lookback_days=7&horizon_minutes=10&timeframe=5m")"

printf 'hybrid_score=%s\n' "${hybrid_score}"
printf 'hybrid_alerts=%s\n' "${hybrid_alerts}"
printf 'forecast_score=%s\n' "${forecast_score}"
