"""
Unit tests for configuration loading, TOML parsing, and validation models.
"""

import os
import tempfile
import unittest

from quip_android.config.loader import _parse_toml_minimal, format_toml, load_config
from quip_android.config.models import AppConfig


class TestConfig(unittest.TestCase):

    def test_default_config_loading(self):
        config = load_config("config.example.toml")
        self.assertIsInstance(config, AppConfig)
        self.assertEqual(config.node.network, "aglais")
        self.assertEqual(config.node.chain_id, "quip-testnet")
        self.assertIn("eco", ("eco", "daily", "performance"))
        self.assertTrue(len(config.rpc.endpoints) >= 3)
        self.assertTrue(all(ep.startswith("wss://") or ep.startswith("ws://") for ep in config.rpc.endpoints))

    def test_toml_parser_multiline_array(self):
        toml_content = """
[rpc]
endpoints = [
    "wss://bootnode-1.aglais.quip.network:20049/rpc",
    "wss://bootnode-2.aglais.quip.network:20049/rpc",
]
timeout_seconds = 6.5
retry_count = 3
"""
        parsed = _parse_toml_minimal(toml_content)
        self.assertIn("rpc", parsed)
        self.assertEqual(len(parsed["rpc"]["endpoints"]), 2)
        self.assertEqual(parsed["rpc"]["timeout_seconds"], 6.5)
        self.assertEqual(parsed["rpc"]["retry_count"], 3)

    def test_save_and_reload_config(self):
        config = load_config("config.example.toml")
        config.node.device_label = "Test-Device-Unit"
        config.miner.workers = 1

        with tempfile.NamedTemporaryFile("w+", suffix=".toml", delete=False) as tf:
            temp_path = tf.name

        try:
            from quip_android.config.loader import save_config
            save_config(config, temp_path)

            reloaded = load_config(temp_path)
            self.assertEqual(reloaded.node.device_label, "Test-Device-Unit")
            self.assertEqual(reloaded.miner.workers, 1)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
