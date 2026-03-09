# Plan Maestro BTC (Fuente Unica Operativa)

Ultima actualizacion: 2026-03-09 01:56 (America/Sao_Paulo)

## 1) Objetivo Total

Llevar el stack BTC de `paper` a `live` con control de riesgo estricto, observabilidad completa y criterio go/no-go automatizado, manteniendo autonomia operativa con n8n + memoria persistente.

## 2) Estado Real Verificado (Hecho)

- Infra activa: `n8n_trading`, `btc_postgres`, `btc_strategy_service` arriba y saludables.
- Workflows BTC activos (7/7):
  - BTC Ingest Market 5m
  - BTC Feature Engineering 15m
  - BTC Signal Risk Execute 15m
  - BTC Reconcile 1m
  - BTC Custody Sweep Daily
  - BTC Ops Monitor 1m
  - BTC Paper Go No-Go Daily
- Riesgo implementado:
  - Kill switch global persistente.
  - Daily loss hard (`DAILY_LOSS_LIMIT_USD`) con activacion automatica.
- Observabilidad implementada:
  - `GET /ops/summary`
  - `POST /alerts/evaluate`
  - Heartbeats de reconcile y persistencia de alertas.
- Go/No-Go paper implementado:
  - `GET /paper/scorecard`
  - `POST /paper/go-no-go`
  - Persistencia en `paper_evaluations`.
- Mejora operativa aplicada:
  - `n8n/scripts/import_workflows_api.sh` ahora autocarga `N8N_API_KEY` desde Postgres si no existe en entorno.
- Mejora iniciada hoy sobre pendientes:
  - Ajuste en scorecard para calcular `reconcile_uptime_pct` desde el primer heartbeat observado del periodo y evitar penalizacion historica falsa.

## 3) Estado Actual De Go/No-Go (No Hecho Aun)

Decision actual: `NO_GO`.

Criterios aun fallando:
- `runtime_days_min` (meta 14 dias, actual ~1.25).
- `filled_orders_min` (meta 20, actual 16).
- `win_rate_min` (meta 0.45, actual 0.0).
- `realized_pnl_usd_min` (meta >= 0, actual negativo).
- `reconcile_uptime_pct_min` (meta 95, actual cerca de 94 tras correccion).
- `critical_ops_alerts_24h_max` (meta 0, actual 1).

## 4) Plan Total Por Fases (Completo)

### Fase A - Estabilizacion Paper (inmediata, 24-72h)

1. Subir `reconcile_uptime_pct` por encima de 95 sostenido.
   - Acciones: vigilar heartbeat cada 1m, detectar huecos, corregir fallas de cron/reconcile.
   - Hecho cuando: uptime >= 95 por ventana de 24h.
2. Bajar alertas criticas 24h a cero.
   - Acciones: analizar ultima alerta critica persistida y eliminar causa raiz.
   - Hecho cuando: `critical_ops_alerts_24h = 0` por 24h.
3. Mantener staleness bajo umbral.
   - Acciones: validar edad de `market/features/reconcile` y ajustar cadence si hace falta.
   - Hecho cuando: sin staleness warning/critical por 24h.

### Fase B - Calidad De Estrategia Paper (1-2 semanas)

1. Mejorar win rate y PnL realizado.
   - Acciones: calibrar reglas de señal, filtros de volatilidad y sizing.
   - Hecho cuando: win rate >= 0.45 y PnL >= 0 en ventana de evaluacion.
2. Aumentar tamaño muestral robusto.
   - Acciones: asegurar continuidad de ejecucion para superar 20 ordenes filled.
   - Hecho cuando: `filled_orders >= 20`.

### Fase C - Riesgo Y Gobernanza (en paralelo)

1. Auditoria de rechazos y reglas de riesgo.
   - Acciones: clasificar motivos de rechazo y reducir rechazos evitables.
   - Hecho cuando: `rejection_rate` estable y bajo umbral.
2. Runbook de incidentes.
   - Acciones: procedimiento claro para kill switch, recovery y rollback.
   - Hecho cuando: runbook documentado y probado en simulacion.

### Fase D - Pre-Live Tecnica (bloqueada por criterios paper)

1. Adaptador firmado real de exchange (`ccxt`) en sandbox.
2. Validacion de slippage y costo real de ejecucion.
3. Pruebas de continuidad (reinicios, reconexion, latencia).
4. Checklist final de seguridad y limites.

Hecho cuando: todas las pruebas en sandbox pasan y go/no-go paper resulta `GO`.

### Fase E - Activacion Live Minima (solo si GO)

1. Habilitar `TRADING_MODE=live` con capital minimo.
2. Monitoreo reforzado y kill switch habilitado desde arranque.
3. Escalado gradual de riesgo solo con metricas estables.

## 5) Prioridad Operativa Actual (ya iniciada)

Prioridad #1: cerrar brechas de scorecard para salir de `NO_GO`.

Orden de ejecucion inmediato:
1. Estabilidad operacional (uptime + alertas criticas).
2. Calidad de señal/PnL.
3. Tamano de muestra y validacion de criterios restantes.

## 6) Protocolo De Actualizacion Obligatorio

En cada sesion nueva:
1. Leer este archivo primero junto con `AGENT_MEMORY.md` y memoria reciente.
2. Actualizar secciones 2, 3 y 5 con metricas reales del momento.
3. Persistir cambios con webhook n8n de memoria (`Memory Add Webhook`) y commit/push.

## 7) Comandos De Control Rapido

- Health: `curl -s http://127.0.0.1:8100/health`
- Ops summary: `curl -s http://127.0.0.1:8100/ops/summary`
- Scorecard: `curl -s "http://127.0.0.1:8100/paper/scorecard?lookback_days=14"`
- Go/No-Go: `curl -s -X POST http://127.0.0.1:8100/paper/go-no-go -H "Content-Type: application/json" -d '{"lookback_days":14,"persist":true}'`
- Workflows activos BTC: `docker exec btc_postgres psql -U n8n -d n8n -At -F $'\t' -c "select name, active from workflow_entity where name like 'BTC %' order by name;"`
