# Fail-Closed Ingestion And Transactional Output

## Problem

The first adapter implementation counted requests only after transport returned, exposed SERP query values in plans and receipts, treated atomic file writes as a transactional three-file report, and allowed live Web Unlocker API page requests without a documented way to verify provider-side target redirects or effective DNS resolution. Pitch drafts also copied raw guideline sentences into outbound copy.

## Symptoms

- A timeout recorded zero requests even though dispatch had begun.
- A later output failure lost request and uncertainty accounting.
- A failure writing the second report file left the first file behind.
- A report-directory swap could split one transaction across directories.
- A post-commit target replacement could be unlinked by an unconditional rollback.
- A partial staging-write failure could leave an unregistered temporary file.
- Private search terms appeared in planned URLs and receipts.
- Raw editorial language appeared verbatim in generated pitches.

## Failed Assumptions

- Client-side redirect disabling protects only the call to `api.brightdata.com`; it does not constrain provider-side target navigation.
- Three individually atomic renames are not one atomic report transaction.
- A pathname re-resolved during rollback may name a different directory or inode than the one committed.
- Counting after a callable returns cannot distinguish no dispatch from uncertain completion.
- Exact guideline evidence is safe evidence but not automatically safe or natural pitch copy.

## Solution

- Count `requests_attempted` immediately before dispatch and `responses_received` immediately after a response returns.
- Carry `completion_unknown` through receipts and CLI write errors.
- Enforce the approval retention ceiling before dispatch and again before appending normalized records.
- Redact every query value in plans, receipts, query metadata, and retained result URLs; reject all live page target query strings.
- Apply query-value redaction in shared URL canonicalization, normalized page text/Markdown links, offline Web/SERP imports, submission routes, and JSON/Markdown/CSV renderers.
- Keep SERP API live collection on its fixed Google target, but fail closed for live Web Unlocker API pages.
- Pin the report directory through a no-follow dirfd. Stage via dirfd with exclusive creation, record device/inode identities, commit with no-clobber hard links, and roll back only targets whose identities still match. Move a rollback candidate into a randomized quarantine name before checking/unlinking it; restore and preserve raced replacements, and retain unrecovered backups rather than deleting them.
- Remove partially staged files by their recorded identity if a write/flush fails before the staging entry is registered.
- Enforce a monotonic 75-second deadline with a temporary interrupting real-time alarm around blocking custom transports and urllib connection/read calls. Fail closed outside the supported main-thread POSIX environment or if a process timer is already active.
- Build pitch copy only for ready rows from observed article facts and structured operator declarations. Keep guideline quotations in evidence.

## Root Cause

The initial implementation treated provider transport security, artifact-level atomicity, and brand-safe composition as local helper concerns. They are whole-operation invariants and need dedicated regression tests at their actual boundaries.

## Prevention

- Keep adapter failure tests checked in beside acceptance tests.
- Keep explicit PS01-PS11 and applicable C01-C20 tests checked in; do not rely on an informal mapping from unrelated test names.
- Compare renderer output and subprocess CLI files byte-for-byte with reviewed golden artifacts.
- Re-read the official direct REST OpenAPI pages before enabling a new live kind.
- Require explicit accounting assertions for timeout, HTTP failure, and persistence failure.
- Test filesystem directory swap, post-commit replacement, replacement at rollback removal, partial-stage write, symlink, and second-commit failure paths.
- Test both slow custom transports and local slow-trickling HTTP reads against a monotonic total deadline.
- Keep evidence rendering and outbound-copy composition separate.
