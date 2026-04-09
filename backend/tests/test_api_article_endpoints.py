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


class ApiArticleEndpointsTests(unittest.TestCase):
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
        while time.time() < deadline:
            try:
                payload = cls.get_json("/health")
                if payload["status"] == "ok":
                    return
            except Exception:
                time.sleep(0.25)
        raise RuntimeError("server did not start")

    @classmethod
    def build_url(cls, path: str) -> str:
        return f"http://127.0.0.1:{cls.port}{path}"

    @classmethod
    def get_json(cls, path: str) -> dict:
        with request.urlopen(cls.build_url(path), timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    @classmethod
    def post_json(cls, path: str, payload: dict) -> dict:
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
    def get_error_json(cls, path: str) -> tuple[int, dict]:
        try:
            with request.urlopen(cls.build_url(path), timeout=15) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    @classmethod
    def delete_json(cls, path: str) -> dict:
        http_request = request.Request(cls.build_url(path), method="DELETE")
        with request.urlopen(http_request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_article_search_and_detail_endpoints(self) -> None:
        preview = self.post_json(
            "/api/workflows/preview",
            {
                "keywords": ["Grid Storage"],
                "platforms": ["wechat"],
                "limit": 2,
                "top_k": 2,
                "fallback_to_mock": True,
            },
        )
        self.assertEqual(preview["fetched_count"], 2)

        payload = self.get_json("/api/workflows/articles?page=1&page_size=10&platform=wechat&content_kind=article")
        self.assertGreaterEqual(payload["total"], 2)
        self.assertGreaterEqual(len(payload["items"]), 1)

        item = payload["items"][0]
        self.assertEqual(item["platform"], "wechat")
        self.assertEqual(item["content_kind"], "article")
        self.assertIn("source_engine", item)
        self.assertIn("comments", item)
        self.assertIsInstance(item["comments"], list)

        detail = self.get_json(f"/api/workflows/articles/{item['id']}")
        self.assertEqual(detail["id"], item["id"])
        self.assertEqual(detail["source_url"], item["source_url"])
        self.assertIn("content_text", detail)
        self.assertIn("content_html", detail)
        self.assertIn("comments", detail)
        self.assertIsInstance(detail["comments"], list)

    def test_delete_article_endpoint(self) -> None:
        preview = self.post_json(
            "/api/workflows/preview",
            {
                "keywords": ["Grid Storage"],
                "platforms": ["wechat"],
                "limit": 1,
                "top_k": 1,
                "fallback_to_mock": True,
            },
        )
        payload = self.get_json(f"/api/workflows/articles?page=1&page_size=10&job_id={preview['job_id']}")
        self.assertEqual(payload["total"], 1)
        article_id = payload["items"][0]["id"]

        deleted = self.delete_json(f"/api/workflows/articles/{article_id}")
        self.assertEqual(deleted["id"], article_id)
        self.assertTrue(deleted["deleted"])

        refreshed = self.get_json(f"/api/workflows/articles?page=1&page_size=10&job_id={preview['job_id']}")
        self.assertEqual(refreshed["total"], 0)

    def test_missing_article_returns_not_found(self) -> None:
        status_code, payload = self.get_error_json("/api/workflows/articles/999999")
        self.assertEqual(status_code, 404)
        self.assertEqual(payload["error"]["code"], "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
