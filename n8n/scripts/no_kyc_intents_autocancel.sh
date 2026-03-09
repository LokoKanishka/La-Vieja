#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8100}"
ALL="false"
MAX_AGE_MINUTES="120"

if [[ "${1:-}" == "--all" ]]; then
  ALL="true"
elif [[ -n "${1:-}" ]]; then
  MAX_AGE_MINUTES="$1"
fi

if ! [[ "${MAX_AGE_MINUTES}" =~ ^[0-9]+$ ]]; then
  echo "Uso: $0 [max_age_minutes] | $0 --all" >&2
  exit 1
fi

open_json="$(curl -fsS "${BASE_URL}/execution/intents?status=open&limit=200")"

ids="$(python3 -c '
import json
import sys
from datetime import datetime, timezone

all_mode = sys.argv[1].lower() == "true"
max_age = int(sys.argv[2])
data = json.load(sys.stdin)
now = datetime.now(timezone.utc)

for item in data.get("items", []):
    intent_id = item.get("intent_id")
    created_at_raw = item.get("created_at")
    if not intent_id:
        continue
    if all_mode:
        print(intent_id)
        continue
    if not created_at_raw:
        continue
    try:
        created_at = datetime.fromisoformat(str(created_at_raw))
    except Exception:
        continue
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_min = (now - created_at.astimezone(timezone.utc)).total_seconds() / 60.0
    if age_min >= max_age:
        print(intent_id)
' "${ALL}" "${MAX_AGE_MINUTES}" <<<"${open_json}")"

closed=0
for intent_id in ${ids}; do
  curl -fsS -X POST "${BASE_URL}/execution/intent/confirm" \
    -H 'Content-Type: application/json' \
    -d "{\"intent_id\":\"${intent_id}\",\"status\":\"canceled\",\"metadata\":{\"source\":\"auto_cancel\",\"reason\":\"stale_open_intent\"}}" >/dev/null
  closed=$((closed + 1))
done

remaining="$(curl -fsS "${BASE_URL}/execution/intents?status=open&limit=200" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("count",0))')"

echo "autocancel_closed=${closed} remaining_open=${remaining} all_mode=${ALL} max_age_minutes=${MAX_AGE_MINUTES}"
