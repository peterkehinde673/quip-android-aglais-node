# Android & Termux Ubuntu PRoot Guide

Complete guide for deploying and running `quip-android-aglais-node` on Android ARM64 devices, specifically calibrated for the **Infinix Note G96** (MediaTek Helio G96, 8-Core ARM64 Cortex-A76/A55, Mali-G57 MC2).

---

## 1. Prerequisites inside Termux

Install Termux from F-Droid (do not use Google Play versions as they are deprecated).

Inside Termux, execute:
```bash
pkg update && pkg upgrade -y
pkg install proot-distro git curl wget -y
```

Install Ubuntu PRoot:
```bash
proot-distro install ubuntu
proot-distro login ubuntu
```

---

## 2. Environment Preparation in Ubuntu PRoot

Inside your Ubuntu PRoot shell:
```bash
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip git build-essential procps
```

---

## 3. Quip Miner Binary Setup

If you already have `quip-miner` built in your environment (for example under `/root/quip-android-node/.quip/bin/quip-miner` or `~/.quip/bin/quip-miner`):
Verify it runs:
```bash
quip-miner --version
```
Ensure it matches Quip v0.2.1+.

If `quip-miner` is located at a custom path, update `config.toml`:
```toml
[miner]
quip_miner_path = "/path/to/quip-miner"
```

---

## 4. Node Controller Installation

```bash
cd /root
git clone https://github.com/quip-network/quip-android-aglais-node.git
cd quip-android-aglais-node

# Run installation script
./scripts/install.sh
```

The script automatically detects existing Quip virtual environments (such as `/root/quip-android-node/.quip`) or provisions a clean `.quip` venv.

---

## 5. Thermal & Power Optimization for Infinix Note G96

The MediaTek Helio G96 contains:
- 2x Performance Cortex-A76 cores (@ 2.05 GHz)
- 6x Efficiency Cortex-A55 cores (@ 2.0 GHz)

### Recommendations:
1. **Eco Mode (`--mode eco`)**: Uses 1 CPU worker and applies `nice 19`. Keeps CPU temperature below 48°C and avoids aggressive battery drain.
2. **Daily Mode (`--mode daily`)**: Target 5–10 qblocks per day during low-activity hours. Automatically stops once target participation is reached.
3. **Screen Off**: In Termux, enable `Acquire Wakelock` from the Android notification bar to keep the process running when the screen is locked.
4. **Charging**: If running multi-hour sessions, connect the phone to a 5V/2A standard charger (avoid fast-charging while mining to prevent battery thermal stress).
