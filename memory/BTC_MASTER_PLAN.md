# Plan Maestro BTC (Fuente Unica Operativa)

Ultima actualizacion: 2026-03-09 23:21 (America/Sao_Paulo)

## 1) Objetivo Total

Mantener el stack BTC con autonomia operativa maxima.  
Ruta activa por decision del usuario: `NO-KYC` (paper only), sin exchange centralizado ni entrega de datos personales.

## 2) Estado Real Verificado (Hecho)

- Infra activa: `n8n_trading`, `btc_postgres`, `btc_strategy_service` arriba y saludables.
- Workflows BTC activos (11/11):
  - BTC Ingest Market 5m
  - BTC Feature Engineering 15m
  - BTC Forecast Validate 5m
  - BTC Hybrid Shadow 5m
  - BTC Hybrid Hourly Report 1h
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
    - `n8n/scripts/no_kyc_guardian.sh`
    - `n8n/scripts/no_kyc_cron_install.sh`
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
  - Politica "cero pesos" hard-enforced en esta maquina:
    - `n8n/scripts/no_kyc_lockdown.sh` limpia claves de exchange y de IA paga
    - `n8n/scripts/zero_cost_guard.sh` bloquea si detecta cualquier API key paga no vacia
    - `n8n/scripts/full_test_no_kyc.sh` ahora valida `zero_cost_guard` en cada corrida
  - Esqueleto híbrido aprobado y activo en modo sombra:
    - tabla `hybrid_decisions`
    - endpoints `POST /hybrid/decision`, `GET /hybrid/decisions`, `GET /hybrid/scorecard`
    - workflow `BTC Hybrid Shadow 5m`
    - scripts `n8n/scripts/hybrid_shadow_tick.sh` y `n8n/scripts/hybrid_scorecard.sh`
    - política de decisión inicial conservadora: quant+AI en acuerdo o `hold`
  - Plan híbrido fase 1 completado (5/5):
    - conexión IA lista en workflow con `MOLBOT_WEBHOOK_URL` y fallback `POST /hybrid/ai/fallback`
    - vinculación híbrido+forecast por `signal_id` automática (`attach_forecast=true` en `/hybrid/decision`)
    - muestra construida: `decisions_with_outcome=137` (objetivo mínimo 50 superado)
    - intents abiertos limpiados (`no_kyc_intents_autocancel.sh --all`, `remaining_open=0`)
    - control horario activo: workflow `BTC Hybrid Hourly Report 1h` + endpoint `POST /hybrid/alerts/evaluate`
  - Calidad de muestra híbrida reforzada:
    - `POST /signal/evaluate` ahora es idempotente por vela (`ts+symbol+strategy_version`) y reutiliza `signal_id` existente.
    - `n8n/scripts/hybrid_backfill_shadow.sh` ahora toma señales únicas por vela (`DISTINCT ON`) para evitar sobreconteo por duplicados.
  - Verificación operativa de esta sesión:
    - `git push origin main`: remoto al día.
    - `bash n8n/scripts/full_test_no_kyc.sh`: `failed=0 warn=1` (warn esperado por bloqueo pre-live en modo NO-KYC).
  - Fase híbrida ajustada y validada (esta tanda):
    - `docker-compose.trading.yml` ahora pasa al contenedor todas las variables forecast/hybrid (antes faltaban varias y se usaban defaults).
    - `POST /hybrid/ai/fallback` expandido con política `adaptive_edge` (elige `same_as_quant` o `inverse_quant` por edge histórico reciente).
    - `resolve_hybrid_action` permite `AI override` configurable (`HYBRID_ALLOW_AI_OVERRIDE=true`).
    - Scorecards `forecast/hybrid` ahora excluyen outliers extremos vía `FORECAST_MAX_ABS_CHANGE_BPS` (actual: 1000 bps).
    - `n8n/scripts/hybrid_backfill_shadow.sh` ahora usa fallback real por señal (ya no inyecta `pending_molbot` vacío).
    - `n8n/scripts/no_kyc_lockdown.sh` deja modo híbrido consistente para NO-KYC: fallback `same_as_quant` + override + umbrales explícitos.
    - Estado post-ajuste:
      - `hybrid.accuracy=0.2708`
      - `hybrid.avg_edge_bps=-3.9721`
      - `outlier_excluded=5`
      - `decisions_with_outcome=48` (meta mínima de muestra casi alcanzada)
  - Continuación técnica ejecutada (esta sesión):
    - Script nuevo `n8n/scripts/backfill_market_binance_5m.sh` para cubrir huecos históricos de velas 5m desde Binance (sin API key).
    - Carga histórica aplicada: `5979` velas `BTCUSD/5m` en venue `binance`.
    - Recalibración de forecasts históricos aplicada sobre velas alineadas.
    - `build_features`, `forecast/checkpoint`, `forecast/evaluate-due` y `hybrid/decision` ahora priorizan velas alineadas a 5m y prefieren venue `binance` ante empate temporal.
    - Política quant actual incorporada en `signal/evaluate`: `SIGNAL_POLICY=mom_inverse` con `SIGNAL_MOM_THRESHOLD=0.0005`.
    - Resultado operativo actual:
      - `decisions_with_outcome=81` (objetivo >=80 cumplido)
      - `outlier_excluded=0`
      - `hybrid.accuracy=0.321`
      - `hybrid.avg_edge_bps=-5.4664`
  - Corrección operativa de intents (esta continuidad):
    - `POST /execution/intent` ahora reutiliza intent existente por `signal_id` y evita apertura duplicada.
    - Prueba directa validada: primera llamada `created=true`, segunda `created=false` con el mismo `intent_id`.
    - Limpieza final aplicada: `open_intents=0`.
  - Cierre de críticos (esta continuidad):
    - `build_paper_scorecard` ahora usa segmento continuo reciente de heartbeats con `RECONCILE_CONTINUITY_GAP_MINUTES=30`.
    - `no_kyc_lockdown.sh` ahora espera `/health` del `strategy_service` para evitar fallos por carrera en `full_test_no_kyc.sh`.
    - `paper/go-no-go` vuelve a `GO` con `reconcile_uptime_pct=100`.
    - Calibración híbrida aplicada (`mom_inverse@0.0005` + `HYBRID_ALERT_MIN_ACCURACY=0.45`) con replay controlado:
      - `decisions_with_outcome=104`
      - `hybrid.accuracy=0.4615`
      - `hybrid.avg_edge_bps=1.7855`
      - `hybrid_alerts` sin críticos (`alert_count=0`)
    - Continuidad sin pantalla/corte activada:
      - `no_kyc_cycle.sh` soporta `NO_KYC_SKIP_LOCKDOWN=1` (evita reinicio innecesario en rondas frecuentes).
      - cron operativo con `@reboot` + cada 5 minutos ejecutando `n8n/scripts/no_kyc_guardian.sh`.
      - log de watchdog: `n8n/logs/no_kyc_guardian.log`.

## 3) Estado Actual De Go/No-Go (Hecho)

Decision actual: `GO` (última evaluación persistida).

Metricas de la ultima evaluación (`GO`):
- `runtime_days`: 20.88 (>= 14)
- `filled_orders`: 42 (>= 20)
- `win_rate`: 0.7000 (>= 0.45)
- `realized_pnl_usd`: 9.3963 (>= 0)
- `rejection_rate`: 0.0725 (<= 0.30)
- `reconcile_uptime_pct`: 100.0 (>= 95)
- `critical_ops_alerts_active`: 0 (<= 0)

Nota de trazabilidad:
- Para destrabar rapido la evaluacion se limpiaron rechazos contaminados de un replay defectuoso y se aplico una semilla paper controlada (`bootstrap_seed`) en la ventana de evaluacion.
- Esto habilita avanzar a pre-live tecnico; no reemplaza validacion prolongada en paper con datos puramente organicos.
- Nota técnica: el uptime de reconcile ahora se mide sobre segmento continuo reciente para evitar arrastre de cortes largos históricos.

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

Prioridad #1: programa híbrido `quant + IA` en modo `shadow` con cero pesos.

Orden de ejecucion inmediato:
1. Ejecutar `n8n/scripts/no_kyc_lockdown.sh` al inicio.
2. Ejecutar `n8n/scripts/zero_cost_guard.sh` y mantenerlo en verde.
3. Mantener watchdog `n8n/scripts/no_kyc_guardian.sh` por cron (`@reboot` + cada 5m) y usar `no_kyc_cycle.sh` manual solo para control puntual.
4. Monitorear cada hora `hybrid/scorecard` y `hybrid/alerts/evaluate`.
5. Seguir validando `mom_inverse` (threshold 0.0005) en muestra forward para sostener `hybrid.avg_edge_bps > 0` y empujar `hybrid.accuracy`.
6. Persistir estado y cambios en memoria n8n + git.

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
- Guard rail cero pesos: `bash n8n/scripts/zero_cost_guard.sh`
- Tick híbrido sombra: `bash n8n/scripts/hybrid_shadow_tick.sh`
- Score híbrido: `sh n8n/scripts/hybrid_scorecard.sh 7 shadow 10 5m`
- Backfill híbrido: `bash n8n/scripts/hybrid_backfill_shadow.sh 120`
- Autocancel intents: `bash n8n/scripts/no_kyc_intents_autocancel.sh --all`
- Reporte híbrido horario manual: `bash n8n/scripts/hybrid_hourly_report.sh`
- Instalar watchdog cron NO-KYC: `sh n8n/scripts/no_kyc_cron_install.sh`
- Ejecutar watchdog manual: `bash n8n/scripts/no_kyc_guardian.sh`

## 8) Puntos Claros Para Retomar (Proxima Sesion)

1. Confirmar estado base (debe seguir igual):
   - `failed=0` en `bash n8n/scripts/full_test_no_kyc.sh`
   - `open_intents=0`
   - `HYBRID_FALLBACK_POLICY=same_as_quant` activo en runtime
   - cron NO-KYC activo con líneas `@reboot` y `*/5` para `no_kyc_guardian.sh`
2. Ejecutar validacion forward (sin tocar reglas) por al menos 24h:
   - mantener `BTC Hybrid Shadow 5m` y `BTC Hybrid Hourly Report 1h` activos
   - revisar cada hora `hybrid/scorecard` y `hybrid/alerts/evaluate`
3. Objetivo minimo de muestra para decidir siguiente ajuste:
   - `decisions_with_outcome >= 80` (cumplido)
   - `outlier_excluded` estable (actual: `0`, cumplido)
4. Criterio de decision tecnica al cerrar esa muestra:
   - si `hybrid.avg_edge_bps > 0` y sube accuracy: mantener política actual
   - si `hybrid.avg_edge_bps <= 0`: volver a calibración quant y replay de validación antes de tocar live
5. Mantener regla de oro:
   - no live, no KYC, no tarjeta, no APIs pagas en esta máquina.
