import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "scripts"))

import manage_services  # noqa: E402


class ManageServicesTests(unittest.TestCase):
    def test_missing_required_env_raises_clear_error(self) -> None:
        service = {"name": "wechat_exporter", "required_env": ["WECHAT_EXPORTER_API_KEY"]}
        with self.assertRaises(RuntimeError) as context:
            manage_services.ensure_required_env(service, {})
        self.assertIn("services.local.example.json", str(context.exception))

    def test_missing_required_binary_raises_error(self) -> None:
        service = {"name": "backend", "requires": ["python", "missing-tool"]}
        with patch("manage_services.shutil.which") as which:
            which.side_effect = lambda name: None if name == "missing-tool" else "/usr/bin/python"
            with self.assertRaises(RuntimeError) as context:
                manage_services.ensure_required_binaries(service)
        self.assertIn("missing-tool", str(context.exception))

    def test_port_check_detects_busy_port(self) -> None:
        with patch("manage_services.socket.socket") as socket_cls:
            socket_instance = socket_cls.return_value.__enter__.return_value
            socket_instance.connect_ex.return_value = 0
            self.assertTrue(manage_services.is_port_in_use(8000))


if __name__ == "__main__":
    unittest.main()
