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
    def test_patch_from_final_starts_dev1(self) -> None:
        version, tag = bump.bump("fix: typo", '__version__ = "1.2.3"\n')
        self.assertEqual(version, "1.2.4.dev1")
        self.assertEqual(tag, "v1.2.4.dev1")

    def test_minor_from_final_starts_dev1(self) -> None:
        version, tag = bump.bump("feat(api): add route", '__version__ = "1.2.3"\n')
        self.assertEqual((version, tag), ("1.3.0.dev1", "v1.3.0.dev1"))

    def test_major_from_final_starts_dev1(self) -> None:
        version, _ = bump.bump("feat!: drop legacy", '__version__ = "1.2.3"\n')
        self.assertEqual(version, "2.0.0.dev1")

    def test_patch_on_dev_increments_dev_n(self) -> None:
        version, tag = bump.bump("fix: more", '__version__ = "1.2.4.dev1"\n')
        self.assertEqual((version, tag), ("1.2.4.dev2", "v1.2.4.dev2"))

    def test_feat_on_dev_bumps_minor_base(self) -> None:
        version, tag = bump.bump("feat: bigger", '__version__ = "1.2.4.dev3"\n')
        self.assertEqual((version, tag), ("1.3.0.dev1", "v1.3.0.dev1"))

    def test_strongest_bump_message_prefers_feat_over_fix(self) -> None:
        msg = bump.strongest_bump_message(
            "fix: expect service field",
            "feat: addition pse service info",
            "docs: note",
        )
        self.assertEqual(bump.bump_kind(msg), "minor")
        self.assertIn("feat:", msg)

    def test_dev_mode_uses_strongest_commit_since_last_bump(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "__version__.py").write_text(
                '__version__ = "0.5.3.dev2"\n', encoding="utf-8"
            )
            out = root / "out.txt"
            env = {
                "MODE": "dev",
                "COMMIT_MESSAGE": "fix: expect service field in /health test",
                "GITHUB_OUTPUT": str(out),
            }
            with (
                mock.patch.object(bump, "VERSION_FILE", root / "__version__.py"),
                mock.patch.object(
                    bump,
                    "commit_subjects_since_last_bump",
                    return_value=[
                        "fix: expect service field in /health test",
                        "feat: addition pse service info",
                        "docs: addition info github",
                    ],
                ),
                mock.patch.object(bump, "existing_tags", return_value=set()),
                mock.patch.dict(os.environ, env, clear=False),
            ):
                bump.main()
            self.assertEqual(
                (root / "__version__.py").read_text(encoding="utf-8"),
                '__version__ = "0.6.0.dev1"\n',
            )

    def test_breaking_on_dev_bumps_major_base(self) -> None:
        version, tag = bump.bump(
            "fix: adjust\n\nBREAKING CHANGE: new protocol\n",
            '__version__ = "1.2.4.dev2"\n',
        )
        self.assertEqual((version, tag), ("2.0.0.dev1", "v2.0.0.dev1"))

    def test_skips_existing_dev_tags(self) -> None:
        version, tag = bump.bump(
            "fix: x",
            '__version__ = "0.1.15"\n',
            taken_tags={"v0.1.16.dev1", "v0.1.16.dev2"},
        )
        self.assertEqual((version, tag), ("0.1.16.dev3", "v0.1.16.dev3"))

    def test_bump_advances_base_when_clean_tag_already_released(self) -> None:
        version, tag = bump.bump(
            "fix: after release",
            '__version__ = "0.5.0.dev4"\n',
            taken_tags={"v0.5.0", "v0.5.0.dev4"},
        )
        self.assertEqual((version, tag), ("0.5.1.dev1", "v0.5.1.dev1"))

    def test_bump_feat_after_released_base(self) -> None:
        version, tag = bump.bump(
            "feat: next",
            '__version__ = "0.5.0.dev2"\n',
            taken_tags={"v0.5.0"},
        )
        self.assertEqual((version, tag), ("0.6.0.dev1", "v0.6.0.dev1"))

    def test_next_dev_checkpoint_from_tag_history(self) -> None:
        version, tag = bump.next_dev_checkpoint(
            '__version__ = "1.2.0.dev1"\n',
            taken_tags={"v1.2.0.dev1", "v1.2.0.dev2"},
        )
        self.assertEqual((version, tag), ("1.2.0.dev3", "v1.2.0.dev3"))

    def test_next_dev_checkpoint_advances_base_if_released(self) -> None:
        version, tag = bump.next_dev_checkpoint(
            '__version__ = "1.2.0"\n',
            taken_tags={"v1.2.0"},
        )
        self.assertEqual((version, tag), ("1.2.1.dev1", "v1.2.1.dev1"))

    def test_next_dev_checkpoint_uses_file_when_ahead_of_tags(self) -> None:
        version, tag = bump.next_dev_checkpoint(
            '__version__ = "1.2.0.dev5"\n',
            taken_tags={"v1.2.0.dev1"},
        )
        self.assertEqual((version, tag), ("1.2.0.dev6", "v1.2.0.dev6"))

    def test_is_release_and_bump_commit(self) -> None:
        self.assertTrue(bump.is_release_commit("chore(release): 1.2.4\n"))
        self.assertTrue(bump.is_bump_commit("chore(bump): 1.2.4.dev1\n"))
        self.assertFalse(bump.is_release_commit("feat: something\n"))
        self.assertFalse(bump.is_bump_commit("feat: something\n"))

    def test_is_dev_tag(self) -> None:
        self.assertTrue(bump.is_dev_tag("v1.2.0.dev1"))
        self.assertFalse(bump.is_dev_tag("v1.2.0"))
        self.assertFalse(bump.is_dev_tag("v1.2.0-rc.1"))

    def test_release_strips_dev_suffix(self) -> None:
        version, tag = bump.release_version_from_file(
            '__version__ = "0.2.5.dev4"\n',
            taken_tags=set(),
        )
        self.assertEqual((version, tag), ("0.2.5", "v0.2.5"))

    def test_release_from_final_keeps_number(self) -> None:
        version, tag = bump.release_version_from_file(
            '__version__ = "0.2.5"\n',
            taken_tags=set(),
        )
        self.assertEqual((version, tag), ("0.2.5", "v0.2.5"))

    def test_release_skips_taken_clean_tag(self) -> None:
        version, tag = bump.release_version_from_file(
            '__version__ = "0.5.0.dev4"\n',
            taken_tags={"v0.5.0"},
        )
        self.assertEqual((version, tag), ("0.5.1", "v0.5.1"))

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

    def test_changelog_sanitizes_markdown_links(self) -> None:
        updated = bump.update_changelog(
            "# Changelog\n\n## [Unreleased]\n",
            "0.3.0",
            "fix: see [docs](https://evil.example/phish)",
            today=date(2026, 10, 19),
        )
        self.assertIn("- see docs", updated)
        self.assertNotIn("evil.example", updated)
        self.assertNotIn("](", updated)

    def test_changelog_source_recovers_from_bump_squash(self) -> None:
        message = (
            "chore(bump): 0.3.2.dev1 (#19)\n"
            "\n"
            "* chore: parameterize repo names\n"
            "* feat: auto-open promote PR\n"
            "* chore(bump): 0.3.3.dev1\n"
        )
        self.assertEqual(
            bump.changelog_source_message(message),
            "chore: parameterize repo names",
        )
        updated = bump.update_changelog(
            "# Changelog\n\n## [Unreleased]\n",
            "0.3.3",
            message,
            today=date(2026, 11, 18),
        )
        self.assertIn("### Chores", updated)
        self.assertIn("- parameterize repo names", updated)
        self.assertNotIn("0.3.2.dev1 (#19)", updated)

    def test_main_mode_strips_dev_and_writes_changelog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_file = root / "__version__.py"
            changelog_file = root / "CHANGELOG.md"
            version_file.write_text('__version__ = "0.2.5.dev3"\n', encoding="utf-8")
            changelog_file.write_text(
                "# Changelog\n\n## [Unreleased]\n", encoding="utf-8"
            )
            output = root / "out.txt"

            with mock.patch.object(bump, "VERSION_FILE", version_file), mock.patch.object(
                bump, "CHANGELOG_FILE", changelog_file
            ), mock.patch.object(bump, "existing_tags", return_value=set()), mock.patch.object(
                bump, "tags_pointing_at_head", return_value=set()
            ), mock.patch.dict(
                os.environ,
                {
                    "MODE": "main",
                    "COMMIT_MESSAGE": "feat: hello",
                    "GITHUB_OUTPUT": str(output),
                },
            ):
                bump.main()

            self.assertEqual(
                version_file.read_text(encoding="utf-8"), '__version__ = "0.2.5"\n'
            )
            changelog = changelog_file.read_text(encoding="utf-8")
            self.assertIn("## [0.2.5]", changelog)
            self.assertIn("### Features", changelog)
            self.assertIn("- hello", changelog)
            text = output.read_text(encoding="utf-8")
            self.assertIn("version=0.2.5\n", text)
            self.assertIn("tag=v0.2.5\n", text)

    def test_main_mode_allows_chore_bump_squash_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_file = root / "__version__.py"
            changelog_file = root / "CHANGELOG.md"
            version_file.write_text('__version__ = "0.3.3.dev2"\n', encoding="utf-8")
            changelog_file.write_text(
                "# Changelog\n\n## [Unreleased]\n", encoding="utf-8"
            )
            output = root / "out.txt"
            message = (
                "chore(bump): 0.3.3.dev2 (#19)\n\n"
                "* feat: auto-open promote PR\n"
            )

            with mock.patch.object(bump, "VERSION_FILE", version_file), mock.patch.object(
                bump, "CHANGELOG_FILE", changelog_file
            ), mock.patch.object(bump, "existing_tags", return_value=set()), mock.patch.object(
                bump, "tags_pointing_at_head", return_value=set()
            ), mock.patch.dict(
                os.environ,
                {
                    "MODE": "main",
                    "COMMIT_MESSAGE": message,
                    "GITHUB_OUTPUT": str(output),
                },
            ):
                bump.main()

            changelog = changelog_file.read_text(encoding="utf-8")
            self.assertEqual(
                version_file.read_text(encoding="utf-8"), '__version__ = "0.3.3"\n'
            )
            self.assertIn("## [0.3.3]", changelog)
            self.assertIn("### Features", changelog)
            self.assertIn("- auto-open promote PR", changelog)
            text = output.read_text(encoding="utf-8")
            self.assertIn("version=0.3.3\n", text)
            self.assertIn("tag=v0.3.3\n", text)

    def test_main_mode_still_refuses_chore_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_file = root / "__version__.py"
            version_file.write_text('__version__ = "0.3.3.dev1"\n', encoding="utf-8")
            with mock.patch.object(bump, "VERSION_FILE", version_file), mock.patch.dict(
                os.environ,
                {"MODE": "main", "COMMIT_MESSAGE": "chore(release): 0.3.3"},
                clear=False,
            ), self.assertRaises(SystemExit) as ctx:
                bump.main()
            self.assertIn("chore(release)", str(ctx.exception))

    def test_main_mode_reuses_clean_tag_on_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_file = root / "__version__.py"
            changelog_file = root / "CHANGELOG.md"
            version_file.write_text('__version__ = "0.2.5.dev3"\n', encoding="utf-8")
            changelog_file.write_text(
                "# Changelog\n\n## [Unreleased]\n", encoding="utf-8"
            )
            output = root / "out.txt"
            before = changelog_file.read_text(encoding="utf-8")

            with mock.patch.object(bump, "VERSION_FILE", version_file), mock.patch.object(
                bump, "CHANGELOG_FILE", changelog_file
            ), mock.patch.object(
                bump, "tags_pointing_at_head", return_value={"v0.2.5"}
            ), mock.patch.dict(
                os.environ,
                {
                    "MODE": "main",
                    "COMMIT_MESSAGE": "feat: hello",
                    "GITHUB_OUTPUT": str(output),
                },
            ):
                bump.main()

            self.assertEqual(
                version_file.read_text(encoding="utf-8"),
                '__version__ = "0.2.5.dev3"\n',
            )
            self.assertEqual(changelog_file.read_text(encoding="utf-8"), before)
            text_out = output.read_text(encoding="utf-8")
            self.assertIn("version=0.2.5\n", text_out)
            self.assertIn("tag=v0.2.5\n", text_out)
            self.assertIn("already_tagged=true\n", text_out)

    def test_dev_tag_mode_writes_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_file = root / "__version__.py"
            version_file.write_text('__version__ = "0.3.6"\n', encoding="utf-8")
            output = root / "out.txt"
            with mock.patch.object(bump, "VERSION_FILE", version_file), mock.patch.object(
                bump, "existing_tags", return_value={"v0.3.6"}
            ), mock.patch.dict(
                os.environ,
                {
                    "MODE": "dev-tag",
                    "COMMIT_MESSAGE": "chore: tag checkpoint",
                    "GITHUB_OUTPUT": str(output),
                },
            ):
                bump.main()
            self.assertEqual(
                version_file.read_text(encoding="utf-8"),
                '__version__ = "0.3.7.dev1"\n',
            )
            self.assertIn("tag=v0.3.7.dev1\n", output.read_text(encoding="utf-8"))

    def test_dev_mode_bumps_to_dev_without_changelog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_file = root / "__version__.py"
            changelog_file = root / "CHANGELOG.md"
            version_file.write_text('__version__ = "0.1.0"\n', encoding="utf-8")
            changelog_file.write_text(
                "# Changelog\n\n## [Unreleased]\n", encoding="utf-8"
            )
            output = root / "out.txt"
            before = changelog_file.read_text(encoding="utf-8")

            with mock.patch.object(bump, "VERSION_FILE", version_file), mock.patch.object(
                bump, "CHANGELOG_FILE", changelog_file
            ), mock.patch.object(bump, "existing_tags", return_value=set()), mock.patch.dict(
                os.environ,
                {
                    "MODE": "dev",
                    "COMMIT_MESSAGE": "feat: hello",
                    "GITHUB_OUTPUT": str(output),
                },
            ):
                bump.main()

            self.assertEqual(
                version_file.read_text(encoding="utf-8"),
                '__version__ = "0.2.0.dev1"\n',
            )
            self.assertEqual(changelog_file.read_text(encoding="utf-8"), before)
            text = output.read_text(encoding="utf-8")
            self.assertIn("version=0.2.0.dev1\n", text)
            self.assertIn("tag=v0.2.0.dev1\n", text)


if __name__ == "__main__":
    unittest.main()
