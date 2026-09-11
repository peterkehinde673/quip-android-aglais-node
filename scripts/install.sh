#!/usr/bin/env bash
# ==============================================================================
# quip-android-aglais-node Installation Script
# Target: Android ARM64 (e.g., Infinix Note G96) -> Termux -> Ubuntu PRoot
# ==============================================================================

set -e

echo "=================================================="
echo "Installing quip-android-aglais-node"
echo "=================================================="

# Check Python3
if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is not installed."
    echo "Inside Ubuntu PRoot run: apt update && apt install -y python3 python3-venv python3-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✓ Found Python $PYTHON_VERSION"

# Detect existing Quip environment or setup local venv
EXISTING_VENV="/root/quip-android-node/.quip"
LOCAL_VENV="./.quip"

if [ -d "$EXISTING_VENV" ] && [ -f "$EXISTING_VENV/bin/activate" ]; then
    echo "✓ Detected existing Quip virtualenv at $EXISTING_VENV"
    VENV_PATH="$EXISTING_VENV"
elif [ -d "$LOCAL_VENV" ] && [ -f "$LOCAL_VENV/bin/activate" ]; then
    echo "✓ Using local virtualenv at $LOCAL_VENV"
    VENV_PATH="$LOCAL_VENV"
else
    echo "Setting up new Python virtual environment in $LOCAL_VENV ..."
    python3 -m venv "$LOCAL_VENV"
    VENV_PATH="$LOCAL_VENV"
fi

# Activate venv
# shellcheck disable=SC1090
source "$VENV_PATH/bin/activate"
echo "✓ Virtual environment activated: $VENV_PATH"

# Install package in editable development mode
echo "Installing dependencies and quip-android CLI..."
if command -v pip >/dev/null 2>&1; then
    pip install --no-cache-dir -e . || pip install --no-cache-dir -r requirements.txt || true
else
    echo "Notice: pip not found inside environment; controller will run with zero-dependency fallback."
fi

# Setup config.toml if not already existing (never overwrite!)
if [ ! -f "config.toml" ]; then
    echo "Initializing config.toml from config.example.toml ..."
    cp config.example.toml config.toml
    echo "✓ Created config.toml"
else
    echo "✓ Existing config.toml found (preserved without modification)"
fi

# Ensure data and logs directories exist
mkdir -p logs data

# Make CLI helper executable
chmod +x scripts/run.sh

echo ""
echo "=================================================="
echo "INSTALLATION COMPLETE"
echo "=================================================="
echo "Run diagnostics using:"
echo "  ./scripts/run.sh doctor"
echo ""
echo "Check Aglais Substrate RPC endpoints:"
echo "  ./scripts/run.sh rpc-check"
echo ""
echo "Start mining in low-power Eco mode:"
echo "  ./scripts/run.sh start --mode eco"
echo "=================================================="
