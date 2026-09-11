# RPC Architecture & Automatic Failover

`quip-android-aglais-node` connects to the Quip Network Aglais Testnet via Substrate JSON-RPC over WebSocket (`wss://`).

---

## 1. Candidate Endpoints

The default configuration includes candidate endpoints distributed across the Aglais testnet cluster:
- `wss://bootnode-1.aglais.quip.network:20049/rpc`
- `wss://bootnode-2.aglais.quip.network:20049/rpc`
- `wss://bootnode-3.aglais.quip.network:20049/rpc`

---

## 2. Health Verification Pipeline

Every candidate endpoint undergoes a 4-step health audit:

1. **DNS Resolution**: Validates that domain resolves to an IP address.
2. **TCP Socket Handshake**: Verifies network route and opens connection within `timeout_seconds`.
3. **RFC 6455 WebSocket Handshake**: Negotiates upgrade header with 16-byte cryptographic `Sec-WebSocket-Key` challenge.
4. **Substrate Chain Verification**:
   - Executes JSON-RPC `system_chain` to verify the node is running the Aglais chain (`AGLS (Quip Testnet)`).
   - Executes `system_health` to verify peer count (`peers > 0`) and synchronization status (`isSyncing == false`).
   - Executes `system_version` to confirm protocol compatibility.

---

## 3. Dynamic Failover Behavior

- The `RpcManager` tests all candidate endpoints and ranks them by lowest round-trip latency.
- If the active endpoint stops responding or drops connection, the manager automatically selects the next healthy endpoint and reconnects.
- Manual verification can be triggered anytime via:
  ```bash
  quip-android rpc-check
  ```
