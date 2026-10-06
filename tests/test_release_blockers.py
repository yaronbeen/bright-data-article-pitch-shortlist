"""Regression tests for the brand and security release blockers."""

from __future__ import annotations

import copy
import csv
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
import json
import os
from pathlib import Path
import signal
import threading
import time

import pytest

from article_pitch_shortlist import __version__, brightdata, cli
from article_pitch_shortlist.brightdata import HttpResponse, TransportError
from article_pitch_shortlist.core import InputError, analyze, draft_pitch
from article_pitch_shortlist.export import render_csv, render_markdown


ROOT = Path(__file__).parents[1]


@pytest.fixture
def demo_payload():
    return json.loads((ROOT / "fixtures" / "demo.json").read_text(encoding="utf-8"))


def serp_manifest(query="project import tutorial"):
    return {
        "schema_version": "1.0",
        "project": "article-pitch-shortlist",
        "jobs": [{
            "id": "search",
            "kind": "serp",
            "role": "discovery",
            "source_prefix": "candidate",
            "query": query,
            "country": "us",
            "language": "en",
        }],
    }


def web_manifest(url="https://publisher.test.invalid/page"):
    return {
        "schema_version": "1.0",
        "project": "article-pitch-shortlist",
        "jobs": [{
            "id": "page",
            "kind": "web_page",
            "role": "publisher_example",
            "source_id": "publisher_page",
            "url": url,
        }],
    }


def approval_for(manifest, *, retained=5):
    planned = brightdata.plan(manifest)
    return {
        "schema_version": "1.0",
        "project": "article-pitch-shortlist",
        "manifest_sha256": brightdata.manifest_sha256(manifest),
        "expires_at": "2035-01-01T00:00:00Z",
        "max_requests": planned["planned_requests"],
        "max_retained_records": retained,
        "approved_urls": [item["approved_url"] for item in planned["requests"]],
        "account_budget_confirmed": True,
        "target_permissions_confirmed": True,
        "remote_resolution_risk_accepted": True,
    }


def collect_serp(manifest, approval, transport, **kwargs):
    return brightdata.collect(
        manifest,
        approval=approval,
        api_key="injected-test-value",
        zones={"serp": "serp-zone"},
        transport=transport,
        now="2026-10-05T10:00:00Z",
        **kwargs,
    )


def test_pitch_uses_structured_capability_not_raw_guideline_quotes(demo_payload):
    report = analyze(demo_payload)
    north = next(row for row in report["publishers"] if row["publisher_id"] == "north")
    draft = north["pitch_draft"]

    assert north["qualification"] == "ready_for_human_pitch_review"
    assert "I can provide a worked example. The proposed length is 700 words." in draft
    for raw_rule in (
        "We accept tutorials.",
        "Only original, unpublished work.",
        "Word count: 500-800 words.",
        "A worked example is required.",
    ):
        assert raw_rule not in draft
    assert not any(word in draft.casefold() for word in ("accept", "approval", "guarantee"))


def test_readme_pitch_example_and_rendered_pitch_omit_guideline_derived_range(demo_payload):
    readme = (ROOT / "docs" / "technical-guide.md").read_text(encoding="utf-8")
    readme_example = readme.split("```text", 1)[1].split("```", 1)[0]
    report = analyze(demo_payload)
    rendered = render_markdown(report)
    rendered_pitch = rendered.split("**Draft for human review**", 1)[1].split("\n\n### ", 1)[0]

    assert "The proposed length is 700 words." in readme_example
    for text in (readme_example, rendered_pitch):
        assert "500-800" not in text
        assert "word range" not in text.casefold()
        assert "within the stated" not in text.casefold()


def test_operator_fields_cannot_reintroduce_raw_guideline_quotations():
    with pytest.raises(InputError, match="raw guideline language"):
        draft_pitch(
            observed_title="Importing data",
            observed_title_is_cited_h1=True,
            example_url="https://publisher.example.com/article",
            matched_topic_phrase="project import",
            proposed_title="Diagnose an import problem",
            proposed_format="tutorial",
            audience="operators",
            contribution="We accept tutorials.",
            method="new_followup",
            is_unpublished=True,
            asset_title="Import methods",
            planned_word_count=700,
            guideline_acknowledgements=["We accept tutorials."],
            has_worked_example=True,
        )


def test_draft_pitch_returns_query_redacted_prose_not_only_a_sanitized_validation_copy():
    draft = draft_pitch(
        observed_title="Importing data",
        observed_title_is_cited_h1=True,
        example_url="https://publisher.example.org/article?token=url-secret",
        matched_topic_phrase="project import",
        proposed_title="Diagnose an import problem",
        proposed_format="tutorial",
        audience="operators",
        contribution="See https://notes.example.org/check?token=contribution-secret.",
        method="new_followup",
        is_unpublished=True,
        asset_title="Import methods",
        planned_word_count=700,
        guideline_acknowledgements=[],
        has_worked_example=True,
    )
    assert "url-secret" not in draft
    assert "contribution-secret" not in draft
    assert "%5Bredacted%5D" in draft


def test_core_draft_and_all_artifacts_redact_operator_supplied_query_urls(demo_payload):
    from article_pitch_shortlist.export import render_json

    demo_payload["proposed_piece"]["contribution"] = (
        "A worked example and checklist. See https://notes.example.org/check?token=report-secret."
    )
    report = analyze(demo_payload)
    north = next(row for row in report["publishers"] if row["publisher_id"] == "north")
    assert "report-secret" not in north["pitch_draft"]
    outputs = (render_json(report), render_markdown(report), render_csv(report))
    assert all("report-secret" not in output for output in outputs)


def test_pitch_rejects_outcome_language_from_operator_fields():
    with pytest.raises(InputError, match="outcome language"):
        draft_pitch(
            observed_title="Importing data",
            observed_title_is_cited_h1=True,
            example_url="https://publisher.example.com/article",
            matched_topic_phrase="project import",
            proposed_title="A guaranteed route to approval",
            proposed_format="tutorial",
            audience="operators",
            contribution="A worked example.",
            method="new_followup",
            is_unpublished=True,
            asset_title="Import methods",
            planned_word_count=700,
            guideline_acknowledgements=[],
            has_worked_example=True,
        )


@pytest.mark.parametrize("claim", [
    "publishers accepts tutorials",
    "publishers are accepting tutorials",
    "publishers approves tutorials",
    "publishers are approving this pitch",
    "the publisher guarantees placement",
    "the publisher is guaranteeing acceptance",
    "this will be published next month",
    "the publisher will accept this article",
    "the publisher will approve the submission",
    "the publisher accepts this pitch",
    "the publisher accepted the proposal",
    "the publisher is accepting this submission",
    "the publisher approves this article",
    "the publisher is approving the pitch",
    "the publisher guarantees publication",
    "the publisher is guaranteeing placement",
    "this will be accepted next week",
    "this will be approved next week",
    "this will be published next week",
])
def test_pitch_rejects_acceptance_approval_and_publication_claim_inflections(claim):
    with pytest.raises(InputError, match="outcome language"):
        draft_pitch(
            observed_title="Importing data",
            observed_title_is_cited_h1=True,
            example_url="https://publisher.example.com/article",
            matched_topic_phrase="project import",
            proposed_title="Diagnose an import problem",
            proposed_format="tutorial",
            audience="operators",
            contribution=claim,
            method="new_followup",
            is_unpublished=True,
            asset_title="Import methods",
            planned_word_count=700,
            guideline_acknowledgements=[],
            has_worked_example=True,
        )


def test_assembled_pitch_prose_is_checked_after_template_composition():
    with pytest.raises(InputError, match="outcome language"):
        draft_pitch(
            observed_title="Importing data",
            observed_title_is_cited_h1=True,
            example_url="https://publisher.example.com/article",
            matched_topic_phrase="project import",
            proposed_title="Diagnose an import problem",
            proposed_format="tutorial. We guarantee acceptance",
            audience="operators",
            contribution="A worked example.",
            method="new_followup",
            is_unpublished=True,
            asset_title="Import methods",
            planned_word_count=700,
            guideline_acknowledgements=[],
            has_worked_example=True,
        )


def test_distribution_and_repository_identity_are_neutral(capsys):
    import tomllib

    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    agent_guide = (ROOT / "AGENT.md").read_text(encoding="utf-8")
    verification = (ROOT / "VERIFICATION.md").read_text(encoding="utf-8")
    latest_handover = (ROOT / "handover" / "handover-007.md").read_text(encoding="utf-8")
    old_distribution = "bright_data_" + "article_pitch_shortlist"
    old_root = "/home/yaron/projects/" + "bright-data-" + "article-pitch-shortlist"
    checkout_directory_names = {"article-pitch-shortlist", "bright-data-article-pitch-shortlist"}

    assert ROOT.name in checkout_directory_names
    assert metadata["project"]["name"] == "article-pitch-shortlist"
    assert metadata["project"]["version"] == __version__
    assert metadata["project"]["scripts"] == {"article-pitch-shortlist": "article_pitch_shortlist.cli:main"}
    assert metadata["tool"]["setuptools"]["packages"] == ["article_pitch_shortlist"]
    assert (ROOT / "article_pitch_shortlist" / "cli.py").is_file()
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    assert "article-pitch-shortlist" in capsys.readouterr().out
    assert "authoriz" not in agent_guide.casefold()
    assert "independent demo" in agent_guide.casefold()
    assert "publication status is unpublished" in agent_guide.casefold()
    for document in (readme, agent_guide, verification, latest_handover):
        assert "the user authorized" not in document.casefold()
        assert "user authorization" not in document.casefold()
        assert "authorization is granted" not in document.casefold()
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in {".git", ".pytest_cache", "__pycache__", "build", "dist"} for part in path.parts):
            continue
        try:
            contents = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        assert old_distribution not in contents, str(path)
        assert old_root not in contents, str(path)


def test_public_readme_states_neutral_independent_demo_status_without_user_authorization():
    readme = (ROOT / "README.md").read_text(encoding="utf-8").casefold()
    for phrase in (
        "the user has explicitly authorized",
        "authorization is granted",
        "authorized by the user",
        "explicitly authorized",
    ):
        assert phrase not in readme
    guide = (ROOT / "docs" / "technical-guide.md").read_text(encoding="utf-8").casefold()
    assert "its fixture is invented and the run makes zero network requests" in guide
    assert "live web unlocker page collection fails closed" in guide
    assert "https://docs.brightdata.com/api-reference/rest-api/serp/serp-api.md" in guide


def test_only_ready_rows_receive_drafts_and_other_rows_keep_research_tasks(demo_payload):
    payload = copy.deepcopy(demo_payload)
    payload["sources"][2]["text"] = "We accept tutorials. Only original, unpublished work."
    report = analyze(payload)
    north = next(row for row in report["publishers"] if row["publisher_id"] == "north")

    assert north["qualification"] == "needs_guideline_or_route_check"
    assert north["pitch_draft"] is None
    assert north["research_task"]
    assert all((row["pitch_draft"] is not None) == (row["qualification"] == "ready_for_human_pitch_review") for row in report["publishers"])


def test_mixed_synthetic_disclosure_and_csv_provenance_are_accurate(demo_payload):
    payload = copy.deepcopy(demo_payload)
    payload["sources"][3]["provenance"] = "operator_supplied"
    report = analyze(payload)
    markdown = render_markdown(report)
    rows = list(csv.DictReader(StringIO(render_csv(report))))

    assert "mixes invented synthetic fixture sources with operator-supplied or Bright Data sources" in markdown
    assert "All cited source material" not in markdown
    assert "evidence_provenance" in rows[0]
    assert rows[0]["provenance_state"] == "mixed"
    assert rows[0]["contains_synthetic_data"] == "true"
    west = next(row for row in rows if row["publisher_id"] == "west")
    assert west["evidence_provenance"] == "operator_supplied;synthetic_fixture"


def test_csv_report_provenance_discloses_synthetic_source_without_row_citations(demo_payload):
    payload = copy.deepcopy(demo_payload)
    payload["publishers"][0]["guideline_source_ids"] = []
    report = analyze(payload)
    report["publishers"][0]["evidence"] = []
    rows = list(csv.DictReader(StringIO(render_csv(report))))
    uncited = next(row for row in rows if row["publisher_id"] == "north")

    assert uncited["evidence_source_ids"] == ""
    assert uncited["evidence_provenance"] == ""
    assert uncited["provenance_state"] == "synthetic"
    assert uncited["contains_synthetic_data"] == "true"


def test_csv_report_provenance_marks_fully_operator_supplied_report(demo_payload):
    payload = copy.deepcopy(demo_payload)
    for source in payload["sources"]:
        source["provenance"] = "operator_supplied"
    report = analyze(payload)
    rows = list(csv.DictReader(StringIO(render_csv(report))))

    assert rows
    assert {row["provenance_state"] for row in rows} == {"operator_supplied"}
    assert {row["contains_synthetic_data"] for row in rows} == {"false"}


def test_markdown_untrusted_values_are_inert_single_line():
    report = {
        "decision": "pitch_shortlist",
        "status": "needs_review",
        "analysis_method": "deterministic_rules_v1",
        "draft_method": "approved_text_templates_v1",
        "scope": {"audience": "operators\n# injected", "as_of": None},
        "cards": [{
            "publisher": "<script>alert(1)</script>\n## takeover",
            "qualification": "needs_guideline_or_route_check",
            "example_url": "https://example.com/a",
            "fit_excerpt": "line one\n> forged quote",
            "submission_url": None,
            "unknowns": [],
            "pitch_draft": None,
            "research_task": "check `rules`\n# forged",
        }],
        "excluded": [],
        "publishers": [],
        "source_index": [],
    }

    rendered = render_markdown(report)
    assert "<script>" not in rendered
    assert "\n# injected" not in rendered
    assert "\n## takeover" not in rendered
    assert "\n> forged quote" not in rendered
    assert "\n# forged" not in rendered


def test_private_json_patterns_are_ignored_and_readme_uses_direct_rest_references():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    readme = (ROOT / "docs" / "technical-guide.md").read_text(encoding="utf-8")

    assert "*.private.json" in gitignore
    assert ".*.tmp" in gitignore
    assert ".*.backup.*" in gitignore
    assert ".*.rollback.*" in gitignore
    assert "Web Unlocker API" in readme
    assert "https://docs.brightdata.com/api-reference/rest-api/unlocker/unlock-website" in readme
    assert "https://docs.brightdata.com/api-reference/rest-api/serp/serp-api" in readme


def test_live_web_page_collection_fails_closed_without_transport():
    manifest = web_manifest("https://publisher.example.org/page")
    calls = []

    with pytest.raises(InputError, match="fail.closed|unsupported"):
        brightdata.collect(
            manifest,
            approval=approval_for(manifest, retained=1),
            api_key="injected-test-value",
            zones={"web_unlocker": "web-zone"},
            transport=lambda request: calls.append(request),
            now="2026-10-05T10:00:00Z",
        )

    assert calls == []


@pytest.mark.parametrize("url", [
    "https://publisher.example.org/page?ref=public",
    "https://publisher.example.org/page?token=secret-value",
    "https://publisher.example.org/page?redirect=https%3A%2F%2Flocalhost",
])
def test_web_targets_reject_every_query_string(url):
    with pytest.raises(InputError, match="query"):
        brightdata.plan(web_manifest(url))


def test_serp_plan_and_receipt_redact_query_values():
    secret_query = "private acquisition target"
    manifest = serp_manifest(secret_query)
    planned = brightdata.plan(manifest)
    serialized_plan = json.dumps(planned)
    assert secret_query not in serialized_plan
    assert "%20" not in serialized_plan

    response = {"general": {"query": secret_query}, "organic": []}
    result = collect_serp(manifest, approval_for(manifest), lambda request: HttpResponse(200, {}, json.dumps(response).encode()))
    serialized_receipt = json.dumps(result["receipt"])
    assert secret_query not in serialized_receipt
    assert result["receipt"]["jobs"][0]["original_job"]["query"] == "[redacted]"


def test_retention_cap_is_enforced_before_request():
    manifest = serp_manifest()
    calls = []
    with pytest.raises(InputError, match="retained-record"):
        collect_serp(manifest, approval_for(manifest, retained=4), lambda request: calls.append(request))
    assert calls == []


def test_retention_cap_is_enforced_again_before_append(monkeypatch):
    manifest = serp_manifest()
    approval = approval_for(manifest, retained=5)
    fake_sources = [{"id": f"s{i}"} for i in range(6)]
    monkeypatch.setattr(brightdata, "_serp_sources", lambda *args: (fake_sources, [], {}))

    result = collect_serp(manifest, approval, lambda request: HttpResponse(200, {}, b'{"organic":[]}'))

    assert result["sources"] == []
    assert result["receipt"]["status"] == "failed"
    assert result["receipt"]["jobs"][0]["error_code"] == "retention_limit_exceeded"


def test_timeout_counts_attempt_before_dispatch_and_marks_completion_unknown():
    manifest = serp_manifest()

    result = collect_serp(manifest, approval_for(manifest), lambda request: (_ for _ in ()).throw(TransportError()))

    receipt = result["receipt"]
    assert receipt["requests_attempted"] == 1
    assert receipt["responses_received"] == 0
    assert receipt["completion_unknown"] is True
    assert receipt["status"] == "completion_unknown"


def test_unexpected_transport_exception_becomes_safe_unknown_receipt():
    manifest = serp_manifest()
    calls = []

    def transport(request):
        calls.append(request)
        raise RuntimeError("private transport message with injected-test-value")

    result = collect_serp(manifest, approval_for(manifest), transport)
    assert len(calls) == 1
    assert result["receipt"]["requests_attempted"] == 1
    assert result["receipt"]["responses_received"] == 0
    assert result["receipt"]["completion_unknown"] is True
    assert "private transport message" not in json.dumps(result)
    assert "injected-test-value" not in json.dumps(result)


def test_http_429_counts_response_and_stops_without_retry():
    manifest = serp_manifest()
    calls = []

    def transport(request):
        calls.append(request)
        return HttpResponse(429, {}, b"provider details must not be retained")

    result = collect_serp(manifest, approval_for(manifest), transport)
    receipt = result["receipt"]
    assert len(calls) == 1
    assert receipt["requests_attempted"] == 1
    assert receipt["responses_received"] == 1
    assert receipt["completion_unknown"] is False
    assert receipt["jobs"][0]["error_code"] == "provider_http_error"
    assert "provider details" not in json.dumps(result)


@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_provider_redirect_responses_are_failures(status):
    manifest = serp_manifest()
    result = collect_serp(manifest, approval_for(manifest), lambda request: HttpResponse(status, {"Location": "https://evil.invalid"}, b""))
    assert result["sources"] == []
    assert result["receipt"]["jobs"][0]["error_code"] == "provider_http_error"
    assert result["receipt"]["responses_received"] == 1


def test_deadline_bounds_request_timeout_and_marks_received_response_as_known():
    manifest = serp_manifest()
    ticks = iter([10.0, 10.0, 21.0])
    seen = []

    def transport(request):
        seen.append(request.timeout_seconds)
        return HttpResponse(200, {}, b'{"organic":[]}')

    result = collect_serp(manifest, approval_for(manifest), transport, deadline_seconds=10, clock=lambda: next(ticks))
    assert seen == [10]
    assert result["receipt"]["status"] == "failed"
    assert result["receipt"]["responses_received"] == 1
    assert result["receipt"]["completion_unknown"] is False
    assert result["receipt"]["jobs"][0]["error_code"] == "operation_deadline_exceeded"


def test_monotonic_deadline_interrupts_a_blocking_custom_transport():
    manifest = serp_manifest()
    started = time.monotonic()
    original_handler = signal.getsignal(signal.SIGALRM)

    def slow_transport(request):
        time.sleep(3)
        return HttpResponse(200, {}, b'{"organic":[]}')

    result = collect_serp(
        manifest, approval_for(manifest), slow_transport,
        deadline_seconds=1,
    )
    elapsed = time.monotonic() - started
    receipt = result["receipt"]

    assert elapsed < 2
    assert receipt["requests_attempted"] == 1
    assert receipt["responses_received"] == 0
    assert receipt["completion_unknown"] is True
    assert receipt["jobs"][0]["error_code"] == "operation_deadline_exceeded"
    assert signal.getsignal(signal.SIGALRM) == original_handler
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


def test_active_process_timer_refuses_collection_before_transport(monkeypatch):
    manifest = serp_manifest()
    calls = []
    monkeypatch.setattr(brightdata.signal, "getitimer", lambda which: (10.0, 0.0))

    with pytest.raises(InputError, match="another real-time process timer"):
        collect_serp(manifest, approval_for(manifest), lambda request: calls.append(request))
    assert calls == []


def test_monotonic_deadline_interrupts_slow_trickling_urllib_response():
    release_handler = threading.Event()

    class SlowHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(200)
            self.send_header("Content-Length", "100")
            self.end_headers()
            self.wfile.write(b"x")
            self.wfile.flush()
            release_handler.wait(3)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), SlowHandler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    started = time.monotonic()
    try:
        request = brightdata.HttpRequest("POST", f"http://127.0.0.1:{server.server_port}/", {}, b"", 3)
        with pytest.raises(brightdata.OperationDeadlineExceeded):
            with brightdata._wall_clock_deadline(started + 0.3):
                brightdata.urllib_transport(request)
        assert time.monotonic() - started < 1.5
    finally:
        release_handler.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def test_collection_write_failure_preserves_request_accounting(monkeypatch, tmp_path, capsys):
    manifest = serp_manifest()
    manifest_path = tmp_path / "manifest.private.json"
    approval_path = tmp_path / "approval.private.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    approval_path.write_text(json.dumps(approval_for(manifest)), encoding="utf-8")
    library = {
        "receipt": {
            "status": "complete",
            "requests_attempted": 1,
            "responses_received": 1,
            "completion_unknown": False,
        }
    }
    monkeypatch.setattr(cli, "collect", lambda *args, **kwargs: library)
    monkeypatch.setattr(cli, "_write_json", lambda *args, **kwargs: (_ for _ in ()).throw(InputError("output file could not be written")))
    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "injected-test-value")
    monkeypatch.setenv("BRIGHT_DATA_SERP_ZONE", "serp-zone")

    code = cli.main(["collect", str(manifest_path), "--out", str(tmp_path / "library.private.json"), "--live", "--accept-charges", "--approval", str(approval_path)])
    error = json.loads(capsys.readouterr().err)

    assert code == 2
    assert error["requests_attempted"] == 1
    assert error["responses_received"] == 1
    assert error["completion_unknown"] is False


def test_completion_unknown_survives_cli_output_write_failure(monkeypatch, tmp_path, capsys):
    manifest = serp_manifest()
    manifest_path = tmp_path / "manifest.private.json"
    approval_path = tmp_path / "approval.private.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    approval_path.write_text(json.dumps(approval_for(manifest)), encoding="utf-8")

    def collect_timeout(manifest_value, *, approval, api_key, zones, now):
        return brightdata.collect(
            manifest_value, approval=approval, api_key=api_key, zones=zones,
            transport=lambda request: (_ for _ in ()).throw(TransportError()), now=now,
        )

    monkeypatch.setattr(cli, "collect", collect_timeout)
    monkeypatch.setattr(cli, "_write_json", lambda *args, **kwargs: (_ for _ in ()).throw(InputError("output file could not be written")))
    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "injected-test-value")
    monkeypatch.setenv("BRIGHT_DATA_SERP_ZONE", "serp-zone")

    code = cli.main([
        "collect", str(manifest_path), "--out", str(tmp_path / "library.private.json"),
        "--live", "--accept-charges", "--approval", str(approval_path),
    ])
    error = json.loads(capsys.readouterr().err)

    assert code == 2
    assert error["requests_attempted"] == 1
    assert error["responses_received"] == 0
    assert error["completion_unknown"] is True


def test_report_set_rolls_back_when_second_commit_fails(monkeypatch, tmp_path):
    original_link = os.link
    calls = 0

    def fail_second(source, destination, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected failure")
        return original_link(source, destination, **kwargs)

    monkeypatch.setattr(cli.os, "link", fail_second)
    with pytest.raises(InputError, match="transaction"):
        cli._write_report_set(tmp_path, {"report.json": "json", "pitches.md": "md", "pitches.csv": "csv"}, overwrite=False)
    assert list(tmp_path.iterdir()) == []


def test_report_set_staging_failure_removes_unregistered_partial_files(monkeypatch, tmp_path):
    original_fsync = os.fsync
    calls = 0

    def fail_second_fsync(fd):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected stage flush failure")
        return original_fsync(fd)

    monkeypatch.setattr(cli.os, "fsync", fail_second_fsync)
    with pytest.raises(InputError, match="transaction"):
        cli._write_report_set(tmp_path, {"report.json": "json", "pitches.md": "md", "pitches.csv": "csv"}, overwrite=False)
    assert list(tmp_path.iterdir()) == []


def test_report_set_no_clobber_survives_race(monkeypatch, tmp_path):
    original_link = os.link
    raced = False

    def race(source, destination, **kwargs):
        nonlocal raced
        if not raced:
            raced = True
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=kwargs["dst_dir_fd"])
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write("attacker")
        return original_link(source, destination, **kwargs)

    monkeypatch.setattr(cli.os, "link", race)
    with pytest.raises(InputError, match="transaction"):
        cli._write_report_set(tmp_path, {"report.json": "safe", "pitches.md": "safe", "pitches.csv": "safe"}, overwrite=False)
    assert (tmp_path / "report.json").read_text(encoding="utf-8") == "attacker"
    assert not (tmp_path / "pitches.md").exists()
    assert not (tmp_path / "pitches.csv").exists()


def test_report_set_rejects_symlink_target(tmp_path):
    outside = tmp_path / "outside"
    outside.write_text("do not replace", encoding="utf-8")
    (tmp_path / "report.json").symlink_to(outside)

    with pytest.raises(InputError, match="symlink"):
        cli._write_report_set(tmp_path, {"report.json": "new", "pitches.md": "md", "pitches.csv": "csv"}, overwrite=True)
    assert outside.read_text(encoding="utf-8") == "do not replace"


def test_report_set_overwrite_failure_restores_all_previous_artifacts(monkeypatch, tmp_path):
    names = {"report.json": "old-json", "pitches.md": "old-md", "pitches.csv": "old-csv"}
    cli._write_report_set(tmp_path, names, overwrite=False)
    before = {name: (tmp_path / name).read_bytes() for name in names}
    original_link = os.link
    commits = 0

    def fail_second_commit(source, destination, **kwargs):
        nonlocal commits
        if source.endswith(".tmp"):
            commits += 1
        if source.endswith(".tmp") and commits == 2:
            raise OSError("injected overwrite commit failure")
        return original_link(source, destination, **kwargs)

    monkeypatch.setattr(cli.os, "link", fail_second_commit)
    with pytest.raises(InputError, match="transaction"):
        cli._write_report_set(tmp_path, {name: f"new-{name}" for name in names}, overwrite=True)
    assert {name: (tmp_path / name).read_bytes() for name in names} == before
    assert not list(tmp_path.glob(".*.backup.*"))


def test_report_set_directory_swap_after_commit_rolls_back_only_pinned_directory(monkeypatch, tmp_path):
    out_dir = tmp_path / "reports"
    displaced = tmp_path / "reports-displaced"
    original_link = os.link
    swapped = False

    def swap_after_first_commit(source, destination, **kwargs):
        nonlocal swapped
        result = original_link(source, destination, **kwargs)
        if not swapped:
            swapped = True
            os.rename(out_dir, displaced)
            out_dir.mkdir()
        return result

    monkeypatch.setattr(cli.os, "link", swap_after_first_commit)
    with pytest.raises(InputError, match="transaction|directory changed"):
        cli._write_report_set(out_dir, {"report.json": "json", "pitches.md": "md", "pitches.csv": "csv"}, overwrite=False)

    assert list(out_dir.iterdir()) == []
    assert list(displaced.iterdir()) == []


def test_report_set_rollback_preserves_post_commit_replacement(monkeypatch, tmp_path):
    out_dir = tmp_path / "reports"
    out_dir.mkdir()
    original_link = os.link
    calls = 0

    def replace_after_first_commit(source, destination, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            target_name = "report.json"
            os.unlink(target_name, dir_fd=kwargs["dst_dir_fd"])
            fd = os.open(target_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=kwargs["dst_dir_fd"])
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write("attacker replacement")
            raise OSError("injected second-commit failure")
        return original_link(source, destination, **kwargs)

    monkeypatch.setattr(cli.os, "link", replace_after_first_commit)
    with pytest.raises(InputError, match="transaction"):
        cli._write_report_set(out_dir, {"report.json": "safe", "pitches.md": "md", "pitches.csv": "csv"}, overwrite=False)

    assert (out_dir / "report.json").read_text(encoding="utf-8") == "attacker replacement"
    assert not (out_dir / "pitches.md").exists()
    assert not (out_dir / "pitches.csv").exists()


def test_report_set_rollback_does_not_unlink_target_swapped_at_removal(monkeypatch, tmp_path):
    out_dir = tmp_path / "reports"
    original_link = os.link
    original_rename = os.rename
    links = 0
    raced = False

    def fail_second_link(source, destination, **kwargs):
        nonlocal links
        links += 1
        if links == 2:
            raise OSError("injected commit failure")
        return original_link(source, destination, **kwargs)

    def replace_during_rollback(source, destination, **kwargs):
        nonlocal raced
        if source == "report.json" and ".rollback." in destination and not raced:
            raced = True
            os.unlink(source, dir_fd=kwargs["src_dir_fd"])
            fd = os.open(source, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=kwargs["src_dir_fd"])
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write("attacker at rollback boundary")
        return original_rename(source, destination, **kwargs)

    monkeypatch.setattr(cli.os, "link", fail_second_link)
    monkeypatch.setattr(cli.os, "rename", replace_during_rollback)
    with pytest.raises(InputError, match="replacement targets were preserved"):
        cli._write_report_set(out_dir, {"report.json": "safe", "pitches.md": "md", "pitches.csv": "csv"}, overwrite=False)

    assert raced is True
    assert (out_dir / "report.json").read_text(encoding="utf-8") == "attacker at rollback boundary"
    recovery_files = list(set(out_dir.glob("*.rollback.*")) | set(out_dir.glob(".report.json.rollback.*")))
    assert len(recovery_files) == 1


def test_report_set_overwrite_rollback_preserves_replacement_and_original_backup(monkeypatch, tmp_path):
    out_dir = tmp_path / "reports"
    old = {"report.json": "old-report", "pitches.md": "old-md", "pitches.csv": "old-csv"}
    cli._write_report_set(out_dir, old, overwrite=False)
    original_link = os.link
    commits = 0

    def replace_after_first_commit(source, destination, **kwargs):
        nonlocal commits
        if source.endswith(".tmp"):
            commits += 1
        if source.endswith(".tmp") and commits == 2:
            target_name = "report.json"
            os.unlink(target_name, dir_fd=kwargs["dst_dir_fd"])
            fd = os.open(target_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=kwargs["dst_dir_fd"])
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write("replacement")
            raise OSError("injected second commit failure")
        return original_link(source, destination, **kwargs)

    monkeypatch.setattr(cli.os, "link", replace_after_first_commit)
    with pytest.raises(InputError, match="transaction"):
        cli._write_report_set(out_dir, {name: f"new-{name}" for name in old}, overwrite=True)

    assert (out_dir / "report.json").read_text(encoding="utf-8") == "replacement"
    assert (out_dir / "pitches.md").read_text(encoding="utf-8") == old["pitches.md"]
    assert (out_dir / "pitches.csv").read_text(encoding="utf-8") == old["pitches.csv"]
    retained_backups = list(out_dir.glob(".report.json.backup.*"))
    assert len(retained_backups) == 1
    assert retained_backups[0].read_text(encoding="utf-8") == old["report.json"]


def test_report_set_rejects_symlink_output_directory(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "linked"
    link.symlink_to(real, target_is_directory=True)

    with pytest.raises(InputError, match="pin|no-follow|transaction"):
        cli._write_report_set(link, {"report.json": "json", "pitches.md": "md", "pitches.csv": "csv"}, overwrite=False)
    assert list(real.iterdir()) == []
