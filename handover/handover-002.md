# Handover 002 - 2026-10-05

## What Changed

- Added 24 brand/security regression tests; the full suite now has 37 tests.
- Removed raw guideline quotations from pitch copy and added neutral capability language from structured proposal fields.
- Restricted drafts to ready rows and preserved research tasks elsewhere.
- Added accurate mixed-provenance Markdown and CSV evidence provenance.
- Made untrusted Markdown fields inert and single-line.
- Added retention checks before requests and before source append.
- Added `requests_attempted`, `responses_received`, and `completion_unknown` accounting through transport and output failures.
- Added fixed operation deadlines, 429/redirect/timeout tests, query redaction, and all-page-query rejection.
- Disabled live Web Unlocker API page collection because official direct REST docs expose no effective-target or target-redirect verification mechanism.
- Replaced sequential report writes with staged no-clobber commits and rollback; added symlink and race tests.
- Added `*.private.json` ignores, pinned development dependencies, official direct REST references, updated expected artifacts, and a security solution note.

## Verification

- Working environment: 37 tests passed.
- Fresh isolated environment: 37 tests passed.
- Compile, wheel build, package install, module CLI, installed CLI, dry-run, offline import, deterministic hashes, private-file ignores, and secret-shaped scan verified.
- Exact commands and outputs: `/home/yaron/projects/article-pitch-shortlist/VERIFICATION.md`.

## Current State

- Offline analysis is verified and deterministic.
- Live SERP API code is fixed-host, redacted outside dispatch, retention/deadline gated, and fake-transport tested.
- Live Web Unlocker API page collection is fail-closed. Offline authorized export import remains available.
- No paid request, remote, push, publication, email, or submission occurred.

## Remaining Gate

- Independent finished-artifact brand/security re-review is still required before public release. This nested agent session could not launch a separate reviewer because the task service reported its subagent depth limit.
