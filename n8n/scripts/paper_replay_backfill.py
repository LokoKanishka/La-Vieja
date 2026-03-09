#!/usr/bin/env python3
import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


INTERVAL_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
}


def http_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    body = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = Request(url=url, data=body, method=method, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        raise RuntimeError(f"{method} {url} -> HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"{method} {url} -> URL error: {exc.reason}") from exc
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{method} {url} -> invalid JSON: {raw[:200]}") from exc
    if isinstance(data, dict) and data.get("detail"):
        raise RuntimeError(f"{method} {url} -> detail: {data['detail']}")
    return data if isinstance(data, dict) else {"data": data}


def fetch_binance_klines(symbol: str, interval: str, start_ms: int, end_ms: int, limit: int = 1000) -> list[list[Any]]:
    q = urlencode(
        {
            "symbol": symbol,
            "interval": interval,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": limit,
        }
    )
    url = f"https://api.binance.com/api/v3/klines?{q}"
    req = Request(url=url, method="GET")
    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as exc:
        raise RuntimeError(f"Binance fetch failed: {exc}") from exc
    data = json.loads(raw)
    if not isinstance(data, list):
        raise RuntimeError(f"Binance unexpected response: {data}")
    return data


def collect_klines(symbol: str, interval: str, start_ms: int, end_ms: int) -> list[list[Any]]:
    step = INTERVAL_MS[interval]
    cur = start_ms
    out: list[list[Any]] = []
    while cur < end_ms:
        batch = fetch_binance_klines(symbol, interval, cur, end_ms, limit=1000)
        if not batch:
            break
        out.extend(batch)
        last_open = int(batch[-1][0])
        nxt = last_open + step
        if nxt <= cur:
            break
        cur = nxt
        time.sleep(0.05)
    # Deduplicate by open time and clip window.
    uniq: dict[int, list[Any]] = {}
    for k in out:
        ts = int(k[0])
        if start_ms <= ts <= end_ms:
            uniq[ts] = k
    return [uniq[k] for k in sorted(uniq.keys())]


def iso_utc_from_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat()


def main() -> int:
    ap = argparse.ArgumentParser(description="Replay paper trading over historical Binance candles.")
    ap.add_argument("--strategy-url", default="http://127.0.0.1:8100")
    ap.add_argument("--source-symbol", default="BTCUSDT")
    ap.add_argument("--target-symbol", default="BTCUSD")
    ap.add_argument("--interval", default="15m", choices=sorted(INTERVAL_MS.keys()))
    ap.add_argument("--days", type=int, default=21)
    ap.add_argument("--end-offset-minutes", type=int, default=20)
    ap.add_argument("--lookback", type=int, default=96)
    ap.add_argument("--build-every", type=int, default=1, help="Build features/signal every N candles")
    ap.add_argument("--reconcile-every", type=int, default=12)
    ap.add_argument("--max-candles", type=int, default=0, help="0 = no cap")
    ap.add_argument("--persist-go-no-go", action="store_true")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    end_ts = now - timedelta(minutes=max(0, args.end_offset_minutes))
    start_ts = end_ts - timedelta(days=max(1, args.days))
    start_ms = int(start_ts.timestamp() * 1000)
    end_ms = int(end_ts.timestamp() * 1000)

    print(f"[replay] collecting {args.source_symbol} {args.interval} from {start_ts.isoformat()} to {end_ts.isoformat()}")
    klines = collect_klines(args.source_symbol, args.interval, start_ms, end_ms)
    if args.max_candles > 0:
        klines = klines[-args.max_candles :]
    if len(klines) < args.lookback:
        print(f"[replay] insufficient candles: {len(klines)} < lookback {args.lookback}", file=sys.stderr)
        return 2

    print(f"[replay] candles loaded: {len(klines)}")
    base = args.strategy_url.rstrip("/")
    ingested = 0
    built = 0
    signals = 0
    executable_signals = 0
    orders_ok = 0
    orders_rejected = 0
    errors = 0

    for idx, k in enumerate(klines):
        ts_ms = int(k[0])
        payload = {
            "source": "binance_replay",
            "symbol": args.target_symbol,
            "timeframe": args.interval,
            "ts": iso_utc_from_ms(ts_ms),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "raw": {"source_symbol": args.source_symbol, "open_time_ms": ts_ms},
        }
        try:
            http_json("POST", f"{base}/ingest/market", payload)
            ingested += 1
        except Exception as exc:
            errors += 1
            if errors <= 10:
                print(f"[replay] ingest error idx={idx}: {exc}", file=sys.stderr)
            continue

        if (idx + 1) < args.lookback:
            continue
        if args.build_every > 1 and (idx + 1) % args.build_every != 0:
            continue

        try:
            http_json(
                "POST",
                f"{base}/features/build",
                {"symbol": args.target_symbol, "timeframe": args.interval, "lookback": args.lookback},
            )
            built += 1
            sig = http_json(
                "POST",
                f"{base}/signal/evaluate",
                {"symbol": args.target_symbol, "feature_set_version": "v1"},
            )
            signals += 1
        except Exception as exc:
            errors += 1
            if errors <= 10:
                print(f"[replay] feature/signal error idx={idx}: {exc}", file=sys.stderr)
            continue

        action = str(sig.get("action", "hold"))
        signal_id = str(sig.get("signal_id", ""))
        if action in {"buy", "sell"} and signal_id:
            executable_signals += 1
            try:
                order = http_json(
                    "POST",
                    f"{base}/execution/order",
                    {"signal_id": signal_id, "order_type": "market"},
                )
                if bool(order.get("ok", False)):
                    orders_ok += 1
                else:
                    orders_rejected += 1
            except Exception as exc:
                errors += 1
                if errors <= 10:
                    print(f"[replay] order error idx={idx}: {exc}", file=sys.stderr)

        if args.reconcile_every > 0 and built % args.reconcile_every == 0:
            try:
                http_json("POST", f"{base}/reconcile", {})
            except Exception as exc:
                errors += 1
                if errors <= 10:
                    print(f"[replay] reconcile error idx={idx}: {exc}", file=sys.stderr)

    try:
        go_no_go = http_json(
            "POST",
            f"{base}/paper/go-no-go",
            {"lookback_days": 14, "persist": bool(args.persist_go_no_go), "include_scorecard": True},
        )
    except Exception as exc:
        print(f"[replay] go/no-go error: {exc}", file=sys.stderr)
        go_no_go = {}

    print("[replay] done")
    print(
        json.dumps(
            {
                "ingested": ingested,
                "features_built": built,
                "signals": signals,
                "executable_signals": executable_signals,
                "orders_ok": orders_ok,
                "orders_rejected": orders_rejected,
                "errors": errors,
                "go_no_go_decision": go_no_go.get("decision"),
                "failed_criteria": go_no_go.get("failed_criteria"),
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
