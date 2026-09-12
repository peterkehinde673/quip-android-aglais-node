"""
Resource monitoring for Android, Termux, PRoot, and Linux environments.
Gracefully handles restricted sandbox access to thermal and battery sensors.
"""

import os
import shutil
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from quip_android.utils.logging import get_logger

logger = get_logger("monitoring.resources")


@dataclass
class ResourceSnapshot:
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_total_mb: float = 0.0
    memory_available_mb: float = 0.0
    disk_percent: float = 0.0
    disk_free_gb: float = 0.0
    load_avg_1m: float = 0.0
    battery_percent: Optional[float] = None
    battery_status: str = "Not available in this environment"
    temperature_c: Optional[float] = None
    temperature_status: str = "Not available in this environment"
    miner_running: bool = False
    miner_pid: Optional[int] = None
    timestamp: float = 0.0


class ResourceMonitor:
    """
    Continuous and on-demand resource monitor with fallback for Android PRoot sandboxes.
    """

    def __init__(self):
        self._last_cpu_stat: Optional[Tuple[int, int]] = None
        self._last_cpu_time: float = 0.0

    def _read_cpu_percent(self) -> float:
        """Calculate CPU usage percent from /proc/stat if psutil not present."""
        try:
            with open("/proc/stat", "r", encoding="utf-8") as f:
                first_line = f.readline()
            parts = [int(x) for x in first_line.split()[1:]]
            idle = parts[3] + parts[4]  # idle + iowait
            total = sum(parts)

            if self._last_cpu_stat is not None:
                last_idle, last_total = self._last_cpu_stat
                idle_delta = idle - last_idle
                total_delta = total - last_total
                if total_delta > 0:
                    cpu_pct = 100.0 * (1.0 - (idle_delta / total_delta))
                    self._last_cpu_stat = (idle, total)
                    return max(0.0, min(100.0, round(cpu_pct, 1)))

            self._last_cpu_stat = (idle, total)
            return 0.0
        except Exception:
            return 0.0

    def _read_memory(self) -> Tuple[float, float, float, float]:
        """Read /proc/meminfo. Returns: (percent, used_mb, total_mb, available_mb)."""
        total_kb = 0
        available_kb = 0
        free_kb = 0
        buffers_kb = 0
        cached_kb = 0

        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.split()
                    if not parts:
                        continue
                    key = parts[0].rstrip(":")
                    if key == "MemTotal":
                        total_kb = int(parts[1])
                    elif key == "MemAvailable":
                        available_kb = int(parts[1])
                    elif key == "MemFree":
                        free_kb = int(parts[1])
                    elif key == "Buffers":
                        buffers_kb = int(parts[1])
                    elif key == "Cached":
                        cached_kb = int(parts[1])

            if total_kb > 0:
                if available_kb == 0:
                    available_kb = free_kb + buffers_kb + cached_kb
                used_kb = max(0, total_kb - available_kb)
                total_mb = total_kb / 1024.0
                used_mb = used_kb / 1024.0
                avail_mb = available_kb / 1024.0
                pct = (used_kb / total_kb) * 100.0
                return (round(pct, 1), round(used_mb, 1), round(total_mb, 1), round(avail_mb, 1))
        except Exception:
            pass

        return (0.0, 0.0, 0.0, 0.0)

    def _read_disk(self, path: str = ".") -> Tuple[float, float]:
        """Read disk usage for path. Returns: (percent, free_gb)."""
        try:
            usage = shutil.disk_usage(path)
            total = usage.total
            free = usage.free
            used = usage.used
            pct = (used / total) * 100.0 if total > 0 else 0.0
            free_gb = free / (1024.0 ** 3)
            return (round(pct, 1), round(free_gb, 2))
        except Exception:
            return (0.0, 0.0)

    def _read_battery(self) -> Tuple[Optional[float], str]:
        """Read battery level if available in /sys/class/power_supply or Android."""
        # Check standard Linux/Android sysfs paths
        battery_paths = [
            "/sys/class/power_supply/battery",
            "/sys/class/power_supply/BAT0",
            "/sys/class/power_supply/BAT1",
        ]
        for b_dir in battery_paths:
            cap_file = os.path.join(b_dir, "capacity")
            status_file = os.path.join(b_dir, "status")
            if os.path.isfile(cap_file):
                try:
                    with open(cap_file, "r") as f:
                        pct = float(f.read().strip())
                    status_text = "Discharging"
                    if os.path.isfile(status_file):
                        with open(status_file, "r") as f:
                            status_text = f.read().strip()
                    return (pct, f"{pct:.0f}% ({status_text})")
                except Exception:
                    pass

        return (None, "Not available in this environment")

    def _read_temperature(self) -> Tuple[Optional[float], str]:
        """Read CPU / SOC thermal sensor if accessible."""
        thermal_base = "/sys/class/thermal"
        try:
            entries = os.listdir(thermal_base)
        except (FileNotFoundError, NotADirectoryError, PermissionError, OSError):
            return (None, "Not available in this environment")

        for entry in entries:
            if entry.startswith("thermal_zone"):
                temp_path = os.path.join(thermal_base, entry, "temp")
                try:
                    with open(temp_path, "r") as f:
                        raw = float(f.read().strip())
                    # Millidegrees vs degrees
                    deg_c = raw / 1000.0 if raw > 200 else raw
                    if 10.0 <= deg_c <= 120.0:
                        return (round(deg_c, 1), f"{deg_c:.1f}°C")
                except (FileNotFoundError, PermissionError, OSError, ValueError):
                    continue

        return (None, "Not available in this environment")

    def snapshot(self, miner_running: bool = False, miner_pid: Optional[int] = None) -> ResourceSnapshot:
        """Take an instantaneous snapshot of system resources."""
        cpu_pct = self._read_cpu_percent()
        mem_pct, mem_used, mem_total, mem_avail = self._read_memory()
        disk_pct, disk_free = self._read_disk()
        batt_pct, batt_status = self._read_battery()
        temp_c, temp_status = self._read_temperature()

        load_1m = 0.0
        try:
            load_1m = os.getloadavg()[0]
        except (AttributeError, OSError):
            pass

        return ResourceSnapshot(
            cpu_percent=cpu_pct,
            memory_percent=mem_pct,
            memory_used_mb=mem_used,
            memory_total_mb=mem_total,
            memory_available_mb=mem_avail,
            disk_percent=disk_pct,
            disk_free_gb=disk_free,
            load_avg_1m=load_1m,
            battery_percent=batt_pct,
            battery_status=batt_status,
            temperature_c=temp_c,
            temperature_status=temp_status,
            miner_running=miner_running,
            miner_pid=miner_pid,
            timestamp=time.time(),
        )
