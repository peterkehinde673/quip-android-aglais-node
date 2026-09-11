"""
MinerLogProvider: Extracts verified participation and win evidence from quip-miner logs.
Never assumes running miner process equals earned participation.
"""

import re
from typing import Optional

from quip_android.participation.base import Evidence, ParticipationProvider
from quip_android.utils.logging import get_logger

logger = get_logger("participation.logs")

# Regex patterns matching official Quip v0.2 miner stdout events
_PARTICIPATION_PATTERNS = [
    re.compile(r"participating\s+in\s+qblock\s+#?([0-9a-zA-Z_]+)", re.IGNORECASE),
    re.compile(r"qblock\s+#?([0-9a-zA-Z_]+)\s+challenge\s+accepted", re.IGNORECASE),
    re.compile(r"submitting\s+solution\s+for\s+qblock\s+#?([0-9a-zA-Z_]+)", re.IGNORECASE),
    re.compile(r"accepted\s+solution\s+for\s+qblock\s+#?([0-9a-zA-Z_]+)", re.IGNORECASE),
    re.compile(r"solver\s+registered\s+for\s+qblock\s+#?([0-9a-zA-Z_]+)", re.IGNORECASE),
]

_WIN_PATTERNS = [
    re.compile(r"won\s+qblock\s+#?([0-9a-zA-Z_]+)", re.IGNORECASE),
    re.compile(r"qblock\s+#?([0-9a-zA-Z_]+)\s+win\s+confirmed", re.IGNORECASE),
    re.compile(r"reward\s+awarded\s+for\s+qblock\s+#?([0-9a-zA-Z_]+)", re.IGNORECASE),
]


class MinerLogProvider(ParticipationProvider):
    """
    Parses quip-miner console outputs to detect genuine cryptographic participation.
    """

    def __init__(self):
        self._verified_count = 0

    def process_line(self, line: str, session_id: str) -> Optional[Evidence]:
        """
        Inspect line for real evidence patterns.
        """
        clean = line.strip()
        if not clean:
            return None

        # Check for wins first
        for pat in _WIN_PATTERNS:
            m = pat.search(clean)
            if m:
                qblock_id = m.group(1)
                self._verified_count += 1
                logger.info("VERIFIED QBLOCK WIN: %s", qblock_id)
                return Evidence(
                    session_id=session_id,
                    evidence_source="miner_logs",
                    qblock_id=qblock_id,
                    participation_status="verified",
                    win_status=True,
                    raw_evidence=clean,
                )

        # Check for participation
        for pat in _PARTICIPATION_PATTERNS:
            m = pat.search(clean)
            if m:
                qblock_id = m.group(1)
                self._verified_count += 1
                logger.info("VERIFIED QBLOCK PARTICIPATION: %s", qblock_id)
                return Evidence(
                    session_id=session_id,
                    evidence_source="miner_logs",
                    qblock_id=qblock_id,
                    participation_status="verified",
                    win_status=False,
                    raw_evidence=clean,
                )

        return None

    def get_status_message(self, is_miner_running: bool) -> str:
        if not is_miner_running:
            return "Miner is stopped."
        if self._verified_count == 0:
            return "Mining is running, but participation has not yet been independently verified."
        return f"Verified participation in {self._verified_count} events this session."
