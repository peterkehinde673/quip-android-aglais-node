"""
Hardware and GPU detection architecture for quip-android-aglais-node.
Specialized for Android ARM64 (e.g., Infinix Note G96) with portable Linux PC/server support.
"""

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from quip_android.utils.logging import get_logger
from quip_android.utils.system import detect_android_proot

logger = get_logger("monitoring.hardware")


@dataclass
class CpuInfo:
    architecture: str = "unknown"
    core_count: int = 1
    model_name: str = "Unknown CPU"
    is_arm: bool = False
    is_supported: bool = True
    features: List[str] = field(default_factory=list)


@dataclass
class GpuInfo:
    cuda_available: bool = False
    device_count: int = 0
    devices: List[str] = field(default_factory=list)
    cuda_version: Optional[str] = None
    driver_version: Optional[str] = None
    status_message: str = "GPU mining unavailable on this device/environment."


@dataclass
class HardwareProfile:
    device_label: str
    is_android: bool
    is_proot: bool
    environment_desc: str
    cpu: CpuInfo
    gpu: GpuInfo
    total_memory_mb: float = 0.0


def detect_cpu() -> CpuInfo:
    """Detect CPU architecture, core count, and processor model."""
    info = CpuInfo()
    arch = platform.machine().lower()
    info.architecture = arch
    info.core_count = os.cpu_count() or 1
    info.is_arm = ("arm" in arch or "aarch64" in arch)

    # Read /proc/cpuinfo if accessible
    if os.path.exists("/proc/cpuinfo"):
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            for line in lines:
                if ":" in line:
                    k, v = [x.strip() for x in line.split(":", 1)]
                    k_lower = k.lower()
                    if k_lower in ("model name", "hardware", "processor"):
                        if info.model_name == "Unknown CPU" and v:
                            info.model_name = v
                    elif k_lower in ("features", "flags"):
                        info.features = v.split()
        except OSError:
            pass

    if info.is_arm and info.model_name == "Unknown CPU":
        info.model_name = f"ARM64 Mobile Processor ({info.core_count} cores)"

    # All modern 64-bit CPUs (ARM64 and x86_64) are supported for CPU mining
    info.is_supported = (info.architecture in ("aarch64", "arm64", "x86_64", "amd64"))
    return info


def detect_gpu() -> GpuInfo:
    """
    Detect GPU and NVIDIA CUDA availability.
    Gracefully identifies unsupported environments (such as Android ARM64)
    without crashing or attempting to install CUDA.
    """
    gpu = GpuInfo()
    is_android, _, _ = detect_android_proot()

    # Android mobile hardware (e.g. Helio G96 with Mali-G57 GPU) lacks NVIDIA CUDA
    if is_android or platform.machine().lower() in ("aarch64", "arm64", "armv7l"):
        gpu.cuda_available = False
        gpu.status_message = "GPU mining unavailable on this device/environment (ARM64 Android lacks NVIDIA CUDA)."
        return gpu

    # Check for nvidia-smi on desktop/server Linux
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            res = subprocess.run(
                [nvidia_smi, "--query-gpu=name,driver_version", "--format=csv,noheader"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip():
                lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
                gpu.cuda_available = True
                gpu.device_count = len(lines)
                for line in lines:
                    parts = [p.strip() for p in line.split(",")]
                    gpu.devices.append(parts[0])
                    if len(parts) > 1:
                        gpu.driver_version = parts[1]
                gpu.status_message = f"CUDA GPU available ({len(lines)} detected: {', '.join(gpu.devices)})"
                return gpu
        except Exception:
            pass

    # Check /proc/driver/nvidia
    if os.path.exists("/proc/driver/nvidia/version"):
        try:
            with open("/proc/driver/nvidia/version", "r", encoding="utf-8", errors="ignore") as f:
                ver_line = f.readline().strip()
                gpu.driver_version = ver_line
        except OSError:
            pass

    gpu.cuda_available = False
    gpu.status_message = "GPU mining unavailable on this device/environment."
    return gpu


def get_hardware_profile(device_label: str = "Infinix-Note-G96") -> HardwareProfile:
    """Build a complete hardware profile for the current host/container."""
    is_android, is_proot, env_desc = detect_android_proot()
    cpu = detect_cpu()
    gpu = detect_gpu()

    total_mem_mb = 0.0
    if os.path.exists("/proc/meminfo"):
        try:
            with open("/proc/meminfo", "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        # MemTotal:       16384000 kB
                        parts = line.split()
                        if len(parts) >= 2:
                            total_mem_mb = float(parts[1]) / 1024.0
                        break
        except OSError:
            pass

    return HardwareProfile(
        device_label=device_label,
        is_android=is_android,
        is_proot=is_proot,
        environment_desc=env_desc,
        cpu=cpu,
        gpu=gpu,
        total_memory_mb=total_mem_mb,
    )
