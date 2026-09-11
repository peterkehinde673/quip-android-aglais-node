"""
Configuration loader and parser for quip-android-aglais-node.
Supports standard tomli/tomllib as well as a lightweight fallback TOML parser.
"""

import os
import re
import sys
from typing import Any, Dict, List, Optional

from quip_android.config.models import (
    AppConfig,
    DashboardConfig,
    MinerConfig,
    NodeConfig,
    ParticipationConfig,
    PointsConfig,
    RpcConfig,
    SafetyConfig,
    SignerConfig,
)
from quip_android.utils.logging import get_logger
from quip_android.utils.system import backup_file_before_overwrite, resolve_path

logger = get_logger("config")


def _parse_toml_minimal(text: str) -> Dict[str, Any]:
    """
    Lightweight, dependency-free TOML parser for standard table-based configurations.
    Handles sections [section], key = value (strings, booleans, ints, floats, multiline lists).
    """
    result: Dict[str, Any] = {}
    current_section: Dict[str, Any] = result

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith("#"):
            continue

        # Section header: [node] or [rpc]
        if line.startswith("[") and line.endswith("]"):
            section_name = line[1:-1].strip()
            if section_name not in result:
                result[section_name] = {}
            current_section = result[section_name]
            continue

        # Key = Value
        if "=" in line:
            key_part, val_part = line.split("=", 1)
            key = key_part.strip()
            val_str = val_part.strip()

            # Handle multiline arrays: val starts with '[' but doesn't end with ']'
            if val_str.startswith("[") and not val_str.endswith("]"):
                array_lines = [val_str]
                while i < len(lines):
                    next_line = lines[i].strip()
                    i += 1
                    # ignore full comment lines
                    if next_line.startswith("#"):
                        continue
                    # strip inline comment
                    if "#" in next_line and not (next_line.startswith('"') or next_line.startswith("'")):
                        next_line = next_line.split("#", 1)[0].strip()
                    array_lines.append(next_line)
                    if "]" in next_line:
                        break
                val_str = " ".join(array_lines)

            # Strip inline comments if not inside quotes
            if not (val_str.startswith('"') or val_str.startswith("[")):
                val_str = val_str.split("#", 1)[0].strip()

            # Parse value type
            parsed_val: Any = val_str
            if val_str.lower() in ("true", "yes"):
                parsed_val = True
            elif val_str.lower() in ("false", "no"):
                parsed_val = False
            elif val_str.startswith('"') and val_str.endswith('"'):
                parsed_val = val_str[1:-1]
            elif val_str.startswith("'") and val_str.endswith("'"):
                parsed_val = val_str[1:-1]
            elif val_str.startswith("[") and val_str.endswith("]"):
                inner = val_str[1:-1].strip()
                if not inner:
                    parsed_val = []
                else:
                    items = []
                    for raw_item in inner.split(","):
                        item = raw_item.strip().strip('"').strip("'").strip()
                        if item:
                            items.append(item)
                    parsed_val = items
            else:
                try:
                    if "." in val_str:
                        parsed_val = float(val_str)
                    else:
                        parsed_val = int(val_str)
                except ValueError:
                    parsed_val = val_str

            current_section[key] = parsed_val

    return result


def parse_toml(text: str) -> Dict[str, Any]:
    """Parse TOML using tomllib (3.11+), tomli (3.10-), or fallback minimal parser."""
    try:
        import tomllib  # Python 3.11+
        return tomllib.loads(text)
    except ImportError:
        pass

    try:
        import tomli  # Third-party library
        return tomli.loads(text)
    except ImportError:
        pass

    # Fallback minimal parser
    return _parse_toml_minimal(text)


def dict_to_app_config(d: Dict[str, Any]) -> AppConfig:
    """Instantiate AppConfig dataclasses from parsed dictionary."""
    config = AppConfig()

    if "node" in d and isinstance(d["node"], dict):
        nd = d["node"]
        config.node = NodeConfig(
            network=str(nd.get("network", config.node.network)),
            chain_id=str(nd.get("chain_id", config.node.chain_id)),
            mode=str(nd.get("mode", config.node.mode)),
            device_label=str(nd.get("device_label", config.node.device_label)),
        )

    if "miner" in d and isinstance(d["miner"], dict):
        md = d["miner"]
        workers = int(md.get("workers", config.miner.workers))
        max_rt = int(md.get("max_runtime_minutes", config.miner.max_runtime_minutes))
        extra_args = md.get("extra_args", config.miner.extra_args)
        if isinstance(extra_args, str):
            extra_args = [extra_args]
        config.miner = MinerConfig(
            backend=str(md.get("backend", config.miner.backend)),
            workers=workers,
            max_runtime_minutes=max_rt,
            quip_miner_path=str(md.get("quip_miner_path", config.miner.quip_miner_path)),
            extra_args=list(extra_args),
        )

    if "rpc" in d and isinstance(d["rpc"], dict):
        rd = d["rpc"]
        endpoints = rd.get("endpoints", config.rpc.endpoints)
        if isinstance(endpoints, str):
            endpoints = [endpoints]
        config.rpc = RpcConfig(
            endpoints=list(endpoints),
            timeout_seconds=float(rd.get("timeout_seconds", config.rpc.timeout_seconds)),
            retry_interval_seconds=float(rd.get("retry_interval_seconds", config.rpc.retry_interval_seconds)),
            require_chain_match=bool(rd.get("require_chain_match", config.rpc.require_chain_match)),
        )

    if "signer" in d and isinstance(d["signer"], dict):
        sd = d["signer"]
        config.signer = SignerConfig(
            key_path=str(sd.get("key_path", config.signer.key_path)),
            require_existing=bool(sd.get("require_existing", config.signer.require_existing)),
        )

    if "safety" in d and isinstance(d["safety"], dict):
        sfd = d["safety"]
        config.safety = SafetyConfig(
            max_memory_percent=float(sfd.get("max_memory_percent", config.safety.max_memory_percent)),
            max_runtime_minutes=int(sfd.get("max_runtime_minutes", config.safety.max_runtime_minutes)),
            max_cpu_workers=int(sfd.get("max_cpu_workers", config.safety.max_cpu_workers)),
            max_temperature_c=float(sfd.get("max_temperature_c", config.safety.max_temperature_c)),
            process_nice=int(sfd.get("process_nice", config.safety.process_nice)),
        )

    if "participation" in d and isinstance(d["participation"], dict):
        pd = d["participation"]
        config.participation = ParticipationConfig(
            provider=str(pd.get("provider", config.participation.provider)),
            journal_path=str(pd.get("journal_path", config.participation.journal_path)),
            daily_qblock_target=int(pd.get("daily_qblock_target", config.participation.daily_qblock_target)),
        )

    if "points" in d and isinstance(d["points"], dict):
        ptd = d["points"]
        config.points = PointsConfig(
            public_p2p=bool(ptd.get("public_p2p", config.points.public_p2p)),
            public_api=bool(ptd.get("public_api", config.points.public_api)),
            tls=bool(ptd.get("tls", config.points.tls)),
            live_rpc=bool(ptd.get("live_rpc", config.points.live_rpc)),
            telemetry=bool(ptd.get("telemetry", config.points.telemetry)),
            dashboard=bool(ptd.get("dashboard", config.points.dashboard)),
        )

    if "dashboard" in d and isinstance(d["dashboard"], dict):
        dbd = d["dashboard"]
        config.dashboard = DashboardConfig(
            enabled=bool(dbd.get("enabled", config.dashboard.enabled)),
            host=str(dbd.get("host", config.dashboard.host)),
            port=int(dbd.get("port", config.dashboard.port)),
        )

    return config


def app_config_to_dict(config: AppConfig) -> Dict[str, Any]:
    """Convert AppConfig object to nested dictionary."""
    return {
        "node": {
            "network": config.node.network,
            "chain_id": config.node.chain_id,
            "mode": config.node.mode,
            "device_label": config.node.device_label,
        },
        "miner": {
            "backend": config.miner.backend,
            "workers": config.miner.workers,
            "max_runtime_minutes": config.miner.max_runtime_minutes,
            "quip_miner_path": config.miner.quip_miner_path,
            "extra_args": config.miner.extra_args,
        },
        "rpc": {
            "endpoints": config.rpc.endpoints,
            "timeout_seconds": config.rpc.timeout_seconds,
            "retry_interval_seconds": config.rpc.retry_interval_seconds,
            "require_chain_match": config.rpc.require_chain_match,
        },
        "signer": {
            "key_path": config.signer.key_path,
            "require_existing": config.signer.require_existing,
        },
        "safety": {
            "max_memory_percent": config.safety.max_memory_percent,
            "max_runtime_minutes": config.safety.max_runtime_minutes,
            "max_cpu_workers": config.safety.max_cpu_workers,
            "max_temperature_c": config.safety.max_temperature_c,
            "process_nice": config.safety.process_nice,
        },
        "participation": {
            "provider": config.participation.provider,
            "journal_path": config.participation.journal_path,
            "daily_qblock_target": config.participation.daily_qblock_target,
        },
        "points": {
            "public_p2p": config.points.public_p2p,
            "public_api": config.points.public_api,
            "tls": config.points.tls,
            "live_rpc": config.points.live_rpc,
            "telemetry": config.points.telemetry,
            "dashboard": config.points.dashboard,
        },
        "dashboard": {
            "enabled": config.dashboard.enabled,
            "host": config.dashboard.host,
            "port": config.dashboard.port,
        },
    }


def format_toml(d: Dict[str, Any]) -> str:
    """Format dictionary as clean TOML text."""
    lines = []
    lines.append("# quip-android-aglais-node configuration")
    lines.append("# Generated automatically - edit values as needed\n")

    for section, values in d.items():
        lines.append(f"[{section}]")
        if isinstance(values, dict):
            for k, v in values.items():
                if isinstance(v, bool):
                    lines.append(f"{k} = {str(v).lower()}")
                elif isinstance(v, (int, float)):
                    lines.append(f"{k} = {v}")
                elif isinstance(v, list):
                    items_str = ", ".join(f'"{item}"' for item in v)
                    lines.append(f"{k} = [{items_str}]")
                else:
                    lines.append(f'{k} = "{v}"')
        lines.append("")

    return "\n".join(lines)


def load_config(path: Optional[str] = None) -> AppConfig:
    """
    Load AppConfig from specified path or standard candidate paths.
    Searches:
    1. Explicit path if provided
    2. config.toml
    3. ~/.quip-android/config.toml
    4. config.example.toml (fallback with warning)
    """
    candidates = []
    if path:
        candidates.append(resolve_path(path))
    candidates.extend([
        resolve_path("./config.toml"),
        resolve_path("~/.quip-android/config.toml"),
        resolve_path("./config.example.toml"),
    ])

    for candidate in candidates:
        if os.path.isfile(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    content = f.read()
                parsed = parse_toml(content)
                config = dict_to_app_config(parsed)
                errors = config.validate()
                if errors:
                    logger.warning("Configuration warnings in %s: %s", candidate, "; ".join(errors))
                logger.info("Loaded configuration from %s", candidate)
                return config
            except Exception as err:
                logger.error("Failed to parse config file %s: %s", candidate, err)

    logger.info("No configuration file found; using default Eco configuration")
    return AppConfig()


def save_config(config: AppConfig, path: str = "config.toml", backup: bool = True) -> str:
    """
    Save AppConfig to path. If backup=True and destination exists,
    creates a timestamped backup before writing.
    """
    resolved = resolve_path(path)
    os.makedirs(os.path.dirname(resolved) or ".", exist_ok=True)

    if backup and os.path.exists(resolved):
        bak = backup_file_before_overwrite(resolved)
        if bak:
            logger.info("Created configuration backup: %s", bak)

    d = app_config_to_dict(config)
    toml_str = format_toml(d)

    with open(resolved, "w", encoding="utf-8") as f:
        f.write(toml_str)

    logger.info("Saved configuration to %s", resolved)
    return resolved
