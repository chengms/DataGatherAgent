import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "scripts"))

import start_mediacrawler_service  # noqa: E402


class StartMediaCrawlerServiceTests(unittest.TestCase):
    def test_repo_python_prefers_local_venv(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repo_dir = Path(tempdir)
            python_bin = repo_dir / ".venv" / "Scripts" / "python.exe"
            python_bin.parent.mkdir(parents=True)
            python_bin.write_text("", encoding="utf-8")
            resolved = start_mediacrawler_service.repo_python(repo_dir)
        self.assertEqual(resolved, python_bin)

    def test_main_execs_repo_python_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repo_dir = Path(tempdir)
            python_bin = repo_dir / ".venv" / "Scripts" / "python.exe"
            python_bin.parent.mkdir(parents=True)
            python_bin.write_text("", encoding="utf-8")
            completed = type("Completed", (), {"returncode": 0})()
            with patch("start_mediacrawler_service.parse_args") as parse_args, patch(
                "start_mediacrawler_service.subprocess.run", return_value=completed
            ) as run:
                parse_args.return_value = type(
                    "Args",
                    (),
                    {"repo": str(repo_dir), "host": "127.0.0.1", "port": "8080", "reload": True},
                )()
                returncode = start_mediacrawler_service.main()
        self.assertEqual(returncode, 0)
        run.assert_called_once()
        argv = run.call_args.args[0]
        self.assertEqual(argv[0], str(python_bin))
        self.assertIn("--reload", argv)
        self.assertEqual(run.call_args.kwargs["cwd"], repo_dir)
        self.assertFalse(run.call_args.kwargs["check"])

    def test_main_falls_back_to_uv_when_local_python_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repo_dir = Path(tempdir)
            completed = type("Completed", (), {"returncode": 0})()
            with patch("start_mediacrawler_service.parse_args") as parse_args, patch(
                "start_mediacrawler_service.shutil.which", return_value="C:/tools/uv.exe"
            ), patch(
                "start_mediacrawler_service.subprocess.run", return_value=completed
            ) as run:
                parse_args.return_value = type(
                    "Args",
                    (),
                    {"repo": str(repo_dir), "host": "127.0.0.1", "port": "8080", "reload": False},
                )()
                returncode = start_mediacrawler_service.main()
        self.assertEqual(returncode, 0)
        run.assert_called_once_with(
            [
                "C:/tools/uv.exe",
                "run",
                "uvicorn",
                "api.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8080",
            ],
            cwd=repo_dir,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
