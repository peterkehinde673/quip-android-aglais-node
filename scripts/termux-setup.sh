#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
echo "== Termux setup for quip-android-aglais-node =="
if [ ! -x "$PREFIX/bin/pkg" ]; then
  echo "Run this script inside Termux."
  exit 1
fi
pkg update -y
pkg install -y git python
echo "Controller prerequisites installed."
echo "Clone the repository and run ./scripts/install.sh then ./scripts/run.sh doctor"
echo "This installs the lightweight controller only. A real compatible quip-miner must still be detected."
