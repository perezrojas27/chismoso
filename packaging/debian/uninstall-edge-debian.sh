#!/usr/bin/env bash
# Desinstala el servicio systemd Albatros Edge (Debian).
#   sudo bash packaging/debian/uninstall-edge-debian.sh
#   sudo REMOVE_FILES=1 bash packaging/debian/uninstall-edge-debian.sh
set -euo pipefail

INSTALL_DIR="${ALBATROS_EDGE_HOME:-/opt/albatros-edge}"
SERVICE_USER="${ALBATROS_EDGE_USER:-albatros-edge}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Ejecute con sudo/root." >&2
  exit 1
fi

systemctl stop albatros-edge.service 2>/dev/null || true
systemctl disable albatros-edge.service 2>/dev/null || true
rm -f /etc/systemd/system/albatros-edge.service
systemctl daemon-reload

if [[ "${REMOVE_FILES:-0}" == "1" ]]; then
  rm -rf "$INSTALL_DIR"
  if id -u "$SERVICE_USER" &>/dev/null; then
    userdel "$SERVICE_USER" 2>/dev/null || true
  fi
  echo "Eliminado $INSTALL_DIR y usuario $SERVICE_USER"
else
  echo "Servicio quitado. Datos en $INSTALL_DIR conservados (REMOVE_FILES=1 para borrar)."
fi
