"""
GPU mining support and architecture for quip-android-aglais-node.
Handles portable NVIDIA CUDA execution on compatible Linux PCs/servers,
and cleanly refuses GPU mode on Android/ARM64 without crashing.
"""

from typing import List, Optional, Tuple

from quip_android.config.models import AppConfig
from quip_android.monitoring.hardware import detect_gpu
from quip_android.utils.logging import get_logger
from quip_android.utils.system import find_quip_miner_binary, resolve_path

logger = get_logger("miner.gpu")


class GpuMinerCommandBuilder:
    """
    Builds commands for `quip-miner gpu` if and only if compatible CUDA hardware exists.
    """

    def __init__(self, config: AppConfig):
        self.config = config

    def check_gpu_readiness(self) -> Tuple[bool, str]:
        """
        Check if the current host/container has compatible GPU architecture.
        """
        gpu_info = detect_gpu()
        if not gpu_info.cuda_available:
            return (False, gpu_info.status_message)
        return (True, gpu_info.status_message)

    def build_command(
        self,
        active_rpc: str,
        custom_signer_key: Optional[str] = None,
    ) -> Tuple[Optional[List[str]], List[str]]:
        """
        Construct the verified argument list for launching `quip-miner gpu`.
        Refuses execution if CUDA is unavailable.
        """
        ready, message = self.check_gpu_readiness()
        if not ready:
            return (None, [message])

        binary_path, _ = find_quip_miner_binary(self.config.miner.quip_miner_path)
        if not binary_path:
            return (None, ["quip-miner binary not found"])

        key_path = resolve_path(custom_signer_key or self.config.signer.key_path)
        cmd = [
            binary_path,
            "gpu",
            "--validator", active_rpc,
            "--signer-key", key_path,
        ]

        if self.config.miner.extra_args:
            cmd.extend(self.config.miner.extra_args)

        return (cmd, [])
