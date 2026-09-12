"""
Central miner and node controller for quip-android-aglais-node.
Orchestrates pre-flight checks, RPC management, process execution, real-time participation tracking,
and safety monitoring across Eco, Daily, and Performance modes.
"""

import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from quip_android.config.models import AppConfig
from quip_android.miner.cpu import CpuMinerCommandBuilder
from quip_android.miner.gpu import GpuMinerCommandBuilder
from quip_android.miner.process import MinerProcess
from quip_android.monitoring.hardware import get_hardware_profile
from quip_android.monitoring.resources import ResourceMonitor, ResourceSnapshot
from quip_android.monitoring.safety import SafetyCheckResult, SafetyGuardian
from quip_android.participation.base import Evidence, ParticipationSummary
from quip_android.participation.miner_logs import MinerLogProvider
from quip_android.participation.records import ParticipationJournal
from quip_android.points.estimator import PointsBreakdown, PointsEstimator
from quip_android.rpc.manager import RpcManager
from quip_android.utils.logging import get_logger

logger = get_logger("miner.controller")


class MinerController:
    """
    Unified controller managing Quip node lifecycle and operating modes.
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.rpc_manager = RpcManager(config.rpc, config.node.chain_id)
        self.resource_monitor = ResourceMonitor()
        self.safety_guardian = SafetyGuardian(config.safety)
        self.participation_journal = ParticipationJournal(config.participation.journal_path)
        self.participation_provider = MinerLogProvider()
        self.points_estimator = PointsEstimator(config.points)

        self.miner_process: Optional[MinerProcess] = None
        self.session_id: str = ""
        self.active_mode: str = config.node.mode
        self.active_workers: int = config.miner.workers
        self.session_start_time: float = 0.0
        self.status_message: str = "Stopped"
        self.safety_status: str = "normal"
        self.last_safety_reasons: List[str] = []

        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_requested = threading.Event()
        self._lock = threading.Lock()

    def run_preflight_checks(
        self,
        custom_signer_key: Optional[str] = None,
    ) -> Tuple[bool, List[str], Optional[str]]:
        """
        Execute comprehensive pre-flight verification:
        1. Select healthy RPC endpoint
        2. Verify quip-miner binary exists
        3. Verify signer key exists
        Returns: (is_ready, error_list, active_rpc)
        """
        errors = []

        # 1. RPC Selection
        logger.info("Verifying Substrate RPC endpoints...")
        active_rpc = self.rpc_manager.select_healthy_endpoint(prefer_existing=True)
        if not active_rpc:
            errors.append(
                "No healthy Substrate RPC endpoints available. Check network connectivity or run 'quip-android rpc-check'."
            )

        # 2. Builder Validation
        cpu_builder = CpuMinerCommandBuilder(self.config)
        valid, builder_errs = cpu_builder.validate_prerequisites(
            active_rpc=active_rpc or "",
            custom_signer_key=custom_signer_key,
        )
        if not valid:
            errors.extend(builder_errs)

        return (len(errors) == 0, errors, active_rpc)

    def start(
        self,
        mode: Optional[str] = None,
        custom_workers: Optional[int] = None,
        custom_signer_key: Optional[str] = None,
        max_runtime_minutes: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """
        Start the miner in specified mode (eco, daily, performance).
        """
        with self._lock:
            if self.miner_process and self.miner_process.is_running:
                return (False, f"Miner is already running (PID: {self.miner_process.pid})")

            target_mode = mode or self.config.node.mode
            if target_mode not in ("eco", "daily", "performance"):
                return (False, f"Invalid mode '{target_mode}'. Choose from: eco, daily, performance")

            self.active_mode = target_mode
            # Keep command generation consistent with the mode requested by the CLI.\n            self.config.node.mode = target_mode\n            self.session_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            self._stop_requested.clear()

            # Determine workers based on mode
            workers = custom_workers if custom_workers is not None else self.config.miner.workers
            if target_mode == "eco":
                workers = 1
                logger.info("Eco Mode: 1 worker, low heat & power prioritization.")
            elif target_mode == "daily":
                workers = min(workers, 2)
                logger.info(
                    "Daily Mode: %d worker(s). Low-power participation session. "
                    "Note: Points depend on actual distinct qblock participation recorded on-chain; "
                    "brief running does not guarantee points.",
                    workers,
                )
            elif target_mode == "performance":
                logger.warning(
                    "Performance Mode: Running %d worker(s). Note: Running on battery-powered phones "
                    "may cause increased thermal load and battery drain.",
                    workers,
                )

            self.active_workers = workers

            # Run Pre-flight
            ready, errors, active_rpc = self.run_preflight_checks(custom_signer_key=custom_signer_key)
            if not ready:
                err_msg = "; ".join(errors)
                logger.error("Pre-flight check failed: %s", err_msg)
                return (False, f"Pre-flight check failed: {err_msg}")

            # Build command
            if self.config.miner.backend == "gpu":
                gpu_builder = GpuMinerCommandBuilder(self.config)
                cmd, cmd_errors = gpu_builder.build_command(active_rpc=active_rpc, custom_signer_key=custom_signer_key)
            else:
                cpu_builder = CpuMinerCommandBuilder(self.config)
                cmd, cmd_errors = cpu_builder.build_command(
                    active_rpc=active_rpc,
                    custom_signer_key=custom_signer_key,
                    custom_workers=workers,
                )

            if not cmd or cmd_errors:
                return (False, f"Failed to build miner command: {'; '.join(cmd_errors)}")

            # Create line output consumer callback
            def on_miner_line(line: str) -> None:
                evidence = self.participation_provider.process_line(line, self.session_id)
                if evidence:
                    self.participation_journal.record(evidence)

            # Spawn process
            self.miner_process = MinerProcess(
                command=cmd,
                log_dir="logs",
                nice_value=self.config.safety.process_nice,
                line_callback=on_miner_line,
            )

            started = self.miner_process.start()
            if not started:
                return (False, "Subprocess failed to launch quip-miner binary")

            self.session_start_time = time.time()
            self.status_message = "Running"

            # Launch monitoring thread
            self._monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                args=(max_runtime_minutes,),
                daemon=True,
            )
            self._monitor_thread.start()

            return (True, f"Started Quip miner in {target_mode.upper()} mode with {workers} worker(s)")

    def _monitoring_loop(self, max_runtime_minutes: Optional[int] = None) -> None:
        """
        Background monitoring loop: evaluates safety, tracks participation goal, and monitors process.
        """
        runtime_limit = (
            max_runtime_minutes
            if max_runtime_minutes is not None
            else self.config.miner.max_runtime_minutes
        ) * 60.0

        daily_target = self.config.participation.daily_qblock_target

        while not self._stop_requested.is_set():
            time.sleep(4.0)

            if not self.miner_process or not self.miner_process.is_running:
                logger.info("Miner process stopped execution.")
                self.status_message = "Stopped"
                break

            current_runtime = self.miner_process.runtime_seconds
            snapshot = self.resource_monitor.snapshot(
                miner_running=True,
                miner_pid=self.miner_process.pid,
            )

            # Safety checks
            safety_res = self.safety_guardian.evaluate(
                snapshot=snapshot,
                runtime_seconds=current_runtime,
                active_workers=self.active_workers,
            )
            self.safety_status = safety_res.status
            self.last_safety_reasons = safety_res.reasons

            if safety_res.should_stop:
                logger.warning("Emergency safety stop: %s", "; ".join(safety_res.reasons))
                self.stop(reason="Safety limit exceeded: " + "; ".join(safety_res.reasons))
                break

            # Daily mode completion check
            if self.active_mode == "daily":
                summary = self.participation_journal.get_summary()
                if summary.today_verified_qblocks >= daily_target:
                    logger.info(
                        "Daily participation target of %d distinct qblocks reached! Stopping to preserve battery.",
                        daily_target,
                    )
                    self.stop(reason=f"Daily target reached ({daily_target} qblocks)")
                    break

            # Configured session runtime check
            if runtime_limit > 0 and current_runtime >= runtime_limit:
                logger.info(
                    "Session runtime limit (%dm) reached. Stopping miner.",
                    runtime_limit / 60.0,
                )
                self.stop(reason=f"Runtime limit ({runtime_limit / 60.0:.0f}m) reached")
                break

    def stop(self, reason: str = "User requested stop") -> bool:
        """Gracefully terminate active miner session."""
        with self._lock:
            self._stop_requested.set()
            self.status_message = f"Stopped ({reason})"
            if self.miner_process and self.miner_process.is_running:
                logger.info("Stopping miner session: %s", reason)
                success = self.miner_process.stop()
                return success
            return True

    def get_status(self) -> Dict[str, Any]:
        """Compile a full node and miner status report."""
        is_running = bool(self.miner_process and self.miner_process.is_running)
        pid = self.miner_process.pid if is_running else None
        runtime = self.miner_process.runtime_seconds if self.miner_process else 0.0

        snapshot = self.resource_monitor.snapshot(miner_running=is_running, miner_pid=pid)
        hw_profile = get_hardware_profile(self.config.node.device_label)
        part_summary = self.participation_journal.get_summary()
        points = self.points_estimator.estimate(part_summary)
        rpc_summary = self.rpc_manager.get_status_summary()

        return {
            "node": {
                "network": self.config.node.network,
                "chain_id": self.config.node.chain_id,
                "mode": self.active_mode,
                "device": self.config.node.device_label,
                "environment": hw_profile.environment_desc,
            },
            "miner": {
                "running": is_running,
                "pid": pid,
                "status": "Running" if is_running else self.status_message,
                "workers": self.active_workers,
                "backend": self.config.miner.backend,
                "runtime_seconds": round(runtime, 1),
                "runtime_minutes": round(runtime / 60.0, 1),
                "log_file": self.miner_process.session_log_path if self.miner_process else None,
            },
            "rpc": {
                "active_endpoint": rpc_summary.get("active_endpoint") or "None selected",
                "endpoints": rpc_summary.get("endpoints", []),
            },
            "hardware": {
                "cpu_arch": hw_profile.cpu.architecture,
                "cpu_cores": hw_profile.cpu.core_count,
                "cpu_model": hw_profile.cpu.model_name,
                "gpu_available": hw_profile.gpu.cuda_available,
                "gpu_status": hw_profile.gpu.status_message,
                "total_ram_mb": hw_profile.total_memory_mb,
            },
            "resources": {
                "cpu_percent": snapshot.cpu_percent,
                "memory_percent": snapshot.memory_percent,
                "memory_used_mb": snapshot.memory_used_mb,
                "memory_available_mb": snapshot.memory_available_mb,
                "disk_percent": snapshot.disk_percent,
                "disk_free_gb": snapshot.disk_free_gb,
                "battery": snapshot.battery_status,
                "temperature": snapshot.temperature_status,
            },
            "safety": {
                "status": self.safety_status,
                "reasons": self.last_safety_reasons,
            },
            "participation": {
                "today_verified_qblocks": part_summary.today_verified_qblocks,
                "today_wins": part_summary.today_wins,
                "today_qblock_ids": part_summary.today_distinct_qblock_ids,
                "status_message": (
                    part_summary.status_message
                    if is_running
                    else "Miner is stopped."
                ),
                "lifetime_qblocks": part_summary.total_lifetime_qblocks,
                "lifetime_wins": part_summary.total_lifetime_wins,
            },
            "points": {
                "base_participation_points": points.base_participation_points,
                "win_points": points.win_points,
                "bonus_multiplier": points.bonus_multiplier,
                "total_estimated_points": points.total_estimated_points,
                "disclaimer": points.disclaimer,
                "active_bonuses": points.active_bonuses,
                "unverified_bonuses": points.unverified_bonuses,
            },
        }
