# Handover 007 - 2026-10-05

## Brand Follow-up

- Removed the guideline-derived first-person `500-800-word range` claim from generated pitch composition. The operator-declared proposed length remains, and structured `word_min`/`word_max` remain in report rows.
- Updated the README sample to the neutral sentence `The proposed length is 700 words.`
- Added a regression checking the README example and rendered draft fields for `500-800`, `word range`, and “within the stated”.
- Regenerated deterministic expected JSON/Markdown/CSV artifacts; only generated pitch text changed.

## Verification

- 159 tests passed locally and in the isolated installed environment.
- Wheel built and installed, installed CLI returned zero requests, all three output hashes matched goldens, and draft-range/editorial-claim scans were clean.
- Exact commands and hashes: `/home/yaron/projects/article-pitch-shortlist/VERIFICATION.md`.
- No live request, remote, push, publication, or submission occurred.

## Remaining Gate

- Fresh independent QA/brand re-review remains pending. Do not publish until both approvals are recorded.
