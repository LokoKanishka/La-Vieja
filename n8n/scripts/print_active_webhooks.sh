#!/usr/bin/env bash
set -euo pipefail

base="${1:-http://127.0.0.1:5111}"
db="/home/lucy/Escritorio/La Vieja/n8n/data/database.sqlite"

python3 - "$base" "$db" <<'PY'
import sqlite3, sys
base=sys.argv[1].rstrip("/")
db=sys.argv[2]
con=sqlite3.connect(db)
cur=con.cursor()
rows=cur.execute(
    "select method, webhookPath from webhook_entity where webhookPath like '%memory/%' order by method, webhookPath"
).fetchall()
for method,path in rows:
    print(f"{method} {base}/webhook/{path}")
PY

