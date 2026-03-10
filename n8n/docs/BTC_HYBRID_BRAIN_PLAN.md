# BTC Hybrid Brain Plan (Zero-Cost Skeleton)

## Objetivo

Combinar motor cuantitativo (`strategy_service`) con capa IA (`Molbot`) en modo `shadow` primero,
sin costo extra ni tarjetas, para validar si el híbrido supera a quant puro en 5-10 minutos.

## Reglas Fijas

1. Cero costo extra: sin API keys pagas en esta máquina.
2. Cero KYC: `paper` + intents externos manuales.
3. Seguridad primero: modo `shadow` por defecto (sin ejecución automática del híbrido).

## Arquitectura Híbrida

1. `n8n` orquesta.
2. `strategy_service` genera señal quant y evalúa forecast.
3. `Molbot` (cuando se conecte) aporta `ai_action/ai_confidence/ai_reason`.
4. Endpoint `POST /hybrid/decision` fusiona quant + AI y guarda decisión en `hybrid_decisions`.
5. Endpoint `GET /hybrid/scorecard` compara performance de quant vs AI vs híbrido.

## Estado Del Esqueleto (implementado)

1. Tabla `hybrid_decisions` + índices.
2. Endpoints:
   - `POST /hybrid/decision`
   - `GET /hybrid/decisions`
   - `GET /hybrid/scorecard`
3. Workflow `BTC Hybrid Shadow 5m`:
   - build features -> evaluate signal -> consulta IA (`MOLBOT_WEBHOOK_URL` o fallback) -> hybrid decision -> evaluate due -> scorecard -> alerts.
4. Workflow `BTC Hybrid Hourly Report 1h`:
   - scorecard híbrido + evaluación de alertas + score forecast.
4. Scripts:
   - `n8n/scripts/hybrid_shadow_tick.sh`
   - `n8n/scripts/hybrid_scorecard.sh`
   - `n8n/scripts/hybrid_backfill_shadow.sh`
   - `n8n/scripts/hybrid_hourly_report.sh`
   - `n8n/scripts/no_kyc_intents_autocancel.sh`
   - `n8n/scripts/backfill_market_binance_5m.sh`
5. `no_kyc_cycle.sh` y `full_test_no_kyc.sh` incluyen score y alertas híbridas.
6. Calidad de muestra:
   - `POST /signal/evaluate` es idempotente por vela (`ts+symbol+strategy_version`), evitando señales duplicadas.
   - `hybrid_backfill_shadow.sh` usa señales únicas por vela (`DISTINCT ON`) para no inflar decisiones repetidas.
   - Forecast/features ahora prefieren velas 5m alineadas y venue `binance` en empate temporal para reducir ruido de fuentes mezcladas.

## Política De Decisión Híbrida (actual)

1. Si quant = `hold` -> híbrido = `hold`.
2. Si quant y AI coinciden y AI supera umbral -> híbrido toma esa acción.
3. Si no hay acuerdo y `HYBRID_ALLOW_AI_OVERRIDE=true` con AI fuerte -> híbrido puede seguir AI.
4. Si no hay acuerdo y AI no supera umbral -> `quant_primary` solo si `HYBRID_REQUIRE_AI_AGREEMENT=false` y quant supera umbral.
5. Si nada anterior aplica -> híbrido = `hold`.
4. Configurable por variables:
   - `HYBRID_MODE`
   - `HYBRID_REQUIRE_AI_AGREEMENT`
   - `HYBRID_AI_MIN_CONFIDENCE`
   - `HYBRID_QUANT_MIN_CONFIDENCE`
   - `HYBRID_ALLOW_AI_OVERRIDE`
   - `HYBRID_FALLBACK_POLICY` (`same_as_quant|inverse_quant|hold_only|adaptive_edge`)
   - `HYBRID_FALLBACK_LOOKBACK_DAYS`
   - `HYBRID_FALLBACK_MIN_SAMPLES`
   - `HYBRID_FALLBACK_EDGE_MARGIN_BPS`
   - `FORECAST_MAX_ABS_CHANGE_BPS` (excluye outliers extremos en scorecards)

Configuración operativa actual NO-KYC:
- `SIGNAL_POLICY=mom_inverse`
- `SIGNAL_MOM_THRESHOLD=0.0005`
- `HYBRID_FALLBACK_POLICY=same_as_quant`
- `HYBRID_ALERT_MIN_ACCURACY=0.45`

## Contrato Molbot

El nodo IA espera respuesta JSON con:

1. `ai_action` (`buy|sell|hold`)
2. `ai_confidence` (`0..1`)
3. `ai_reason` (texto corto)
4. `ai_model` (ej. `openai-codex/gpt-5.2`)
5. `ai_source` (ej. `molbot`)

Si `MOLBOT_WEBHOOK_URL` no está definido, usa `POST /hybrid/ai/fallback`.
En fallback `adaptive_edge`, la IA local elige entre `same_as_quant` o `inverse_quant`
según edge histórico reciente (con muestra mínima y exclusión de outliers).

## Métricas De Paso

1. Mínimo 50 decisiones híbridas con outcome.
2. `hybrid.accuracy >= 0.45`.
3. `hybrid.avg_edge_bps > 0`.
4. Híbrido debe superar quant en al menos 7 días continuos.

## Comandos Rápidos

```bash
bash n8n/scripts/hybrid_shadow_tick.sh
sh n8n/scripts/hybrid_scorecard.sh 7 shadow 10 5m
curl -s "http://127.0.0.1:8100/hybrid/decisions?mode=shadow&limit=20"
```
