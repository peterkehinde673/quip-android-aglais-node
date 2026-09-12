# quip-android-aglais-node

Unofficial low-power controller and monitor for running a compatible official quip-miner against the Aglais testnet.

## Current workflow

The controller now uses a config-driven workflow:

1. Select a healthy Aglais Substrate RPC.
2. Detect an installed official quip-miner.
3. Generate data/quip-miner.runtime.toml.
4. Validate it with resolve-modes or resolve-mode.
5. Launch quip-miner with --config and the selected backend mode.

The generated runtime config contains validators, signer_key, Aglais faucet_url, and a CPU backend section. This follows the current official direction where miner configuration is file-driven rather than assembled from legacy environment variables. citeturn0search0turn0search1turn0search3turn0search4

## Smallest Android setup

Ubuntu/PRoot is not required just to run this controller.

Android -> Termux -> Python virtual environment -> controller

In Termux:

    pkg update -y
    pkg install -y git python
    git clone https://github.com/peterkehinde673/quip-android-aglais-node.git
    cd quip-android-aglais-node
    bash scripts/termux-setup.sh
    bash scripts/install.sh
    bash scripts/run.sh doctor

The controller is lightweight, but real mining still requires a compatible official quip-miner runtime. The installer does not fake-install one. If the official miner cannot run in Termux, doctor/config validation should expose that before any mining process starts.

## Aglais defaults

- Chain id: quip_testnet
- Public RPC: wss://bootnode-{1,2,3}.aglais.quip.network:20049/rpc
- Faucet: https://faucet.aglais.quip.network
- CPU config: [cpu] with num_cpus
- Current config-driven schema uses backend binary selection such as quip-cpu-sa. citeturn0search0turn0search1turn0search4

## Eco mode

After doctor confirms a compatible miner and signer:

    bash scripts/run.sh start --mode eco --max-runtime 30

Eco mode clamps CPU mining to one worker and uses low process priority.

A short session does not guarantee participation points.

## Security

- Signing keys are never generated silently.
- Existing configs are preserved.
- Runtime configs are written with restrictive permissions where supported.
- TLS verification is not silently disabled.
- Infrastructure bonuses default to disabled.

## Limitations

This repository is not an official Quip validator and does not itself implement the Quip mining protocol. Local log evidence and local point estimates are not official account balances.
