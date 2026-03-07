#!/usr/bin/env bash
set -euo pipefail

USER_NAME="${USER:-lucy}"
REPO_DIR="/home/lucy/Escritorio/La Vieja"
SSH_KEY="${HOME}/.ssh/id_ed25519_lavieja"

cd "${REPO_DIR}"
mkdir -p "${HOME}/.ssh"
chmod 700 "${HOME}/.ssh"

if [[ ! -f "${SSH_KEY}" ]]; then
  ssh-keygen -t ed25519 -C "lavieja-codex" -f "${SSH_KEY}" -N ""
fi
chmod 600 "${SSH_KEY}"
chmod 644 "${SSH_KEY}.pub"
ssh-keyscan -t ed25519 github.com >> "${HOME}/.ssh/known_hosts" 2>/dev/null || true
chmod 600 "${HOME}/.ssh/known_hosts"

if [[ ! -f "${HOME}/.ssh/config" ]] || ! grep -q "Host github.com" "${HOME}/.ssh/config"; then
  cat >> "${HOME}/.ssh/config" <<CFG
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519_lavieja
  IdentitiesOnly yes
CFG
fi
chmod 600 "${HOME}/.ssh/config"

git remote set-url origin git@github.com:LokoKanishka/La-Vieja.git

echo
echo "== Paso GitHub (manual, una vez) =="
echo "Copia esta llave publica en GitHub > Settings > SSH and GPG keys > New SSH key:"
cat "${SSH_KEY}.pub"
echo
echo "URL directa: https://github.com/settings/keys"
echo
echo "Prueba SSH (esperado: success o permission denied si no agregaste key aun):"
ssh -T git@github.com || true

echo
echo "== Paso Docker (manual, una vez) =="
echo "Ejecuta en tu terminal local con password sudo:"
echo "  sudo usermod -aG docker ${USER_NAME}"
echo "Luego abre una nueva sesion (o reinicia) y valida con:"
echo "  docker ps"

echo
echo "Si quieres aplicar sin reiniciar toda la PC, en una sesion nueva ejecuta:"
echo "  newgrp docker"

echo
echo "== Verificacion final sugerida =="
echo "  cd '${REPO_DIR}'"
echo "  git push origin main"
echo "  sh n8n/scripts/trading_up.sh"
