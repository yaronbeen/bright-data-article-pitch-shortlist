"""Deterministic analysis for the Article Pitch Shortlist."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

PROJECT = "article-pitch-shortlist"
SCHEMA_VERSION = "1.0"
TRANSPORT_CONTRACT_VERSION = "1.0"
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024
ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
BLOCK_ID_RE = re.compile(r"^b\d{4}$")
UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
URL_IN_TEXT_RE = re.compile(r"https?://[^\s<>\]\)\"']+", re.IGNORECASE)
FORMATS = {"tutorial", "comparison", "case_study", "checklist"}
SOURCE_ROLES = {
    "own_article": "page",
    "publisher_example": "page",
    "submission_guidelines": "page",
    "discovery": "search_result",
    "context_note": "operator_note",
}
SOURCE_KEYS = {
    "id", "kind", "role", "url", "title", "text", "status",
    "observed_at", "published_at", "provider_date", "record_id",
    "record_id_origin", "provenance",
}


class InputError(ValueError):
    """A safe, operator-facing input validation error."""

    code = "invalid_input"


@dataclass(frozen=True)
class EvaluationResult:
    publisher_host: str
    qualification: str
    reasons: list[str]
    topic_state: str
    matched_topic_phrase: str | None
    fit_excerpt: str | None
    format_state: str
    accepted_formats: list[str]
    originality_state: str
    word_min: int | None
    word_max: int | None
    worked_example_state: str
    route_state: str
    submission_url: str | None
    unknowns: list[str]
    example_evidence: list[dict[str, str]]
    guideline_evidence: list[dict[str, str]]


def _object(value: Any, name: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"{name} must be an object")
    unknown = set(value) - keys
    if unknown:
        raise InputError(f"{name} has unknown keys: {', '.join(sorted(unknown))}")
    return value


def _string(value: Any, name: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or not minimum <= len(value) <= maximum:
        raise InputError(f"{name} must be a non-blank string of {minimum}-{maximum} characters")
    if "\x00" in value or any(ord(char) < 32 and char not in "\t\n\r" for char in value):
        raise InputError(f"{name} contains unsupported control characters")
    return value


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise InputError(f"{name} must be an integer from {minimum} to {maximum}")
    return value


def _timestamp(value: Any, name: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not UTC_TIMESTAMP_RE.fullmatch(value):
        raise InputError(f"{name} must be a UTC RFC3339 timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise InputError(f"{name} must be a valid UTC RFC3339 timestamp") from exc
    return value


def redact_url_query(url: str) -> str:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return url
    if not parsed.query:
        return url
    values = [(key, "[redacted]" if value else "") for key, value in parse_qsl(parsed.query, keep_blank_values=True)]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(values), parsed.fragment))


def redact_text_urls(text: str) -> str:
    def redact(match: re.Match[str]) -> str:
        value = match.group(0)
        suffix = ""
        while value and value[-1] in ".,;:!":
            suffix = value[-1] + suffix
            value = value[:-1]
        return redact_url_query(value) + suffix

    return URL_IN_TEXT_RE.sub(redact, text)


def canonical_url(url: str, *, allow_fixture: bool = True, redact_query: bool = True) -> str:
    _string(url, "URL", 1, 2048)
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise InputError("URL is invalid") from exc
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise InputError("URL must be an absolute credential-free HTTPS URL")
    if parsed.fragment:
        raise InputError("URL fragments are not allowed")
    host = parsed.hostname.lower().rstrip(".")
    if not host:
        raise InputError("URL host is invalid")
    netloc = host if port in (None, 443) else f"{host}:{port}"
    canonical = urlunsplit(("https", netloc, parsed.path, parsed.query, ""))
    return redact_url_query(canonical) if redact_query else canonical


def normalize_publisher_host(url_or_host: str) -> str:
    value = _string(url_or_host, "publisher host", 1, 2048)
    candidate = value if "://" in value else f"https://{value}"
    canonical = canonical_url(candidate)
    return urlsplit(canonical).hostname or ""


def same_publisher_host(publisher: str, source: str) -> bool:
    return normalize_publisher_host(publisher) == normalize_publisher_host(source)


def validate_publisher_sources(*, publisher_host: str, example_url: str, guideline_url: str | None = None) -> None:
    expected = normalize_publisher_host(publisher_host)
    if normalize_publisher_host(example_url) != expected:
        raise InputError("example URL host does not match publisher host")
    if guideline_url is not None and normalize_publisher_host(guideline_url) != expected:
        raise InputError("guideline URL host does not match publisher host")


def normalize_text(text: str) -> tuple[str, list[dict[str, Any]]]:
    if not isinstance(text, str):
        raise InputError("source text must be a string")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if "\x00" in text or any(ord(char) < 32 and char not in "\t\n" for char in text):
        raise InputError("source text contains unsupported control characters")
    text = redact_text_urls(text)
    if text.lstrip().lower().startswith(("<!doctype html", "<html", "<body")):
        raise InputError("unsupported_content_format")
    pieces: list[str] = []
    paragraph: list[str] = []
    for line in text.split("\n"):
        if re.fullmatch(r"[\t ]*", line):
            if paragraph:
                pieces.append("\n".join(paragraph))
                paragraph = []
            continue
        if re.fullmatch(r"[\t ]*#{1,6}\s+.+?\s*#*[\t ]*", line):
            if paragraph:
                pieces.append("\n".join(paragraph))
                paragraph = []
            pieces.append(line)
        else:
            paragraph.append(line)
    if paragraph:
        pieces.append("\n".join(paragraph))
    blocks: list[dict[str, Any]] = []
    for piece in pieces:
        piece = re.sub(r"\s+", " ", piece, flags=re.UNICODE).strip()
        if not piece:
            continue
        heading = re.fullmatch(r"(#{1,6})\s+(.+?)\s*#*", piece)
        blocks.append({
            "id": f"b{len(blocks) + 1:04d}",
            "text": heading.group(2).strip() if heading else piece,
            "heading": bool(heading),
            "heading_level": len(heading.group(1)) if heading else None,
        })
    return "\n\n".join(block["text"] for block in blocks), blocks


def _sentences(block: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])(?:\s+|$)", block) if part.strip()]


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    escaped = re.escape(re.sub(r"\s+", " ", phrase.casefold().strip()))
    return re.compile(rf"(?<![^\W_]){escaped}(?![^\W_])")


def _phrase_hit(text: str, phrase: str) -> bool:
    return bool(_phrase_pattern(phrase).search(re.sub(r"\s+", " ", text.casefold())))


def _casefold_with_positions(text: str) -> tuple[str, list[int]]:
    folded: list[str] = []
    positions: list[int] = []
    for position, character in enumerate(text):
        value = character.casefold()
        folded.append(value)
        positions.extend([position] * len(value))
    return "".join(folded), positions


def _excerpt(text: str, phrase: str, limit: int = 240) -> str:
    if len(text) <= limit:
        return text
    folded, positions = _casefold_with_positions(text)
    match = _phrase_pattern(phrase).search(folded)
    hit_start = positions[match.start()] if match and match.start() < len(positions) else 0
    start = max(0, hit_start - 80)
    return text[start:start + limit]


def _citation(source_id: str, block_id: str, quote: str, *, hit: str | None = None) -> dict[str, str]:
    if len(quote) > 240:
        quote = _excerpt(quote, hit or quote[:1])
    return {"source_id": source_id, "block_id": block_id, "quote": quote}


def _literal_rule_evidence(text: str, source_id: str = "guidelines") -> tuple[dict[str, Any], list[dict[str, str]]]:
    _, blocks = normalize_text(text)
    state: dict[str, Any] = {
        "accepted": [], "only": [], "rejected": [], "closed": False,
        "original_only": False, "republishing": False, "ranges": [],
        "worked_required": False,
    }
    evidence: list[dict[str, str]] = []
    plural = {"tutorials": "tutorial", "comparisons": "comparison", "case studies": "case_study", "checklists": "checklist"}
    for block in blocks:
        if block["heading"]:
            continue
        for sentence in _sentences(block["text"]):
            folded = sentence.casefold()
            matched = False
            for prefix, field in (("we accept ", "accepted"), ("we only accept ", "only"), ("we do not accept ", "rejected")):
                for label, format_name in plural.items():
                    if folded == f"{prefix}{label}.":
                        state[field].append(format_name)
                        matched = True
            if folded in {"we do not accept guest posts.", "guest contributions are closed."}:
                state["closed"] = True
                matched = True
            if folded in {"only original, unpublished work.", "we do not accept previously published work."}:
                state["original_only"] = True
                matched = True
            if folded == "we accept republished articles.":
                state["republishing"] = True
                matched = True
            range_match = re.fullmatch(r"word count: (\d+)-(\d+) words\.", folded)
            if range_match:
                low, high = map(int, range_match.groups())
                if 100 <= low <= high <= 10000:
                    state["ranges"].append((low, high))
                    matched = True
            if folded == "a worked example is required.":
                state["worked_required"] = True
                matched = True
            if matched:
                evidence.append(_citation(source_id, block["id"], sentence))
    return state, evidence


ROUTE_RE = re.compile(r"\[([^\]]+)\]\((https://[^\s)]+)\)", re.IGNORECASE)
ROUTE_LABELS = {"submission form", "submit an article", "submit a pitch", "pitch form", "submit your pitch"}
OUTCOME_LANGUAGE_RE = re.compile(
    r"\b(?:accepts?|accepting|accepted|acceptance|approves?|approving|approved|approval|"
    r"guarantees?|guaranteeing|guaranteed)\b|"
    r"\bwill\s+(?:be\s+)?(?:published|publish|accepted|accept|approved|approve)\b|"
    r"\b(?:is|are|gets?)\s+(?:being\s+)?published\b",
    re.IGNORECASE,
)


def evaluate_publisher(
    *, publisher_host: str, example_url: str, example_body: str,
    guidelines_body: str, topic_phrase: str, proposed_format: str,
    planned_word_count: int | None, has_worked_example: bool,
    method: str, is_unpublished: bool, asset_publication_state: str = "published",
) -> EvaluationResult:
    host = normalize_publisher_host(publisher_host)
    validate_publisher_sources(publisher_host=host, example_url=example_url)
    if proposed_format not in FORMATS:
        raise InputError("unsupported proposed format")
    if method not in {"reuse_asset", "new_followup"}:
        raise InputError("unsupported proposal method")
    if planned_word_count is not None:
        _integer(planned_word_count, "planned_word_count", 100, 10000)

    _, example_blocks = normalize_text(example_body)
    example_evidence: list[dict[str, str]] = []
    fit_excerpt = None
    for block in example_blocks:
        if block["heading"]:
            continue
        for sentence in _sentences(block["text"]):
            if _phrase_hit(sentence, topic_phrase):
                fit_excerpt = _excerpt(sentence, topic_phrase)
                example_evidence.append(_citation("example", block["id"], fit_excerpt))
                break
        if fit_excerpt:
            break
    topic_state = "body_evidence_found" if fit_excerpt else "not_found"

    rules, guideline_evidence = _literal_rule_evidence(guidelines_body)
    stated_accepted = list(dict.fromkeys(rules["accepted"]))
    only = list(dict.fromkeys(rules["only"]))
    accepted = list(dict.fromkeys(stated_accepted + only))
    rejected = list(dict.fromkeys(rules["rejected"]))
    closed_rule_conflict = len(only) > 1 or bool(only and any(item not in only for item in stated_accepted))
    format_conflict = closed_rule_conflict or (proposed_format in accepted and proposed_format in rejected)
    closed_set_mismatch = bool(only) and proposed_format not in only
    format_state = "conflicting" if format_conflict else (
        "explicitly_rejected" if proposed_format in rejected else (
            "closed_set_mismatch" if closed_set_mismatch else (
                "explicitly_accepted" if proposed_format in accepted else "not_stated"
            )
        )
    )

    originality_conflict = rules["original_only"] and rules["republishing"]
    if originality_conflict:
        originality_state = "conflicting"
    elif rules["original_only"]:
        originality_state = "original_unpublished_required"
    elif rules["republishing"]:
        originality_state = "republishing_allowed"
    else:
        originality_state = "not_stated"

    ranges = list(dict.fromkeys(rules["ranges"]))
    range_conflict = len(ranges) > 1
    word_min, word_max = ranges[0] if len(ranges) == 1 else (None, None)
    route_candidates: list[str] = []
    external_route_seen = False
    _, guideline_blocks = normalize_text(guidelines_body)
    for block in guideline_blocks:
        if block["heading"]:
            continue
        for match in ROUTE_RE.finditer(block["text"]):
            label, route = match.groups()
            if label.casefold().strip() not in ROUTE_LABELS:
                continue
            guideline_evidence.append(_citation("guidelines", block["id"], match.group(0), hit=label))
            try:
                if normalize_publisher_host(route) == host:
                    route_candidates.append(canonical_url(route))
                else:
                    external_route_seen = True
            except InputError:
                continue
    route_candidates = list(dict.fromkeys(route_candidates))
    route_state = "observed_route" if len(route_candidates) == 1 else ("conflicting_routes" if len(route_candidates) > 1 else "not_observed")

    reasons: list[str] = []
    if rules["closed"]:
        reasons.append("submissions_closed")
    if proposed_format in rejected and not format_conflict:
        reasons.append("explicitly_rejected_format")
    if closed_set_mismatch and not format_conflict:
        reasons.append("closed_format_set_mismatch")
    prior_publication = (method == "reuse_asset" and asset_publication_state == "published") or not is_unpublished
    if rules["original_only"] and prior_publication and not originality_conflict:
        reasons.append("prior_publication_disallowed")
    if word_min is not None and planned_word_count is not None and not word_min <= planned_word_count <= word_max:
        reasons.append("stated_word_count_mismatch")
    if rules["worked_required"] and not has_worked_example:
        reasons.append("worked_example_required_but_absent")
    if not fit_excerpt:
        reasons.append("no_topic_evidence_in_selected_example")

    conflicts = format_conflict or originality_conflict or range_conflict or route_state == "conflicting_routes"
    unknowns: list[str] = []
    if format_state == "not_stated":
        unknowns.append("format_permission_not_stated")
    if originality_state == "not_stated":
        unknowns.append("originality_rule_not_stated")
    if not rules["worked_required"]:
        unknowns.append("worked_example_rule_not_stated")
    if not guidelines_body.strip():
        unknowns.append("guidelines_not_supplied")
    if route_state != "observed_route":
        unknowns.append("submission_route_not_observed")
    if external_route_seen:
        unknowns.append("external_submission_route_requires_manual_inspection")
    if word_min is not None and planned_word_count is None:
        unknowns.append("planned_word_count_missing")
    if conflicts:
        unknowns.append("conflicting_guidelines")

    blocking_unknowns = {
        "format_permission_not_stated", "guidelines_not_supplied",
        "submission_route_not_observed", "external_submission_route_requires_manual_inspection",
        "planned_word_count_missing", "conflicting_guidelines",
    }
    if reasons:
        qualification = "explicit_mismatch"
    elif conflicts or blocking_unknowns.intersection(unknowns) or format_state != "explicitly_accepted":
        qualification = "needs_guideline_or_route_check"
    else:
        qualification = "ready_for_human_pitch_review"
    return EvaluationResult(
        publisher_host=host, qualification=qualification, reasons=reasons,
        topic_state=topic_state, matched_topic_phrase=topic_phrase if fit_excerpt else None,
        fit_excerpt=fit_excerpt, format_state=format_state, accepted_formats=accepted,
        originality_state=originality_state, word_min=word_min, word_max=word_max,
        worked_example_state="required" if rules["worked_required"] else "not_stated",
        route_state=route_state, submission_url=route_candidates[0] if len(route_candidates) == 1 else None,
        unknowns=unknowns, example_evidence=example_evidence, guideline_evidence=guideline_evidence,
    )


def draft_pitch(
    *, observed_title: str, observed_title_is_cited_h1: bool, example_url: str,
    matched_topic_phrase: str, proposed_title: str, proposed_format: str,
    audience: str, contribution: str, method: str, is_unpublished: bool,
    asset_title: str, planned_word_count: int | None,
    guideline_acknowledgements: list[str], has_worked_example: bool = False,
) -> str:
    draft_fields = (
        observed_title, matched_topic_phrase, proposed_title, audience,
        contribution, asset_title,
    )
    if not isinstance(guideline_acknowledgements, list) or any(not isinstance(item, str) for item in guideline_acknowledgements):
        raise InputError("guideline acknowledgements must be a list of strings")
    normalized_fields = [" ".join(value.casefold().split()) for value in draft_fields]
    for acknowledgement in guideline_acknowledgements:
        normalized_acknowledgement = " ".join(acknowledgement.casefold().split())
        if normalized_acknowledgement and any(normalized_acknowledgement in value for value in normalized_fields):
            raise InputError("pitch fields repeat raw guideline language")
    if any(OUTCOME_LANGUAGE_RE.search(value) for value in (
        matched_topic_phrase, proposed_title, audience, contribution, asset_title,
    )):
        raise InputError("pitch fields contain unsupported outcome language")
    if OUTCOME_LANGUAGE_RE.search(observed_title):
        observed_title_is_cited_h1 = False
    if observed_title_is_cited_h1:
        opening = f'I read "{observed_title}" ({example_url}), which discusses {matched_topic_phrase}.'
    else:
        opening = f"I read your article at {example_url}, which discusses {matched_topic_phrase}."
    draft = f'{opening} I propose "{proposed_title}", a {proposed_format.replace("_", " ")} for {audience}. The contribution is {contribution}'
    if not draft.endswith(('.', '?', '!')):
        draft += "."
    if method == "new_followup" and is_unpublished:
        draft += f' This would be a new follow-up, not a republication of "{asset_title}".'
    if has_worked_example and planned_word_count is not None:
        draft += f" I can provide a worked example. The proposed length is {planned_word_count} words."
    elif has_worked_example:
        draft += " I can provide a worked example."
    elif planned_word_count is not None:
        draft += f" The proposed length is {planned_word_count} words."
    draft = redact_text_urls(draft)
    pitch_prose = URL_IN_TEXT_RE.sub("", draft)
    if OUTCOME_LANGUAGE_RE.search(pitch_prose):
        raise InputError("assembled pitch contains unsupported outcome language")
    return draft


def _validate_source(raw: Any) -> dict[str, Any]:
    source = _object(raw, "source", SOURCE_KEYS)
    missing = SOURCE_KEYS - set(source)
    if missing:
        raise InputError(f"source is missing keys: {', '.join(sorted(missing))}")
    source_id = _string(source["id"], "source.id", 1, 64)
    if not ID_RE.fullmatch(source_id):
        raise InputError("source.id is invalid")
    role = source["role"]
    if role not in SOURCE_ROLES or source["kind"] != SOURCE_ROLES[role]:
        raise InputError("source kind/role is unsupported")
    if role == "own_article" and source["kind"] != "page":
        raise InputError("own_article must be a page")
    url = source["url"]
    if url is None:
        if source["kind"] != "operator_note":
            raise InputError("only operator notes may have a null URL")
    else:
        url = canonical_url(url)
    title = redact_text_urls(_string(source["title"], "source.title", 1, 200))[:200]
    text_limit = 50000 if source["kind"] == "page" else 2000
    if not isinstance(source["text"], str) or len(source["text"]) > text_limit:
        raise InputError("source.text has an invalid type or length")
    status = source["status"]
    if status not in {"collected", "empty", "unavailable", "pending"}:
        raise InputError("source.status is invalid")
    if status == "collected" and not source["text"].strip():
        raise InputError("collected source text must not be empty")
    if status != "collected" and source["text"]:
        raise InputError("non-collected source text must be empty")
    observed_at = _timestamp(source["observed_at"], "source.observed_at")
    published_at = _timestamp(source["published_at"], "source.published_at", nullable=True)
    provider_date = source["provider_date"]
    if provider_date is not None:
        provider_date = redact_text_urls(_string(provider_date, "source.provider_date", 1, 100))[:100]
    origin = source["record_id_origin"]
    if origin not in {"provider", "operator", "content_hash", "none"}:
        raise InputError("source.record_id_origin is invalid")
    record_id = source["record_id"]
    if origin == "none" and record_id is not None:
        raise InputError("record_id must be null when origin is none")
    if origin != "none":
        record_id = redact_text_urls(_string(record_id, "source.record_id", 1, 200))[:200]
    if source["provenance"] not in {"synthetic_fixture", "operator_supplied", "bright_data"}:
        raise InputError("source.provenance is invalid")
    canonical, blocks = normalize_text(source["text"])
    return {
        **source, "url": url, "title": title, "observed_at": observed_at,
        "published_at": published_at, "provider_date": provider_date,
        "record_id": record_id, "canonical_text": canonical, "blocks": blocks,
        "content_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def _source_index(source: dict[str, Any]) -> dict[str, Any]:
    return {key: source[key] for key in (
        "id", "kind", "role", "url", "status", "observed_at", "published_at",
        "provider_date", "record_id", "record_id_origin", "provenance", "content_sha256",
    )}


def analyze(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InputError("input must be a JSON object")
    try:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise InputError("input must be JSON-compatible") from exc
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise InputError("input exceeds 2 MiB")
    keys = {"schema_version", "project", "sources", "as_of", "audience", "asset", "proposed_piece", "publishers"}
    _object(payload, "input", keys)
    required = keys - {"as_of"}
    if required - set(payload):
        raise InputError(f"input is missing keys: {', '.join(sorted(required - set(payload)))}")
    if payload["schema_version"] != SCHEMA_VERSION or payload["project"] != PROJECT:
        raise InputError("schema_version or project is invalid")
    audience = _string(payload["audience"], "audience", 1, 160)

    asset = _object(payload["asset"], "asset", {"title", "source_id", "publication_state", "topic_phrases", "format"})
    if set(asset) != {"title", "source_id", "publication_state", "topic_phrases", "format"}:
        raise InputError("asset is missing required fields")
    asset_title = _string(asset["title"], "asset.title", 1, 160)
    if asset["source_id"] is not None and (not isinstance(asset["source_id"], str) or not ID_RE.fullmatch(asset["source_id"])):
        raise InputError("asset.source_id is invalid")
    if asset["publication_state"] not in {"published", "unpublished", "outline"} or asset["format"] not in FORMATS:
        raise InputError("asset publication_state or format is invalid")
    if not isinstance(asset["topic_phrases"], list) or not 1 <= len(asset["topic_phrases"]) <= 8:
        raise InputError("asset.topic_phrases must contain 1-8 phrases")
    topics = [_string(item, "asset.topic_phrase", 1, 80) for item in asset["topic_phrases"]]

    proposed = _object(payload["proposed_piece"], "proposed_piece", {"title", "contribution", "format", "method", "is_unpublished", "planned_word_count", "has_worked_example"})
    if len(proposed) != 7:
        raise InputError("proposed_piece is missing required fields")
    proposed_title = _string(proposed["title"], "proposed_piece.title", 1, 160)
    contribution = _string(proposed["contribution"], "proposed_piece.contribution", 1, 300)
    if proposed["format"] not in FORMATS or proposed["method"] not in {"reuse_asset", "new_followup"}:
        raise InputError("proposed format or method is invalid")
    if type(proposed["is_unpublished"]) is not bool or type(proposed["has_worked_example"]) is not bool:
        raise InputError("proposal boolean fields must be booleans")
    if proposed["planned_word_count"] is not None:
        _integer(proposed["planned_word_count"], "planned_word_count", 100, 10000)

    raw_sources = payload["sources"]
    if not isinstance(raw_sources, list) or len(raw_sources) > 100:
        raise InputError("sources must be an array with at most 100 entries")
    sources = [_validate_source(source) for source in raw_sources]
    ids = [source["id"] for source in sources]
    if len(ids) != len(set(ids)):
        raise InputError("source IDs must be unique")
    by_id = {source["id"]: source for source in sources}
    role_limits = {"own_article": 1, "publisher_example": 5, "submission_guidelines": 5, "discovery": 5, "context_note": 5}
    for role, limit in role_limits.items():
        if sum(source["role"] == role for source in sources) > limit:
            raise InputError(f"too many {role} sources")
    if asset["source_id"] is not None:
        source = by_id.get(asset["source_id"])
        expected_role = "context_note" if asset["publication_state"] == "outline" else "own_article"
        if source is None or source["role"] != expected_role:
            raise InputError("asset.source_id is dangling or has the wrong role")
    if asset["publication_state"] == "published" and asset["source_id"] is None:
        raise InputError("published asset requires own_article evidence")

    raw_publishers = payload["publishers"]
    if not isinstance(raw_publishers, list) or not 1 <= len(raw_publishers) <= 5:
        raise InputError("publishers must contain 1-5 entries")
    publisher_ids: set[str] = set()
    publisher_rows: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    unavailable = any(source["status"] != "collected" for source in sources if source["role"] in {"publisher_example", "submission_guidelines"})
    declared_checks = {
        "method": proposed["method"],
        "is_unpublished": proposed["is_unpublished"],
        "planned_word_count": proposed["planned_word_count"],
        "has_worked_example": proposed["has_worked_example"],
    }
    originality_declaration = {
        "method": proposed["method"],
        "is_unpublished": proposed["is_unpublished"],
        "verification": "operator_declared_unverified",
    }

    for raw_publisher in raw_publishers:
        publisher = _object(raw_publisher, "publisher", {"id", "name", "example_source_ids", "guideline_source_ids"})
        if len(publisher) != 4:
            raise InputError("publisher is missing required fields")
        publisher_id = _string(publisher["id"], "publisher.id", 1, 64)
        if not ID_RE.fullmatch(publisher_id) or publisher_id in publisher_ids:
            raise InputError("publisher IDs must be unique valid IDs")
        publisher_ids.add(publisher_id)
        name = _string(publisher["name"], "publisher.name", 1, 100)
        if not isinstance(publisher["example_source_ids"], list) or len(publisher["example_source_ids"]) != 1:
            raise InputError("publisher requires exactly one example_source_id")
        if not isinstance(publisher["guideline_source_ids"], list) or len(publisher["guideline_source_ids"]) > 1:
            raise InputError("publisher permits at most one guideline_source_id")
        refs = publisher["example_source_ids"] + publisher["guideline_source_ids"]
        if len(refs) != len(set(refs)):
            raise InputError("publisher source references must be unique")
        example = by_id.get(publisher["example_source_ids"][0])
        if example is None or example["role"] != "publisher_example":
            raise InputError("publisher example reference is dangling or has the wrong role")
        guideline = None
        if publisher["guideline_source_ids"]:
            guideline = by_id.get(publisher["guideline_source_ids"][0])
            if guideline is None or guideline["role"] != "submission_guidelines":
                raise InputError("publisher guideline reference is dangling or has the wrong role")
        if example["url"] is None:
            raise InputError("publisher example URL is required")
        host = normalize_publisher_host(example["url"])
        validate_publisher_sources(publisher_host=host, example_url=example["url"], guideline_url=guideline["url"] if guideline else None)

        if example["status"] != "collected":
            example_state = {
                "empty": "source_empty",
                "unavailable": "source_unavailable",
                "pending": "source_pending",
            }[example["status"]]
            row = {
                "publisher_id": publisher_id, "publisher": name, "publisher_host": host,
                "qualification": "needs_guideline_or_route_check", "exclusion_reasons": [],
                "topic_state": example_state, "matched_topic_phrase": None,
                "format_state": "not_evaluated", "worked_example_state": "not_evaluated",
                "proposed_format": proposed["format"],
                "declared_checks": dict(declared_checks),
                "originality_declaration": dict(originality_declaration),
                "fit_excerpt": None, "example_url": example["url"], "accepted_formats": [],
                "originality_state": "unknown", "word_min": None, "word_max": None,
                "route_state": "not_observed", "submission_url": None,
                "unknowns": [f"selected_example_{example['status']}"], "pitch_draft": None,
                "evidence": [], "research_task": "Obtain a readable selected example and verify topical fit.",
            }
            publisher_rows.append(row)
            continue

        topic = next((phrase for phrase in topics if any(not block["heading"] and _phrase_hit(block["text"], phrase) for block in example["blocks"])), topics[0])
        guidelines_body = guideline["canonical_text"] if guideline and guideline["status"] == "collected" else ""
        result = evaluate_publisher(
            publisher_host=host, example_url=example["url"], example_body=example["canonical_text"],
            guidelines_body=guidelines_body, topic_phrase=topic, proposed_format=proposed["format"],
            planned_word_count=proposed["planned_word_count"], has_worked_example=proposed["has_worked_example"],
            method=proposed["method"], is_unpublished=proposed["is_unpublished"], asset_publication_state=asset["publication_state"],
        )
        data = asdict(result)
        evidence: list[dict[str, str]] = []
        for citation in data.pop("example_evidence"):
            evidence.append({**citation, "source_id": example["id"]})
        if guideline:
            for citation in data.pop("guideline_evidence"):
                evidence.append({**citation, "source_id": guideline["id"]})
        observed_h1 = next((block for block in example["blocks"] if block["heading_level"] == 1 and len(block["text"]) <= 200), None)
        if observed_h1:
            evidence.insert(0, _citation(example["id"], observed_h1["id"], observed_h1["text"]))
        acknowledgements = [
            citation["quote"] for citation in evidence
            if guideline and citation["source_id"] == guideline["id"] and not citation["quote"].startswith("[")
        ]
        rules_known = bool(acknowledgements)
        pitch = None
        research_task = None
        if result.fit_excerpt and rules_known and result.qualification == "ready_for_human_pitch_review":
            pitch = draft_pitch(
                observed_title=observed_h1["text"] if observed_h1 else example["title"],
                observed_title_is_cited_h1=observed_h1 is not None,
                example_url=example["url"], matched_topic_phrase=result.matched_topic_phrase or topic,
                proposed_title=proposed_title, proposed_format=proposed["format"], audience=audience,
                contribution=contribution, method=proposed["method"], is_unpublished=proposed["is_unpublished"],
                asset_title=asset_title, planned_word_count=proposed["planned_word_count"],
                guideline_acknowledgements=acknowledgements,
                has_worked_example=proposed["has_worked_example"],
            )
            cited_constraints: list[str] = []
            if proposed["format"] in result.accepted_formats:
                cited_constraints.append(f"I have framed the proposed piece as a {proposed['format'].replace('_', ' ')}.")
            if result.originality_state == "original_unpublished_required":
                cited_constraints.append("The proposed piece is planned as a new, unpublished follow-up.")
            if cited_constraints:
                pitch += " " + " ".join(cited_constraints)
        else:
            research_task = "Verify the publisher's current guidelines and an exact-host submission route before pitching."
        unknowns = list(result.unknowns)
        if guideline and guideline["status"] != "collected":
            unknowns = [item for item in unknowns if item != "guidelines_not_supplied"]
            unknowns.append(f"guidelines_{guideline['status']}")
        publisher_rows.append({
            "publisher_id": publisher_id, "publisher": name, "publisher_host": host,
            "qualification": result.qualification, "exclusion_reasons": result.reasons,
            "topic_state": result.topic_state,
            "matched_topic_phrase": result.matched_topic_phrase,
            "format_state": result.format_state,
            "worked_example_state": result.worked_example_state,
            "proposed_format": proposed["format"],
            "declared_checks": dict(declared_checks),
            "originality_declaration": dict(originality_declaration),
            "fit_excerpt": result.fit_excerpt, "example_url": example["url"],
            "accepted_formats": result.accepted_formats, "originality_state": result.originality_state,
            "word_min": result.word_min, "word_max": result.word_max,
            "route_state": result.route_state, "submission_url": result.submission_url,
            "unknowns": unknowns,
            "pitch_draft": pitch, "evidence": evidence, "research_task": research_task,
        })
        if guideline and "external_submission_route_requires_manual_inspection" in result.unknowns:
            warnings.append({"code": "external_submission_route", "source_ids": [guideline["id"]], "note": "An observed submission link uses a different host and requires manual inspection."})

    excluded = [row for row in publisher_rows if row["qualification"] == "explicit_mismatch"]
    cards = [row for row in publisher_rows if row["qualification"] != "explicit_mismatch"][:5]
    decision = "pitch_shortlist" if cards else "no_matching_publishers"
    as_of = payload.get("as_of")
    if as_of is not None:
        as_of = _timestamp(as_of, "as_of")
    elif sources:
        as_of = max(source["observed_at"] for source in sources)
    for source in sources:
        if as_of:
            age = datetime.fromisoformat(as_of[:-1] + "+00:00") - datetime.fromisoformat(source["observed_at"][:-1] + "+00:00")
            if age.days > 30:
                warnings.append({"code": "stale_source", "source_ids": [source["id"]], "note": "Source was observed more than 30 days before as_of."})
    if any(source["provenance"] == "synthetic_fixture" for source in sources):
        warnings.append({"code": "synthetic_data", "source_ids": [source["id"] for source in sources if source["provenance"] == "synthetic_fixture"], "note": "Invented fixture data is for demonstration only."})
    unresolved = any(row["qualification"] == "needs_guideline_or_route_check" for row in publisher_rows)
    status = "needs_review" if unavailable or unresolved else ("no_data" if not publisher_rows else "ok")
    return {
        "schema_version": SCHEMA_VERSION, "project": PROJECT,
        "transport_contract_version": TRANSPORT_CONTRACT_VERSION,
        "analysis_method": "deterministic_rules_v1", "draft_method": "approved_text_templates_v1",
        "status": status, "decision": decision,
        "scope": {
            "audience": audience, "asset_title": asset_title, "topic_phrases": topics,
            "proposed_title": proposed_title, "source_ids": ids,
            "source_roles": [source["role"] for source in sources], "as_of": as_of,
        },
        "summary": {"analyzed_publishers": len(publisher_rows), "excluded_publishers": len(excluded), "output_cards": len(cards)},
        "warnings": warnings, "source_index": [_source_index(source) for source in sources],
        "publishers": publisher_rows, "cards": cards, "excluded": excluded,
    }
