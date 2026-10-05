"""Optional Bright Data ingestion with explicit local cost and permission gates."""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime
import hashlib
import ipaddress
import json
import math
import re
import socket
import ssl
import signal
import time
import threading
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

from .core import ID_RE, InputError, PROJECT, SCHEMA_VERSION, _timestamp, canonical_url, normalize_text, redact_text_urls, redact_url_query

API_HOST = "api.brightdata.com"
REQUEST_URL = "https://api.brightdata.com/request"
TRANSPORT_CONTRACT_VERSION = "1.0"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
WEB_ROLES = {"own_article", "publisher_example", "submission_guidelines"}
FIXTURE_HOSTS = {"example.com", "example.org", "example.net"}


class CollectionError(RuntimeError):
    def __init__(self, code: str, message: str = "Collection failed safely.") -> None:
        super().__init__(message)
        self.code = code


class TransportError(CollectionError):
    def __init__(self, code: str = "transport_error") -> None:
        super().__init__(code, "The provider transport failed.")


class OperationDeadlineExceeded(CollectionError):
    def __init__(self) -> None:
        super().__init__("operation_deadline_exceeded", "The collection operation exceeded its deadline.")


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes
    timeout_seconds: int


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes


Transport = Callable[[HttpRequest], HttpResponse]


def _require_hard_deadline_support() -> None:
    if not hasattr(signal, "setitimer") or not hasattr(signal, "ITIMER_REAL") or threading.current_thread() is not threading.main_thread():
        raise InputError("live collection requires a main-thread platform with interruptible monotonic deadlines")
    remaining, interval = signal.getitimer(signal.ITIMER_REAL)
    if remaining or interval:
        raise InputError("live collection cannot run while another real-time process timer is active")


@contextmanager
def _wall_clock_deadline(deadline_at: float):
    remaining = deadline_at - time.monotonic()
    if remaining <= 0:
        raise OperationDeadlineExceeded()
    previous_handler = signal.getsignal(signal.SIGALRM)

    def expire(signum: int, frame: Any) -> None:
        if time.monotonic() >= deadline_at:
            raise OperationDeadlineExceeded()
        signal.setitimer(signal.ITIMER_REAL, max(0.001, deadline_at - time.monotonic()))

    signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, remaining)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def urllib_transport(request: HttpRequest) -> HttpResponse:
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), _NoRedirectHandler())
    raw = Request(request.url, data=request.body or None, headers=request.headers, method=request.method)
    try:
        with opener.open(raw, timeout=request.timeout_seconds) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise TransportError("response_too_large")
            return HttpResponse(response.status, dict(response.headers.items()), body)
    except HTTPError as exc:
        body = exc.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise TransportError("response_too_large") from None
        return HttpResponse(exc.code, dict(exc.headers.items()), body)
    except OperationDeadlineExceeded:
        raise
    except (URLError, TimeoutError, socket.timeout, OSError) as exc:
        raise TransportError() from exc


def _exact_object(value: Any, name: str, required: set[str], optional: set[str] = frozenset()) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - required - optional or required - set(value):
        raise InputError(f"{name} has invalid fields")
    return value


def _live_url(url: Any, *, reject_fixture: bool) -> str:
    canonical = canonical_url(url)
    parsed = urlsplit(canonical)
    if parsed.port not in (None, 443):
        raise InputError("target URL ports other than 443 are not allowed")
    host = parsed.hostname or ""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise InputError("IP-literal target URLs are not allowed")
    labels = host.split(".")
    if len(labels) < 2 or labels[-1].isdigit() or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label) for label in labels):
        raise InputError("target URL host is not a valid public DNS name")
    blocked = ("localhost", ".localhost", ".local", ".internal", ".invalid", ".example", ".test")
    if host == "localhost" or any(host.endswith(suffix) for suffix in blocked[1:]):
        raise InputError("reserved target hosts are not allowed")
    if reject_fixture and any(host == root or host.endswith("." + root) for root in FIXTURE_HOSTS):
        raise InputError("fixture hosts are not allowed in live mode")
    if parsed.query:
        raise InputError("live web target query strings are not supported")
    return canonical


def manifest_sha256(manifest: dict[str, Any]) -> str:
    raw = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _validate_manifest(manifest: Any, *, reject_fixture: bool = False) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = _exact_object(manifest, "manifest", {"schema_version", "project", "jobs"})
    if manifest["schema_version"] != SCHEMA_VERSION or manifest["project"] != PROJECT:
        raise InputError("manifest schema_version or project is invalid")
    if not isinstance(manifest["jobs"], list) or not 1 <= len(manifest["jobs"]) <= 12:
        raise InputError("manifest jobs must contain 1-12 entries")
    ids: set[str] = set()
    source_ids: set[str] = set()
    serp_count = 0
    role_counts = {"own_article": 0, "publisher_example": 0, "submission_guidelines": 0}
    normalized: list[dict[str, Any]] = []
    for raw in manifest["jobs"]:
        if not isinstance(raw, dict) or raw.get("kind") not in {"web_page", "serp"}:
            raise InputError("only web_page and serp jobs are supported")
        kind = raw["kind"]
        if kind == "web_page":
            job = _exact_object(raw, "web_page job", {"id", "kind", "role", "source_id", "url"}, {"country"})
            if job["role"] not in WEB_ROLES:
                raise InputError("unsupported web_page role")
            source_id = job["source_id"]
            if not isinstance(source_id, str) or not ID_RE.fullmatch(source_id) or source_id in source_ids:
                raise InputError("web source_id must be a unique ID")
            source_ids.add(source_id)
            role_counts[job["role"]] += 1
            country = job.get("country")
            if country is not None and (not isinstance(country, str) or not re.fullmatch(r"[a-z]{2}", country)):
                raise InputError("country must be two lowercase ASCII letters")
            normalized.append({**job, "url": _live_url(job["url"], reject_fixture=reject_fixture), "country": country})
        else:
            job = _exact_object(raw, "serp job", {"id", "kind", "role", "source_prefix", "query", "country", "language"})
            if job["role"] != "discovery" or job["language"] != "en":
                raise InputError("serp role/language is unsupported")
            if not isinstance(job["source_prefix"], str) or len(job["source_prefix"]) > 47 or not ID_RE.fullmatch(job["source_prefix"]):
                raise InputError("serp source_prefix is invalid")
            if not isinstance(job["query"], str) or not 1 <= len(job["query"]) <= 200 or not job["query"].strip():
                raise InputError("serp query is invalid")
            if not isinstance(job["country"], str) or not re.fullmatch(r"[a-z]{2}", job["country"]):
                raise InputError("serp country is invalid")
            serp_count += 1
            normalized.append(dict(job))
        job_id = raw.get("id")
        if not isinstance(job_id, str) or not ID_RE.fullmatch(job_id) or job_id in ids:
            raise InputError("job IDs must be unique valid IDs")
        ids.add(job_id)
    if serp_count > 1 or role_counts["own_article"] > 1 or role_counts["publisher_example"] > 5 or role_counts["submission_guidelines"] > 5:
        raise InputError("manifest exceeds Article Pitch Shortlist scope")
    return manifest, normalized


def _serp_url(job: dict[str, Any]) -> str:
    query = quote(job["query"], safe="")
    return f"https://www.google.com/search?q={query}&gl={job['country']}&hl=en&pws=0&brd_json=1"


def _redact_url_query(url: str) -> str:
    return redact_url_query(url)


def _redacted_job(job: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(job)
    if "query" in redacted:
        redacted["query"] = "[redacted]"
    if isinstance(redacted.get("url"), str):
        redacted["url"] = _redact_url_query(redacted["url"])
    return redacted


def _planned_retention(jobs: list[dict[str, Any]]) -> int:
    return sum(5 if job["kind"] == "serp" else 1 for job in jobs)


def plan(manifest: dict[str, Any]) -> dict[str, Any]:
    original, jobs = _validate_manifest(manifest)
    requests = []
    for job in jobs:
        target = job["url"] if job["kind"] == "web_page" else _serp_url(job)
        requests.append({"job_id": job["id"], "kind": job["kind"], "method": "POST", "provider_url": REQUEST_URL, "approved_url": _redact_url_query(target)})
    return {
        "schema_version": SCHEMA_VERSION, "project": PROJECT,
        "manifest_sha256": manifest_sha256(original), "requests_made": 0,
        "planned_requests": len(requests), "max_retained_records": _planned_retention(jobs),
        "requests": requests,
    }


def _source(
    *, source_id: str, kind: str, role: str, url: str, title: str, text: str,
    observed_at: str, provenance: str,
) -> dict[str, Any]:
    canonical, _ = normalize_text(text)
    return {
        "id": source_id, "kind": kind, "role": role, "url": url,
        "title": redact_text_urls(title)[:200] or "Selected public page", "text": canonical,
        "status": "collected" if canonical else "empty", "observed_at": observed_at,
        "published_at": None, "provider_date": None, "record_id": None,
        "record_id_origin": "none", "provenance": provenance,
    }


def _web_source(job: dict[str, Any], body: bytes, observed_at: str, provenance: str) -> dict[str, Any]:
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CollectionError("invalid_response") from exc
    stripped = text.lstrip().lower()
    if stripped.startswith(("<!doctype html", "<html", "<body")):
        raise CollectionError("unsupported_content_format")
    if text.lstrip().startswith("{"):
        try:
            candidate = json.loads(text)
        except json.JSONDecodeError:
            candidate = None
        envelope_keys = {"status_code", "headers", "body", "error", "error_code", "errors", "response_id"}
        if isinstance(candidate, dict) and set(candidate) & envelope_keys:
            raise CollectionError("response_contract_mismatch")
    if len(text) > 50000:
        raise CollectionError("text_too_long")
    title = "Selected public page"
    for line in text.splitlines():
        match = re.fullmatch(r"#\s+(.+?)\s*", line.strip())
        if match:
            title = match.group(1)[:200]
            break
    return _source(source_id=job["source_id"], kind="page", role=job["role"], url=job["url"], title=title, text=text, observed_at=observed_at, provenance=provenance)


def _serp_sources(job: dict[str, Any], data: Any, observed_at: str, provenance: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("organic"), list):
        raise CollectionError("invalid_response")
    sources: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    ranks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, item in enumerate(data["organic"]):
        if len(sources) >= 5:
            has_unretained_distinct_result = False
            for extra in data["organic"][position:]:
                if not isinstance(extra, dict) or not isinstance(extra.get("link"), str):
                    continue
                try:
                    extra_identity = canonical_url(extra["link"], redact_query=False)
                except InputError:
                    continue
                if extra_identity not in seen:
                    has_unretained_distinct_result = True
                    break
            if has_unretained_distinct_result:
                warnings.append({
                    "code": "provider_limit_exceeded",
                    "source_ids": [source["id"] for source in sources],
                    "note": "The provider returned more distinct search results than the local retention limit.",
                })
            break
        if not isinstance(item, dict) or not isinstance(item.get("link"), str):
            warnings.append({"code": "invalid_record", "source_ids": [], "note": "A search result without a valid HTTPS link was excluded."})
            continue
        try:
            identity_url = canonical_url(item["link"], redact_query=False)
        except InputError:
            warnings.append({"code": "invalid_record", "source_ids": [], "note": "A search result without a valid HTTPS link was excluded."})
            continue
        if identity_url in seen:
            continue
        seen.add(identity_url)
        url = _redact_url_query(identity_url)
        identity_digest = hashlib.sha256(f"{url}\0{position}".encode()).hexdigest()[:16]
        source_id = f"{job['source_prefix']}-{identity_digest}"
        description = item.get("description", "")
        if not isinstance(description, str):
            description = ""
        if len(description) > 2000:
            description = description[:2000]
            warnings.append({"code": "text_truncated", "source_ids": [source_id], "note": "Search result description was truncated to 2,000 characters."})
        title = item.get("title") if isinstance(item.get("title"), str) else "Search result"
        try:
            normalized_description, _ = normalize_text(description)
            normalized_title, _ = normalize_text(title)
        except InputError:
            warnings.append({"code": "invalid_record", "source_ids": [], "note": "A search result with invalid text was excluded."})
            continue
        sources.append(_source(source_id=source_id, kind="search_result", role="discovery", url=url, title=normalized_title[:200], text=normalized_description, observed_at=observed_at, provenance=provenance))
        rank = item.get("rank") if isinstance(item.get("rank"), int) and not isinstance(item.get("rank"), bool) and item["rank"] > 0 else None
        global_rank = item.get("global_rank") if isinstance(item.get("global_rank"), int) and not isinstance(item.get("global_rank"), bool) and item["global_rank"] > 0 else None
        if rank is None:
            warnings.append({"code": "rank_missing", "source_ids": [source_id], "note": "Organic rank was not supplied."})
        ranks.append({"source_id": source_id, "organic_rank": rank, "global_rank": global_rank})
    general = data.get("general") if isinstance(data.get("general"), dict) else {}
    effective = general.get("query") if isinstance(general.get("query"), str) else None
    detected = general.get("detected_query") if isinstance(general.get("detected_query"), str) else None
    metadata = {
        "submitted_query": "[redacted]", "effective_query": "[redacted]" if effective else None,
        "detected_query": "[redacted]" if detected else None,
        "spelling_present": any(key in general for key in ("spelling", "corrected_query", "did_you_mean")),
        "result_ranks": ranks,
    }
    if effective and effective != job["query"]:
        warnings.append({"code": "query_changed", "source_ids": [], "note": "The provider reported a different effective query."})
    if detected and effective and detected != effective and not metadata["spelling_present"]:
        warnings.append({"code": "query_mismatch", "source_ids": [], "note": "Detected and effective query differ without a correction marker."})
    return sources, warnings, metadata


def normalize_export(kind: str, records: Any, *, role: str, source_url: str, observed_at: str, source_prefix: str) -> dict[str, Any]:
    _timestamp(observed_at, "observed_at")
    if not isinstance(source_prefix, str) or len(source_prefix) > 47 or not ID_RE.fullmatch(source_prefix):
        raise InputError("source_prefix is invalid")
    warnings: list[dict[str, Any]] = []
    canonical_url(source_url)
    if kind == "web_page":
        if role not in WEB_ROLES or not isinstance(records, str):
            raise InputError("web_page import requires a supported role and raw Markdown string")
        url = canonical_url(source_url)
        source_id = f"{source_prefix}-{hashlib.sha256(url.encode()).hexdigest()[:16]}"
        try:
            source = _web_source({"source_id": source_id, "role": role, "url": url}, records.encode("utf-8"), observed_at, "operator_supplied")
        except CollectionError as exc:
            raise InputError(exc.code) from exc
        sources = [source]
    elif kind == "serp":
        if role != "discovery" or not isinstance(records, dict):
            raise InputError("serp import requires discovery role and a JSON object")
        general = records.get("general") if isinstance(records.get("general"), dict) else {}
        supplied_query = general.get("query") if isinstance(general.get("query"), str) else "operator-supplied export"
        job = {"source_prefix": source_prefix, "query": supplied_query}
        try:
            sources, warnings, _ = _serp_sources(job, records, observed_at, "operator_supplied")
        except CollectionError as exc:
            raise InputError(exc.code) from exc
    else:
        raise InputError("unsupported import kind")
    returned = len(records["organic"]) if kind == "serp" else len(sources)
    if returned > len(sources):
        warnings.append({
            "code": "provider_limit_exceeded", "source_ids": [],
            "note": "Offline import exceeded the local retained-record limit; excess records were not retained.",
        })
    receipt = {
        "schema_version": SCHEMA_VERSION, "project": PROJECT, "manifest_sha256": None,
        "status": "partial" if returned > len(sources) else "complete", "requests_made": 0, "requests_attempted": 0,
        "responses_received": 0, "completion_unknown": False,
        "returned_records": returned, "retained_records": len(sources), "excluded_records": returned - len(sources),
        "jobs": [], "warnings": warnings, "provider_cost_usd": None,
    }
    return {"schema_version": SCHEMA_VERSION, "project": PROJECT, "transport_contract_version": TRANSPORT_CONTRACT_VERSION, "sources": sources, "receipt": receipt}


def _approval(approval: Any, manifest: dict[str, Any], planned: dict[str, Any], now: str) -> None:
    keys = {"schema_version", "project", "manifest_sha256", "expires_at", "max_requests", "max_retained_records", "approved_urls", "account_budget_confirmed", "target_permissions_confirmed", "remote_resolution_risk_accepted"}
    approval = _exact_object(approval, "approval", keys)
    if approval["schema_version"] != SCHEMA_VERSION or approval["project"] != PROJECT or approval["manifest_sha256"] != manifest_sha256(manifest):
        raise InputError("approval does not match manifest")
    _timestamp(approval["expires_at"], "approval.expires_at")
    _timestamp(now, "now")
    try:
        expiry = datetime.fromisoformat(approval["expires_at"].replace("Z", "+00:00"))
        current = datetime.fromisoformat(now.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise InputError("approval timestamps are invalid") from exc
    if expiry <= current:
        raise InputError("approval has expired")
    if isinstance(approval["max_requests"], bool) or not isinstance(approval["max_requests"], int) or approval["max_requests"] < planned["planned_requests"]:
        raise InputError("approval request allowance is insufficient")
    if isinstance(approval["max_retained_records"], bool) or not isinstance(approval["max_retained_records"], int) or not 1 <= approval["max_retained_records"] <= 50:
        raise InputError("approval retained-record limit is invalid")
    if approval["max_retained_records"] < planned["max_retained_records"]:
        raise InputError("approval retained-record allowance is insufficient")
    if any(approval[key] is not True for key in ("account_budget_confirmed", "target_permissions_confirmed", "remote_resolution_risk_accepted")):
        raise InputError("all approval attestations are required")
    if not isinstance(approval["approved_urls"], list) or any(item["approved_url"] not in approval["approved_urls"] for item in planned["requests"]):
        raise InputError("approval does not include every exact target/search URL")


def _provider_error(response: HttpResponse) -> str | None:
    headers = {key.casefold(): value for key, value in response.headers.items()}
    for key in ("x-brd-error-code", "x-brd-err-code", "x-luminati-error-code", "x-brd-error", "x-brd-err-msg", "x-luminati-error"):
        if headers.get(key):
            return "provider_target_error"
    for key in ("x-brd-status-code", "x-luminati-status-code"):
        if key in headers:
            try:
                if not 200 <= int(headers[key]) < 300:
                    return "provider_target_error"
            except ValueError:
                return "invalid_response"
    return None if 200 <= response.status < 300 else "provider_http_error"


def collect(
    manifest: dict[str, Any], *, approval: dict[str, Any], api_key: str,
    zones: dict[str, str], transport: Transport = urllib_transport, now: str,
    deadline_seconds: int = 75, clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    original, jobs = _validate_manifest(manifest)
    if any(job["kind"] == "web_page" for job in jobs):
        raise InputError("live web_page collection is fail-closed because effective target redirects cannot be verified")
    planned = plan(original)
    _approval(approval, original, planned, now)
    if isinstance(deadline_seconds, bool) or not isinstance(deadline_seconds, int) or not 1 <= deadline_seconds <= 75:
        raise InputError("deadline_seconds must be an integer from 1 to 75")
    if not isinstance(api_key, str) or not api_key:
        raise InputError("BRIGHT_DATA_API_KEY is required")
    if not isinstance(zones, dict) or any(kind not in zones or not isinstance(zones[kind], str) or not zones[kind] for kind in {"web_unlocker", "serp"} if any(job["kind"] == ("web_page" if kind == "web_unlocker" else "serp") for job in jobs)):
        raise InputError("required Bright Data zone is missing")
    _require_hard_deadline_support()
    sources: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    requests_attempted = 0
    responses_received = 0
    failed = False
    completion_unknown = False
    started = clock()
    wall_deadline = time.monotonic() + deadline_seconds
    retention_limit = approval["max_retained_records"]
    for job in jobs:
        if failed:
            receipts.append(_job_receipt(job, "not_attempted", error_code=None))
            continue
        remaining = min(deadline_seconds - (clock() - started), wall_deadline - time.monotonic())
        if remaining <= 0:
            failed = True
            receipts.append(_job_receipt(job, "failed", error_code="operation_deadline_exceeded"))
            continue
        body_data = {"zone": zones["serp"], "url": _serp_url(job), "format": "json"}
        request = HttpRequest("POST", REQUEST_URL, {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json.dumps(body_data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), min(75, max(1, math.ceil(remaining))))
        attempts_before_dispatch = requests_attempted
        try:
            with _wall_clock_deadline(wall_deadline):
                requests_attempted += 1
                response = transport(request)
        except OperationDeadlineExceeded as exc:
            failed = True
            was_dispatched = requests_attempted > attempts_before_dispatch
            completion_unknown = completion_unknown or was_dispatched
            receipts.append(_job_receipt(job, "completion_unknown" if was_dispatched else "failed", error_code=exc.code))
            continue
        except Exception:
            failed = True
            completion_unknown = True
            receipts.append(_job_receipt(job, "completion_unknown", error_code="transport_error"))
            continue
        responses_received += 1
        try:
            with _wall_clock_deadline(wall_deadline):
                if (
                    not isinstance(response, HttpResponse)
                    or isinstance(response.status, bool) or not isinstance(response.status, int)
                    or not 100 <= response.status <= 599
                    or not isinstance(response.body, bytes)
                    or not isinstance(response.headers, dict)
                    or any(not isinstance(key, str) or not isinstance(value, str) for key, value in response.headers.items())
                ):
                    raise CollectionError("invalid_response")
                if clock() - started > deadline_seconds or time.monotonic() >= wall_deadline:
                    raise OperationDeadlineExceeded()
                if len(response.body) > MAX_RESPONSE_BYTES:
                    raise CollectionError("response_too_large")
                error = _provider_error(response)
                if error:
                    raise CollectionError(error)
                try:
                    data = json.loads(response.body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise CollectionError("invalid_response") from exc
                found, found_warnings, metadata = _serp_sources(job, data, now, "bright_data")
                if len(sources) + len(found) > retention_limit:
                    raise CollectionError("retention_limit_exceeded")
                if time.monotonic() >= wall_deadline:
                    raise OperationDeadlineExceeded()
                sources.extend(found)
                warnings.extend(found_warnings)
                receipts.append(_job_receipt(job, "complete" if found else "empty", returned=len(data["organic"]), retained=len(found), excluded=max(0, len(data["organic"]) - len(found)), query_metadata=metadata))
        except (CollectionError, TimeoutError, socket.timeout, OSError) as exc:
            failed = True
            code = exc.code if isinstance(exc, CollectionError) else "transport_error"
            unknown = code == "transport_error" or (code == "operation_deadline_exceeded" and responses_received == 0)
            completion_unknown = completion_unknown or unknown
            receipts.append(_job_receipt(job, "completion_unknown" if unknown else "failed", error_code=code))
    returned = sum(item["returned_records"] for item in receipts)
    retained = sum(item["retained_records"] for item in receipts)
    excluded = sum(item["excluded_records"] for item in receipts)
    exceeded_local_limit = any(warning["code"] == "provider_limit_exceeded" for warning in warnings)
    status = "partial" if exceeded_local_limit else (
        "complete" if not failed else "partial" if sources else "completion_unknown" if completion_unknown else "failed"
    )
    receipt = {
        "schema_version": SCHEMA_VERSION, "project": PROJECT, "manifest_sha256": manifest_sha256(original),
        "status": status, "requests_made": requests_attempted,
        "requests_attempted": requests_attempted, "responses_received": responses_received,
        "completion_unknown": completion_unknown, "returned_records": returned,
        "retained_records": retained, "excluded_records": excluded, "jobs": receipts,
        "warnings": warnings, "provider_cost_usd": None,
    }
    return {"schema_version": SCHEMA_VERSION, "project": PROJECT, "transport_contract_version": TRANSPORT_CONTRACT_VERSION, "sources": sources, "receipt": receipt}


def _job_receipt(job: dict[str, Any], state: str, *, returned: int = 0, retained: int = 0, excluded: int = 0, error_code: str | None = None, query_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": job["id"], "kind": job["kind"], "state": state, "original_job": _redacted_job(job),
        "requested_records": None, "returned_records": returned, "retained_records": retained,
        "excluded_records": excluded, "snapshot_id": None, "error_code": error_code,
        "query_metadata": query_metadata,
    }


def resume(receipt: dict[str, Any], *, approval: dict[str, Any], api_key: str, transport: Transport = urllib_transport, now: str) -> dict[str, Any]:
    raise InputError("resume is unsupported because this project has no asynchronous scraper job kinds")
