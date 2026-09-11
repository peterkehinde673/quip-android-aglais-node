# Architecture & Design

`quip-android-aglais-node` is architected specifically around the resource and operational constraints of Android mobile hardware running within PRoot sandboxes.

---

## 1. System Topology

```
+-------------------------------------------------------------+
|                      User Interfaces                        |
|   CLI (quip-android)          Mobile Web Dashboard (:8080)   |
+------------------------------+------------------------------+
                               |
+------------------------------v------------------------------+
|                       Miner Controller                      |
|                  (Lifecycle, Modes, Signals)                |
+-------+--------------------+--------------------+-----------+
        |                    |                    |
+-------v-------+    +-------v-------+    +-------v-------+
|  RPC Manager  |    | Safety Guard  |    | Participation |
|  & WebSocket  |    | & Resources   |    |    Journal    |
+-------+-------+    +-------+-------+    +-------+-------+
        |                    |                    |
        |                    v                    v
        |            /proc, Sysfs, Mem      data/participation.jsonl
        |
        v
+-------------------------------------------------------------+
|               Substrate RPC WebSocket Cluster               |
|      wss://bootnode-1/2/3.aglais.quip.network:20049/rpc     |
+-------------------------------------------------------------+
```

---

## 2. Component Directory Structure

- `quip_android/config/`: TOML configuration models and zero-dependency parser supporting multiline arrays and comments.
- `quip_android/rpc/`:
  - `substrate_rpc.py`: Native RFC 6455 WebSocket client executing Substrate JSON-RPC methods (`system_chain`, `system_health`, `system_version`, `chain_getHeader`).
  - `health.py`: 4-stage health verification (DNS -> TCP -> WebSocket -> Substrate identity).
  - `manager.py`: Multi-endpoint latency tracking, dynamic failover, and candidate selection.
- `quip_android/monitoring/`:
  - `hardware.py`: CPU architecture inspection and CUDA GPU capability detection.
  - `resources.py`: Thermal, battery, RAM, CPU, and disk monitoring tailored for Android.
  - `safety.py`: Threshold enforcement (RAM limit, session runtime limit, worker limit).
- `quip_android/miner/`:
  - `process.py`: Subprocess management, output streaming, PID file handling, and safe signal propagation.
  - `cpu.py`: Official `quip-miner cpu` command builder. Rejects P2P port 30333.
  - `gpu.py`: CUDA GPU launcher. Cleanly refuses on Android/ARM64.
  - `controller.py`: Primary orchestrator.
- `quip_android/participation/`:
  - `base.py`: Evidence definitions and provider interface.
  - `miner_logs.py`: Real-time stdout parser matching verified qblock challenge and win events.
  - `records.py`: Append-only JSONL journal (`data/participation.jsonl`).
- `quip_android/points/`:
  - `estimator.py`: Local unofficial point calculation engine based on verified evidence.
- `quip_android/dashboard/`:
  - `app.py`: Built-in HTTP server providing REST API and mobile-optimized frontend.

---

## 3. Substrate vs P2P Boundary

Quip Network v0.2.1 employs a dual-port architecture on bootnodes:
- **Port 30333 (TCP)**: Substrate P2P Gossip and LibP2P bootnode transport.
- **Port 20049 (WSS)**: Substrate JSON-RPC WebSocket interface.

The controller explicitly prevents passing port 30333 to `--validator`, ensuring the miner connects directly to the authenticated JSON-RPC interface.
