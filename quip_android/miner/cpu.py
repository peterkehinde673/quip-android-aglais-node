"""CPU config-driven launcher for the official quip-miner workflow."""
import os
from typing import List, Optional, Tuple
from quip_android.config.models import AppConfig
from quip_android.miner.runtime_config import build_runtime_config, validate_runtime_config
from quip_android.utils.system import find_quip_miner_binary, resolve_path

class CpuMinerCommandBuilder:
    def __init__(self, config: AppConfig):
        self.config = config

    def validate_prerequisites(self, active_rpc: str, custom_signer_key: Optional[str] = None) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        binary_path, _ = find_quip_miner_binary(self.config.miner.quip_miner_path)
        if not binary_path:
            errors.append("quip-miner binary not found. Install or configure a compatible official runtime first.")
        key_path = resolve_path(custom_signer_key or self.config.signer.key_path)
        if self.config.signer.require_existing:
            if not os.path.isfile(key_path):
                errors.append(f"Signer key does not exist at '{key_path}'. Run quip-android keygen explicitly or configure an existing key.")
            elif not os.access(key_path, os.R_OK):
                errors.append(f"Signer key exists but is not readable: '{key_path}'")
        if not active_rpc:
            errors.append("No healthy Substrate RPC endpoint available.")
        elif ":30333" in active_rpc.lower() or active_rpc.lower().startswith("tcp://"):
            errors.append("P2P port 30333 is not a miner RPC endpoint.")
        return (not errors, errors)

    def build_command(self, active_rpc: str, custom_signer_key: Optional[str] = None, custom_workers: Optional[int] = None) -> Tuple[Optional[List[str]], List[str]]:
        valid, errors = self.validate_prerequisites(active_rpc, custom_signer_key)
        if not valid:
            return None, errors
        binary_path, _ = find_quip_miner_binary(self.config.miner.quip_miner_path)
        workers = custom_workers if custom_workers is not None else self.config.miner.workers
        workers = max(1, workers)
        if self.config.node.mode == "eco":
            workers = 1
        elif self.config.node.mode == "daily":
            workers = min(workers, 2)
        validators = [active_rpc] + [ep for ep in self.config.rpc.endpoints if ep != active_rpc and ep.lower().startswith(("ws://", "wss://")) and ":30333" not in ep]\n        config_path = build_runtime_config(self.config, validators, workers, "cpu", custom_signer_key)
        accepted, output = validate_runtime_config(binary_path, config_path)
        if not accepted:
            return None, ["Installed quip-miner rejected the generated config-driven runtime file.", f"Validation output: {output}", "Update the official miner or adjust the generated config to the installed schema before mining."]
        command = [binary_path, "--config", config_path, "--mode", "cpu"]
        command.extend(self.config.miner.extra_args)
        return command, []
