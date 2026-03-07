#!/bin/sh
set -eu

days="${1:-2}"

if [ ! -d memory ]; then
  echo "No existe carpeta memory/" >&2
  exit 1
fi

files="$(find memory -type f -name '20??-??-??.md' | sort)"

if [ -z "${files}" ]; then
  echo "No hay memorias diarias aun."
  exit 0
fi

echo "${files}" | tail -n "${days}" | while IFS= read -r f; do
  [ -n "$f" ] || continue
  echo "=================================================="
  echo "Archivo: $f"
  echo "=================================================="
  cat "$f"
  echo
done

