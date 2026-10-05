# Release Status

Date: 2026-10-05

## Final Reviews

- QA: SHIP/APPROVE.
- Brand: SHIP/APPROVE.
- Security: APPROVE.
- Independent runtime verification: PASS; no reproducible blocker observed within scope.
- No review remains pending for the frozen candidate.

## Verified Candidate

- Source suite: 159 passed. Exact frozen-wheel-installed suite: 159 passed.
- Offline installed CLI: zero requests and zero socket connection attempts.
- Three outputs matched the fixture goldens byte-for-byte; compile checks and isolated dependency checks passed.
- All 37 candidate hashes matched before and after independent verification.
- Frozen wheel SHA-256: `7aa14ef56505d80074fbae9a1fbd85703bd9c1be46d3db6331afc94f7d594990`.
- Publication preparation changes documentation and one runtime-built synthetic URL expression in `/home/yaron/projects/article-pitch-shortlist/tests/test_contract_matrix.py:655`. Production, fixtures, packaging, CI, and expected behaviors are unchanged. The exact test diff and superseded hash are recorded in `/home/yaron/projects/article-pitch-shortlist/VERIFICATION.md`; the new 21-file manifest is `/home/yaron/projects/article-pitch-shortlist/RELEASE_FILES.sha256`. The frozen wheel is verification evidence, not a newly built published artifact.

## Publication

- Published public repository: https://github.com/yaronbeen/article-pitch-shortlist
- Authenticated owner and access checked; target returned HTTP 404 and was absent from the authenticated owner inventory before creation.
- Historical first commit attempt: rejected by TruffleHog for a synthetic dummy-userinfo URI in one rejection test (zero verified secrets, one unverified finding). No commit was created by that attempt.
- Fresh full suite after the sole test rewrite: `159 passed in 5.66s`. The exact same URL still fails the original pytest assertion and direct validation with `URL must be an absolute credential-free HTTPS URL`.
- The tests require historical unpublished-status phrases; these remain explicitly labeled as historical in the README and agent guide, not as current status claims.
- Intended inventory: 40 files, including the new 21-file runtime/test manifest. Private independent evidence, venv, builds, egg-info, and caches are excluded. All 17 private/build/venv/cache ignore probes previously passed.
- Hook false positive resolved: the unchanged normal pre-commit hook scanned the full staged inventory and reported `No secrets detected. Proceeding with commit.` No exception, bypass, or scanner configuration change was applied.
- All 21 manifest entries validate. Bounded staged scan: 40 blobs, zero matches; exact test-only reverse substitution restores the original frozen test-file hash, proving no other test line changed.
- Normal commit succeeded and `main` was pushed: code commit `d681ed1db20801acc27ef1b80847138175693ef0`. The failed earlier attempt was not amended. Repository API confirms `private: false`, `visibility: public`, default branch `main`, and owner admin/push access; remote main matched this code commit.
- Public README was fetched successfully without authentication. A fresh unauthenticated HTTPS clone at `/tmp/opencode/article-pitch-publication-20261005/article-pitch-shortlist` matched the code commit and passed `159 tests in 5.73s`, all 21 manifest hashes, the committed-file inventory/secret-pattern audit, and package/test compile checks. Clone worktree remained clean.
- Clean-clone offline CLI returned `pitch_shortlist`, `needs_review`, and zero requests. All three outputs matched goldens byte-for-byte by equality and `cmp`; the socket-denied repeat also matched and recorded zero connection attempts. Existing-output and missing-input checks returned structured `invalid_input`, exit 2, and zero requests without changing artifacts or creating missing outputs; dry-run returned 0 without writes.
- GitHub CI for the code commit passed on Python 3.11 and 3.12, including package install, tests, installed CLI version, and offline analysis: https://github.com/yaronbeen/article-pitch-shortlist/actions/runs/37353698230
- The final publication-evidence commit changes documentation only; the code commit, sole test rewrite, and 21-file manifest remain unchanged. Its latest workflow status is available on the repository's Actions page.
- PyPI and GitHub binary release artifacts are not published by this pass.

## Limitations

- No authenticated Bright Data call or paid live request was made. SERP live behavior remains unverified; request serialization/parsing is fake-transport tested.
- Live Web Unlocker page collection remains fail-closed.
- Reviews and bounded secret-pattern scans are not guarantees against untested security/privacy failures or sensitive free text.
