"""
Base interfaces and data structures for Quip Aglais participation evidence.
"""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Evidence:
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    session_id: str = ""
    network: str = "aglais"
    evidence_source: str = "miner_logs"  # "miner_logs", "telemetry", "substrate_event", "official_api"
    qblock_id: Optional[str] = None
    participation_status: str = "unverified"  # "verified", "unverified", "pending"
    win_status: bool = False
    raw_evidence: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Evidence":
        return cls(
            timestamp=data.get("timestamp", ""),
            session_id=data.get("session_id", ""),
            network=data.get("network", "aglais"),
            evidence_source=data.get("evidence_source", "miner_logs"),
            qblock_id=data.get("qblock_id"),
            participation_status=data.get("participation_status", "unverified"),
            win_status=bool(data.get("win_status", False)),
            raw_evidence=data.get("raw_evidence", ""),
        )


@dataclass
class ParticipationSummary:
    today_verified_qblocks: int = 0
    today_distinct_qblock_ids: List[str] = field(default_factory=list)
    today_wins: int = 0
    total_lifetime_qblocks: int = 0
    total_lifetime_wins: int = 0
    latest_evidence: Optional[Evidence] = None
    status_message: str = "Mining is running, but participation has not yet been independently verified."


class ParticipationProvider(ABC):
    """
    Pluggable provider interface for detecting real on-chain/miner participation evidence.
    """

    @abstractmethod
    def process_line(self, line: str, session_id: str) -> Optional[Evidence]:
        """Parse incoming line or event and return Evidence if participation verified."""
        pass

    @abstractmethod
    def get_status_message(self, is_miner_running: bool) -> str:
        """Return human-readable verification status."""
        pass
