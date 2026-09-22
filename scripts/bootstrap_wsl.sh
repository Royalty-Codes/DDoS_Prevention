#!/usr/bin/env bash
set -euo pipefail

# The system Python runs Mininet. A separate Python 3.11 environment runs Ryu,
# because the legacy Ryu/Eventlet stack is not validated on Python 3.14.
if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash scripts/bootstrap_wsl.sh" >&2
  exit 1
fi

apt-get update
apt-get install -y \
  mininet \
  openvswitch-switch \
  tcpdump \
  iperf3 \
  curl \
  netcat-openbsd \
  ca-certificates \
  python3-pip

systemctl enable --now openvswitch-switch 2>/dev/null || service openvswitch-switch start
mn -c

# Codex/WSL can inherit a Windows-side VIRTUAL_ENV whose interpreter does not
# exist in Linux. It makes uv reject otherwise valid Python installations.
unset VIRTUAL_ENV
if ! command -v uv >/dev/null 2>&1; then
  # A pip wheel is more reliable in restricted WSL environments than piping a
  # remote installer into the shell.
  python3 -m pip install --break-system-packages --user uv
fi
export PATH="/root/.local/bin:${PATH}"
uv python install 3.11
# Keep the virtual environment on the Linux filesystem. A venv under /mnt/d
# fails when pip atomically replaces packages across the Windows/Linux mount.
CONTROLLER_VENV="${SDN_DDOS_CONTROLLER_VENV:-/opt/sdn-ddos-ryu-venv}"
if [[ ! -x "$CONTROLLER_VENV/bin/python" ]]; then
  uv venv "$CONTROLLER_VENV" --python 3.11
fi
# Ryu 4.34 imports a setuptools easy_install API removed by modern setuptools.
# Keep this compatibility pin inside the controller-only environment.
"$CONTROLLER_VENV/bin/python" -m ensurepip --upgrade
"$CONTROLLER_VENV/bin/python" -m pip install --force-reinstall --no-deps setuptools==57.5.0 wheel
"$CONTROLLER_VENV/bin/python" -m pip install --no-build-isolation -r requirements-controller.txt

echo "System packages installed. Use: export RYU_MANAGER=$CONTROLLER_VENV/bin/ryu-manager"
echo "Capture runs with system python3 so Mininet remains importable. Install requirements-lab.txt in a compatible Python environment for final Parquet materialization."
