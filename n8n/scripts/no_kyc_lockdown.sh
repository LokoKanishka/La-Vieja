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
upsert_env "HYBRID_MODE" "shadow"
upsert_env "HYBRID_REQUIRE_AI_AGREEMENT" "true"
upsert_env "HYBRID_ALERT_MIN_RESOLVED" "20"
upsert_env "HYBRID_ALERT_MIN_ACCURACY" "0.55"
upsert_env "HYBRID_ALERT_MIN_EDGE_BPS" "0"
for key in \
  EXCHANGE_API_KEY \
  EXCHANGE_API_SECRET \
  EXCHANGE_API_PASSPHRASE \
  OPENAI_API_KEY \
  ANTHROPIC_API_KEY \
  GOOGLE_API_KEY \
  GEMINI_API_KEY \
  GROQ_API_KEY \
  MISTRAL_API_KEY \
  PERPLEXITY_API_KEY \
  TOGETHER_API_KEY \
  COHERE_API_KEY \
  DEEPSEEK_API_KEY
do
  upsert_env "${key}" ""
done

cd "${ROOT_DIR}/n8n"
docker compose -f docker-compose.trading.yml --env-file .env.trading up -d strategy_service >/dev/null

echo "NO-KYC lockdown aplicado: paper only + claves de exchange/IA pagas vacias (modo cero pesos)."
