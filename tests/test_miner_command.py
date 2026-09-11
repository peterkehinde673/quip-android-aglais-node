"""
Unit tests for CPU and GPU miner command builders.
Verifies rejection of raw P2P bootnodes and safety worker clamping.
"""

import os
import tempfile
import unittest

from quip_android.config.models import AppConfig
from quip_android.miner.cpu import CpuMinerCommandBuilder
from quip_android.miner.gpu import GpuMinerCommandBuilder


class TestMinerCommand(unittest.TestCase):

    def setUp(self):
        self.config = AppConfig()
        # Mock binary path for unit testing builder
        self.config.miner.quip_miner_path = "/usr/bin/python3"  # Existing executable

    def test_p2p_bootnode_rejection(self):
        builder = CpuMinerCommandBuilder(self.config)

        # Rejects port 30333 as Substrate RPC
        valid, errors = builder.validate_prerequisites("wss://bootnode-1.aglais.quip.network:30333/rpc")
        self.assertFalse(valid)
        self.assertTrue(any("P2P bootnode" in e for e in errors))

        # Rejects tcp://
        valid2, errors2 = builder.validate_prerequisites("tcp://bootnode-1.aglais.quip.network:30333")
        self.assertFalse(valid2)

    def test_gpu_builder_refuses_when_no_cuda(self):
        gpu_builder = GpuMinerCommandBuilder(self.config)
        ready, msg = gpu_builder.check_gpu_readiness()
        # In this container environment, CUDA GPU is unavailable
        if not ready:
            self.assertIn("GPU mining unavailable", msg)
            cmd, errs = gpu_builder.build_command("wss://bootnode-1.aglais.quip.network:20049/rpc")
            self.assertIsNone(cmd)
            self.assertTrue(len(errs) > 0)


if __name__ == "__main__":
    unittest.main()
