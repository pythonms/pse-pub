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

    def test_default_title_skips_chore_bump_tip(self) -> None:
        lines = [
            "- abc1234 chore(bump): 0.3.2",
            "- def5678 feat: auto-open promote PR",
            "- ghi9012 fix: tidy docstring",
        ]
        self.assertEqual(
            promote.default_title(lines), "feat: auto-open promote PR"
        )

    def test_default_title_all_bumps_falls_back(self) -> None:
        lines = ["- abc1234 chore(bump): 0.3.2", "- def5678 chore(bump): 0.3.1"]
        self.assertEqual(promote.default_title(lines), promote.DEFAULT_TITLE)

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
            "## Commits on dev since last sync with main\n\n"
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
        self.assertIn("since last sync with main", body)

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

    def test_collect_uses_last_main_sync_merge(self) -> None:
        def fake_git(*args: str):
            cmd = list(args)
            if cmd[:3] == ["rev-list", "--first-parent", "--merges"]:
                return mock.Mock(
                    returncode=0, stdout="merge1\nmerge0\n", stderr=""
                )
            if cmd[:1] == ["rev-parse"] and cmd[1:] == ["merge1^1", "merge1^2"]:
                return mock.Mock(
                    returncode=0, stdout="parent1\nmainish\n", stderr=""
                )
            if cmd[:3] == ["merge-base", "--is-ancestor", "mainish"]:
                return mock.Mock(returncode=0, stdout="", stderr="")
            if cmd[:1] == ["log"]:
                self.assertEqual(cmd[-1], "merge1..HEAD")
                return mock.Mock(
                    returncode=0,
                    stdout="- abc1234 feat: only new\n- def5678 chore(bump): 1.0.1.dev1\n",
                    stderr="",
                )
            self.fail(f"unexpected git args: {cmd}")

        with mock.patch.object(promote, "_git", side_effect=fake_git):
            lines = promote.collect_promote_commit_lines("origin/main", "HEAD")
        self.assertEqual(
            lines,
            [
                "- abc1234 feat: only new",
                "- def5678 chore(bump): 1.0.1.dev1",
            ],
        )

    def test_collect_falls_back_to_ancestry_path(self) -> None:
        def fake_git(*args: str):
            cmd = list(args)
            if cmd[:3] == ["rev-list", "--first-parent", "--merges"]:
                return mock.Mock(returncode=0, stdout="", stderr="")
            if cmd[:1] == ["merge-base"] and "--is-ancestor" not in cmd:
                return mock.Mock(returncode=0, stdout="mbsha\n", stderr="")
            if cmd[:1] == ["log"] and "--ancestry-path" in cmd:
                return mock.Mock(
                    returncode=0,
                    stdout="- abc1234 fix: narrow list\n",
                    stderr="",
                )
            self.fail(f"unexpected git args: {cmd}")

        with mock.patch.object(promote, "_git", side_effect=fake_git):
            lines = promote.collect_promote_commit_lines("origin/main", "HEAD")
        self.assertEqual(lines, ["- abc1234 fix: narrow list"])


if __name__ == "__main__":
    unittest.main()
