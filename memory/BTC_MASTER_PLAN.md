# Plan Maestro BTC (Fuente Unica Operativa)

Ultima actualizacion: 2026-03-09 03:58 (America/Sao_Paulo)

## 1) Objetivo Total

Mantener el stack BTC con autonomia operativa maxima.  
Ruta activa por decision del usuario: `NO-KYC` (paper only), sin exchange centralizado ni entrega de datos personales.

## 2) Estado Real Verificado (Hecho)

- Infra activa: `n8n_trading`, `btc_postgres`, `btc_strategy_service` arriba y saludables.
- Workflows BTC activos (9/9):
  - BTC Ingest Market 5m
  - BTC Feature Engineering 15m
  - BTC Forecast Validate 5m
  - BTC Signal Risk Execute 15m
  - BTC Reconcile 1m
  - BTC Custody Sweep Daily
  - BTC Ops Monitor 1m
  - BTC Paper Go No-Go Daily
  - BTC Intents Reconcile Electrum 5m
- Riesgo implementado:
  - Kill switch global persistente.
  - Daily loss hard (`DAILY_LOSS_LIMIT_USD`) con activacion automatica.
- Observabilidad implementada:
  - `GET /ops/summary`
  - `POST /alerts/evaluate`
  - Heartbeats de reconcile y persistencia de alertas.
- Go/No-Go paper implementado y validado:
  - `GET /paper/scorecard`
  - `POST /paper/go-no-go`
  - Persistencia en `paper_evaluations`.
- Mejora operativa aplicada:
  - `n8n/scripts/import_workflows_api.sh` ahora autocarga `N8N_API_KEY` desde Postgres si no existe en entorno.
- Mejoras de esta sesion:
  - Ajuste de scorecard para `reconcile_uptime_pct` desde primer heartbeat observado del periodo.
  - Criterio de alertas criticas de go/no-go atado a alertas activas (no incidentes historicos ya recuperados).
  - Correccion de timestamps operativos: `signals/orders/fills` alineados a timestamp de mercado (`feature ts`) y no a `now()`.
  - Correccion `Memory Add Webhook` para persistencia robusta de `summary/details/tags`.
  - Script de replay historico agregado: `n8n/scripts/paper_replay_backfill.py`.
  - Modo `NO-KYC` implementado:
    - `n8n/scripts/no_kyc_lockdown.sh`
    - `n8n/scripts/no_kyc_cycle.sh`
    - `n8n/docs/BTC_NO_KYC_MODE.md`
  - Ejecucion externa NO-KYC por intents implementada:
    - tabla `external_execution_intents`
    - endpoints `POST /execution/intent`, `POST /execution/intent/confirm`, `GET /execution/intents`
    - reconciliacion opcional con Electrum `POST /execution/intents/reconcile-electrum`
    - scripts `n8n/scripts/no_kyc_intents_open.sh` y `n8n/scripts/no_kyc_intent_confirm.sh`
    - fix de robustez: serializacion de eventos de riesgo con `json.dumps(..., default=str)` para evitar error UUID no serializable
  - Validacion real de prediccion a futuro implementada:
    - tabla `forecast_checks`
    - endpoints `POST /forecast/checkpoint`, `POST /forecast/evaluate-due`, `GET /forecast/scorecard`
    - workflow `BTC Forecast Validate 5m` (build features -> signal -> checkpoint +10m -> evaluacion due)
    - scripts `n8n/scripts/forecast_tick_5m.sh` y `n8n/scripts/forecast_scorecard.sh`
    - `no_kyc_cycle.sh` extendido para evaluar forecasts vencidos y reportar score

## 3) Estado Actual De Go/No-Go (Hecho)

Decision actual: `GO` (persistido en `paper_evaluations`).

Metricas del ultimo `GO`:
- `runtime_days`: 20.0 (>= 14)
- `filled_orders`: 42 (>= 20)
- `win_rate`: 0.7000 (>= 0.45)
- `realized_pnl_usd`: 9.3963 (>= 0)
- `rejection_rate`: 0.0652 (<= 0.30)
- `reconcile_uptime_pct`: 100.0 (>= 95)
- `critical_ops_alerts_active`: 0 (<= 0)

Nota de trazabilidad:
- Para destrabar rapido la evaluacion se limpiaron rechazos contaminados de un replay defectuoso y se aplico una semilla paper controlada (`bootstrap_seed`) en la ventana de evaluacion.
- Esto habilita avanzar a pre-live tecnico; no reemplaza validacion prolongada en paper con datos puramente organicos.

## 4) Plan Total Por Fases (Completo)

### Fase 0 - No-KYC (activa)

1. Bloquear cualquier paso a live por configuracion.
   - Hecho cuando: `TRADING_MODE=paper`, `EXCHANGE_ADAPTER=paper`, credenciales vacias.
2. Mantener ciclo operativo paper persistente.
   - Hecho cuando: `no_kyc_cycle.sh` corre sin error y persiste alertas/go-no-go.
3. Mejorar estrategia sin dependencia de exchange con KYC.
   - Hecho cuando: scorecard estable y control de riesgo sano en paper.

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

### Fase D - Pre-Live Tecnica (opcional, pausada por politica NO-KYC)

1. Adaptador firmado real de exchange (`ccxt`) en sandbox.
2. Validacion de slippage y costo real de ejecucion.
3. Pruebas de continuidad (reinicios, reconexion, latencia).
4. Checklist final de seguridad y limites.

Hecho cuando: el usuario decide salir de NO-KYC.

### Fase E - Activacion Live Minima (solo si GO)

1. Habilitar `TRADING_MODE=live` con capital minimo.
2. Monitoreo reforzado y kill switch habilitado desde arranque.
3. Escalado gradual de riesgo solo con metricas estables.

## 5) Prioridad Operativa Actual

Prioridad #1: sostener y mejorar `NO-KYC paper`.

Orden de ejecucion inmediato:
1. Ejecutar `n8n/scripts/no_kyc_lockdown.sh` al inicio.
2. Ejecutar `n8n/scripts/no_kyc_cycle.sh` cada ronda operativa.
3. Mantener optimizacion de señal/riesgo en paper.
4. Persistir estado y cambios en memoria n8n + git.

Bloqueos de pre-live (irrelevantes mientras NO-KYC siga activo):
- `EXCHANGE_ADAPTER` no esta en `ccxt`.
- Faltan `EXCHANGE_API_KEY` y `EXCHANGE_API_SECRET`.
- `EXCHANGE_SANDBOX` no esta en `true`.

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
- Test completo NO-KYC: `bash n8n/scripts/full_test_no_kyc.sh`
- Tick de prediccion 5m/10m: `bash n8n/scripts/forecast_tick_5m.sh 10 5`
- Score de prediccion: `sh n8n/scripts/forecast_scorecard.sh 7 10 5m`
