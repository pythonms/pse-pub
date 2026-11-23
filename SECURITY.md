# Security Policy

## Supported versions

Only the latest release on [pse-pub](https://github.com/pythonms/pse-pub)
(`main` / newest `vX.Y.Z` tag) receives security fixes.

| Version | Supported |
|---------|-----------|
| Latest `vX.Y.Z` on pse-pub | Yes |
| Older releases | No |
| `.devN` checkpoints on pse-priv | No (development only) |

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

1. Prefer [GitHub Security Advisories](https://github.com/pythonms/pse-priv/security/advisories/new)
   on this repository, or
2. Contact the repository owner via GitHub.

Include:

- Description of the issue and impact
- Steps to reproduce or a proof of concept if possible
- Affected version / commit if known

You should receive an acknowledgement within a few days. We will coordinate a
fix and, when appropriate, a public disclosure after a patch is available.

## Scope

In scope: the FastAPI demo app, Docker image, and release/sync tooling in this
repository. Out of scope: third-party dependencies’ upstream bugs (please report
those upstream; we will upgrade when feasible).
