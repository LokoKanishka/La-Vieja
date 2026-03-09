create table if not exists market_candles (
  ts timestamptz not null,
  venue text not null,
  symbol text not null,
  timeframe text not null,
  open numeric not null,
  high numeric not null,
  low numeric not null,
  close numeric not null,
  volume numeric not null default 0,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (ts, venue, symbol, timeframe)
);

create index if not exists idx_market_candles_symbol_ts
  on market_candles (symbol, ts desc);

create table if not exists onchain_metrics (
  ts timestamptz not null,
  source text not null,
  metric text not null,
  value numeric not null,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (ts, source, metric)
);

create index if not exists idx_onchain_metrics_metric_ts
  on onchain_metrics (metric, ts desc);

create table if not exists features (
  ts timestamptz not null,
  symbol text not null,
  feature_set_version text not null,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (ts, symbol, feature_set_version)
);

create index if not exists idx_features_symbol_ts
  on features (symbol, ts desc);

create table if not exists signals (
  signal_id uuid primary key,
  ts timestamptz not null,
  symbol text not null,
  strategy_version text not null,
  action text not null check (action in ('buy', 'sell', 'hold')),
  confidence numeric not null,
  target_notional_usd numeric not null,
  reason text,
  created_at timestamptz not null default now()
);

create index if not exists idx_signals_symbol_ts
  on signals (symbol, ts desc);

create table if not exists orders (
  order_id uuid primary key,
  signal_id uuid references signals(signal_id),
  venue text not null,
  venue_order_id text unique,
  symbol text not null,
  side text not null check (side in ('buy', 'sell')),
  type text not null,
  qty numeric not null,
  requested_notional_usd numeric not null default 0,
  status text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_orders_status_created
  on orders (status, created_at desc);

create table if not exists fills (
  fill_id uuid primary key,
  order_id uuid references orders(order_id),
  price numeric not null,
  qty numeric not null,
  fee numeric not null,
  fee_asset text not null,
  notional_usd numeric not null,
  realized_pnl_usd numeric not null default 0,
  ts timestamptz not null
);

create index if not exists idx_fills_ts
  on fills (ts desc);

create table if not exists positions (
  symbol text primary key,
  qty numeric not null,
  avg_entry numeric not null,
  unrealized_pnl numeric not null default 0,
  updated_at timestamptz not null default now()
);

create table if not exists risk_events (
  id uuid primary key,
  ts timestamptz not null,
  rule text not null,
  severity text not null,
  context jsonb not null
);

create index if not exists idx_risk_events_ts
  on risk_events (ts desc);

create table if not exists risk_controls (
  control_key text primary key,
  enabled boolean not null default false,
  reason text not null default '',
  metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

insert into risk_controls(control_key, enabled, reason, metadata)
values('global_kill_switch', false, 'sql_default', '{"source":"sql_init"}'::jsonb)
on conflict(control_key) do nothing;

create table if not exists ops_heartbeats (
  component text primary key,
  last_seen_at timestamptz not null,
  status text not null,
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists ops_alert_state (
  alert_key text primary key,
  last_level text not null,
  last_message text not null,
  last_payload jsonb not null default '{}'::jsonb,
  last_fired_at timestamptz not null,
  updated_at timestamptz not null default now()
);

create table if not exists ops_heartbeat_log (
  id uuid primary key,
  component text not null,
  ts timestamptz not null default now(),
  status text not null,
  payload jsonb not null default '{}'::jsonb
);

create index if not exists idx_ops_heartbeat_log_component_ts
  on ops_heartbeat_log (component, ts desc);

create table if not exists paper_evaluations (
  evaluation_id uuid primary key,
  ts timestamptz not null default now(),
  lookback_days int not null,
  decision text not null check (decision in ('go', 'no_go')),
  scorecard jsonb not null,
  criteria jsonb not null
);

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
);

create index if not exists idx_external_execution_intents_status_created
  on external_execution_intents (status, created_at desc);

create index if not exists idx_external_execution_intents_txid
  on external_execution_intents (txid);

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
);

create index if not exists idx_forecast_checks_outcome_due
  on forecast_checks (outcome, due_ts asc);

create index if not exists idx_forecast_checks_created
  on forecast_checks (created_at desc);

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
);

create index if not exists idx_hybrid_decisions_created
  on hybrid_decisions (created_at desc);

create index if not exists idx_hybrid_decisions_mode_created
  on hybrid_decisions (mode, created_at desc);
