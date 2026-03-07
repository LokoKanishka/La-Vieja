#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${N8N_API_KEY:-}" ]]; then
  echo "Falta N8N_API_KEY en el entorno." >&2
  exit 1
fi

base_url="${N8N_BASE_URL:-http://127.0.0.1:5111/api/v1}"
wf_dir="n8n/workflows"
health_url="${N8N_HEALTH_URL:-http://127.0.0.1:5111}"
replace_existing="${N8N_IMPORT_REPLACE:-true}"

if [[ ! -d "${wf_dir}" ]]; then
  echo "No existe ${wf_dir}" >&2
  exit 1
fi

echo "Esperando n8n en ${health_url} ..."
ok=0
for _ in $(seq 1 40); do
  if curl -sS -m 2 "${health_url}" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 1
done
if [[ "${ok}" -ne 1 ]]; then
  echo "n8n no responde aun en ${health_url}" >&2
  exit 1
fi

import_one() {
  local file="$1"
  local name
  name="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("name",""))' "${file}")"
  if [[ -z "${name}" ]]; then
    echo "Nombre de workflow vacio en ${file}" >&2
    exit 1
  fi

  local exists
  exists="$(curl -sS -f -G "${base_url}/workflows" \
    -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
    --data-urlencode "limit=200" \
    --data-urlencode "name=${name}" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(any(w.get("name")==sys.argv[1] for w in d.get("data",[])))' "${name}")"

  if [[ "${exists}" == "True" ]]; then
    if [[ "${replace_existing}" == "true" ]]; then
      old_ids="$(curl -sS -f -G "${base_url}/workflows" \
        -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
        --data-urlencode "limit=200" \
        --data-urlencode "name=${name}" \
        | python3 -c 'import json,sys; d=json.load(sys.stdin); print(" ".join([str(w.get("id")) for w in d.get("data",[]) if w.get("name")==sys.argv[1]]))' "${name}")"
      for oid in ${old_ids}; do
        echo "Eliminando workflow previo: ${name} (${oid})"
        curl -sS -f -X DELETE "${base_url}/workflows/${oid}" \
          -H "X-N8N-API-KEY: ${N8N_API_KEY}" >/dev/null
      done
    else
      echo "Ya existe: ${name} (skip)"
      return 0
    fi
  fi

  local tmp_json
  tmp_json="$(mktemp)"
  python3 - "${file}" "${tmp_json}" <<'PY'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
d = json.load(open(src))
keep = {k: d[k] for k in ("name", "nodes", "connections", "settings") if k in d}
json.dump(keep, open(dst, "w"))
PY

  echo "Importando ${name} ..."
  curl -sS -f -X POST "${base_url}/workflows" \
    -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
    -H "Content-Type: application/json" \
    --data-binary "@${tmp_json}" >/dev/null
  rm -f "${tmp_json}"

  LAST_IMPORTED_NAME="${name}"
}

shopt -s nullglob
LAST_IMPORTED_NAME=""
imported_count=0
declare -a imported_names=()

while IFS= read -r -d '' wf_file; do
  import_one "${wf_file}"
  imported_names+=("${LAST_IMPORTED_NAME}")
  imported_count=$((imported_count + 1))
done < <(find "${wf_dir}" -maxdepth 1 -type f -name '*.json' -print0 | sort -z)

if [[ "${imported_count}" -eq 0 ]]; then
  echo "No hay workflows JSON para importar en ${wf_dir}" >&2
  exit 1
fi

declare -A seen_names=()
for name in "${imported_names[@]}"; do
  if [[ -n "${seen_names[${name}]:-}" ]]; then
    continue
  fi
  seen_names["${name}"]=1
  wid="$(curl -sS -f -G "${base_url}/workflows" \
    -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
    --data-urlencode "limit=200" \
    --data-urlencode "name=${name}" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); ms=[w.get("id") for w in d.get("data",[]) if w.get("name")==sys.argv[1]]; print(ms[-1] if ms else "")' "${name}")"
  if [[ -n "${wid}" ]]; then
    curl -sS -f -X POST "${base_url}/workflows/${wid}/activate" \
      -H "X-N8N-API-KEY: ${N8N_API_KEY}" >/dev/null
    echo "Activado: ${name} (${wid})"
  fi
done

echo "Importacion completada."
