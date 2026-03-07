import base64
import json
import os
import uuid
from datetime import datetime, timezone
from statistics import pstdev
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

try:
    import ccxt  # type: ignore
except Exception:  # pragma: no cover - optional dependency at runtime
    ccxt = None


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://n8n:n8n@postgres:5432/n8n")
TRADING_MODE = os.getenv("TRADING_MODE", "paper").lower()
FEATURE_SET_VERSION = os.getenv("FEATURE_SET_VERSION", "v1")
PAPER_EQUITY_USD = float(os.getenv("PAPER_EQUITY_USD", "10000"))
MAX_POSITION_PCT = float(os.getenv("MAX_POSITION_PCT", "0.20"))
MAX_ORDERS_PER_HOUR = int(os.getenv("MAX_ORDERS_PER_HOUR", "12"))
DAILY_LOSS_LIMIT_USD = float(os.getenv("DAILY_LOSS_LIMIT_USD", "300"))
TAKER_FEE_BPS = float(os.getenv("TAKER_FEE_BPS", "10"))
VOLATILITY_CUTOFF = float(os.getenv("VOLATILITY_CUTOFF", "0.08"))

EXCHANGE_ADAPTER = os.getenv("EXCHANGE_ADAPTER", "paper").lower()
EXCHANGE_ID = os.getenv("EXCHANGE_ID", "kraken")
EXCHANGE_API_KEY = os.getenv("EXCHANGE_API_KEY", "")
EXCHANGE_API_SECRET = os.getenv("EXCHANGE_API_SECRET", "")
EXCHANGE_API_PASSPHRASE = os.getenv("EXCHANGE_API_PASSPHRASE", "")
EXCHANGE_SYMBOL = os.getenv("EXCHANGE_SYMBOL", "BTC/USD")
LIVE_ORDER_TYPE = os.getenv("LIVE_ORDER_TYPE", "market")
EXCHANGE_SANDBOX = os.getenv("EXCHANGE_SANDBOX", "false").lower() == "true"

ENABLE_ELECTRUM_RPC = os.getenv("ENABLE_ELECTRUM_RPC", "false").lower() == "true"
ELECTRUM_RPC_URL = os.getenv("ELECTRUM_RPC_URL", "http://127.0.0.1:7777")
ELECTRUM_RPC_USER = os.getenv("ELECTRUM_RPC_USER", "")
ELECTRUM_RPC_PASSWORD = os.getenv("ELECTRUM_RPC_PASSWORD", "")


app = FastAPI(title="btc-strategy-service", version="1.0.0")


class MarketIngestRequest(BaseModel):
    source: str = "coingecko"
    symbol: str = "BTCUSD"
    timeframe: str = "5m"
    ts: datetime | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    volume: float = 0.0
    raw: dict[str, Any] = Field(default_factory=dict)


class OnchainIngestRequest(BaseModel):
    source: str
    metric: str
    value: float
    ts: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class FeatureBuildRequest(BaseModel):
    symbol: str = "BTCUSD"
    timeframe: str = "5m"
    lookback: int = 96


class SignalEvaluateRequest(BaseModel):
    symbol: str = "BTCUSD"
    feature_set_version: str = FEATURE_SET_VERSION


class RiskCheckRequest(BaseModel):
    signal_id: str | None = None
    symbol: str = "BTCUSD"
    action: str | None = None
    target_notional_usd: float | None = None


class ExecutionOrderRequest(BaseModel):
    signal_id: str
    order_type: str = "market"


class SweepRequest(BaseModel):
    min_sweep_btc: float = 0.01


class ElectrumRpcRequest(BaseModel):
    method: str
    params: list[Any] = Field(default_factory=list)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_conn() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def latest_price(cur: psycopg.Cursor, symbol: str) -> float:
    cur.execute(
        """
        select close
        from market_candles
        where symbol = %s
        order by ts desc
        limit 1
        """,
        (symbol,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=409, detail="No hay precio reciente en market_candles")
    return float(row["close"])


def evaluate_risk(cur: psycopg.Cursor, symbol: str, action: str, target_notional: float) -> dict[str, Any]:
    action = (action or "hold").lower()
    reasons: list[str] = []

    if action not in {"buy", "sell", "hold"}:
        reasons.append("accion_invalida")

    if action == "hold":
        reasons.append("accion_hold_no_ejecutable")

    if target_notional <= 0:
        reasons.append("notional_no_positivo")

    cur.execute(
        """
        select count(*) as c
        from orders
        where created_at >= now() - interval '1 hour'
          and status in ('submitted', 'open', 'partially_filled', 'filled')
        """
    )
    hourly_orders = int(cur.fetchone()["c"])
    if hourly_orders >= MAX_ORDERS_PER_HOUR:
        reasons.append("max_orders_per_hour_excedido")

    px = latest_price(cur, symbol)
    cur.execute("select qty from positions where symbol = %s", (symbol,))
    pos = cur.fetchone()
    position_qty = float(pos["qty"]) if pos else 0.0
    current_notional = position_qty * px

    max_position_usd = PAPER_EQUITY_USD * MAX_POSITION_PCT
    if action == "buy" and (current_notional + target_notional) > max_position_usd:
        reasons.append("max_position_pct_excedido")

    cur.execute("select coalesce(sum(fee), 0) as fees from fills where ts::date = current_date")
    daily_fees = float(cur.fetchone()["fees"])
    if daily_fees >= DAILY_LOSS_LIMIT_USD:
        reasons.append("daily_loss_limit_excedido")

    return {
        "approved": len(reasons) == 0,
        "reasons": reasons,
        "hourly_orders": hourly_orders,
        "current_notional_usd": round(current_notional, 2),
        "max_position_usd": round(max_position_usd, 2),
        "daily_fees_usd": round(daily_fees, 4),
    }


def update_position(cur: psycopg.Cursor, symbol: str, side: str, qty: float, price: float) -> None:
    cur.execute("select qty, avg_entry from positions where symbol = %s", (symbol,))
    row = cur.fetchone()
    old_qty = float(row["qty"]) if row else 0.0
    old_avg = float(row["avg_entry"]) if row else 0.0

    if side == "buy":
        new_qty = old_qty + qty
        new_avg = ((old_qty * old_avg) + (qty * price)) / new_qty if new_qty > 0 else 0.0
    else:
        new_qty = max(0.0, old_qty - qty)
        new_avg = old_avg if new_qty > 0 else 0.0

    cur.execute(
        """
        insert into positions(symbol, qty, avg_entry, unrealized_pnl, updated_at)
        values(%s, %s, %s, 0, now())
        on conflict(symbol) do update
            set qty = excluded.qty,
                avg_entry = excluded.avg_entry,
                updated_at = now()
        """,
        (symbol, new_qty, new_avg),
    )


def insert_risk_event(cur: psycopg.Cursor, rule: str, severity: str, context: dict[str, Any]) -> None:
    cur.execute(
        """
        insert into risk_events(id, ts, rule, severity, context)
        values(%s, now(), %s, %s, %s::jsonb)
        """,
        (str(uuid.uuid4()), rule, severity, json.dumps(context)),
    )


def normalize_order_status(status: str) -> str:
    s = (status or "").lower()
    if s in {"closed", "filled"}:
        return "filled"
    if s in {"canceled", "cancelled"}:
        return "canceled"
    if s in {"open"}:
        return "open"
    if s in {"rejected"}:
        return "rejected"
    return "submitted"


def build_ccxt_exchange() -> Any:
    if ccxt is None:
        raise HTTPException(status_code=503, detail="ccxt no esta instalado en el contenedor")
    if EXCHANGE_ADAPTER != "ccxt":
        raise HTTPException(status_code=503, detail="EXCHANGE_ADAPTER debe ser 'ccxt' para modo live")
    if not EXCHANGE_API_KEY or not EXCHANGE_API_SECRET:
        raise HTTPException(status_code=503, detail="Faltan credenciales de exchange API")

    exchange_class = getattr(ccxt, EXCHANGE_ID, None)
    if exchange_class is None:
        raise HTTPException(status_code=400, detail=f"Exchange no soportado en ccxt: {EXCHANGE_ID}")

    kwargs: dict[str, Any] = {
        "apiKey": EXCHANGE_API_KEY,
        "secret": EXCHANGE_API_SECRET,
        "enableRateLimit": True,
    }
    if EXCHANGE_API_PASSPHRASE:
        kwargs["password"] = EXCHANGE_API_PASSPHRASE

    exchange = exchange_class(kwargs)
    if EXCHANGE_SANDBOX and hasattr(exchange, "set_sandbox_mode"):
        exchange.set_sandbox_mode(True)

    try:
        exchange.load_markets()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo cargar mercados de {EXCHANGE_ID}: {exc}") from exc

    if EXCHANGE_SYMBOL not in exchange.markets:
        raise HTTPException(status_code=400, detail=f"Par no disponible en {EXCHANGE_ID}: {EXCHANGE_SYMBOL}")

    return exchange


def execute_live_ccxt_order(side: str, qty: float) -> dict[str, Any]:
    exchange = build_ccxt_exchange()
    try:
        qty_precise = float(exchange.amount_to_precision(EXCHANGE_SYMBOL, qty))
    except Exception:
        qty_precise = qty

    if qty_precise <= 0:
        raise HTTPException(status_code=400, detail="Cantidad de orden invalida para live trading")

    try:
        order = exchange.create_order(EXCHANGE_SYMBOL, LIVE_ORDER_TYPE, side, qty_precise)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Fallo creando orden en {EXCHANGE_ID}: {exc}") from exc

    venue_order_id = str(order.get("id") or "")
    normalized_status = normalize_order_status(str(order.get("status") or "submitted"))
    filled_qty = float(order.get("filled") or 0.0)
    avg_price = float(order.get("average") or order.get("price") or 0.0)
    notional = float(order.get("cost") or (filled_qty * avg_price))
    fee_info = order.get("fee") or {}
    fee_cost = float(fee_info.get("cost") or 0.0)
    fee_asset = str(fee_info.get("currency") or "USD")

    return {
        "venue_order_id": venue_order_id,
        "status": normalized_status,
        "filled_qty": filled_qty,
        "avg_price": avg_price,
        "notional_usd": notional,
        "fee_cost": fee_cost,
        "fee_asset": fee_asset,
        "raw": order,
    }


def electrum_rpc(method: str, params: list[Any] | None = None) -> Any:
    if not ENABLE_ELECTRUM_RPC:
        raise HTTPException(status_code=503, detail="Electrum RPC deshabilitado")

    payload = json.dumps({"jsonrpc": "2.0", "id": "codex", "method": method, "params": params or []}).encode("utf-8")
    req = Request(ELECTRUM_RPC_URL, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")

    if ELECTRUM_RPC_USER:
        auth_bytes = f"{ELECTRUM_RPC_USER}:{ELECTRUM_RPC_PASSWORD}".encode("utf-8")
        req.add_header("Authorization", f"Basic {base64.b64encode(auth_bytes).decode('ascii')}")

    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", "ignore")
        raise HTTPException(status_code=502, detail=f"Electrum HTTP error: {exc.code} {body}") from exc
    except URLError as exc:
        raise HTTPException(status_code=502, detail=f"Electrum unreachable: {exc.reason}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Electrum devolvio respuesta no JSON") from exc

    if data.get("error"):
        raise HTTPException(status_code=502, detail=f"Electrum RPC error: {data['error']}")

    return data.get("result")


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("select 1 as ok")
            _ = cur.fetchone()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"DB no disponible: {exc}") from exc

    return {
        "status": "ok",
        "mode": TRADING_MODE,
        "exchange_adapter": EXCHANGE_ADAPTER,
        "exchange_id": EXCHANGE_ID,
        "exchange_symbol": EXCHANGE_SYMBOL,
        "feature_set_version": FEATURE_SET_VERSION,
        "electrum_rpc_enabled": ENABLE_ELECTRUM_RPC,
    }


@app.post("/ingest/market")
def ingest_market(req: MarketIngestRequest) -> dict[str, Any]:
    ts = req.ts or utc_now()
    o = float(req.open if req.open is not None else req.close)
    h = float(req.high if req.high is not None else req.close)
    l = float(req.low if req.low is not None else req.close)
    c = float(req.close)
    v = float(req.volume)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            insert into market_candles(
                ts, venue, symbol, timeframe, open, high, low, close, volume, raw_payload
            )
            values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            on conflict(ts, venue, symbol, timeframe) do update
                set open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume,
                    raw_payload = excluded.raw_payload,
                    updated_at = now()
            """,
            (ts, req.source, req.symbol, req.timeframe, o, h, l, c, v, json.dumps(req.raw)),
        )
        conn.commit()

    return {
        "ok": True,
        "symbol": req.symbol,
        "source": req.source,
        "timeframe": req.timeframe,
        "ts": ts.isoformat(),
        "close": c,
    }


@app.post("/ingest/onchain")
def ingest_onchain(req: OnchainIngestRequest) -> dict[str, Any]:
    ts = req.ts or utc_now()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            insert into onchain_metrics(ts, source, metric, value, raw_payload)
            values(%s, %s, %s, %s, %s::jsonb)
            on conflict(ts, source, metric) do update
                set value = excluded.value,
                    raw_payload = excluded.raw_payload,
                    updated_at = now()
            """,
            (ts, req.source, req.metric, req.value, json.dumps(req.raw)),
        )
        conn.commit()

    return {"ok": True, "source": req.source, "metric": req.metric, "value": req.value, "ts": ts.isoformat()}


@app.post("/features/build")
def build_features(req: FeatureBuildRequest) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select ts, close
            from market_candles
            where symbol = %s and timeframe = %s
            order by ts desc
            limit %s
            """,
            (req.symbol, req.timeframe, req.lookback),
        )
        rows = cur.fetchall()
        if len(rows) < 25:
            raise HTTPException(status_code=409, detail="No hay suficientes velas para construir features (minimo 25)")

        rows = list(reversed(rows))
        closes = [float(r["close"]) for r in rows]
        current_ts = rows[-1]["ts"]

        returns = []
        for i in range(1, len(closes)):
            prev = closes[i - 1]
            if prev == 0:
                returns.append(0.0)
            else:
                returns.append((closes[i] / prev) - 1.0)

        sma_short = sum(closes[-8:]) / 8.0
        sma_long = sum(closes[-21:]) / 21.0
        momentum_12 = (closes[-1] / closes[-12]) - 1.0 if len(closes) >= 12 and closes[-12] != 0 else 0.0
        volatility_20 = pstdev(returns[-20:]) if len(returns) >= 20 else (pstdev(returns) if len(returns) > 1 else 0.0)

        payload = {
            "last_close": closes[-1],
            "sma_short_8": sma_short,
            "sma_long_21": sma_long,
            "momentum_12": momentum_12,
            "volatility_20": volatility_20,
            "sample_size": len(closes),
        }

        cur.execute(
            """
            insert into features(ts, symbol, feature_set_version, payload)
            values(%s, %s, %s, %s::jsonb)
            on conflict(ts, symbol, feature_set_version) do update
                set payload = excluded.payload,
                    updated_at = now()
            """,
            (current_ts, req.symbol, FEATURE_SET_VERSION, json.dumps(payload)),
        )
        conn.commit()

    return {
        "ok": True,
        "symbol": req.symbol,
        "feature_set_version": FEATURE_SET_VERSION,
        "ts": current_ts.isoformat(),
        "payload": payload,
    }


@app.post("/signal/evaluate")
def evaluate_signal(req: SignalEvaluateRequest) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select ts, payload
            from features
            where symbol = %s and feature_set_version = %s
            order by ts desc
            limit 1
            """,
            (req.symbol, req.feature_set_version),
        )
        feature_row = cur.fetchone()
        if not feature_row:
            raise HTTPException(status_code=409, detail="No hay features. Ejecuta /features/build primero")

        payload = feature_row["payload"]
        sma_short = float(payload.get("sma_short_8", 0))
        sma_long = float(payload.get("sma_long_21", 0))
        momentum = float(payload.get("momentum_12", 0))
        volatility = float(payload.get("volatility_20", 1))

        action = "hold"
        if sma_short > sma_long and momentum > 0 and volatility <= VOLATILITY_CUTOFF:
            action = "buy"
        elif sma_short < sma_long and momentum < 0:
            action = "sell"

        trend_score = abs(sma_short - sma_long) / max(abs(sma_long), 1e-9)
        confidence = min(0.99, max(0.05, abs(momentum) * 10.0 + trend_score * 5.0))

        target_notional = PAPER_EQUITY_USD * MAX_POSITION_PCT * confidence
        if action == "hold":
            target_notional = 0.0

        signal_id = str(uuid.uuid4())
        reason = f"sma8={sma_short:.2f}, sma21={sma_long:.2f}, momentum12={momentum:.5f}, vol20={volatility:.5f}"

        cur.execute(
            """
            insert into signals(
                signal_id, ts, symbol, strategy_version, action, confidence, target_notional_usd, reason
            )
            values(%s, now(), %s, %s, %s, %s, %s, %s)
            """,
            (
                signal_id,
                req.symbol,
                req.feature_set_version,
                action,
                confidence,
                target_notional,
                reason,
            ),
        )
        conn.commit()

    return {
        "ok": True,
        "signal_id": signal_id,
        "symbol": req.symbol,
        "action": action,
        "confidence": round(confidence, 4),
        "target_notional_usd": round(target_notional, 2),
        "reason": reason,
    }


@app.post("/risk/check")
def risk_check(req: RiskCheckRequest) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        symbol = req.symbol
        action = req.action
        target = req.target_notional_usd

        if req.signal_id:
            cur.execute("select symbol, action, target_notional_usd from signals where signal_id = %s", (req.signal_id,))
            signal = cur.fetchone()
            if not signal:
                raise HTTPException(status_code=404, detail="signal_id no encontrado")
            symbol = signal["symbol"]
            action = signal["action"]
            target = float(signal["target_notional_usd"])

        if action is None or target is None:
            raise HTTPException(status_code=400, detail="Debes enviar signal_id o action + target_notional_usd")

        result = evaluate_risk(cur, symbol, action, float(target))
        if not result["approved"]:
            insert_risk_event(
                cur,
                rule="pre_trade_risk_gate",
                severity="high",
                context={"symbol": symbol, "action": action, "target": target, "reasons": result["reasons"]},
            )
            conn.commit()

    return {"ok": True, "symbol": symbol, "action": action, **result}


@app.post("/execution/order")
def execution_order(req: ExecutionOrderRequest) -> dict[str, Any]:
    if TRADING_MODE not in {"paper", "live"}:
        raise HTTPException(status_code=500, detail=f"TRADING_MODE invalido: {TRADING_MODE}")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select signal_id, symbol, action, target_notional_usd
            from signals
            where signal_id = %s
            """,
            (req.signal_id,),
        )
        signal = cur.fetchone()
        if not signal:
            raise HTTPException(status_code=404, detail="signal_id no encontrado")

        symbol = signal["symbol"]
        action = signal["action"]
        target_notional = float(signal["target_notional_usd"])

        if action not in {"buy", "sell"}:
            return {
                "ok": True,
                "signal_id": req.signal_id,
                "status": "skipped",
                "reason": "accion_no_ejecutable",
                "action": action,
            }

        risk = evaluate_risk(cur, symbol, action, target_notional)

        order_id = str(uuid.uuid4())
        side = action

        if not risk["approved"]:
            cur.execute(
                """
                insert into orders(
                    order_id, signal_id, venue, venue_order_id, symbol, side, type,
                    qty, requested_notional_usd, status, metadata
                )
                values(%s, %s, %s, %s, %s, %s, %s, 0, %s, %s, %s::jsonb)
                """,
                (
                    order_id,
                    req.signal_id,
                    "paper" if TRADING_MODE == "paper" else EXCHANGE_ID,
                    f"paper-{order_id}",
                    symbol,
                    side,
                    req.order_type,
                    target_notional,
                    "rejected",
                    json.dumps({"risk": risk}),
                ),
            )
            insert_risk_event(
                cur,
                rule="execution_blocked_by_risk",
                severity="high",
                context={"signal_id": req.signal_id, "risk": risk},
            )
            conn.commit()
            return {
                "ok": False,
                "order_id": order_id,
                "status": "rejected",
                "signal_id": req.signal_id,
                "risk": risk,
            }

        px = latest_price(cur, symbol)
        qty = target_notional / px if px > 0 else 0.0
        fee = target_notional * (TAKER_FEE_BPS / 10000.0)
        venue = "paper"
        venue_order_id = f"paper-{order_id}"
        order_status = "filled"
        executed_qty = qty
        fill_price = px
        fee_asset = "USD"
        raw_meta: dict[str, Any] = {"fill_price": px, "mode": "paper"}

        if TRADING_MODE == "live":
            live = execute_live_ccxt_order(side, qty)
            venue = EXCHANGE_ID
            venue_order_id = live["venue_order_id"] or f"{EXCHANGE_ID}-{order_id}"
            order_status = live["status"]
            executed_qty = float(live["filled_qty"] or 0.0)
            fill_price = float(live["avg_price"] or px)
            if fill_price <= 0:
                fill_price = px
            if live["fee_cost"] > 0:
                fee = float(live["fee_cost"])
            fee_asset = live["fee_asset"] or "USD"
            raw_meta = {"mode": "live", "ccxt": live["raw"], "fallback_price": px}

        cur.execute(
            """
            insert into orders(
                order_id, signal_id, venue, venue_order_id, symbol, side, type,
                qty, requested_notional_usd, status, metadata
            )
            values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                order_id,
                req.signal_id,
                venue,
                venue_order_id,
                symbol,
                side,
                req.order_type,
                executed_qty,
                target_notional,
                order_status,
                json.dumps(raw_meta),
            ),
        )

        if order_status == "filled" and executed_qty > 0:
            fill_id = str(uuid.uuid4())
            cur.execute(
                """
                insert into fills(fill_id, order_id, price, qty, fee, fee_asset, notional_usd, ts)
                values(%s, %s, %s, %s, %s, %s, %s, now())
                """,
                (fill_id, order_id, fill_price, executed_qty, fee, fee_asset, executed_qty * fill_price),
            )
            update_position(cur, symbol, side, executed_qty, fill_price)

        conn.commit()

    return {
        "ok": True,
        "signal_id": req.signal_id,
        "order_id": order_id,
        "status": order_status,
        "mode": TRADING_MODE,
        "venue": venue,
        "side": side,
        "qty": round(executed_qty, 8),
        "fill_price": round(fill_price, 2),
        "fee_usd": round(fee, 4),
    }


@app.post("/reconcile")
def reconcile() -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("select status, count(*) as c from orders group by status order by status")
        by_status = {row["status"]: int(row["c"]) for row in cur.fetchall()}

        cur.execute(
            """
            select symbol, qty, avg_entry, updated_at
            from positions
            order by symbol asc
            """
        )
        positions = cur.fetchall()

        cur.execute("select count(*) as c from signals")
        signal_count = int(cur.fetchone()["c"])

    return {
        "ok": True,
        "signal_count": signal_count,
        "orders_by_status": by_status,
        "positions": positions,
    }


@app.post("/custody/sweep")
def custody_sweep(req: SweepRequest) -> dict[str, Any]:
    if TRADING_MODE != "live":
        return {
            "ok": True,
            "executed": False,
            "mode": TRADING_MODE,
            "reason": "sweep solo se ejecuta en modo live",
        }

    balance = electrum_rpc("getbalance", [])
    confirmed = 0.0
    if isinstance(balance, dict):
        confirmed = float(balance.get("confirmed", 0.0))

    if confirmed < req.min_sweep_btc:
        return {
            "ok": True,
            "executed": False,
            "reason": "balance_insuficiente",
            "confirmed_btc": confirmed,
            "threshold_btc": req.min_sweep_btc,
        }

    return {
        "ok": True,
        "executed": False,
        "reason": "control_manual_requerido",
        "confirmed_btc": confirmed,
        "threshold_btc": req.min_sweep_btc,
        "hint": "usar /electrum/rpc para enviar transaccion despues de validar destino",
    }


@app.get("/electrum/balance")
def electrum_balance() -> dict[str, Any]:
    if not ENABLE_ELECTRUM_RPC:
        return {"ok": False, "enabled": False, "detail": "Electrum RPC deshabilitado"}
    result = electrum_rpc("getbalance", [])
    return {"ok": True, "enabled": True, "result": result}


@app.post("/electrum/rpc")
def electrum_passthrough(req: ElectrumRpcRequest) -> dict[str, Any]:
    result = electrum_rpc(req.method, req.params)
    return {"ok": True, "method": req.method, "result": result}
