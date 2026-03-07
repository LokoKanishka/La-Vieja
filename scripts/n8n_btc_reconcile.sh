#!/usr/bin/env sh
set -eu

base_url="${STRATEGY_BASE_URL:-http://strategy_service:8100}"

python3 - "$base_url" <<'PY'
import json
import sys
from urllib.request import Request, urlopen

base_url = sys.argv[1].rstrip("/")
body = b"{}"
req = Request(f"{base_url}/reconcile", data=body, method="POST")
req.add_header("Content-Type", "application/json")
with urlopen(req, timeout=20) as resp:
    out = json.loads(resp.read().decode("utf-8"))
print(json.dumps(out))
PY
