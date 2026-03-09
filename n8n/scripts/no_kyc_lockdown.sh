#!/usr/bin/env sh
set -eu

ROOT_DIR="/home/lucy/Escritorio/La Vieja"
ENV_FILE="${ROOT_DIR}/n8n/.env.trading"

if [ ! -f "${ENV_FILE}" ]; then
  echo "ERROR: falta ${ENV_FILE}" >&2
  exit 1
fi

upsert_env() {
  key="$1"
  value="$2"
  if grep -q "^${key}=" "${ENV_FILE}"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "${ENV_FILE}"
  else
    printf '%s=%s\n' "${key}" "${value}" >> "${ENV_FILE}"
  fi
}

upsert_env "TRADING_MODE" "paper"
upsert_env "EXCHANGE_ADAPTER" "paper"
upsert_env "EXCHANGE_SANDBOX" "false"
upsert_env "EXCHANGE_API_KEY" ""
upsert_env "EXCHANGE_API_SECRET" ""
upsert_env "EXCHANGE_API_PASSPHRASE" ""

cd "${ROOT_DIR}/n8n"
docker compose -f docker-compose.trading.yml --env-file .env.trading up -d strategy_service >/dev/null

echo "NO-KYC lockdown aplicado: TRADING_MODE=paper, EXCHANGE_ADAPTER=paper, credenciales vacias."
