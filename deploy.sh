#!/usr/bin/env bash
# Despliega una versión y, si no queda sana, vuelve a la anterior.
# Uso: ./deploy.sh <tag>   (el tag es el SHA del commit)
set -euo pipefail

# En la VM usa compose.prod.yaml. Para probarlo en local: COMPOSE_FILE=compose.yaml ./deploy.sh <tag>
export COMPOSE_FILE="${COMPOSE_FILE:-compose.prod.yaml}"

NEW="${1:?Uso: ./deploy.sh <tag>}"
PREV="$(cat .deployed-tag 2>/dev/null || true)"

echo "Desplegando $NEW (versión actual: ${PREV:-ninguna})"

# --wait espera hasta 60 s a que el healthcheck de cada servicio diga que está sano.
if TAG="$NEW" docker compose up -d --wait --wait-timeout 60; then
  echo "$NEW" > .deployed-tag
  echo "La versión $NEW quedó sana"
  exit 0
fi

echo "La versión $NEW no quedó sana; vuelvo a ${PREV:-ninguna}"
if [ -n "$PREV" ]; then
  TAG="$PREV" docker compose up -d --wait --wait-timeout 60
fi
exit 1 # termina en error aunque el rollback funcione, para que CI quede en rojo
