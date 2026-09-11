"""
Command Line Interface (CLI) for quip-android-aglais-node.
Provides status, doctor, rpc-check, start, stop, logs, hardware, config, participation, and keygen.
"""

import argparse
import os
import sys
import time
from typing import List, Optional

from quip_android import __chain__, __network__, __version__
from quip_android.config.loader import app_config_to_dict, format_toml, load_config, save_config
from quip_android.config.models import AppConfig
from quip_android.miner.controller import MinerController
from quip_android.monitoring.hardware import get_hardware_profile
from quip_android.monitoring.resources import ResourceMonitor
from quip_android.rpc.health import check_endpoint_health
from quip_android.rpc.manager import RpcManager
from quip_android.utils.logging import get_logger, setup_logger
from quip_android.utils.system import detect_android_proot, find_quip_miner_binary, resolve_path

logger = setup_logger()


def run_doctor(config: AppConfig) -> int:
    """Execute complete system doctor diagnostics."""
    print("=" * 60)
    print("QUIP ANDROID NODE DOCTOR")
    print(f"Controller Version: v{__version__} | Target Network: {__network__}")
    print("=" * 60)

    issues = 0

    # 1. Python version
    py_ver = sys.version.split()[0]
    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 9):
        print(f"Environment:\n  ✓ Python {py_ver} (supported)")
    else:
        print(f"Environment:\n  ✗ Python {py_ver} is too old (requires 3.9+)")
        issues += 1

    # 2. Virtual environment
    in_venv = (sys.prefix != getattr(sys, "base_prefix", sys.prefix)) or ("VIRTUAL_ENV" in os.environ)
    if in_venv:
        print("  ✓ Virtual environment active")
    else:
        print("  ⚠ Running outside virtual environment (recommended: source .quip/bin/activate)")

    # 3. Environment & OS
    is_android, is_proot, env_desc = detect_android_proot()
    print(f"  ✓ Platform detected: {env_desc}")

    # 4. Quip Miner Binary
    print("\nQuip Miner:")
    binary_path, bin_info = find_quip_miner_binary(config.miner.quip_miner_path)
    if binary_path:
        print(f"  ✓ quip-miner binary found at: {binary_path}")
        print(f"  ✓ Version: {bin_info}")
    else:
        print("  ✗ quip-miner binary not found")
        print("    Searched standard paths (~/.quip/bin, /root/quip-android-node/.quip/bin, PATH)")
        print("    Configure [miner.quip_miner_path] in config.toml once compiled.")
        issues += 1

    # 5. Hardware Profile
    print("\nHardware:")
    hw = get_hardware_profile(config.node.device_label)
    if hw.cpu.is_supported:
        print(f"  ✓ CPU: {hw.cpu.architecture} ({hw.cpu.core_count} cores, {hw.cpu.model_name})")
    else:
        print(f"  ⚠ CPU architecture {hw.cpu.architecture} may have limited support")

    if hw.gpu.cuda_available:
        print(f"  ✓ GPU: {hw.gpu.status_message}")
    else:
        print(f"  ⚠ GPU: {hw.gpu.status_message}")

    # 6. Resources
    print("\nResources:")
    mon = ResourceMonitor()
    snap = mon.snapshot()
    print(f"  ✓ RAM: {snap.memory_used_mb:.0f}MB / {snap.memory_total_mb:.0f}MB ({snap.memory_percent:.1f}% used, {snap.memory_available_mb:.0f}MB free)")
    print(f"  ✓ Disk: {snap.disk_free_gb:.1f} GB available ({snap.disk_percent:.1f}% used)")
    print(f"  • Battery: {snap.battery_status}")
    print(f"  • Thermal: {snap.temperature_status}")

    # 7. Signer Key Check
    print("\nSigner Key:")
    key_path = resolve_path(config.signer.key_path)
    if os.path.isfile(key_path):
        print(f"  ✓ Existing signer key found: {key_path}")
    else:
        print(f"  ⚠ No signer key found at {key_path}")
        print("    Run 'quip-android keygen' to generate one, or specify --signer-key <path>")

    # 8. RPC Connectivity & Identity
    print("\nNetwork & Substrate RPC:")
    rpc_mgr = RpcManager(config.rpc, config.node.chain_id)
    results = rpc_mgr.check_all()
    healthy_count = sum(1 for r in results.values() if r.is_healthy)

    for ep, res in results.items():
        if res.is_healthy:
            print(f"  ✓ {ep} healthy ({res.latency_ms:.1f}ms, chain={res.chain_name}, peers={res.peers})")
        else:
            print(f"  ✗ {ep} ({res.error_message})")

    if healthy_count == 0:
        print("  ✗ No healthy candidate Substrate RPC endpoints could be verified!")
        issues += 1

    # 9. Final Readiness
    print("\n" + "=" * 60)
    if issues == 0 and os.path.isfile(key_path):
        print("STATUS: READY FOR MINING (Eco / Daily / Performance)")
    elif issues == 0:
        print("STATUS: READY FOR SIGNER KEY CONFIGURATION")
    else:
        print(f"STATUS: {issues} issue(s) require attention before mining")
    print("=" * 60)

    return 0 if issues == 0 else 1


def run_rpc_check(config: AppConfig) -> int:
    """Test candidate RPC endpoints and print health details."""
    print(f"Checking Substrate RPC endpoints for network: {config.node.network} ({config.node.chain_id})...\n")
    rpc_mgr = RpcManager(config.rpc, config.node.chain_id)
    results = rpc_mgr.check_all(force=True)

    for ep, res in results.items():
        status_icon = "✓" if res.is_healthy else "✗"
        print(f"{status_icon} Endpoint: {ep}")
        print(f"    DNS Resolved: {'Yes (' + str(res.ip_address) + ')' if res.dns_resolved else 'No'}")
        print(f"    TCP Connected: {'Yes' if res.tcp_connected else 'No'}")
        print(f"    WebSocket RPC: {'Yes' if res.ws_connected else 'No'}")
        if res.is_healthy:
            print(f"    Chain Name:    {res.chain_name}")
            print(f"    Node Version:  {res.node_version or 'unknown'}")
            print(f"    Peers:         {res.peers}")
            print(f"    Latency:       {res.latency_ms:.1f} ms")
        else:
            print(f"    Error:         {res.error_message}")
        print()

    active = rpc_mgr.select_healthy_endpoint()
    if active:
        print(f"Active Selected RPC: {active}")
        return 0
    else:
        print("Error: No healthy Substrate RPC endpoints available.")
        return 1


def run_status(config: AppConfig) -> int:
    """Display comprehensive node status report."""
    controller = MinerController(config)
    status = controller.get_status()

    node = status["node"]
    miner = status["miner"]
    rpc = status["rpc"]
    hw = status["hardware"]
    res = status["resources"]
    part = status["participation"]
    pts = status["points"]
    safety = status["safety"]

    print("=" * 60)
    print("NODE STATUS")
    print("=" * 60)
    print(f"Network:                   {node['network']} ({node['chain_id']})")
    print(f"Operating Mode:            {node['mode'].upper()}")
    print(f"Device:                    {node['device']} ({node['environment']})")
    print("-" * 60)
    print(f"Active RPC:                {rpc['active_endpoint']}")
    print(f"Miner Status:              {miner['status']}")
    print(f"Process PID:               {miner['pid'] or 'None'}")
    print(f"CPU Workers:               {miner['workers']}")
    print(f"GPU Capability:            {'Available' if hw['gpu_available'] else 'Unavailable'}")
    print(f"Session Runtime:           {miner['runtime_minutes']:.1f} minutes")
    print("-" * 60)
    print(f"CPU Usage:                 {res['cpu_percent']:.1f}% ({hw['cpu_cores']} cores, {hw['cpu_arch']})")
    print(f"Memory Usage:              {res['memory_percent']:.1f}% ({res['memory_used_mb']:.0f}MB / {res['memory_available_mb']:.0f}MB free)")
    print(f"Disk Available:            {res['disk_free_gb']:.1f} GB ({res['disk_percent']:.1f}% used)")
    print(f"Battery:                   {res['battery']}")
    print(f"Temperature:               {res['temperature']}")
    print("-" * 60)
    print(f"Today's Verified Qblocks:  {part['today_verified_qblocks']}")
    print(f"Qblock Wins:               {part['today_wins']}")
    print(f"Latest Event:              {part['status_message']}")
    print("-" * 60)
    print(f"Estimated Points:          {pts['total_estimated_points']} (Base: {pts['base_participation_points']}, Wins: {pts['win_points']})")
    print(f"Points Label:              {pts['disclaimer']}")
    print("-" * 60)
    print(f"Safety Status:             {safety['status'].upper()}")
    if safety["reasons"]:
        print(f"Safety Notes:              {'; '.join(safety['reasons'])}")
    print("=" * 60)
    return 0


def run_hardware(config: AppConfig) -> int:
    """Display detailed hardware profile."""
    hw = get_hardware_profile(config.node.device_label)
    print("=" * 60)
    print(f"HARDWARE PROFILE: {hw.device_label}")
    print("=" * 60)
    print(f"Environment:     {hw.environment_desc}")
    print(f"Android Host:    {'Yes' if hw.is_android else 'No'}")
    print(f"PRoot Container: {'Yes' if hw.is_proot else 'No'}")
    print(f"CPU Arch:        {hw.cpu.architecture}")
    print(f"CPU Model:       {hw.cpu.model_name}")
    print(f"CPU Cores:       {hw.cpu.core_count}")
    print(f"Total RAM:       {hw.total_memory_mb:.0f} MB")
    print(f"GPU CUDA:        {'Available' if hw.gpu.cuda_available else 'Unavailable'}")
    print(f"GPU Details:     {hw.gpu.status_message}")
    print("=" * 60)
    return 0


def run_keygen(config: AppConfig, output_path: Optional[str] = None) -> int:
    """Safely and explicitly generate a new Quip signing key using quip-miner keygen."""
    target_path = resolve_path(output_path or config.signer.key_path)

    print("=" * 60)
    print("EXPLICIT SIGNER KEY GENERATION")
    print("=" * 60)

    if os.path.exists(target_path):
        print(f"CRITICAL WARNING: A key file already exists at '{target_path}'!")
        print("To protect against accidental key loss, this tool WILL NEVER overwrite an existing key silently.")
        print("If you wish to replace it, please backup and delete or rename the old key manually.")
        return 1

    binary_path, _ = find_quip_miner_binary(config.miner.quip_miner_path)
    if not binary_path:
        print("Error: quip-miner binary not found. Cannot generate key.")
        return 1

    os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
    print(f"Target keystore path: {target_path}")
    print("Invoking official: quip-miner keygen ...")

    import subprocess
    try:
        res = subprocess.run(
            [binary_path, "keygen", "--out", target_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
        )
        if res.returncode == 0:
            print(f"✓ Key generated successfully and saved to: {target_path}")
            return 0
        else:
            print(f"Error generating key: {res.stderr or res.stdout}")
            return 1
    except Exception as err:
        print(f"Failed to execute quip-miner keygen: {err}")
        return 1


def run_start(args: argparse.Namespace, config: AppConfig) -> int:
    """Start the node/miner session."""
    controller = MinerController(config)
    mode = args.mode or config.node.mode
    workers = args.workers
    signer_key = args.signer_key
    max_runtime = args.max_runtime

    print(f"Initiating Quip miner session in {mode.upper()} mode...")
    success, message = controller.start(
        mode=mode,
        custom_workers=workers,
        custom_signer_key=signer_key,
        max_runtime_minutes=max_runtime,
    )

    if not success:
        print(f"Failed to start: {message}")
        return 1

    print(f"✓ {message}")
    print(f"Session log: {controller.miner_process.session_log_path if controller.miner_process else 'logs/'}")
    print("Press Ctrl+C to safely shut down miner.")

    try:
        while controller.miner_process and controller.miner_process.is_running:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nCtrl+C detected. Initiating clean miner shutdown...")
        controller.stop(reason="User Ctrl+C interrupt")
        print("✓ Miner process cleanly stopped.")

    return 0


def run_dashboard(args: argparse.Namespace, config: AppConfig) -> int:
    """Launch the lightweight local web dashboard."""
    from quip_android.dashboard.app import start_local_dashboard
    host = args.host or config.dashboard.host
    port = args.port or config.dashboard.port
    print(f"Starting local dashboard at http://{host}:{port}/ ...")
    start_local_dashboard(config=config, host=host, port=port)
    return 0


def main(args_list: Optional[List[str]] = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="quip-android",
        description="Android-friendly Quip Network Aglais Testnet node & miner smart controller.",
    )
    parser.add_argument("--config", "-c", type=str, default=None, help="Path to custom config.toml")
    parser.add_argument("--version", "-v", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # doctor
    subparsers.add_parser("doctor", help="Run system, network, binary, and environment checks")

    # rpc-check
    subparsers.add_parser("rpc-check", help="Test candidate Substrate RPC endpoints for Aglais")

    # status
    subparsers.add_parser("status", help="Show live node, miner, hardware, and participation status")

    # hardware
    subparsers.add_parser("hardware", help="Show hardware and GPU detection details")

    # start
    start_parser = subparsers.add_parser("start", help="Start mining session")
    start_parser.add_argument("--mode", "-m", choices=["eco", "daily", "performance"], help="Operating mode")
    start_parser.add_argument("--workers", "-w", type=int, help="CPU worker count")
    start_parser.add_argument("--signer-key", "-k", type=str, help="Path to signing key file")
    start_parser.add_argument("--max-runtime", "-r", type=int, help="Max runtime in minutes")

    # stop
    subparsers.add_parser("stop", help="Stop running miner process")

    # logs
    logs_parser = subparsers.add_parser("logs", help="View recent miner session logs")
    logs_parser.add_argument("--lines", "-n", type=int, default=30, help="Number of lines to show")

    # participation
    subparsers.add_parser("participation", help="Display verified participation and win journal records")

    # keygen
    keygen_parser = subparsers.add_parser("keygen", help="Explicitly generate a new Quip signing key")
    keygen_parser.add_argument("--output", "-o", type=str, help="Output path for signing key")

    # dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Start local web dashboard on phone")
    dash_parser.add_argument("--host", type=str, help="Host to bind")
    dash_parser.add_argument("--port", "-p", type=int, help="Port to bind")

    # config
    cfg_parser = subparsers.add_parser("config", help="Manage configuration")
    cfg_parser.add_argument("--show", action="store_true", help="Print current configuration")
    cfg_parser.add_argument("--init", action="store_true", help="Initialize config.toml from example")

    parsed_args = parser.parse_args(args_list)

    if not parsed_args.command:
        parser.print_help()
        return 0

    config = load_config(parsed_args.config)

    if parsed_args.command == "doctor":
        return run_doctor(config)
    elif parsed_args.command == "rpc-check":
        return run_rpc_check(config)
    elif parsed_args.command == "status":
        return run_status(config)
    elif parsed_args.command == "hardware":
        return run_hardware(config)
    elif parsed_args.command == "start":
        return run_start(parsed_args, config)
    elif parsed_args.command == "stop":
        # Check PID file in logs
        pid_file = "logs/miner.pid"
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                import signal
                os.kill(pid, signal.SIGTERM)
                print(f"Sent SIGTERM to miner PID {pid}")
                return 0
            except Exception as e:
                print(f"Could not stop miner: {e}")
                return 1
        else:
            print("No active miner process PID found.")
            return 0
    elif parsed_args.command == "logs":
        log_dir = "logs"
        if not os.path.exists(log_dir):
            print("No logs directory found.")
            return 0
        log_files = sorted(
            [os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.startswith("miner_") and f.endswith(".log")],
            reverse=True,
        )
        if not log_files:
            print("No miner session logs found in logs/.")
            return 0
        latest = log_files[0]
        print(f"--- Latest Session Log: {latest} ---")
        try:
            with open(latest, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            for line in lines[-parsed_args.lines:]:
                print(line.rstrip())
        except Exception as e:
            print(f"Error reading log file: {e}")
        return 0
    elif parsed_args.command == "participation":
        from quip_android.participation.records import ParticipationJournal
        j = ParticipationJournal(config.participation.journal_path)
        summary = j.get_summary()
        entries = j.get_entries(limit=20)
        print("=" * 60)
        print("PARTICIPATION EVIDENCE JOURNAL")
        print("=" * 60)
        print(f"Today's Verified Qblocks:  {summary.today_verified_qblocks}")
        print(f"Today's Qblock Wins:       {summary.today_wins}")
        print(f"Lifetime Qblocks:          {summary.total_lifetime_qblocks}")
        print(f"Lifetime Wins:             {summary.total_lifetime_wins}")
        print(f"Status:                    {summary.status_message}")
        print("-" * 60)
        print("Recent Evidence Entries (latest 20):")
        if not entries:
            print("  (No participation events recorded yet)")
        for e in entries:
            print(f"  [{e.timestamp}] QBlock: {e.qblock_id or 'none'} | Status: {e.participation_status} | Win: {e.win_status} | Source: {e.evidence_source}")
        print("=" * 60)
        return 0
    elif parsed_args.command == "keygen":
        return run_keygen(config, parsed_args.output)
    elif parsed_args.command == "dashboard":
        return run_dashboard(parsed_args, config)
    elif parsed_args.command == "config":
        if parsed_args.init:
            save_config(config, "config.toml")
            print("✓ Generated config.toml from current settings.")
            return 0
        elif parsed_args.show:
            d = app_config_to_dict(config)
            print(format_toml(d))
            return 0
        else:
            cfg_parser.print_help()
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
