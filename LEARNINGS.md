# Learnings

## Current Skills-Only Workflow - 2026-10-06

- The user explicitly retired the Python product in favor of one simple Bright Data-backed business skill. Historical application decisions below are not current operating instructions.
- Source evidence must be retrieved through configured Bright Data tools in the current agent session. Missing access means connect and stop, not use an export, mock, or another provider.
- The owned article/outline body must actually be collected before fit analysis. An unobserved URL or user facts alone are insufficient.
- Genuine guideline quotations are allowed as policy evidence; they never guarantee acceptance. An explicitly observed form or submission address can be a route without contact enrichment or clicking it.
- Official MCP setup and tools documentation was fetched on 2026-10-06. `chub` was unavailable, so current official pages were read directly. Static documentation checks do not establish live functionality.

- Independent real-data exercise: PASS for a held/excluded outcome only, not the drafting branch. Closing new contributor applications excludes that route; it does not prove all existing-contributor submissions are closed. Unknown status and missing applicable routes keep the pitch held.
- Error bodies, navigation, newsletter forms, advertising links, and unrelated activity invitations do not establish article guidelines, example-body fit, or an open submission route. A footer date is not a policy date, and a collected older article does not establish user authorship/rights.
- External evidence remains at `/home/yaron/.claude/data/brightdata-drafts/2026-10-06-brightdata-real-business-validation.md`. The public validation business is not the user's business. No source excerpts or dataset were copied into the repository, and no calls were repeated for the rule clarification.

## Historical Application Learnings

- Publisher identity is intentionally exact after hostname case/trailing-dot/port-443 normalization. `www.north.example.com` is not `north.example.com`.
- A topic hit in a heading or SERP snippet cannot establish selected-example body fit.
- Observed routes need both an allowed Markdown label and the exact publisher host; external forms remain unknown.
- Literal rule conflicts must surface as review work rather than becoming first-match exclusions.
- The report can honestly be `needs_review` while still containing a ready card and an explicit exclusion.
- Bright Data search discovery and destination retrieval are separate approval stages. A result never authorizes a follow-up request.
- Guideline quotations belong in cited evidence, never in pitch copy; capability language comes from structured operator fields.
- Only ready rows receive pitch drafts. Unresolved rows retain an explicit research task.
- Request attempts must be counted before transport dispatch; response and uncertainty counts survive later write failures.
- Provider-endpoint redirect rejection does not control target redirects or DNS resolution behind a central API.
- The Web Unlocker API direct REST docs do not expose an effective-target URL or target no-redirect control, so live page jobs fail closed in v1.
- Multi-file reports require an atomic no-clobber commit pattern plus rollback; sequential atomic writes still leave partial artifact sets.
- Unavailable guidelines and absent guidelines are distinct states; never emit both for one publisher.
- Publisher rows must retain the intermediate rule states and structured operator declarations so a qualification remains auditable after export.
- Citation bounds apply to headings and observed route links too, not only body excerpts.
- Python's `datetime.fromisoformat` accepts forms broader than the v1 contract; enforce the canonical UTC shape before parsing.
- ASCII-only boundary lookarounds can match inside Unicode words; use Unicode alphanumeric boundaries.
- Casefolded indexes can differ from original-text offsets (`ß` expands); map folded offsets back to source-character positions before clipping evidence.
- Redacting query values before deduplication can collapse distinct SERP destinations; dedupe and assign identity from the unredacted URL in memory while serializing only the redacted URL.
- Provider transports and DTOs are failure boundaries: never let arbitrary exceptions or malformed status/header/body values escape as tracebacks.
- Empty, pending, and unavailable source statuses should retain distinct unknown labels; none implies a negative editorial fact.
- Optional unstated rules must stay visible as unknowns without being promoted into hard qualification blockers.
- CSV formula-prefix detection must skip Unicode whitespace and all Unicode control characters, not just ASCII tabs/spaces.
- URL query redaction must cover source URL fields and URLs embedded in normalized Markdown text/citations, then be repeated defensively at every output renderer boundary.
- The report writer pins a no-follow output-directory fd and quarantines entries before inode-checked rollback; this avoids path swaps and preserves replacements at the rollback boundary.
- The total collection budget uses a main-thread monotonic deadline alarm. Live collection fails closed if the platform/thread cannot support it or another real-time timer is active.
# Contract Versioning And Provenance

- Additive output columns are still a contract change. Explicitly version the CSV and record why the old fixed schema was insufficient; do not silently extend a published header.
- Report-wide provenance and row-cited provenance solve different problems. Keep both so an uncited output row cannot hide a synthetic source elsewhere in the report.
- Use contract receipt states verbatim (`complete`, not `succeeded`) across serialized JSON, CLI output, and tests. Keep transport attempt/response uncertainty as separate accounting fields when they convey information the completion enum does not.
- In pitches, distinguish proposed copy length from publisher requirements, and paraphrase only guideline constraints that were actually cited. Never reuse acceptance-language phrases from a guideline.
- Renderer placeholders are literal contract text: do not add explanatory clauses that change the required marker. Markdown escaping is separate presentation behavior and needs an assertion against the visible placeholder text.
