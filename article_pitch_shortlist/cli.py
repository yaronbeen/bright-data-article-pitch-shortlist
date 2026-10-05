"""Command-line interface for offline analysis and explicit ingestion."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import tempfile
from typing import Any

from . import __version__
from .brightdata import CollectionError, collect, normalize_export, plan, resume
from .core import InputError, PROJECT, analyze
from .export import render_csv, render_json, render_markdown

MAX_FILE_BYTES = 2 * 1024 * 1024


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="article-pitch-shortlist", description="Build a deterministic shortlist of publisher-fit checks and human-reviewed pitch drafts.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    analysis = commands.add_parser("analyze", help="analyze an offline JSON input")
    analysis.add_argument("input")
    analysis.add_argument("--out-dir", required=True)
    analysis.add_argument("--sources")
    analysis.add_argument("--dry-run", action="store_true")
    analysis.add_argument("--overwrite", action="store_true")

    collection = commands.add_parser("collect", help="validate or explicitly execute an approved collection manifest")
    collection.add_argument("manifest")
    collection.add_argument("--out", required=True)
    collection.add_argument("--live", action="store_true")
    collection.add_argument("--accept-charges", action="store_true")
    collection.add_argument("--approval")
    collection.add_argument("--dry-run", action="store_true")
    collection.add_argument("--overwrite", action="store_true")

    importer = commands.add_parser("import-provider", help="normalize an already authorized provider export offline")
    importer.add_argument("file")
    importer.add_argument("--kind", choices=["web_page", "serp"], required=True)
    importer.add_argument("--role", required=True)
    importer.add_argument("--source-url", required=True)
    importer.add_argument("--observed-at", required=True)
    importer.add_argument("--source-prefix", default="import")
    importer.add_argument("--out", required=True)
    importer.add_argument("--overwrite", action="store_true")

    resume_parser = commands.add_parser("resume", help="reject unsupported asynchronous resume operations")
    resume_parser.add_argument("receipt")
    resume_parser.add_argument("--out", required=True)
    resume_parser.add_argument("--live", action="store_true")
    resume_parser.add_argument("--accept-charges", action="store_true")
    resume_parser.add_argument("--approval", required=True)
    resume_parser.add_argument("--overwrite", action="store_true")
    return parser


def _read_bytes(path: str) -> bytes:
    file_path = Path(path)
    try:
        if file_path.stat().st_size > MAX_FILE_BYTES:
            raise InputError("input file exceeds 2 MiB")
        return file_path.read_bytes()
    except InputError:
        raise
    except OSError as exc:
        raise InputError("input file could not be read") from exc


def _read_json(path: str) -> Any:
    try:
        return json.loads(_read_bytes(path).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError("input file is not valid UTF-8 JSON") from exc


def _write_atomic(path: Path, content: str, overwrite: bool) -> None:
    if path.is_symlink():
        raise InputError("output path must not be a symlink")
    if path.exists() and not overwrite:
        raise InputError(f"output already exists: {path.name}")
    temporary: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        if overwrite:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
            temporary.unlink()
    except OSError as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise InputError("output file could not be written") from exc


def _write_json(path: Path, value: Any, overwrite: bool) -> None:
    _write_atomic(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", overwrite)


def _write_report_set(out_dir: Path, contents: dict[str, str], overwrite: bool) -> None:
    if not contents or any(not name or Path(name).name != name or name in {".", ".."} for name in contents):
        raise InputError("report transaction contains an invalid filename")
    out_dir = out_dir.absolute()
    if not getattr(os, "O_DIRECTORY", 0) or not getattr(os, "O_NOFOLLOW", 0):
        raise InputError("report transactions require directory no-follow support")
    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    parent_fd = dir_fd = None
    try:
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        parent_fd = os.open(out_dir.parent, dir_flags)
        try:
            expected_dir = os.stat(out_dir.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            os.mkdir(out_dir.name, dir_fd=parent_fd)
            expected_dir = os.stat(out_dir.name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISDIR(expected_dir.st_mode):
            raise OSError("output path is not a real directory")
        dir_fd = os.open(out_dir.name, dir_flags, dir_fd=parent_fd)
        pinned = os.fstat(dir_fd)
        directory_identity = (pinned.st_dev, pinned.st_ino)
        if (expected_dir.st_dev, expected_dir.st_ino) != directory_identity:
            raise OSError("output directory changed while opening")
    except OSError as exc:
        if dir_fd is not None:
            os.close(dir_fd)
        if parent_fd is not None:
            os.close(parent_fd)
        raise InputError("report transaction could not pin its output directory") from exc

    def directory_is_current() -> bool:
        try:
            current = os.stat(out_dir.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return False
        return stat.S_ISDIR(current.st_mode) and (current.st_dev, current.st_ino) == directory_identity

    def stat_identity(name: str) -> tuple[int, int] | None:
        try:
            current = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
        return current.st_dev, current.st_ino

    def unlink_if_identity(name: str, identity: tuple[int, int]) -> bool:
        if stat_identity(name) != identity:
            return False
        for _ in range(100):
            quarantine = f".{name}.rollback.{secrets.token_hex(12)}"
            if stat_identity(quarantine) is None:
                break
        else:
            return False
        os.rename(name, quarantine, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        moved_identity = stat_identity(quarantine)
        if moved_identity == identity:
            os.unlink(quarantine, dir_fd=dir_fd)
            return stat_identity(name) is None
        if moved_identity is None:
            return False
        try:
            os.link(quarantine, name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd, follow_symlinks=False)
        except FileExistsError:
            pass
        return False

    def stage(name: str, content: str) -> tuple[str, tuple[int, int]]:
        for _ in range(100):
            temp_name = f".{name}.{secrets.token_hex(12)}.tmp"
            try:
                fd = os.open(
                    temp_name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
                    0o600,
                    dir_fd=dir_fd,
                )
            except FileExistsError:
                continue
            identity_stat = None
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    identity_stat = os.fstat(handle.fileno())
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
            except BaseException:
                try:
                    os.close(fd)
                except OSError:
                    pass
                try:
                    if identity_stat is not None:
                        identity = (identity_stat.st_dev, identity_stat.st_ino)
                        if stat_identity(temp_name) == identity:
                            os.unlink(temp_name, dir_fd=dir_fd)
                except OSError:
                    pass
                raise
            return temp_name, (identity_stat.st_dev, identity_stat.st_ino)
        raise OSError("could not allocate a report staging file")

    staged: dict[str, tuple[str, tuple[int, int]]] = {}
    backups: dict[str, tuple[str, tuple[int, int]]] = {}
    committed: dict[str, tuple[int, int]] = {}
    rollback_incomplete = False
    try:
        if not directory_is_current():
            raise OSError("output directory changed before validation")

        original_targets: dict[str, tuple[int, int]] = {}
        for name in contents:
            identity = stat_identity(name)
            if identity is None:
                continue
            target = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
            if stat.S_ISLNK(target.st_mode):
                raise InputError("report output target is a symlink")
            if not stat.S_ISREG(target.st_mode):
                raise InputError("report output target must be a regular file")
            if not overwrite:
                raise InputError("one or more report outputs already exist")
            original_targets[name] = identity

        for name, content in contents.items():
            staged[name] = stage(name, content)

        for name, expected in original_targets.items():
            while True:
                backup = f".{name}.backup.{secrets.token_hex(12)}"
                if stat_identity(backup) is None:
                    break
            os.rename(name, backup, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
            backup_identity = stat_identity(backup)
            if backup_identity is None:
                raise OSError("report backup disappeared")
            backups[name] = (backup, backup_identity)
            if backup_identity != expected:
                raise OSError("report target changed before backup")
            if not directory_is_current():
                raise OSError("output directory changed during backup")

        for name, (temp_name, temp_identity) in staged.items():
            os.link(temp_name, name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd, follow_symlinks=False)
            target_identity = stat_identity(name)
            if target_identity != temp_identity:
                raise OSError("committed report target identity changed")
            committed[name] = target_identity
            if not directory_is_current():
                raise OSError("output directory changed during commit")

        if not directory_is_current():
            raise OSError("output directory changed after commit")
        for name, (backup, backup_identity) in backups.items():
            try:
                unlink_if_identity(backup, backup_identity)
            except OSError:
                pass
    except BaseException as exc:
        for name, committed_identity in reversed(list(committed.items())):
            try:
                if not unlink_if_identity(name, committed_identity) and stat_identity(name) is not None:
                    rollback_incomplete = True
            except OSError:
                rollback_incomplete = True
        for name, (backup, backup_identity) in backups.items():
            try:
                if stat_identity(backup) != backup_identity:
                    rollback_incomplete = True
                    continue
                if stat_identity(name) is not None:
                    rollback_incomplete = True
                    continue
                os.link(backup, name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd, follow_symlinks=False)
                if stat_identity(name) != backup_identity:
                    rollback_incomplete = True
                    continue
                unlink_if_identity(backup, backup_identity)
            except OSError:
                rollback_incomplete = True
        if rollback_incomplete:
            raise InputError("report transaction failed; replacement targets were preserved and unrecovered backups retained") from exc
        if isinstance(exc, InputError):
            raise
        raise InputError("report transaction failed and was rolled back") from exc
    finally:
        for temp_name, identity in staged.values():
            try:
                unlink_if_identity(temp_name, identity)
            except OSError:
                pass
        os.close(dir_fd)
        os.close(parent_fd)


def _validate_output_path(path: Path, overwrite: bool) -> None:
    if path.is_symlink():
        raise InputError("output path must not be a symlink")
    if path.exists():
        if not overwrite:
            raise InputError(f"output already exists: {path.name}")
        if not path.is_file() or not os.access(path, os.W_OK):
            raise InputError("output path is not a writable file")
        return
    parent = path.parent
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    if not parent.is_dir() or not os.access(parent, os.W_OK):
        raise InputError("output directory is not writable")


def _error(
    code: str, message: str, *, requests_attempted: int = 0,
    responses_received: int = 0, completion_unknown: bool = False,
) -> None:
    print(json.dumps({
        "code": code, "message": message, "requests_made": requests_attempted,
        "requests_attempted": requests_attempted,
        "responses_received": responses_received,
        "completion_unknown": completion_unknown,
    }, sort_keys=True), file=sys.stderr)


def _analyze(args: argparse.Namespace) -> int:
    payload = _read_json(args.input)
    if args.sources:
        library = _read_json(args.sources)
        if not isinstance(library, dict) or library.get("project") != PROJECT or not isinstance(library.get("sources"), list):
            raise InputError("source library is invalid")
        if not isinstance(payload, dict) or not isinstance(payload.get("sources"), list):
            raise InputError("analysis input sources are invalid")
        combined = payload["sources"] + library["sources"]
        source_ids = [source.get("id") for source in combined if isinstance(source, dict)]
        if len(source_ids) != len(set(source_ids)):
            raise InputError("duplicate source IDs across input and library")
        payload = {**payload, "sources": combined}
    report = analyze(payload)
    if args.dry_run:
        print(json.dumps({"project": PROJECT, "input_sources": len(payload["sources"]), "publishers": len(payload["publishers"]), "requests_made": 0}, sort_keys=True))
        return 0
    out_dir = Path(args.out_dir)
    targets = [out_dir / "report.json", out_dir / "pitches.md", out_dir / "pitches.csv"]
    _write_report_set(out_dir, {
        "report.json": render_json(report),
        "pitches.md": render_markdown(report),
        "pitches.csv": render_csv(report),
    }, args.overwrite)
    print(json.dumps({"status": report["status"], "decision": report["decision"], "outputs": [str(path) for path in targets], "requests_made": 0}, sort_keys=True))
    return 0


def _collect(args: argparse.Namespace) -> int:
    manifest = _read_json(args.manifest)
    planned = plan(manifest)
    if args.dry_run:
        print(json.dumps(planned, ensure_ascii=False, sort_keys=True))
        return 0
    if not args.live:
        raise InputError("collect without --live is only allowed with --dry-run")
    if not args.accept_charges or not args.approval:
        raise InputError("--accept-charges and --approval are required for live collection")
    _validate_output_path(Path(args.out), args.overwrite)
    approval = _read_json(args.approval)
    api_key = os.environ.get("BRIGHT_DATA_API_KEY", "")
    zones = {
        "web_unlocker": os.environ.get("BRIGHT_DATA_WEB_UNLOCKER_ZONE", ""),
        "serp": os.environ.get("BRIGHT_DATA_SERP_ZONE", ""),
    }
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    library = collect(manifest, approval=approval, api_key=api_key, zones=zones, now=now)
    try:
        _write_json(Path(args.out), library, args.overwrite)
    except InputError as exc:
        receipt = library["receipt"]
        exc.requests_attempted = receipt["requests_attempted"]
        exc.responses_received = receipt["responses_received"]
        exc.completion_unknown = receipt["completion_unknown"]
        raise
    print(json.dumps({
        "status": library["receipt"]["status"],
        "requests_made": library["receipt"]["requests_attempted"],
        "requests_attempted": library["receipt"]["requests_attempted"],
        "responses_received": library["receipt"]["responses_received"],
        "completion_unknown": library["receipt"]["completion_unknown"],
        "output": args.out,
    }, sort_keys=True))
    return 4 if library["receipt"]["status"] in {"partial", "pending", "completion_unknown"} else (3 if library["receipt"]["status"] == "failed" else 0)


def _import(args: argparse.Namespace) -> int:
    _validate_output_path(Path(args.out), args.overwrite)
    raw = _read_bytes(args.file)
    try:
        records = raw.decode("utf-8") if args.kind == "web_page" else json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError("provider export has an invalid format") from exc
    library = normalize_export(args.kind, records, role=args.role, source_url=args.source_url, observed_at=args.observed_at, source_prefix=args.source_prefix)
    _write_json(Path(args.out), library, args.overwrite)
    print(json.dumps({"status": library["receipt"]["status"], "requests_made": 0, "output": args.out}, sort_keys=True))
    return 4 if library["receipt"]["status"] == "partial" else 0


def _resume(args: argparse.Namespace) -> int:
    if not args.live or not args.accept_charges:
        raise InputError("resume requires --live and --accept-charges")
    _validate_output_path(Path(args.out), args.overwrite)
    value = resume(_read_json(args.receipt), approval=_read_json(args.approval), api_key=os.environ.get("BRIGHT_DATA_API_KEY", ""), now=os.environ.get("ARTICLE_PITCH_SHORTLIST_NOW", ""))
    _write_json(Path(args.out), value, args.overwrite)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "analyze":
            return _analyze(args)
        if args.command == "collect":
            return _collect(args)
        if args.command == "import-provider":
            return _import(args)
        return _resume(args)
    except InputError as exc:
        _error(
            getattr(exc, "code", "invalid_input"), str(exc),
            requests_attempted=getattr(exc, "requests_attempted", 0),
            responses_received=getattr(exc, "responses_received", 0),
            completion_unknown=getattr(exc, "completion_unknown", False),
        )
        return 2
    except CollectionError as exc:
        _error(exc.code, str(exc))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
