#!/usr/bin/env python3
"""scan-dependencies.py -- axis 2 (SCA) detection + triage filing for the
review-sca-axis feature (IMPLEMENTATION.md "Layer Structure" / "Shared
Components").

Co-owned by two tasks in one plugin change (IMPLEMENTATION.md "Module
co-ownership skeleton"):

  * task0001 implements `scan` -- ecosystem detection, external scanner
    execution, normalization into review-output-schema.json's shape.
  * task0005 (this half) implements `file-tasks` -- turns unresolved
    `vulnerability` findings into human-triageable artifacts: one task per
    package in the external task system when an entry point was supplied
    and its incomplete-task listing could be obtained, otherwise a report
    under the MAIN working tree's `tmp/` (never the current project root --
    see `resolve_main_worktree_root`).

Each task supplies the OTHER subcommand as a placeholder that exits with
EXIT_EXECUTION_ERROR and a one-line "implemented by the other task"
message -- never overwritten by a real implementation until the
corresponding task's branch merges. Whichever task's branch merges SECOND
performs the symmetric merge duty described there: adopt the parent
branch's file wholesale (git checkout --theirs), then re-apply only its own
half on top -- a placeholder must never overwrite a real implementation.

Exit codes: 0 = success (exactly one JSON object on stdout); 2 = execution
error (bad/missing input, a subcommand not yet implemented on this branch,
or a failure while talking to the external task system) -- the reason is
printed to stderr, and nothing is printed to stdout.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

EXIT_OK = 0
EXIT_EXECUTION_ERROR = 2


class ExecutionError(Exception):
    """Common base for every exit-2 condition this script raises."""


class GitError(ExecutionError):
    pass


class EntryPointError(ExecutionError):
    pass


class FindingTitleError(ExecutionError):
    """A finding's `title` does not match the Finding text-encoding
    contract -- raised rather than silently guessed at."""


# ---------------------------------------------------------------------------
# Untrusted-text truncation (IMPLEMENTATION.md Shared Components,
# "Untrusted-text truncation"). ONE helper, top-level so either
# subcommand's implementation calls the SAME code -- the 4096-byte
# discipline R3b step 4 also applies, reused here rather than restated.
# ---------------------------------------------------------------------------

UNTRUSTED_TEXT_MAX_BYTES = 4096
TRUNCATION_MARKER = "… [truncated]"  # "… [truncated]"


def truncate_untrusted(text):
    """Caps `text` at UNTRUSTED_TEXT_MAX_BYTES bytes (UTF-8), appending
    TRUNCATION_MARKER when truncation actually happens. `None` passes
    through unchanged. Never splits a multi-byte UTF-8 sequence."""
    if text is None:
        return text
    data = text.encode("utf-8")
    if len(data) <= UNTRUSTED_TEXT_MAX_BYTES:
        return text
    marker_bytes = TRUNCATION_MARKER.encode("utf-8")
    budget = max(0, UNTRUSTED_TEXT_MAX_BYTES - len(marker_bytes))
    truncated = data[:budget]
    while truncated:
        try:
            return truncated.decode("utf-8") + TRUNCATION_MARKER
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    return TRUNCATION_MARKER


# ---------------------------------------------------------------------------
# Finding text-encoding contract (IMPLEMENTATION.md Shared Components):
# title = "{package}: {advisory_id} — {advisory short title}". This is
# the ONE recovery function -- no call site parses a finding's title
# itself.
# ---------------------------------------------------------------------------

_TITLE_RE = re.compile(r"^(?P<package>.+?): (?P<advisory_id>\S+)(?: — (?P<advisory_title>.*))?$")


def recover_package_advisory(finding):
    """Returns (package, advisory_id) recovered from finding['title'] per
    the Finding text-encoding contract. Raises FindingTitleError when the
    title does not match the contract's shape."""
    title = finding.get("title") if isinstance(finding, dict) else None
    if not isinstance(title, str):
        raise FindingTitleError(f"finding has no string title: {finding!r}")
    m = _TITLE_RE.match(title)
    if not m:
        raise FindingTitleError(
            f"title does not match the finding text-encoding contract "
            f"'{{package}}: {{advisory_id}} — {{advisory short title}}': {title!r}"
        )
    return m.group("package"), m.group("advisory_id")


def group_findings_by_package(findings):
    """Groups findings by package (recovered via recover_package_advisory),
    de-duplicating repeated advisory ids within the SAME input, and
    truncating package/advisory_id ONCE here so every downstream use (the
    dedup key, a filed field, the report) sees the same canonical string a
    later run would also derive from the same finding. Returns an ordered
    dict-like mapping {package: [(advisory_id, severity), ...]}."""
    groups = {}
    order = []
    for finding in findings:
        package, advisory_id = recover_package_advisory(finding)
        package = truncate_untrusted(package)
        advisory_id = truncate_untrusted(advisory_id)
        severity = finding.get("severity")
        if package not in groups:
            groups[package] = []
            order.append(package)
        if not any(a == advisory_id for a, _ in groups[package]):
            groups[package].append((advisory_id, severity))
    return {p: groups[p] for p in order}


# ---------------------------------------------------------------------------
# Duplicate-detection key (IMPLEMENTATION.md "Grouping and content" /
# "Duplicate detection"): the ONE function every call site uses to build a
# key. Package alone is the task-identity key; package + advisory_id is
# the entry-identity key. A later widening of task identity (e.g. "package
# name + major version") changes only this function.
# ---------------------------------------------------------------------------

_KEY_SEP = "\x00"


def build_dedup_key(package, advisory_id=None):
    if advisory_id is None:
        return package
    return f"{package}{_KEY_SEP}{advisory_id}"


def format_reference_line(advisory_id, severity):
    """One 参照 (references) field line: the advisory identifier and
    its severity, recorded as a fact -- never derived into priority.
    Callers pass an already-truncated advisory_id (see
    group_findings_by_package)."""
    return f"{advisory_id} ({severity})"


def parse_reference_line(line):
    """Recovers the advisory identifier this script itself wrote via
    format_reference_line, for round-tripping an existing task's 参照
    field content back into per-advisory dedup keys."""
    line = line.strip()
    if line.endswith(")") and " (" in line:
        return line.rsplit(" (", 1)[0]
    return line


# ---------------------------------------------------------------------------
# Report destination resolution (FR13): tmp/ under the FIRST entry of
# `git worktree list --porcelain` run against the project root -- the main
# working tree. The single-worktree top-level-resolution git subcommand
# (project root only, per current worktree) is deliberately never used:
# under review it would resolve to the integration worktree, the wrong
# tree.
# ---------------------------------------------------------------------------

def resolve_main_worktree_root(project_root):
    """Returns the path of the FIRST entry `git worktree list --porcelain`
    reports for the repository containing `project_root`. This is the main
    working tree regardless of which worktree `project_root` itself points
    at -- the destination must not depend on which worktree happened to
    invoke this script."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(project_root), "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise GitError(f"cannot run git worktree list: {exc}")
    if proc.returncode != 0:
        raise GitError(f"git worktree list --porcelain failed: {proc.stderr.strip()}")
    for line in proc.stdout.splitlines():
        if line.startswith("worktree "):
            return line[len("worktree "):].strip()
    raise GitError("git worktree list --porcelain produced no 'worktree' entry")


def report_destination(project_root, feature):
    root = resolve_main_worktree_root(project_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(root) / "tmp" / f"sca-triage-{feature}-{timestamp}.md"


def write_report(dest, groups, *, degraded, degraded_reason):
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# SCA triage report", ""]
    if degraded:
        lines.append(
            f"DEGRADED: task-system listing unavailable ({degraded_reason}); "
            "filed as a report instead of the task system (D6)."
        )
        lines.append("")
    for package, entries in groups.items():
        lines.append(f"## {package}")
        for advisory_id, severity in entries:
            lines.append(f"- {format_reference_line(advisory_id, severity)}")
        lines.append("")
    dest.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# External task system invocation. The entry point is always an INPUT
# (never probed for -- that is R0's job, task0003); every call here is a
# subprocess to the caller-supplied executable. Tests substitute a
# stand-in that records the arguments it received and replies with a
# scripted result.
# ---------------------------------------------------------------------------

SECURITY_TASK_TYPE = "セキュリティ"  # "セキュリティ"
FILED_PRIORITY = "高"  # "高"


def list_security_tasks(entry_point):
    """Returns a list of {"id", "package", "status", "references"} dicts
    describing every task of the security type, or None when the listing
    could not be obtained (non-zero exit, or stdout that is not a JSON
    array) -- the caller degrades to the report branch (IMPLEMENTATION.md
    D6). `status` is one of "incomplete" / "complete" / "discarded";
    `references` is the raw current 参照 field text (possibly empty,
    possibly multi-line)."""
    try:
        proc = subprocess.run(
            [str(entry_point), "task", "list", "--type", SECURITY_TASK_TYPE, "--format", "json"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, list):
        return None
    return data


def _write_references_tempfile(reference_lines):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write("\n".join(reference_lines) + "\n")
        return fh.name


def create_security_task(entry_point, package, reference_lines):
    refs_path = _write_references_tempfile(reference_lines)
    try:
        proc = subprocess.run(
            [
                str(entry_point), "task", "create",
                "--title", package,
                "--type", SECURITY_TASK_TYPE,
                "--priority", FILED_PRIORITY,
                "--references-file", refs_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        Path(refs_path).unlink(missing_ok=True)
    if proc.returncode != 0:
        raise EntryPointError(f"task create failed for package {package!r}: {proc.stderr.strip()}")


def append_security_task_references(entry_point, task_id, reference_lines):
    refs_path = _write_references_tempfile(reference_lines)
    try:
        proc = subprocess.run(
            [str(entry_point), "task", "update", "--id", str(task_id), "--append-references-file", refs_path],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        Path(refs_path).unlink(missing_ok=True)
    if proc.returncode != 0:
        raise EntryPointError(f"task update failed for task {task_id!r}: {proc.stderr.strip()}")


# ---------------------------------------------------------------------------
# `file-tasks` subcommand (task0005's half in full)
# ---------------------------------------------------------------------------

def file_tasks(project_root, feature, findings, entry_point):
    """Pre: `findings` is a list of already-gated finding dicts (each
    unresolved, each category "vulnerability" -- the SELECTION is the
    orchestrator's, never this function's). `entry_point` is the
    notion-task-dispatch entry-point path, or None when R0's probe found
    none. Post: one summary dict naming the branch taken, the packages
    filed / appended to, the duplicates suppressed, and the report path
    when the report branch ran. Idempotent for the same input: a second
    call against the same unresolved set and the same listing state files
    nothing new."""
    groups = group_findings_by_package(findings)

    if entry_point is None:
        dest = report_destination(project_root, feature)
        write_report(dest, groups, degraded=False, degraded_reason=None)
        return {
            "branch": "report",
            "filed_packages": [],
            "appended_packages": [],
            "suppressed": [],
            "report_path": str(dest),
            "degraded": False,
            "degraded_reason": None,
        }

    listing = list_security_tasks(entry_point)
    if listing is None:
        dest = report_destination(project_root, feature)
        write_report(dest, groups, degraded=True, degraded_reason="task_listing_unavailable")
        return {
            "branch": "report",
            "filed_packages": [],
            "appended_packages": [],
            "suppressed": [],
            "report_path": str(dest),
            "degraded": True,
            "degraded_reason": "task_listing_unavailable",
        }

    tasks_by_package_key = {}
    for task in listing:
        key = build_dedup_key(task.get("package"))
        tasks_by_package_key.setdefault(key, []).append(task)

    filed_packages = []
    appended_packages = []
    suppressed = []

    for package, entries in groups.items():
        candidate_tasks = tasks_by_package_key.get(build_dedup_key(package), [])
        incomplete_tasks = [t for t in candidate_tasks if t.get("status") == "incomplete"]

        if incomplete_tasks:
            task = incomplete_tasks[0]
            existing_lines = [l for l in (task.get("references") or "").splitlines() if l.strip()]
            existing_keys = {build_dedup_key(package, parse_reference_line(l)) for l in existing_lines}

            new_lines = []
            for advisory_id, severity in entries:
                key = build_dedup_key(package, advisory_id)
                if key in existing_keys:
                    suppressed.append([package, advisory_id])
                    continue
                new_lines.append(format_reference_line(advisory_id, severity))

            if new_lines:
                append_security_task_references(entry_point, task.get("id"), new_lines)
                appended_packages.append(package)
        else:
            lines = [format_reference_line(advisory_id, severity) for advisory_id, severity in entries]
            create_security_task(entry_point, package, lines)
            filed_packages.append(package)

    return {
        "branch": "ntd",
        "filed_packages": filed_packages,
        "appended_packages": appended_packages,
        "suppressed": suppressed,
        "report_path": None,
        "degraded": False,
        "degraded_reason": None,
    }


def file_tasks_command(args):
    findings_path = Path(args.findings)
    try:
        text = findings_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ExecutionError(f"cannot read findings file {findings_path}: {exc}")
    try:
        findings = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExecutionError(f"cannot parse findings file {findings_path}: {exc}")
    if not isinstance(findings, list):
        raise ExecutionError(f"findings file {findings_path} must contain a JSON array")

    return file_tasks(Path(args.project_root), args.feature, findings, args.entry_point)


# ---------------------------------------------------------------------------
# `scan` subcommand -- PLACEHOLDER. Implemented by task0001. Whichever
# task's branch merges second must adopt the parent's real implementation
# of the OTHER subcommand wholesale and never let this placeholder
# overwrite it (IMPLEMENTATION.md "Module co-ownership skeleton").
# ---------------------------------------------------------------------------

PLACEHOLDER_MESSAGE = (
    "{subcommand}: implemented by the other task "
    "(see IMPLEMENTATION.md 'Module co-ownership skeleton')"
)


def scan_command(args):
    raise ExecutionError(PLACEHOLDER_MESSAGE.format(subcommand="scan"))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(prog="scan-dependencies.py")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    scan_parser = sub.add_parser(
        "scan",
        help="[PLACEHOLDER on this branch -- implemented by task0001] run axis 2's detection pass",
    )
    # Accepts anything without validation: this branch's `scan` never uses
    # its arguments, and the real argument surface belongs to task0001.
    scan_parser.add_argument("scan_args", nargs=argparse.REMAINDER)
    scan_parser.set_defaults(func=scan_command)

    ft_parser = sub.add_parser(
        "file-tasks",
        help="turn unresolved vulnerability findings into human-triageable artifacts",
    )
    ft_parser.add_argument("--project-root", required=True)
    ft_parser.add_argument("--feature", required=True)
    ft_parser.add_argument("--findings", required=True, help="path to a JSON file holding an array of findings")
    ft_parser.add_argument(
        "--entry-point",
        default=None,
        help="path to the notion-task-dispatch entry point (absent => report branch)",
    )
    ft_parser.set_defaults(func=file_tasks_command)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except ExecutionError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_EXECUTION_ERROR
    print(json.dumps(result, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
