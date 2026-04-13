import unittest
from unittest.mock import patch

from app.core.exceptions import NetworkError
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

    def test_start_session_forwards_uuid_cookie_when_loading_qrcode(self) -> None:
        service = WechatLoginService()
        opener = object()
        with patch.object(service, "_cleanup_expired_sessions"), patch.object(
            service, "_current_base_url", return_value="http://127.0.0.1:3000"
        ), patch.object(
            service, "_debug_key", return_value="debug-key"
        ), patch.object(
            service, "_saved_auth_key", return_value=""
        ), patch.object(
            service, "_fetch_debug_store", return_value={}
        ), patch.object(
            service, "_select_valid_auth_key", return_value=None
        ), patch.object(
            service, "_build_opener", return_value=opener
        ), patch.object(
            service,
            "_request_json_response",
            return_value=({"base_resp": {"ret": 0}}, ["uuid=test-uuid; Path=/; Secure; HttpOnly"]),
        ), patch.object(
            service, "_request_bytes", return_value=(b"png", "image/png")
        ) as request_bytes:
            payload = service.start_session()

        request_bytes.assert_called_once()
        self.assertEqual(request_bytes.call_args.kwargs["extra_headers"], {"Cookie": "uuid=test-uuid"})
        self.assertEqual(payload["status"], "pending_scan")
        self.assertEqual(payload["qrcode_revision"], 1)

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

    def test_poll_session_uses_saved_login_cookie_for_scan(self) -> None:
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
            login_cookie="uuid=test-uuid",
        )
        service._sessions[session.session_id] = session

        with patch.object(
            service,
            "_request_json",
            return_value={"base_resp": {"ret": 0}, "status": 0},
        ) as request_json:
            payload = service.poll_session("session-1")

        request_json.assert_called_once_with(
            session.opener,
            "http://127.0.0.1:3000/api/web/login/scan",
            extra_headers={"Cookie": "uuid=test-uuid"},
        )
        self.assertEqual(payload["status"], "pending_scan")

    def test_ensure_authkey_valid_requires_real_mp_profile(self) -> None:
        service = WechatLoginService()

        class DummyResponse:
            def __init__(self, payload: dict) -> None:
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self) -> bytes:
                import json

                return json.dumps(self.payload).encode("utf-8")

        with patch.object(
            service,
            "_open_with_retry",
            return_value=DummyResponse({"nick_name": "AI Insight", "head_img": "https://example.com/avatar.png"}),
        ):
            service._ensure_authkey_valid(object(), "http://127.0.0.1:3000", "auth-key")

        with patch.object(
            service,
            "_open_with_retry",
            return_value=DummyResponse({"nick_name": "", "head_img": ""}),
        ):
            with self.assertRaises(NetworkError) as context:
                service._ensure_authkey_valid(object(), "http://127.0.0.1:3000", "auth-key")
        self.assertEqual(context.exception.details["reason"], "auth_invalid")


if __name__ == "__main__":
    unittest.main()
