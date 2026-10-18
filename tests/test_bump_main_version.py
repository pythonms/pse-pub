import importlib.util
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock


def load_bump_module():
    path = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "bump_main_version.py"
    spec = importlib.util.spec_from_file_location("bump_main_version", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bump_main_version"] = module
    spec.loader.exec_module(module)
    return module


bump = load_bump_module()


class BumpMainVersionTest(unittest.TestCase):
    def test_patch_bump_default(self) -> None:
        version, tag = bump.bump("fix: typo", '__version__ = "1.2.3"\n')
        self.assertEqual(version, "1.2.4")
        self.assertEqual(tag, "v1.2.4")

    def test_minor_bump_on_feat(self) -> None:
        version, tag = bump.bump("feat(api): add route", '__version__ = "1.2.3"\n')
        self.assertEqual((version, tag), ("1.3.0", "v1.3.0"))

    def test_major_bump_on_breaking_bang(self) -> None:
        version, _ = bump.bump("feat!: drop legacy", '__version__ = "1.2.3"\n')
        self.assertEqual(version, "2.0.0")

    def test_major_bump_on_breaking_footer(self) -> None:
        message = "fix: adjust\n\nBREAKING CHANGE: new protocol\n"
        version, _ = bump.bump(message, '__version__ = "1.2.3"\n')
        self.assertEqual(version, "2.0.0")

    def test_strips_dev_suffix_before_bump(self) -> None:
        version, _ = bump.bump(
            "fix: x",
            '__version__ = "0.1.15.dev13"\n',
            taken_tags=set(),
        )
        self.assertEqual(version, "0.1.16")

    def test_skips_existing_tags(self) -> None:
        version, tag = bump.bump(
            "fix: x",
            '__version__ = "0.1.15"\n',
            taken_tags={"v0.1.16", "v0.1.17"},
        )
        self.assertEqual((version, tag), ("0.1.18", "v0.1.18"))

    def test_is_release_commit(self) -> None:
        self.assertTrue(bump.is_release_commit("chore(release): 1.2.4\n"))
        self.assertFalse(bump.is_release_commit("feat: something\n"))

    def test_changelog_feat_under_unreleased(self) -> None:
        current = "# Changelog\n\n## [Unreleased]\n\n## [0.1.0] - 2026-01-01\n- old\n"
        updated = bump.update_changelog(
            current,
            "0.2.0",
            "feat(api): add health",
            today=date(2026, 10, 19),
        )
        self.assertIn("## [Unreleased]", updated)
        self.assertIn("## [0.2.0] - 2026-10-19", updated)
        self.assertIn("### Features", updated)
        self.assertIn("- **api:** add health", updated)
        # New entry before previous release
        self.assertLess(updated.index("## [0.2.0]"), updated.index("## [0.1.0]"))

    def test_changelog_breaking_section(self) -> None:
        updated = bump.update_changelog(
            "# Changelog\n\n## [Unreleased]\n",
            "2.0.0",
            "feat!: drop legacy auth",
            today=date(2026, 10, 19),
        )
        self.assertIn("### Breaking Changes", updated)
        self.assertIn("- drop legacy auth", updated)

    def test_main_writes_version_changelog_and_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_file = root / "__version__.py"
            changelog_file = root / "CHANGELOG.md"
            version_file.write_text('__version__ = "0.1.0"\n', encoding="utf-8")
            changelog_file.write_text(
                "# Changelog\n\n## [Unreleased]\n", encoding="utf-8"
            )
            output = root / "out.txt"

            with mock.patch.object(bump, "VERSION_FILE", version_file), mock.patch.object(
                bump, "CHANGELOG_FILE", changelog_file
            ), mock.patch.object(bump, "existing_tags", return_value=set()), mock.patch.dict(
                os.environ,
                {
                    "COMMIT_MESSAGE": "feat: hello",
                    "GITHUB_OUTPUT": str(output),
                },
            ):
                bump.main()

            self.assertEqual(
                version_file.read_text(encoding="utf-8"), '__version__ = "0.2.0"\n'
            )
            changelog = changelog_file.read_text(encoding="utf-8")
            self.assertIn("## [0.2.0]", changelog)
            self.assertIn("### Features", changelog)
            self.assertIn("- hello", changelog)
            text = output.read_text(encoding="utf-8")
            self.assertIn("version=0.2.0\n", text)
            self.assertIn("tag=v0.2.0\n", text)


if __name__ == "__main__":
    unittest.main()
