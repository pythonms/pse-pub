import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def load_module():
    path = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "scripts"
        / "build_promote_pr.py"
    )
    spec = importlib.util.spec_from_file_location("build_promote_pr", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_promote_pr"] = module
    spec.loader.exec_module(module)
    return module


promote = load_module()


class BuildPromotePrTest(unittest.TestCase):
    def test_parse_commit_lines_normalizes_bullets(self) -> None:
        raw = "abc1234 feat: one\n- def5678 fix: two\n\n"
        self.assertEqual(
            promote.parse_commit_lines(raw),
            ["- abc1234 feat: one", "- def5678 fix: two"],
        )

    def test_default_title_from_latest_conventional(self) -> None:
        lines = ["- abc1234 feat: add endpoint", "- def5678 fix: typo"]
        self.assertEqual(promote.default_title(lines), "feat: add endpoint")

    def test_default_title_fallback_when_not_conventional(self) -> None:
        lines = ["- abc1234 Update stuff"]
        self.assertEqual(promote.default_title(lines), promote.DEFAULT_TITLE)

    def test_default_title_empty(self) -> None:
        self.assertEqual(promote.default_title([]), promote.DEFAULT_TITLE)

    def test_build_body_fresh(self) -> None:
        body = promote.build_body(["- abc1234 feat: one"])
        self.assertIn(promote.COMMITS_START, body)
        self.assertIn("- abc1234 feat: one", body)
        self.assertIn(promote.COMMITS_END, body)
        self.assertIn("## Squash message", body)

    def test_build_body_refreshes_only_marked_section(self) -> None:
        existing = (
            f"{promote.COMMITS_START}\n"
            "## Commits on dev (since main)\n\n"
            "- oldsha old: commit\n"
            f"{promote.COMMITS_END}\n\n"
            "## Notes\n\nKeep my note.\n\n"
            "## Squash message\n\nExisting footer.\n"
        )
        body = promote.build_body(["- newsha feat: fresh"], existing)
        self.assertIn("- newsha feat: fresh", body)
        self.assertNotIn("oldsha", body)
        self.assertIn("Keep my note.", body)
        self.assertIn("Existing footer.", body)

    def test_main_writes_github_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.txt"
            env = {
                "COMMIT_LINES": "- abc1234 feat: ship it\n- def5678 fix: nits",
                "EXISTING_BODY": "",
                "GITHUB_OUTPUT": str(out),
            }
            with mock.patch.dict(os.environ, env, clear=False):
                self.assertEqual(promote.main(), 0)
            text = out.read_text(encoding="utf-8")
            self.assertIn("title=feat: ship it\n", text)
            self.assertIn("has_commits=true\n", text)
            self.assertIn("body<<EOF\n", text)
            self.assertIn("- abc1234 feat: ship it", text)


if __name__ == "__main__":
    unittest.main()
