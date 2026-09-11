# Troubleshooting & Common Issues

Solutions for common operational scenarios on Android, Termux, and PRoot.

---

## 1. `quip-miner binary not found`

- **Cause**: `quip-miner` has not been compiled or is placed in a custom directory not in `$PATH`.
- **Solution**:
  1. Verify the location of your `quip-miner` binary.
  2. In `config.toml`, update:
     ```toml
     [miner]
     quip_miner_path = "/full/path/to/quip-miner"
     ```
  3. Ensure execution permissions:
     ```bash
     chmod +x /full/path/to/quip-miner
     ```

---

## 2. Termux Process Killed in Background (Signal 9)

- **Cause**: Android OEM battery optimizer (Phantom Process Killer / Doze Mode) killed Termux.
- **Solution**:
  1. Swipe down the Android notification shade, find the Termux notification, and tap **"Acquire Wakelock"**.
  2. In Android Settings -> Apps -> Termux:
     - Set **Battery** to **"Unrestricted"**.
     - Enable **Autostart** / **Run in background**.
  3. Run the miner in **Eco Mode** (`--mode eco`) to keep thermal emission and memory below trigger thresholds.

---

## 3. `GPU mining unavailable on this device/environment`

- **Notice**: This is expected behavior on Android mobile hardware (e.g. Infinix Note G96).
- **Explanation**: MediaTek Helio G96 uses an ARM Mali-G57 GPU, which does not support NVIDIA CUDA. `quip-android` gracefully identifies this and operates in CPU mode.
- Do NOT attempt to install NVIDIA CUDA packages inside Ubuntu PRoot on an ARM64 phone.

---

## 4. `No healthy Substrate RPC endpoints available`

- **Cause**: Mobile network or Wi-Fi is blocking outbound WebSocket ports (20049) or DNS resolution failed.
- **Solution**:
  1. Run `quip-android rpc-check` to isolate the failure stage.
  2. Toggle Airplane Mode or switch from Mobile Data to Wi-Fi.
  3. Ensure DNS servers (e.g. `8.8.8.8` or `1.1.1.1`) are configured in `/etc/resolv.conf` inside Ubuntu PRoot.

---

## 5. `quip-miner keygen: file already exists`

- **Notice**: `quip-android` strictly prevents accidental overwriting of existing signing keys.
- **Solution**: If you genuinely intend to generate a new key, back up the existing key first:
  ```bash
  mv ~/.quip-miner/signing.json ~/.quip-miner/signing.json.bak
  quip-android keygen
  ```
