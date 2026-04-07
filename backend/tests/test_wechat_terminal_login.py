import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "scripts"))

import wechat_terminal_login  # noqa: E402


class WechatTerminalLoginTests(unittest.TestCase):
    def test_fetch_debug_store_retries_transient_503(self) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"abc":{"token":"123"}}'

        http_error = urllib.error.HTTPError(
            url="http://127.0.0.1:3000/api/_debug?key=x",
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=None,
        )
        mock_opener = type("MockOpener", (), {})()
        mock_opener.open = unittest.mock.Mock(side_effect=[http_error, FakeResponse()])
        with patch("wechat_terminal_login.time.sleep") as sleep, patch(
            "wechat_terminal_login.time.time",
            side_effect=[0.0, 0.5],
        ):
            store = wechat_terminal_login.fetch_debug_store(mock_opener, "http://127.0.0.1:3000", "x")
        self.assertEqual(store, {"abc": {"token": "123"}})
        sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
