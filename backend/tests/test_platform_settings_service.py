import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import platform_settings


class PlatformSettingsServiceTests(unittest.TestCase):
    def test_get_settings_reads_defaults_from_example(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            example = temp_root / "services.local.example.json"
            local = temp_root / "services.local.json"
            example.write_text('{"global_env": {}, "services": {}}\n', encoding="utf-8")
            with patch.object(platform_settings, "LOCAL_EXAMPLE_PATH", example), patch.object(platform_settings, "LOCAL_OVERRIDE_PATH", local):
                payload = platform_settings.get_mediacrawler_settings()
        self.assertEqual(payload["browser_mode"], "safe")
        self.assertTrue(payload["browser_headless"])
        self.assertEqual(payload["max_sleep_sec"], 4)
        self.assertEqual(payload["max_concurrency"], 1)

    def test_update_settings_persists_global_env_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            example = temp_root / "services.local.example.json"
            local = temp_root / "services.local.json"
            example.write_text('{"global_env": {}, "services": {}}\n', encoding="utf-8")
            with patch.object(platform_settings, "LOCAL_EXAMPLE_PATH", example), patch.object(platform_settings, "LOCAL_OVERRIDE_PATH", local):
                payload = platform_settings.update_mediacrawler_settings(
                    {
                        "browser_mode": "cdp",
                        "browser_headless": False,
                        "max_sleep_sec": 7,
                        "max_concurrency": 2,
                        "browser_path": "C:/Chrome/chrome.exe",
                    }
                )
                saved = json.loads(local.read_text(encoding="utf-8"))
        self.assertEqual(payload["browser_mode"], "cdp")
        self.assertFalse(payload["browser_headless"])
        self.assertEqual(saved["global_env"]["DATA_GATHER_BROWSER_MODE"], "cdp")
        self.assertEqual(saved["global_env"]["DATA_GATHER_BROWSER_HEADLESS"], "false")
        self.assertEqual(saved["global_env"]["DATA_GATHER_CRAWLER_MAX_SLEEP_SEC"], "7")
        self.assertEqual(saved["global_env"]["DATA_GATHER_CRAWLER_MAX_CONCURRENCY"], "2")

    def test_build_runtime_args_reflect_current_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            example = temp_root / "services.local.example.json"
            local = temp_root / "services.local.json"
            example.write_text(
                '{"global_env": {"DATA_GATHER_BROWSER_MODE": "standard", "DATA_GATHER_BROWSER_HEADLESS": "true", "DATA_GATHER_CRAWLER_MAX_SLEEP_SEC": "5", "DATA_GATHER_CRAWLER_MAX_CONCURRENCY": "1", "DATA_GATHER_BROWSER_PATH": ""}, "services": {}}\n',
                encoding="utf-8",
            )
            with patch.object(platform_settings, "LOCAL_EXAMPLE_PATH", example), patch.object(platform_settings, "LOCAL_OVERRIDE_PATH", local):
                args = platform_settings.build_mediacrawler_runtime_cli_args()
        self.assertEqual(
            args,
            [
                "--browser-mode",
                "standard",
                "--headless",
                "true",
                "--max-sleep-sec",
                "5",
                "--max-concurrency",
                "1",
                "--browser-path",
                "",
            ],
        )


if __name__ == "__main__":
    unittest.main()
