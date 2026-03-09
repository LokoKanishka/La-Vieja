#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/lucy/Escritorio/La Vieja"
BASE_URL="${BASE_URL:-http://127.0.0.1:8100}"
LIMIT="${1:-120}"

if ! [[ "${LIMIT}" =~ ^[0-9]+$ ]]; then
  echo "Uso: $0 [limit_signals]" >&2
  exit 1
fi

cd "${ROOT_DIR}"

ok=0
fail=0

signal_rows="$(docker exec btc_postgres psql -U n8n -d n8n -At -F $'\t' -c "
select signal_id, symbol, action, confidence
from (
  select distinct on (symbol, ts, strategy_version)
    signal_id, symbol, action, confidence, ts
  from signals
  order by symbol, ts, strategy_version, created_at desc, signal_id desc
) s
order by ts desc
limit ${LIMIT};
")"

while IFS=$'\t' read -r signal_id symbol quant_action quant_confidence; do
  [ -z "${signal_id}" ] && continue
  [ -z "${symbol}" ] && symbol="BTCUSD"
  [ -z "${quant_action}" ] && quant_action="hold"
  [ -z "${quant_confidence}" ] && quant_confidence="0"

  ai_payload="$(curl -fsS -X POST "${BASE_URL}/hybrid/ai/fallback" \
    -H 'Content-Type: application/json' \
    -d "{\"signal_id\":\"${signal_id}\",\"symbol\":\"${symbol}\",\"quant_action\":\"${quant_action}\",\"quant_confidence\":${quant_confidence},\"reason\":\"hybrid_backfill_shadow\"}" || true)"
  if [ -z "${ai_payload}" ]; then
    fail=$((fail + 1))
    continue
  fi

  ai_action="$(printf '%s' "${ai_payload}" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("ai_action","hold"))' 2>/dev/null || printf 'hold')"
  ai_confidence="$(printf '%s' "${ai_payload}" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("ai_confidence",0.0))' 2>/dev/null || printf '0')"
  ai_reason="$(printf '%s' "${ai_payload}" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("ai_reason","fallback"))' 2>/dev/null || printf 'fallback')"
  ai_model="$(printf '%s' "${ai_payload}" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("ai_model","strategy_fallback_rule"))' 2>/dev/null || printf 'strategy_fallback_rule')"
  ai_source="$(printf '%s' "${ai_payload}" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("ai_source","strategy_fallback"))' 2>/dev/null || printf 'strategy_fallback')"

  if curl -fsS -X POST "${BASE_URL}/hybrid/decision" \
    -H 'Content-Type: application/json' \
    -d "{\"signal_id\":\"${signal_id}\",\"mode\":\"shadow\",\"ai_action\":\"${ai_action}\",\"ai_confidence\":${ai_confidence},\"ai_reason\":\"${ai_reason}\",\"ai_model\":\"${ai_model}\",\"ai_source\":\"${ai_source}\",\"attach_forecast\":true,\"forecast_horizon_minutes\":10,\"forecast_min_move_bps\":5,\"forecast_timeframe\":\"5m\",\"metadata\":{\"source\":\"hybrid_backfill_shadow\"}}" >/dev/null; then
      ok=$((ok + 1))
    else
      fail=$((fail + 1))
    fi
done <<EOF_IDS
${signal_rows}
EOF_IDS

forecast_eval="$(curl -fsS -X POST "${BASE_URL}/forecast/evaluate-due" -H 'Content-Type: application/json' -d '{"limit":2000,"max_resolution_lag_minutes":240,"persist_events":false}')"
hybrid_score="$(curl -fsS "${BASE_URL}/hybrid/scorecard?lookback_days=14&mode=shadow&horizon_minutes=10&timeframe=5m")"

echo "hybrid_backfill_ok=${ok} hybrid_backfill_fail=${fail}"
printf 'forecast_evaluate_due=%s\n' "${forecast_eval}"
printf 'hybrid_score=%s\n' "${hybrid_score}"
