# Memoria Operativa Del Proyecto

## Premisas Principales

1. **Maquina vieja siempre optimizada al maximo**
   - Al cerrar cada sesion/tarea, dejar la maquina en estado limpio y liviano.
   - Priorizar: liberar almacenamiento, reducir uso de RAM/CPU y desactivar procesos o servicios innecesarios.
   - Objetivo: mantener el mejor rendimiento posible en hardware antiguo.
   - **Regla de activacion directa**: si el usuario dice "limpiar" o "limpia la PC", se activa automaticamente este Punto 1.

2. **Objetivo principal del proyecto: validar capacidad real con Codex + n8n**
   - Usar esta maquina vieja como banco de prueba para medir hasta donde puede llegar con Codex (cerebro) y n8n (orquestador).
   - Priorizar automatizacion via APIs, uso de MCPs y memoria persistente para lograr la mayor autonomia operativa posible.

3. **Autonomia maxima por defecto (friccion minima para el usuario)**
   - Ejecutar todo lo posible de forma autonoma en consola, sin delegar pasos manuales al usuario salvo que sea estrictamente necesario.
   - Evitar pedir al usuario que ejecute comandos.
   - Evitar solicitudes de interaccion/permisos innecesarias y agrupar acciones para reducir interrupciones.
   - Solo pedir intervencion del usuario cuando sea inevitable: credenciales, claves/API, autenticaciones externas o limites tecnicos del entorno.
   - Motivo operativo: el usuario trabaja en paralelo y la maquina es lenta; minimizar interacciones mejora mucho el flujo y la productividad.

4. **Politica de APIs y herramientas: cero pago / cero tarjeta**
   - No usar servicios pagos ni trials que exijan tarjeta.
   - Priorizar APIs gratuitas, open source o planes free sin metodo de pago.
   - Mantener enfoque "cyberpunk": maxima autonomia tecnica con recursos libres.

## Reanudacion De Sesion (estado operativo)

- Proyecto activo: banco de prueba de autonomia en maquina vieja con Codex + n8n.
- n8n corre en Docker local en `http://127.0.0.1:5111` (compose en `n8n/docker-compose.yml`).
- Nueva fase activa (BTC core): stack dedicado en `n8n/docker-compose.trading.yml` con:
  - `postgres` (persistencia operacional)
  - `strategy_service` (API de ingesta, features, señal, riesgo, ejecución, reconciliación, custodia)
  - `n8n` conectado a Postgres y al servicio de estrategia
- Servicio de estrategia: `n8n/trading_service/app.py`
  - Modo `paper` para ejecución automática segura.
  - Modo `live` disponible vía `ccxt` (requiere credenciales en `n8n/.env.trading`).
  - Electrum integrado por RPC para custodia (`/electrum/balance`, `/electrum/rpc`), no como motor de matching.
  - Módulo híbrido activo en modo sombra (`/hybrid/decision`, `/hybrid/scorecard`).
- Workflows de trading listos para importar en `n8n/workflows/trading/`:
  - ingesta mercado 5m
  - features 15m
  - forecast validate 5m
  - hybrid shadow 5m
  - señal/riesgo/ejecución 15m
  - intents reconcile 5m
  - reconcile 1m
  - ops monitor 1m
  - paper go/no-go daily
  - sweep de custodia diario
- Scripts operativos nuevos:
  - `n8n/scripts/trading_up.sh`
  - `n8n/scripts/trading_down.sh`
  - `n8n/scripts/import_trading_workflows_api.sh`
- SQL inicial: `n8n/sql/init/001_trading_core.sql`
- Documentación operativa: `n8n/docs/BTC_TRADING_STACK.md`
- Memoria persistente disponible en:
  - `memory/index.jsonl`
  - `memory/YYYY/MM/YYYY-MM-DD.md`
  - `memory/BTC_MASTER_PLAN.md` (fuente unica del plan total BTC)
- Scripts clave:
  - `scripts/memory_add.sh`
  - `scripts/memory_recent.sh`
  - `scripts/memory_find.sh`
  - `n8n/scripts/import_workflows_api.sh`
  - `n8n/scripts/print_active_webhooks.sh`
  - `n8n/scripts/zero_cost_guard.sh`
  - `n8n/scripts/hybrid_shadow_tick.sh`
  - `n8n/scripts/hybrid_scorecard.sh`
  - `n8n/scripts/hybrid_backfill_shadow.sh`
  - `n8n/scripts/no_kyc_intents_autocancel.sh`
  - `n8n/scripts/hybrid_hourly_report.sh`
- Ajuste crítico reciente:
  - `POST /signal/evaluate` ahora evita duplicar señales por la misma vela y reutiliza `signal_id`.
  - `POST /execution/intent` ahora es idempotente por `signal_id` y reutiliza intent existente (evita duplicados abiertos).
  - `n8n/scripts/hybrid_backfill_shadow.sh` ahora selecciona señales únicas por vela para score híbrido más limpio.
  - `docker-compose.trading.yml` ahora inyecta variables `forecast/hybrid` completas al `strategy_service`.
  - Scorecards `forecast/hybrid` excluyen outliers con `FORECAST_MAX_ABS_CHANGE_BPS`.
  - `n8n/scripts/backfill_market_binance_5m.sh` agrega velas históricas 5m desde Binance para cerrar huecos previos de mercado.
  - `signal/evaluate` ahora soporta `SIGNAL_POLICY=mom_inverse` (umbral configurable `SIGNAL_MOM_THRESHOLD`).
  - `HYBRID_FALLBACK_POLICY` operativo en NO-KYC: `same_as_quant` (alineado al quant actual).
  - Queries de features/forecast/hybrid priorizan velas alineadas a 5m y prefieren venue `binance` en empate temporal.
- Pendientes críticos actuales para la próxima sesión:
  - Mantener `full_test_no_kyc.sh` en `failed=0`.
  - Mantener `open_intents=0`.
  - Objetivo de muestra híbrida ya cumplido (`decisions_with_outcome=81`, `outlier_excluded=0`).
  - `go/no-go` actual: `NO_GO` por `reconcile_uptime_pct` bajo umbral (44.86% vs 95%).
  - Pendiente activo: convertir `hybrid.avg_edge_bps` a positivo (actual `-5.4664`) con ajuste quant adicional.
- Al retomar:
  1. Verificar contenedor: `cd n8n && sudo docker compose ps`
  2. Si no esta arriba: `cd n8n && sudo docker compose up -d`
  3. Revisar webhooks activos: `./n8n/scripts/print_active_webhooks.sh`
  4. Probar memoria reciente por webhook: `curl "http://127.0.0.1:5111/webhook/MEmRecntWf123456/webhook-memory-recent/memory/recent?days=1"`
  5. Para fase BTC: `cp n8n/.env.trading.example n8n/.env.trading && sh n8n/scripts/trading_up.sh`

## Protocolo Automatico Al Recibir "hola"

1. Leer contexto sin que el usuario lo pida:
   - `AGENT_MEMORY.md`
   - ultimas entradas de `memory/index.jsonl`
   - nota del dia en `memory/YYYY/MM/YYYY-MM-DD.md`
   - `memory/BTC_MASTER_PLAN.md` (si existe)
2. Auto-actualizar estado operativo:
   - `git status --short`
   - `git log --oneline -n 5`
   - estado de contenedores (`docker ps`)
3. Reportar resumen de estado y pendientes criticos en 1 mensaje corto, incluyendo estado del plan BTC (hecho/en curso/pendiente).
4. Si hay cambios pendientes relevantes, ejecutar flujo de cierre:
   - actualizar memoria persistente por n8n webhook (resolver URL real con `./n8n/scripts/print_active_webhooks.sh` y usar la que termine en `memory/add`)
   - reflejar cambios en `memory/BTC_MASTER_PLAN.md`
   - `git add -A && git commit -m "<resumen>"`
   - `git push origin main`
5. Mantener este protocolo como comportamiento por defecto para proximas sesiones.
