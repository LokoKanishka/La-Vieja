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
- Workflows de trading listos para importar en `n8n/workflows/trading/`:
  - ingesta mercado 5m
  - features 15m
  - señal/riesgo/ejecución 15m
  - reconcile 1m
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
- Scripts clave:
  - `scripts/memory_add.sh`
  - `scripts/memory_recent.sh`
  - `scripts/memory_find.sh`
  - `n8n/scripts/import_workflows_api.sh`
  - `n8n/scripts/print_active_webhooks.sh`
- Al retomar:
  1. Verificar contenedor: `cd n8n && sudo docker compose ps`
  2. Si no esta arriba: `cd n8n && sudo docker compose up -d`
  3. Revisar webhooks activos: `./n8n/scripts/print_active_webhooks.sh`
  4. Probar memoria reciente por webhook: `curl "http://127.0.0.1:5111/webhook/memory/recent?days=1"`
  5. Para fase BTC: `cp n8n/.env.trading.example n8n/.env.trading && sh n8n/scripts/trading_up.sh`

## Protocolo Automatico Al Recibir "hola"

1. Leer contexto sin que el usuario lo pida:
   - `AGENT_MEMORY.md`
   - ultimas entradas de `memory/index.jsonl`
   - nota del dia en `memory/YYYY/MM/YYYY-MM-DD.md`
2. Auto-actualizar estado operativo:
   - `git status --short`
   - `git log --oneline -n 5`
   - estado de contenedores (`docker ps`)
3. Reportar resumen de estado y pendientes criticos en 1 mensaje corto.
4. Si hay cambios pendientes relevantes, ejecutar flujo de cierre:
   - actualizar memoria (`scripts/memory_add.sh`)
   - `git add -A && git commit -m "<resumen>"`
   - `git push origin main`
5. Mantener este protocolo como comportamiento por defecto para proximas sesiones.
