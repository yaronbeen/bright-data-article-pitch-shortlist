"""Acceptance contract for the Article Pitch Shortlist public API."""

import importlib

import pytest


@pytest.fixture(scope="module")
def shortlist():
    return importlib.import_module("article_pitch_shortlist")


def test_normalizes_hostname_case_trailing_dot_and_explicit_443(shortlist):
    normalize = shortlist.normalize_publisher_host
    assert normalize("HTTPS://North.Example.com.:443/path") == "north.example.com"


@pytest.mark.parametrize(
    ("publisher", "source", "same"),
    [
        ("north.example.com", "www.north.example.com", False),
        ("north.example.com", "blog.north.example.com", False),
        ("north.example.com", "south.example.com", False),
        ("north.example.com", "north.example.com", True),
    ],
)
def test_publisher_identity_does_not_collapse_hosts(shortlist, publisher, source, same):
    assert shortlist.same_publisher_host(publisher, source) is same


def test_corrected_north_fixture_has_observed_same_host_route(shortlist):
    result = shortlist.evaluate_publisher(
        publisher_host="north.example.com",
        example_url="https://north.example.com/example",
        example_body="A guide to project import.",
        guidelines_body=(
            "We accept tutorials. Only original, unpublished work. "
            "Word count: 500-800 words. A worked example is required.\n"
            "[submission form](https://north.example.com/contribute)"
        ),
        topic_phrase="project import",
        proposed_format="tutorial",
        planned_word_count=700,
        has_worked_example=True,
        method="new_followup",
        is_unpublished=True,
    )
    assert result.route_state == "observed_route"
    assert result.submission_url == "https://north.example.com/contribute"
    assert result.qualification == "ready_for_human_pitch_review"
    assert result.guideline_evidence


@pytest.mark.parametrize(
    "route_url",
    [
        "https://www.north.example.com/contribute",
        "https://forms.example.net/north",
    ],
)
def test_route_must_be_observed_in_guidelines_and_on_exact_publisher_host(shortlist, route_url):
    result = shortlist.evaluate_publisher(
        publisher_host="north.example.com",
        example_url="https://north.example.com/example",
        example_body="A guide to project import.",
        guidelines_body=f"[submission form]({route_url})",
        topic_phrase="project import",
        proposed_format="tutorial",
        planned_word_count=None,
        has_worked_example=False,
        method="new_followup",
        is_unpublished=True,
    )
    assert result.route_state == "not_observed"
    assert result.submission_url is None


def test_rejects_example_from_nonmatching_host(shortlist):
    with pytest.raises(ValueError, match="host"):
        shortlist.validate_publisher_sources(
            publisher_host="north.example.com",
            example_url="https://www.north.example.com/example",
            guideline_url="https://north.example.com/guidelines",
        )


def test_reports_explicit_rejection_with_reason_and_evidence(shortlist):
    result = shortlist.evaluate_publisher(
        publisher_host="north.example.com",
        example_url="https://north.example.com/example",
        example_body="A guide to project import.",
        guidelines_body="We do not accept tutorials.",
        topic_phrase="project import",
        proposed_format="tutorial",
        planned_word_count=None,
        has_worked_example=False,
        method="new_followup",
        is_unpublished=True,
    )
    assert result.qualification == "explicit_mismatch"
    assert "explicitly_rejected_format" in result.reasons
    assert result.guideline_evidence


def test_reports_absent_topic_body_evidence_as_exclusion_reason(shortlist):
    result = shortlist.evaluate_publisher(
        publisher_host="north.example.com",
        example_url="https://north.example.com/example",
        example_body="A general operations overview.",
        guidelines_body="",
        topic_phrase="project import",
        proposed_format="tutorial",
        planned_word_count=None,
        has_worked_example=False,
        method="new_followup",
        is_unpublished=True,
    )
    assert "no_topic_evidence_in_selected_example" in result.reasons


def test_reuse_of_published_asset_violates_original_unpublished_rule(shortlist):
    result = shortlist.evaluate_publisher(
        publisher_host="north.example.com",
        example_url="https://north.example.com/example",
        example_body="A guide to project import.",
        guidelines_body="Only original, unpublished work.",
        topic_phrase="project import",
        proposed_format="tutorial",
        planned_word_count=None,
        has_worked_example=False,
        method="reuse_asset",
        is_unpublished=True,
        asset_publication_state="published",
    )
    assert result.qualification == "explicit_mismatch"
    assert "prior_publication_disallowed" in result.reasons


def test_pitch_uses_only_supplied_article_facts(shortlist):
    draft = shortlist.draft_pitch(
        observed_title="Importing project data",
        observed_title_is_cited_h1=True,
        example_url="https://north.example.com/example",
        matched_topic_phrase="project import",
        proposed_title="Diagnose a failed project import",
        proposed_format="tutorial",
        audience="small-team operators",
        contribution="A synthetic malformed-date example and a corrected-row retry checklist.",
        method="new_followup",
        is_unpublished=True,
        asset_title="Choosing an import method",
        planned_word_count=700,
        guideline_acknowledgements=["The guidelines require original, unpublished work."],
    )
    assert '"Importing project data"' in draft
    assert "project import" in draft
    assert "700 words" in draft
    assert "new follow-up" in draft
    assert "performance" not in draft.lower()
    assert "accept" not in draft.lower()
    assert "expert" not in draft.lower()
