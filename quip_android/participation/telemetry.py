"""
Telemetry participation provider for quip-miner telemetry stream.
"""

from typing import Optional

from quip_android.participation.base import Evidence, ParticipationProvider
from quip_android.utils.logging import get_logger

logger = get_logger("participation.telemetry")


class TelemetryProvider(ParticipationProvider):
    """
    Parses quip-miner telemetry reports if enabled.
    """

    def __init__(self):
        self._verified_count = 0

    def process_line(self, line: str, session_id: str) -> Optional[Evidence]:
        # Handle telemetry payloads
        if "telemetry" in line.lower() and "block" in line.lower():
            self._verified_count += 1
            return Evidence(
                session_id=session_id,
                evidence_source="telemetry",
                participation_status="verified",
                raw_evidence=line.strip(),
            )
        return None

    def get_status_message(self, is_miner_running: bool) -> str:
        if not is_miner_running:
            return "Miner is stopped."
        if self._verified_count == 0:
            return "Mining is running, but participation has not yet been independently verified."
        return f"Telemetry verified {self._verified_count} events."
