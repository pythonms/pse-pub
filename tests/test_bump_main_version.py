import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


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
        version, _ = bump.bump("fix: x", '__version__ = "0.1.15.dev13"\n')
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

    def test_main_writes_file_and_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_file = root / "__version__.py"
            version_file.write_text('__version__ = "0.1.0"\n', encoding="utf-8")
            output = root / "out.txt"
            # Script uses fixed VERSION_FILE path relative to cwd
            import os
            from unittest import mock

            with mock.patch.object(bump, "VERSION_FILE", version_file):
                with mock.patch.dict(
                    os.environ,
                    {
                        "COMMIT_MESSAGE": "feat: hello",
                        "GITHUB_OUTPUT": str(output),
                    },
                ):
                    bump.main()
            self.assertEqual(version_file.read_text(encoding="utf-8"), '__version__ = "0.2.0"\n')
            text = output.read_text(encoding="utf-8")
            self.assertIn("version=0.2.0\n", text)
            self.assertIn("tag=v0.2.0\n", text)


if __name__ == "__main__":
    unittest.main()
