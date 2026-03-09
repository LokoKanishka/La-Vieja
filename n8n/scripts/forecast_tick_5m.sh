#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8100}"
SYMBOL="${SYMBOL:-BTCUSD}"
TIMEFRAME="${TIMEFRAME:-5m}"
LOOKBACK="${LOOKBACK:-96}"
HORIZON_MINUTES="${1:-10}"
MIN_MOVE_BPS="${2:-5}"

curl -fsS -X POST "${BASE_URL}/features/build" \
  -H 'Content-Type: application/json' \
  -d "{\"symbol\":\"${SYMBOL}\",\"timeframe\":\"${TIMEFRAME}\",\"lookback\":${LOOKBACK}}" >/dev/null

signal_json="$(curl -fsS -X POST "${BASE_URL}/signal/evaluate" \
  -H 'Content-Type: application/json' \
  -d "{\"symbol\":\"${SYMBOL}\"}")"

signal_id="$(printf '%s' "${signal_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("signal_id",""))')"
action="$(printf '%s' "${signal_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("action",""))')"
confidence="$(printf '%s' "${signal_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("confidence",""))')"

forecast_json="$(curl -fsS -X POST "${BASE_URL}/forecast/checkpoint" \
  -H 'Content-Type: application/json' \
  -d "{\"signal_id\":\"${signal_id}\",\"horizon_minutes\":${HORIZON_MINUTES},\"min_move_bps\":${MIN_MOVE_BPS},\"timeframe\":\"${TIMEFRAME}\",\"metadata\":{\"source\":\"forecast_tick_5m_script\"}}")"

due_ts="$(printf '%s' "${forecast_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("due_ts",""))')"
forecast_id="$(printf '%s' "${forecast_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("forecast_id",""))')"

echo "signal_id=${signal_id} action=${action} confidence=${confidence}"
echo "forecast_id=${forecast_id} horizon_minutes=${HORIZON_MINUTES} due_ts=${due_ts}"
echo "ALERTA: accion sugerida ahora -> ${action} (revision objetiva en ${HORIZON_MINUTES} minutos)"

