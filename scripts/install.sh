#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
echo "== quip-android-aglais-node minimal setup =="
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Termux: pkg install python"
  exit 1
fi
VENV_PATH="${QUIP_ANDROID_VENV:-$ROOT_DIR/.venv}"
if [ ! -x "$VENV_PATH/bin/python" ]; then
  python3 -m venv "$VENV_PATH"
fi
"$VENV_PATH/bin/python" -m pip install --upgrade pip
"$VENV_PATH/bin/python" -m pip install --no-cache-dir -e .
mkdir -p logs data
if [ ! -f config.toml ]; then
  cp config.example.toml config.toml
  echo "Created config.toml"
else
  echo "Preserved existing config.toml"
fi
chmod +x scripts/run.sh scripts/termux-setup.sh
echo "Controller installed."
echo "Next: ./scripts/run.sh doctor"
echo "The official quip-miner runtime is detected separately and its config is validated before mining."
