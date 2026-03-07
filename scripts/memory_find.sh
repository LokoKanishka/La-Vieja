#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Uso: $0 \"texto_o_tag\"" >&2
  exit 1
fi

query="$1"

if [[ ! -d memory ]]; then
  echo "No existe carpeta memory/" >&2
  exit 1
fi

echo "== Coincidencias en indice =="
if [[ -f memory/index.jsonl ]]; then
  rg -n -i -- "${query}" memory/index.jsonl || true
else
  echo "Sin indice."
fi

echo
echo "== Coincidencias en notas diarias =="
rg -n -i --glob '20??-??-??.md' -- "${query}" memory || true

