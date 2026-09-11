"""
Configuration dataclasses and validation models for quip-android-aglais-node.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class NodeConfig:
    network: str = "aglais"
    chain_id: str = "quip-testnet"
    mode: str = "eco"  # "eco", "daily", "performance"
    device_label: str = "Infinix-Note-G96"

    def validate(self) -> List[str]:
        errors = []
        if self.mode not in ("eco", "daily", "performance"):
            errors.append(f"Invalid mode '{self.mode}'. Allowed: eco, daily, performance")
        if not self.network:
            errors.append("Network name cannot be empty")
        return errors


@dataclass
class MinerConfig:
    backend: str = "cpu"  # "cpu", "gpu"
    workers: int = 1
    max_runtime_minutes: int = 60
    quip_miner_path: str = "auto"
    extra_args: List[str] = field(default_factory=list)

    def validate(self) -> List[str]:
        errors = []
        if self.backend not in ("cpu", "gpu"):
            errors.append(f"Invalid backend '{self.backend}'. Allowed: cpu, gpu")
        if self.workers < 1:
            errors.append("Worker count must be at least 1")
        if self.max_runtime_minutes < 0:
            errors.append("max_runtime_minutes cannot be negative")
        return errors


@dataclass
class RpcConfig:
    endpoints: List[str] = field(
        default_factory=lambda: [
            "wss://bootnode-1.aglais.quip.network:20049/rpc",
            "wss://bootnode-2.aglais.quip.network:20049/rpc",
            "wss://bootnode-3.aglais.quip.network:20049/rpc",
        ]
    )
    timeout_seconds: float = 6.0
    retry_interval_seconds: float = 10.0
    require_chain_match: bool = True

    def validate(self) -> List[str]:
        errors = []
        if not self.endpoints:
            errors.append("At least one candidate RPC endpoint must be configured")
        for ep in self.endpoints:
            lower = ep.strip().lower()
            if lower.startswith("tcp://") or ":30333" in lower:
                errors.append(
                    f"Invalid RPC endpoint '{ep}'. Port 30333/TCP is a Substrate P2P bootnode address, "
                    f"NOT a WebSocket RPC endpoint. Quip miner requires ws:// or wss:// RPC."
                )
            elif not (lower.startswith("ws://") or lower.startswith("wss://") or lower.startswith("http://") or lower.startswith("https://")):
                errors.append(f"RPC endpoint '{ep}' must start with ws:// or wss:// (or http:// for query)")
        return errors


@dataclass
class SignerConfig:
    key_path: str = "~/.quip-miner/signing.json"
    require_existing: bool = True

    def validate(self) -> List[str]:
        errors = []
        if not self.key_path:
            errors.append("Signer key_path cannot be empty")
        return errors


@dataclass
class SafetyConfig:
    max_memory_percent: float = 85.0
    max_runtime_minutes: int = 120
    max_cpu_workers: int = 2
    max_temperature_c: float = 72.0
    process_nice: int = 19

    def validate(self) -> List[str]:
        errors = []
        if not (0.0 < self.max_memory_percent <= 100.0):
            errors.append("max_memory_percent must be between 1 and 100")
        if self.max_cpu_workers < 1:
            errors.append("max_cpu_workers must be at least 1")
        if not (-20 <= self.process_nice <= 19):
            errors.append("process_nice must be between -20 and 19")
        return errors


@dataclass
class ParticipationConfig:
    provider: str = "miner_logs"  # "miner_logs", "telemetry", "substrate_events"
    journal_path: str = "data/participation.jsonl"
    daily_qblock_target: int = 10

    def validate(self) -> List[str]:
        errors = []
        if self.provider not in ("miner_logs", "telemetry", "substrate_events"):
            errors.append(f"Invalid participation provider '{self.provider}'")
        if not self.journal_path:
            errors.append("journal_path cannot be empty")
        return errors


@dataclass
class PointsConfig:
    public_p2p: bool = False
    public_api: bool = False
    tls: bool = False
    live_rpc: bool = False
    telemetry: bool = False
    dashboard: bool = True


@dataclass
class DashboardConfig:
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8080

    def validate(self) -> List[str]:
        errors = []
        if not (1024 <= self.port <= 65535):
            errors.append("Dashboard port must be between 1024 and 65535")
        return errors


@dataclass
class AppConfig:
    node: NodeConfig = field(default_factory=NodeConfig)
    miner: MinerConfig = field(default_factory=MinerConfig)
    rpc: RpcConfig = field(default_factory=RpcConfig)
    signer: SignerConfig = field(default_factory=SignerConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    participation: ParticipationConfig = field(default_factory=ParticipationConfig)
    points: PointsConfig = field(default_factory=PointsConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)

    def validate(self) -> List[str]:
        all_errors = []
        all_errors.extend(self.node.validate())
        all_errors.extend(self.miner.validate())
        all_errors.extend(self.rpc.validate())
        all_errors.extend(self.signer.validate())
        all_errors.extend(self.safety.validate())
        all_errors.extend(self.participation.validate())
        all_errors.extend(self.dashboard.validate())
        return all_errors
