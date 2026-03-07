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

## Reanudacion De Sesion (estado operativo)

- Proyecto activo: banco de prueba de autonomia en maquina vieja con Codex + n8n.
- n8n corre en Docker local en `http://127.0.0.1:5111` (compose en `n8n/docker-compose.yml`).
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
