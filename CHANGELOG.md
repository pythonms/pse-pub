# Changelog

## [Unreleased]

















## [0.1.34] - 2026-11-09

### Changes
- Merge pull request #7 from pythonms/clean-up

## [0.1.33] - 2026-11-09

### Changes
- drop gha-workflows inheritance, restore local workflows

## [0.1.32] - 2026-11-09

### Bug Fixes
- restore Dev Build / Main Release wrappers on local reusable workflows

## [0.1.31] - 2026-11-09

### Bug Fixes
- vendor gha-workflows locally instead of cross-repo uses

## [0.1.30] - 2026-11-09

### Bug Fixes
- close remaining CI security findings except action SHA pins

## [0.1.29] - 2026-11-09

### Bug Fixes
- harden main-release with CI gate and Trivy before pub sync

## [0.1.28] - 2026-11-09

### Bug Fixes
- apt-get upgrade base image packages for Trivy zlib CVEs

## [0.1.27] - 2026-11-09

### Bug Fixes
- run container as non-root user for Trivy DS-0002

## [0.1.26] - 2026-11-09

### Bug Fixes
- pin Trivy action to v0.36.0 tag

## [0.1.25] - 2026-11-09

### CI
- add Trivy filesystem and image scans on Dev Build

## [0.1.24] - 2026-11-09

### CI
- split Build & Release back into Dev Build and Main Release

## [0.1.23] - 2026-11-09

### Bug Fixes
- repair YAML in build-and-release COMMIT_MESSAGE env

## [0.1.22] - 2026-11-09

### CI
- merge Dev Build and Main Release into one Actions workflow

## [0.1.21] - 2026-11-09

### Chores
- refresh FLOW_PROBE for workflow test

## [0.1.20] - 2026-10-19

### Changes
- clean up

## [0.1.19] - 2026-10-18

### Changes
- Dev (#5)

## [0.1.18] - 2026-10-18

### Changes
- Merge branch 'main' of https://github.com/pythonms/pse-priv

