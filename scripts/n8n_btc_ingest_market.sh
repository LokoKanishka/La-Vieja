#!/usr/bin/env sh
set -eu

base_url="${STRATEGY_BASE_URL:-http://strategy_service:8100}"

python3 - "$base_url" <<'PY'
import json
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen

base_url = sys.argv[1].rstrip("/")

def get_json(url: str):
    req = Request(url, method="GET")
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

def post_json(url: str, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

cg = get_json("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_vol=true&include_last_updated_at=true")
btc = cg.get("bitcoin", {})
price = float(btc.get("usd"))
vol24h = float(btc.get("usd_24h_vol", 0.0))
ts = datetime.now(timezone.utc).isoformat()

market_payload = {
    "source": "coingecko",
    "symbol": "BTCUSD",
    "timeframe": "5m",
    "ts": ts,
    "open": price,
    "high": price,
    "low": price,
    "close": price,
    "volume": vol24h,
    "raw": cg,
}
market_res = post_json(f"{base_url}/ingest/market", market_payload)

fees = get_json("https://mempool.space/api/v1/fees/recommended")
metrics = []
for key in ("fastestFee", "halfHourFee", "hourFee"):
    if key not in fees:
        continue
    value = float(fees[key])
    res = post_json(
        f"{base_url}/ingest/onchain",
        {
            "source": "mempool",
            "metric": f"mempool_{key}",
            "value": value,
            "ts": ts,
            "raw": fees,
        },
    )
    metrics.append(res)

print(json.dumps({"ok": True, "market": market_res, "onchain_metrics": metrics}))
PY
