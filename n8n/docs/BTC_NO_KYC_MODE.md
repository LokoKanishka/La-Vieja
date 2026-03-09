# BTC No-KYC Mode (Paper Only)

Este modo evita entregar datos personales a exchanges centralizados.

## Objetivo

Operar el stack BTC en `paper` con datos reales de mercado y control de riesgo completo,
sin credenciales de exchange y sin activacion `live`.

## Comandos

1. Bloquear modo live y limpiar credenciales:

```bash
sh n8n/scripts/no_kyc_lockdown.sh
```

2. Correr ciclo operativo no-kYC (reconcile + alerts + go/no-go persistente):

```bash
sh n8n/scripts/no_kyc_cycle.sh
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
- Mantener seguimiento via:
  - `GET /ops/summary`
  - `POST /paper/go-no-go`
