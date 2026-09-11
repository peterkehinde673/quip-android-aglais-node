"""
Persistent local journal for participation evidence records.
Appends verified participation events to data/participation.jsonl.
"""

import json
import os
import threading
from datetime import datetime
from typing import List, Optional

from quip_android.participation.base import Evidence, ParticipationSummary
from quip_android.utils.logging import get_logger
from quip_android.utils.system import resolve_path

logger = get_logger("participation.records")


class ParticipationJournal:
    """
    Thread-safe append-only journal storing participation evidence in JSON Lines format.
    Calculates distinct qblock counts and wins without faking data.
    """

    def __init__(self, journal_path: str = "data/participation.jsonl"):
        self.journal_path = resolve_path(journal_path)
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.journal_path) or ".", exist_ok=True)

    def record(self, evidence: Evidence) -> None:
        """Append a new evidence entry to the journal."""
        with self._lock:
            try:
                line = json.dumps(evidence.to_dict()) + "\n"
                with open(self.journal_path, "a", encoding="utf-8") as f:
                    f.write(line)
                logger.info(
                    "Recorded participation evidence: qblock=%s, verified=%s, win=%s",
                    evidence.qblock_id or "unknown",
                    evidence.participation_status == "verified",
                    evidence.win_status,
                )
            except Exception as err:
                logger.error("Failed to write evidence to journal %s: %s", self.journal_path, err)

    def get_entries(self, limit: Optional[int] = None) -> List[Evidence]:
        """Read all or latest N evidence entries."""
        if not os.path.exists(self.journal_path):
            return []

        entries = []
        with self._lock:
            try:
                with open(self.journal_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                d = json.loads(line)
                                entries.append(Evidence.from_dict(d))
                            except json.JSONDecodeError:
                                pass
            except Exception as err:
                logger.error("Failed to read journal %s: %s", self.journal_path, err)

        if limit is not None and len(entries) > limit:
            return entries[-limit:]
        return entries

    def get_summary(self, target_date: Optional[str] = None) -> ParticipationSummary:
        """
        Calculate distinct qblock participation and wins for today.
        Target date format: YYYY-MM-DD (defaults to UTC today).
        """
        day_str = target_date or datetime.utcnow().strftime("%Y-%m-%d")
        entries = self.get_entries()

        today_qblocks = set()
        today_wins = 0
        total_qblocks = set()
        total_wins = 0
        latest_evidence: Optional[Evidence] = None

        for entry in entries:
            is_today = entry.timestamp.startswith(day_str)
            is_verified = (entry.participation_status == "verified")

            if is_verified and entry.qblock_id:
                total_qblocks.add(entry.qblock_id)
                if is_today:
                    today_qblocks.add(entry.qblock_id)

            if entry.win_status:
                total_wins += 1
                if is_today:
                    today_wins += 1

            latest_evidence = entry

        msg = "Mining is running, but participation has not yet been independently verified."
        if today_qblocks:
            msg = f"Verified participation in {len(today_qblocks)} distinct qblock(s) today."

        return ParticipationSummary(
            today_verified_qblocks=len(today_qblocks),
            today_distinct_qblock_ids=sorted(list(today_qblocks)),
            today_wins=today_wins,
            total_lifetime_qblocks=len(total_qblocks),
            total_lifetime_wins=total_wins,
            latest_evidence=latest_evidence,
            status_message=msg,
        )
