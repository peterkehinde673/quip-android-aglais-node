"""
Safety guardian and threshold enforcement for quip-android-aglais-node.
Protects battery life, memory headroom, and device temperatures on mobile hardware.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from quip_android.config.models import SafetyConfig
from quip_android.monitoring.resources import ResourceSnapshot
from quip_android.utils.logging import get_logger

logger = get_logger("monitoring.safety")


@dataclass
class SafetyCheckResult:
    status: str = "normal"  # "normal", "warning", "stopped"
    should_stop: bool = False
    reasons: List[str] = field(default_factory=list)


class SafetyGuardian:
    """
    Enforces device safety limits for low-power operation on Android hardware.
    Triggers safety events if memory or runtime exceeds defined limits.
    """

    def __init__(self, config: SafetyConfig):
        self.config = config

    def evaluate(
        self,
        snapshot: ResourceSnapshot,
        runtime_seconds: float,
        active_workers: int,
    ) -> SafetyCheckResult:
        """
        Evaluate current metrics against safety thresholds.
        Returns SafetyCheckResult with status and reasons.
        """
        result = SafetyCheckResult()
        reasons = []

        # Check 1: Memory threshold
        if snapshot.memory_percent >= self.config.max_memory_percent:
            reasons.append(
                f"Memory usage ({snapshot.memory_percent:.1f}%) exceeded safe limit of {self.config.max_memory_percent:.1f}%"
            )
            result.should_stop = True
            result.status = "stopped"
        elif snapshot.memory_percent >= (self.config.max_memory_percent - 5.0):
            reasons.append(
                f"Memory usage ({snapshot.memory_percent:.1f}%) is nearing limit ({self.config.max_memory_percent:.1f}%)"
            )
            result.status = "warning"

        # Check 2: Maximum continuous session runtime limit
        max_seconds = self.config.max_runtime_minutes * 60.0
        if max_seconds > 0 and runtime_seconds >= max_seconds:
            reasons.append(
                f"Session runtime ({runtime_seconds / 60.0:.1f}m) reached maximum runtime threshold ({self.config.max_runtime_minutes}m)"
            )
            result.should_stop = True
            result.status = "stopped"

        # Check 3: Thermal limit (if thermal sensor accessible)
        if snapshot.temperature_c is not None and snapshot.temperature_c >= self.config.max_temperature_c:
            reasons.append(
                f"Device temperature ({snapshot.temperature_c:.1f}°C) exceeded limit ({self.config.max_temperature_c:.1f}°C)"
            )
            result.should_stop = True
            result.status = "stopped"

        # Check 4: Worker limit
        if active_workers > self.config.max_cpu_workers:
            reasons.append(
                f"Configured workers ({active_workers}) exceeds device max ({self.config.max_cpu_workers})"
            )
            result.status = "warning"

        result.reasons = reasons
        if result.should_stop:
            logger.warning("SAFETY LIMIT TRIGGERED: %s", "; ".join(reasons))
        elif result.status == "warning":
            logger.warning("Safety warning: %s", "; ".join(reasons))

        return result
