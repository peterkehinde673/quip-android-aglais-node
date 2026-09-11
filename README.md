# quip-android-aglais-node

An **unofficial, low-power controller and monitoring tool** for operating a Quip miner against the **Aglais testnet**.

> **Important:** This repository is not a Quip validator and does not itself implement the Quip mining protocol. It detects and launches a compatible official `quip-miner` runtime, monitors the local process, checks configured Substrate RPC endpoints, and keeps a local evidence journal.

## Current status

The controller source code is present, but **real mining depends on a compatible official Quip miner/runtime**. A Google AI web preview or GitHub repository alone cannot mine; a real execution environment is still required.

The current official Aglais deployment uses a Substrate validator + config-driven miner architecture. Verify the installed `quip-miner` version and CLI/config schema before starting. The controller must never claim points merely because a process is running. citeturn1search0turn1search1

## Key features

- Android/Termux/Ubuntu PRoot-aware environment detection
- CPU-first low-power operating modes
- Optional CUDA capability detection for compatible Linux hardware
- Substrate RPC DNS/TCP/WebSocket health checks and endpoint selection
- Safe signer-key handling
- Process priority and runtime safety controls
- Local participation evidence journal
- **Unofficial** points estimation based only on recorded evidence
- Local mobile dashboard at `127.0.0.1:8080`

## Quick start

Clone **your repository**:

```bash
git clone https://github.com/peterkehinde673/quip-android-aglais-node.git
cd quip-android-aglais-node
./scripts/install.sh
./scripts/run.sh doctor
```

The doctor command must find a compatible `quip-miner` before mining can start.

## Important limitations

- Running the dashboard alone does not run a node or miner.
- A short mining session does not guarantee daily participation points.
- A local dashboard is not automatically a verified public-infrastructure bonus.
- Local log matching is not equivalent to an official account-points balance.
- The controller should be updated whenever Quip changes the miner CLI or config schema.

## Aglais network

Aglais is the current Quip public testnet. The official operator repository documents the current network identity, public RPC endpoints, faucet, and config-driven CPU/CUDA deployment architecture. citeturn1search0turn1search1

## License

Apache License 2.0. See [LICENSE](LICENSE).
