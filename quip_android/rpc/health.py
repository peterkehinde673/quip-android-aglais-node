"""
Substrate RPC health check system for Quip Network / Aglais testnet.
Validates DNS resolution, TCP connection, WebSocket handshake, and Substrate JSON-RPC methods.
"""

import re
import socket
import time
import urllib.parse
from dataclasses import dataclass
from typing import Optional

from quip_android.rpc.substrate_rpc import SubstrateRpcClient
from quip_android.utils.logging import get_logger

logger = get_logger("rpc.health")


@dataclass
class RpcHealthCheckResult:
    endpoint: str
    is_healthy: bool = False
    dns_resolved: bool = False
    ip_address: Optional[str] = None
    tcp_connected: bool = False
    ws_connected: bool = False
    rpc_responded: bool = False
    chain_name: Optional[str] = None
    chain_matched: bool = False
    node_name: Optional[str] = None
    node_version: Optional[str] = None
    peers: Optional[int] = None
    is_syncing: Optional[bool] = None
    latency_ms: float = 0.0
    error_message: Optional[str] = None

    def summary(self) -> str:
        if self.is_healthy:
            chain_info = f"chain={self.chain_name}" if self.chain_name else ""
            peers_info = f"peers={self.peers}" if self.peers is not None else ""
            ver_info = f"ver={self.node_version}" if self.node_version else ""
            details = ", ".join(filter(None, [chain_info, peers_info, ver_info]))
            return f"✓ Healthy ({self.latency_ms:.1f}ms) [{details}]"
        return f"✗ Unhealthy ({self.error_message or 'Failed health checks'})"


def check_endpoint_health(
    endpoint: str,
    timeout: float = 6.0,
    expected_chain: str = "quip-testnet",
    require_chain_match: bool = True,
) -> RpcHealthCheckResult:
    """
    Perform rigorous multi-stage verification on a candidate RPC endpoint:
    1. Validate scheme & check against P2P port 30333 trap
    2. DNS resolution
    3. TCP connection test
    4. WebSocket handshake & Substrate RPC queries:
       - system_chain
       - system_health
       - system_name
       - system_version
    5. Chain identity verification
    """
    result = RpcHealthCheckResult(endpoint=endpoint)
    start_time = time.perf_counter()

    # Stage 0: Guard against P2P bootnode confusion
    lower_ep = endpoint.strip().lower()
    if ":30333" in lower_ep or lower_ep.startswith("tcp://"):
        result.error_message = (
            "Port 30333/TCP is a Substrate P2P bootnode address, NOT an RPC endpoint! "
            "Do not pass P2P bootnodes to --validator. Quip miner requires ws:// or wss:// RPC."
        )
        return result

    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme.lower() not in ("ws", "wss"):
        result.error_message = f"Invalid scheme '{parsed.scheme}'. Quip RPC requires ws:// or wss://"
        return result

    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "wss" else 80)

    if not host:
        result.error_message = "Missing hostname in RPC endpoint URL"
        return result

    # Stage 1: DNS Resolution
    try:
        ip = socket.gethostbyname(host)
        result.dns_resolved = True
        result.ip_address = ip
    except socket.gaierror as err:
        result.error_message = f"DNS resolution failed for '{host}': {err}"
        return result

    # Stage 2: TCP Connection Test
    try:
        test_sock = socket.create_connection((host, port), timeout=timeout)
        test_sock.close()
        result.tcp_connected = True
    except (socket.timeout, OSError) as err:
        result.error_message = f"TCP connection failed to {host}:{port}: {err}"
        return result

    # Stage 3: Substrate JSON-RPC Queries over WebSocket
    try:
        client = SubstrateRpcClient(endpoint, timeout=timeout)

        # 3a: system_chain
        chain = client.get_system_chain()
        result.ws_connected = True
        result.rpc_responded = True
        result.chain_name = chain

        if expected_chain:
            # Normalize strings by removing hyphens, spaces, and converting to lowercase
            norm_expected = re.sub(r"[^a-z0-9]", "", expected_chain.lower())
            norm_actual = re.sub(r"[^a-z0-9]", "", chain.lower())
            
            # Check if expected chain matches, or both mention quip & testnet, or agls / aglais
            is_match = (
                norm_expected in norm_actual
                or norm_actual in norm_expected
                or ("quip" in norm_actual and "testnet" in norm_actual)
                or ("agls" in norm_actual or "aglais" in norm_actual)
            )

            if is_match:
                result.chain_matched = True
            else:
                result.chain_matched = False
                if require_chain_match:
                    result.error_message = (
                        f"Chain mismatch: expected '{expected_chain}', endpoint returned '{chain}'"
                    )
                    return result
        else:
            result.chain_matched = True

        # 3b: system_health
        try:
            health = client.get_system_health()
            result.peers = health.get("peers")
            result.is_syncing = health.get("isSyncing")
        except Exception:
            pass

        # 3c: system_name & system_version
        try:
            result.node_name = client.get_system_name()
        except Exception:
            pass
        try:
            result.node_version = client.get_system_version()
        except Exception:
            pass

        # All checks passed
        elapsed = (time.perf_counter() - start_time) * 1000.0
        result.latency_ms = elapsed
        result.is_healthy = True
        return result

    except Exception as err:
        result.error_message = f"WebSocket Substrate RPC check failed: {err}"
        return result
