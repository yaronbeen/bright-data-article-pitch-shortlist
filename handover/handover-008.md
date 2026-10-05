# Handover 008 - 2026-10-05

## Brand Appendix Fix

- Rendered Markdown/report JSON no longer includes raw text from any `submission_guidelines` citation, regardless of wording. It uses the exact §3.2 omission marker and retains source ID, block ID, URL, date, hash, and structured decision fields. CSV remains fixed to schema 1.1 without citation quotes.
- Exact §3.2 marker in JSON: `[editorial guideline wording omitted; structured rule state retained]`; Markdown renders the escaped form. The former extra `; classified as guidance` text is removed.
- Added regressions for varied paraphrased acceptance/approval/guarantee/length claims across every renderer.
- The README pitch example uses operator-declared length wording only; the guideline-derived range remains structured, not in the pitch.

## Verification

- 159 tests passed locally and in the isolated installation.
- The neutral distribution installs, `pip check` passes, installed CLI is offline (`requests_made: 0`), and all three goldens match.
- Secret and exact-claim scans are clean.
- Current wheel SHA-256: `f4bf95dbabec87311dc3009f767bcbf12451fd5bea48c409b5b9a0f394dbbbd5`. Exact test commands/golden hashes: `/home/yaron/projects/article-pitch-shortlist/VERIFICATION.md`.

## Remaining Gate

- Fresh QA and brand re-review remains pending. Do not publish until their approval is recorded.
- No live paid request, remote, push, publication, email, or submission occurred.
