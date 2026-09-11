"""
Unit tests for hardware detection, CPU/GPU profiling, and safety limits.
"""

import unittest

from quip_android.config.models import SafetyConfig
from quip_android.monitoring.hardware import detect_cpu, detect_gpu, get_hardware_profile
from quip_android.monitoring.resources import ResourceMonitor, ResourceSnapshot
from quip_android.monitoring.safety import SafetyGuardian


class TestHardwareAndSafety(unittest.TestCase):

    def test_cpu_detection(self):
        cpu = detect_cpu()
        self.assertIsNotNone(cpu.architecture)
        self.assertGreater(cpu.core_count, 0)
        self.assertTrue(cpu.is_supported)

    def test_gpu_graceful_status(self):
        gpu = detect_gpu()
        self.assertIsInstance(gpu.cuda_available, bool)
        self.assertIsInstance(gpu.status_message, str)
        if not gpu.cuda_available:
            self.assertIn("GPU mining unavailable", gpu.status_message)

    def test_hardware_profile(self):
        hw = get_hardware_profile("Infinix-Note-G96")
        self.assertEqual(hw.device_label, "Infinix-Note-G96")
        self.assertGreater(hw.total_memory_mb, 0.0)

    def test_safety_memory_threshold_stop(self):
        cfg = SafetyConfig(max_memory_percent=80.0, max_runtime_minutes=60, max_cpu_workers=2)
        guardian = SafetyGuardian(cfg)

        # Snapshot below threshold
        snap_normal = ResourceSnapshot(memory_percent=55.0)
        res_normal = guardian.evaluate(snap_normal, runtime_seconds=300, active_workers=1)
        self.assertEqual(res_normal.status, "normal")
        self.assertFalse(res_normal.should_stop)

        # Snapshot exceeding threshold
        snap_high = ResourceSnapshot(memory_percent=85.0)
        res_high = guardian.evaluate(snap_high, runtime_seconds=300, active_workers=1)
        self.assertEqual(res_high.status, "stopped")
        self.assertTrue(res_high.should_stop)

    def test_safety_runtime_limit_stop(self):
        cfg = SafetyConfig(max_runtime_minutes=30, max_memory_percent=80.0)
        guardian = SafetyGuardian(cfg)

        snap = ResourceSnapshot(memory_percent=40.0)
        res = guardian.evaluate(snap, runtime_seconds=31 * 60, active_workers=1)
        self.assertEqual(res.status, "stopped")
        self.assertTrue(res.should_stop)
        self.assertTrue(any("runtime" in r.lower() for r in res.reasons))


if __name__ == "__main__":
    unittest.main()
