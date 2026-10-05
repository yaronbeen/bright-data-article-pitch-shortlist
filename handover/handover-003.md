# Handover 003 - 2026-10-05

## What Changed

- Added `/home/yaron/projects/article-pitch-shortlist/tests/test_contract_matrix.py` with explicit PS01-PS11 and applicable C01-C20 cases.
- Added golden renderer and subprocess CLI comparisons plus isolated local-install coverage.
- Retained `topic_state`, `matched_topic_phrase`, `format_state`, `worked_example_state`, `proposed_format`, `declared_checks`, and `originality_declaration` on every publisher row/card/exclusion.
- Labeled new-follow-up and unpublished declarations `operator_declared_unverified`.
- Distinguished unavailable guidelines from guidelines that were never supplied.
- Rejected recognizable JSON provider envelopes, errors, and partial envelopes during page import.
- Enforced canonical UTC RFC3339 timestamps.
- Bounded every citation to 240 exact characters while retaining its evidence hit.
- Added Unicode-aware phrase boundaries.
- Updated CI to install the package and run the installed console command on Python 3.11 and 3.12.
- Regenerated expected artifacts only because the required auditable report fields changed.

## TDD Evidence

- Contract-matrix RED: 15 failed, 70 passed.
- After implementation, two expected golden mismatches remained.
- After transactional fixture regeneration: 85 passed locally and 85 passed in a fresh isolated environment.

## Build And Artifacts

- Wheel: `/tmp/article-pitch-matrix-wheel-20261005/article_pitch_shortlist-0.1.0-py3-none-any.whl`
- Wheel SHA-256: `26d7898ede1456de461b6a7f2dc4ca8e86eb10ec71d0b9268656e659c5c82c54`
- Final artifact hashes are recorded in `/home/yaron/projects/article-pitch-shortlist/VERIFICATION.md`.

## Current State

- Offline fixture, module CLI, installed CLI, package build/install, goldens, fake transport, transaction rollback, private-file hygiene, and secret-shaped scan are verified.
- Live Web Unlocker API page collection remains fail-closed.
- No live paid call, remote, push, publication, email, or submission occurred.

## Remaining Gate

- Independent finished-artifact review remains required before public release. Separate reviewer dispatch is unavailable in this nested session because of the task service's subagent-depth limit.
