#!/usr/bin/env bash
# Levanta el servidor de subtítulos en vivo.
#   ./scripts/run.sh                    # usa .env / sessions.yaml
#   CAPTIONS_ENGINE=mock ./scripts/run.sh
#   ./scripts/run.sh sessions.yaml
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  echo "No existe .venv. Creando entorno e instalando dependencias..."
  uv venv .venv
  uv pip install --python .venv/bin/python -r requirements.txt
fi

if [ -f .env ]; then
  set -a; source .env; set +a
fi

CONFIG="${1:-${CAPTIONS_CONFIG:-sessions.yaml}}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "Sincro → http://localhost:${PORT}  (config: ${CONFIG})"
exec .venv/bin/uvicorn captions.main:app --app-dir src --host "${HOST}" --port "${PORT}"
