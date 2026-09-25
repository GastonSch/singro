#!/usr/bin/env bash
# Instalación de Sincro en un LXC Debian (sin Docker).
# Uso (como root):
#   sudo GEMINI_API_KEY=AIza... bash deploy/install-lxc.sh
# Opcional: REPO=... DIR=... para sobreescribir.
set -euo pipefail

REPO="${REPO:-https://github.com/GastonSch/singro.git}"
DIR="${DIR:-/opt/sincro}"
PORT="${PORT:-8000}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Ejecutá como root (sudo)." >&2
  exit 1
fi

echo ">> Dependencias del sistema"
apt-get update
apt-get install -y --no-install-recommends git ffmpeg python3-venv python3-pip curl ca-certificates

echo ">> Usuario de servicio"
id -u sincro >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin sincro

echo ">> Código en ${DIR}"
if [ -d "${DIR}/.git" ]; then
  git -C "${DIR}" pull --ff-only
else
  git clone "${REPO}" "${DIR}"
fi

echo ">> Entorno virtual + dependencias"
python3 -m venv "${DIR}/.venv"
"${DIR}/.venv/bin/pip" install -q --upgrade pip
"${DIR}/.venv/bin/pip" install -q -r "${DIR}/requirements.txt"

if [ ! -f "${DIR}/.env" ]; then
  echo ">> Creando ${DIR}/.env"
  cat > "${DIR}/.env" <<ENV
CAPTIONS_ENGINE=gemini_live
GEMINI_API_KEY=${GEMINI_API_KEY:-}
CAPTIONS_MODEL=gemini-3.5-live-translate-preview
CAPTIONS_REST_MODEL=gemini-3.8-flash
CAPTIONS_NATIVE_TRANSLATION=1
CAPTIONS_CONFIG=sessions.yaml
HOST=0.0.0.0
PORT=${PORT}
ENV
else
  echo ">> ${DIR}/.env ya existe, no se toca"
fi

chown -R sincro:sincro "${DIR}"

echo ">> Servicio systemd"
install -m 644 "${DIR}/deploy/sincro.service" /etc/systemd/system/sincro.service
systemctl daemon-reload
systemctl enable --now sincro
sleep 2

echo ">> Estado"
systemctl --no-pager --full status sincro | head -12 || true
echo
echo ">> Health local"
curl -s "http://127.0.0.1:${PORT}/api/health" || true
echo
echo "Listo. Si GEMINI_API_KEY quedó vacía, editá ${DIR}/.env y: systemctl restart sincro"
