import base64
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
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
GLOBAL_KILL_SWITCH_DEFAULT = os.getenv("GLOBAL_KILL_SWITCH_DEFAULT", "false").lower() == "true"
MONITORED_SYMBOL = os.getenv("MONITORED_SYMBOL", "BTCUSD")
MONITORED_TIMEFRAME = os.getenv("MONITORED_TIMEFRAME", "5m")
MARKET_DATA_STALE_MINUTES = int(os.getenv("MARKET_DATA_STALE_MINUTES", "15"))
FEATURES_DATA_STALE_MINUTES = int(os.getenv("FEATURES_DATA_STALE_MINUTES", "30"))
RECONCILE_STALE_MINUTES = int(os.getenv("RECONCILE_STALE_MINUTES", "3"))
REJECTED_ORDERS_1H_WARN_THRESHOLD = int(os.getenv("REJECTED_ORDERS_1H_WARN_THRESHOLD", "3"))
ALERT_COOLDOWN_MINUTES = int(os.getenv("ALERT_COOLDOWN_MINUTES", "30"))
RECONCILE_HEARTBEAT_INTERVAL_MINUTES = int(os.getenv("RECONCILE_HEARTBEAT_INTERVAL_MINUTES", "1"))
PAPER_GO_NO_GO_LOOKBACK_DAYS = int(os.getenv("PAPER_GO_NO_GO_LOOKBACK_DAYS", "14"))
GO_NO_GO_MIN_DAYS = int(os.getenv("GO_NO_GO_MIN_DAYS", "14"))
GO_NO_GO_MIN_EXECUTED_ORDERS = int(os.getenv("GO_NO_GO_MIN_EXECUTED_ORDERS", "20"))
GO_NO_GO_MIN_WIN_RATE = float(os.getenv("GO_NO_GO_MIN_WIN_RATE", "0.45"))
GO_NO_GO_MAX_DRAWDOWN_PCT = float(os.getenv("GO_NO_GO_MAX_DRAWDOWN_PCT", "0.08"))
GO_NO_GO_MIN_REALIZED_PNL_USD = float(os.getenv("GO_NO_GO_MIN_REALIZED_PNL_USD", "0"))
GO_NO_GO_MAX_REJECTION_RATE = float(os.getenv("GO_NO_GO_MAX_REJECTION_RATE", "0.30"))
GO_NO_GO_MIN_RECONCILE_UPTIME_PCT = float(os.getenv("GO_NO_GO_MIN_RECONCILE_UPTIME_PCT", "95"))
GO_NO_GO_MAX_CRITICAL_ALERTS_24H = int(os.getenv("GO_NO_GO_MAX_CRITICAL_ALERTS_24H", "0"))
FORECAST_DEFAULT_HORIZON_MINUTES = int(os.getenv("FORECAST_DEFAULT_HORIZON_MINUTES", "10"))
FORECAST_MIN_MOVE_BPS = float(os.getenv("FORECAST_MIN_MOVE_BPS", "5"))
FORECAST_MAX_RESOLUTION_LAG_MINUTES = int(os.getenv("FORECAST_MAX_RESOLUTION_LAG_MINUTES", "20"))
FORECAST_GO_MIN_ACCURACY = float(os.getenv("FORECAST_GO_MIN_ACCURACY", "0.55"))
HYBRID_MODE = os.getenv("HYBRID_MODE", "shadow").lower()
HYBRID_REQUIRE_AI_AGREEMENT = os.getenv("HYBRID_REQUIRE_AI_AGREEMENT", "true").lower() == "true"
HYBRID_AI_MIN_CONFIDENCE = float(os.getenv("HYBRID_AI_MIN_CONFIDENCE", "0.60"))
HYBRID_QUANT_MIN_CONFIDENCE = float(os.getenv("HYBRID_QUANT_MIN_CONFIDENCE", "0.10"))
HYBRID_ALERT_MIN_RESOLVED = int(os.getenv("HYBRID_ALERT_MIN_RESOLVED", "20"))
HYBRID_ALERT_MIN_ACCURACY = float(os.getenv("HYBRID_ALERT_MIN_ACCURACY", "0.55"))
HYBRID_ALERT_MIN_EDGE_BPS = float(os.getenv("HYBRID_ALERT_MIN_EDGE_BPS", "0"))

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


class ExecutionIntentRequest(BaseModel):
    signal_id: str
    source: str = "n8n_no_kyc"
    note: str | None = None


class ExecutionIntentConfirmRequest(BaseModel):
    intent_id: str
    status: str
    txid: str | None = None
    fill_price: float | None = None
    filled_qty: float | None = None
    fee: float = 0.0
    fee_asset: str = "USD"
    confirmed_at: datetime | None = None
    external_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntentElectrumReconcileRequest(BaseModel):
    limit: int = 25


class SweepRequest(BaseModel):
    min_sweep_btc: float = 0.01


class ElectrumRpcRequest(BaseModel):
    method: str
    params: list[Any] = Field(default_factory=list)


class KillSwitchSetRequest(BaseModel):
    enabled: bool
    reason: str = "manual_override"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AlertEvaluateRequest(BaseModel):
    persist: bool = True
    include_snapshot: bool = True


class PaperGoNoGoRequest(BaseModel):
    lookback_days: int = PAPER_GO_NO_GO_LOOKBACK_DAYS
    persist: bool = True
    include_scorecard: bool = True


class ForecastCheckpointRequest(BaseModel):
    signal_id: str
    horizon_minutes: int = FORECAST_DEFAULT_HORIZON_MINUTES
    min_move_bps: float = FORECAST_MIN_MOVE_BPS
    timeframe: str = MONITORED_TIMEFRAME
    metadata: dict[str, Any] = Field(default_factory=dict)


class ForecastEvaluateDueRequest(BaseModel):
    limit: int = 200
    max_resolution_lag_minutes: int = FORECAST_MAX_RESOLUTION_LAG_MINUTES
    persist_events: bool = True


class HybridDecisionRequest(BaseModel):
    signal_id: str
    ai_action: str | None = None
    ai_confidence: float | None = None
    ai_reason: str | None = None
    ai_model: str = "unset"
    ai_source: str = "pending_molbot"
    mode: str = HYBRID_MODE
    attach_forecast: bool = True
    forecast_horizon_minutes: int = FORECAST_DEFAULT_HORIZON_MINUTES
    forecast_min_move_bps: float = FORECAST_MIN_MOVE_BPS
    forecast_timeframe: str = MONITORED_TIMEFRAME
    metadata: dict[str, Any] = Field(default_factory=dict)


class HybridAiFallbackRequest(BaseModel):
    signal_id: str
    symbol: str = MONITORED_SYMBOL
    quant_action: str = "hold"
    quant_confidence: float = 0.0
    reason: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class HybridAlertEvaluateRequest(BaseModel):
    lookback_days: int = 7
    mode: str = HYBRID_MODE
    horizon_minutes: int = FORECAST_DEFAULT_HORIZON_MINUTES
    timeframe: str = MONITORED_TIMEFRAME
    persist: bool = True
    include_scorecard: bool = False


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_conn() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def bootstrap_runtime_schema() -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            alter table fills
            add column if not exists realized_pnl_usd numeric not null default 0
            """
        )
        cur.execute(
            """
            create table if not exists risk_controls (
              control_key text primary key,
              enabled boolean not null default false,
              reason text not null default '',
              metadata jsonb not null default '{}'::jsonb,
              updated_at timestamptz not null default now()
            )
            """
        )
        cur.execute(
            """
            create table if not exists ops_heartbeats (
              component text primary key,
              last_seen_at timestamptz not null,
              status text not null,
              payload jsonb not null default '{}'::jsonb,
              updated_at timestamptz not null default now()
            )
            """
        )
        cur.execute(
            """
            create table if not exists ops_alert_state (
              alert_key text primary key,
              last_level text not null,
              last_message text not null,
              last_payload jsonb not null default '{}'::jsonb,
              last_fired_at timestamptz not null,
              updated_at timestamptz not null default now()
            )
            """
        )
        cur.execute(
            """
            create table if not exists ops_heartbeat_log (
              id uuid primary key,
              component text not null,
              ts timestamptz not null default now(),
              status text not null,
              payload jsonb not null default '{}'::jsonb
            )
            """
        )
        cur.execute(
            """
            create index if not exists idx_ops_heartbeat_log_component_ts
            on ops_heartbeat_log(component, ts desc)
            """
        )
        cur.execute(
            """
            create table if not exists paper_evaluations (
              evaluation_id uuid primary key,
              ts timestamptz not null default now(),
              lookback_days int not null,
              decision text not null check (decision in ('go', 'no_go')),
              scorecard jsonb not null,
              criteria jsonb not null
            )
            """
        )
        cur.execute(
            """
            create table if not exists external_execution_intents (
              intent_id uuid primary key,
              order_id uuid references orders(order_id),
              signal_id uuid references signals(signal_id),
              symbol text not null,
              side text not null check (side in ('buy', 'sell')),
              target_notional_usd numeric not null,
              reference_price numeric not null,
              expected_qty numeric not null,
              status text not null check (status in ('open', 'filled', 'rejected', 'canceled', 'settled')),
              source text not null default 'n8n_no_kyc',
              txid text,
              external_ref text,
              notes text,
              metadata jsonb not null default '{}'::jsonb,
              created_at timestamptz not null default now(),
              updated_at timestamptz not null default now(),
              confirmed_at timestamptz
            )
            """
        )
        cur.execute(
            """
            create index if not exists idx_external_execution_intents_status_created
            on external_execution_intents(status, created_at desc)
            """
        )
        cur.execute(
            """
            create index if not exists idx_external_execution_intents_txid
            on external_execution_intents(txid)
            """
        )
        cur.execute(
            """
            create table if not exists forecast_checks (
              forecast_id uuid primary key,
              signal_id uuid not null references signals(signal_id),
              signal_ts timestamptz not null,
              symbol text not null,
              timeframe text not null,
              predicted_action text not null check (predicted_action in ('buy', 'sell', 'hold')),
              predicted_confidence numeric not null,
              horizon_minutes int not null,
              min_move_bps numeric not null default 0,
              entry_price numeric not null,
              due_ts timestamptz not null,
              resolved_ts timestamptz,
              resolved_price numeric,
              price_change_bps numeric,
              outcome text not null check (outcome in ('pending', 'hit', 'miss', 'expired')),
              metadata jsonb not null default '{}'::jsonb,
              created_at timestamptz not null default now(),
              updated_at timestamptz not null default now(),
              unique(signal_id, timeframe, horizon_minutes)
            )
            """
        )
        cur.execute(
            """
            create index if not exists idx_forecast_checks_outcome_due
            on forecast_checks(outcome, due_ts asc)
            """
        )
        cur.execute(
            """
            create index if not exists idx_forecast_checks_created
            on forecast_checks(created_at desc)
            """
        )
        cur.execute(
            """
            create table if not exists hybrid_decisions (
              decision_id uuid primary key,
              signal_id uuid not null references signals(signal_id),
              signal_ts timestamptz not null,
              symbol text not null,
              quant_action text not null check (quant_action in ('buy', 'sell', 'hold')),
              quant_confidence numeric not null,
              ai_action text not null check (ai_action in ('buy', 'sell', 'hold')),
              ai_confidence numeric not null default 0,
              ai_reason text,
              ai_model text not null default 'unset',
              ai_source text not null default 'pending_molbot',
              agreement boolean not null default false,
              hybrid_action text not null check (hybrid_action in ('buy', 'sell', 'hold')),
              hybrid_confidence numeric not null default 0,
              decision_reason text not null,
              mode text not null check (mode in ('shadow', 'paper', 'live')),
              metadata jsonb not null default '{}'::jsonb,
              created_at timestamptz not null default now(),
              updated_at timestamptz not null default now(),
              unique(signal_id, mode, ai_source)
            )
            """
        )
        cur.execute(
            """
            create index if not exists idx_hybrid_decisions_created
            on hybrid_decisions(created_at desc)
            """
        )
        cur.execute(
            """
            create index if not exists idx_hybrid_decisions_mode_created
            on hybrid_decisions(mode, created_at desc)
            """
        )
        cur.execute(
            """
            insert into risk_controls(control_key, enabled, reason, metadata)
            values('global_kill_switch', %s, %s, %s::jsonb)
            on conflict(control_key) do nothing
            """,
            (GLOBAL_KILL_SWITCH_DEFAULT, "startup_default", json.dumps({"source": "startup"})),
        )
        conn.commit()


@app.on_event("startup")
def on_startup() -> None:
    try:
        bootstrap_runtime_schema()
    except Exception as exc:
        print(f"warning: bootstrap_runtime_schema failed: {exc}")


def set_kill_switch_state(
    cur: psycopg.Cursor,
    enabled: bool,
    reason: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    cur.execute(
        """
        insert into risk_controls(control_key, enabled, reason, metadata, updated_at)
        values('global_kill_switch', %s, %s, %s::jsonb, now())
        on conflict(control_key) do update
            set enabled = excluded.enabled,
                reason = excluded.reason,
                metadata = excluded.metadata,
                updated_at = now()
        """,
        (enabled, reason, json.dumps(metadata or {})),
    )


def get_kill_switch_state(cur: psycopg.Cursor) -> dict[str, Any]:
    cur.execute(
        """
        select enabled, reason, metadata, updated_at
        from risk_controls
        where control_key = 'global_kill_switch'
        limit 1
        """
    )
    row = cur.fetchone()
    if row:
        return {
            "enabled": bool(row["enabled"]),
            "reason": row["reason"],
            "metadata": row["metadata"],
            "updated_at": row["updated_at"],
        }

    set_kill_switch_state(cur, GLOBAL_KILL_SWITCH_DEFAULT, "lazy_default", {"source": "lazy_init"})
    return {
        "enabled": GLOBAL_KILL_SWITCH_DEFAULT,
        "reason": "lazy_default",
        "metadata": {"source": "lazy_init"},
        "updated_at": utc_now(),
    }


def get_daily_realized_pnl(cur: psycopg.Cursor) -> float:
    cur.execute(
        """
        select coalesce(sum(realized_pnl_usd), 0) as pnl
        from fills
        where ts::date = current_date
        """
    )
    row = cur.fetchone()
    return float(row["pnl"])


def minutes_since(ts: datetime | None) -> float | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max(0.0, (utc_now() - ts.astimezone(timezone.utc)).total_seconds() / 60.0)


def upsert_heartbeat(cur: psycopg.Cursor, component: str, status: str, payload: dict[str, Any]) -> None:
    cur.execute(
        """
        insert into ops_heartbeats(component, last_seen_at, status, payload, updated_at)
        values(%s, now(), %s, %s::jsonb, now())
        on conflict(component) do update
            set last_seen_at = excluded.last_seen_at,
                status = excluded.status,
                payload = excluded.payload,
                updated_at = now()
        """,
        (component, status, json.dumps(payload)),
    )


def get_ops_snapshot(cur: psycopg.Cursor) -> dict[str, Any]:
    kill_switch = get_kill_switch_state(cur)
    daily_realized_pnl = get_daily_realized_pnl(cur)
    daily_loss_usd = max(0.0, -daily_realized_pnl)

    cur.execute(
        """
        select max(ts) as latest_ts
        from market_candles
        where symbol = %s and timeframe = %s
        """,
        (MONITORED_SYMBOL, MONITORED_TIMEFRAME),
    )
    market_row = cur.fetchone()
    latest_market_ts = market_row["latest_ts"] if market_row else None
    market_age_minutes = minutes_since(latest_market_ts)

    cur.execute(
        """
        select max(ts) as latest_ts
        from features
        where symbol = %s and feature_set_version = %s
        """,
        (MONITORED_SYMBOL, FEATURE_SET_VERSION),
    )
    feature_row = cur.fetchone()
    latest_feature_ts = feature_row["latest_ts"] if feature_row else None
    feature_age_minutes = minutes_since(latest_feature_ts)

    cur.execute(
        """
        select last_seen_at, status, payload
        from ops_heartbeats
        where component = 'reconcile_loop'
        limit 1
        """
    )
    reconcile_row = cur.fetchone()
    reconcile_last_seen = reconcile_row["last_seen_at"] if reconcile_row else None
    reconcile_age_minutes = minutes_since(reconcile_last_seen)
    reconcile_status = reconcile_row["status"] if reconcile_row else "missing"

    cur.execute(
        """
        select count(*) as c
        from orders
        where created_at >= now() - interval '1 hour'
          and status = 'rejected'
        """
    )
    rejected_orders_1h = int(cur.fetchone()["c"])

    cur.execute(
        """
        select severity, count(*) as c
        from risk_events
        where ts >= now() - interval '1 hour'
        group by severity
        """
    )
    risk_event_counts = {str(row["severity"]): int(row["c"]) for row in cur.fetchall()}

    return {
        "monitored_symbol": MONITORED_SYMBOL,
        "monitored_timeframe": MONITORED_TIMEFRAME,
        "kill_switch_enabled": bool(kill_switch["enabled"]),
        "kill_switch_reason": kill_switch["reason"],
        "daily_realized_pnl_usd": round(daily_realized_pnl, 4),
        "daily_loss_usd": round(daily_loss_usd, 4),
        "daily_loss_limit_usd": DAILY_LOSS_LIMIT_USD,
        "market_data_age_minutes": None if market_age_minutes is None else round(market_age_minutes, 2),
        "feature_data_age_minutes": None if feature_age_minutes is None else round(feature_age_minutes, 2),
        "reconcile_age_minutes": None if reconcile_age_minutes is None else round(reconcile_age_minutes, 2),
        "reconcile_status": reconcile_status,
        "rejected_orders_1h": rejected_orders_1h,
        "risk_events_1h": risk_event_counts,
        "latest_market_ts": latest_market_ts,
        "latest_feature_ts": latest_feature_ts,
        "reconcile_last_seen_at": reconcile_last_seen,
    }


def build_ops_alerts(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []

    market_age = snapshot["market_data_age_minutes"]
    if market_age is None:
        alerts.append(
            {
                "key": "market_data_missing",
                "level": "critical",
                "message": "No hay velas de mercado para el simbolo monitoreado",
                "context": {"symbol": snapshot["monitored_symbol"], "timeframe": snapshot["monitored_timeframe"]},
            }
        )
    elif float(market_age) > MARKET_DATA_STALE_MINUTES:
        level = "critical" if float(market_age) > (MARKET_DATA_STALE_MINUTES * 2) else "warning"
        alerts.append(
            {
                "key": "market_data_stale",
                "level": level,
                "message": f"Market data stale: {market_age}m",
                "context": {"age_minutes": market_age, "threshold_minutes": MARKET_DATA_STALE_MINUTES},
            }
        )

    feature_age = snapshot["feature_data_age_minutes"]
    if feature_age is None:
        alerts.append(
            {
                "key": "features_missing",
                "level": "warning",
                "message": "No hay features recientes para el simbolo monitoreado",
                "context": {"symbol": snapshot["monitored_symbol"], "feature_set_version": FEATURE_SET_VERSION},
            }
        )
    elif float(feature_age) > FEATURES_DATA_STALE_MINUTES:
        alerts.append(
            {
                "key": "features_stale",
                "level": "warning",
                "message": f"Feature data stale: {feature_age}m",
                "context": {"age_minutes": feature_age, "threshold_minutes": FEATURES_DATA_STALE_MINUTES},
            }
        )

    reconcile_age = snapshot["reconcile_age_minutes"]
    if reconcile_age is None:
        alerts.append(
            {
                "key": "reconcile_missing",
                "level": "critical",
                "message": "No existe heartbeat del reconcile loop",
                "context": {"component": "reconcile_loop"},
            }
        )
    elif float(reconcile_age) > RECONCILE_STALE_MINUTES:
        alerts.append(
            {
                "key": "reconcile_stale",
                "level": "critical",
                "message": f"Reconcile stale: {reconcile_age}m",
                "context": {"age_minutes": reconcile_age, "threshold_minutes": RECONCILE_STALE_MINUTES},
            }
        )

    if snapshot["kill_switch_enabled"]:
        alerts.append(
            {
                "key": "kill_switch_enabled",
                "level": "critical",
                "message": "Kill switch global activado",
                "context": {"reason": snapshot["kill_switch_reason"]},
            }
        )

    if float(snapshot["daily_loss_usd"]) >= DAILY_LOSS_LIMIT_USD:
        alerts.append(
            {
                "key": "daily_loss_limit_exceeded",
                "level": "critical",
                "message": "Perdida diaria supero limite configurado",
                "context": {
                    "daily_loss_usd": snapshot["daily_loss_usd"],
                    "daily_loss_limit_usd": DAILY_LOSS_LIMIT_USD,
                },
            }
        )

    if int(snapshot["rejected_orders_1h"]) >= REJECTED_ORDERS_1H_WARN_THRESHOLD:
        alerts.append(
            {
                "key": "high_rejected_orders_1h",
                "level": "warning",
                "message": f"Rechazos altos en 1h: {snapshot['rejected_orders_1h']}",
                "context": {
                    "rejected_orders_1h": snapshot["rejected_orders_1h"],
                    "threshold": REJECTED_ORDERS_1H_WARN_THRESHOLD,
                },
            }
        )

    return alerts


def persist_ops_alerts(cur: psycopg.Cursor, alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    persisted: list[dict[str, Any]] = []
    for alert in alerts:
        alert_key = str(alert["key"])
        level = str(alert["level"])
        message = str(alert["message"])
        context = dict(alert.get("context") or {})

        cur.execute(
            """
            select last_fired_at, last_level, last_message
            from ops_alert_state
            where alert_key = %s
            """,
            (alert_key,),
        )
        row = cur.fetchone()
        should_fire = True
        if row:
            elapsed = minutes_since(row["last_fired_at"])
            same_signature = row["last_level"] == level and row["last_message"] == message
            if elapsed is not None and elapsed < ALERT_COOLDOWN_MINUTES and same_signature:
                should_fire = False

        if should_fire:
            insert_risk_event(
                cur,
                rule=f"ops_alert_{alert_key}",
                severity=level,
                context={"message": message, "context": context},
            )
            persisted.append(alert)
            cur.execute(
                """
                insert into ops_alert_state(alert_key, last_level, last_message, last_payload, last_fired_at, updated_at)
                values(%s, %s, %s, %s::jsonb, now(), now())
                on conflict(alert_key) do update
                    set last_level = excluded.last_level,
                        last_message = excluded.last_message,
                        last_payload = excluded.last_payload,
                        last_fired_at = excluded.last_fired_at,
                        updated_at = now()
                """,
                (alert_key, level, message, json.dumps(context)),
            )

    return persisted


def build_paper_scorecard(cur: psycopg.Cursor, lookback_days: int) -> dict[str, Any]:
    window_start = utc_now() - timedelta(days=lookback_days)

    cur.execute(
        """
        select min(ts) as first_ts, max(ts) as last_ts, count(*) as c
        from signals
        """
    )
    signal_history = cur.fetchone()
    first_signal_ts = signal_history["first_ts"] if signal_history else None
    last_signal_ts = signal_history["last_ts"] if signal_history else None
    runtime_days = 0.0
    if first_signal_ts is not None:
        runtime_days = max(0.0, (utc_now() - first_signal_ts).total_seconds() / 86400.0)

    cur.execute(
        """
        select count(*) as signal_count,
               count(*) filter (where action in ('buy', 'sell')) as executable_signal_count
        from signals
        where ts >= %s
        """,
        (window_start,),
    )
    signal_window = cur.fetchone()
    signal_count = int(signal_window["signal_count"])
    executable_signal_count = int(signal_window["executable_signal_count"])

    cur.execute(
        """
        select count(*) as total_orders,
               count(*) filter (where status = 'filled') as filled_orders,
               count(*) filter (where status = 'rejected') as rejected_orders
        from orders
        where created_at >= %s
        """,
        (window_start,),
    )
    order_window = cur.fetchone()
    total_orders = int(order_window["total_orders"])
    filled_orders = int(order_window["filled_orders"])
    rejected_orders = int(order_window["rejected_orders"])
    rejection_rate = (rejected_orders / total_orders) if total_orders > 0 else None

    cur.execute(
        """
        select coalesce(sum(realized_pnl_usd), 0) as realized_pnl
        from fills
        where ts >= %s
        """,
        (window_start,),
    )
    realized_pnl_usd = float(cur.fetchone()["realized_pnl"])

    cur.execute(
        """
        select count(*) filter (where o.side = 'sell') as sell_fills,
               count(*) filter (where o.side = 'sell' and f.realized_pnl_usd > 0) as winning_sell_fills
        from fills f
        join orders o on o.order_id = f.order_id
        where f.ts >= %s
        """,
        (window_start,),
    )
    win_stats = cur.fetchone()
    sell_fills = int(win_stats["sell_fills"])
    winning_sell_fills = int(win_stats["winning_sell_fills"])
    win_rate = (winning_sell_fills / sell_fills) if sell_fills > 0 else None

    cur.execute(
        """
        select realized_pnl_usd
        from fills
        where ts >= %s
        order by ts asc
        """,
        (window_start,),
    )
    cumulative = 0.0
    peak = 0.0
    max_drawdown_usd = 0.0
    for row in cur.fetchall():
        cumulative += float(row["realized_pnl_usd"])
        if cumulative > peak:
            peak = cumulative
        drawdown = peak - cumulative
        if drawdown > max_drawdown_usd:
            max_drawdown_usd = drawdown
    max_drawdown_pct = (max_drawdown_usd / PAPER_EQUITY_USD) if PAPER_EQUITY_USD > 0 else 1.0

    cur.execute(
        """
        select min(ts) as first_ok_ts, count(*) as ok_count
        from ops_heartbeat_log
        where component = 'reconcile_loop'
          and status = 'ok'
          and ts >= %s
        """,
        (window_start,),
    )
    heartbeat_stats = cur.fetchone()
    first_reconcile_ok_ts = heartbeat_stats["first_ok_ts"] if heartbeat_stats else None
    reconcile_heartbeat_ok = int(heartbeat_stats["ok_count"]) if heartbeat_stats else 0

    # Heartbeat logging was introduced after initial trading runtime.
    # Measure uptime from the first observed heartbeat in the score window to avoid false penalties.
    if first_reconcile_ok_ts is not None:
        uptime_start = max(window_start, first_reconcile_ok_ts)
    else:
        uptime_start = window_start

    uptime_window_minutes = max(1.0, (utc_now() - uptime_start).total_seconds() / 60.0)
    uptime_window_days = uptime_window_minutes / (24.0 * 60.0)
    expected_heartbeat_count = max(
        1,
        int(uptime_window_minutes / max(1, RECONCILE_HEARTBEAT_INTERVAL_MINUTES)) + 1,
    )
    reconcile_uptime_pct = min(100.0, (reconcile_heartbeat_ok / expected_heartbeat_count) * 100.0)

    cur.execute(
        """
        select count(*) as c
        from risk_events
        where ts >= now() - interval '24 hour'
          and severity = 'critical'
          and rule like 'ops_alert_%'
        """
    )
    critical_ops_alerts_24h = int(cur.fetchone()["c"])

    # For go/no-go readiness, unresolved critical conditions matter more than
    # already-recovered incidents in the last 24h.
    snapshot = get_ops_snapshot(cur)
    active_alerts = build_ops_alerts(snapshot)
    critical_ops_alerts_active = sum(1 for a in active_alerts if str(a.get("level")) == "critical")

    return {
        "generated_at": utc_now().isoformat(),
        "lookback_days": lookback_days,
        "window_start": window_start.isoformat(),
        "runtime_days": round(runtime_days, 2),
        "first_signal_ts": first_signal_ts.isoformat() if first_signal_ts is not None else None,
        "last_signal_ts": last_signal_ts.isoformat() if last_signal_ts is not None else None,
        "signal_count": signal_count,
        "executable_signal_count": executable_signal_count,
        "total_orders": total_orders,
        "filled_orders": filled_orders,
        "rejected_orders": rejected_orders,
        "rejection_rate": None if rejection_rate is None else round(rejection_rate, 4),
        "realized_pnl_usd": round(realized_pnl_usd, 4),
        "sell_fills": sell_fills,
        "winning_sell_fills": winning_sell_fills,
        "win_rate": None if win_rate is None else round(win_rate, 4),
        "max_drawdown_usd": round(max_drawdown_usd, 4),
        "max_drawdown_pct": round(max_drawdown_pct, 6),
        "reconcile_heartbeat_ok_count": reconcile_heartbeat_ok,
        "reconcile_heartbeat_expected_count": expected_heartbeat_count,
        "reconcile_uptime_window_days": round(uptime_window_days, 2),
        "reconcile_uptime_start_ts": uptime_start.isoformat(),
        "reconcile_uptime_pct": round(reconcile_uptime_pct, 2),
        "critical_ops_alerts_24h": critical_ops_alerts_24h,
        "critical_ops_alerts_active": critical_ops_alerts_active,
    }


def evaluate_paper_go_no_go(scorecard: dict[str, Any]) -> dict[str, Any]:
    def check_rule(key: str, operator: str, metric: float | None, target: float) -> dict[str, Any]:
        passed = False
        if metric is not None:
            if operator == ">=":
                passed = float(metric) >= float(target)
            elif operator == "<=":
                passed = float(metric) <= float(target)
        return {
            "key": key,
            "operator": operator,
            "metric": metric,
            "target": target,
            "passed": passed,
        }

    criteria = [
        check_rule("runtime_days_min", ">=", float(scorecard["runtime_days"]), float(GO_NO_GO_MIN_DAYS)),
        check_rule("filled_orders_min", ">=", float(scorecard["filled_orders"]), float(GO_NO_GO_MIN_EXECUTED_ORDERS)),
        check_rule("win_rate_min", ">=", scorecard["win_rate"], float(GO_NO_GO_MIN_WIN_RATE)),
        check_rule("max_drawdown_pct_max", "<=", float(scorecard["max_drawdown_pct"]), float(GO_NO_GO_MAX_DRAWDOWN_PCT)),
        check_rule(
            "realized_pnl_usd_min",
            ">=",
            float(scorecard["realized_pnl_usd"]),
            float(GO_NO_GO_MIN_REALIZED_PNL_USD),
        ),
        check_rule("rejection_rate_max", "<=", scorecard["rejection_rate"], float(GO_NO_GO_MAX_REJECTION_RATE)),
        check_rule(
            "reconcile_uptime_pct_min",
            ">=",
            float(scorecard["reconcile_uptime_pct"]),
            float(GO_NO_GO_MIN_RECONCILE_UPTIME_PCT),
        ),
        check_rule(
            "critical_ops_alerts_24h_max",
            "<=",
            float(scorecard["critical_ops_alerts_active"]),
            float(GO_NO_GO_MAX_CRITICAL_ALERTS_24H),
        ),
    ]

    failed = [c["key"] for c in criteria if not c["passed"]]
    decision = "go" if not failed else "no_go"
    return {
        "decision": decision,
        "go": decision == "go",
        "failed_criteria": failed,
        "criteria": criteria,
    }


def persist_paper_evaluation(
    cur: psycopg.Cursor,
    lookback_days: int,
    scorecard: dict[str, Any],
    evaluation: dict[str, Any],
) -> str:
    evaluation_id = str(uuid.uuid4())
    cur.execute(
        """
        insert into paper_evaluations(evaluation_id, ts, lookback_days, decision, scorecard, criteria)
        values(%s, now(), %s, %s, %s::jsonb, %s::jsonb)
        """,
        (
            evaluation_id,
            lookback_days,
            evaluation["decision"],
            json.dumps(scorecard),
            json.dumps(evaluation["criteria"]),
        ),
    )

    severity = "info" if evaluation["go"] else "high"
    insert_risk_event(
        cur,
        rule="paper_go_no_go_evaluation",
        severity=severity,
        context={
            "evaluation_id": evaluation_id,
            "lookback_days": lookback_days,
            "decision": evaluation["decision"],
            "failed_criteria": evaluation["failed_criteria"],
            "scorecard": scorecard,
        },
    )
    return evaluation_id


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

    kill_switch = get_kill_switch_state(cur)
    if kill_switch["enabled"]:
        reasons.append("kill_switch_activado")

    daily_realized_pnl = get_daily_realized_pnl(cur)
    daily_loss_usd = max(0.0, -daily_realized_pnl)
    if daily_loss_usd >= DAILY_LOSS_LIMIT_USD:
        reasons.append("daily_loss_limit_excedido")
        if not kill_switch["enabled"]:
            auto_ctx = {
                "daily_loss_usd": round(daily_loss_usd, 4),
                "daily_loss_limit_usd": DAILY_LOSS_LIMIT_USD,
                "symbol": symbol,
                "action": action,
            }
            set_kill_switch_state(cur, True, "auto_daily_loss_limit", auto_ctx)
            insert_risk_event(cur, "kill_switch_auto_enabled_daily_loss", "critical", auto_ctx)
            kill_switch = get_kill_switch_state(cur)
            reasons.append("kill_switch_auto_activado")

    return {
        "approved": len(reasons) == 0,
        "reasons": reasons,
        "hourly_orders": hourly_orders,
        "current_notional_usd": round(current_notional, 2),
        "max_position_usd": round(max_position_usd, 2),
        "daily_realized_pnl_usd": round(daily_realized_pnl, 4),
        "daily_loss_usd": round(daily_loss_usd, 4),
        "daily_loss_limit_usd": DAILY_LOSS_LIMIT_USD,
        "kill_switch_enabled": bool(kill_switch["enabled"]),
        "kill_switch_reason": kill_switch["reason"],
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


def compute_realized_pnl(
    side: str,
    qty: float,
    price: float,
    fee: float,
    position_qty: float,
    position_avg: float,
) -> float:
    if side == "buy":
        return -fee

    closed_qty = min(max(position_qty, 0.0), qty)
    gross_pnl = (price - position_avg) * closed_qty
    return gross_pnl - fee


def insert_risk_event(cur: psycopg.Cursor, rule: str, severity: str, context: dict[str, Any]) -> None:
    cur.execute(
        """
        insert into risk_events(id, ts, rule, severity, context)
        values(%s, now(), %s, %s, %s::jsonb)
        """,
        # Risk context may include UUID/datetime values from DB rows.
        (str(uuid.uuid4()), rule, severity, json.dumps(context, default=str)),
    )


def normalize_intent_status(status: str) -> str:
    normalized = (status or "").strip().lower()
    if normalized in {"filled", "rejected", "canceled"}:
        return normalized
    raise HTTPException(status_code=400, detail="status debe ser filled|rejected|canceled")


def forecast_outcome_for_move(action: str, price_change_bps: float, min_move_bps: float) -> str:
    if action == "buy":
        return "hit" if price_change_bps >= min_move_bps else "miss"
    if action == "sell":
        return "hit" if price_change_bps <= -min_move_bps else "miss"
    return "hit" if abs(price_change_bps) <= min_move_bps else "miss"


def forecast_edge_bps(action: str, price_change_bps: float) -> float:
    if action == "buy":
        return price_change_bps
    if action == "sell":
        return -price_change_bps
    return -abs(price_change_bps)


def build_forecast_scorecard(
    cur: psycopg.Cursor,
    lookback_days: int,
    horizon_minutes: int | None,
    timeframe: str | None,
) -> dict[str, Any]:
    window_start = utc_now() - timedelta(days=lookback_days)
    cur.execute(
        """
        select forecast_id, predicted_action, price_change_bps, outcome
        from forecast_checks
        where created_at >= %s
          and (%s::int is null or horizon_minutes = %s)
          and (%s::text is null or timeframe = %s)
        """,
        (window_start, horizon_minutes, horizon_minutes, timeframe, timeframe),
    )
    rows = cur.fetchall()

    total = len(rows)
    pending = 0
    expired = 0
    resolved = 0
    hits = 0
    misses = 0
    edge_values: list[float] = []
    action_stats: dict[str, dict[str, Any]] = {
        "buy": {"resolved": 0, "hits": 0, "avg_price_change_bps": None},
        "sell": {"resolved": 0, "hits": 0, "avg_price_change_bps": None},
        "hold": {"resolved": 0, "hits": 0, "avg_price_change_bps": None},
    }
    action_changes: dict[str, list[float]] = {"buy": [], "sell": [], "hold": []}

    for row in rows:
        outcome = str(row["outcome"])
        action = str(row["predicted_action"])
        if outcome == "pending":
            pending += 1
            continue
        if outcome == "expired":
            expired += 1
            continue

        resolved += 1
        change_bps = float(row["price_change_bps"] or 0.0)
        action_changes.setdefault(action, []).append(change_bps)
        if action in action_stats:
            action_stats[action]["resolved"] += 1
        edge_values.append(forecast_edge_bps(action, change_bps))
        if outcome == "hit":
            hits += 1
            if action in action_stats:
                action_stats[action]["hits"] += 1
        else:
            misses += 1

    for action, changes in action_changes.items():
        if action not in action_stats:
            continue
        if changes:
            action_stats[action]["avg_price_change_bps"] = round(sum(changes) / len(changes), 4)
        resolved_count = int(action_stats[action]["resolved"])
        if resolved_count > 0:
            action_stats[action]["accuracy"] = round(float(action_stats[action]["hits"]) / resolved_count, 4)
        else:
            action_stats[action]["accuracy"] = None

    accuracy = (hits / resolved) if resolved > 0 else None
    avg_edge_bps = (sum(edge_values) / len(edge_values)) if edge_values else None
    predictive_go = bool(accuracy is not None and avg_edge_bps is not None and accuracy >= FORECAST_GO_MIN_ACCURACY and avg_edge_bps > 0)

    return {
        "generated_at": utc_now().isoformat(),
        "lookback_days": lookback_days,
        "window_start": window_start.isoformat(),
        "filters": {"horizon_minutes": horizon_minutes, "timeframe": timeframe},
        "total_forecasts": total,
        "resolved_forecasts": resolved,
        "pending_forecasts": pending,
        "expired_forecasts": expired,
        "hits": hits,
        "misses": misses,
        "accuracy": None if accuracy is None else round(accuracy, 4),
        "avg_edge_bps": None if avg_edge_bps is None else round(avg_edge_bps, 4),
        "go_threshold_accuracy": FORECAST_GO_MIN_ACCURACY,
        "predictive_go": predictive_go,
        "by_action": action_stats,
    }


def normalize_trade_action(action: str | None) -> str:
    normalized = (action or "").strip().lower()
    if normalized in {"buy", "sell", "hold"}:
        return normalized
    raise HTTPException(status_code=400, detail="action debe ser buy|sell|hold")


def normalize_hybrid_mode(mode: str | None) -> str:
    normalized = (mode or "").strip().lower()
    if normalized in {"shadow", "paper", "live"}:
        return normalized
    raise HTTPException(status_code=400, detail="mode debe ser shadow|paper|live")


def resolve_hybrid_action(
    quant_action: str,
    quant_confidence: float,
    ai_action: str,
    ai_confidence: float,
) -> tuple[str, float, bool, str]:
    if quant_action == "hold":
        return "hold", max(0.0, quant_confidence), ai_action == quant_action, "quant_hold"

    agreement = ai_action == quant_action
    if agreement and ai_confidence >= HYBRID_AI_MIN_CONFIDENCE:
        return quant_action, min(0.99, max(quant_confidence, ai_confidence)), True, "quant_ai_agree"

    if not HYBRID_REQUIRE_AI_AGREEMENT and quant_confidence >= HYBRID_QUANT_MIN_CONFIDENCE:
        return quant_action, min(0.99, max(0.05, quant_confidence)), agreement, "quant_primary_without_ai_agreement"

    return "hold", 0.0, agreement, "ai_disagree_or_low_confidence"


def build_hybrid_scorecard(
    cur: psycopg.Cursor,
    lookback_days: int,
    horizon_minutes: int | None,
    timeframe: str | None,
    mode: str,
) -> dict[str, Any]:
    window_start = utc_now() - timedelta(days=lookback_days)
    cur.execute(
        """
        select d.decision_id, d.quant_action, d.ai_action, d.hybrid_action,
               d.quant_confidence, d.ai_confidence, d.hybrid_confidence,
               d.agreement, d.decision_reason,
               f.price_change_bps, f.min_move_bps, f.outcome as forecast_outcome
        from hybrid_decisions d
        left join forecast_checks f
          on f.signal_id = d.signal_id
         and (%s::int is null or f.horizon_minutes = %s)
         and (%s::text is null or f.timeframe = %s)
        where d.created_at >= %s
          and d.mode = %s
        order by d.created_at desc
        """,
        (horizon_minutes, horizon_minutes, timeframe, timeframe, window_start, mode),
    )
    rows = cur.fetchall()

    total = len(rows)
    agreement_count = 0
    tradable = 0
    with_outcome = 0

    quant_hits = 0
    quant_misses = 0
    ai_hits = 0
    ai_misses = 0
    hybrid_hits = 0
    hybrid_misses = 0

    quant_edges: list[float] = []
    ai_edges: list[float] = []
    hybrid_edges: list[float] = []

    reason_counts: dict[str, int] = {}

    for row in rows:
        if bool(row["agreement"]):
            agreement_count += 1
        reason = str(row["decision_reason"])
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        if str(row["hybrid_action"]) in {"buy", "sell"}:
            tradable += 1

        if row["forecast_outcome"] not in {"hit", "miss"} or row["price_change_bps"] is None:
            continue

        with_outcome += 1
        change_bps = float(row["price_change_bps"])
        min_move_bps = float(row["min_move_bps"] or FORECAST_MIN_MOVE_BPS)

        quant_action = str(row["quant_action"])
        ai_action = str(row["ai_action"])
        hybrid_action = str(row["hybrid_action"])

        quant_outcome = forecast_outcome_for_move(quant_action, change_bps, min_move_bps)
        ai_outcome = forecast_outcome_for_move(ai_action, change_bps, min_move_bps)
        hybrid_outcome = forecast_outcome_for_move(hybrid_action, change_bps, min_move_bps)

        if quant_outcome == "hit":
            quant_hits += 1
        else:
            quant_misses += 1
        if ai_outcome == "hit":
            ai_hits += 1
        else:
            ai_misses += 1
        if hybrid_outcome == "hit":
            hybrid_hits += 1
        else:
            hybrid_misses += 1

        quant_edges.append(forecast_edge_bps(quant_action, change_bps))
        ai_edges.append(forecast_edge_bps(ai_action, change_bps))
        hybrid_edges.append(forecast_edge_bps(hybrid_action, change_bps))

    def metric_block(hits: int, misses: int, edges: list[float]) -> dict[str, Any]:
        resolved = hits + misses
        accuracy = (hits / resolved) if resolved > 0 else None
        avg_edge = (sum(edges) / len(edges)) if edges else None
        return {
            "hits": hits,
            "misses": misses,
            "resolved": resolved,
            "accuracy": None if accuracy is None else round(accuracy, 4),
            "avg_edge_bps": None if avg_edge is None else round(avg_edge, 4),
        }

    return {
        "generated_at": utc_now().isoformat(),
        "lookback_days": lookback_days,
        "window_start": window_start.isoformat(),
        "filters": {"mode": mode, "horizon_minutes": horizon_minutes, "timeframe": timeframe},
        "total_decisions": total,
        "tradable_decisions": tradable,
        "agreement_count": agreement_count,
        "agreement_rate": round((agreement_count / total), 4) if total > 0 else None,
        "decisions_with_outcome": with_outcome,
        "reason_counts": reason_counts,
        "quant": metric_block(quant_hits, quant_misses, quant_edges),
        "ai": metric_block(ai_hits, ai_misses, ai_edges),
        "hybrid": metric_block(hybrid_hits, hybrid_misses, hybrid_edges),
    }


def build_hybrid_alerts(scorecard: dict[str, Any]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    resolved = int(scorecard.get("hybrid", {}).get("resolved") or 0)
    accuracy = scorecard.get("hybrid", {}).get("accuracy")
    avg_edge_bps = scorecard.get("hybrid", {}).get("avg_edge_bps")

    if resolved < HYBRID_ALERT_MIN_RESOLVED:
        alerts.append(
            {
                "key": "hybrid_sample_low",
                "level": "warning",
                "message": f"Muestra híbrida insuficiente: {resolved} < {HYBRID_ALERT_MIN_RESOLVED}",
                "context": {
                    "resolved": resolved,
                    "required": HYBRID_ALERT_MIN_RESOLVED,
                    "filters": scorecard.get("filters", {}),
                },
            }
        )
        return alerts

    if accuracy is None or float(accuracy) < HYBRID_ALERT_MIN_ACCURACY:
        alerts.append(
            {
                "key": "hybrid_accuracy_low",
                "level": "critical",
                "message": f"Accuracy híbrida baja: {accuracy}",
                "context": {
                    "accuracy": accuracy,
                    "min_accuracy": HYBRID_ALERT_MIN_ACCURACY,
                    "resolved": resolved,
                    "filters": scorecard.get("filters", {}),
                },
            }
        )

    if avg_edge_bps is None or float(avg_edge_bps) <= HYBRID_ALERT_MIN_EDGE_BPS:
        alerts.append(
            {
                "key": "hybrid_edge_nonpositive",
                "level": "critical",
                "message": f"Edge híbrido no positivo: {avg_edge_bps}",
                "context": {
                    "avg_edge_bps": avg_edge_bps,
                    "min_edge_bps": HYBRID_ALERT_MIN_EDGE_BPS,
                    "resolved": resolved,
                    "filters": scorecard.get("filters", {}),
                },
            }
        )

    return alerts


def electrum_best_receive_address() -> str | None:
    if not ENABLE_ELECTRUM_RPC:
        return None
    for method in ("getunusedaddress", "getnewaddress"):
        try:
            result = electrum_rpc(method, [])
            if isinstance(result, str) and result:
                return result
        except Exception:
            continue
    return None


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
            kill_switch = get_kill_switch_state(cur)
            daily_realized_pnl = get_daily_realized_pnl(cur)
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
        "kill_switch_enabled": bool(kill_switch["enabled"]),
        "daily_realized_pnl_usd": round(daily_realized_pnl, 4),
        "daily_loss_limit_usd": DAILY_LOSS_LIMIT_USD,
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

        signal_ts = feature_row["ts"]
        cur.execute(
            """
            select signal_id
            from signals
            where ts = %s
              and symbol = %s
              and strategy_version = %s
            order by created_at desc, signal_id desc
            limit 1
            """,
            (signal_ts, req.symbol, req.feature_set_version),
        )
        existing_signal = cur.fetchone()

        if existing_signal:
            signal_id = str(existing_signal["signal_id"])
            cur.execute(
                """
                update signals
                set action = %s,
                    confidence = %s,
                    target_notional_usd = %s,
                    reason = %s
                where signal_id = %s
                """,
                (
                    action,
                    confidence,
                    target_notional,
                    reason,
                    signal_id,
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
                "deduped": True,
            }

        cur.execute(
            """
            insert into signals(
                signal_id, ts, symbol, strategy_version, action, confidence, target_notional_usd, reason, created_at
            )
            values(%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                signal_id,
                signal_ts,
                req.symbol,
                req.feature_set_version,
                action,
                confidence,
                target_notional,
                reason,
                signal_ts,
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
        "deduped": False,
    }


@app.post("/forecast/checkpoint")
def forecast_checkpoint(req: ForecastCheckpointRequest) -> dict[str, Any]:
    horizon = int(req.horizon_minutes)
    min_move_bps = float(req.min_move_bps)
    timeframe = (req.timeframe or "").strip() or MONITORED_TIMEFRAME

    if horizon < 1 or horizon > 120:
        raise HTTPException(status_code=400, detail="horizon_minutes debe estar entre 1 y 120")
    if min_move_bps < 0 or min_move_bps > 1000:
        raise HTTPException(status_code=400, detail="min_move_bps fuera de rango (0..1000)")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select signal_id, ts, symbol, action, confidence
            from signals
            where signal_id = %s
            """,
            (req.signal_id,),
        )
        signal = cur.fetchone()
        if not signal:
            raise HTTPException(status_code=404, detail="signal_id no encontrado")

        action = str(signal["action"])
        if action not in {"buy", "sell", "hold"}:
            raise HTTPException(status_code=400, detail="accion de señal invalida para forecast")

        symbol = str(signal["symbol"])
        signal_ts = signal["ts"]
        confidence = float(signal["confidence"])

        cur.execute(
            """
            select ts, close
            from market_candles
            where symbol = %s and timeframe = %s and ts <= %s
            order by ts desc
            limit 1
            """,
            (symbol, timeframe, signal_ts),
        )
        candle = cur.fetchone()
        if not candle:
            raise HTTPException(status_code=409, detail="no hay vela para fijar entry_price del forecast")

        entry_price = float(candle["close"])
        due_ts = signal_ts + timedelta(minutes=horizon)
        forecast_id = str(uuid.uuid4())
        metadata = dict(req.metadata or {})

        cur.execute(
            """
            insert into forecast_checks(
                forecast_id, signal_id, signal_ts, symbol, timeframe, predicted_action, predicted_confidence,
                horizon_minutes, min_move_bps, entry_price, due_ts, outcome, metadata, created_at, updated_at
            )
            values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s::jsonb, now(), now())
            on conflict(signal_id, timeframe, horizon_minutes) do nothing
            returning forecast_id, due_ts
            """,
            (
                forecast_id,
                req.signal_id,
                signal_ts,
                symbol,
                timeframe,
                action,
                confidence,
                horizon,
                min_move_bps,
                entry_price,
                due_ts,
                json.dumps(metadata),
            ),
        )
        inserted = cur.fetchone()

        if inserted:
            conn.commit()
            return {
                "ok": True,
                "created": True,
                "forecast_id": str(inserted["forecast_id"]),
                "signal_id": req.signal_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "action": action,
                "confidence": round(confidence, 4),
                "horizon_minutes": horizon,
                "min_move_bps": round(min_move_bps, 4),
                "entry_price": round(entry_price, 6),
                "signal_ts": signal_ts.isoformat(),
                "due_ts": inserted["due_ts"].isoformat(),
            }

        cur.execute(
            """
            select forecast_id, due_ts, outcome, entry_price
            from forecast_checks
            where signal_id = %s
              and timeframe = %s
              and horizon_minutes = %s
            limit 1
            """,
            (req.signal_id, timeframe, horizon),
        )
        existing = cur.fetchone()
        return {
            "ok": True,
            "created": False,
            "forecast_id": str(existing["forecast_id"]),
            "signal_id": req.signal_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "action": action,
            "confidence": round(confidence, 4),
            "horizon_minutes": horizon,
            "min_move_bps": round(min_move_bps, 4),
            "entry_price": round(float(existing["entry_price"]), 6),
            "signal_ts": signal_ts.isoformat(),
            "due_ts": existing["due_ts"].isoformat(),
            "status": str(existing["outcome"]),
        }


@app.post("/forecast/evaluate-due")
def forecast_evaluate_due(req: ForecastEvaluateDueRequest) -> dict[str, Any]:
    cap = max(1, min(int(req.limit), 1000))
    max_lag = int(req.max_resolution_lag_minutes)
    if max_lag < 1 or max_lag > 240:
        raise HTTPException(status_code=400, detail="max_resolution_lag_minutes debe estar entre 1 y 240")

    evaluated = 0
    hits = 0
    misses = 0
    expired = 0
    still_pending = 0
    samples: list[dict[str, Any]] = []

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select forecast_id, signal_id, symbol, timeframe, predicted_action, min_move_bps,
                   entry_price, due_ts
            from forecast_checks
            where outcome = 'pending'
              and due_ts <= now()
            order by due_ts asc
            limit %s
            for update skip locked
            """,
            (cap,),
        )
        rows = cur.fetchall()

        for row in rows:
            forecast_id = str(row["forecast_id"])
            symbol = str(row["symbol"])
            timeframe = str(row["timeframe"])
            action = str(row["predicted_action"])
            due_ts = row["due_ts"]
            entry_price = float(row["entry_price"])
            min_move_bps = float(row["min_move_bps"])

            cur.execute(
                """
                select ts, close
                from market_candles
                where symbol = %s
                  and timeframe = %s
                  and ts >= %s
                order by ts asc
                limit 1
                """,
                (symbol, timeframe, due_ts),
            )
            resolution = cur.fetchone()
            if not resolution:
                lag_minutes = minutes_since(due_ts)
                if lag_minutes is not None and lag_minutes > max_lag:
                    cur.execute(
                        """
                        update forecast_checks
                        set outcome = 'expired',
                            resolved_ts = now(),
                            updated_at = now()
                        where forecast_id = %s
                        """,
                        (forecast_id,),
                    )
                    expired += 1
                else:
                    still_pending += 1
                continue

            resolved_ts = resolution["ts"]
            resolved_price = float(resolution["close"])
            if entry_price <= 0:
                cur.execute(
                    """
                    update forecast_checks
                    set outcome = 'expired',
                        resolved_ts = %s,
                        resolved_price = %s,
                        updated_at = now()
                    where forecast_id = %s
                    """,
                    (resolved_ts, resolved_price, forecast_id),
                )
                expired += 1
                continue

            change_bps = ((resolved_price - entry_price) / entry_price) * 10000.0
            outcome = forecast_outcome_for_move(action, change_bps, min_move_bps)
            cur.execute(
                """
                update forecast_checks
                set outcome = %s,
                    resolved_ts = %s,
                    resolved_price = %s,
                    price_change_bps = %s,
                    updated_at = now()
                where forecast_id = %s
                """,
                (outcome, resolved_ts, resolved_price, change_bps, forecast_id),
            )

            evaluated += 1
            if outcome == "hit":
                hits += 1
            else:
                misses += 1

            if req.persist_events:
                insert_risk_event(
                    cur,
                    rule=f"forecast_{outcome}",
                    severity="info" if outcome == "hit" else "warning",
                    context={
                        "forecast_id": forecast_id,
                        "signal_id": row["signal_id"],
                        "action": action,
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "due_ts": due_ts.isoformat(),
                        "resolved_ts": resolved_ts.isoformat(),
                        "entry_price": entry_price,
                        "resolved_price": resolved_price,
                        "price_change_bps": round(change_bps, 4),
                        "min_move_bps": min_move_bps,
                        "outcome": outcome,
                    },
                )

            if len(samples) < 20:
                samples.append(
                    {
                        "forecast_id": forecast_id,
                        "action": action,
                        "outcome": outcome,
                        "price_change_bps": round(change_bps, 4),
                        "due_ts": due_ts.isoformat(),
                        "resolved_ts": resolved_ts.isoformat(),
                    }
                )

        conn.commit()

        cur.execute(
            """
            select count(*) as c
            from forecast_checks
            where outcome = 'pending'
              and due_ts <= now()
            """
        )
        due_pending_count = int(cur.fetchone()["c"])

    accuracy = (hits / evaluated) if evaluated > 0 else None
    return {
        "ok": True,
        "evaluated": evaluated,
        "hits": hits,
        "misses": misses,
        "expired": expired,
        "still_pending_without_price": still_pending,
        "due_pending_count": due_pending_count,
        "accuracy": None if accuracy is None else round(accuracy, 4),
        "samples": samples,
    }


@app.get("/forecast/scorecard")
def forecast_scorecard(
    lookback_days: int = 14,
    horizon_minutes: int | None = None,
    timeframe: str | None = None,
) -> dict[str, Any]:
    if lookback_days < 1 or lookback_days > 120:
        raise HTTPException(status_code=400, detail="lookback_days debe estar entre 1 y 120")
    if horizon_minutes is not None and (horizon_minutes < 1 or horizon_minutes > 120):
        raise HTTPException(status_code=400, detail="horizon_minutes debe estar entre 1 y 120")

    tf = None
    if timeframe is not None:
        tf = timeframe.strip()
        if not tf:
            tf = None

    with get_conn() as conn, conn.cursor() as cur:
        scorecard = build_forecast_scorecard(cur, lookback_days, horizon_minutes, tf)

    return {"ok": True, "scorecard": scorecard}


@app.post("/hybrid/decision")
def hybrid_decision(req: HybridDecisionRequest) -> dict[str, Any]:
    ai_action = normalize_trade_action(req.ai_action) if req.ai_action is not None else "hold"
    ai_confidence = max(0.0, min(0.99, float(req.ai_confidence if req.ai_confidence is not None else 0.0)))
    mode = normalize_hybrid_mode(req.mode)
    ai_source = (req.ai_source or "").strip() or "pending_molbot"
    ai_model = (req.ai_model or "").strip() or "unset"
    forecast_linked: dict[str, Any] | None = None

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select signal_id, ts, symbol, action, confidence
            from signals
            where signal_id = %s
            """,
            (req.signal_id,),
        )
        signal = cur.fetchone()
        if not signal:
            raise HTTPException(status_code=404, detail="signal_id no encontrado")

        quant_action = normalize_trade_action(signal["action"])
        quant_confidence = max(0.0, min(0.99, float(signal["confidence"])))
        symbol = str(signal["symbol"])
        signal_ts = signal["ts"]

        hybrid_action, hybrid_confidence, agreement, reason = resolve_hybrid_action(
            quant_action, quant_confidence, ai_action, ai_confidence
        )

        decision_id = str(uuid.uuid4())
        metadata = dict(req.metadata or {})
        metadata["hybrid_policy"] = {
            "require_ai_agreement": HYBRID_REQUIRE_AI_AGREEMENT,
            "ai_min_confidence": HYBRID_AI_MIN_CONFIDENCE,
            "quant_min_confidence": HYBRID_QUANT_MIN_CONFIDENCE,
        }

        if req.attach_forecast:
            horizon = int(req.forecast_horizon_minutes)
            min_move_bps = float(req.forecast_min_move_bps)
            timeframe = (req.forecast_timeframe or "").strip() or MONITORED_TIMEFRAME
            if horizon < 1 or horizon > 120:
                raise HTTPException(status_code=400, detail="forecast_horizon_minutes debe estar entre 1 y 120")
            if min_move_bps < 0 or min_move_bps > 1000:
                raise HTTPException(status_code=400, detail="forecast_min_move_bps fuera de rango (0..1000)")

            cur.execute(
                """
                select close
                from market_candles
                where symbol = %s
                  and timeframe = %s
                  and ts <= %s
                order by ts desc
                limit 1
                """,
                (symbol, timeframe, signal_ts),
            )
            candle = cur.fetchone()
            if candle:
                entry_price = float(candle["close"])
                due_ts = signal_ts + timedelta(minutes=horizon)
                forecast_id = str(uuid.uuid4())
                forecast_meta = {
                    "source": "hybrid_decision",
                    "mode": mode,
                    "ai_source": ai_source,
                    "decision_reason": reason,
                }
                cur.execute(
                    """
                    insert into forecast_checks(
                        forecast_id, signal_id, signal_ts, symbol, timeframe, predicted_action, predicted_confidence,
                        horizon_minutes, min_move_bps, entry_price, due_ts, outcome, metadata, created_at, updated_at
                    )
                    values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s::jsonb, now(), now())
                    on conflict(signal_id, timeframe, horizon_minutes) do nothing
                    returning forecast_id, due_ts
                    """,
                    (
                        forecast_id,
                        req.signal_id,
                        signal_ts,
                        symbol,
                        timeframe,
                        quant_action,
                        quant_confidence,
                        horizon,
                        min_move_bps,
                        entry_price,
                        due_ts,
                        json.dumps(forecast_meta),
                    ),
                )
                inserted_forecast = cur.fetchone()
                if inserted_forecast:
                    forecast_linked = {
                        "created": True,
                        "forecast_id": str(inserted_forecast["forecast_id"]),
                        "timeframe": timeframe,
                        "horizon_minutes": horizon,
                        "due_ts": inserted_forecast["due_ts"].isoformat(),
                    }
                else:
                    cur.execute(
                        """
                        select forecast_id, due_ts, outcome
                        from forecast_checks
                        where signal_id = %s
                          and timeframe = %s
                          and horizon_minutes = %s
                        limit 1
                        """,
                        (req.signal_id, timeframe, horizon),
                    )
                    existing_forecast = cur.fetchone()
                    if existing_forecast:
                        forecast_linked = {
                            "created": False,
                            "forecast_id": str(existing_forecast["forecast_id"]),
                            "timeframe": timeframe,
                            "horizon_minutes": horizon,
                            "due_ts": existing_forecast["due_ts"].isoformat(),
                            "status": str(existing_forecast["outcome"]),
                        }
            else:
                forecast_linked = {"created": False, "detail": "no_hay_vela_para_signal_ts"}

        cur.execute(
            """
            insert into hybrid_decisions(
                decision_id, signal_id, signal_ts, symbol,
                quant_action, quant_confidence,
                ai_action, ai_confidence, ai_reason, ai_model, ai_source,
                agreement, hybrid_action, hybrid_confidence, decision_reason,
                mode, metadata, created_at, updated_at
            )
            values(
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s::jsonb, now(), now()
            )
            on conflict(signal_id, mode, ai_source) do update
                set quant_action = excluded.quant_action,
                    quant_confidence = excluded.quant_confidence,
                    ai_action = excluded.ai_action,
                    ai_confidence = excluded.ai_confidence,
                    ai_reason = excluded.ai_reason,
                    ai_model = excluded.ai_model,
                    agreement = excluded.agreement,
                    hybrid_action = excluded.hybrid_action,
                    hybrid_confidence = excluded.hybrid_confidence,
                    decision_reason = excluded.decision_reason,
                    metadata = excluded.metadata,
                    updated_at = now()
            returning decision_id
            """,
            (
                decision_id,
                req.signal_id,
                signal_ts,
                symbol,
                quant_action,
                quant_confidence,
                ai_action,
                ai_confidence,
                req.ai_reason,
                ai_model,
                ai_source,
                agreement,
                hybrid_action,
                hybrid_confidence,
                reason,
                mode,
                json.dumps(metadata),
            ),
        )
        decision_row = cur.fetchone()
        conn.commit()

    return {
        "ok": True,
        "decision_id": str(decision_row["decision_id"]),
        "signal_id": req.signal_id,
        "symbol": symbol,
        "mode": mode,
        "quant": {"action": quant_action, "confidence": round(quant_confidence, 4)},
        "ai": {"action": ai_action, "confidence": round(ai_confidence, 4), "source": ai_source, "model": ai_model},
        "agreement": agreement,
        "hybrid": {"action": hybrid_action, "confidence": round(hybrid_confidence, 4), "reason": reason},
        "forecast_linked": forecast_linked,
        "execution": "shadow_only" if mode == "shadow" else "manual_gate_required",
    }


@app.get("/hybrid/decisions")
def hybrid_decisions(mode: str = HYBRID_MODE, limit: int = 50) -> dict[str, Any]:
    selected_mode = normalize_hybrid_mode(mode)
    cap = max(1, min(int(limit), 200))
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select decision_id, signal_id, signal_ts, symbol,
                   quant_action, quant_confidence,
                   ai_action, ai_confidence, ai_reason, ai_model, ai_source,
                   agreement, hybrid_action, hybrid_confidence, decision_reason,
                   mode, metadata, created_at, updated_at
            from hybrid_decisions
            where mode = %s
            order by created_at desc
            limit %s
            """,
            (selected_mode, cap),
        )
        rows = cur.fetchall()
    return {"ok": True, "mode": selected_mode, "count": len(rows), "items": rows}


@app.get("/hybrid/scorecard")
def hybrid_scorecard(
    lookback_days: int = 7,
    mode: str = HYBRID_MODE,
    horizon_minutes: int | None = 10,
    timeframe: str | None = "5m",
) -> dict[str, Any]:
    if lookback_days < 1 or lookback_days > 120:
        raise HTTPException(status_code=400, detail="lookback_days debe estar entre 1 y 120")
    selected_mode = normalize_hybrid_mode(mode)
    if horizon_minutes is not None and (horizon_minutes < 1 or horizon_minutes > 120):
        raise HTTPException(status_code=400, detail="horizon_minutes debe estar entre 1 y 120")
    tf = None
    if timeframe is not None:
        tf = timeframe.strip()
        if not tf:
            tf = None

    with get_conn() as conn, conn.cursor() as cur:
        scorecard = build_hybrid_scorecard(cur, lookback_days, horizon_minutes, tf, selected_mode)

    return {"ok": True, "scorecard": scorecard}


@app.post("/hybrid/ai/fallback")
def hybrid_ai_fallback(req: HybridAiFallbackRequest) -> dict[str, Any]:
    quant_action = normalize_trade_action(req.quant_action)
    quant_confidence = max(0.0, min(0.99, float(req.quant_confidence)))
    ai_action = quant_action
    ai_confidence = max(0.55, quant_confidence)
    ai_reason = "fallback_rule_same_as_quant"
    if quant_action == "hold":
        ai_confidence = max(0.55, quant_confidence)
        ai_reason = "fallback_hold_no_external_ai"

    return {
        "ok": True,
        "signal_id": req.signal_id,
        "ai_action": ai_action,
        "ai_confidence": round(ai_confidence, 4),
        "ai_reason": ai_reason,
        "ai_model": "strategy_fallback_rule",
        "ai_source": "strategy_fallback",
    }


@app.post("/hybrid/alerts/evaluate")
def hybrid_alerts_evaluate(req: HybridAlertEvaluateRequest) -> dict[str, Any]:
    if req.lookback_days < 1 or req.lookback_days > 120:
        raise HTTPException(status_code=400, detail="lookback_days debe estar entre 1 y 120")
    selected_mode = normalize_hybrid_mode(req.mode)
    horizon = int(req.horizon_minutes)
    if horizon < 1 or horizon > 120:
        raise HTTPException(status_code=400, detail="horizon_minutes debe estar entre 1 y 120")
    timeframe = (req.timeframe or "").strip() or MONITORED_TIMEFRAME

    with get_conn() as conn, conn.cursor() as cur:
        scorecard = build_hybrid_scorecard(cur, req.lookback_days, horizon, timeframe, selected_mode)
        alerts = build_hybrid_alerts(scorecard)
        persisted: list[dict[str, Any]] = []
        if req.persist and alerts:
            persisted = persist_ops_alerts(cur, alerts)
            conn.commit()

    critical_count = sum(1 for a in alerts if a["level"] == "critical")
    warning_count = sum(1 for a in alerts if a["level"] == "warning")
    return {
        "ok": True,
        "evaluated_at": utc_now().isoformat(),
        "alert_count": len(alerts),
        "critical_count": critical_count,
        "warning_count": warning_count,
        "persisted_count": len(persisted),
        "alerts": alerts,
        "scorecard": scorecard if req.include_scorecard else None,
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


@app.get("/ops/summary")
def ops_summary() -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        snapshot = get_ops_snapshot(cur)

    return {
        "ok": True,
        "snapshot": snapshot,
        "thresholds": {
            "market_data_stale_minutes": MARKET_DATA_STALE_MINUTES,
            "features_data_stale_minutes": FEATURES_DATA_STALE_MINUTES,
            "reconcile_stale_minutes": RECONCILE_STALE_MINUTES,
            "rejected_orders_1h_warn_threshold": REJECTED_ORDERS_1H_WARN_THRESHOLD,
            "daily_loss_limit_usd": DAILY_LOSS_LIMIT_USD,
            "alert_cooldown_minutes": ALERT_COOLDOWN_MINUTES,
        },
    }


@app.post("/alerts/evaluate")
def alerts_evaluate(req: AlertEvaluateRequest) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        snapshot = get_ops_snapshot(cur)
        alerts = build_ops_alerts(snapshot)
        persisted: list[dict[str, Any]] = []

        if req.persist and alerts:
            persisted = persist_ops_alerts(cur, alerts)
            conn.commit()

    critical_count = sum(1 for a in alerts if a["level"] == "critical")
    warning_count = sum(1 for a in alerts if a["level"] == "warning")

    return {
        "ok": True,
        "evaluated_at": utc_now().isoformat(),
        "alert_count": len(alerts),
        "critical_count": critical_count,
        "warning_count": warning_count,
        "persisted_count": len(persisted),
        "alerts": alerts,
        "snapshot": snapshot if req.include_snapshot else None,
    }


@app.get("/paper/scorecard")
def paper_scorecard(lookback_days: int = PAPER_GO_NO_GO_LOOKBACK_DAYS) -> dict[str, Any]:
    if lookback_days < 1 or lookback_days > 120:
        raise HTTPException(status_code=400, detail="lookback_days debe estar entre 1 y 120")

    with get_conn() as conn, conn.cursor() as cur:
        scorecard = build_paper_scorecard(cur, lookback_days)

    return {"ok": True, "scorecard": scorecard}


@app.post("/paper/go-no-go")
def paper_go_no_go(req: PaperGoNoGoRequest) -> dict[str, Any]:
    if req.lookback_days < 1 or req.lookback_days > 120:
        raise HTTPException(status_code=400, detail="lookback_days debe estar entre 1 y 120")

    with get_conn() as conn, conn.cursor() as cur:
        scorecard = build_paper_scorecard(cur, req.lookback_days)
        evaluation = evaluate_paper_go_no_go(scorecard)
        evaluation_id = None

        if req.persist:
            evaluation_id = persist_paper_evaluation(cur, req.lookback_days, scorecard, evaluation)
            conn.commit()

    return {
        "ok": True,
        "evaluation_id": evaluation_id,
        "decision": evaluation["decision"],
        "go": evaluation["go"],
        "failed_criteria": evaluation["failed_criteria"],
        "criteria": evaluation["criteria"],
        "scorecard": scorecard if req.include_scorecard else None,
    }


@app.get("/risk/controls")
def risk_controls() -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        kill_switch = get_kill_switch_state(cur)
        daily_realized_pnl = get_daily_realized_pnl(cur)
        daily_loss_usd = max(0.0, -daily_realized_pnl)

    return {
        "ok": True,
        "kill_switch": kill_switch,
        "daily_realized_pnl_usd": round(daily_realized_pnl, 4),
        "daily_loss_usd": round(daily_loss_usd, 4),
        "daily_loss_limit_usd": DAILY_LOSS_LIMIT_USD,
    }


@app.post("/risk/kill-switch")
def set_kill_switch(req: KillSwitchSetRequest) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        set_kill_switch_state(cur, req.enabled, req.reason, req.metadata)
        insert_risk_event(
            cur,
            rule="kill_switch_manual_change",
            severity="high" if req.enabled else "info",
            context={"enabled": req.enabled, "reason": req.reason, "metadata": req.metadata},
        )
        kill_switch = get_kill_switch_state(cur)
        conn.commit()

    return {"ok": True, "kill_switch": kill_switch}


@app.get("/execution/intents")
def execution_intents(status: str | None = None, limit: int = 50) -> dict[str, Any]:
    allowed = {"open", "filled", "rejected", "canceled", "settled"}
    status_filter = None
    if status is not None:
        status_filter = status.strip().lower()
        if status_filter not in allowed:
            raise HTTPException(status_code=400, detail="status invalido")

    cap = max(1, min(int(limit), 200))
    with get_conn() as conn, conn.cursor() as cur:
        if status_filter is None:
            cur.execute(
                """
                select intent_id, order_id, signal_id, symbol, side, target_notional_usd,
                       reference_price, expected_qty, status, source, txid, external_ref,
                       notes, metadata, created_at, updated_at, confirmed_at
                from external_execution_intents
                order by created_at desc
                limit %s
                """,
                (cap,),
            )
        else:
            cur.execute(
                """
                select intent_id, order_id, signal_id, symbol, side, target_notional_usd,
                       reference_price, expected_qty, status, source, txid, external_ref,
                       notes, metadata, created_at, updated_at, confirmed_at
                from external_execution_intents
                where status = %s
                order by created_at desc
                limit %s
                """,
                (status_filter, cap),
            )
        rows = cur.fetchall()
    return {"ok": True, "count": len(rows), "items": rows}


@app.post("/execution/intent")
def execution_intent(req: ExecutionIntentRequest) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select signal_id, symbol, action, target_notional_usd, ts
            from signals
            where signal_id = %s
            """,
            (req.signal_id,),
        )
        signal = cur.fetchone()
        if not signal:
            raise HTTPException(status_code=404, detail="signal_id no encontrado")

        action = str(signal["action"])
        symbol = str(signal["symbol"])
        target_notional = float(signal["target_notional_usd"])
        signal_ts = signal["ts"]

        if action not in {"buy", "sell"}:
            return {
                "ok": True,
                "created": False,
                "status": "skipped",
                "reason": "accion_no_ejecutable",
                "signal_id": req.signal_id,
                "action": action,
            }

        risk = evaluate_risk(cur, symbol, action, target_notional)
        reference_price = latest_price(cur, symbol)
        expected_qty = (target_notional / reference_price) if reference_price > 0 else 0.0

        order_id = str(uuid.uuid4())
        intent_id = str(uuid.uuid4())
        receive_address = electrum_best_receive_address()

        if not risk["approved"]:
            cur.execute(
                """
                insert into orders(
                    order_id, signal_id, venue, venue_order_id, symbol, side, type,
                    qty, requested_notional_usd, status, metadata, created_at
                )
                values(%s, %s, %s, %s, %s, %s, %s, 0, %s, %s, %s::jsonb, %s)
                """,
                (
                    order_id,
                    req.signal_id,
                    "external_no_kyc",
                    f"intent-{order_id}",
                    symbol,
                    action,
                    "manual",
                    target_notional,
                    "rejected",
                    json.dumps({"risk": risk, "mode": "no_kyc_intent"}),
                    signal_ts,
                ),
            )
            insert_risk_event(
                cur,
                rule="execution_intent_blocked_by_risk",
                severity="high",
                context={"signal_id": req.signal_id, "risk": risk},
            )
            conn.commit()
            return {
                "ok": False,
                "created": False,
                "status": "rejected",
                "signal_id": req.signal_id,
                "risk": risk,
            }

        cur.execute(
            """
            insert into orders(
                order_id, signal_id, venue, venue_order_id, symbol, side, type,
                qty, requested_notional_usd, status, metadata, created_at
            )
            values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                order_id,
                req.signal_id,
                "external_no_kyc",
                f"intent-{order_id}",
                symbol,
                action,
                "manual",
                expected_qty,
                target_notional,
                "submitted",
                json.dumps(
                    {
                        "mode": "no_kyc_intent",
                        "reference_price": reference_price,
                        "risk": risk,
                        "receive_address": receive_address,
                    }
                ),
                signal_ts,
            ),
        )

        cur.execute(
            """
            insert into external_execution_intents(
                intent_id, order_id, signal_id, symbol, side, target_notional_usd,
                reference_price, expected_qty, status, source, notes, metadata, created_at, updated_at
            )
            values(%s, %s, %s, %s, %s, %s, %s, %s, 'open', %s, %s, %s::jsonb, %s, %s)
            """,
            (
                intent_id,
                order_id,
                req.signal_id,
                symbol,
                action,
                target_notional,
                reference_price,
                expected_qty,
                req.source,
                req.note,
                json.dumps({"risk": risk, "receive_address": receive_address}),
                signal_ts,
                signal_ts,
            ),
        )
        conn.commit()

    return {
        "ok": True,
        "created": True,
        "intent_id": intent_id,
        "order_id": order_id,
        "signal_id": req.signal_id,
        "symbol": symbol,
        "side": action,
        "target_notional_usd": round(target_notional, 4),
        "reference_price": round(reference_price, 4),
        "expected_qty": round(expected_qty, 8),
        "receive_address_hint": receive_address,
        "instructions": "Ejecutar trade no-KYC externamente y luego confirmar por /execution/intent/confirm",
    }


@app.post("/execution/intent/confirm")
def execution_intent_confirm(req: ExecutionIntentConfirmRequest) -> dict[str, Any]:
    status = normalize_intent_status(req.status)
    confirmed_at = req.confirmed_at or utc_now()

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select i.intent_id, i.order_id, i.signal_id, i.symbol, i.side, i.target_notional_usd,
                   i.reference_price, i.expected_qty, i.status as intent_status, i.txid,
                   i.external_ref, i.metadata as intent_metadata,
                   o.status as order_status, o.metadata as order_metadata
            from external_execution_intents i
            join orders o on o.order_id = i.order_id
            where i.intent_id = %s
            for update
            """,
            (req.intent_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="intent_id no encontrado")

        intent_status = str(row["intent_status"])
        if intent_status in {"filled", "rejected", "canceled", "settled"}:
            return {"ok": True, "updated": False, "intent_id": req.intent_id, "status": intent_status}

        order_metadata = dict(row["order_metadata"] or {})
        intent_metadata = dict(row["intent_metadata"] or {})
        order_metadata["confirmation"] = {
            "status": status,
            "txid": req.txid,
            "external_ref": req.external_ref,
            "confirmed_at": confirmed_at.isoformat(),
            "metadata": req.metadata,
        }
        intent_metadata.update(req.metadata or {})

        next_intent_status = status
        next_order_status = status

        if status == "filled":
            side = str(row["side"])
            symbol = str(row["symbol"])
            fill_price = float(req.fill_price if req.fill_price is not None else row["reference_price"])
            filled_qty = float(req.filled_qty if req.filled_qty is not None else row["expected_qty"])
            fee = max(0.0, float(req.fee))
            fee_asset = req.fee_asset or "USD"

            if fill_price <= 0 or filled_qty <= 0:
                raise HTTPException(status_code=400, detail="fill_price y filled_qty deben ser positivos")

            cur.execute("select qty, avg_entry from positions where symbol = %s", (symbol,))
            pos = cur.fetchone()
            position_qty = float(pos["qty"]) if pos else 0.0
            position_avg = float(pos["avg_entry"]) if pos else 0.0

            tx_or_ref = req.txid or row["txid"] or f"intent-fill-{row['order_id']}"
            realized_pnl = compute_realized_pnl(side, filled_qty, fill_price, fee, position_qty, position_avg)

            cur.execute(
                """
                update orders
                set status = 'filled',
                    qty = %s,
                    venue_order_id = %s,
                    metadata = %s::jsonb,
                    updated_at = %s
                where order_id = %s
                """,
                (filled_qty, tx_or_ref, json.dumps(order_metadata), confirmed_at, row["order_id"]),
            )
            cur.execute(
                """
                insert into fills(fill_id, order_id, price, qty, fee, fee_asset, notional_usd, realized_pnl_usd, ts)
                values(%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    row["order_id"],
                    fill_price,
                    filled_qty,
                    fee,
                    fee_asset,
                    filled_qty * fill_price,
                    realized_pnl,
                    confirmed_at,
                ),
            )
            update_position(cur, symbol, side, filled_qty, fill_price)
            next_intent_status = "filled"
            next_order_status = "filled"
            insert_risk_event(
                cur,
                rule="no_kyc_intent_filled",
                severity="info",
                context={
                    "intent_id": req.intent_id,
                    "order_id": row["order_id"],
                    "txid": req.txid,
                    "fill_price": fill_price,
                    "filled_qty": filled_qty,
                },
            )
        else:
            cur.execute(
                """
                update orders
                set status = %s,
                    metadata = %s::jsonb,
                    updated_at = %s
                where order_id = %s
                """,
                (next_order_status, json.dumps(order_metadata), confirmed_at, row["order_id"]),
            )
            insert_risk_event(
                cur,
                rule="no_kyc_intent_not_filled",
                severity="high" if status == "rejected" else "info",
                context={
                    "intent_id": req.intent_id,
                    "order_id": row["order_id"],
                    "status": status,
                    "txid": req.txid,
                },
            )

        cur.execute(
            """
            update external_execution_intents
            set status = %s,
                txid = coalesce(%s, txid),
                external_ref = coalesce(%s, external_ref),
                metadata = %s::jsonb,
                confirmed_at = %s,
                updated_at = %s
            where intent_id = %s
            """,
            (
                next_intent_status,
                req.txid,
                req.external_ref,
                json.dumps(intent_metadata),
                confirmed_at,
                confirmed_at,
                req.intent_id,
            ),
        )
        conn.commit()

    return {
        "ok": True,
        "updated": True,
        "intent_id": req.intent_id,
        "status": next_intent_status,
        "order_status": next_order_status,
        "confirmed_at": confirmed_at.isoformat(),
    }


@app.post("/execution/intents/reconcile-electrum")
def execution_intents_reconcile_electrum(req: IntentElectrumReconcileRequest) -> dict[str, Any]:
    cap = max(1, min(int(req.limit), 200))
    if not ENABLE_ELECTRUM_RPC:
        return {"ok": False, "enabled": False, "detail": "Electrum RPC deshabilitado", "checked": 0, "updated": 0}

    checked = 0
    updated = 0
    settled = 0
    failures: list[dict[str, Any]] = []
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select intent_id, txid, status, metadata
            from external_execution_intents
            where txid is not null
              and status in ('open', 'filled')
            order by updated_at asc
            limit %s
            """,
            (cap,),
        )
        rows = cur.fetchall()
        for row in rows:
            checked += 1
            intent_id = str(row["intent_id"])
            txid = str(row["txid"])
            current_status = str(row["status"])
            current_meta = dict(row["metadata"] or {})
            try:
                tx_data = electrum_rpc("gettransaction", [txid])
                confirmations = None
                if isinstance(tx_data, dict) and tx_data.get("confirmations") is not None:
                    confirmations = int(tx_data["confirmations"])
                current_meta["electrum_reconcile"] = {
                    "last_check_at": utc_now().isoformat(),
                    "confirmations": confirmations,
                    "txid": txid,
                }
                new_status = current_status
                if current_status == "filled" and confirmations is not None and confirmations > 0:
                    new_status = "settled"
                cur.execute(
                    """
                    update external_execution_intents
                    set status = %s,
                        metadata = %s::jsonb,
                        updated_at = now()
                    where intent_id = %s
                    """,
                    (new_status, json.dumps(current_meta), intent_id),
                )
                updated += 1
                if new_status == "settled" and current_status != "settled":
                    settled += 1
            except Exception as exc:
                failures.append({"intent_id": intent_id, "txid": txid, "error": str(exc)})
        conn.commit()

    return {
        "ok": True,
        "enabled": True,
        "checked": checked,
        "updated": updated,
        "settled": settled,
        "failures": failures[:20],
    }


@app.post("/execution/order")
def execution_order(req: ExecutionOrderRequest) -> dict[str, Any]:
    if TRADING_MODE not in {"paper", "live"}:
        raise HTTPException(status_code=500, detail=f"TRADING_MODE invalido: {TRADING_MODE}")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select signal_id, symbol, action, target_notional_usd
                 , ts
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
        signal_ts = signal["ts"]

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
                    qty, requested_notional_usd, status, metadata, created_at
                )
                values(%s, %s, %s, %s, %s, %s, %s, 0, %s, %s, %s::jsonb, %s)
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
                    signal_ts,
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
                qty, requested_notional_usd, status, metadata, created_at
            )
            values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
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
                signal_ts,
            ),
        )

        cur.execute("select qty, avg_entry from positions where symbol = %s", (symbol,))
        position_before = cur.fetchone()
        position_qty = float(position_before["qty"]) if position_before else 0.0
        position_avg = float(position_before["avg_entry"]) if position_before else 0.0

        if order_status == "filled" and executed_qty > 0:
            fill_id = str(uuid.uuid4())
            realized_pnl = compute_realized_pnl(side, executed_qty, fill_price, fee, position_qty, position_avg)
            cur.execute(
                """
                insert into fills(fill_id, order_id, price, qty, fee, fee_asset, notional_usd, realized_pnl_usd, ts)
                values(%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (fill_id, order_id, fill_price, executed_qty, fee, fee_asset, executed_qty * fill_price, realized_pnl, signal_ts),
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

        upsert_heartbeat(
            cur,
            component="reconcile_loop",
            status="ok",
            payload={"signal_count": signal_count, "orders_by_status": by_status},
        )
        cur.execute(
            """
            insert into ops_heartbeat_log(id, component, ts, status, payload)
            values(%s, %s, now(), %s, %s::jsonb)
            """,
            (
                str(uuid.uuid4()),
                "reconcile_loop",
                "ok",
                json.dumps({"signal_count": signal_count, "orders_by_status": by_status}),
            ),
        )
        conn.commit()

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
