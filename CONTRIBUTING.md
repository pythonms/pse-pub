# Contributing

Thanks for helping improve this project. Development happens in **pse-priv**;
public releases are mirrored to [pse-pub](https://github.com/pythonms/pse-pub).

## Workflow

1. Branch from `dev` (not `main`).
2. Use [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` → minor bump
   - `fix:` → patch bump
   - `feat!:` / `BREAKING CHANGE:` → major bump
3. Open a PR into `dev`. CI must be green.
4. After merge to `dev`, Actions bumps `__version__.py` to `X.Y.Z.devN` and
   opens/updates the promote PR `dev` → `main`.
5. Squash-merge to `main` with a clear PR **title** (that title becomes the
   CHANGELOG entry). Prefer `feat:` over a newer `fix:` when both are in the PR.

Details: [docs/workflows/config-A-mirror-auto.md](docs/workflows/config-A-mirror-auto.md).

## Local checks

```sh
python -m pip install ".[dev]"
ruff check .
coverage run -m unittest discover -s tests -v
coverage report
```

Or: `docker compose up --build` and hit `/health`, `/version`.

## Issues

Use the issue templates (bug / feature). Security issues: see [SECURITY.md](SECURITY.md).

## Code of conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
