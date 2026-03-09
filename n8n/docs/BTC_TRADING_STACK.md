# BTC Trading Stack (n8n + Postgres + Strategy Service)

Este stack implementa la fase central del proyecto:

- Ingesta de datos BTC y métricas on-chain.
- Feature engineering.
- Generación de señal.
- Control de riesgo.
- Ejecución paper automatizada.
- Reconciliación.
- Sweep de custodia (controlado).

## 1) Arranque

```bash
cd /home/lucy/Escritorio/La Vieja
cp n8n/.env.trading.example n8n/.env.trading
# editar secretos y límites
sh n8n/scripts/trading_up.sh
```

Modo cero pesos (regla cyberpunk):

```bash
bash n8n/scripts/no_kyc_lockdown.sh
bash n8n/scripts/zero_cost_guard.sh
```

Health checks:

```bash
curl -s http://127.0.0.1:8100/health
curl -s http://127.0.0.1:5111
```

## 2) Importar workflows

Requiere API Key de n8n:

```bash
export N8N_API_KEY="tu_api_key"
sh n8n/scripts/import_trading_workflows_api.sh
```

Workflows incluidos:

- `BTC Ingest Market 5m`
- `BTC Feature Engineering 15m`
- `BTC Signal Risk Execute 15m`
- `BTC Reconcile 1m`
- `BTC Custody Sweep Daily`
- `BTC Ops Monitor 1m`
- `BTC Paper Go No-Go Daily`
- `BTC Intents Reconcile Electrum 5m`
- `BTC Forecast Validate 5m`
- `BTC Hybrid Shadow 5m`

## 3) Proceso automático

1. Ingesta trae precio BTC (CoinGecko) y fees (mempool.space).
2. Features calcula SMA, momentum, volatilidad.
3. Señal define `buy/sell/hold`.
4. Riesgo valida límites (`max position`, `max orders/hour`, `daily loss`).
5. Ejecución paper guarda `orders`, `fills`, `positions`.
6. Reconciliación reporta estados y posiciones.
7. Sweep diario queda bloqueado fuera de `live`.

## 4) Endpoints principales (`strategy_service`)

- `POST /ingest/market`
- `POST /ingest/onchain`
- `POST /features/build`
- `POST /signal/evaluate`
- `POST /risk/check`
- `GET /risk/controls`
- `POST /risk/kill-switch`
- `GET /ops/summary`
- `POST /alerts/evaluate`
- `GET /paper/scorecard`
- `POST /paper/go-no-go`
- `POST /execution/order`
- `POST /execution/intent`
- `POST /execution/intent/confirm`
- `GET /execution/intents`
- `POST /execution/intents/reconcile-electrum`
- `POST /forecast/checkpoint`
- `POST /forecast/evaluate-due`
- `GET /forecast/scorecard`
- `POST /hybrid/decision`
- `GET /hybrid/decisions`
- `GET /hybrid/scorecard`
- `POST /reconcile`
- `POST /custody/sweep`
- `GET /electrum/balance`
- `POST /electrum/rpc`

## 5) Electrum en esta arquitectura

Electrum se integra para custodia y operaciones de wallet por RPC.

No se usa como motor de órdenes de compra/venta en mercado. El trading real requiere API de exchange con firma y gestión de ejecución.

Variables relevantes:

- `ENABLE_ELECTRUM_RPC=true`
- `ELECTRUM_RPC_URL=http://host:port`
- `ELECTRUM_RPC_USER=...`
- `ELECTRUM_RPC_PASSWORD=...`

## 6) Paso a real (controlado)

Estado actual por seguridad:

- `TRADING_MODE=paper` ejecuta paper trading.
- `TRADING_MODE=live` requiere `EXCHANGE_ADAPTER=ccxt` y credenciales válidas.

Variables para live con ccxt:

- `EXCHANGE_ADAPTER=ccxt`
- `EXCHANGE_ID=kraken` (o exchange soportado por ccxt)
- `EXCHANGE_API_KEY=...`
- `EXCHANGE_API_SECRET=...`
- `EXCHANGE_API_PASSPHRASE=...` (si aplica)
- `EXCHANGE_SYMBOL=BTC/USD`
- `EXCHANGE_SANDBOX=true|false`

Variables de control de riesgo:

- `DAILY_LOSS_LIMIT_USD=300` (límite duro diario)
- `GLOBAL_KILL_SWITCH_DEFAULT=false` (arranque del kill switch)
- `MONITORED_SYMBOL=BTCUSD` y `MONITORED_TIMEFRAME=5m`
- `MARKET_DATA_STALE_MINUTES=15`
- `FEATURES_DATA_STALE_MINUTES=30`
- `RECONCILE_STALE_MINUTES=3`
- `REJECTED_ORDERS_1H_WARN_THRESHOLD=3`
- `ALERT_COOLDOWN_MINUTES=30`
- `RECONCILE_HEARTBEAT_INTERVAL_MINUTES=1`
- `PAPER_GO_NO_GO_LOOKBACK_DAYS=14`
- `GO_NO_GO_MIN_DAYS=14`
- `GO_NO_GO_MIN_EXECUTED_ORDERS=20`
- `GO_NO_GO_MIN_WIN_RATE=0.45`
- `GO_NO_GO_MAX_DRAWDOWN_PCT=0.08`
- `GO_NO_GO_MIN_REALIZED_PNL_USD=0`
- `GO_NO_GO_MAX_REJECTION_RATE=0.30`
- `GO_NO_GO_MIN_RECONCILE_UPTIME_PCT=95`
- `GO_NO_GO_MAX_CRITICAL_ALERTS_24H=0`
- `FORECAST_DEFAULT_HORIZON_MINUTES=10`
- `FORECAST_MIN_MOVE_BPS=5`
- `FORECAST_MAX_RESOLUTION_LAG_MINUTES=20`
- `FORECAST_GO_MIN_ACCURACY=0.55`
- `HYBRID_MODE=shadow`
- `HYBRID_REQUIRE_AI_AGREEMENT=true`
- `HYBRID_AI_MIN_CONFIDENCE=0.60`
- `HYBRID_QUANT_MIN_CONFIDENCE=0.10`

Kill switch y pérdida diaria:

- Si `daily_loss_usd >= DAILY_LOSS_LIMIT_USD`, el servicio activa `global_kill_switch` automáticamente y bloquea nuevas órdenes.
- El estado se consulta en `GET /risk/controls` y también aparece en `GET /health`.
- Activación/desactivación manual: `POST /risk/kill-switch` con `{ "enabled": true|false, "reason": "...", "metadata": {} }`.
- `GET /ops/summary` expone staleness de datos, heartbeat de reconcile, rechazos por hora y eventos de riesgo recientes.
- `POST /alerts/evaluate` calcula alertas (`warning/critical`) y con `persist=true` las registra en `risk_events` con cooldown.

Go / No-Go (paper):

- `GET /paper/scorecard` calcula métricas del período (P&L realizado, drawdown, win rate, rechazo y uptime reconcile).
- `POST /paper/go-no-go` evalúa umbrales de paso a `live` y puede persistir historial en `paper_evaluations`.
- El workflow `BTC Paper Go No-Go Daily` ejecuta esta evaluación diariamente y guarda decisión `go|no_go`.

Validacion de prediccion a futuro (5-10m):

- `POST /forecast/checkpoint` guarda la prediccion con vencimiento (por ejemplo +10m).
- `POST /forecast/evaluate-due` compara la prediccion vencida contra precio real y marca `hit|miss|expired`.
- `GET /forecast/scorecard` resume accuracy y edge estadistico por ventana.
- Regla de lectura rapida:
  - `accuracy` mide aciertos reales.
  - `avg_edge_bps` > 0 indica ventaja direccional neta.
  - `predictive_go=true` cuando supera umbral (`FORECAST_GO_MIN_ACCURACY`) y edge positivo.

Antes de operar en `live`:

1. Implementar adaptador firmado para exchange elegido.
2. Validar en sandbox del exchange (si disponible).
3. Agregar validación de slippage real.
4. Definir kill switch global.
5. Correr paper por 2-4 semanas.
6. Activar con capital mínimo.

## 7) Apagar stack

```bash
sh n8n/scripts/trading_down.sh
```
