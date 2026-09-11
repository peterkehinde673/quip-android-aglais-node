# quip-android-aglais-node

An open-source, low-power, mobile-optimized node and miner controller for the **Quip Network Aglais Testnet** (v0.2.1+).

Engineered specifically for **Android ARM64** devices (primary target: **Infinix Note G96** running **Termux → Ubuntu PRoot**) while retaining complete portability across standard Linux PCs and servers.

---

## Key Highlights

- **Ultra-Low Resource Footprint**: Zero heavy external dependencies. Includes a custom RFC 6455 Substrate JSON-RPC WebSocket engine and minimal TOML parser to operate effortlessly within constrained PRoot environments.
- **True Substrate JSON-RPC Architecture**: Accurately targets Substrate WebSocket RPC endpoints (`wss://` / `ws://`), strictly rejecting raw P2P bootnodes (port `30333`).
- **Real Participation Verification**: Rejects fake counters or vanity claims. Cryptographically verifies real mining progress through log evidence, qblock solutions, and challenge confirmations recorded in `data/participation.jsonl`.
- **Automatic Multi-RPC Failover**: Continuously monitors latency, peer count, block height, and chain identity across candidate Aglais bootnode RPCs, auto-switching when an endpoint degrades.
- **Hardware & Safety Guardian**: Enforces memory thresholds, max session runtimes, thermal limits, and low-priority process scheduling (`nice 19`).
- **Unofficial Local Points Estimator**: Strictly adheres to official Quip rules (1 point per distinct qblock, capped at 72 points/day; 20 points per win; infrastructure multipliers only when independently verified).
- **Mobile Web Dashboard**: Built-in, zero-dependency dark-mode web dashboard accessible directly from phone browsers at `http://127.0.0.1:8080`.

---

## Operating Modes

| Mode | Workers | Nice | Description |
|---|---|---|---|
| `eco` | 1 | 19 | Minimal thermal footprint, safe for long sessions on battery. |
| `daily` | 1–2 | 19 | Low-power daily participation session. Stops automatically upon reaching daily qblock target or session limit. |
| `performance` | Configurable | 10 | Max throughput. Recommended only when connected to a charger with active cooling. |

---

## Quick Start on Android (Termux + Ubuntu PRoot)

### 1. Install & Setup
```bash
# Clone the repository inside your Ubuntu PRoot environment
git clone https://github.com/quip-network/quip-android-aglais-node.git
cd quip-android-aglais-node

# Run automated installer
./scripts/install.sh
```

### 2. Verify System Health
```bash
./scripts/run.sh doctor
```

### 3. Check Substrate RPC Connectivity
```bash
./scripts/run.sh rpc-check
```

### 4. Configure Signing Key
If you already possess a Quip signer key:
```toml
# Edit config.toml
[signer]
key_path = "/path/to/your/signing.json"
require_existing = true
```
Or generate one explicitly:
```bash
./scripts/run.sh keygen --output ~/.quip-miner/signing.json
```

### 5. Start Mining
```bash
# Start in Eco Mode (1 CPU worker, lowest priority)
./scripts/run.sh start --mode eco

# Or launch local web dashboard
./scripts/run.sh dashboard
```

---

## CLI Reference

```bash
quip-android doctor              # System & network diagnostics
quip-android rpc-check           # Live latency & peer check across RPCs
quip-android status              # Formatted live status table
quip-android hardware            # CPU architecture & GPU CUDA report
quip-android start --mode <mode> # Launch miner (eco, daily, performance)
quip-android stop                # Cleanly shut down miner process
quip-android logs -n 50          # Tail recent session logs
quip-android participation       # Review verified on-chain qblock journal
quip-android dashboard           # Launch local web dashboard (localhost:8080)
quip-android config --show       # Output active configuration
```

---

## Documentation

- [Hardware & Android PRoot Deployment Guide](docs/ANDROID_TERMUX_GUIDE.md)
- [Architecture & Design](docs/ARCHITECTURE.md)
- [Points & Participation Evidence Engine](docs/POINTS_AND_PARTICIPATION.md)
- [RPC Failover & Substrate Health](docs/FAILOVER_AND_RPC.md)
- [Troubleshooting & FAQs](docs/TROUBLESHOOTING.md)

---

## License

MIT License. See [LICENSE](LICENSE) for details.
