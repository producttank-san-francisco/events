#!/usr/bin/env python3
"""Fetch GitHub traffic data and render a plain-language Markdown report."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.parse import quote

SCHEMA_VERSION = 1
API_VERSION = "2022-11-28"
ENDPOINTS = {
    "views": "traffic/views",
    "clones": "traffic/clones",
    "referrers": "traffic/popular/referrers",
    "paths": "traffic/popular/paths",
}
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REFERRER_DOMAIN_PATTERN = re.compile(r"^[A-Za-z0-9.-]+$")


class ReportError(RuntimeError):
    """A user-actionable collection or validation failure."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as temporary_file:
            temporary_file.write(data)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def append_json_line(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8") as log_file:
        log_file.write(encoded)
        log_file.flush()
        os.fsync(log_file.fileno())


def require_nonnegative_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReportError(f"Invalid GitHub response: {field} must be a non-negative integer")
    return value


def validate_count_pair(item: dict[str, Any], field: str) -> None:
    count = require_nonnegative_integer(item.get("count"), f"{field}.count")
    uniques = require_nonnegative_integer(item.get("uniques"), f"{field}.uniques")
    if uniques > count:
        raise ReportError(f"Invalid GitHub response: {field}.uniques exceeds {field}.count")


def validate_series(payload: Any, name: str) -> None:
    if not isinstance(payload, dict):
        raise ReportError(f"Invalid GitHub response: {name} must be an object")
    validate_count_pair(payload, name)
    rows = payload.get(name)
    if not isinstance(rows, list) or not rows:
        raise ReportError(f"Invalid GitHub response: {name}.{name} must be a non-empty list")
    observed_count = 0
    previous_timestamp = ""
    for index, row in enumerate(rows):
        field = f"{name}.{name}[{index}]"
        if not isinstance(row, dict):
            raise ReportError(f"Invalid GitHub response: {field} must be an object")
        validate_count_pair(row, field)
        timestamp = row.get("timestamp")
        if not isinstance(timestamp, str):
            raise ReportError(f"Invalid GitHub response: {field}.timestamp must be a string")
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as error:
            raise ReportError(f"Invalid GitHub response: {field}.timestamp is not ISO 8601") from error
        if timestamp <= previous_timestamp:
            raise ReportError(f"Invalid GitHub response: {name} timestamps must be ascending")
        previous_timestamp = timestamp
        observed_count += row["count"]
    if observed_count != payload["count"]:
        raise ReportError(
            f"Invalid GitHub response: {name}.count is {payload['count']} but daily rows total {observed_count}"
        )


def validate_ranked_rows(payload: Any, name: str, text_fields: Sequence[str]) -> None:
    if not isinstance(payload, list):
        raise ReportError(f"Invalid GitHub response: {name} must be a list")
    for index, row in enumerate(payload):
        field = f"{name}[{index}]"
        if not isinstance(row, dict):
            raise ReportError(f"Invalid GitHub response: {field} must be an object")
        validate_count_pair(row, field)
        for text_field in text_fields:
            if not isinstance(row.get(text_field), str) or not row[text_field].strip():
                raise ReportError(f"Invalid GitHub response: {field}.{text_field} must be a non-empty string")


def validate_snapshot(snapshot: Any) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        raise ReportError("Invalid snapshot: top level must be an object")
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        raise ReportError(f"Unsupported snapshot schema: expected {SCHEMA_VERSION}")
    repository = snapshot.get("repository")
    if not isinstance(repository, str) or not REPOSITORY_PATTERN.fullmatch(repository):
        raise ReportError("Invalid snapshot: repository must be OWNER/REPOSITORY")
    report = snapshot.get("report")
    if not isinstance(report, dict):
        raise ReportError("Invalid snapshot: report configuration is missing")
    focus_path = report.get("focus_path")
    focus_label = report.get("focus_label")
    if focus_path is not None and (not isinstance(focus_path, str) or not focus_path.startswith("/")):
        raise ReportError("Invalid snapshot: report.focus_path must start with /")
    if not isinstance(focus_label, str) or not focus_label.strip():
        raise ReportError("Invalid snapshot: report.focus_label must be non-empty")
    if not isinstance(snapshot.get("fetched_at"), str):
        raise ReportError("Invalid snapshot: fetched_at is missing")
    validate_series(snapshot.get("views"), "views")
    validate_series(snapshot.get("clones"), "clones")
    validate_ranked_rows(snapshot.get("referrers"), "referrers", ("referrer",))
    validate_ranked_rows(snapshot.get("paths"), "paths", ("path", "title"))
    return snapshot


def run_gh_api(
    repository: str,
    endpoint: str,
    api_calls: list[dict[str, Any]],
    *,
    timeout_seconds: int = 30,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> Any:
    resource = f"repos/{repository}/{endpoint}"
    command = [
        "gh",
        "api",
        "--method",
        "GET",
        resource,
        "-H",
        "Accept: application/vnd.github+json",
        "-H",
        f"X-GitHub-Api-Version: {API_VERSION}",
    ]
    started = time.monotonic()
    try:
        result = runner(command, capture_output=True, text=True, timeout=timeout_seconds, check=False)
    except FileNotFoundError as error:
        api_calls.append(
            {
                "resource": resource,
                "status": "spawn_error",
                "duration_ms": round((time.monotonic() - started) * 1000),
            }
        )
        raise ReportError("Cannot run GitHub API: install the gh CLI and authenticate with gh auth login") from error
    except subprocess.TimeoutExpired as error:
        api_calls.append(
            {
                "resource": resource,
                "status": "timeout",
                "duration_ms": round((time.monotonic() - started) * 1000),
            }
        )
        raise ReportError(f"GitHub API timed out after {timeout_seconds}s: {resource}") from error
    stdout = result.stdout.encode("utf-8")
    call_record = {
        "resource": resource,
        "status": "success" if result.returncode == 0 else "error",
        "exit_code": result.returncode,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "response_bytes": len(stdout),
        "response_sha256": sha256_bytes(stdout),
    }
    api_calls.append(call_record)
    if result.returncode != 0:
        detail = result.stderr.strip() or "no error detail returned"
        raise ReportError(f"GitHub API failed for {resource}: {detail}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        call_record["status"] = "invalid_json"
        raise ReportError(f"GitHub API returned invalid JSON for {resource}") from error


def collect_snapshot(
    repository: str,
    focus_path: str | None,
    focus_label: str,
    api_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    if not REPOSITORY_PATTERN.fullmatch(repository):
        raise ReportError("Repository must use OWNER/REPOSITORY with no URL or extra path")
    payloads: dict[str, Any] = {}
    for name, endpoint in ENDPOINTS.items():
        payloads[name] = run_gh_api(repository, endpoint, api_calls)
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "repository": repository,
        "fetched_at": iso_utc(utc_now()),
        "source": "GitHub REST API repository traffic endpoints",
        "report": {"focus_path": focus_path, "focus_label": focus_label},
        **payloads,
    }
    return validate_snapshot(snapshot)


def metric_window(snapshot: dict[str, Any]) -> tuple[str, str]:
    rows = snapshot["views"]["views"]
    return rows[0]["timestamp"][:10], rows[-1]["timestamp"][:10]


def display_path(repository: str, path: str) -> str:
    prefix = f"/{repository}"
    relative = path[len(prefix) :] if path.startswith(prefix) else path
    if not relative:
        return "Repository home"
    return relative.replace("/tree/main/", "").replace("/blob/main/", "")

def escape_table_text(value: str) -> str:
    return value.replace("|", "\\|").replace("[", "\\[").replace("]", "\\]")


def page_link(repository: str, path: str) -> str:
    label = escape_table_text(display_path(repository, path))
    return f"[{label}](https://github.com{quote(path, safe='/')})"


def referrer_label(referrer: str) -> str:
    label = escape_table_text(referrer)
    if REFERRER_DOMAIN_PATTERN.fullmatch(referrer) and "." in referrer:
        return f"[{label}](https://{referrer})"
    return label


def render_report(snapshot: dict[str, Any]) -> str:
    validate_snapshot(snapshot)
    repository = snapshot["repository"]
    views = snapshot["views"]
    clones = snapshot["clones"]
    paths = snapshot["paths"]
    referrers = snapshot["referrers"]
    focus_path = snapshot["report"]["focus_path"]
    focus_label = snapshot["report"]["focus_label"]
    start_date, end_date = metric_window(snapshot)

    lines = [
        f"# GitHub traffic: [{repository}](https://github.com/{repository})",
        "",
        (
            f"> **GitHub counted {views['uniques']} unique visitors and {views['count']} page views "
            f"from {start_date} through {end_date}.**"
        ),
        "",
        "GitHub reports a rolling 14-day window. “Unique” means GitHub’s estimate of distinct visitors or clients, not confirmed people.",
        "",
        "![Animated cumulative page views and Git clones](traffic.gif)",
        "",
    ]

    if focus_path:
        focus_match = next(
            ((rank, row) for rank, row in enumerate(paths, 1) if row["path"] == focus_path),
            None,
        )
        lines.extend([f"## {focus_label}", ""])
        if focus_match:
            rank, focus_row = focus_match
            lines.extend(
                [
                    f"- **{focus_row['uniques']} unique visitors** opened the page **{focus_row['count']} times**.",
                    f"- It ranked **#{rank}** among the repository pages GitHub returned.",
                    "- **This does not show link clicks.** GitHub counts visits to this page, not clicks from it to another site.",
                ]
            )
        else:
            lines.append("- GitHub did not include this page in its top-path results, so no page-specific count is available.")
        lines.append("")

    lines.extend(
        [
            "## At a glance",
            "",
            "| Activity | Total | Unique | Plain-language meaning |",
            "| --- | ---: | ---: | --- |",
            f"| Page views | {views['count']} | {views['uniques']} | Repository pages loaded in a browser |",
            f"| Git clones | {clones['count']} | {clones['uniques']} | Repository copies requested through Git; automation may be included |",
            "",
            "## Most-viewed pages",
            "",
            "| Page | Views | Unique visitors |",
            "| --- | ---: | ---: |",
        ]
    )
    for row in paths:
        lines.append(f"| {page_link(repository, row['path'])} | {row['count']} | {row['uniques']} |")

    lines.extend(["", "## Where visitors came from", ""])
    if referrers:
        lines.extend(["| Referring site | Visits | Unique visitors |", "| --- | ---: | ---: |"])
        for row in referrers:
            lines.append(f"| {referrer_label(row['referrer'])} | {row['count']} | {row['uniques']} |")
    else:
        lines.append("GitHub reported no referring sites for this window.")

    lines.extend(
        [
            "",
            "## Daily activity",
            "",
            "Only days with recorded activity are shown.",
            "",
            "| Date | Page views | Unique visitors | Clones | Unique cloning clients |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    clones_by_date = {row["timestamp"][:10]: row for row in clones["clones"]}
    for row in views["views"]:
        date = row["timestamp"][:10]
        clone_row = clones_by_date.get(date, {"count": 0, "uniques": 0})
        if row["count"] or clone_row["count"]:
            lines.append(
                f"| {date} | {row['count']} | {row['uniques']} | {clone_row['count']} | {clone_row['uniques']} |"
            )

    lines.extend(
        [
            "",
            "## What these numbers cannot answer",
            "",
            "- They do not identify visitors.",
            "- They do not show which outbound links visitors clicked.",
            "- Daily unique counts cannot be added: the same visitor can appear on more than one day.",
            "- Git clones can include automated systems, so they are not the same as people adopting the material.",
            "",
            "## Source",
            "",
            f"GitHub REST API snapshot fetched at {snapshot['fetched_at']}. The adjacent JSON file contains the exact API responses used for this report.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--repo", help="GitHub repository as OWNER/REPOSITORY")
    source.add_argument("--from-snapshot", type=Path, help="Render a previously saved source JSON file")
    parser.add_argument("--focus-path", help="Exact repository path to call out in the report")
    parser.add_argument("--focus-label", default="Focus page", help="Plain-language heading for the focus path")
    parser.add_argument("--output-dir", type=Path, default=Path("docs/reports/github-traffic"))
    parser.add_argument("--log-file", type=Path, help="JSON Lines invocation log; defaults inside output directory")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv if argv is not None else sys.argv[1:])
    run_id = str(uuid.uuid4())
    started_at = utc_now()
    started_monotonic = time.monotonic()
    api_calls: list[dict[str, Any]] = []
    log_path = arguments.log_file or arguments.output_dir / "invocations.jsonl"
    report_path = arguments.output_dir / "report.md"
    snapshot_path = arguments.output_dir / "source.json"
    animation_path = arguments.output_dir / "traffic.gif"
    log_record: dict[str, Any] = {
        "run_id": run_id,
        "started_at": iso_utc(started_at),
        "arguments": {
            "repo": arguments.repo,
            "from_snapshot": str(arguments.from_snapshot) if arguments.from_snapshot else None,
            "focus_path": arguments.focus_path,
            "focus_label": arguments.focus_label,
            "output_dir": str(arguments.output_dir),
        },
        "api_calls": api_calls,
    }
    try:
        if arguments.from_snapshot:
            try:
                snapshot = json.loads(arguments.from_snapshot.read_text(encoding="utf-8"))
            except OSError as error:
                raise ReportError(f"Cannot read snapshot {arguments.from_snapshot}: {error}") from error
            except json.JSONDecodeError as error:
                raise ReportError(f"Snapshot is not valid JSON: {arguments.from_snapshot}") from error
        else:
            snapshot = collect_snapshot(arguments.repo, arguments.focus_path, arguments.focus_label, api_calls)
        snapshot_bytes = (json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        report_bytes = render_report(snapshot).encode("utf-8")
        try:
            if __package__:
                from .traffic_animation.github_traffic_animation import AnimationError, render_traffic_gif
            else:
                from traffic_animation.github_traffic_animation import AnimationError, render_traffic_gif
        except ModuleNotFoundError as error:
            if error.name == "PIL":
                raise ReportError("Cannot render traffic animation: install Pillow") from error
            raise
        try:
            animation_bytes = render_traffic_gif(snapshot)
        except AnimationError as error:
            raise ReportError(str(error)) from error
        atomic_write(snapshot_path, snapshot_bytes)
        atomic_write(report_path, report_bytes)
        atomic_write(animation_path, animation_bytes)
        log_record.update(
            {
                "status": "success",
                "outputs": {
                    "snapshot": {"path": str(snapshot_path), "bytes": len(snapshot_bytes), "sha256": sha256_bytes(snapshot_bytes)},
                    "report": {"path": str(report_path), "bytes": len(report_bytes), "sha256": sha256_bytes(report_bytes)},
                    "animation": {
                        "path": str(animation_path),
                        "bytes": len(animation_bytes),
                        "sha256": sha256_bytes(animation_bytes),
                    },
                },
            }
        )
        print(f"Wrote {report_path}")
        print(f"Wrote {snapshot_path}")
        print(f"Wrote {animation_path}")
        return_code = 0
    except ReportError as error:
        log_record.update({"status": "error", "error": str(error)})
        print(f"error: {error}", file=sys.stderr)
        return_code = 1
    except OSError as error:
        log_record.update({"status": "error", "error": f"File operation failed: {error}"})
        print(f"error: file operation failed: {error}", file=sys.stderr)
        return_code = 1
    except Exception as error:
        log_record.update({"status": "internal_error", "error": f"{type(error).__name__}: {error}"})
        raise
    finally:
        log_record["finished_at"] = iso_utc(utc_now())
        log_record["duration_ms"] = round((time.monotonic() - started_monotonic) * 1000)
        try:
            append_json_line(log_path, log_record)
        except OSError as error:
            print(f"error: could not write invocation log {log_path}: {error}", file=sys.stderr)
            return_code = 1
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
