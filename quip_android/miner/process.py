"""
Process manager for quip-miner subprocess execution.
Handles streaming stdout/stderr, signal handling, process priority (nice), and safe shutdown.
"""

import os
import signal
import subprocess
import threading
import time
from datetime import datetime
from typing import Callable, List, Optional

from quip_android.utils.logging import get_logger
from quip_android.utils.system import apply_process_nice, resolve_path

logger = get_logger("miner.process")


class MinerProcess:
    """
    Manages the lifecycle of a single quip-miner execution instance.
    Streams output lines to both session log files and real-time callback listeners.
    """

    def __init__(
        self,
        command: List[str],
        log_dir: str = "logs",
        nice_value: int = 19,
        line_callback: Optional[Callable[[str], None]] = None,
    ):
        self.command = command
        self.log_dir = log_dir
        self.nice_value = nice_value
        self.line_callback = line_callback

        self.proc: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self.start_time: float = 0.0
        self.stop_time: float = 0.0
        self.exit_code: Optional[int] = None
        self.session_log_path: Optional[str] = None
        self.is_running: bool = False

        self._stdout_thread: Optional[threading.Thread] = None
        self._log_file_handle = None
        self._lock = threading.Lock()

    def start(self) -> bool:
        """
        Launch the miner subprocess. Returns True if started successfully.
        """
        with self._lock:
            if self.is_running:
                logger.warning("Miner process is already running (PID: %s)", self.pid)
                return True

            os.makedirs(self.log_dir, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            self.session_log_path = os.path.join(self.log_dir, f"miner_{timestamp}.log")

            try:
                self._log_file_handle = open(self.session_log_path, "w", encoding="utf-8", buffering=1)
                cmd_str = " ".join(self.command)
                self._log_file_handle.write(f"--- QUIP MINER SESSION STARTED AT {timestamp} ---\n")
                self._log_file_handle.write(f"Command: {cmd_str}\n\n")

                logger.info("Executing command: %s", cmd_str)
                self.proc = subprocess.Popen(
                    self.command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    preexec_fn=os.setsid if hasattr(os, "setsid") else None,
                )

                self.pid = self.proc.pid
                self.start_time = time.time()
                self.is_running = True

                # Set nice priority for Android responsiveness
                if self.nice_value is not None:
                    success = apply_process_nice(self.pid, self.nice_value)
                    if success:
                        logger.debug("Applied nice value %d to PID %d", self.nice_value, self.pid)

                # Write PID file for process tracking
                pid_path = os.path.join(self.log_dir, "miner.pid")
                with open(pid_path, "w") as pf:
                    pf.write(str(self.pid))

                # Background output streaming thread
                self._stdout_thread = threading.Thread(target=self._stream_output, daemon=True)
                self._stdout_thread.start()

                logger.info("Miner started successfully (PID: %d)", self.pid)
                return True

            except Exception as err:
                logger.error("Failed to start miner process: %s", err)
                self.is_running = False
                if self._log_file_handle:
                    self._log_file_handle.close()
                    self._log_file_handle = None
                return False

    def _stream_output(self) -> None:
        """Read stdout lines and dispatch to callbacks and log file."""
        if not self.proc or not self.proc.stdout:
            return

        try:
            for line in iter(self.proc.stdout.readline, ""):
                if not line:
                    break
                clean_line = line.rstrip()
                # Log to session file
                if self._log_file_handle and not self._log_file_handle.closed:
                    ts = datetime.utcnow().strftime("%H:%M:%S")
                    self._log_file_handle.write(f"[{ts}] {clean_line}\n")
                    self._log_file_handle.flush()

                # Dispatch callback (for real participation parsing)
                if self.line_callback:
                    try:
                        self.line_callback(clean_line)
                    except Exception as cb_err:
                        logger.debug("Callback error on log line: %s", cb_err)

        except Exception as err:
            logger.debug("Stream reading closed: %s", err)
        finally:
            self.proc.stdout.close()
            self.proc.wait()
            self.exit_code = self.proc.returncode
            self.is_running = False
            self.stop_time = time.time()
            if self._log_file_handle and not self._log_file_handle.closed:
                self._log_file_handle.write(
                    f"\n--- QUIP MINER SESSION TERMINATED (Exit Code: {self.exit_code}) ---\n"
                )
                self._log_file_handle.close()

            # Remove PID file
            pid_path = os.path.join(self.log_dir, "miner.pid")
            if os.path.exists(pid_path):
                try:
                    os.remove(pid_path)
                except OSError:
                    pass

            logger.info("Miner process PID %s terminated with exit code %s", self.pid, self.exit_code)

    def stop(self, timeout: float = 8.0) -> bool:
        """
        Gracefully stop the miner process using SIGTERM, followed by SIGKILL if unresponsive.
        """
        with self._lock:
            if not self.is_running or not self.proc:
                return True

            logger.info("Stopping miner process (PID: %d)...", self.pid)
            try:
                # Send SIGTERM to process group or process
                if hasattr(os, "killpg") and hasattr(os, "getpgid"):
                    try:
                        os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                else:
                    self.proc.terminate()

                # Wait for clean exit
                start_wait = time.time()
                while time.time() - start_wait < timeout:
                    if self.proc.poll() is not None:
                        self.is_running = False
                        self.exit_code = self.proc.returncode
                        logger.info("Miner process cleanly exited.")
                        return True
                    time.sleep(0.2)

                # Force kill if still alive
                logger.warning("Miner did not exit within %ss; sending SIGKILL...", timeout)
                if hasattr(os, "killpg") and hasattr(os, "getpgid"):
                    try:
                        os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:
                    self.proc.kill()

                self.proc.wait()
                self.is_running = False
                self.exit_code = self.proc.returncode
                return True

            except Exception as err:
                logger.error("Error stopping miner: %s", err)
                return False

    @property
    def runtime_seconds(self) -> float:
        if not self.start_time:
            return 0.0
        if self.is_running:
            return time.time() - self.start_time
        return max(0.0, self.stop_time - self.start_time)
