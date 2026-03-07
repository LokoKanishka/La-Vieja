#!/usr/bin/env sh
set -eu

ROOT_DIR="/home/lucy/Escritorio/La Vieja"
cd "${ROOT_DIR}"

export WF_DIR="n8n/workflows/trading"
export N8N_BASE_URL="${N8N_BASE_URL:-http://127.0.0.1:5111/api/v1}"
export N8N_HEALTH_URL="${N8N_HEALTH_URL:-http://127.0.0.1:5111}"

bash ./n8n/scripts/import_workflows_api.sh
