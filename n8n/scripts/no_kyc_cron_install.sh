#!/usr/bin/env sh
set -eu

ROOT_DIR="/home/lucy/Escritorio/La Vieja"
LOG_DIR="${ROOT_DIR}/n8n/logs"
CRON_BEGIN="# BEGIN NO_KYC_CYCLE"
CRON_END="# END NO_KYC_CYCLE"
CRON_LINE='*/15 * * * * cd "/home/lucy/Escritorio/La Vieja" && /bin/sh n8n/scripts/no_kyc_cycle.sh >> n8n/logs/no_kyc_cycle.log 2>&1'

mkdir -p "${LOG_DIR}"

TMP_FILE="$(mktemp)"
EXISTING="$(mktemp)"
trap 'rm -f "${TMP_FILE}" "${EXISTING}"' EXIT

crontab -l 2>/dev/null > "${EXISTING}" || true

awk -v b="${CRON_BEGIN}" -v e="${CRON_END}" '
  $0 == b {skip=1; next}
  $0 == e {skip=0; next}
  skip != 1 {print}
' "${EXISTING}" > "${TMP_FILE}"

{
  echo "${CRON_BEGIN}"
  echo "${CRON_LINE}"
  echo "${CRON_END}"
} >> "${TMP_FILE}"

crontab "${TMP_FILE}"
echo "Cron NO-KYC instalado: cada 15 minutos."
echo "Log: ${LOG_DIR}/no_kyc_cycle.log"
