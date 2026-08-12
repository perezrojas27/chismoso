#!/usr/bin/env bash
# Instala el cliente Albatros Edge en Debian 12+ (venv + systemd).
# Uso (desde la raíz del repo, como root o con sudo):
#   sudo bash packaging/debian/install-edge-debian.sh
#   sudo bash packaging/debian/install-edge-debian.sh /opt/ruta/albatros-biometrico
set -euo pipefail

REPO_ROOT="${1:-}"
if [[ -z "$REPO_ROOT" ]]; then
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
INSTALL_DIR="${ALBATROS_EDGE_HOME:-/opt/albatros-edge}"
SERVICE_USER="${ALBATROS_EDGE_USER:-albatros-edge}"
PORT="${BIOMETRICO_EDGE_PORT:-8003}"

if [[ ! -f "$REPO_ROOT/backend/edge_app/main.py" ]]; then
  echo "ERROR: no se encontró backend/edge_app en $REPO_ROOT" >&2
  exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Ejecute con sudo/root." >&2
  exit 1
fi

echo "==> Paquetes del sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip

if ! id -u "$SERVICE_USER" &>/dev/null; then
  echo "==> Usuario $SERVICE_USER"
  useradd --system --home-dir "$INSTALL_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

echo "==> Copiando a $INSTALL_DIR"
mkdir -p "$INSTALL_DIR/backend/data"
rsync -a --delete \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'data/' \
  "$REPO_ROOT/backend/edge_app/" "$INSTALL_DIR/backend/edge_app/"
rsync -a --delete \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "$REPO_ROOT/backend/shared/" "$INSTALL_DIR/backend/shared/"

REQ="$REPO_ROOT/backend/requirements-edge.txt"
[[ -f "$REQ" ]] || REQ="$REPO_ROOT/backend/requirements.txt"
cp -f "$REQ" "$INSTALL_DIR/backend/requirements-edge.txt"

ENV_DST="$INSTALL_DIR/backend/.env"
if [[ ! -f "$ENV_DST" ]]; then
  if [[ -f "$REPO_ROOT/.env.edge-sede.example" ]]; then
    cp "$REPO_ROOT/.env.edge-sede.example" "$ENV_DST"
  else
    cat >"$ENV_DST" <<EOF
SOURCE=hikvision
SITE_CODE=oficina_central
SITE_NAME=Sede
EDGE_DATA_DIR=$INSTALL_DIR/backend/data
EDGE_ADMIN_USER=admin
EDGE_ADMIN_PASSWORD=
AUTH_DISABLED=true
INTEGRADO_BASE_URL=
ENROLLMENT_TOKEN=
EOF
  fi
  # Forzar rutas Debian
  if grep -q '^EDGE_DATA_DIR=' "$ENV_DST"; then
    sed -i "s|^EDGE_DATA_DIR=.*|EDGE_DATA_DIR=$INSTALL_DIR/backend/data|" "$ENV_DST"
  else
    echo "EDGE_DATA_DIR=$INSTALL_DIR/backend/data" >>"$ENV_DST"
  fi
  echo "==> Creado $ENV_DST — EDITAR (EDGE_ADMIN_PASSWORD, INTEGRADO_BASE_URL, token)."
fi

echo "==> venv + pip"
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/backend/requirements-edge.txt"

chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

UNIT_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/albatros-edge.service"
UNIT_DST="/etc/systemd/system/albatros-edge.service"
sed -e "s|/opt/albatros-edge|$INSTALL_DIR|g" \
    -e "s|User=albatros-edge|User=$SERVICE_USER|g" \
    -e "s|Group=albatros-edge|Group=$SERVICE_USER|g" \
    -e "s|--port 8003|--port $PORT|g" \
    "$UNIT_SRC" >"$UNIT_DST"

systemctl daemon-reload
systemctl enable albatros-edge.service
systemctl restart albatros-edge.service

echo ""
echo "Listo. Consola: http://127.0.0.1:${PORT}/"
echo "Estado: systemctl status albatros-edge"
echo "Logs:   journalctl -u albatros-edge -f"
echo "Config: $ENV_DST"
