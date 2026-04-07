import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.platform_login import PlatformLoginService


class PlatformLoginServiceTests(unittest.TestCase):
    def test_poll_session_returns_status_from_status_file(self) -> None:
        service = PlatformLoginService()
        with tempfile.TemporaryDirectory() as tempdir:
            status_file = Path(tempdir) / "xhs.json"
            status_file.write_text(
                json.dumps(
                    {
                        "status": "pending_scan",
                        "message": "二维码已生成",
                        "qrcode_data_url": "data:image/png;base64,abc",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            process = type("Proc", (), {"poll": lambda self: None})()
            service._sessions["xhs-1"] = type(
                "Session",
                (),
                {
                    "session_id": "xhs-1",
                    "platform": "xhs",
                    "process": process,
                    "status_file": status_file,
                    "started_at": 0.0,
                },
            )()
            payload = service.poll_session("xhs-1")
        self.assertEqual(payload["status"], "pending_scan")
        self.assertEqual(payload["qrcode_data_url"], "data:image/png;base64,abc")

    def test_start_session_rejects_unknown_platform(self) -> None:
        service = PlatformLoginService()
        with self.assertRaises(Exception):
            service.start_session("unknown")


if __name__ == "__main__":
    unittest.main()
