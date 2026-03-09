# AGENTS.md

## Objetivo
Forzar reanudacion operativa automatica en cada sesion nueva, especialmente al recibir `hola`.

## Protocolo De Arranque Obligatorio
Al primer mensaje del usuario en una sesion nueva, o si el mensaje es `hola`/`buenas`:

1. Cargar contexto local sin pedir permiso:
   - Leer `AGENT_MEMORY.md`.
   - Leer ultimas 20 lineas de `memory/index.jsonl` (si existe).
   - Leer la nota del dia en `memory/YYYY/MM/YYYY-MM-DD.md` (si existe).
   - Leer `memory/BTC_MASTER_PLAN.md` (si existe) como fuente unica del plan BTC.
2. Verificar estado operativo:
   - `git status --short`
   - `git log --oneline -n 5`
   - `docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'`
3. Responder al usuario con un resumen corto:
   - Memoria cargada (si/no).
   - Estado de n8n/docker.
   - Pendientes criticos detectados.
   - Estado del plan maestro BTC (hecho/en curso/pendiente).

## Regla De Ejecucion
- No esperar a que el usuario pida "leer memoria": hacerlo directo bajo el protocolo anterior.
- Si algun archivo o comando falla, informar el faltante y continuar con lo disponible.
