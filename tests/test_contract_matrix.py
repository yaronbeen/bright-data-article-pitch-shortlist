"""Explicit PS01-PS11 and applicable shared C01-C20 contract matrix."""

from __future__ import annotations

import copy
import csv
from io import StringIO
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from article_pitch_shortlist import brightdata, cli
from article_pitch_shortlist.brightdata import HttpResponse, TransportError
from article_pitch_shortlist.core import InputError, analyze, canonical_url, evaluate_publisher, normalize_text
from article_pitch_shortlist.export import render_csv, render_json, render_markdown


ROOT = Path(__file__).parents[1]


@pytest.fixture
def demo():
    return json.loads((ROOT / "fixtures" / "demo.json").read_text(encoding="utf-8"))


def evaluate(**overrides):
    values = {
        "publisher_host": "north.example.com",
        "example_url": "https://north.example.com/example",
        "example_body": "# Importing data\n\nA guide to project import.",
        "guidelines_body": "We accept tutorials. Only original, unpublished work. Word count: 500-800 words. A worked example is required.\n\n[submission form](https://north.example.com/contribute)",
        "topic_phrase": "project import",
        "proposed_format": "tutorial",
        "planned_word_count": 700,
        "has_worked_example": True,
        "method": "new_followup",
        "is_unpublished": True,
        "asset_publication_state": "published",
    }
    values.update(overrides)
    return evaluate_publisher(**values)


def serp_manifest(query="project import tutorial"):
    return {
        "schema_version": "1.0",
        "project": "article-pitch-shortlist",
        "jobs": [{
            "id": "search", "kind": "serp", "role": "discovery",
            "source_prefix": "candidate", "query": query,
            "country": "us", "language": "en",
        }],
    }


def approval_for(manifest, **overrides):
    planned = brightdata.plan(manifest)
    value = {
        "schema_version": "1.0",
        "project": "article-pitch-shortlist",
        "manifest_sha256": brightdata.manifest_sha256(manifest),
        "expires_at": "2027-01-01T00:00:00Z",
        "max_requests": planned["planned_requests"],
        "max_retained_records": planned["max_retained_records"],
        "approved_urls": [request["approved_url"] for request in planned["requests"]],
        "account_budget_confirmed": True,
        "target_permissions_confirmed": True,
        "remote_resolution_risk_accepted": True,
    }
    value.update(overrides)
    return value


def collect_serp(manifest, approval, transport):
    return brightdata.collect(
        manifest, approval=approval, api_key="test-key", zones={"serp": "zone"},
        transport=transport, now="2026-10-05T10:00:00Z",
    )


def test_ps01_fixture_north_ready_west_excluded_east_unknown_and_rows_retain_decision_fields(demo):
    report = analyze(demo)
    rows = {row["publisher_id"]: row for row in report["publishers"]}

    assert rows["north"]["qualification"] == "ready_for_human_pitch_review"
    assert rows["west"]["qualification"] == "explicit_mismatch"
    assert rows["east"]["qualification"] == "needs_guideline_or_route_check"
    assert [row["publisher_id"] for row in report["cards"]] == ["north", "east"]
    assert [row["publisher_id"] for row in report["excluded"]] == ["west"]
    required = {
        "topic_state", "matched_topic_phrase", "format_state",
        "worked_example_state", "proposed_format", "declared_checks",
        "originality_declaration",
    }
    assert all(required <= row.keys() for row in report["publishers"])
    assert all(required <= row.keys() for row in report["cards"])
    assert rows["north"]["originality_declaration"] == {
        "method": "new_followup", "is_unpublished": True,
        "verification": "operator_declared_unverified",
    }


def test_ps02_published_asset_reuse_fails_original_only_but_new_followup_is_operator_declared(demo):
    reuse = copy.deepcopy(demo)
    reuse["proposed_piece"]["method"] = "reuse_asset"
    report = analyze(reuse)
    north = next(row for row in report["publishers"] if row["publisher_id"] == "north")
    assert north["qualification"] == "explicit_mismatch"
    assert "prior_publication_disallowed" in north["exclusion_reasons"]

    new_report = analyze(demo)
    north = next(row for row in new_report["publishers"] if row["publisher_id"] == "north")
    assert north["originality_declaration"]["verification"] == "operator_declared_unverified"
    assert "new follow-up" in north["pitch_draft"]


def test_ps03_title_only_topic_match_never_qualifies():
    result = evaluate(example_body="# Project import\n\nA general operations article.")
    assert result.topic_state == "not_found"
    assert result.matched_topic_phrase is None
    assert "no_topic_evidence_in_selected_example" in result.reasons


def test_ps04_unsupported_guideline_paraphrase_remains_unknown():
    result = evaluate(guidelines_body="Tutorials are welcome. Fresh material is preferred.")
    assert result.format_state == "not_stated"
    assert result.originality_state == "not_stated"
    assert result.qualification == "needs_guideline_or_route_check"


def test_ps05_missing_external_and_conflicting_routes_are_never_guessed():
    missing = evaluate(guidelines_body="We accept tutorials.")
    external = evaluate(guidelines_body="We accept tutorials.\n\n[submit a pitch](https://forms.example.net/pitch)")
    conflicting = evaluate(guidelines_body="We accept tutorials.\n\n[submit a pitch](https://north.example.com/a) [pitch form](https://north.example.com/b)")
    assert (missing.route_state, missing.submission_url) == ("not_observed", None)
    assert (external.route_state, external.submission_url) == ("not_observed", None)
    assert "external_submission_route_requires_manual_inspection" in external.unknowns
    assert (conflicting.route_state, conflicting.submission_url) == ("conflicting_routes", None)


def test_ps06_word_count_outside_observed_range_is_explicit_mismatch():
    result = evaluate(planned_word_count=900)
    assert result.qualification == "explicit_mismatch"
    assert "stated_word_count_mismatch" in result.reasons


def test_ps07_worked_example_fails_only_when_literal_requirement_is_observed():
    required = evaluate(has_worked_example=False)
    unstated = evaluate(guidelines_body="We accept tutorials.\n\n[submission form](https://north.example.com/contribute)", has_worked_example=False)
    assert "worked_example_required_but_absent" in required.reasons
    assert "worked_example_required_but_absent" not in unstated.reasons


def test_ps08_contradictory_format_and_originality_rules_require_review():
    result = evaluate(guidelines_body=(
        "We accept tutorials. We do not accept tutorials. "
        "Only original, unpublished work. We accept republished articles.\n\n"
        "[submission form](https://north.example.com/contribute)"
    ))
    assert result.format_state == "conflicting"
    assert result.originality_state == "conflicting"
    assert result.qualification == "needs_guideline_or_route_check"
    assert "conflicting_guidelines" in result.unknowns


def test_ps09_open_format_statement_does_not_ban_other_formats():
    result = evaluate(
        proposed_format="comparison",
        guidelines_body="We accept tutorials.\n\n[submission form](https://north.example.com/contribute)",
    )
    assert result.format_state == "not_stated"
    assert "closed_format_set_mismatch" not in result.reasons
    assert "explicitly_rejected_format" not in result.reasons


def test_ps09_not_stated_optional_rules_do_not_block_otherwise_ready_pitch():
    result = evaluate(guidelines_body="We accept tutorials.\n\n[submission form](https://north.example.com/contribute)")
    assert result.qualification == "ready_for_human_pitch_review"
    assert "originality_rule_not_stated" in result.unknowns
    assert "worked_example_rule_not_stated" in result.unknowns


def test_ps10_unavailable_example_is_unknown_not_publisher_wide_mismatch(demo):
    payload = copy.deepcopy(demo)
    example = next(source for source in payload["sources"] if source["id"] == "north_example")
    example["status"] = "unavailable"
    example["text"] = ""
    report = analyze(payload)
    north = next(row for row in report["publishers"] if row["publisher_id"] == "north")
    assert north["qualification"] == "needs_guideline_or_route_check"
    assert north["topic_state"] == "source_unavailable"
    assert north["exclusion_reasons"] == []
    assert north["evidence"] == []


def test_ps11_pitch_has_only_observed_or_declared_facts_and_no_sending_fields(demo):
    report = analyze(demo)
    north = next(row for row in report["publishers"] if row["publisher_id"] == "north")
    serialized = json.dumps(report).casefold()
    assert north["pitch_draft"]
    assert north["declared_checks"] == {
        "method": "new_followup", "is_unpublished": True,
        "planned_word_count": 700, "has_worked_example": True,
    }
    assert "The proposed length is 700 words." in north["pitch_draft"]
    assert "keep the draft to 700 words" not in north["pitch_draft"]
    assert not ({"email", "recipient", "send", "mailbox"} & north.keys())
    assert '"email"' not in serialized and '"recipient"' not in serialized


def test_pitch_draft_and_all_rendered_draft_fields_omit_guideline_derived_length_claim(demo):
    report = analyze(demo)
    north = next(row for row in report["publishers"] if row["publisher_id"] == "north")
    json_report = json.loads(render_json(report))
    json_north = next(row for row in json_report["publishers"] if row["publisher_id"] == "north")
    csv_north = next(row for row in csv.DictReader(StringIO(render_csv(report))) if row["publisher_id"] == "north")
    markdown = render_markdown(report)
    markdown_draft = markdown.split("**Draft for human review**", 1)[1].split("\n\n### ", 1)[0]
    forbidden = ("word range", "500-800", "accept tutorials", "original, unpublished", "worked example is required")

    for draft in (north["pitch_draft"], json_north["pitch_draft"], csv_north["pitch_draft"], markdown_draft):
        folded = draft.casefold()
        assert all(phrase not in folded for phrase in forbidden)
    assert north["word_min"] == 500 and north["word_max"] == 800


def test_c01_positive_fixture_has_substantive_cited_business_artifacts(demo):
    report = analyze(demo)
    assert report["decision"] == "pitch_shortlist"
    assert report["cards"][0]["pitch_draft"]
    assert report["cards"][0]["evidence"]
    assert report["excluded"][0]["exclusion_reasons"] == ["submissions_closed"]


def test_c02_offline_cli_and_local_install_need_no_provider_credentials_or_network(tmp_path):
    install_dir = tmp_path / "installed"
    install = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-deps", "--no-build-isolation", "--target", str(install_dir), str(ROOT)],
        cwd=tmp_path, text=True, capture_output=True, timeout=120,
    )
    assert install.returncode == 0, install.stderr
    env = {**os.environ, "PYTHONPATH": str(install_dir)}
    for key in ("BRIGHT_DATA_API_KEY", "BRIGHT_DATA_WEB_UNLOCKER_ZONE", "BRIGHT_DATA_SERP_ZONE"):
        env.pop(key, None)
    output = tmp_path / "output"
    run = subprocess.run(
        [sys.executable, "-m", "article_pitch_shortlist", "analyze", str(ROOT / "fixtures" / "demo.json"), "--out-dir", str(output)],
        cwd=tmp_path, env=env, text=True, capture_output=True, timeout=30,
    )
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["requests_made"] == 0


def test_c02_pure_analysis_works_with_all_socket_connection_attempts_denied(monkeypatch, demo):
    def deny_network(*args, **kwargs):
        raise AssertionError("pure analysis attempted network access")

    monkeypatch.setattr(socket, "create_connection", deny_network)
    report = analyze(demo)
    assert report["decision"] == "pitch_shortlist"


def test_c03_wall_clock_and_environment_changes_do_not_change_pure_analysis(monkeypatch, demo):
    import article_pitch_shortlist.core as core

    expected = (render_json(analyze(demo)), render_markdown(analyze(demo)), render_csv(analyze(demo)))
    monkeypatch.setenv("TZ", "Pacific/Kiritimati")
    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "different-test-sentinel")

    class MovedClock:
        @staticmethod
        def fromisoformat(value):
            from datetime import datetime
            return datetime.fromisoformat(value)

        @staticmethod
        def now(*args, **kwargs):
            raise AssertionError("pure analysis read wall clock")

    monkeypatch.setattr(core, "datetime", MovedClock)
    actual_report = analyze(demo)
    actual = (render_json(actual_report), render_markdown(actual_report), render_csv(actual_report))
    assert actual == expected


def test_c03_two_runs_and_checked_in_goldens_are_byte_identical(demo, tmp_path):
    report = analyze(demo)
    expected = {
        "report.json": render_json(report),
        "pitches.md": render_markdown(report),
        "pitches.csv": render_csv(report),
    }
    for name, content in expected.items():
        assert content.encode() == (ROOT / "fixtures" / "expected" / name).read_bytes()
    first = tmp_path / "first"
    second = tmp_path / "second"
    cli._write_report_set(first, expected, overwrite=False)
    cli._write_report_set(second, expected, overwrite=False)
    assert all((first / name).read_bytes() == (second / name).read_bytes() for name in expected)


def test_pitch_csv_schema_version_and_appended_provenance_columns(demo):
    rows = list(csv.DictReader(StringIO(render_csv(analyze(demo)))))
    original_v10_columns = [
        "publisher_id", "publisher", "qualification", "exclusion_reasons",
        "fit_excerpt", "example_url", "accepted_formats", "originality_state",
        "word_min", "word_max", "route_state", "submission_url", "unknowns",
        "pitch_draft", "evidence_source_ids", "evidence_urls",
    ]
    assert rows
    assert rows[0]["schema_version"] == "1.1"
    assert list(rows[0])[:16] == original_v10_columns
    assert list(rows[0])[16:] == [
        "schema_version", "evidence_provenance", "provenance_state", "contains_synthetic_data",
    ]


def test_c04_wrong_schema_unknown_keys_bool_int_oversize_and_dangling_refs_fail(demo):
    cases = []
    wrong_schema = copy.deepcopy(demo)
    wrong_schema["schema_version"] = "2.0"
    cases.append(wrong_schema)
    unknown = copy.deepcopy(demo)
    unknown["extra"] = True
    cases.append(unknown)
    bool_int = copy.deepcopy(demo)
    bool_int["proposed_piece"]["planned_word_count"] = True
    cases.append(bool_int)
    dangling = copy.deepcopy(demo)
    dangling["publishers"][0]["example_source_ids"] = ["missing"]
    cases.append(dangling)
    oversize = copy.deepcopy(demo)
    oversize["sources"][0]["text"] = "x" * (2 * 1024 * 1024)
    cases.append(oversize)
    for payload in cases:
        with pytest.raises(InputError):
            analyze(payload)


def test_c04_generated_citations_are_not_stale_against_current_normalized_sources(demo):
    report = analyze(demo)
    sources = {source["id"]: normalize_text(source["text"])[1] for source in demo["sources"]}
    blocks = {source_id: {block["id"]: block["text"] for block in values} for source_id, values in sources.items()}
    citations = [citation for row in report["publishers"] for citation in row["evidence"]]
    assert citations
    for citation in citations:
        assert citation["block_id"] in blocks[citation["source_id"]]
        assert citation["quote"] in blocks[citation["source_id"]][citation["block_id"]]


def test_c05_unavailable_guideline_is_not_also_not_supplied_and_cannot_be_evidence(demo):
    payload = copy.deepcopy(demo)
    guideline = next(source for source in payload["sources"] if source["id"] == "north_rules")
    guideline["status"] = "unavailable"
    guideline["text"] = ""
    report = analyze(payload)
    north = next(row for row in report["publishers"] if row["publisher_id"] == "north")
    assert "guidelines_unavailable" in north["unknowns"]
    assert "guidelines_not_supplied" not in north["unknowns"]
    assert all(citation["source_id"] != "north_rules" for citation in north["evidence"])


@pytest.mark.parametrize(("source_status", "expected_unknown"), [
    ("empty", "guidelines_empty"),
    ("pending", "guidelines_pending"),
    ("unavailable", "guidelines_unavailable"),
])
def test_c05_noncollected_guideline_states_are_truthful_and_never_evidence(demo, source_status, expected_unknown):
    payload = copy.deepcopy(demo)
    guideline = next(source for source in payload["sources"] if source["id"] == "north_rules")
    guideline["status"] = source_status
    guideline["text"] = ""
    report = analyze(payload)
    north = next(row for row in report["publishers"] if row["publisher_id"] == "north")
    assert expected_unknown in north["unknowns"]
    assert "guidelines_not_supplied" not in north["unknowns"]
    assert all(citation["source_id"] != "north_rules" for citation in north["evidence"])


def test_c06_every_citation_is_exact_bounded_and_heading_never_topic_body_evidence(demo):
    payload = copy.deepcopy(demo)
    north_example = next(source for source in payload["sources"] if source["id"] == "north_example")
    north_example["text"] = "# " + ("Heading " * 40) + "\n\n" + ("prefix " * 50) + "project import" + (" suffix" * 50)
    north_rules = next(source for source in payload["sources"] if source["id"] == "north_rules")
    north_rules["text"] = north_rules["text"].replace(
        "https://north.example.com/contribute",
        "https://north.example.com/" + ("x" * 300),
    )
    report = analyze(payload)
    block_index = {}
    for source in payload["sources"]:
        _, blocks = normalize_text(source["text"])
        block_index[source["id"]] = {block["id"]: block for block in blocks}
    for row in report["publishers"]:
        for citation in row["evidence"]:
            block = block_index[citation["source_id"]][citation["block_id"]]
            assert len(citation["quote"]) <= 240
            assert citation["quote"] in block["text"]
    north = next(row for row in report["publishers"] if row["publisher_id"] == "north")
    assert "project import" in north["fit_excerpt"]
    assert north["topic_state"] == "body_evidence_found"
    route_citation = next(citation for citation in north["evidence"] if "submission form" in citation["quote"])
    assert "submission form" in route_citation["quote"]


def test_c07_provider_normalizer_drops_person_metadata_and_raw_payload():
    records = {
        "general": {"query": "project import"},
        "organic": [{
            "link": "https://publisher.example.org/article",
            "title": "Article", "description": "Project import tutorial",
            "rank": 1, "username": "private-person", "profile_url": "https://social.invalid/person",
            "author_hash": "secret-hash", "address": "private address", "replies": [{"text": "private"}],
        }],
    }
    library = brightdata.normalize_export(
        "serp", records, role="discovery", source_url="https://www.google.com/search",
        observed_at="2026-10-05T10:00:00Z", source_prefix="import",
    )
    serialized = json.dumps(library)
    for forbidden in ("private-person", "profile_url", "secret-hash", "private address", "replies"):
        assert forbidden not in serialized


def test_c07_query_redaction_does_not_merge_distinct_result_urls():
    records = {
        "general": {"query": "project import"},
        "organic": [
            {"link": "https://publisher.example.org/article?id=one", "title": "First", "description": "First result", "rank": 1},
            {"link": "https://publisher.example.org/article?id=two", "title": "Second", "description": "Second result", "rank": 2},
        ],
    }
    library = brightdata.normalize_export(
        "serp", records, role="discovery", source_url="https://www.google.com/search",
        observed_at="2026-10-05T10:00:00Z", source_prefix="import",
    )
    assert len(library["sources"]) == 2
    assert library["sources"][0]["id"] != library["sources"][1]["id"]
    assert library["sources"][0]["url"] == library["sources"][1]["url"]
    assert {source["text"] for source in library["sources"]} == {"First result", "Second result"}


def test_c08_csv_formula_and_markdown_injection_are_inert(demo):
    payload = copy.deepcopy(demo)
    payload["publishers"][0]["name"] = "\t=WEBSERVICE(\"https://evil.invalid\")"
    payload["sources"][1]["text"] = "# Importing data\n\nProject import <script>alert(1)</script>\n# forged"
    report = analyze(payload)
    csv_rows = list(csv.DictReader(StringIO(render_csv(report))))
    assert csv_rows[0]["publisher"].startswith("'")
    markdown = render_markdown(report)
    assert "<script>" not in markdown
    assert "\n# forged" not in markdown


@pytest.mark.parametrize("prefix", ["\t", "\u00a0", "\u2003"])
def test_c08_csv_formula_guard_skips_unicode_whitespace(prefix):
    rendered = render_csv({
        "publishers": [{
            "publisher_id": "p", "publisher": prefix + "=1+1",
            "qualification": "needs_guideline_or_route_check",
            "exclusion_reasons": [], "accepted_formats": [], "unknowns": [], "evidence": [],
        }],
        "source_index": [],
    })
    row = next(csv.DictReader(StringIO(rendered)))
    assert row["publisher"].startswith("'")


def test_c09_missing_or_bad_live_gates_make_zero_requests():
    manifest = serp_manifest()
    valid = approval_for(manifest)
    bad_approvals = [
        {**valid, "expires_at": "2026-10-05T10:00:00Z"},
        {**valid, "manifest_sha256": "0" * 64},
        {**valid, "max_requests": 0},
        {**valid, "target_permissions_confirmed": False},
    ]
    for approval in bad_approvals:
        calls = []
        with pytest.raises(InputError):
            collect_serp(manifest, approval, lambda request: calls.append(request))
        assert calls == []
    calls = []
    with pytest.raises(InputError):
        brightdata.collect(manifest, approval=valid, api_key="", zones={"serp": "zone"}, transport=lambda request: calls.append(request), now="2026-10-05T10:00:00Z")
    assert calls == []
    with pytest.raises(InputError, match="zone"):
        brightdata.collect(manifest, approval=valid, api_key="test-key", zones={}, transport=lambda request: calls.append(request), now="2026-10-05T10:00:00Z")
    assert calls == []


@pytest.mark.parametrize("extra_args", [[], ["--live"]])
def test_c09_collection_cli_requires_live_and_charge_gates_before_output(tmp_path, capsys, extra_args):
    output = tmp_path / "library.json"
    code = cli.main([
        "collect", str(ROOT / "fixtures" / "manifest.example.json"), "--out", str(output), *extra_args,
    ])
    assert code == 2
    assert json.loads(capsys.readouterr().err)["requests_made"] == 0
    assert not output.exists()


def test_c10_live_dry_run_subprocess_makes_zero_requests_and_writes_nothing(tmp_path):
    output = tmp_path / "never.json"
    run = subprocess.run(
        [sys.executable, "-m", "article_pitch_shortlist", "collect", str(ROOT / "fixtures" / "manifest.example.json"), "--out", str(output), "--live", "--accept-charges", "--dry-run"],
        cwd=ROOT, text=True, capture_output=True, timeout=30,
    )
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result["requests_made"] == 0
    assert "project%20import" not in run.stdout
    assert not output.exists()


def test_c11_fake_transport_asserts_exact_serp_request_shape():
    manifest = serp_manifest("project import")
    calls = []

    def transport(request):
        calls.append((request, json.loads(request.body)))
        return HttpResponse(200, {}, b'{"organic":[]}')

    result = collect_serp(manifest, approval_for(manifest), transport)
    assert len(calls) == 1
    request, body = calls[0]
    assert request.method == "POST"
    assert request.url == "https://api.brightdata.com/request"
    assert request.timeout_seconds == 75
    assert body == {
        "zone": "zone",
        "url": "https://www.google.com/search?q=project%20import&gl=us&hl=en&pws=0&brd_json=1",
        "format": "json",
    }
    assert result["receipt"]["requests_attempted"] == 1


@pytest.mark.parametrize("body", [
    '{"status_code":200,"body":"# page"}',
    '{"headers":{},"body":"partial"}',
    '{"error":"denied"}',
    '{"error_code":"rate_limit","body":"partial"}',
    '{"body":"partial"}',
])
def test_c12_recognizable_json_provider_envelopes_never_become_page_evidence(body):
    with pytest.raises(InputError, match="response_contract_mismatch|invalid_response"):
        brightdata.normalize_export(
            "web_page", body, role="publisher_example",
            source_url="https://publisher.example.org/page",
            observed_at="2026-10-05T10:00:00Z", source_prefix="import",
        )


@pytest.mark.parametrize("status", [401, 403, 429])
def test_c13_http_auth_rate_limit_and_transport_timeout_stop_once(status):
    manifest = serp_manifest()
    calls = []

    def transport(request):
        calls.append(request)
        return HttpResponse(status, {}, b"secret provider message")

    result = collect_serp(manifest, approval_for(manifest), transport)
    assert len(calls) == 1
    assert result["receipt"]["status"] == "failed"
    assert result["receipt"]["responses_received"] == 1
    assert result["receipt"]["jobs"][0]["state"] == "failed"
    assert "secret provider message" not in json.dumps(result)

    timeout_calls = []
    timeout = collect_serp(manifest, approval_for(manifest), lambda request: (timeout_calls.append(request), (_ for _ in ()).throw(TransportError()))[1])
    assert len(timeout_calls) == 1
    assert timeout["receipt"]["status"] == "completion_unknown"
    assert timeout["receipt"]["completion_unknown"] is True
    assert timeout["receipt"]["jobs"][0]["state"] == "completion_unknown"


@pytest.mark.parametrize("response", [
    HttpResponse("200", {}, b'{"organic":[]}'),
    HttpResponse(200, {1: "header"}, b'{"organic":[]}'),
    HttpResponse(200, {}, "not-bytes"),
])
def test_malformed_http_response_dto_is_safe_failure(response):
    manifest = serp_manifest()
    result = collect_serp(manifest, approval_for(manifest), lambda request: response)
    receipt = result["receipt"]
    assert receipt["requests_attempted"] == 1
    assert receipt["responses_received"] == 1
    assert receipt["jobs"][0]["error_code"] == "invalid_response"
    assert result["sources"] == []


@pytest.mark.parametrize("body", [b"not-json", b'{"organic":[]}\n{"organic":[]}', b" " * (2 * 1024 * 1024 + 1)])
def test_c12_invalid_ndjson_and_oversized_serp_responses_never_become_evidence(body):
    manifest = serp_manifest()
    result = collect_serp(manifest, approval_for(manifest), lambda request: HttpResponse(200, {}, body))
    assert result["sources"] == []
    assert result["receipt"]["status"] == "failed"
    assert result["receipt"]["jobs"][0]["state"] == "failed"
    assert result["receipt"]["jobs"][0]["error_code"] in {"invalid_response", "response_too_large"}


@pytest.mark.parametrize("bad_field", ["title", "description"])
def test_invalid_provider_text_record_is_excluded_without_crashing(bad_field):
    manifest = serp_manifest()
    record = {"link": "https://publisher.example.org/article", "title": "Article", "description": "A safe snippet", "rank": 1}
    record[bad_field] = "bad\x00provider text"
    body = json.dumps({"organic": [record]}).encode()
    result = collect_serp(manifest, approval_for(manifest), lambda request: HttpResponse(200, {}, body))
    assert result["receipt"]["status"] == "complete"
    assert result["receipt"]["returned_records"] == 1
    assert result["receipt"]["retained_records"] == 0
    assert result["receipt"]["excluded_records"] == 1
    assert result["receipt"]["warnings"][0]["code"] == "invalid_record"


def test_c14_async_scraper_kinds_and_pending_jobs_are_rejected_without_http():
    unsupported = {
        "schema_version": "1.0", "project": "article-pitch-shortlist",
        "jobs": [{"id": "comments", "kind": "youtube_comments"}],
    }
    with pytest.raises(InputError, match="only web_page and serp"):
        brightdata.plan(unsupported)


def test_c15_resume_is_unsupported_and_never_invokes_transport():
    calls = []
    with pytest.raises(InputError, match="unsupported"):
        brightdata.resume({}, approval={}, api_key="key", transport=lambda request: calls.append(request), now="2026-10-05T10:00:00Z")
    assert calls == []


def test_c16_zero_and_overreturned_serp_records_have_truthful_counts():
    manifest = serp_manifest()
    empty = collect_serp(manifest, approval_for(manifest), lambda request: HttpResponse(200, {}, b'{"organic":[]}'))
    assert empty["receipt"]["returned_records"] == 0
    assert empty["receipt"]["retained_records"] == 0
    organic = [{"link": f"https://publisher{i}.example.org/a", "description": "x", "rank": i + 1} for i in range(7)]
    over = collect_serp(manifest, approval_for(manifest), lambda request: HttpResponse(200, {}, json.dumps({"organic": organic}).encode()))
    assert over["receipt"]["returned_records"] == 7
    assert over["receipt"]["retained_records"] == 5
    assert over["receipt"]["excluded_records"] == 2
    assert over["receipt"]["status"] == "partial"
    assert over["receipt"]["jobs"][0]["state"] == "complete"
    assert any(warning["code"] == "provider_limit_exceeded" for warning in over["receipt"]["warnings"])


@pytest.mark.parametrize("url", [
    "http://publisher.example.org/a",
    "https://{}:{}@publisher.example.org/a".format("user", "pass"),  # Synthetic userinfo rejection case.
    "https://127.0.0.1/a",
    "https://localhost/a",
    "https://publisher.invalid/a",
    "https://publisher.example.org/a?token=secret",
])
def test_c17_unsafe_live_page_targets_are_refused(url):
    manifest = {
        "schema_version": "1.0", "project": "article-pitch-shortlist",
        "jobs": [{"id": "page", "kind": "web_page", "role": "publisher_example", "source_id": "page", "url": url}],
    }
    with pytest.raises(InputError):
        brightdata.plan(manifest)


def test_c17_ip_literal_rejection_is_explicit():
    manifest = {
        "schema_version": "1.0", "project": "article-pitch-shortlist",
        "jobs": [{
            "id": "page", "kind": "web_page", "role": "publisher_example",
            "source_id": "page", "url": "https://127.0.0.1/article",
        }],
    }
    with pytest.raises(InputError, match="IP-literal"):
        brightdata.plan(manifest)


def test_c18_serp_results_never_authorize_destination_fetches():
    manifest = serp_manifest()
    calls = []
    response = {"organic": [{"link": "https://publisher.example.org/a", "title": "A", "description": "x", "rank": 1}]}
    result = collect_serp(manifest, approval_for(manifest), lambda request: (calls.append(request), HttpResponse(200, {}, json.dumps(response).encode()))[1])
    assert len(calls) == 1
    assert calls[0].url == "https://api.brightdata.com/request"
    assert result["sources"][0]["role"] == "discovery"
    assert result["receipt"]["status"] == "complete"
    assert result["receipt"]["jobs"][0]["state"] == "complete"


def test_c19_cli_golden_subprocess_and_transactional_rollback(tmp_path, monkeypatch):
    output = tmp_path / "report"
    run = subprocess.run(
        [sys.executable, "-m", "article_pitch_shortlist", "analyze", str(ROOT / "fixtures" / "demo.json"), "--out-dir", str(output)],
        cwd=ROOT, text=True, capture_output=True, timeout=30,
    )
    assert run.returncode == 0, run.stderr
    for name in ("report.json", "pitches.md", "pitches.csv"):
        assert (output / name).read_bytes() == (ROOT / "fixtures" / "expected" / name).read_bytes()

    original_link = os.link
    commits = 0

    def fail_third(source, destination):
        nonlocal commits
        commits += 1
        if commits == 3:
            raise OSError("injected third-commit failure")
        return original_link(source, destination)

    rollback = tmp_path / "rollback"
    monkeypatch.setattr(cli.os, "link", fail_third)
    with pytest.raises(InputError, match="transaction"):
        cli._write_report_set(rollback, {"report.json": "a", "pitches.md": "b", "pitches.csv": "c"}, overwrite=False)
    assert list(rollback.iterdir()) == []


def test_c20_report_declares_scope_methods_synthetic_limits_and_no_outcome_claims(demo):
    report = analyze(demo)
    markdown = render_markdown(report)
    assert report["scope"]["source_ids"]
    assert report["analysis_method"] == "deterministic_rules_v1"
    assert report["draft_method"] == "approved_text_templates_v1"
    assert report["transport_contract_version"] == "1.0"
    assert any(warning["code"] == "synthetic_data" for warning in report["warnings"])
    assert "Synthetic demonstration" in markdown
    assert "Transport contract: `1.0`" in markdown
    assert "provenance: `synthetic\\_fixture`" in markdown
    assert "not a directory" in markdown
    assert "acceptance prediction" in markdown


def test_rendered_artifacts_omit_editorial_acceptance_claims_but_keep_decision_evidence(demo):
    report = analyze(demo)
    rendered = {
        "json": render_json(report),
        "markdown": render_markdown(report),
        "csv": render_csv(report),
    }
    forbidden_claims = [
        "We accept tutorials.",
        "Only original, unpublished work.",
        "Word count: 500-800 words.",
        "A worked example is required.",
        "We do not accept guest posts.",
    ]
    for artifact in rendered.values():
        assert not any(claim in artifact for claim in forbidden_claims)
    marker = "[editorial guideline wording omitted; structured rule state retained]"
    markdown_marker = "\\[editorial guideline wording omitted; structured rule state retained\\]"
    assert markdown_marker in rendered["markdown"]
    assert marker in rendered["json"]
    assert "editorial guideline wording omitted; classified as guidance" not in rendered["markdown"]
    assert "editorial guideline wording omitted; classified as guidance" not in rendered["json"]
    assert '"format_state": "explicitly_accepted"' in rendered["json"]
    assert '"exclusion_reasons": [\n        "submissions_closed"' in rendered["json"]
    assert '"source_id": "north_rules"' in rendered["json"]
    assert '"block_id": "b0002"' in rendered["json"]


def test_renderers_redact_arbitrary_approval_guarantee_and_publication_claim_sentences():
    claims = [
        "The publisher guarantees placement.",
        "The editor approves this pitch.",
        "This will be published next month.",
    ]
    report = {
        "decision": "pitch_shortlist", "status": "needs_review",
        "analysis_method": "deterministic_rules_v1", "draft_method": "approved_text_templates_v1",
        "transport_contract_version": "1.0", "scope": {"audience": "operators", "as_of": None},
        "source_index": [{"id": "guide", "url": "https://publisher.example.org/guidelines", "provenance": "operator_supplied", "observed_at": "2026-10-05T10:00:00Z", "content_sha256": "hash", "record_id": None}],
        "publishers": [{"publisher_id": "p", "publisher": "P", "qualification": "needs_guideline_or_route_check", "exclusion_reasons": [], "accepted_formats": [], "unknowns": [], "pitch_draft": claims[0], "research_task": "Review the rules.", "evidence": [{"source_id": "guide", "block_id": f"b{i:04d}", "quote": claim} for i, claim in enumerate(claims, 1)]}],
        "cards": [], "excluded": [], "warnings": [],
    }
    outputs = (render_json(report), render_markdown(report), render_csv(report))
    for output in outputs:
        assert all(claim not in output for claim in claims)
    assert "editorial outcome claim omitted" in outputs[0]
    assert "editorial outcome claim omitted" in outputs[1]
    assert "editorial outcome claim omitted" in outputs[2]


def test_all_guideline_evidence_quotes_are_omitted_regardless_of_claim_wording():
    varied_guideline_claims = [
        "Tutorial contributions are normally selected for this section.",
        "Editors usually approve this format after review.",
        "Placement is assured when the article meets these expectations.",
        "We generally look for pieces around 500 to 800 words.",
        "The editorial team prefers an original worked example.",
    ]
    citations = [
        {"source_id": "guidelines", "block_id": f"b{i:04d}", "quote": quote}
        for i, quote in enumerate(varied_guideline_claims, 1)
    ]
    row = {
        "publisher_id": "north", "publisher": "North",
        "qualification": "ready_for_human_pitch_review", "exclusion_reasons": [],
        "accepted_formats": ["tutorial"], "unknowns": [], "originality_state": "original_unpublished_required",
        "fit_excerpt": "A tutorial about importing a project.", "example_url": "https://north.example.com/example",
        "submission_url": "https://north.example.com/contribute", "route_state": "observed_route",
        "word_min": 500, "word_max": 800, "evidence": citations, "pitch_draft": "A neutral operator-authored draft.",
    }
    report = {
        "schema_version": "1.0", "project": "article-pitch-shortlist",
        "transport_contract_version": "1.0", "analysis_method": "deterministic_rules_v1",
        "draft_method": "approved_text_templates_v1", "status": "ok", "decision": "pitch_shortlist",
        "scope": {"audience": "operators", "as_of": "2026-10-05T10:00:00Z"},
        "warnings": [], "summary": {}, "source_index": [{
            "id": "guidelines", "kind": "page", "role": "submission_guidelines",
            "url": "https://north.example.com/guidelines", "observed_at": "2026-10-05T10:00:00Z",
            "record_id": None, "content_sha256": "known-hash", "provenance": "operator_supplied",
        }, {
            "id": "example", "kind": "page", "role": "publisher_example",
            "url": "https://north.example.com/example", "observed_at": "2026-10-05T10:00:00Z",
            "record_id": None, "content_sha256": "example-hash", "provenance": "operator_supplied",
        }],
        "publishers": [row], "cards": [row], "excluded": [],
    }
    outputs = (render_json(report), render_markdown(report), render_csv(report))
    appendix = outputs[1].split("## Evidence Appendix", 1)[1].split("## Limitations", 1)[0]

    for output in outputs:
        assert all(claim not in output for claim in varied_guideline_claims)
    placeholders = [line for line in appendix.splitlines() if "structured rule state retained" in line]
    assert len(placeholders) == len(varied_guideline_claims)
    marker = r"\[editorial guideline wording omitted; structured rule state retained\]"
    assert all(marker in line for line in placeholders)
    assert "[editorial guideline wording omitted; structured rule state retained]" in outputs[0]
    assert "editorial guideline wording omitted" in outputs[0]
    assert "editorial guideline wording omitted" in outputs[1]
    assert '"source_id": "guidelines"' in outputs[0]
    assert '"block_id": "b0001"' in outputs[0]
    assert "known-hash" in outputs[0] and "north.example.com/guidelines" in outputs[0]
    assert "north_rules" not in outputs[2]
    assert "guidelines" in outputs[2]


def test_guideline_appendix_uses_exact_contract_placeholder_for_arbitrary_quotes(demo):
    report = analyze(demo)
    guideline_citations = [
        citation
        for row in report["publishers"]
        for citation in row["evidence"]
        if citation["source_id"] in {"north_rules", "west_rules"}
    ]
    assert guideline_citations
    appendix = render_markdown(report).split("## Evidence Appendix", 1)[1].split("## Limitations", 1)[0]

    for citation in guideline_citations:
        assert citation["quote"] not in appendix
    placeholders = [line for line in appendix.splitlines() if "structured rule state retained" in line]
    assert len(placeholders) == len(guideline_citations)
    marker = r"\[editorial guideline wording omitted; structured rule state retained\]"
    assert all(line.rsplit(': "', 1)[1] == marker + '"' for line in placeholders)
    rendered_report = json.loads(render_json(report))
    for section in ("publishers", "cards", "excluded"):
        for row in rendered_report[section]:
            for citation in row["evidence"]:
                if citation["source_id"] in {"north_rules", "west_rules"}:
                    assert citation["quote"] == "[editorial guideline wording omitted; structured rule state retained]"


def test_shared_receipt_enum_values_are_exercised_by_named_scenarios(tmp_path, capsys):
    expected_statuses = {"complete", "partial", "failed", "pending", "completion_unknown"}
    expected_job_states = {"complete", "empty", "failed", "pending", "completion_unknown", "not_attempted"}
    manifest = serp_manifest()
    complete = collect_serp(manifest, approval_for(manifest), lambda request: HttpResponse(200, {}, b'{"organic":[]}'))
    assert complete["receipt"]["status"] in expected_statuses
    assert complete["receipt"]["jobs"][0]["state"] in expected_job_states
    assert complete["receipt"]["status"] == "complete"
    assert complete["receipt"]["jobs"][0]["state"] == "empty"
    populated = collect_serp(manifest, approval_for(manifest), lambda request: HttpResponse(200, {}, json.dumps({"organic": [{"link": "https://publisher.example.org/a", "title": "A", "description": "x", "rank": 1}]}).encode()))
    assert populated["receipt"]["status"] == "complete"
    assert populated["receipt"]["jobs"][0]["state"] == "complete"
    failed = collect_serp(manifest, approval_for(manifest), lambda request: HttpResponse(503, {}, b""))
    assert failed["receipt"]["status"] == "failed"
    assert failed["receipt"]["jobs"][0]["state"] == "failed"
    unknown = collect_serp(manifest, approval_for(manifest), lambda request: (_ for _ in ()).throw(TransportError()))
    assert unknown["receipt"]["status"] == "completion_unknown"
    assert unknown["receipt"]["jobs"][0]["state"] == "completion_unknown"
    partial = collect_serp(manifest, approval_for(manifest), lambda request: HttpResponse(200, {}, json.dumps({"organic": [{"link": f"https://publisher{i}.example.org/a", "title": "A", "description": "x", "rank": i} for i in range(7)]}).encode()))
    assert partial["receipt"]["status"] == "partial"
    assert partial["receipt"]["jobs"][0]["state"] == "complete"
    imported = brightdata.normalize_export(
        "web_page", "# Guidelines", role="submission_guidelines",
        source_url="https://publisher.example.org/guidelines",
        observed_at="2026-10-05T10:00:00Z", source_prefix="import",
    )
    assert imported["receipt"]["status"] == "complete"
    assert imported["receipt"]["jobs"] == []
    over_limit = brightdata.normalize_export(
        "serp", {"organic": [
            {"link": f"https://publisher{i}.example.org/a", "title": "Article", "description": "Excerpt"}
            for i in range(7)
        ]}, role="discovery", source_url="https://www.google.com/search",
        observed_at="2026-10-05T10:00:00Z", source_prefix="import",
    )
    assert over_limit["receipt"]["status"] == "partial"
    assert over_limit["receipt"]["returned_records"] == 7
    assert over_limit["receipt"]["retained_records"] == 5
    assert over_limit["receipt"]["excluded_records"] == 2
    assert any(warning["code"] == "provider_limit_exceeded" for warning in over_limit["receipt"]["warnings"])
    provider_export = tmp_path / "provider.json"
    provider_export.write_text(json.dumps({"organic": [
        {"link": f"https://publisher{i}.example.org/a", "title": "Article", "description": "Excerpt"}
        for i in range(7)
    ]}), encoding="utf-8")
    output = tmp_path / "library.json"
    code = cli.main([
        "import-provider", str(provider_export), "--kind", "serp", "--role", "discovery",
        "--source-url", "https://www.google.com/search", "--observed-at", "2026-10-05T10:00:00Z",
        "--out", str(output),
    ])
    assert code == 4
    assert json.loads(capsys.readouterr().out)["status"] == "partial"
    assert json.loads(output.read_text(encoding="utf-8"))["receipt"]["status"] == "partial"

    # pending/not_attempted are contract-permitted states, but this synchronous
    # adapter cannot emit them: async jobs are unsupported and live web pages fail closed.
    assert "pending" in expected_statuses and "pending" in expected_job_states
    assert "not_attempted" in expected_job_states


@pytest.mark.parametrize("timestamp", [
    "2026-10-05Z",
    "2026-10-05 10:00:00Z",
    "2026-10-05T10:00Z",
    "2026-10-05T10:00:00+00:00",
    "2026-02-30T10:00:00Z",
])
def test_strict_utc_rfc3339_rejects_noncanonical_timestamps(demo, timestamp):
    payload = copy.deepcopy(demo)
    payload["sources"][0]["observed_at"] = timestamp
    with pytest.raises(InputError, match="UTC RFC3339|valid"):
        analyze(payload)
    with pytest.raises(InputError, match="UTC RFC3339|valid"):
        brightdata.normalize_export(
            "web_page", "# Page", role="publisher_example",
            source_url="https://publisher.example.org/page",
            observed_at=timestamp, source_prefix="import",
        )


def test_unicode_phrase_boundaries_do_not_match_inside_unicode_words():
    embedded = evaluate(example_body="A guide to éporté migrations.", topic_phrase="port")
    separate = evaluate(example_body="A guide to port migrations.", topic_phrase="port")
    assert embedded.topic_state == "not_found"
    assert separate.topic_state == "body_evidence_found"


def test_shared_canonical_url_redacts_query_values_and_preserves_parameter_names():
    result = canonical_url("https://Publisher.Example.org/article?token=private-value&campaign=launch")
    assert "private-value" not in result
    assert "launch" not in result
    assert "token=" in result and "campaign=" in result
    assert result.count("%5Bredacted%5D") == 2


def test_core_persists_no_source_or_route_query_values_and_all_renderers_redact(demo):
    payload = copy.deepcopy(demo)
    secrets_in_urls = ["own-secret", "example-secret", "guideline-secret", "route-secret"]
    for source, value in zip(payload["sources"][:3], secrets_in_urls[:3]):
        source["url"] += f"?token={value}&campaign=private-campaign"
    payload["sources"][0]["record_id"] = "https://records.example.org/item?token=record-secret"
    payload["sources"][0]["record_id_origin"] = "operator"
    payload["sources"][0]["provider_date"] = "reference https://dates.example.org/item?token=date-secret"
    guidelines = next(source for source in payload["sources"] if source["id"] == "north_rules")
    guidelines["text"] = guidelines["text"].replace(
        "https://north.example.com/contribute",
        "https://north.example.com/contribute?token=route-secret&campaign=private-campaign",
    )
    report = analyze(payload)
    outputs = (render_json(report), render_markdown(report), render_csv(report))
    indexed_own_source = next(item for item in report["source_index"] if item["id"] == "own")
    assert "record-secret" not in indexed_own_source["record_id"]
    assert "date-secret" not in indexed_own_source["provider_date"]
    for secret in (*secrets_in_urls, "private-campaign", "record-secret", "date-secret"):
        assert all(secret not in output for output in outputs)
    north = next(row for row in report["publishers"] if row["publisher_id"] == "north")
    assert "%5Bredacted%5D" in north["submission_url"]
    route_quote = next(citation["quote"] for citation in north["evidence"] if "submission form" in citation["quote"])
    assert "route-secret" not in route_quote
    assert "%5Bredacted%5D" in route_quote


def test_offline_provider_imports_redact_source_and_result_query_values():
    web = brightdata.normalize_export(
        "web_page", "# Read https://publisher.example.org/page?token=title-secret\n\n[submission form](https://publisher.example.org/go?token=page-secret)",
        role="submission_guidelines",
        source_url="https://publisher.example.org/guidelines?auth=source-secret",
        observed_at="2026-10-05T10:00:00Z", source_prefix="import",
    )
    serp = brightdata.normalize_export(
        "serp", {"organic": [{
            "link": "https://publisher.example.org/article?secret=result-secret",
            "title": "Read https://publisher.example.org/article?token=serp-title-secret",
            "description": "Article excerpt", "rank": 1,
        }]},
        role="discovery", source_url="https://www.google.com/search?q=private-query",
        observed_at="2026-10-05T10:00:00Z", source_prefix="search",
    )
    serialized = json.dumps({"web": web, "serp": serp})
    for secret in ("title-secret", "serp-title-secret", "page-secret", "source-secret", "result-secret", "private-query"):
        assert secret not in serialized
    assert "%5Bredacted%5D" in serialized


def test_renderers_redact_untrusted_query_urls_even_for_external_report_objects():
    report = {
        "schema_version": "1.0", "project": "article-pitch-shortlist",
        "transport_contract_version": "1.0", "analysis_method": "deterministic_rules_v1",
        "draft_method": "approved_text_templates_v1", "decision": "pitch_shortlist",
        "status": "needs_review", "scope": {"audience": "operators", "as_of": None},
        "source_index": [{
            "id": "source", "url": "https://publisher.example.org/a?token=json-secret",
            "provenance": "operator_supplied", "observed_at": "2026-10-05T10:00:00Z",
            "content_sha256": "hash", "record_id": None,
        }],
        "publishers": [{"publisher_id": "p", "publisher": "P", "qualification": "needs_guideline_or_route_check", "evidence": [{"source_id": "source", "block_id": "b0001", "quote": "See https://publisher.example.org/a?auth=quote-secret."}], "exclusion_reasons": [], "accepted_formats": [], "unknowns": [], "pitch_draft": "Read https://publisher.example.org/a?token=draft-secret."}],
        "cards": [{"publisher_id": "p", "publisher": "P", "qualification": "needs_guideline_or_route_check", "example_url": "https://publisher.example.org/a?token=markdown-secret", "fit_excerpt": None, "submission_url": "https://publisher.example.org/go?secret=route-secret", "unknowns": [], "pitch_draft": "See https://publisher.example.org/a?token=draft-secret.", "research_task": None}],
        "excluded": [], "warnings": [],
    }
    outputs = (render_json(report), render_markdown(report), render_csv(report))
    for secret in ("json-secret", "quote-secret", "draft-secret", "markdown-secret", "route-secret"):
        assert all(secret not in output for output in outputs)


def test_unicode_casefold_expansion_keeps_late_excerpt_hit():
    body = ("ß" * 250) + " project import begins here."
    result = evaluate(example_body=body, topic_phrase="project import")
    assert result.topic_state == "body_evidence_found"
    assert "project import" in result.fit_excerpt
    assert len(result.fit_excerpt) <= 240
