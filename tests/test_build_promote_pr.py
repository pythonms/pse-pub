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

    def test_default_title_prefers_feat_over_newer_fix(self) -> None:
        lines = [
            "- abc1234 fix: expect service field in /health test",
            "- def5678 feat: addition pse service info",
            "- ghi9012 docs: addition info github",
        ]
        self.assertEqual(
            promote.default_title(lines), "feat: addition pse service info"
        )

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
                head = cmd[3]
                if head == "HEAD":
                    return mock.Mock(
                        returncode=0, stdout="merge1\nmerge0\n", stderr=""
                    )
                # pre-sync walk: no older sync → empty
                return mock.Mock(returncode=0, stdout="", stderr="")
            if cmd[:1] == ["rev-parse"] and cmd[1:] == ["merge1^1", "merge1^2"]:
                return mock.Mock(
                    returncode=0, stdout="parent1\nmainish\n", stderr=""
                )
            if cmd[:2] == ["merge-base", "--is-ancestor"]:
                return mock.Mock(returncode=0, stdout="", stderr="")
            if cmd[:1] == ["merge-base"]:
                return mock.Mock(returncode=0, stdout="mb\n", stderr="")
            if cmd[:2] == ["diff", "--name-only"]:
                # Post-sync work explains the whole tree diff → no pre-sync list
                return mock.Mock(returncode=0, stdout="src/x.py\n", stderr="")
            if cmd[:1] == ["log"]:
                range_spec = cmd[-1]
                if range_spec == "merge1..HEAD":
                    return mock.Mock(
                        returncode=0,
                        stdout=(
                            "- abc1234 feat: only new\n"
                            "- def5678 chore(bump): 1.0.1.dev1\n"
                        ),
                        stderr="",
                    )
                # ancestry-path / before-sync fallback
                return mock.Mock(returncode=0, stdout="", stderr="")
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

    def test_collect_includes_pre_sync_when_only_bumps_after(self) -> None:
        """After main→dev merge, sync..HEAD is often only chore(bump)."""

        def fake_git(*args: str):
            cmd = list(args)
            if cmd[:3] == ["rev-list", "--first-parent", "--merges"]:
                head = cmd[3]
                if head == "HEAD":
                    return mock.Mock(returncode=0, stdout="sync1\n", stderr="")
                if head == "sync1^1":
                    return mock.Mock(returncode=0, stdout="sync0\n", stderr="")
                return mock.Mock(returncode=0, stdout="", stderr="")
            if cmd[:1] == ["rev-parse"]:
                sha = cmd[1].split("^")[0]
                if sha == "sync1":
                    return mock.Mock(
                        returncode=0, stdout="devparent\nmainish\n", stderr=""
                    )
                if sha == "sync0":
                    return mock.Mock(
                        returncode=0, stdout="older\nmainish0\n", stderr=""
                    )
            if cmd[:2] == ["merge-base", "--is-ancestor"]:
                return mock.Mock(returncode=0, stdout="", stderr="")
            if cmd[:1] == ["log"]:
                range_spec = cmd[-1]
                if range_spec == "sync1..HEAD":
                    return mock.Mock(
                        returncode=0,
                        stdout="- aaa1111 chore(bump): 0.5.2.dev2\n",
                        stderr="",
                    )
                if range_spec == "sync0..sync1^1":
                    return mock.Mock(
                        returncode=0,
                        stdout="- bbb2222 docs: tidy info.md\n",
                        stderr="",
                    )
            if cmd[:2] == ["diff", "--name-only"]:
                range_spec = cmd[-1]
                if range_spec == "origin/main...HEAD":
                    return mock.Mock(
                        returncode=0, stdout="docs/info.md\n__version__.py\n", stderr=""
                    )
                if range_spec == "sync1...HEAD":
                    return mock.Mock(
                        returncode=0, stdout="__version__.py\n", stderr=""
                    )
                return mock.Mock(returncode=0, stdout="", stderr="")
            self.fail(f"unexpected git args: {cmd}")

        with mock.patch.object(promote, "_git", side_effect=fake_git):
            lines = promote.collect_promote_commit_lines("origin/main", "HEAD")
        self.assertEqual(
            lines,
            [
                "- bbb2222 docs: tidy info.md",
                "- aaa1111 chore(bump): 0.5.2.dev2",
            ],
        )

    def test_main_needs_promote_when_tree_differs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.txt"
            env = {
                "COMMIT_LINES": "\n",
                "EXISTING_BODY": "",
                "GITHUB_OUTPUT": str(out),
                "MAIN_REF": "origin/main",
            }
            with (
                mock.patch.dict(os.environ, env, clear=False),
                mock.patch.object(promote, "tree_differs", return_value=True),
            ):
                self.assertEqual(promote.main(), 0)
            self.assertIn("has_commits=true\n", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
