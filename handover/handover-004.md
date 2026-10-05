# Handover 004 - 2026-10-05

## What Changed

- Continued the release-fix loop with tests first, then corrections for the remaining edge cases.
- Non-stated originality/worked-example rules remain unknown but do not block an otherwise-ready pitch.
- Empty, pending, unavailable, and unsupplied guidelines now have distinct states.
- Arbitrary transport exceptions and malformed response DTOs become safe receipts; invalid SERP title/snippet text is excluded with accurate counts.
- SERP URL query values remain redacted without merging distinct destinations.
- Reports and Markdown evidence now state transport contract version and provenance.
- CSV formula protection now recognizes Unicode whitespace/control prefixes.
- Unicode case-fold expansion offsets map back to source text, preserving a bounded citation hit.
- IP-literal validation uses an explicit branch and returns the intended safe validation error.
- Added a regression ensuring an operator field cannot reintroduce a raw cited guideline sentence into a pitch.
- README now describes the soft, non-cancelling aggregate deadline accurately.

## TDD And Verification

- Added regressions before each change; observed RED for optional-rule readiness, provider DTO/text failures, Unicode excerpt offsets, CSV Unicode whitespace, explicit IP-literal errors, and operator-reintroduced raw guideline text.
- Final suite: 105 tests green locally and in `/tmp/article-pitch-matrix-venv-20261005`.
- Package install, explicit wheel build, module/installed CLI, offline no-key demo, golden hashes, private-file ignore checks, and secret scan verified.
- Full commands/results/hashes are recorded in `/home/yaron/projects/article-pitch-shortlist/VERIFICATION.md`.

## Current State

- Offline behavior and fake-transport SERP API paths are verified.
- Live Web Unlocker API page collection remains fail-closed because official direct REST documentation provides no effective-target/no-redirect verification mechanism.
- The 75-second synchronous budget is soft, not hard cancellation; this is disclosed in README and receipts preserve uncertainty.
- No live paid request, remote, push, publication, email, or submission occurred.

## Remaining Gate

- Independent finished-artifact review remains required before public release. Reviewer dispatch was attempted and blocked by the task service's nested subagent-depth limit.
