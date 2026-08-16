#!/usr/bin/env bash
#
# Install & enable the TangBox systemd service so the Pi boots into TV mode.
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="${REPO_DIR}/scripts/tangbox.service"
TARGET="/etc/systemd/system/tangbox.service"

RUN_USER="${SUDO_USER:-$USER}"
RUN_UID="$(id -u "${RUN_USER}")"
RUN_HOME="$(getent passwd "${RUN_USER}" | cut -d: -f6)"

if [[ ! -x "${REPO_DIR}/.venv/bin/tangbox" ]]; then
  echo "error: ${REPO_DIR}/.venv/bin/tangbox not found." >&2
  echo "Run ./scripts/install.sh first." >&2
  exit 1
fi

echo "==> Rendering service unit for user '${RUN_USER}'"
tmp="$(mktemp)"
sed \
  -e "s|__USER__|${RUN_USER}|g" \
  -e "s|__UID__|${RUN_UID}|g" \
  -e "s|__HOME__|${RUN_HOME}|g" \
  -e "s|__REPO_DIR__|${REPO_DIR}|g" \
  "${TEMPLATE}" > "${tmp}"

echo "==> Installing ${TARGET}"
sudo cp "${tmp}" "${TARGET}"
rm -f "${tmp}"

echo "==> Allowing '${RUN_USER}' to power off without a password (for the"
echo "    volume-down-past-zero shutdown)"
sudo tee /etc/sudoers.d/tangbox-poweroff > /dev/null <<EOF
${RUN_USER} ALL=(root) NOPASSWD: /sbin/poweroff, /usr/sbin/poweroff, /sbin/shutdown, /usr/sbin/shutdown, /usr/bin/systemctl poweroff
EOF
sudo chmod 440 /etc/sudoers.d/tangbox-poweroff

echo "==> Enabling and starting the service"
sudo systemctl daemon-reload
sudo systemctl enable tangbox.service
sudo systemctl restart tangbox.service

cat <<EOF

==> Service installed.

Handy commands:
  systemctl status tangbox     # is it running?
  journalctl -u tangbox -f     # live logs
  sudo systemctl stop tangbox  # stop the TV
  sudo systemctl disable tangbox   # don't start on boot
EOF
