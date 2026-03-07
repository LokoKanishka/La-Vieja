#!/usr/bin/env sh
set -eu

base_url="${STRATEGY_BASE_URL:-http://strategy_service:8100}"
min_sweep_btc="${1:-0.01}"

python3 - "$base_url" "$min_sweep_btc" <<'PY'
import json
import sys
from urllib.request import Request, urlopen

base_url = sys.argv[1].rstrip("/")
min_sweep_btc = float(sys.argv[2])

payload = {"min_sweep_btc": min_sweep_btc}
body = json.dumps(payload).encode("utf-8")
req = Request(f"{base_url}/custody/sweep", data=body, method="POST")
req.add_header("Content-Type", "application/json")
with urlopen(req, timeout=20) as resp:
    out = json.loads(resp.read().decode("utf-8"))
print(json.dumps(out))
PY
