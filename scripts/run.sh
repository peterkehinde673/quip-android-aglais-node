#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
VENV_PATH="${QUIP_ANDROID_VENV:-$ROOT_DIR/.venv}"
if [ -x "$VENV_PATH/bin/quip-android" ]; then
  exec "$VENV_PATH/bin/quip-android" "$@"
fi
exec python3 -m quip_android.cli "$@"
