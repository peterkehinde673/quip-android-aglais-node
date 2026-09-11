"""
CPU mining command builder and launcher for quip-miner v0.2.
Ensures valid Substrate RPC endpoint, verified signer key, and configured worker limits.
"""

import os
from typing import List, Optional, Tuple

from quip_android.config.models import AppConfig
from quip_android.utils.logging import get_logger
from quip_android.utils.system import find_quip_miner_binary, resolve_path

logger = get_logger("miner.cpu")


class CpuMinerCommandBuilder:
    """
    Builds and validates official CLI commands for `quip-miner cpu`.
    """

    def __init__(self, config: AppConfig):
        self.config = config

    def validate_prerequisites(
        self,
        active_rpc: str,
        custom_signer_key: Optional[str] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Validate all requirements before building execution command:
        1. quip-miner binary exists and is executable
        2. Signer key exists and is readable
        3. Active RPC is a valid WebSocket URL (never a raw P2P port 30333)
        4. CPU worker count is within safety limits
        """
        errors = []

        # 1. Check binary
        binary_path, version_info = find_quip_miner_binary(self.config.miner.quip_miner_path)
        if not binary_path:
            errors.append(
                "quip-miner binary not found. Checked standard paths and PATH. "
                "Specify [miner.quip_miner_path] in config.toml or install quip-protocol."
            )

        # 2. Check signer key
        key_path_str = custom_signer_key or self.config.signer.key_path
        resolved_key = resolve_path(key_path_str)
        if not os.path.isfile(resolved_key):
            if self.config.signer.require_existing:
                errors.append(
                    f"Quip signer key file does not exist at '{resolved_key}'. "
                    f"Use 'quip-android keygen' to generate one explicitly, or specify --signer-key <path>."
                )
        elif not os.access(resolved_key, os.R_OK):
            errors.append(f"Quip signer key file exists at '{resolved_key}' but is not readable.")

        # 3. Check RPC endpoint
        if not active_rpc:
            errors.append("No active RPC endpoint provided. Run 'quip-android rpc-check' first.")
        else:
            lower_rpc = active_rpc.strip().lower()
            if ":30333" in lower_rpc or lower_rpc.startswith("tcp://"):
                errors.append(
                    f"CRITICAL: Address '{active_rpc}' is a P2P bootnode (port 30333), NOT a Substrate RPC! "
                    f"Do not pass P2P bootnodes to --validator."
                )
            elif not (lower_rpc.startswith("ws://") or lower_rpc.startswith("wss://")):
                errors.append(f"RPC endpoint '{active_rpc}' must be a WebSocket URL (ws:// or wss://)")

        # 4. Check worker count vs mode
        workers = self.config.miner.workers
        if self.config.node.mode == "eco" and workers > 1:
            logger.info("Eco mode active: Clamping workers from %d to 1 for low power.", workers)
            workers = 1

        if workers > self.config.safety.max_cpu_workers:
            errors.append(
                f"Configured workers ({workers}) exceeds safety threshold ({self.config.safety.max_cpu_workers})"
            )

        return (len(errors) == 0, errors)

    def build_command(
        self,
        active_rpc: str,
        custom_signer_key: Optional[str] = None,
        custom_workers: Optional[int] = None,
    ) -> Tuple[Optional[List[str]], List[str]]:
        """
        Construct the verified argument list for launching `quip-miner cpu`.
        """
        valid, errors = self.validate_prerequisites(active_rpc, custom_signer_key)
        if not valid:
            return (None, errors)

        binary_path, _ = find_quip_miner_binary(self.config.miner.quip_miner_path)
        key_path = resolve_path(custom_signer_key or self.config.signer.key_path)

        workers = custom_workers if custom_workers is not None else self.config.miner.workers
        if self.config.node.mode == "eco":
            workers = 1
        elif self.config.node.mode == "daily" and workers > 2:
            workers = 2

        cmd = [
            binary_path,
            "cpu",
            "--validator", active_rpc,
            "--signer-key", key_path,
            "--workers", str(workers),
        ]

        if self.config.miner.extra_args:
            cmd.extend(self.config.miner.extra_args)

        return (cmd, [])
