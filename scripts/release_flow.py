#!/usr/bin/env python3
"""Version rules and the private-to-public release snapshot.

Private main keeps X.Y.Z-dev. A release PR titled "release: X.Y.Z" sets that
version, tags vX.Y.Z, copies the file tree onto pse-pub (parent stays the
previous public commit), then main moves to the Next-dev version from the
PR body.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-dev)?$")
RELEASE_TITLE_RE = re.compile(r"^release: ([0-9]+\.[0-9]+\.[0-9]+)$")
SEMVER_TITLE_RE = re.compile(
    r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-dev)?$"
)
NEXT_DEV_RE = re.compile(r"^Next-dev:\s*(\S+)\s*$", re.MULTILINE)

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
}

GIT_NAME = "github-actions[bot]"
GIT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"


class ReleaseError(Exception):
    pass


def read_version(path: Path) -> str:
    if not path.is_file():
        raise ReleaseError(f"missing version file: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text or any(c.isspace() for c in text):
        raise ReleaseError(f"version file must be a single token: {path}")
    return text


def write_version(path: Path, version: str) -> None:
    if version_error(version):
        raise ReleaseError(version_error(version) or "invalid version")
    path.write_text(version + "\n", encoding="utf-8")


def parse_version(version: str) -> tuple[int, int, int, bool] | None:
    match = VERSION_RE.fullmatch(version)
    if not match:
        return None
    major, minor, patch, dev = match.groups()
    return int(major), int(minor), int(patch), dev is not None


def version_error(version: str) -> str | None:
    if parse_version(version) is None:
        return (
            f"invalid version {version!r}; use X.Y.Z or X.Y.Z-dev "
            "with no leading zeros"
        )
    return None


def numeric(version: str) -> tuple[int, int, int]:
    parsed = parse_version(version)
    if parsed is None:
        raise ReleaseError(version_error(version) or "invalid version")
    return parsed[0], parsed[1], parsed[2]


def is_dev(version: str) -> bool:
    parsed = parse_version(version)
    if parsed is None:
        raise ReleaseError(version_error(version) or "invalid version")
    return parsed[3]


def changelog_has_version(changelog: str, version: str) -> bool:
    heading = f"## [{version}]"
    for line in changelog.splitlines():
        stripped = line.strip()
        if stripped == heading or stripped.startswith(heading + " "):
            return True
    return False


def parse_release_title(title: str) -> str | None:
    match = RELEASE_TITLE_RE.fullmatch(title.strip())
    if not match:
        return None
    version = match.group(1)
    if version_error(version) or is_dev(version):
        return None
    return version


def parse_next_dev(body: str) -> str | None:
    found = NEXT_DEV_RE.findall(body or "")
    if not found:
        return None
    unique = set(found)
    if len(unique) != 1:
        raise ReleaseError("Next-dev is declared more than once with different values")
    return found[0]


def validate_pr(
    title: str,
    body: str,
    version: str,
    changelog: str,
    base_version: str | None = None,
) -> list[str]:
    errors: list[str] = []
    if err := version_error(version):
        errors.append(err)
        return errors

    if base_version is not None:
        if err := version_error(base_version):
            errors.append(f"base {err}")
            return errors

    release = parse_release_title(title)
    if title.strip().startswith("release:") and release is None:
        errors.append("release PR title must be exactly 'release: X.Y.Z'")
        return errors

    if release is not None:
        if is_dev(version):
            errors.append("release PR must set VERSION to X.Y.Z without -dev")
        elif version != release:
            errors.append(f"VERSION is {version}, title says {release}")
        if not changelog_has_version(changelog, release or version):
            errors.append(f"CHANGELOG.md needs a heading '## [{release}]'")
        try:
            next_dev = parse_next_dev(body)
        except ReleaseError as exc:
            errors.append(str(exc))
            next_dev = None
        if next_dev is None:
            errors.append("release PR body needs a line 'Next-dev: X.Y.Z-dev'")
        else:
            if err := version_error(next_dev):
                errors.append(f"Next-dev {err}")
            elif not is_dev(next_dev):
                errors.append("Next-dev must use the -dev suffix")
            elif numeric(next_dev) <= numeric(release):
                errors.append("Next-dev must be a higher X.Y.Z than the release")
        if base_version is not None and numeric(release) < numeric(base_version):
            errors.append(
                f"release {release} is lower than current main version {base_version}"
            )
        return errors

    if SEMVER_TITLE_RE.fullmatch(title.strip()):
        errors.append(
            "PR title is a version number; describe the change, "
            "and use 'release: X.Y.Z' only when cutting a release"
        )
    if not is_dev(version):
        errors.append("non-release PR must keep VERSION on X.Y.Z-dev")
    if base_version is not None and version != base_version:
        errors.append(
            f"non-release PR must leave VERSION at {base_version}; "
            "the number changes only when a release is cut"
        )
    return errors


def _git(
    repo: Path,
    args: list[str],
    *,
    check: bool = True,
    identity: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = ["git"]
    if identity:
        command += ["-c", f"user.name={GIT_NAME}", "-c", f"user.email={GIT_EMAIL}"]
    command += args
    result = subprocess.run(
        command,
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ReleaseError(f"git {' '.join(args)} failed: {detail}")
    return result


def head_sha(repo: Path) -> str:
    return _git(repo, ["rev-parse", "HEAD"]).stdout.strip()


def tag_sha(repo: Path, tag: str) -> str | None:
    result = _git(repo, ["rev-parse", "--verify", f"refs/tags/{tag}^{{}}"], check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def ensure_annotated_tag(repo: Path, version: str, commit: str) -> None:
    if is_dev(version) or version_error(version):
        raise ReleaseError(f"refusing to tag a non-release version {version}")
    tag = f"v{version}"
    existing = tag_sha(repo, tag)
    if existing is not None:
        if existing != commit:
            raise ReleaseError(f"{tag} already points at {existing}, not {commit}")
        return
    _git(repo, ["tag", "-a", tag, commit, "-m", version], identity=True)


def _rel_parts(path: Path, root: Path) -> tuple[str, ...]:
    return path.relative_to(root).parts


def _ignored(rel: tuple[str, ...]) -> bool:
    return any(part in SKIP_DIR_NAMES for part in rel)


def replace_tree(source: Path, dest: Path) -> None:
    source = source.resolve()
    dest = dest.resolve()
    if not source.is_dir():
        raise ReleaseError(f"source is not a directory: {source}")
    if not (dest / ".git").exists():
        raise ReleaseError(f"dest is not a git checkout: {dest}")
    if dest == source or dest in source.parents:
        raise ReleaseError("dest must not be the source directory or a parent of it")
    if source in dest.parents:
        raise ReleaseError("dest must not live inside source")

    wanted: set[tuple[str, ...]] = set()
    for path in source.rglob("*"):
        rel = _rel_parts(path, source)
        if _ignored(rel):
            continue
        wanted.add(rel)
        target = dest.joinpath(*rel)
        if path.is_symlink():
            raise ReleaseError(f"refusing to copy symlink: {path}")
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)

    for path in sorted(dest.rglob("*"), reverse=True):
        rel = _rel_parts(path, dest)
        if _ignored(rel) or rel in wanted:
            continue
        if path.is_dir():
            path.rmdir()
        else:
            path.unlink()


def snapshot(source: Path, dest: Path, version: str) -> str:
    """Point dest at a new commit whose tree is source. Parent stays dest HEAD."""
    if version_error(version) or is_dev(version):
        raise ReleaseError(f"public snapshot version must be X.Y.Z, got {version}")
    previous = head_sha(dest)
    tag = f"v{version}"
    existing = tag_sha(dest, tag)
    if existing is not None:
        return existing

    replace_tree(source, dest)
    _git(dest, ["add", "-A"])
    dirty = _git(dest, ["status", "--porcelain"]).stdout.strip()
    if dirty:
        _git(dest, ["commit", "-m", version], identity=True)
    elif read_version(dest / "VERSION") != version:
        raise ReleaseError(
            "public tree already matches source but VERSION is not the release"
        )

    commit = head_sha(dest)
    if commit != previous:
        parents = _git(dest, ["rev-parse", f"{commit}^@"]).stdout.split()
        if previous not in parents:
            raise ReleaseError("public release commit lost its public parent")
    ensure_annotated_tag(dest, version, commit)
    return commit


def push_ref(repo: Path, *refs: str) -> None:
    _git(repo, ["push", "origin", *refs])


def commit_dev_bump(repo: Path, next_dev: str, expect: str) -> str:
    current = read_version(repo / "VERSION")
    if not is_dev(next_dev) or numeric(next_dev) <= numeric(expect):
        raise ReleaseError(f"refusing bump to {next_dev}")
    if current == next_dev:
        return head_sha(repo)
    if current != expect:
        raise ReleaseError(
            f"refusing to bump VERSION from {current}; expected {expect}"
        )
    write_version(repo / "VERSION", next_dev)
    _git(repo, ["add", "VERSION"])
    _git(repo, ["commit", "-m", f"Set version to {next_dev}"], identity=True)
    return head_sha(repo)


def _print_errors(errors: list[str]) -> int:
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


def _load_pr(args: argparse.Namespace) -> tuple[str, str]:
    version = read_version(Path(args.version_file))
    changelog_path = Path(args.changelog)
    if not changelog_path.is_file():
        raise ReleaseError(f"missing changelog: {changelog_path}")
    return version, changelog_path.read_text(encoding="utf-8")


def _title_body(args: argparse.Namespace) -> tuple[str, str]:
    title = args.title if args.title is not None else os.environ.get("PR_TITLE", "")
    body = args.body if args.body is not None else os.environ.get("PR_BODY", "")
    return title, body


def _base_version(args: argparse.Namespace) -> str | None:
    if args.base_version is not None:
        return args.base_version
    return os.environ.get("PR_BASE_VERSION") or None


def cmd_check_pr(args: argparse.Namespace) -> int:
    version, changelog = _load_pr(args)
    title, body = _title_body(args)
    errors = validate_pr(
        title,
        body,
        version,
        changelog,
        base_version=_base_version(args),
    )
    return _print_errors(errors)


def cmd_print_release(args: argparse.Namespace) -> int:
    version, changelog = _load_pr(args)
    title, body = _title_body(args)
    errors = validate_pr(
        title,
        body,
        version,
        changelog,
        base_version=_base_version(args),
    )
    if errors:
        return _print_errors(errors)
    release = parse_release_title(title)
    next_dev = parse_next_dev(body)
    if release is None or next_dev is None:
        print("not a release PR", file=sys.stderr)
        return 1
    print(f"version={release}")
    print(f"next_dev={next_dev}")
    return 0


def cmd_tag(args: argparse.Namespace) -> int:
    repo = Path(args.repo)
    version = read_version(repo / "VERSION")
    if version != args.version:
        print(f"VERSION is {version}, expected {args.version}", file=sys.stderr)
        return 1
    ensure_annotated_tag(repo, args.version, head_sha(repo))
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    commit = snapshot(Path(args.source), Path(args.dest), args.version)
    print(commit)
    return 0


def cmd_bump(args: argparse.Namespace) -> int:
    commit_dev_bump(Path(args.repo), args.version, args.expect)
    return 0


def cmd_check_version(args: argparse.Namespace) -> int:
    version = read_version(Path(args.version_file))
    if err := version_error(version):
        print(err, file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check-pr")
    check.add_argument("--title", default=None)
    check.add_argument("--body", default=None)
    check.add_argument("--version-file", default="VERSION")
    check.add_argument("--changelog", default="CHANGELOG.md")
    check.add_argument("--base-version")
    check.set_defaults(func=cmd_check_pr)

    printed = sub.add_parser("print-release")
    printed.add_argument("--title", default=None)
    printed.add_argument("--body", default=None)
    printed.add_argument("--version-file", default="VERSION")
    printed.add_argument("--changelog", default="CHANGELOG.md")
    printed.add_argument("--base-version")
    printed.set_defaults(func=cmd_print_release)

    version = sub.add_parser("check-version")
    version.add_argument("--version-file", default="VERSION")
    version.set_defaults(func=cmd_check_version)

    tag = sub.add_parser("tag")
    tag.add_argument("--repo", default=".")
    tag.add_argument("--version", required=True)
    tag.set_defaults(func=cmd_tag)

    snap = sub.add_parser("snapshot")
    snap.add_argument("--source", required=True)
    snap.add_argument("--dest", required=True)
    snap.add_argument("--version", required=True)
    snap.set_defaults(func=cmd_snapshot)

    bump = sub.add_parser("bump")
    bump.add_argument("--repo", default=".")
    bump.add_argument("--version", required=True)
    bump.add_argument("--expect", required=True)
    bump.set_defaults(func=cmd_bump)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ReleaseError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
