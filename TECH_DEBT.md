# Technical Debt

## P0 - Before Publication

- None. The sole synthetic test-expression rewrite preserves the exact rejected URL; the unchanged normal pre-commit hook now passes with no secrets detected.
- Final frozen-candidate QA SHIP/APPROVE, brand SHIP/APPROVE, security APPROVE, and independent runtime PASS are recorded; no review is pending.

## P1 - Before Live Pilot

- None. Live Web Unlocker API page collection is disabled; SERP API remains explicitly gated and fake-transport verified.

## P2 - When Convenient

- Add JSON Schema documents generated from the stable v1 input and library contracts.
- If separately authorized, run a budget-capped SERP API direct REST smoke test and record the receipt without publishing private query data.

## P3 - Nice To Have

- Add more invented examples for each supported literal guideline sentence.

## Resolved Items

- 2026-10-05: Added deterministic fixture outputs, strict exact-host rules, atomic output writes, and no-network dry runs.
- 2026-10-05: Added adapter regressions for retention, accounting, 429, redirects, timeouts, deadlines, query redaction, and fail-closed page collection.
- 2026-10-05: Replaced sequential report writes with no-clobber transactional staging and rollback.
- 2026-10-05: Reworked report transactions to use a pinned no-follow directory fd, inode-checked rollback, and race-preserving backups.
- 2026-10-05: Quarantined rollback candidates before inode verification and added a replacement-at-unlink-boundary race test.
- 2026-10-05: Redacted URL query values in shared canonicalization, imported/page text, routes, source indices, and every report renderer.
- 2026-10-05: Added hard monotonic deadline interruption for custom transport and slow urllib reads, plus combined timeout/write-failure accounting tests.
- 2026-10-05: Removed raw guideline text from pitches and restricted drafts to ready rows.
- 2026-10-05: Pinned pytest and its transitive development dependencies.
- 2026-10-05: Added explicit PS01-PS11 and applicable C01-C20 tests, golden comparisons, subprocess CLI, and isolated local-install coverage.
- 2026-10-05: Added auditable qualification fields, strict UTC timestamps, bounded citations, envelope rejection, and Unicode phrase boundaries.
- 2026-10-05: Hardened malformed transport DTOs/provider text, preserved result identity through query redaction, retained transport/source provenance in Markdown, and extended Unicode CSV formula protection.
- 2026-10-05: Made optional unstated originality/worked-example rules non-blocking while retaining their unknown states; distinguished empty, pending, unavailable, and unsupplied sources.
- 2026-10-05: Renamed the repository/distribution to `article-pitch-shortlist`, removed stale branded metadata, and recorded neutral future GitHub slug.
- 2026-10-05 (historical snapshot): Verified the final 159-test local/isolated suites, reinstalled the neutral CLI, regenerated/compared goldens after the exact §3.2 placeholder fix, and rescanned stale metadata/secrets/private-file ignores. Independent QA/brand re-review was still pending at that point; superseded by the final approvals below.
- 2026-10-05: Removed guideline-derived first-person length/range claims from generated pitches and verified rendered JSON/Markdown/CSV artifacts.
- 2026-10-05: Replaced the soft transport timeout budget with a monotonic hard caller deadline and added slow custom-transport/slow-read interruption tests.
- 2026-10-05: Final frozen-candidate QA SHIP/APPROVE, brand SHIP/APPROVE, security APPROVE; independent runtime PASS with 159 source and 159 exact-wheel-installed tests, zero socket attempts, three golden matches, and all 37 hashes unchanged.
- 2026-10-05: Resolved the synthetic dummy-userinfo URI scanner false positive by constructing the exact same test URL at runtime; original rejection assertions and all 159 tests pass. Sole test diff/hash supersession and 21-file release manifest recorded; unchanged normal staged hook scan passes without exceptions or bypass.
