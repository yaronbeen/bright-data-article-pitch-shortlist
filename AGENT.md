# Agent Guide

## Start Here

1. Read the newest file in `/home/yaron/projects/article-pitch-shortlist/handover/`.
2. Review P0 items in `/home/yaron/projects/article-pitch-shortlist/TECH_DEBT.md`.
3. Skim `/home/yaron/projects/article-pitch-shortlist/LEARNINGS.md`.
4. Run `python3 -m pytest -q` before changing behavior.

## Purpose And Context

This Python 3.11+ CLI turns selected article examples and literal publisher guidelines into cited fit checks, explicit exclusions, and bounded pitch drafts. It is deterministic, offline-first, and does not submit pitches. Optional SERP API live ingestion is separately gated and fake-transport verified. Web Unlocker API page exports can be imported offline; live page collection fails closed.

Distribution name and GitHub slug: `article-pitch-shortlist`. This is an independent demo. Final QA, brand, and security reviews approved the frozen candidate; independent runtime verification passed. GitHub publication checks are recorded in `/home/yaron/projects/article-pitch-shortlist/RELEASE_STATUS.md`; PyPI remains unpublished.

Historical frozen-candidate snapshot: "publication status is unpublished." This is not the current GitHub status; consult `/home/yaron/projects/article-pitch-shortlist/RELEASE_STATUS.md`.

## Architecture / Design

```text
JSON input/library -> core validation + block evidence -> deterministic report
                                                        |-> report.json
                                                        |-> pitches.md
                                                        `-> pitches.csv

approved manifest -> brightdata adapter -> normalized source library -> explicit --sources merge
```

- `/home/yaron/projects/article-pitch-shortlist/article_pitch_shortlist/core.py`: schemas, normalization, literal rules, qualification, draft composition.
- `/home/yaron/projects/article-pitch-shortlist/article_pitch_shortlist/export.py`: deterministic safe renderers.
- `/home/yaron/projects/article-pitch-shortlist/article_pitch_shortlist/brightdata.py`: local provider transport, planning, gates, and normalization.
- `/home/yaron/projects/article-pitch-shortlist/article_pitch_shortlist/cli.py`: file boundaries, flags, exit codes, atomic writes.

## Decisions Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-10-05 | Use stdlib-only deterministic rules | Reproducible offline behavior with no hidden model or key. |
| 2026-10-05 | Require exact normalized host identity | Avoid inferring that `www` or another subdomain belongs to the selected publisher. |
| 2026-10-05 | Keep live retrieval explicit and unverified | No paid call or pilot collection was performed during implementation. |
| 2026-10-05 | Fail closed for live Web Unlocker API pages | Official direct REST docs expose no verifiable effective-target or target-redirect control. |
| 2026-10-05 | Draft only ready rows from structured facts | Raw editorial quotations must remain evidence, not outbound copy. |
| 2026-10-05 | Use neutral project distribution and repository identity | The tool is a general editorial workflow helper, not a Bright Data product or endorsement. |

## Runbook / Operations

- Tests: `python3 -m pytest -q`
- Demo: `python3 -m article_pitch_shortlist analyze /home/yaron/projects/article-pitch-shortlist/fixtures/demo.json --out-dir /tmp/article-pitch-demo`
- Dry-run manifest: `python3 -m article_pitch_shortlist collect /home/yaron/projects/article-pitch-shortlist/fixtures/manifest.example.json --out /tmp/unused --dry-run`
- Never make a live request without explicit URL permission, budget confirmation, zones, key, approval hash, `--live`, and `--accept-charges`.
- Never commit private reports, approvals, receipts, provider exports, or secrets.

## API References

- https://docs.brightdata.com/api-reference/rest-api/unlocker/unlock-website.md
- https://docs.brightdata.com/api-reference/rest-api/serp/serp-api.md

## Project File Structure

- `/home/yaron/projects/article-pitch-shortlist/article_pitch_shortlist/`: production package.
- `/home/yaron/projects/article-pitch-shortlist/tests/`: acceptance tests.
- `/home/yaron/projects/article-pitch-shortlist/fixtures/`: invented demo, provider examples, and generated expected artifacts.
- `/home/yaron/projects/article-pitch-shortlist/.github/workflows/tests.yml`: Python 3.11/3.12 CI.

## References

- `/home/yaron/projects/article-pitch-shortlist/LEARNINGS.md`
- `/home/yaron/projects/article-pitch-shortlist/TECH_DEBT.md`
- `/home/yaron/projects/article-pitch-shortlist/handover/`
