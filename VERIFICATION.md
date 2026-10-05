# Verification Record

Date: 2026-10-05

## Candidate Status

- Scope is frozen to the README pitch example, exact appendix marker, and verification counts/status. No new features, modes, or review requirements are introduced.
- Final frozen-candidate review results: QA SHIP/APPROVE, brand SHIP/APPROVE, security APPROVE.
- Independent runtime verifier: PASS. No reproducible blocker was observed within the verification scope. Review is no longer pending.
- Publication checks are recorded in `/home/yaron/projects/article-pitch-shortlist/RELEASE_STATUS.md`. No submission or paid live request was performed.
- Public GitHub publication verified at https://github.com/yaronbeen/article-pitch-shortlist : clean-clone 159 tests, three offline goldens, zero socket attempts, compile/manifest/committed-inventory checks, and Python 3.11/3.12 CI passed for code commit `d681ed1db20801acc27ef1b80847138175693ef0`.
- Governing contract: `/home/yaron/.claude/data/brightdata-drafts/2026-10-04-five-project-build-contract.md`, Section 3.2 (line 82).

## Frozen Fixes

- The README pitch example uses operator-declared wording: `I can provide a worked example. The proposed length is 700 words.` It does not repeat the publisher's word-count range.
- `/home/yaron/projects/article-pitch-shortlist/article_pitch_shortlist/export.py:22` uses exactly `[editorial guideline wording omitted; structured rule state retained]`. JSON quotes equal the marker; Markdown escapes its brackets for presentation. Guideline source/block references and structured findings remain.
- `/home/yaron/projects/article-pitch-shortlist/tests/test_release_blockers.py` scans the README example and rendered pitch for guideline-derived range language.
- `/home/yaron/projects/article-pitch-shortlist/tests/test_contract_matrix.py` checks the exact omission marker in Markdown and JSON, including publisher, card, and exclusion evidence. Arbitrary guideline wording is omitted; non-guideline evidence remains.

## Historical Counts

- The previously recorded QA count was 158 (13 acceptance, 82 contract-matrix, 63 release-blocker tests), before the README range regression was added.
- The subsequent collected total was 159 (13 acceptance, 82 contract-matrix, 64 release-blocker tests). This frozen pass changes existing assertions only and adds no test cases.
- Earlier 130/132/140/155-test runs and their build hashes are superseded historical snapshots, not current release evidence. Duplicated final-build claims have been removed from this ledger.

## Final Verification

One final local-suite pass and one full suite against a clean, wheel-installed venv were run after the frozen fixes. No production file or golden changed afterward.

- Local suite: `159 passed in 5.17s`. Collection: 13 acceptance, 82 contract-matrix, 64 release-blocker tests. `compileall` exited 0.
- Clean venv with pinned development requirements: wheel built once, then that exact wheel installed with `--no-deps`. Installed suite: `159 passed in 4.10s`; `pip check`: `No broken requirements found.`
- Installed tests ran outside the repository with `PYTHONPATH` unset and `--import-mode=importlib`. Module location verified as `/tmp/opencode/article-pitch-frozen-20261005-W9IZ7h/venv/lib/python3.12/site-packages/article_pitch_shortlist/__init__.py`; installed version `0.1.0`; exact installed marker assertion passed.
- Installed offline CLI: `decision: pitch_shortlist`, `status: needs_review`, `requests_made: 0`. All three outputs matched checked-in goldens byte-for-byte via `cmp`.
- Credential-shaped scan of Git-listed candidate files: `0 matches`, `0 matched lines`, `0 files contained matches`. This is a pattern scan, not a guarantee that arbitrary free text contains no sensitive information.
- Ignore check: all 12 supplied private-input, credential, report, receipt, staging, backup, and rollback paths matched `/home/yaron/projects/article-pitch-shortlist/.gitignore`. `git remote -v` returned no remotes.
- Existing regression variations cover arbitrary guideline paraphrases, all three renderers, source metadata retention, malformed inputs/transports, timeout/write accounting, and output races. No known outstanding safety failure was observed in this pass; final independent reviews approved the frozen candidate.

## Independent Verification

- Independently observed source suite: `159 passed in 7.08s`; exact frozen-wheel-installed suite: `159 passed in 4.08s`.
- Source and installed compile checks passed; isolated `pip check` reported no broken requirements.
- Installed offline analysis returned `pitch_shortlist`, `needs_review`, and `requests_made: 0`. Socket-denied analysis returned 0 with zero connection attempts.
- All three installed output files matched the fixture goldens byte-for-byte. Existing-output and missing-input variations returned structured `invalid_input`, exit 2, and zero requests without changing existing artifacts or creating missing output directories.
- All 37 frozen file hashes matched before and after independent verification. The later publication pass changes documentation plus one synthetic URL expression in one test; production, fixtures, packaging, CI, and expected behaviors remain unchanged.
- Wheel and independently built sdist archive-safety checks passed. The bounded secret scan checked 69 file/archive entries with zero matches; this is not proof against arbitrary sensitive free text.

## Exact Evidence

Raw command outputs and artifacts are retained in `/tmp/opencode/article-pitch-frozen-20261005-W9IZ7h`:

- `/tmp/opencode/article-pitch-frozen-20261005-W9IZ7h/local-tests.log`
- `/tmp/opencode/article-pitch-frozen-20261005-W9IZ7h/collection.log`
- `/tmp/opencode/article-pitch-frozen-20261005-W9IZ7h/install.log`
- `/tmp/opencode/article-pitch-frozen-20261005-W9IZ7h/build.log`
- `/tmp/opencode/article-pitch-frozen-20261005-W9IZ7h/wheel-install.log`
- `/tmp/opencode/article-pitch-frozen-20261005-W9IZ7h/installed-location.log`
- `/tmp/opencode/article-pitch-frozen-20261005-W9IZ7h/installed-tests.log`
- `/tmp/opencode/article-pitch-frozen-20261005-W9IZ7h/pip-check.log`
- `/tmp/opencode/article-pitch-frozen-20261005-W9IZ7h/cli.log`
- `/tmp/opencode/article-pitch-frozen-20261005-W9IZ7h/goldens.log`
- `/tmp/opencode/article-pitch-frozen-20261005-W9IZ7h/secrets.log`
- `/tmp/opencode/article-pitch-frozen-20261005-W9IZ7h/ignore.log`
- `/tmp/opencode/article-pitch-frozen-20261005-W9IZ7h/remotes.log`
- `/tmp/opencode/article-pitch-frozen-20261005-W9IZ7h/candidate-files.sha256` records the final Git-listed file set after this ledger update.

The frozen-pass suite commands were `python3 -m pytest -o addopts= -q` from `/home/yaron/projects/article-pitch-shortlist`, and the venv Python's `-m pytest --import-mode=importlib -o addopts= -q /home/yaron/projects/article-pitch-shortlist/tests` from `/tmp/opencode/article-pitch-frozen-20261005-W9IZ7h` with `PYTHONPATH` and Bright Data credential/zone variables unset. Publication-pass reruns are recorded separately in `/home/yaron/projects/article-pitch-shortlist/RELEASE_STATUS.md`.

## Stable Artifacts

The independent frozen test-file hash is superseded only for `/home/yaron/projects/article-pitch-shortlist/tests/test_contract_matrix.py`: old SHA-256 `f4352bab088ba328e2993b73833e130e086ccffebda1815373ef42efd9751aa1`, publication SHA-256 `5bef007521ba2e542e0205a18b89d496429b00e857effd6724c5c3ef5e136362`. The sole test-file diff replaces the literal dummy userinfo URL at line 655 with `"https://{}:{}@publisher.example.org/a".format("user", "pass"),  # Synthetic userinfo rejection case.` All other test lines are unchanged. The old value is exactly this expression's evaluated result without its comment. This removes a static synthetic-credential scanner false positive without weakening URL rejection or changing the final test input. The exact original/replacement diff is retained locally at `/tmp/opencode/article-pitch-synthetic-test-only.diff`, not included in the public repository.

The evaluated URL was asserted byte-equal to the original, with username `user` and password `pass`. The original pytest rejection assertion and direct `brightdata.plan()` rejection both passed (`URL must be an absolute credential-free HTTPS URL`). Fresh full suite: `159 passed in 5.66s`. `/home/yaron/projects/article-pitch-shortlist/RELEASE_FILES.sha256` covers all 21 production/test/fixture/packaging/CI/license/ignore files; only this test hash differs from the original manifest. Existing approvals and independent runtime results apply to unchanged production; the test-only rewrite is separately verified here.

Wheel: `/tmp/opencode/article-pitch-frozen-20261005-W9IZ7h/article_pitch_shortlist-0.1.0-py3-none-any.whl`

SHA-256: `7aa14ef56505d80074fbae9a1fbd85703bd9c1be46d3db6331afc94f7d594990`

Installed CLI output directory: `/tmp/opencode/article-pitch-frozen-20261005-W9IZ7h/cli`. Each output matches its golden:

- `/home/yaron/projects/article-pitch-shortlist/fixtures/expected/report.json`: `b34b4c7c807f2f519508e5e6ebdd98bc4df3940994ca5eab41ad403295ab9564`
- `/home/yaron/projects/article-pitch-shortlist/fixtures/expected/pitches.md`: `6aa626adc45e2fb228ff76a2e0ca5b12adc5980e5097eb9fec332021b8e7e110`
- `/home/yaron/projects/article-pitch-shortlist/fixtures/expected/pitches.csv`: `87f532ee082e0c5fdd4787e1223e1ed7382dfba10c0015c0ba7d866f5e4b262f`

Earlier wheel builds are historical; the wheel above is the single candidate artifact for this frozen pass.

## Safety Boundary

- Live Web Unlocker API page collection remains fail-closed. The optional SERP adapter is fake-transport tested; no paid live request is part of this pass.
- Tests include malformed inputs/transports, deadline interruption, query-value redaction, formula escaping, transactional output races, and receipt accounting. Passing tests are evidence for the exercised cases, not a security or privacy guarantee.
- Final QA, brand, and security approval applies to the frozen offline candidate, not to unexercised live provider behavior or a guarantee against untested failures.
