#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8100}"
SYMBOL="${SYMBOL:-BTCUSD}"
TIMEFRAME="${TIMEFRAME:-5m}"
LOOKBACK="${LOOKBACK:-96}"

curl -fsS -X POST "${BASE_URL}/features/build" \
  -H 'Content-Type: application/json' \
  -d "{\"symbol\":\"${SYMBOL}\",\"timeframe\":\"${TIMEFRAME}\",\"lookback\":${LOOKBACK}}" >/dev/null

signal_json="$(curl -fsS -X POST "${BASE_URL}/signal/evaluate" \
  -H 'Content-Type: application/json' \
  -d "{\"symbol\":\"${SYMBOL}\"}")"

signal_id="$(printf '%s' "${signal_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("signal_id",""))')"
quant_action="$(printf '%s' "${signal_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("action",""))')"
quant_conf="$(printf '%s' "${signal_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("confidence",""))')"

hybrid_json="$(curl -fsS -X POST "${BASE_URL}/hybrid/decision" \
  -H 'Content-Type: application/json' \
  -d "{\"signal_id\":\"${signal_id}\",\"mode\":\"shadow\",\"ai_source\":\"pending_molbot\",\"ai_model\":\"unset\",\"metadata\":{\"source\":\"hybrid_shadow_tick_script\"}}")"

hybrid_action="$(printf '%s' "${hybrid_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("hybrid",{}).get("action",""))')"
hybrid_reason="$(printf '%s' "${hybrid_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("hybrid",{}).get("reason",""))')"
decision_id="$(printf '%s' "${hybrid_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("decision_id",""))')"

echo "signal_id=${signal_id} quant_action=${quant_action} quant_confidence=${quant_conf}"
echo "decision_id=${decision_id} hybrid_action=${hybrid_action} reason=${hybrid_reason}"
echo "MODO SHADOW: no ejecuta orden; solo registra decision híbrida."

