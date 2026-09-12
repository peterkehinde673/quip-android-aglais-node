"""GPU config-driven launcher for compatible NVIDIA CUDA environments."""
from typing import List, Optional, Tuple
from quip_android.config.models import AppConfig
from quip_android.miner.runtime_config import build_runtime_config, validate_runtime_config
from quip_android.monitoring.hardware import detect_gpu
from quip_android.utils.system import find_quip_miner_binary

class GpuMinerCommandBuilder:
    def __init__(self, config: AppConfig):
        self.config = config

    def check_gpu_readiness(self) -> Tuple[bool, str]:
        info = detect_gpu()
        if not info.cuda_available:
            return False, info.status_message
        return True, info.status_message

    def build_command(self, active_rpc: str, custom_signer_key: Optional[str] = None) -> Tuple[Optional[List[str]], List[str]]:
        ready, message = self.check_gpu_readiness()
        if not ready:
            return None, [message]
        binary_path, _ = find_quip_miner_binary(self.config.miner.quip_miner_path)
        if not binary_path:
            return None, ["quip-miner binary not found"]
        config_path = build_runtime_config(self.config, [active_rpc], 1, "gpu", custom_signer_key)
        accepted, output = validate_runtime_config(binary_path, config_path)
        if not accepted:
            return None, [f"quip-miner rejected generated GPU config: {output}"]
        command = [binary_path, "--config", config_path, "--mode", "gpu"]
        command.extend(self.config.miner.extra_args)
        return command, []
