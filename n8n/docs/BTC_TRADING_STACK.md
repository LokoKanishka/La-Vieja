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
- `POST /execution/order`
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
