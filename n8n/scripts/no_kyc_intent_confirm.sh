#!/usr/bin/env sh
set -eu

if [ "$#" -lt 2 ]; then
  echo "Uso: $0 <intent_id> <filled|rejected|canceled> [fill_price] [filled_qty] [txid]" >&2
  exit 1
fi

INTENT_ID="$1"
STATUS="$2"
FILL_PRICE="${3:-}"
FILLED_QTY="${4:-}"
TXID="${5:-}"

payload='{"intent_id":"'"${INTENT_ID}"'","status":"'"${STATUS}"'","metadata":{"source":"manual_cli_confirm"}}'

if [ "${STATUS}" = "filled" ]; then
  if [ -n "${FILL_PRICE}" ]; then
    payload="$(printf '%s' "${payload}" | sed 's/}$/,"fill_price":'"${FILL_PRICE}"'}/')"
  fi
  if [ -n "${FILLED_QTY}" ]; then
    payload="$(printf '%s' "${payload}" | sed 's/}$/,"filled_qty":'"${FILLED_QTY}"'}/')"
  fi
fi

if [ -n "${TXID}" ]; then
  payload="$(printf '%s' "${payload}" | sed 's/}$/,"txid":"'"${TXID}"'"}/')"
fi

curl -fsS -X POST http://127.0.0.1:8100/execution/intent/confirm \
  -H 'Content-Type: application/json' \
  -d "${payload}"
echo
