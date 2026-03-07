#!/usr/bin/env sh
set -eu

base_url="${STRATEGY_BASE_URL:-http://strategy_service:8100}"
symbol="${1:-BTCUSD}"

python3 - "$base_url" "$symbol" <<'PY'
import json
import sys
from urllib.request import Request, urlopen

base_url = sys.argv[1].rstrip("/")
symbol = sys.argv[2]

def post(url: str, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

signal = post(f"{base_url}/signal/evaluate", {"symbol": symbol})

execution = {
    "ok": True,
    "status": "skipped",
    "reason": "signal_hold",
}
if signal.get("action") in {"buy", "sell"}:
    execution = post(f"{base_url}/execution/order", {"signal_id": signal["signal_id"], "order_type": "market"})

print(json.dumps({"ok": True, "signal": signal, "execution": execution}))
PY
