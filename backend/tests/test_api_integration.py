import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib import error, request


BACKEND_DIR = Path(__file__).resolve().parents[1]


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.tempdir.name) / "integration.sqlite3"
        cls.port = find_free_port()
        env = os.environ.copy()
        env["DATA_GATHER_DB_PATH"] = str(cls.db_path)
        cls.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(cls.port),
            ],
            cwd=BACKEND_DIR,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls.wait_for_server()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.process.terminate()
        try:
            cls.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.process.kill()
        cls.tempdir.cleanup()

    @classmethod
    def wait_for_server(cls) -> None:
        deadline = time.time() + 20
        last_error = None
        while time.time() < deadline:
            try:
                payload = cls.get_json("/health")
                if payload["status"] == "ok":
                    return
            except Exception as exc:  # pragma: no cover - polling helper
                last_error = exc
                time.sleep(0.25)
        raise RuntimeError(f"server did not start: {last_error}")

    @classmethod
    def build_url(cls, path: str) -> str:
        return f"http://127.0.0.1:{cls.port}{path}"

    @classmethod
    def get_json(cls, path: str):
        with request.urlopen(cls.build_url(path), timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    @classmethod
    def post_json(cls, path: str, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            cls.build_url(path),
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(http_request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    @classmethod
    def get_error_json(cls, path: str):
        try:
            with request.urlopen(cls.build_url(path), timeout=15) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_root_page_is_served(self) -> None:
        with request.urlopen(self.build_url("/"), timeout=15) as response:
            html = response.read().decode("utf-8")
        self.assertIn("数据采集工作台", html)
        self.assertIn("/assets/app.js", html)

    def test_health_and_sources(self) -> None:
        health = self.get_json("/health")
        sources = self.get_json("/api/discovery/sources")
        self.assertEqual(health["status"], "ok")
        self.assertEqual(len(sources), 7)
        self.assertEqual({item["kind"] for item in sources}, {"search", "fetch"})
        self.assertEqual({item["platform"] for item in sources}, {"wechat", "xiaohongshu"})
        self.assertTrue(any(item["name"] == "web_fetch_wechat" and item["live"] for item in sources))
        self.assertTrue(any(item["name"] == "wechat_exporter_fetch" and item["live"] for item in sources))
        self.assertTrue(any(item["name"] == "xiaohongshu_external_search" for item in sources))

    def test_preview_and_job_queries(self) -> None:
        preview = self.post_json(
            "/api/workflows/preview",
            {
                "keywords": ["AI Agent", "Semiconductor"],
                "discovery_source": "mock_wechat_search",
                "fetch_source": "mock_wechat_fetch",
                "limit": 3,
                "top_k": 2,
                "fallback_to_mock": True,
            },
        )
        self.assertEqual(preview["discovered_count"], 6)
        self.assertEqual(preview["fetched_count"], 6)
        self.assertEqual(preview["ranked_count"], 2)
        self.assertEqual(len(preview["hot_articles"]), 2)

        jobs = self.get_json("/api/workflows/jobs")
        self.assertGreaterEqual(len(jobs), 1)
        detail = self.get_json(f"/api/workflows/jobs/{preview['job_id']}")
        self.assertEqual(detail["job"]["status"], "success")
        self.assertEqual(len(detail["hot_articles"]), 2)

    def test_missing_job_returns_structured_not_found(self) -> None:
        status_code, payload = self.get_error_json("/api/workflows/jobs/999999")
        self.assertEqual(status_code, 404)
        self.assertEqual(payload["error"]["code"], "NOT_FOUND")
        self.assertIn("request_id", payload)
