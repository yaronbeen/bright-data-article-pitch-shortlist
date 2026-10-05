"""Deterministic, publication-safe report renderers."""

from __future__ import annotations

import csv
import html
import io
import json
import re
import unicodedata
from typing import Any

from .core import redact_text_urls

CSV_COLUMNS = [
    "publisher_id", "publisher", "qualification", "exclusion_reasons",
    "fit_excerpt", "example_url", "accepted_formats", "originality_state",
    "word_min", "word_max", "route_state", "submission_url", "unknowns",
    "pitch_draft", "evidence_source_ids", "evidence_urls", "schema_version",
    "evidence_provenance", "provenance_state", "contains_synthetic_data",
]
GUIDELINE_CITATION_REDACTION = "[editorial guideline wording omitted; structured rule state retained]"
GUIDELINE_CLAIM_REDACTIONS = (
    (
        re.compile(r"\bWe (?:only )?accept (?:tutorials|comparisons|case studies|checklists)\.", re.IGNORECASE),
        "[format-availability statement omitted; classified internally as guidance]",
    ),
    (
        re.compile(r"\bWe do not accept (?:tutorials|comparisons|case studies|checklists)\.", re.IGNORECASE),
        "[format-availability statement omitted; classified internally as guidance]",
    ),
    (
        re.compile(r"\b(?:We do not accept guest posts|Guest contributions are closed)\.", re.IGNORECASE),
        "[submission-policy statement omitted; classified internally as guidance]",
    ),
    (
        re.compile(r"\b(?:Only original, unpublished work|We do not accept previously published work)\.", re.IGNORECASE),
        "[originality guideline omitted; classified internally as guidance]",
    ),
    (
        re.compile(r"\bWe accept republished articles\.", re.IGNORECASE),
        "[republishing guideline omitted; classified internally as guidance]",
    ),
    (
        re.compile(r"\bWord count: \d+-\d+ words\.", re.IGNORECASE),
        "[length guideline omitted; classified internally as guidance]",
    ),
    (
        re.compile(r"\bA worked example is required\.", re.IGNORECASE),
        "[format requirement omitted; classified internally as guidance]",
    ),
    (
        re.compile(
            r"\b(?:we|our team|the publisher|the editor|the outlet)\s+"
            r"(?:(?:is|are|will be|will)\s+)?(?:accept\w*|approv\w*|guarantee\w*)"
            r"[^.!?\n]*(?:[.!?]|$)",
            re.IGNORECASE,
        ),
        "[editorial outcome claim omitted]",
    ),
    (
        re.compile(
            r"\b(?:this|it|the pitch|the article|the submission)\s+will\s+"
            r"(?:be\s+)?(?:publish\w*|accept\w*|approv\w*)[^.!?\n]*(?:[.!?]|$)",
            re.IGNORECASE,
        ),
        "[editorial outcome claim omitted]",
    ),
    (
        re.compile(r"\b(?:acceptance|publication|placement)\s+(?:is\s+)?guaranteed\b[^.!?\n]*(?:[.!?]|$)", re.IGNORECASE),
        "[editorial outcome claim omitted]",
    ),
)


def _redact_guideline_claims(text: str) -> str:
    for pattern, replacement in GUIDELINE_CLAIM_REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def _md(value: Any) -> str:
    text = "" if value is None else str(value)
    text = redact_text_urls(text)
    text = _redact_guideline_claims(text)
    text = " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split())
    text = html.escape(text, quote=False)
    return re.sub(r"([\\`*_{}\[\]|])", r"\\\1", text)


def _csv_safe(value: Any) -> str:
    if value is None:
        return ""
    text = _redact_guideline_claims(redact_text_urls(str(value)))
    index = 0
    while index < len(text) and (text[index].isspace() or unicodedata.category(text[index]) == "Cc"):
        index += 1
    stripped = text[index:]
    return "'" + text if stripped.startswith(("=", "+", "-", "@")) else text


def render_markdown(report: dict[str, Any]) -> str:
    provenances = {item.get("provenance") for item in report.get("source_index", [])}
    lines = ["# Article Pitch Shortlist", ""]
    if provenances == {"synthetic_fixture"}:
        lines += ["> **Synthetic demonstration:** All cited source material in this report is invented fixture data.", ""]
    elif "synthetic_fixture" in provenances:
        lines += ["> **Mixed provenance:** This report mixes invented synthetic fixture sources with operator-supplied or Bright Data sources. Check each evidence source before sharing.", ""]
    lines += [
        f"- Decision: `{_md(report.get('decision'))}`",
        f"- Status: `{_md(report.get('status'))}`",
        f"- Analysis method: `{_md(report.get('analysis_method'))}`",
        f"- Draft method: `{_md(report.get('draft_method'))}`",
        f"- Transport contract: `{_md(report.get('transport_contract_version'))}`",
        f"- Audience: {_md(report.get('scope', {}).get('audience'))}",
        f"- As of: {_md(report.get('scope', {}).get('as_of')) or 'not supplied'}",
        "",
        "No submissions are made. Qualification means only that the declared proposal passed the literal rules visible in the selected sources.",
        "",
        "## Shortlist",
        "",
    ]
    cards = report.get("cards", [])
    if not cards:
        lines += ["No publisher passed into the shortlist.", ""]
    for row in cards:
        lines += [
            f"### {_md(row.get('publisher'))}", "",
            f"- Qualification: `{_md(row.get('qualification'))}`",
            f"- Selected example: {_md(row.get('example_url'))}",
            f"- Fit excerpt: > {_md(row.get('fit_excerpt'))}" if row.get("fit_excerpt") else "- Fit excerpt: unknown",
            f"- Submission route: {_md(row.get('submission_url')) or 'not observed'}",
            f"- Unknowns: {_md('; '.join(row.get('unknowns', []))) or 'none declared'}",
        ]
        if row.get("pitch_draft"):
            lines += ["", "**Draft for human review**", "", _md(row["pitch_draft"])]
        elif row.get("research_task"):
            lines += ["", f"**Research task:** {_md(row['research_task'])}"]
        lines.append("")
    lines += ["## Explicit Exclusions", ""]
    if not report.get("excluded"):
        lines += ["None.", ""]
    else:
        lines += ["| Publisher | Reasons |", "|---|---|"]
        for row in report["excluded"]:
            lines.append(f"| {_md(row.get('publisher'))} | {_md('; '.join(row.get('exclusion_reasons', [])))} |")
        lines.append("")
    lines += ["## Evidence Appendix", ""]
    index = {item["id"]: item for item in report.get("source_index", [])}
    citations: list[dict[str, str]] = []
    for row in report.get("publishers", []):
        citations.extend(row.get("evidence", []))
    if not citations:
        lines += ["No source-backed excerpts were available.", ""]
    for citation in citations:
        source = index.get(citation["source_id"], {})
        identity = source.get("url") or "local operator note"
        if source.get("record_id"):
            identity += f" (record {source['record_id']})"
        quote = GUIDELINE_CITATION_REDACTION if source.get("role") == "submission_guidelines" else citation["quote"]
        lines += [
            f"- `{_md(citation['source_id'])}/{_md(citation['block_id'])}`: \"{_md(quote)}\"",
            f"  Source: {_md(identity)}; provenance: `{_md(source.get('provenance'))}`; observed {_md(source.get('observed_at'))}; SHA-256 `{_md(source.get('content_sha256'))}`",
        ]
    lines += ["", "## Limitations", "", "This is deterministic literal-rule analysis of selected sources, not a directory, publisher-wide coverage claim, acceptance prediction, originality verification, or privacy guarantee. Inspect free-text excerpts before sharing.", ""]
    return "\n".join(lines)


def render_csv(report: dict[str, Any]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    source_urls = {item["id"]: item.get("url") for item in report.get("source_index", [])}
    source_provenance = {item["id"]: item.get("provenance") for item in report.get("source_index", [])}
    provenances = set(source_provenance.values())
    contains_synthetic_data = "synthetic_fixture" in provenances
    provenance_state = (
        "mixed" if contains_synthetic_data and len(provenances) > 1
        else "synthetic" if contains_synthetic_data
        else "operator_supplied" if provenances == {"operator_supplied"}
        else "bright_data" if provenances == {"bright_data"}
        else "none" if not provenances
        else "non_synthetic_mixed"
    )
    for row in report.get("publishers", []):
        source_ids = list(dict.fromkeys(item["source_id"] for item in row.get("evidence", [])))
        values = {
            "publisher_id": row.get("publisher_id"), "publisher": row.get("publisher"),
            "qualification": row.get("qualification"),
            "exclusion_reasons": ";".join(row.get("exclusion_reasons", [])),
            "fit_excerpt": row.get("fit_excerpt"), "example_url": row.get("example_url"),
            "accepted_formats": ";".join(row.get("accepted_formats", [])),
            "originality_state": row.get("originality_state"), "word_min": row.get("word_min"),
            "word_max": row.get("word_max"), "route_state": row.get("route_state"),
            "submission_url": row.get("submission_url"), "unknowns": ";".join(row.get("unknowns", [])),
            "pitch_draft": row.get("pitch_draft"), "evidence_source_ids": ";".join(source_ids),
            "evidence_urls": ";".join(source_urls[source_id] or "" for source_id in source_ids),
            "evidence_provenance": ";".join(source_provenance[source_id] or "" for source_id in source_ids),
            "provenance_state": provenance_state,
            "contains_synthetic_data": str(contains_synthetic_data).lower(),
            "schema_version": "1.1",
        }
        writer.writerow({key: _csv_safe(values.get(key)) for key in CSV_COLUMNS})
    return output.getvalue()


def render_json(report: dict[str, Any]) -> str:
    guideline_source_ids = {
        item.get("id") for item in report.get("source_index", [])
        if item.get("role") == "submission_guidelines"
    }

    def sanitize(value: Any) -> Any:
        if isinstance(value, str):
            return _redact_guideline_claims(redact_text_urls(value))
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        if isinstance(value, dict):
            result = {key: sanitize(item) for key, item in value.items()}
            if result.get("source_id") in guideline_source_ids and "block_id" in result and "quote" in result:
                result["quote"] = GUIDELINE_CITATION_REDACTION
            return result
        return value

    return json.dumps(sanitize(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
