#!/usr/bin/env bash
set -euo pipefail

days="${1:-2}"

if [[ ! -d memory ]]; then
  echo "No existe carpeta memory/" >&2
  exit 1
fi

mapfile -t files < <(find memory -type f -name '20??-??-??.md' | sort)

if [[ ${#files[@]} -eq 0 ]]; then
  echo "No hay memorias diarias aun."
  exit 0
fi

if [[ "${days}" -gt "${#files[@]}" ]]; then
  days="${#files[@]}"
fi

start=$(( ${#files[@]} - days ))

for ((i=start; i<${#files[@]}; i++)); do
  echo "=================================================="
  echo "Archivo: ${files[$i]}"
  echo "=================================================="
  cat "${files[$i]}"
  echo
done

