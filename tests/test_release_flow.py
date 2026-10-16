import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.release_flow import (
    ReleaseError,
    commit_dev_bump,
    ensure_annotated_tag,
    head_sha,
    main,
    snapshot,
    validate_pr,
)


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=check,
    )


def init_repo(path: Path) -> None:
    path.mkdir(parents=True)
    git(path, "init", "-b", "main")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")


def commit_all(path: Path, message: str) -> str:
    git(path, "add", "-A")
    git(path, "commit", "-m", message)
    return head_sha(path)


class ValidatePrTest(unittest.TestCase):
    def test_feature_pr_keeps_dev_version(self) -> None:
        errors = validate_pr(
            "Add settlement export",
            "",
            "1.5.0-dev",
            "# Changelog\n\n## [Unreleased]\n",
            base_version="1.5.0-dev",
        )
        self.assertEqual(errors, [])

    def test_feature_pr_rejects_version_bump_and_version_title(self) -> None:
        errors = validate_pr(
            "1.5.0-dev",
            "",
            "1.6.0-dev",
            "",
            base_version="1.5.0-dev",
        )
        self.assertTrue(any("version number" in error for error in errors))
        self.assertTrue(any("leave VERSION" in error for error in errors))

    def test_feature_pr_rejects_stable_version(self) -> None:
        errors = validate_pr("Add export", "", "1.5.0", "", base_version="1.5.0-dev")
        self.assertTrue(any("X.Y.Z-dev" in error for error in errors))

    def test_release_pr_accepts_stable_version_and_higher_next_dev(self) -> None:
        errors = validate_pr(
            "release: 1.5.0",
            "Ship it.\n\nNext-dev: 1.5.1-dev\n",
            "1.5.0",
            "# Changelog\n\n## [1.5.0] - 2026-10-16\n",
            base_version="1.5.0-dev",
        )
        self.assertEqual(errors, [])

    def test_release_pr_can_jump_to_a_higher_number(self) -> None:
        errors = validate_pr(
            "release: 1.0.0",
            "Next-dev: 1.1.0-dev\n",
            "1.0.0",
            "## [1.0.0]\n",
            base_version="0.1.0-dev",
        )
        self.assertEqual(errors, [])

    def test_release_pr_rejects_lower_number_same_dev_and_missing_notes(self) -> None:
        errors = validate_pr(
            "release: 1.4.0",
            "Next-dev: 1.4.0-dev\n",
            "1.5.0-dev",
            "# Changelog\n",
            base_version="1.5.0-dev",
        )
        joined = "\n".join(errors)
        self.assertIn("without -dev", joined)
        self.assertIn("CHANGELOG.md", joined)
        self.assertIn("higher", joined)
        self.assertIn("lower", joined)

    def test_release_version_must_match_title(self) -> None:
        errors = validate_pr(
            "release: 1.5.0",
            "Next-dev: 1.5.1-dev\n",
            "1.4.0",
            "## [1.5.0]\n",
            base_version="1.4.0-dev",
        )
        self.assertTrue(any("title says 1.5.0" in error for error in errors))

    def test_release_title_must_be_exact(self) -> None:
        errors = validate_pr(
            "release: v1.5.0",
            "Next-dev: 1.5.1-dev\n",
            "1.5.0",
            "## [1.5.0]\n",
        )
        self.assertTrue(any("exactly" in error for error in errors))

    def test_rejects_leading_zeros(self) -> None:
        errors = validate_pr("Add export", "", "01.2.3-dev", "")
        self.assertTrue(any("leading zeros" in error for error in errors))

    def test_introducing_dev_version_without_a_base_is_allowed(self) -> None:
        errors = validate_pr("Add release workflow", "", "0.1.0-dev", "# Changelog\n")
        self.assertEqual(errors, [])


class SnapshotTest(unittest.TestCase):
    def test_public_commit_has_only_the_public_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root / "priv"
            public = root / "pub"
            init_repo(private)
            init_repo(public)
            (public / "README.md").write_text("# pse-pub\n", encoding="utf-8")
            (public / "scratch.txt").write_text("drop me\n", encoding="utf-8")
            public_root = commit_all(public, "Initial commit")

            (private / "VERSION").write_text("1.5.0\n", encoding="utf-8")
            (private / "README.md").write_text("# pse\n", encoding="utf-8")
            secret = private / "notes"
            secret.mkdir()
            (secret / "wip.txt").write_text("not in this release\n", encoding="utf-8")
            private_sha = commit_all(private, "release: 1.5.0")
            secret_blob = git(private, "rev-parse", "HEAD:notes/wip.txt").stdout.strip()

            # The published tree is the release tree, not every private path
            # that happens to exist only in earlier commits. Remove the note
            # from the working tree that the snapshot copies.
            (secret / "wip.txt").unlink()
            secret.rmdir()

            published = snapshot(private, public, "1.5.0")
            parents = git(public, "rev-parse", f"{published}^@").stdout.split()
            history = git(public, "rev-list", "--all").stdout.split()

            self.assertEqual(parents, [public_root])
            self.assertNotIn(private_sha, history)
            self.assertNotIn(private_sha, parents)
            self.assertEqual((public / "VERSION").read_text(encoding="utf-8"), "1.5.0\n")
            self.assertFalse((public / "scratch.txt").exists())
            self.assertFalse((public / "notes").exists())
            self.assertEqual(git(public, "log", "-1", "--format=%s").stdout.strip(), "1.5.0")
            self.assertEqual(
                git(public, "rev-parse", "refs/tags/v1.5.0^{}").stdout.strip(),
                published,
            )
            self.assertNotIn(secret_blob, git(public, "rev-list", "--objects", "--all").stdout)

            again = snapshot(private, public, "1.5.0")
            self.assertEqual(again, published)
            self.assertEqual(head_sha(public), published)

    def test_existing_tag_is_not_moved_when_source_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root / "priv"
            public = root / "pub"
            init_repo(private)
            init_repo(public)
            (public / "README.md").write_text("old\n", encoding="utf-8")
            commit_all(public, "Initial commit")
            (private / "VERSION").write_text("1.5.0\n", encoding="utf-8")
            commit_all(private, "release")
            first = snapshot(private, public, "1.5.0")

            (private / "VERSION").write_text("1.5.0\nextra\n", encoding="utf-8")
            second = snapshot(private, public, "1.5.0")
            self.assertEqual(second, first)
            self.assertEqual((public / "VERSION").read_text(encoding="utf-8"), "1.5.0\n")

    def test_refuses_dev_version_and_nested_dest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root / "priv"
            public = root / "pub"
            init_repo(private)
            init_repo(public)
            (public / "README.md").write_text("old\n", encoding="utf-8")
            commit_all(public, "Initial commit")
            (private / "VERSION").write_text("1.5.0-dev\n", encoding="utf-8")
            commit_all(private, "dev")
            with self.assertRaises(ReleaseError):
                snapshot(private, public, "1.5.0-dev")
            nested = private / "pub"
            init_repo(nested)
            with self.assertRaises(ReleaseError):
                snapshot(private, nested, "1.5.0")

    def test_push_roundtrip_does_not_publish_private_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root / "priv"
            bare = root / "pub.git"
            public = root / "pub"
            init_repo(private)
            (private / "VERSION").write_text("0.1.0-dev\n", encoding="utf-8")
            (private / "wip.txt").write_text("secret work\n", encoding="utf-8")
            private_sha = commit_all(private, "wip")
            (private / "VERSION").write_text("0.1.0\n", encoding="utf-8")
            (private / "wip.txt").unlink()
            commit_all(private, "release: 0.1.0")

            bare.mkdir()
            git(bare, "init", "--bare", "-b", "main")
            init_repo(public)
            (public / "README.md").write_text("# pse-pub\n", encoding="utf-8")
            commit_all(public, "Initial commit")
            git(public, "remote", "add", "origin", bare.as_uri())
            git(public, "push", "-u", "origin", "main")

            snapshot(private, public, "0.1.0")
            git(public, "push", "origin", "HEAD:main")
            git(public, "push", "origin", "v0.1.0")

            mirror = root / "mirror"
            git(root, "clone", bare.as_uri(), str(mirror))
            history = git(mirror, "rev-list", "--all").stdout.split()
            self.assertNotIn(private_sha, history)
            self.assertEqual((mirror / "VERSION").read_text(encoding="utf-8"), "0.1.0\n")
            self.assertFalse((mirror / "wip.txt").exists())
            self.assertEqual(
                git(mirror, "rev-parse", "v0.1.0^{}").stdout.strip(),
                git(mirror, "rev-parse", "HEAD").stdout.strip(),
            )


class BumpAndTagTest(unittest.TestCase):
    def test_bump_moves_main_forward_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "priv"
            init_repo(repo)
            (repo / "VERSION").write_text("1.5.0\n", encoding="utf-8")
            commit_all(repo, "release: 1.5.0")
            first = commit_dev_bump(repo, "1.6.0-dev", "1.5.0")
            self.assertEqual((repo / "VERSION").read_text(encoding="utf-8"), "1.6.0-dev\n")
            self.assertEqual(git(repo, "log", "-1", "--format=%s").stdout.strip(), "Set version to 1.6.0-dev")
            self.assertNotEqual(first, git(repo, "rev-parse", "HEAD^").stdout.strip())
            second = commit_dev_bump(repo, "1.6.0-dev", "1.5.0")
            self.assertEqual(second, first)

    def test_bump_refuses_same_or_lower_number(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "priv"
            init_repo(repo)
            (repo / "VERSION").write_text("1.5.0\n", encoding="utf-8")
            commit_all(repo, "release: 1.5.0")
            with self.assertRaises(ReleaseError):
                commit_dev_bump(repo, "1.5.0-dev", "1.5.0")

    def test_tag_is_not_moved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "priv"
            init_repo(repo)
            (repo / "VERSION").write_text("1.5.0\n", encoding="utf-8")
            first = commit_all(repo, "release: 1.5.0")
            ensure_annotated_tag(repo, "1.5.0", first)
            (repo / "VERSION").write_text("1.5.0\n", encoding="utf-8")
            (repo / "extra.txt").write_text("x\n", encoding="utf-8")
            second = commit_all(repo, "later")
            ensure_annotated_tag(repo, "1.5.0", first)
            with self.assertRaises(ReleaseError):
                ensure_annotated_tag(repo, "1.5.0", second)


class CliTest(unittest.TestCase):
    def test_print_release_outputs_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("0.1.0\n", encoding="utf-8")
            (root / "CHANGELOG.md").write_text("## [0.1.0] - 2026-10-16\n", encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "print-release",
                        "--title",
                        "release: 0.1.0",
                        "--body",
                        "Next-dev: 0.1.1-dev\n",
                        "--version-file",
                        str(root / "VERSION"),
                        "--changelog",
                        str(root / "CHANGELOG.md"),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertEqual(stdout.getvalue(), "version=0.1.0\nnext_dev=0.1.1-dev\n")

    def test_check_pr_fails_for_dev_titled_pr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("0.1.0-dev\n", encoding="utf-8")
            (root / "CHANGELOG.md").write_text("## [Unreleased]\n", encoding="utf-8")
            code = main(
                [
                    "check-pr",
                    "--title",
                    "0.1.0-dev",
                    "--version-file",
                    str(root / "VERSION"),
                    "--changelog",
                    str(root / "CHANGELOG.md"),
                    "--base-version",
                    "0.1.0-dev",
                ]
            )
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
