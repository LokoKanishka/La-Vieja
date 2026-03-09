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

signal_ids="$(docker exec btc_postgres psql -U n8n -d n8n -At -c "select signal_id from signals order by ts desc limit ${LIMIT};")"

while IFS= read -r signal_id; do
  [ -z "${signal_id}" ] && continue
  if curl -fsS -X POST "${BASE_URL}/hybrid/decision" \
    -H 'Content-Type: application/json' \
    -d "{\"signal_id\":\"${signal_id}\",\"mode\":\"shadow\",\"ai_source\":\"pending_molbot\",\"ai_model\":\"unset\",\"attach_forecast\":true,\"forecast_horizon_minutes\":10,\"forecast_min_move_bps\":5,\"forecast_timeframe\":\"5m\",\"metadata\":{\"source\":\"hybrid_backfill_shadow\"}}" >/dev/null; then
    ok=$((ok + 1))
  else
    fail=$((fail + 1))
  fi
done <<EOF_IDS
${signal_ids}
EOF_IDS

forecast_eval="$(curl -fsS -X POST "${BASE_URL}/forecast/evaluate-due" -H 'Content-Type: application/json' -d '{"limit":2000,"max_resolution_lag_minutes":240,"persist_events":false}')"
hybrid_score="$(curl -fsS "${BASE_URL}/hybrid/scorecard?lookback_days=14&mode=shadow&horizon_minutes=10&timeframe=5m")"

echo "hybrid_backfill_ok=${ok} hybrid_backfill_fail=${fail}"
printf 'forecast_evaluate_due=%s\n' "${forecast_eval}"
printf 'hybrid_score=%s\n' "${hybrid_score}"
