#!/usr/bin/env bash
set -euo pipefail

base="${1:-http://127.0.0.1:5111}"
base="${base%/}"
db="/home/lucy/Escritorio/La Vieja/n8n/data/database.sqlite"

# Trading stack (Postgres): build webhook URLs from active workflows.
if docker ps --format '{{.Names}}' | grep -qx 'btc_postgres'; then
  if docker exec btc_postgres psql -U n8n -d n8n -At -c "select 1" >/dev/null 2>&1; then
    docker exec btc_postgres psql -U n8n -d n8n -At -F $'\t' -c "
      select
        w.id,
        coalesce(upper(n->'parameters'->>'httpMethod'), 'GET') as method,
        n->>'name' as node_name,
        n->'parameters'->>'path' as path
      from workflow_entity w
      cross join lateral json_array_elements(w.nodes) as n
      where w.active = true
        and n->>'type' = 'n8n-nodes-base.webhook'
      order by method, path;
    " | while IFS=$'\t' read -r wid method node_name path; do
      if [[ -n "${wid}" && -n "${node_name}" && -n "${path}" ]]; then
        echo "${method} ${base}/webhook/${wid}/${node_name}/${path}"
      fi
    done
    exit 0
  fi
fi

# Local stack (SQLite legacy fallback).
python3 - "$base" "$db" <<'PY'
import sqlite3, sys
base = sys.argv[1]
db = sys.argv[2]
con = sqlite3.connect(db)
cur = con.cursor()
rows = cur.execute(
    "select method, webhookPath from webhook_entity order by method, webhookPath"
).fetchall()
for method, path in rows:
    print(f"{method} {base}/webhook/{path}")
PY
