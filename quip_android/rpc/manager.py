"""
RPC Manager with automatic failover and health tracking for Quip Network / Aglais.
"""

import time
from typing import Any, Dict, List, Optional

from quip_android.config.models import RpcConfig
from quip_android.rpc.health import RpcHealthCheckResult, check_endpoint_health
from quip_android.utils.logging import get_logger

logger = get_logger("rpc.manager")


class RpcManager:
    """
    Manages a pool of candidate Substrate RPC endpoints for Aglais testnet.
    Automatically verifies health, tracks failure histories, and handles failovers.
    """

    def __init__(
        self,
        config: RpcConfig,
        expected_chain: str = "quip-testnet",
    ):
        self.config = config
        self.expected_chain = expected_chain
        self.active_endpoint: Optional[str] = None
        self.last_results: Dict[str, RpcHealthCheckResult] = {}
        self.health_history: List[RpcHealthCheckResult] = []
        self.endpoint_failure_counts: Dict[str, int] = {ep: 0 for ep in config.endpoints}
        self.last_check_time: float = 0.0

    def check_all(self, force: bool = False) -> Dict[str, RpcHealthCheckResult]:
        """
        Run health check on all candidate endpoints with configured timeout and chain validation.
        """
        now = time.time()
        # Enforce rate-limiting on checks unless forced
        if not force and (now - self.last_check_time) < 3.0 and self.last_results:
            return self.last_results

        results = {}
        for ep in self.config.endpoints:
            res = check_endpoint_health(
                endpoint=ep,
                timeout=self.config.timeout_seconds,
                expected_chain=self.expected_chain,
                require_chain_match=self.config.require_chain_match,
            )
            results[ep] = res
            self.health_history.append(res)
            # Limit history to latest 50 entries
            if len(self.health_history) > 50:
                self.health_history.pop(0)

            if res.is_healthy:
                self.endpoint_failure_counts[ep] = 0
            else:
                self.endpoint_failure_counts[ep] = self.endpoint_failure_counts.get(ep, 0) + 1

        self.last_results = results
        self.last_check_time = now
        return results

    def select_healthy_endpoint(self, prefer_existing: bool = True) -> Optional[str]:
        """
        Select the fastest healthy endpoint. If prefer_existing is True and current
        active endpoint is healthy, retains it to prevent unnecessary reconnection churning.
        """
        results = self.check_all()

        if prefer_existing and self.active_endpoint:
            current_res = results.get(self.active_endpoint)
            if current_res and current_res.is_healthy:
                logger.debug("Retaining current healthy active RPC: %s", self.active_endpoint)
                return self.active_endpoint

        # Filter healthy endpoints and sort by latency
        healthy_candidates = [
            res for res in results.values() if res.is_healthy
        ]

        if not healthy_candidates:
            logger.error("No healthy Substrate RPC endpoints available out of %d candidates!", len(results))
            self.active_endpoint = None
            return None

        healthy_candidates.sort(key=lambda r: r.latency_ms)
        selected = healthy_candidates[0].endpoint

        if selected != self.active_endpoint:
            logger.info(
                "Switched active RPC from %s to %s (latency: %.1fms)",
                self.active_endpoint or "None",
                selected,
                healthy_candidates[0].latency_ms,
            )
            self.active_endpoint = selected

        return self.active_endpoint

    def failover(self) -> Optional[str]:
        """
        Explicitly mark current active endpoint as failed and trigger failover to next healthy.
        """
        logger.warning("Triggering RPC failover from active endpoint: %s", self.active_endpoint)
        if self.active_endpoint:
            self.endpoint_failure_counts[self.active_endpoint] = (
                self.endpoint_failure_counts.get(self.active_endpoint, 0) + 1
            )
        return self.select_healthy_endpoint(prefer_existing=False)

    def get_status_summary(self) -> Dict[str, Any]:
        """Return structured summary for CLI and dashboard."""
        return {
            "active_endpoint": self.active_endpoint,
            "has_healthy": any(r.is_healthy for r in self.last_results.values()),
            "endpoints": [
                {
                    "endpoint": ep,
                    "healthy": res.is_healthy,
                    "latency_ms": res.latency_ms,
                    "peers": res.peers,
                    "chain": res.chain_name,
                    "error": res.error_message,
                    "is_active": (ep == self.active_endpoint),
                }
                for ep, res in self.last_results.items()
            ],
        }
