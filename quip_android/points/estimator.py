"""
Unofficial local points estimator for Quip Aglais participation.

This module never claims an official account balance. It estimates rewards only
from locally recorded evidence and applies infrastructure bonuses only when the
caller has independently verified that the corresponding feature is genuinely
available to the public.

Aglais announcement rates:
- 1 participation point per distinct qblock, capped at 72/day
- 20 points per qblock win
- Public P2P: +15%
- Public API: +15%
- Valid TLS certificate: +20%
- Live RPC: +15%
- Telemetry API: +10%
- Live dashboard: +10%

The six infrastructure bonuses stack multiplicatively. All six yield
approximately a 2.2083x participation multiplier (+120.83%), while qblock win
points remain separate.
"""

from dataclasses import dataclass, field
from typing import List

from quip_android.config.models import PointsConfig
from quip_android.participation.base import ParticipationSummary


@dataclass
class PointsBreakdown:
    verified_qblocks_today: int = 0
    base_participation_points: int = 0
    participation_cap_reached: bool = False
    verified_wins_today: int = 0
    win_points: int = 0
    bonus_multiplier: float = 1.0
    active_bonuses: List[str] = field(default_factory=list)
    unverified_bonuses: List[str] = field(default_factory=list)
    total_estimated_points: float = 0.0
    disclaimer: str = (
        "UNOFFICIAL LOCAL ESTIMATE - not an official Quip points balance; "
        "participation and infrastructure eligibility must be verified by the network."
    )


class PointsEstimator:
    MAX_DAILY_PARTICIPATION_POINTS = 72
    POINTS_PER_DISTINCT_QBLOCK = 1
    POINTS_PER_QBLOCK_WIN = 20

    BONUS_RATES = (
        ("public_p2p", 0.15),
        ("public_api", 0.15),
        ("tls", 0.20),
        ("live_rpc", 0.15),
        ("telemetry", 0.10),
        ("dashboard", 0.10),
    )

    def __init__(self, config: PointsConfig):
        self.config = config

    def estimate(self, summary: ParticipationSummary) -> PointsBreakdown:
        breakdown = PointsBreakdown()

        distinct_qblocks = summary.today_verified_qblocks
        breakdown.verified_qblocks_today = distinct_qblocks
        breakdown.base_participation_points = min(
            distinct_qblocks * self.POINTS_PER_DISTINCT_QBLOCK,
            self.MAX_DAILY_PARTICIPATION_POINTS,
        )
        breakdown.participation_cap_reached = (
            distinct_qblocks >= self.MAX_DAILY_PARTICIPATION_POINTS
        )

        breakdown.verified_wins_today = summary.today_wins
        breakdown.win_points = (
            summary.today_wins * self.POINTS_PER_QBLOCK_WIN
        )

        multiplier = 1.0
        active = []
        unverified = []

        for feature, rate in self.BONUS_RATES:
            if getattr(self.config, feature, False):
                active.append(feature)
                multiplier *= (1.0 + rate)
            else:
                unverified.append(f"{feature} (not independently verified)")

        breakdown.bonus_multiplier = round(multiplier, 4)
        breakdown.active_bonuses = active
        breakdown.unverified_bonuses = unverified
        breakdown.total_estimated_points = round(
            breakdown.base_participation_points * multiplier
            + breakdown.win_points,
            2,
        )
        return breakdown
