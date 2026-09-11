#!/usr/bin/env bash
# ==============================================================================
# quip-android launcher script
# Automatically activates detected virtualenv and forwards CLI arguments
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Try activating known virtualenvs
if [ -f "/root/quip-android-node/.quip/bin/activate" ]; then
    source "/root/quip-android-node/.quip/bin/activate"
elif [ -f "./.quip/bin/activate" ]; then
    source "./.quip/bin/activate"
elif [ -f "./.venv/bin/activate" ]; then
    source "./.venv/bin/activate"
fi

# Execute quip-android via installed script or python module fallback
if command -v quip-android >/dev/null 2>&1; then
    exec quip-android "$@"
else
    exec python3 -m quip_android.cli "$@"
fi
