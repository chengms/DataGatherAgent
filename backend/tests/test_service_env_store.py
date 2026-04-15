import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "scripts"))

import service_env_store  # noqa: E402


class ServiceEnvStoreTests(unittest.TestCase):
    def test_set_global_env_creates_local_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            example = temp_root / "services.local.example.json"
            local = temp_root / "services.local.json"
            example.write_text('{"global_env": {}, "services": {}}\n', encoding="utf-8")
            with patch.object(service_env_store, "LOCAL_EXAMPLE_PATH", example), patch.object(
                service_env_store, "LOCAL_OVERRIDE_PATH", local
            ):
                service_env_store.set_global_env("WECHAT_EXPORTER_API_KEY", "demo-key")
            payload = local.read_text(encoding="utf-8")
            self.assertIn("WECHAT_EXPORTER_API_KEY", payload)
            self.assertIn("demo-key", payload)

    def test_set_service_env_creates_nested_service_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            example = temp_root / "services.local.example.json"
            local = temp_root / "services.local.json"
            example.write_text('{"global_env": {}, "services": {}}\n', encoding="utf-8")
            with patch.object(service_env_store, "LOCAL_EXAMPLE_PATH", example), patch.object(
                service_env_store, "LOCAL_OVERRIDE_PATH", local
            ):
                service_env_store.set_service_env("mediacrawler_xhs", "XHS_MEDIACRAWLER_COOKIES", "a=1")
            payload = local.read_text(encoding="utf-8")
            self.assertIn("mediacrawler_xhs", payload)
            self.assertIn("XHS_MEDIACRAWLER_COOKIES", payload)
            self.assertIn("a=1", payload)


if __name__ == "__main__":
    unittest.main()
