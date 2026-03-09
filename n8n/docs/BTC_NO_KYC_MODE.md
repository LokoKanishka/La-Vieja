# BTC No-KYC Mode (Paper Only)

Este modo evita entregar datos personales a exchanges centralizados.

## Objetivo

Operar el stack BTC en `paper` con datos reales de mercado y control de riesgo completo,
sin credenciales de exchange y sin activacion `live`.

En este modo, la ejecucion pasa por `intents` no-KYC:
- `POST /execution/intent` crea una orden externa pendiente.
- `POST /execution/intent/confirm` confirma resultado real (filled/rejected/canceled).
- `POST /execution/intents/reconcile-electrum` revisa `txid` en Electrum y marca `settled` cuando confirma.

## Comandos

1. Bloquear modo live y limpiar credenciales:

```bash
sh n8n/scripts/no_kyc_lockdown.sh
```

2. Correr ciclo operativo no-kYC (reconcile + alerts + go/no-go persistente):

```bash
sh n8n/scripts/no_kyc_cycle.sh
```

3. Activar automatizacion cada 15 minutos (cron):

```bash
sh n8n/scripts/no_kyc_cron_install.sh
```

4. Ver intents abiertos:

```bash
sh n8n/scripts/no_kyc_intents_open.sh 20
```

5. Confirmar resultado de un intent manual:

```bash
# filled
sh n8n/scripts/no_kyc_intent_confirm.sh <intent_id> filled <fill_price> <filled_qty> [txid]

# rejected o canceled
sh n8n/scripts/no_kyc_intent_confirm.sh <intent_id> rejected
```

## Garantias del modo

- `TRADING_MODE=paper`
- `EXCHANGE_ADAPTER=paper`
- `EXCHANGE_API_KEY` vacia
- `EXCHANGE_API_SECRET` vacia
- `EXCHANGE_API_PASSPHRASE` vacia

## Uso recomendado

- Ejecutar `no_kyc_lockdown.sh` al inicio de sesion.
- Ejecutar `no_kyc_cycle.sh` en cada ronda operativa (o cron).
- Ver logs del cron en `n8n/logs/no_kyc_cycle.log`.
- Mantener seguimiento via:
  - `GET /ops/summary`
  - `POST /paper/go-no-go`
  - `GET /execution/intents?status=open`
