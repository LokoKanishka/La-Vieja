#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/lucy/Escritorio/La Vieja"
cd "${ROOT_DIR}"

fail=0
warn=0

ok() {
  echo "OK: $1"
}

warning() {
  echo "WARN: $1"
  warn=$((warn + 1))
}

blocked() {
  echo "BLOCKED: $1"
  fail=$((fail + 1))
}

check_container() {
  local name="$1"
  if docker ps --format '{{.Names}}' | grep -qx "${name}"; then
    ok "contenedor ${name} activo"
  else
    blocked "contenedor ${name} no activo"
  fi
}

echo "== Full Test NO-KYC =="

check_container "btc_strategy_service"
check_container "n8n_trading"
check_container "btc_postgres"

if python3 -m py_compile n8n/trading_service/app.py; then
  ok "py_compile trading_service/app.py"
else
  blocked "py_compile trading_service/app.py"
fi

cycle_out="$(bash n8n/scripts/no_kyc_cycle.sh 2>&1)" || {
  printf '%s\n' "${cycle_out}"
  blocked "no_kyc_cycle.sh fallo"
}
printf '%s\n' "${cycle_out}"

set +e
zero_cost_out="$(bash n8n/scripts/zero_cost_guard.sh 2>&1)"
zero_cost_rc=$?
set -e
printf '%s\n' "${zero_cost_out}"
if [[ "${zero_cost_rc}" -eq 0 ]]; then
  ok "zero_cost_guard en verde (sin claves pagas)"
else
  blocked "zero_cost_guard detecto configuracion con costo (rc=${zero_cost_rc})"
fi

health_json="$(curl -fsS http://127.0.0.1:8100/health)" || {
  blocked "health endpoint no responde"
  health_json='{}'
}
if printf '%s' "${health_json}" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("status")=="ok"; assert d.get("mode")=="paper"'; then
  ok "health status=ok y mode=paper"
else
  blocked "health fuera de estado esperado"
fi

ops_json="$(curl -fsS http://127.0.0.1:8100/ops/summary)" || {
  blocked "ops/summary endpoint no responde"
  ops_json='{}'
}
if printf '%s' "${ops_json}" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True'; then
  ok "ops/summary ok=true"
else
  blocked "ops/summary no valido"
fi

open_intents_json="$(curl -fsS 'http://127.0.0.1:8100/execution/intents?status=open&limit=20')" || {
  blocked "execution/intents?status=open no responde"
  open_intents_json='{}'
}
if printf '%s' "${open_intents_json}" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; assert isinstance(d.get("count"), int)'; then
  open_count="$(printf '%s' "${open_intents_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("count", -1))')"
  ok "intents abiertos consultables (count=${open_count})"
else
  blocked "respuesta invalida en execution/intents?status=open"
fi

forecast_score_json="$(curl -fsS 'http://127.0.0.1:8100/forecast/scorecard?lookback_days=7&horizon_minutes=10&timeframe=5m')" || {
  blocked "forecast/scorecard endpoint no responde"
  forecast_score_json='{}'
}
if printf '%s' "${forecast_score_json}" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; assert isinstance(d.get("scorecard"), dict)'; then
  ok "forecast/scorecard responde con scorecard valido"
else
  blocked "forecast/scorecard no valido"
fi

workflow_count="$(docker exec btc_postgres psql -U n8n -d n8n -At -c "select count(*) from workflow_entity where name like 'BTC %' and active = true;" | tr -d '[:space:]')" || workflow_count="0"
if [[ "${workflow_count}" =~ ^[0-9]+$ ]] && [[ "${workflow_count}" -ge 8 ]]; then
  ok "workflows BTC activos: ${workflow_count} (minimo requerido 8)"
else
  blocked "workflows BTC activos insuficientes (actual ${workflow_count}, minimo 8)"
fi

set +e
readiness_out="$(bash n8n/scripts/prelive_readiness_check.sh 2>&1)"
readiness_rc=$?
set -e
printf '%s\n' "${readiness_out}"
if [[ "${readiness_rc}" -eq 0 ]]; then
  ok "prelive_readiness_check en verde"
elif [[ "${readiness_rc}" -eq 2 ]]; then
  warning "prelive_readiness_check bloqueado (esperable en ruta NO-KYC)"
else
  blocked "prelive_readiness_check fallo tecnico (rc=${readiness_rc})"
fi

echo "----"
echo "Resumen: failed=${fail} warn=${warn}"
if [[ "${fail}" -gt 0 ]]; then
  exit 1
fi
exit 0
