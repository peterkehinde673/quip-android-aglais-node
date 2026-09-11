"""
Substrate JSON-RPC client for Quip Network / Aglais testnet.
Includes standard-library WebSocket implementation with SSL support
and fallback to websockets library if available.
"""

import base64
import json
import os
import re
import socket
import ssl
import struct
import time
import urllib.parse
from typing import Any, Dict, Optional, Tuple

from quip_android.utils.logging import get_logger

logger = get_logger("rpc.substrate")


class SubstrateRpcError(Exception):
    """Exception raised when a Substrate RPC call fails."""
    pass


class LightweightWebSocketClient:
    """
    Minimal RFC 6455 compliant WebSocket client built on Python standard library.
    Zero external dependencies, ideal for Android Termux / PRoot environments.
    """

    def __init__(self, url: str, timeout: float = 6.0):
        self.url = url
        self.timeout = timeout
        parsed = urllib.parse.urlparse(url)
        self.scheme = parsed.scheme.lower()
        if self.scheme not in ("ws", "wss"):
            raise ValueError(f"Unsupported WebSocket scheme: {self.scheme}")

        self.host = parsed.hostname or ""
        self.port = parsed.port or (443 if self.scheme == "wss" else 80)
        self.path = parsed.path or "/"
        if parsed.query:
            self.path += f"?{parsed.query}"

        self.sock: Optional[socket.socket] = None
        self._connected = False

    def connect(self) -> None:
        """Establish TCP + TLS connection and perform WebSocket handshake."""
        raw_sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        raw_sock.settimeout(self.timeout)

        if self.scheme == "wss":
            # Never silently disable certificate verification. A failed TLS
            # handshake is a health-check failure, not a reason to trust an
            # unauthenticated endpoint.
            ssl_context = ssl.create_default_context()
            self.sock = ssl_context.wrap_socket(raw_sock, server_hostname=self.host)
        else:
            self.sock = raw_sock

        # Generate 16-byte random Sec-WebSocket-Key
        sec_key = base64.b64encode(os.urandom(16)).decode("ascii")

        handshake_req = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {sec_key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"User-Agent: quip-android-aglais-node/0.2.1\r\n"
            f"\r\n"
        )
        self.sock.sendall(handshake_req.encode("utf-8"))

        # Read HTTP response headers
        response_bytes = b""
        while b"\r\n\r\n" not in response_bytes:
            chunk = self.sock.recv(1024)
            if not chunk:
                raise ConnectionError("Server closed connection during WebSocket handshake")
            response_bytes += chunk
            if len(response_bytes) > 8192:
                raise ConnectionError("WebSocket handshake response too large")

        header_part = response_bytes.split(b"\r\n\r\n")[0].decode("latin1", errors="ignore")
        first_line = header_part.splitlines()[0] if header_part else ""
        if "101" not in first_line:
            raise ConnectionError(f"WebSocket upgrade rejected by server: {first_line}")

        self._connected = True

    def send_text(self, text: str) -> None:
        """Send a masked text frame (RFC 6455)."""
        if not self.sock or not self._connected:
            raise ConnectionError("WebSocket is not connected")

        payload = text.encode("utf-8")
        length = len(payload)

        # Header byte 1: FIN (0x80) | opcode text (0x01)
        header = bytearray([0x81])

        # Header byte 2: MASK (0x80) | length
        mask_key = os.urandom(4)
        if length <= 125:
            header.append(0x80 | length)
        elif length <= 65535:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))

        header.extend(mask_key)

        # Mask payload
        masked_payload = bytearray(length)
        for i in range(length):
            masked_payload[i] = payload[i] ^ mask_key[i % 4]

        self.sock.sendall(header + masked_payload)

    def recv_text(self) -> str:
        """Receive a text frame, unmasking if necessary."""
        if not self.sock or not self._connected:
            raise ConnectionError("WebSocket is not connected")

        def recv_exact(n: int) -> bytes:
            buf = bytearray()
            while len(buf) < n:
                chunk = self.sock.recv(n - len(buf))
                if not chunk:
                    raise ConnectionError("Connection closed while receiving WebSocket frame")
                buf.extend(chunk)
            return bytes(buf)

        head = recv_exact(2)
        b1, b2 = head[0], head[1]

        opcode = b1 & 0x0F
        # 0x8 is close, 0x9 is ping, 0xA is pong, 0x1 is text
        if opcode == 0x8:
            self._connected = False
            raise ConnectionError("Received WebSocket Close frame from server")

        is_masked = bool(b2 & 0x80)
        payload_len = b2 & 0x7F

        if payload_len == 126:
            payload_len = struct.unpack("!H", recv_exact(2))[0]
        elif payload_len == 127:
            payload_len = struct.unpack("!Q", recv_exact(8))[0]

        mask = recv_exact(4) if is_masked else None
        data = recv_exact(payload_len)

        if is_masked and mask:
            unmasked = bytearray(payload_len)
            for i in range(payload_len):
                unmasked[i] = data[i] ^ mask[i % 4]
            data = bytes(unmasked)

        if opcode == 0x9:  # Ping -> reply Pong
            pong_frame = bytearray([0x8A, 0x80]) + os.urandom(4)
            self.sock.sendall(pong_frame)
            return self.recv_text()

        return data.decode("utf-8", errors="replace")

    def close(self) -> None:
        """Close the WebSocket connection."""
        self._connected = False
        if self.sock:
            try:
                # Send close frame
                self.sock.sendall(bytearray([0x88, 0x80]) + os.urandom(4))
                self.sock.close()
            except Exception:
                pass
            self.sock = None


class SubstrateRpcClient:
    """
    Substrate RPC Client capable of querying Substrate nodes via WebSocket or HTTP.
    """

    def __init__(self, endpoint: str, timeout: float = 6.0):
        self.endpoint = endpoint.strip()
        self.timeout = timeout
        self._req_id = 0

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def call(self, method: str, params: Optional[list] = None) -> Any:
        """
        Execute JSON-RPC call against Substrate endpoint.
        Returns the result field of the response or raises SubstrateRpcError.
        """
        req_id = self._next_id()
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or [],
        }
        json_str = json.dumps(payload)

        # Connect via WebSocket
        ws = LightweightWebSocketClient(self.endpoint, timeout=self.timeout)
        try:
            ws.connect()
            ws.send_text(json_str)
            raw_resp = ws.recv_text()
            data = json.loads(raw_resp)
            if "error" in data:
                err_msg = data["error"].get("message", str(data["error"]))
                raise SubstrateRpcError(f"RPC method '{method}' error: {err_msg}")
            return data.get("result")
        finally:
            ws.close()

    def get_system_health(self) -> Dict[str, Any]:
        """Call system_health. Returns {isSyncing: bool, peers: int, shouldHavePeers: bool}."""
        res = self.call("system_health")
        return res if isinstance(res, dict) else {}

    def get_system_chain(self) -> str:
        """Call system_chain. Returns chain name e.g. 'quip-testnet'."""
        res = self.call("system_chain")
        return str(res or "")

    def get_system_name(self) -> str:
        """Call system_name. Returns node client name e.g. 'quip-node'."""
        res = self.call("system_name")
        return str(res or "")

    def get_system_version(self) -> str:
        """Call system_version. Returns node version e.g. '0.2.1'."""
        res = self.call("system_version")
        return str(res or "")
