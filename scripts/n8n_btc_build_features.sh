#!/usr/bin/env sh
set -eu

base_url="${STRATEGY_BASE_URL:-http://strategy_service:8100}"
symbol="${1:-BTCUSD}"
timeframe="${2:-5m}"
lookback="${3:-96}"

python3 - "$base_url" "$symbol" "$timeframe" "$lookback" <<'PY'
import json
import sys
from urllib.request import Request, urlopen

base_url = sys.argv[1].rstrip("/")
symbol = sys.argv[2]
timeframe = sys.argv[3]
lookback = int(sys.argv[4])

payload = {
    "symbol": symbol,
    "timeframe": timeframe,
    "lookback": lookback,
}
body = json.dumps(payload).encode("utf-8")
req = Request(f"{base_url}/features/build", data=body, method="POST")
req.add_header("Content-Type", "application/json")
with urlopen(req, timeout=20) as resp:
    out = json.loads(resp.read().decode("utf-8"))
print(json.dumps(out))
PY
