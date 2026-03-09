#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/lucy/Escritorio/La Vieja"
ENV_FILE="${ROOT_DIR}/n8n/.env.trading"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "BLOCKED: falta ${ENV_FILE}"
  exit 1
fi

env_get() {
  local key="$1"
  local line
  line="$(grep -E "^${key}=" "${ENV_FILE}" | tail -n 1 || true)"
  printf '%s' "${line#*=}"
}

fail=0

ok() {
  echo "OK: $1"
}

blocked() {
  echo "BLOCKED: $1"
  fail=$((fail + 1))
}

trading_mode="$(env_get TRADING_MODE)"
exchange_adapter="$(env_get EXCHANGE_ADAPTER)"

if [[ "${trading_mode:-paper}" == "paper" ]]; then
  ok "TRADING_MODE=paper"
else
  blocked "TRADING_MODE debe ser paper (actual=${trading_mode})"
fi

if [[ "${exchange_adapter:-paper}" == "paper" ]]; then
  ok "EXCHANGE_ADAPTER=paper"
else
  blocked "EXCHANGE_ADAPTER debe ser paper (actual=${exchange_adapter})"
fi

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
  value="$(env_get "${key}")"
  if [[ -n "${value}" ]]; then
    blocked "${key} debe estar vacia en modo cero pesos"
  else
    ok "${key} vacia"
  fi
done

echo "----"
echo "Resumen: blocked=${fail}"
if [[ "${fail}" -gt 0 ]]; then
  exit 2
fi
exit 0

