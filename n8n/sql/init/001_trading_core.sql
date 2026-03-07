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
