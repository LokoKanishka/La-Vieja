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

    uptime_window_days = max(0.01, min(float(lookback_days), runtime_days if runtime_days > 0 else float(lookback_days)))
    expected_heartbeat_count = max(
        1,
        int((uptime_window_days * 24 * 60) / max(1, RECONCILE_HEARTBEAT_INTERVAL_MINUTES)),
    )
    cur.execute(
        """
        select count(*) as c
        from ops_heartbeat_log
        where component = 'reconcile_loop'
          and status = 'ok'
          and ts >= %s
        """,
        (window_start,),
    )
    reconcile_heartbeat_ok = int(cur.fetchone()["c"])
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
        "reconcile_uptime_pct": round(reconcile_uptime_pct, 2),
        "critical_ops_alerts_24h": critical_ops_alerts_24h,
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
            float(scorecard["critical_ops_alerts_24h"]),
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
                values(%s, %s, %s, %s, %s, %s, %s, %s, now())
                """,
                (fill_id, order_id, fill_price, executed_qty, fee, fee_asset, executed_qty * fill_price, realized_pnl),
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
