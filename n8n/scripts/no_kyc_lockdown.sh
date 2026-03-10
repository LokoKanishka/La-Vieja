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
upsert_env "SIGNAL_POLICY" "mom_inverse"
upsert_env "SIGNAL_ADAPT_LOOKBACK_DAYS" "14"
upsert_env "SIGNAL_ADAPT_MIN_SAMPLES" "40"
upsert_env "SIGNAL_ADAPT_EDGE_MARGIN_BPS" "0"
upsert_env "SIGNAL_MOM_THRESHOLD" "0.0005"
upsert_env "RECONCILE_CONTINUITY_GAP_MINUTES" "30"
upsert_env "HYBRID_MODE" "shadow"
upsert_env "HYBRID_REQUIRE_AI_AGREEMENT" "false"
upsert_env "HYBRID_AI_MIN_CONFIDENCE" "0.60"
upsert_env "HYBRID_QUANT_MIN_CONFIDENCE" "0.10"
upsert_env "HYBRID_ALLOW_AI_OVERRIDE" "true"
upsert_env "HYBRID_FALLBACK_POLICY" "same_as_quant"
upsert_env "HYBRID_FALLBACK_MIN_CONFIDENCE" "0.70"
upsert_env "HYBRID_FALLBACK_LOOKBACK_DAYS" "7"
upsert_env "HYBRID_FALLBACK_MIN_SAMPLES" "30"
upsert_env "HYBRID_FALLBACK_EDGE_MARGIN_BPS" "0"
upsert_env "FORECAST_MAX_ABS_CHANGE_BPS" "1000"
upsert_env "HYBRID_ALERT_MIN_RESOLVED" "20"
upsert_env "HYBRID_ALERT_MIN_ACCURACY" "0.45"
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

attempts=0
until curl -fsS "http://127.0.0.1:8100/health" >/dev/null 2>&1; do
  attempts=$((attempts + 1))
  if [ "${attempts}" -ge 30 ]; then
    echo "ERROR: strategy_service no responde en /health tras aplicar lockdown" >&2
    exit 1
  fi
  sleep 1
done

echo "NO-KYC lockdown aplicado: paper only + claves de exchange/IA pagas vacias (modo cero pesos)."
