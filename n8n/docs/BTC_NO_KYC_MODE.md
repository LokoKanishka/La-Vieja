# BTC No-KYC Mode (Paper Only)

Este modo evita entregar datos personales a exchanges centralizados.
Regla de oro operativa: cero tarjeta y cero costo extra.

## Objetivo

Operar el stack BTC en `paper` con datos reales de mercado y control de riesgo completo,
sin credenciales de exchange y sin activacion `live`.

En este modo, la ejecucion pasa por `intents` no-KYC:
- `POST /execution/intent` crea una orden externa pendiente.
- `POST /execution/intent/confirm` confirma resultado real (filled/rejected/canceled).
- `POST /execution/intents/reconcile-electrum` revisa `txid` en Electrum y marca `settled` cuando confirma.

Validacion de "adelantarse en el tiempo":
- `POST /forecast/checkpoint` guarda prediccion con horizonte (ej: +10 minutos).
- `POST /forecast/evaluate-due` evalua si esa prediccion acerto o fallo al vencimiento.
- `GET /forecast/scorecard` muestra accuracy y edge real.

## Comandos

1. Bloquear modo live y limpiar credenciales:

```bash
sh n8n/scripts/no_kyc_lockdown.sh
```

2. Correr ciclo operativo no-kYC (reconcile + alerts + go/no-go persistente):

```bash
sh n8n/scripts/no_kyc_cycle.sh
```

3. Activar watchdog persistente (arranque + cada 5 minutos):

```bash
sh n8n/scripts/no_kyc_cron_install.sh
```

4. Ejecutar watchdog manual (recupera stack y corre ciclo sin depender de pantalla):

```bash
bash n8n/scripts/no_kyc_guardian.sh
```

5. Ver intents abiertos:

```bash
sh n8n/scripts/no_kyc_intents_open.sh 20
```

6. Confirmar resultado de un intent manual:

```bash
# filled
sh n8n/scripts/no_kyc_intent_confirm.sh <intent_id> filled <fill_price> <filled_qty> [txid]

# rejected o canceled
sh n8n/scripts/no_kyc_intent_confirm.sh <intent_id> rejected
```

7. Test completo NO-KYC (1 comando):

```bash
bash n8n/scripts/full_test_no_kyc.sh
```

8. Generar señal + checkpoint ahora (aviso operativo) y revisar score:

```bash
# alerta inmediata (buy/sell/hold) + checkpoint a 10m
bash n8n/scripts/forecast_tick_5m.sh 10 5

# score de capacidad predictiva
sh n8n/scripts/forecast_scorecard.sh 7 10 5m
```

9. Verificacion estricta de modo cero pesos:

```bash
bash n8n/scripts/zero_cost_guard.sh
```

10. Esqueleto híbrido (quant + IA) en modo sombra:

```bash
bash n8n/scripts/hybrid_shadow_tick.sh
sh n8n/scripts/hybrid_scorecard.sh 7 shadow 10 5m
```

11. Backfill híbrido para construir muestra rápida:

```bash
bash n8n/scripts/hybrid_backfill_shadow.sh 120
```

12. Limpieza de intents abiertos (todo o por antigüedad):

```bash
# cerrar todos
bash n8n/scripts/no_kyc_intents_autocancel.sh --all

# cerrar solo intents con más de 120 min
bash n8n/scripts/no_kyc_intents_autocancel.sh 120
```

13. Reporte/alerta híbrida (manual):

```bash
bash n8n/scripts/hybrid_hourly_report.sh
```

## Garantias del modo

- `TRADING_MODE=paper`
- `EXCHANGE_ADAPTER=paper`
- `EXCHANGE_API_KEY` vacia
- `EXCHANGE_API_SECRET` vacia
- `EXCHANGE_API_PASSPHRASE` vacia
- `OPENAI_API_KEY` vacia
- `ANTHROPIC_API_KEY` vacia
- `GOOGLE_API_KEY` vacia
- `GEMINI_API_KEY` vacia

## Uso recomendado

- Ejecutar `no_kyc_lockdown.sh` al inicio de sesion.
- Mantener watchdog con `no_kyc_cron_install.sh` (`@reboot` + cada 5 minutos).
- Usar `no_kyc_guardian.sh` para recuperación manual rápida.
- Ver logs del watchdog en `n8n/logs/no_kyc_guardian.log`.
- Mantener seguimiento via:
  - `GET /ops/summary`
  - `POST /paper/go-no-go`
  - `GET /execution/intents?status=open`
