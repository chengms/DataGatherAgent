import argparse
import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_script_module(name: str, relative_path: str):
    script_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load script module: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MediaCrawlerRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.xhs_runner = load_script_module("mediacrawler_xhs_runner_v2", "scripts/mediacrawler_xhs_runner_v2.py")
        cls.platform_runner = load_script_module("mediacrawler_platform_runner", "scripts/mediacrawler_platform_runner.py")

    def test_xhs_search_command_defaults_to_headless_and_disables_comments(self) -> None:
        args = argparse.Namespace(
            mode="search",
            start_command=["uv", "run", "main.py", "--platform", "xhs"],
            login_type="cookie",
            cookies="demo",
            headless="true",
            keyword="AI startup",
            source_url=None,
        )
        command = self.xhs_runner.build_start_command(args, Path("output"))
        headless_index = command.index("--headless") + 1
        comment_index = command.index("--get_comment") + 1
        self.assertEqual(command[headless_index], "true")
        self.assertEqual(command[comment_index], "false")

    def test_xhs_runtime_profile_defaults_to_safe_cdp(self) -> None:
        args = argparse.Namespace(
            browser_mode="safe",
            browser_path="",
            headless="true",
            max_sleep_sec=4,
            max_concurrency=1,
        )
        profile = self.xhs_runner.create_runtime_profile(args)
        self.assertEqual(profile["mode"], "safe")
        self.assertTrue(profile["headless"])
        self.assertEqual(profile["max_sleep_sec"], 4)
        self.assertEqual(profile["max_concurrency"], 1)

    def test_xhs_fetch_command_enables_comments(self) -> None:
        args = argparse.Namespace(
            mode="fetch",
            start_command=["uv", "run", "main.py", "--platform", "xhs"],
            login_type="cookie",
            cookies="demo",
            headless="true",
            keyword=None,
            source_url="https://www.xiaohongshu.com/explore/demo",
        )
        command = self.xhs_runner.build_start_command(args, Path("output"))
        headless_index = command.index("--headless") + 1
        comment_index = command.index("--get_comment") + 1
        self.assertEqual(command[headless_index], "true")
        self.assertEqual(command[comment_index], "true")

    def test_xhs_runner_retry_marker_detects_comment_failures(self) -> None:
        stderr_text = "tenacity.RetryError ... get_note_comments ... DataFetchError"
        self.assertTrue(self.xhs_runner.should_retry_without_comments(stderr_text))

    def test_platform_search_command_defaults_to_headless_and_disables_comments(self) -> None:
        args = argparse.Namespace(
            platform="weibo",
            mode="search",
            start_command=["uv", "run", "main.py"],
            keyword="AI startup",
            source_url=None,
            login_type=None,
            cookies=None,
            headless="true",
        )
        command = self.platform_runner.build_start_command(args, Path("output"), "cookie", "demo")
        headless_index = command.index("--headless") + 1
        comment_index = command.index("--get_comment") + 1
        self.assertEqual(command[headless_index], "true")
        self.assertEqual(command[comment_index], "false")

    def test_platform_runtime_profile_builds_safe_sitecustomize(self) -> None:
        args = argparse.Namespace(
            browser_mode="safe",
            browser_path=r"C:\Browsers\chrome.exe",
            headless="true",
            max_sleep_sec=5,
            max_concurrency=1,
        )
        profile = self.platform_runner.create_runtime_profile(args)
        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = self.platform_runner.build_sitecustomize(Path(temp_dir), profile)
            content = script_path.read_text(encoding="utf-8")
        self.assertIn("config.ENABLE_CDP_MODE = True", content)
        self.assertIn("config.CDP_HEADLESS = True", content)
        self.assertIn(r'config.CUSTOM_BROWSER_PATH = r"C:\\Browsers\\chrome.exe"', content)
        self.assertIn("config.CRAWLER_MAX_SLEEP_SEC = 5", content)

    def test_platform_runner_can_explicitly_disable_headless(self) -> None:
        args = argparse.Namespace(
            platform="xiaohongshu",
            mode="search",
            start_command=["uv", "run", "main.py"],
            keyword="AI startup",
            source_url=None,
            login_type=None,
            cookies=None,
            headless="false",
        )
        command = self.platform_runner.build_start_command(args, Path("output"), "cookie", "demo")
        headless_index = command.index("--headless") + 1
        self.assertEqual(command[headless_index], "false")

    def test_platform_fetch_retry_marker_detects_comment_failures(self) -> None:
        stderr_text = "RetryError ... get_comments failed"
        self.assertTrue(self.platform_runner.should_retry_without_comments(stderr_text))


if __name__ == "__main__":
    unittest.main()
