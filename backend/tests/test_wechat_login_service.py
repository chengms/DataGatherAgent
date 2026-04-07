import unittest
from unittest.mock import patch

from app.services.wechat_login import WechatLoginService, WechatLoginSession


class WechatLoginServiceTests(unittest.TestCase):
    def test_start_session_short_circuits_when_saved_auth_key_is_still_valid(self) -> None:
        service = WechatLoginService()
        with patch.object(service, "_cleanup_expired_sessions"), patch.object(
            service, "_current_base_url", return_value="http://127.0.0.1:3000"
        ), patch.object(
            service, "_debug_key", return_value="debug-key"
        ), patch.object(
            service, "_saved_auth_key", return_value="auth-key-1234"
        ), patch.object(
            service, "_auth_key_is_valid", return_value=True
        ):
            payload = service.start_session()
        self.assertEqual(payload["status"], "already_valid")
        self.assertIsNone(payload["session_id"])
        self.assertEqual(payload["auth_key_prefix"], "auth-key")

    def test_poll_session_completes_login_and_saves_auth_key(self) -> None:
        service = WechatLoginService()
        session = WechatLoginSession(
            session_id="session-1",
            upstream_sid="sid-1",
            opener=object(),
            base_url="http://127.0.0.1:3000",
            debug_key="debug-key",
            known_auth_keys=set(),
            qrcode_bytes=b"png",
            qrcode_content_type="image/png",
        )
        service._sessions[session.session_id] = session
        with patch.object(
            service,
            "_request_json",
            side_effect=[
                {"base_resp": {"ret": 0}, "status": 1},
                {},
            ],
        ), patch.object(
            service, "_get_cookie_value", return_value="saved-auth-key"
        ), patch.object(
            service, "_ensure_authkey_valid"
        ) as ensure_authkey_valid, patch.object(
            service, "_save_auth_key"
        ) as save_auth_key:
            payload = service.poll_session("session-1")
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["auth_key_prefix"], "saved-au")
        ensure_authkey_valid.assert_called_once()
        save_auth_key.assert_called_once_with("saved-auth-key")


if __name__ == "__main__":
    unittest.main()
