# Sistema De Memoria Permanente

Estructura:
- `memory/index.jsonl`: indice global, una linea JSON por evento.
- `memory/YYYY/MM/YYYY-MM-DD.md`: notas por dia.

Scripts:
- `scripts/memory_add.sh "resumen" "detalle" "tags_csv"`
- `scripts/memory_recent.sh [dias]`
- `scripts/memory_find.sh "consulta"`

Politica de lectura operativa:
- Leer por defecto hoy y ayer.
- Consultar historico por busqueda cuando haga falta.
- Mantener catalogacion por fecha para trazabilidad.

