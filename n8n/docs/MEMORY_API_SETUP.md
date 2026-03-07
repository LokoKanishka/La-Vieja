# n8n Memory API Setup

## Modo Recomendado (Docker interno)
Levantar n8n dentro de esta maquina con Docker:
- `n8n/docker-compose.yml`
- `n8n/scripts/install_docker_and_start_n8n_5111.sh` (instala Docker + arranca n8n)
- `n8n/scripts/docker_up.sh`
- `n8n/scripts/docker_down.sh`

URL esperada:
- `http://127.0.0.1:5111`

Instalacion/arranque rapido (una vez):
```bash
cd "/home/lucy/Escritorio/La Vieja" && chmod +x n8n/scripts/install_docker_and_start_n8n_5111.sh && ./n8n/scripts/install_docker_and_start_n8n_5111.sh
```

## Importar Workflows
Importar estos 3 archivos en n8n:
- `n8n/workflows/memory_add_webhook.json`
- `n8n/workflows/memory_find_webhook.json`
- `n8n/workflows/memory_recent_webhook.json`

## Activar Endpoints
Al activar los workflows, quedan endpoints:
- `POST /webhook/<workflowId>/webhook-memory-add/memory/add`
- `GET /webhook/<workflowId>/webhook-memory-find/memory/find?query=...`
- `GET /webhook/<workflowId>/webhook-memory-recent/memory/recent?days=2`

Si usas Test URL en n8n, cambia `/webhook/` por `/webhook-test/`.

Puerto operativo del proyecto:
- `5111` (base local: `http://127.0.0.1:5111`)

## Ejemplos
Primero listar URLs activas reales:
```bash
n8n/scripts/print_active_webhooks.sh
```

Guardar memoria:
```bash
curl -X POST "http://127.0.0.1:5111/webhook/<ID>/webhook-memory-add/memory/add" \
  -H "Content-Type: application/json" \
  -d '{"summary":"Tema del dia","details":"Detalle largo","tags":"n8n,codex,memoria"}'
```

Buscar en historico:
```bash
curl "http://127.0.0.1:5111/webhook/<ID>/webhook-memory-find/memory/find?query=n8n"
```

Leer dias recientes:
```bash
curl "http://127.0.0.1:5111/webhook/<ID>/webhook-memory-recent/memory/recent?days=2"
```

## Notas operativas
- Estos flujos usan scripts locales en:
  - `scripts/memory_add.sh`
  - `scripts/memory_find.sh`
  - `scripts/memory_recent.sh`
- Ruta de trabajo esperada:
  - `/home/lucy/Escritorio/La Vieja`
- Si cambias la ruta del proyecto, actualiza el comando en cada nodo `Execute Command`.
- Script de arranque sugerido:
  - `n8n/scripts/start_n8n_5111.sh`
- Script de importacion por API (requiere `N8N_API_KEY`):
  - `n8n/scripts/import_workflows_api.sh`
- Script para imprimir URLs webhook activas:
  - `n8n/scripts/print_active_webhooks.sh`
- Si usas Docker, preferi:
  - `n8n/scripts/docker_up.sh`
  - `n8n/scripts/docker_down.sh`
