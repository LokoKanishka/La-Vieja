#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Uso: $0 \"resumen\" [detalle] [tags_csv]" >&2
  exit 1
fi

summary="$1"
details="${2:-}"
tags_csv="${3:-general}"

date_str="$(date +%F)"
time_str="$(date +%T)"
year="$(date +%Y)"
month="$(date +%m)"

mem_dir="memory/${year}/${month}"
mem_file="${mem_dir}/${date_str}.md"
index_file="memory/index.jsonl"

mkdir -p "${mem_dir}"
mkdir -p "memory"
touch "${index_file}"

if [[ ! -f "${mem_file}" ]]; then
  cat > "${mem_file}" <<EOF
# Memoria ${date_str}

## Resumen Del Dia
- Pendiente de cierre.

## Conversaciones
EOF
fi

{
  echo
  echo "### ${time_str} - ${summary}"
  echo "- Tags: ${tags_csv}"
  if [[ -n "${details}" ]]; then
    echo "- Detalle: ${details}"
  fi
} >> "${mem_file}"

json_escape() {
  local s="${1}"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  printf "%s" "${s}"
}

summary_j="$(json_escape "${summary}")"
details_j="$(json_escape "${details}")"
tags_j="$(json_escape "${tags_csv}")"
file_j="$(json_escape "${mem_file}")"

printf '{"date":"%s","time":"%s","summary":"%s","details":"%s","tags":"%s","file":"%s"}\n' \
  "${date_str}" "${time_str}" "${summary_j}" "${details_j}" "${tags_j}" "${file_j}" >> "${index_file}"

echo "Guardado en ${mem_file}"

