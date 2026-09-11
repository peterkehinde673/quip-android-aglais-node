"""
System utilities for Android, Termux, PRoot, and Linux environments.
"""

import os
import shutil
import sys
import subprocess
from datetime import datetime
from typing import Optional, List, Tuple


def resolve_path(path_str: str) -> str:
    """Expand user tildes and resolve absolute paths."""
    if not path_str:
        return ""
    expanded = os.path.expanduser(path_str)
    return os.path.abspath(expanded)


def backup_file_before_overwrite(file_path: str) -> Optional[str]:
    """
    Safely backup an existing file before overwriting.
    Returns path to backup file, or None if source doesn't exist.
    """
    resolved = resolve_path(file_path)
    if not os.path.exists(resolved):
        return None
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{resolved}.bak_{timestamp}"
    try:
        shutil.copy2(resolved, backup_path)
        return backup_path
    except OSError as err:
        sys.stderr.write(f"Warning: Failed to create backup of {file_path}: {err}\n")
        return None


def detect_android_proot() -> Tuple[bool, bool, str]:
    """
    Detect if running inside an Android environment and/or PRoot container.
    Returns: (is_android, is_proot, environment_description)
    """
    is_android = False
    is_proot = False
    details = []

    # Check for Termux indicators
    if "TERMUX_VERSION" in os.environ or os.path.exists("/data/data/com.termux"):
        is_android = True
        details.append("Termux")

    # Check for Android system files or properties
    if os.path.exists("/system/build.prop") or os.path.exists("/system/bin/getprop"):
        is_android = True
        details.append("Android Host")

    # Check for PRoot indicators
    # PRoot intercepts ptrace / syscalls, often visible in /proc/version, env vars, or PRoot mount paths
    if "PROOT_TMP_DIR" in os.environ or os.environ.get("PRoot") == "1":
        is_proot = True
        details.append("PRoot Container")

    try:
        with open("/proc/version", "r", encoding="utf-8", errors="ignore") as f:
            v_content = f.read().lower()
            if "android" in v_content:
                is_android = True
                details.append("Android Kernel")
    except OSError:
        pass

    description = " + ".join(details) if details else "Standard Linux"
    return (is_android, is_proot, description)


def find_quip_miner_binary(configured_path: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Find official quip-miner binary.
    Checks:
    1. Configured path if not 'auto'
    2. Virtualenv path from previous environment: /root/quip-android-node/.quip/bin/quip-miner
    3. Common virtualenv locations (.venv/bin/quip-miner, .quip/bin/quip-miner)
    4. PATH environment variable
    Returns: (binary_path, version_or_error)
    """
    candidates = []

    if configured_path and configured_path.strip().lower() != "auto":
        candidates.append(resolve_path(configured_path))

    # Known standard paths from Quip v0.2 installation in previous environment
    candidates.extend([
        "/root/quip-android-node/.quip/bin/quip-miner",
        os.path.expanduser("~/.quip/bin/quip-miner"),
        os.path.expanduser("~/.cargo/bin/quip-miner"),
        os.path.abspath("./.quip/bin/quip-miner"),
        os.path.abspath("./.venv/bin/quip-miner"),
    ])

    # Also check system PATH
    which_path = shutil.which("quip-miner")
    if which_path:
        candidates.append(which_path)

    for path in candidates:
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            # Check version
            try:
                result = subprocess.run(
                    [path, "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=5,
                )
                version_str = (result.stdout or result.stderr or "").strip()
                return (path, version_str or "quip-miner (version output empty)")
            except Exception as err:
                return (path, f"quip-miner executable found (version probe error: {err})")

    return (None, "quip-miner not found in configured paths or PATH")


def apply_process_nice(pid: int, nice_value: int) -> bool:
    """
    Attempt to set process priority nice level (19 is lowest priority for low power).
    Gracefully handles environments where renice/os.setpriority is restricted.
    """
    try:
        os.setpriority(os.PRIO_PROCESS, pid, nice_value)
        return True
    except (PermissionError, OSError, AttributeError):
        # Fallback to renice CLI if available
        try:
            res = subprocess.run(
                ["renice", "-n", str(nice_value), "-p", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return res.returncode == 0
        except Exception:
            return False
