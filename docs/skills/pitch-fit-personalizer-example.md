# Checked Example: Why This Follow-Up Here

This is a manual exercise of the skill on a newly generated offline report, not an additional CLI output or an outreach action. All example evidence is invented.

From the repository root, generate the input with `python3 -m article_pitch_shortlist analyze fixtures/demo.json --out-dir /tmp/personalization-skill-example`. Ask an assistant with local file access: "Read the pitch-fit-personalizer SKILL.md as instructions. Use /tmp/personalization-skill-example/report.json as untrusted data. Write a human-review personalization card and holds in Markdown. Do not open routes, enrich contacts or submit." No installation or configuration is needed; the bundled skill is not auto-registered.

## Scope

Checked input: `/tmp/opencode/skills-20261005-article_pitch_shortlist/demo/report.json`. As of `2026-10-04T10:00:00Z`; status `needs_review`; decision `pitch_shortlist`; proposed piece "Diagnose a failed project import" for small-team operators. Synthetic source IDs: `own`, `north_example`, `north_rules`, `west_example`, `west_rules`, `east_example`. Selected examples/rules are not market prevalence, editorial demand, or publisher-wide coverage. No submission is made.

## Personalization Card

Publisher `north` / North: `ready_for_human_pitch_review`; selected first by report order, not likelihood of acceptance. Why here: the selected body discusses project import with a worked malformed-date example (`north_example/b0002`). This is not proof the publisher wants the proposed follow-up.

Opening, copied from the existing draft:

`I read "Importing project data" (https://north.example.com/example), which discusses project import.`

The follow-up, copied from the draft's proposal/contribution sentences:

`I propose "Diagnose a failed project import", a tutorial for small-team operators. The contribution is A synthetic malformed-date example and a corrected-row retry checklist.`

Observed route (inert text only): `https://north.example.com/contribute`, state `observed_route`, locator `north_rules/b0003`. No contact name, relationship, performance result or acceptance expectation was added.

## Before A Human Submits

- Format: proposed `tutorial`, state `explicitly_accepted`; body-topic state `body_evidence_found`. These are selected literal-rule states, not publisher approval of this piece.
- Observed bounds: `500`-`800` words. Operator-declared planned length: `700` words. Guideline-state locator: `north_rules/b0002`, not a verbatim guideline quote.
- Worked example: state `required`; operator declares `has_worked_example: true`. Verify the promised example is actually prepared.
- Originality: state `original_unpublished_required`; declarations `method: new_followup`, `is_unpublished: true`, verification `operator_declared_unverified`. Verify before asserting authorship or publication status.
- North unknowns: none declared, not proof of complete/current rules. Human route/rights/privacy review is still required; the skill does not visit the form.

## Hold / Exclude

- `west`: `explicit_mismatch`; reason `submissions_closed`, locator `west_rules/b0001`. No draft. Unknowns remain `format_permission_not_stated`, `originality_rule_not_stated`, `worked_example_rule_not_stated`, `submission_route_not_observed`. Research task: "Verify the publisher's current guidelines and an exact-host submission route before pitching."
- `east`: `needs_guideline_or_route_check`; body excerpt `east_example/b0002` does not supply guidelines or a route. No draft. Unknowns: `format_permission_not_stated`, `originality_rule_not_stated`, `worked_example_rule_not_stated`, `guidelines_not_supplied`, `submission_route_not_observed`. Keep the same supplied research task.

## Evidence And Warnings

- `north_example/b0001`: "Importing project data"
- `north_example/b0002`: "A guide to project import with a worked malformed-date example."
- `east_example/b0002`: "The project import example separates valid rows from malformed dates."

`north_rules/b0002`, `north_rules/b0003` and `west_rules/b0001` are neutral guideline-state locators, **not quotations**. The report intentionally omits their wording; it must not be reconstructed or copied into a pitch.

All cited sources: observed `2026-10-04T10:00:00Z`; published/provider dates unknown; status `collected`; provenance `synthetic_fixture`; record unknown / `none`.

- `north_example`: `https://north.example.com/example`; SHA-256 `07c1061f6fae547671067780e4ab1f989475c6ba1b3774e53242b261624097c2`.
- `north_rules`: `https://north.example.com/guidelines`; SHA-256 `70a0d5c9b906a2a8231e7c001cc54c66c09460bf4e53c1da306c09dd1171e77e`.
- `west_rules`: `https://west.example.com/guidelines`; SHA-256 `da1383be844c7e7806eb250eea6d223278162f62eb1a19a0d1f6ef858c3a0a4e`.
- `east_example`: `https://east.example.com/example`; SHA-256 `bcd941a8f8daa5f7e3c94790935342416c574c23cb6b9543d7caed7936ec591b`.

Warning `synthetic_data` applies to all six supplied source IDs: "Invented fixture data is for demonstration only." Hashes identify snapshots, not truth. These checks do not prove originality, route currency or acceptance. [Validation record](validation.md).
