"""
Unit tests for real participation detection, journal records, and points estimation.
"""

import os
import tempfile
import unittest

from quip_android.config.models import PointsConfig
from quip_android.participation.base import Evidence
from quip_android.participation.miner_logs import MinerLogProvider
from quip_android.participation.records import ParticipationJournal
from quip_android.points.estimator import PointsEstimator


class TestParticipationAndPoints(unittest.TestCase):

    def test_miner_log_participation_parsing(self):
        provider = MinerLogProvider()
        line = "2026-09-11 20:00:00 [INFO] participating in qblock #48291 solver mode"
        evidence = provider.process_line(line, session_id="test-session")

        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.qblock_id, "48291")
        self.assertEqual(evidence.participation_status, "verified")
        self.assertFalse(evidence.win_status)
        self.assertEqual(evidence.evidence_source, "miner_logs")

    def test_miner_log_win_parsing(self):
        provider = MinerLogProvider()
        line = "2026-09-11 20:05:12 [INFO] won qblock #48291 with hash 0xabcd"
        evidence = provider.process_line(line, session_id="test-session")

        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.qblock_id, "48291")
        self.assertTrue(evidence.win_status)
        self.assertEqual(evidence.participation_status, "verified")

    def test_journal_recording_and_summary(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".jsonl", delete=False) as tf:
            journal_path = tf.name

        try:
            journal = ParticipationJournal(journal_path)

            # Record 3 distinct qblocks, 1 duplicate qblock, and 1 win
            e1 = Evidence(timestamp="2026-09-11T10:00:00Z", qblock_id="101", participation_status="verified")
            e2 = Evidence(timestamp="2026-09-11T10:30:00Z", qblock_id="102", participation_status="verified")
            e3 = Evidence(timestamp="2026-09-11T11:00:00Z", qblock_id="103", participation_status="verified")
            e_dup = Evidence(timestamp="2026-09-11T11:15:00Z", qblock_id="101", participation_status="verified")
            e_win = Evidence(timestamp="2026-09-11T11:30:00Z", qblock_id="102", win_status=True, participation_status="verified")

            journal.record(e1)
            journal.record(e2)
            journal.record(e3)
            journal.record(e_dup)
            journal.record(e_win)

            summary = journal.get_summary("2026-09-11")
            self.assertEqual(summary.today_verified_qblocks, 3)  # Distinct qblocks!
            self.assertEqual(summary.today_wins, 1)
            self.assertEqual(summary.today_distinct_qblock_ids, ["101", "102", "103"])

            # Test Points Calculation on this summary
            cfg = PointsConfig(dashboard=False)
            estimator = PointsEstimator(cfg)
            points = estimator.estimate(summary)

            self.assertEqual(points.base_participation_points, 3)  # 3 qblocks * 1 pt
            self.assertEqual(points.win_points, 20)  # 1 win * 20 pts
            self.assertEqual(points.total_estimated_points, 23.0)
            self.assertIn("UNOFFICIAL LOCAL ESTIMATE", points.disclaimer)

        finally:
            if os.path.exists(journal_path):
                os.remove(journal_path)

    def test_daily_participation_cap_at_72(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".jsonl", delete=False) as tf:
            journal_path = tf.name

        try:
            journal = ParticipationJournal(journal_path)
            for i in range(100):
                e = Evidence(
                    timestamp="2026-09-11T12:00:00Z",
                    qblock_id=f"q_{i}",
                    participation_status="verified",
                )
                journal.record(e)

            summary = journal.get_summary("2026-09-11")
            self.assertEqual(summary.today_verified_qblocks, 100)

            cfg = PointsConfig()
            estimator = PointsEstimator(cfg)
            points = estimator.estimate(summary)

            # Must be strictly capped at 72 points
            self.assertEqual(points.base_participation_points, 72)
            self.assertTrue(points.participation_cap_reached)
        finally:
            if os.path.exists(journal_path):
                os.remove(journal_path)


if __name__ == "__main__":
    unittest.main()
