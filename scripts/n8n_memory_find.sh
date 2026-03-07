#!/bin/sh
set -eu

if [ $# -lt 1 ]; then
  echo "Uso: $0 \"texto_o_tag\"" >&2
  exit 1
fi

query="$1"

if [ ! -d memory ]; then
  echo "No existe carpeta memory/" >&2
  exit 1
fi

echo "== Coincidencias en indice =="
if [ -f memory/index.jsonl ]; then
  if command -v rg >/dev/null 2>&1; then
    rg -n -i -- "${query}" memory/index.jsonl || true
  else
    grep -n -i -- "${query}" memory/index.jsonl || true
  fi
else
  echo "Sin indice."
fi

echo
echo "== Coincidencias en notas diarias =="
if command -v rg >/dev/null 2>&1; then
  rg -n -i --glob '20??-??-??.md' -- "${query}" memory || true
else
  find memory -type f -name '20??-??-??.md' -exec grep -n -i -- "${query}" {} + || true
fi
