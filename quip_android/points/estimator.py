"""
Points Estimator for Quip Network Aglais Testnet.
Strictly calculates local estimates based on verified participation evidence.
Clearly labeled: UNOFFICIAL LOCAL ESTIMATE.
"""

from dataclasses import dataclass, field
from typing import Dict, List

from quip_android.config.models import PointsConfig
from quip_android.participation.base import ParticipationSummary


@dataclass
class PointsBreakdown:
    # Participation points: 1 pt per distinct qblock, capped at 72/day
    verified_qblocks_today: int = 0
    base_participation_points: int = 0
    participation_cap_reached: bool = False

    # Win points: 20 pts per qblock win
    verified_wins_today: int = 0
    win_points: int = 0

    # Infrastructure bonuses (applied to participation points)
    bonus_multiplier: float = 1.0
    active_bonuses: List[str] = field(default_factory=list)
    unverified_bonuses: List[str] = field(default_factory=list)

    # Total estimated points
    total_estimated_points: float = 0.0
    disclaimer: str = "UNOFFICIAL LOCAL ESTIMATE - Points depend entirely on actual Aglais network records."


class PointsEstimator:
    """
    Computes local estimated points according to official Quip Aglais testnet rules:
    - 1 point per distinct qblock participation (daily cap: 72 points)
    - 20 points per qblock win
    - Infrastructure multipliers only if independently verified
    """

    MAX_DAILY_PARTICIPATION_POINTS = 72
    POINTS_PER_DISTINCT_QBLOCK = 1
    POINTS_PER_QBLOCK_WIN = 20

    def __init__(self, config: PointsConfig):
        self.config = config

    def estimate(self, summary: ParticipationSummary) -> PointsBreakdown:
        breakdown = PointsBreakdown()

        # 1. Base participation points
        distinct_qblocks = summary.today_verified_qblocks
        breakdown.verified_qblocks_today = distinct_qblocks

        base_pts = min(distinct_qblocks * self.POINTS_PER_DISTINCT_QBLOCK, self.MAX_DAILY_PARTICIPATION_POINTS)
        breakdown.base_participation_points = base_pts
        breakdown.participation_cap_reached = (distinct_qblocks >= self.MAX_DAILY_PARTICIPATION_POINTS)

        # 2. Win points
        breakdown.verified_wins_today = summary.today_wins
        breakdown.win_points = summary.today_wins * self.POINTS_PER_QBLOCK_WIN

        # 3. Infrastructure bonuses
        # On Android phones, inbound ports and public domains are typically unavailable / not verified
        multiplier = 1.0
        active = []
        unverified = []

        # Local dashboard bonus (can be active locally if enabled)
        if self.config.dashboard:
            active.append("local_dashboard")
            multiplier += 0.05  # +5% local telemetry/dashboard estimate
        else:
            unverified.append("dashboard (disabled)")

        # Public server bonuses (strictly marked unverified on mobile without public IP/TLS)
        if self.config.public_p2p:
            active.append("public_p2p")
            multiplier += 0.10
        else:
            unverified.append("public_p2p (Not verified / unavailable on Android)")

        if self.config.public_api:
            active.append("public_api")
            multiplier += 0.10
        else:
            unverified.append("public_api (Not verified / unavailable on Android)")

        if self.config.tls:
            active.append("tls")
            multiplier += 0.05
        else:
            unverified.append("tls (Not verified / unavailable on Android)")

        if self.config.live_rpc:
            active.append("live_rpc")
            multiplier += 0.10
        else:
            unverified.append("live_rpc (Not verified / client mode only)")

        if self.config.telemetry:
            active.append("telemetry")
            multiplier += 0.05
        else:
            unverified.append("telemetry (Not verified / unavailable)")

        breakdown.bonus_multiplier = round(multiplier, 2)
        breakdown.active_bonuses = active
        breakdown.unverified_bonuses = unverified

        # Total points calculation: (base_participation * multiplier) + win_points
        total = (base_pts * multiplier) + breakdown.win_points
        breakdown.total_estimated_points = round(total, 1)

        return breakdown
