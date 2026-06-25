#!/usr/bin/env bash
#
# deploy.sh — install TallyBridge.py as a systemd service on Linux.
#
# Usage:
#   sudo ./deploy.sh
#
# Re-running is safe: it refreshes the installed code and restarts the service.

set -euo pipefail

INSTALL_DIR="/opt/tcp-udp-bridge"
SERVICE_USER="tallybridge"
SERVICE_NAME="tally-bridge"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Must run as root (needs to write to /opt and /etc/systemd) ---
if [[ "${EUID}" -ne 0 ]]; then
    echo "Error: please run with sudo (e.g. 'sudo ./deploy.sh')." >&2
    exit 1
fi

# --- Sanity check: required files are present alongside this script ---
for f in TallyBridge.py tally-bridge.service; do
    if [[ ! -f "${SCRIPT_DIR}/${f}" ]]; then
        echo "Error: ${f} not found next to deploy.sh." >&2
        exit 1
    fi
done

# --- Require Python 3 ---
if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is not installed. Install it and re-run." >&2
    exit 1
fi

echo "==> Installing code to ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"
install -m 644 "${SCRIPT_DIR}/TallyBridge.py" "${INSTALL_DIR}/TallyBridge.py"

echo "==> Ensuring service account '${SERVICE_USER}' exists"
if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
    useradd -r -s /usr/sbin/nologin "${SERVICE_USER}"
    echo "    created."
else
    echo "    already present."
fi

echo "==> Installing systemd unit"
install -m 644 "${SCRIPT_DIR}/tally-bridge.service" "/etc/systemd/system/${SERVICE_NAME}.service"

echo "==> Enabling and (re)starting service"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}" >/dev/null
systemctl restart "${SERVICE_NAME}"

echo
echo "Done. Service '${SERVICE_NAME}' is installed and running."
echo
systemctl --no-pager --full status "${SERVICE_NAME}" || true
echo
echo "Follow live logs with:  journalctl -u ${SERVICE_NAME} -f"
