# Handover 012 - Rename-Fix CI Green - 2026-10-06

## What Changed

- The public GitHub repository is named `bright-data-article-pitch-shortlist` at the user's request for the `bright-data-` prefix on GitHub repository names. Commit `9dcaba7` updated the README slug but not the release-blocker identity test, so CI failed after the rename.
- Fix commit `84e26d1` (test file plus its `RELEASE_FILES.sha256` entry): `tests/test_release_blockers.py::test_distribution_and_repository_identity_are_neutral` now accepts both `article-pitch-shortlist` and `bright-data-article-pitch-shortlist` checkout directory names and asserts stable neutral identities (pyproject distribution name, version match, CLI entry point, package, README slug and neutral distribution statement). The full-tree scan still forbids the old conflated distribution identifier and the historical bright-data local path.
- The evidence for the fix is recorded in `/home/yaron/projects/article-pitch-shortlist/VERIFICATION.md` under `## Repository Rename Maintenance (2026-10-06)`.

## Current State

- Production code, fixtures, packaging, and the CI workflow are unchanged. Distribution, module, CLI, and local checkout remain neutral.
- Local source suite: `159 passed`. Offline CLI: `requests_made: 0`; all three outputs matched goldens byte-for-byte. TruffleHog commit hook and repeat scan: `verified_secrets: 0, unverified_secrets: 0`.
- CI for `84e26d1`: Python 3.11 and 3.12 both success (run 37413628879); failed run 37360241446 is superseded.

## Open Items / Next

- No production follow-up required. Historical pre-rename URLs in older documents redirect on GitHub.
- PyPI remains unpublished; live provider behavior remains outside the reviewed scope.