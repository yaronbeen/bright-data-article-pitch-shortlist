# Skill Validation: pitch-fit-personalizer

Date: 2026-10-05. Python: 3.12.3. Scope: README/documentation/skill exercise only; no production, test, package, configuration, fixture, VERIFICATION or release-hash changes. No commit, push, remote, live/paid call, new model, or global skill installation.

## Actual CLI Evidence

Read the actual README, current input fixture and expected report first. `publishers` is the authoritative row list; `cards`/`excluded` repeat those decisions. Guideline evidence intentionally uses neutral placeholders rather than verbatim quotations.

Working directory: `/home/yaron/projects/article-pitch-shortlist`. Executed the actual `article_pitch_shortlist.__main__` with these arguments through `/tmp/opencode/five-repo-skill-check.py`, with socket/DNS/HTTP audit events denied:

```bash
python3 -m article_pitch_shortlist analyze /home/yaron/projects/article-pitch-shortlist/fixtures/demo.json --out-dir /tmp/opencode/skills-20261005-article_pitch_shortlist/demo
```

- Exit `0`: `status=needs_review`, `decision=pitch_shortlist`, `requests_made=0`; network attempts `0`.
- Generated JSON/Markdown/CSV match all three expected artifacts byte-for-byte.
- Recomputed all `6` source hashes with the repo's normalizer; checked `6` unique exact article refs and `3` unique neutral guideline locators. Placeholder text is intentionally NOT asserted to be a source substring; its source role and actual block existence were checked separately.
- Generated report SHA-256: `b34b4c7c807f2f519508e5e6ebdd98bc4df3940994ca5eab41ad403295ab9564`.
- `--dry-run`: exit `0`, zero requests, no output directory. Same destination without overwrite: structured exit `2`, original three hashes unchanged.
- Raw CLI arguments/results and artifact hashes: `/tmp/opencode/skills-20261005-article_pitch_shortlist/cli-evidence.json`. These temporary logs are local session evidence, not portable skill inputs; checked-in fixtures reproduce the report.

## Skill Exercise And Variations

The main assistant followed [the skill](../../skills/pitch-fit-personalizer/SKILL.md) on the freshly generated report and wrote [the checked card](pitch-fit-personalizer-example.md). This is a manual instruction exercise, not a deterministic skill runner or a new model/API call. Exact opening/proposal substrings, state/length/route, locator/hash and neutral-guideline checks are part of the documentation audit.

- Demo: only North gets the bounded personalization card. Planned length `700` is operator-declared; observed `500`-`800` bounds and originality/worked-example states are kept outside the draft. Guideline wording is not reconstructed. West is excluded; East is held with all unknowns.
- Actual missing-guidelines variant `/tmp/opencode/skills-20261005-article_pitch_shortlist/missing-guidelines/report.json`: North's selected guideline list is empty, qualification `needs_guideline_or_route_check`, pitch null. Skill output: "No ready publisher: hold North and East for guideline/route review; keep West excluded. No draft or guessed contact."
- Actual hostile-source variant `/tmp/opencode/skills-20261005-article_pitch_shortlist/hostile-source/report.json`: publisher rows/decision unchanged; affected snapshot hash changes. Skill disposition: "Ignore article instructions; retain the cited opening and pre-submission checklist. No contact lookup, route visit or submission."
- Report-level `needs_review` does not invalidate North's ready row, and a ready row does not predict acceptance.

## Documentation Audit

`/tmp/opencode/check-five-repo-skill-docs.py` returned PASS: standard name/description front matter, folder/name match, all `10` local links, ASCII/whitespace checks, and the five-file review inventory. The card has `3` exact article quote refs and `6` valid source/block locators, including three neutral guideline locators. Every cited hash/URL/date resolves to the generated report; opening/contribution are exact draft substrings; row states, unknowns, route and declared-originality label match. Omitted guideline wording is not reconstructed. This is a mechanical consistency audit, not independent approval. `git diff --check` passed for the README change.

For repeat CLI replay, choose a fresh output directory; the recorded paths already contain this session's outputs. Temporary session logs may later be removed. The skill itself needs only the operator's local report.

## Limits And Review

No actual publisher interest, acceptance likelihood, contact, original authorship, current route validity, live provider behavior or outreach result was verified. One manual hostile-input exercise is not a prompt-injection guarantee across agents.

[The stable review manifest](review-manifest.txt) includes README and the four skill/doc files. The initial skill pass left independent approval pending; that historical state is superseded by the record below. Historical release statements remain intact; the approval below is for the frozen skills/README sections, not inferred from older code approvals.

## Approved Integration

On 2026-10-05, the user reports that all three independent reviewers APPROVE the five frozen skills/README sections under the lightweight showcase standard (user-reported). Reviewer artifact paths were not supplied. Reviewed input: `/tmp/opencode/five-repo-skill-review-20261005.json`, SHA-256 `0bc5f74f49b71eda3898ad4a0229612e06841a5acd7e599006a77fc8f2b353e2`. The original manifest is retained as review history, not overwritten.

The approved skill section is retained verbatim. The README's current GitHub slug/link now uses `yaronbeen/bright-data-article-pitch-shortlist`; the package/CLI `article-pitch-shortlist`, module `article_pitch_shortlist` and local directory are unchanged. The independent-demo/PyPI caveat and non-endorsement statement are retained. Skill instructions and the checked example are byte-identical to the reviewed snapshot; no outputs or features were expanded. The actual remote rename remains owned by the separate rename worker; no remote operation was performed here.

Integration validation uses only simple front matter, local links, cited-sample checks and one offline demo replay. The three generated artifacts match the existing goldens; the demo reports zero requests. No new TDD matrix, framework, source/test/package/configuration/core VERIFICATION change, staging, commit, push, remote operation or global installation is part of this pass. Final four-repo documentation hashes, exact intended diffs and the staging list are recorded separately at `/tmp/opencode/four-repo-skills-final-20261005.json`.

Approval concerns the lightweight showcase artifacts, not live Bright Data behavior, publisher interest, acceptance probability, verified authorship, current route validity or outreach results. No pitch was sent; this integration does not claim that the local documentation changes have been pushed.
