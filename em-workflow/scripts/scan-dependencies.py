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

Reworked by task0007 (review round 1, feature-docs/review-sca-axis/tasks/
task0007.md): the task-listing outcome is now three-valued (an available
listing with zero validated entries files rather than degrading), a
malformed finding is skipped and recorded rather than aborting the batch,
and the filing loop records partial progress when the external task system
fails mid-batch instead of letting the exception escape. task0008 and
task0009 rework the `scan` half in disjoint regions of this same file
(IMPLEMENTATION.md D8).
"""

import argparse
import contextlib
import dataclasses
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

# The standard-library TOML parser (Python 3.11+). Guarded like the optional
# YAML dependency above: an interpreter without it still loads this module,
# and any TOML input is then treated as unparseable (see `_parse_toml`).
try:
    import tomllib
except ImportError:
    tomllib = None

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


class JobConstructionError(ExecutionError, ValueError):
    """`build_scan_job` was asked for a job it must never build (a pip
    lockfile without a prepared requirements file). A ValueError as well, so
    a caller can reject on either type."""


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


# Poison-finding policy (task plan "Poison-finding policy: skip and
# record"): the ONE reason string recorded for every malformed finding,
# derived from this script's own contract text -- NEVER from the offending
# finding's own content (NFR4: advisory-sourced text never becomes part of
# a reason identifier). recover_package_advisory's own exception message
# is deliberately not reused here since it may echo the offending finding.
MALFORMED_FINDING_REASON = (
    "finding title does not match the finding text-encoding contract "
    "'{package}: {advisory_id} — {advisory short title}'"
)


def group_findings_by_package(findings):
    """Groups findings by package (recovered via recover_package_advisory),
    de-duplicating repeated advisory ids within the SAME input, and
    truncating package/advisory_id ONCE here so every downstream use (the
    dedup key, a filed field, the report) sees the same canonical string a
    later run would also derive from the same finding.

    A finding whose title violates the Finding text-encoding contract is
    SKIPPED and recorded rather than aborting the whole batch (task plan
    "Poison-finding policy") -- every other finding is still grouped, even
    when every finding in the input is malformed.

    Returns (groups, malformed) where `groups` is an ordered dict-like
    mapping {package: [(advisory_id, severity), ...]} and `malformed` is a
    list of {"position": <index in `findings`>, "reason": <machine-stable
    reason>} dicts, in input order."""
    groups = {}
    order = []
    malformed = []
    for position, finding in enumerate(findings):
        try:
            package, advisory_id = recover_package_advisory(finding)
        except FindingTitleError:
            malformed.append({"position": position, "reason": MALFORMED_FINDING_REASON})
            continue
        package = truncate_untrusted(package)
        advisory_id = truncate_untrusted(advisory_id)
        severity = finding.get("severity") if isinstance(finding, dict) else None
        if package not in groups:
            groups[package] = []
            order.append(package)
        if not any(a == advisory_id for a, _ in groups[package]):
            groups[package].append((advisory_id, severity))
    return {p: groups[p] for p in order}, malformed


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


def write_report(dest, groups, *, degraded, degraded_reason, malformed_findings=None):
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# SCA triage report", ""]
    if degraded:
        lines.append(
            f"DEGRADED: task-system listing unavailable ({degraded_reason}); "
            "filed as a report instead of the task system (D6)."
        )
        lines.append("")
    if malformed_findings:
        lines.append("## Malformed findings (skipped)")
        for m in malformed_findings:
            lines.append(f"- position {m['position']}: {m['reason']}")
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


def _entry_point_is_valid(entry_point):
    """Returns True when entry_point is an existing regular file that is
    executable. Callers must not exec entry_point unless this passes."""
    try:
        path = Path(entry_point)
        return path.is_file() and os.access(path, os.X_OK)
    except OSError:
        return False


class ListingOutcome:
    """The task-listing outcome is three-valued, not two (task plan "The
    listing outcome is three-valued, not two"):

    - `available=True` -- the entry point ran, exited successfully, and
      produced a JSON array. `tasks` is that array after item-wise
      validation; it may legitimately be an EMPTY list (the normal
      first-run state, not an error). Entries dropped item-wise by
      validation while others survive do not make the listing unavailable
      -- they are just counted in `dropped_count`.
    - `available=False` -- one of the five genuine unavailability
      conditions (IMPLEMENTATION.md D6): `tasks` is None and `reason` is a
      machine-stable identifier distinguishing which condition occurred.
    """

    def __init__(self, available, tasks=None, reason=None, dropped_count=0):
        self.available = available
        self.tasks = tasks
        self.reason = reason
        self.dropped_count = dropped_count


def list_security_tasks(entry_point):
    """Returns a ListingOutcome (see class docstring) describing every task
    of the security type. The caller degrades to the report branch ONLY
    when `available` is False (IMPLEMENTATION.md D6) -- an available
    listing with zero validated entries must reach the filing branch.
    `status` is one of "incomplete" / "complete" / "discarded";
    `references` is the raw current 参照 field text (possibly empty,
    possibly multi-line)."""
    if not _entry_point_is_valid(entry_point):
        return ListingOutcome(available=False, reason="entry_point_invalid")
    try:
        proc = subprocess.run(
            [str(entry_point), "task", "list", "--type", SECURITY_TASK_TYPE, "--format", "json"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ListingOutcome(available=False, reason="listing_launch_failed")
    if proc.returncode != 0:
        return ListingOutcome(available=False, reason="listing_exit_nonzero")
    try:
        data = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return ListingOutcome(available=False, reason="listing_output_not_json")
    if not isinstance(data, list):
        return ListingOutcome(available=False, reason="listing_output_not_array")
    validated = []
    dropped_count = 0
    for entry in data:
        if not isinstance(entry, dict):
            dropped_count += 1
            continue
        if not isinstance(entry.get("id"), str):
            dropped_count += 1
            continue
        if not isinstance(entry.get("package"), str):
            dropped_count += 1
            continue
        if not isinstance(entry.get("status"), str):
            dropped_count += 1
            continue
        references = entry.get("references")
        if references is not None and not isinstance(references, str):
            dropped_count += 1
            continue
        validated.append(entry)
    return ListingOutcome(available=True, tasks=validated, dropped_count=dropped_count)


def _write_references_tempfile(reference_lines):
    """Writes `reference_lines` to a new temporary file and returns its path.
    A failure while writing removes the partial file before the OS error
    propagates, so the caller never has a path to clean up that it was not
    given."""
    fh = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
    try:
        with fh:
            fh.write("\n".join(reference_lines) + "\n")
    except OSError:
        with contextlib.suppress(OSError):
            Path(fh.name).unlink(missing_ok=True)
        raise
    return fh.name


def _run_entry_point_with_references(reference_lines, build_argv):
    """Writes `reference_lines` to a temporary references file, launches the
    entry point with the argv `build_argv(<that file's path>)` builds, removes
    the file afterwards (also when the launch failed) and returns the
    CompletedProcess. An OS error raised while creating or writing the file
    or while launching the process propagates as an OSError for the two
    public helpers below to convert. An OS error raised while removing the
    file is reported on stderr only and leaves the result unchanged: the
    CompletedProcess is still returned, and a launch error already in flight
    still reaches the caller as it was. Removal is attempted once; a file
    that cannot be removed stays, and a file that is already absent is
    accepted silently."""
    refs_path = None
    try:
        refs_path = _write_references_tempfile(reference_lines)
        return subprocess.run(
            build_argv(refs_path),
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        if refs_path is not None:
            try:
                Path(refs_path).unlink(missing_ok=True)
            except OSError as exc:
                print(
                    f"file-tasks: could not remove temporary references file {refs_path}: {exc}",
                    file=sys.stderr,
                )


def create_security_task(entry_point, package, reference_lines):
    """Creates one security task for `package` through the entry point.
    Pre: unchanged -- an entry point that is not an executable file raises
    EntryPointError. Post: the task was created, or EntryPointError was
    raised: for a non-zero exit of the launched process, and for ANY OS error
    raised while writing the temporary references file or launching the
    process (the OS error is kept as the cause and its text may appear in the
    message, which only ever reaches stderr). A raw OS error never leaves
    this function. An OS error raised while removing the temporary file is
    reported on stderr only and leaves the result unchanged."""
    if not _entry_point_is_valid(entry_point):
        raise EntryPointError(f"entry point {entry_point!r} is not an executable file")
    try:
        proc = _run_entry_point_with_references(
            reference_lines,
            lambda refs_path: [
                str(entry_point), "task", "create",
                "--title", package,
                "--type", SECURITY_TASK_TYPE,
                "--priority", FILED_PRIORITY,
                "--references-file", refs_path,
            ],
        )
    except OSError as exc:
        raise EntryPointError(f"task create failed for package {package!r}: {exc}") from exc
    if proc.returncode != 0:
        raise EntryPointError(f"task create failed for package {package!r}: {proc.stderr.strip()}")


def append_security_task_references(entry_point, task_id, reference_lines):
    """Appends `reference_lines` to the references of task `task_id` through
    the entry point. Same pre/postcondition as `create_security_task`: the
    only exception that leaves this function for a launch, file or exit
    failure is EntryPointError."""
    if not _entry_point_is_valid(entry_point):
        raise EntryPointError(f"entry point {entry_point!r} is not an executable file")
    try:
        proc = _run_entry_point_with_references(
            reference_lines,
            lambda refs_path: [
                str(entry_point), "task", "update",
                "--id", str(task_id),
                "--append-references-file", refs_path,
            ],
        )
    except OSError as exc:
        raise EntryPointError(f"task update failed for task {task_id!r}: {exc}") from exc
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
    nothing new.

    Every pre-existing key (`branch`, `filed_packages`, `appended_packages`,
    `suppressed`, `report_path`, `degraded`, `degraded_reason`) keeps its
    name and meaning (task plan "the summary dict grows, never changes
    shape"). Five keys are ADDED:

    - `malformed_findings` -- findings skipped by the poison-finding policy
      (position + machine-stable reason, never advisory-sourced text).
    - `listing_dropped_count` -- entries the task listing dropped item-wise
      by validation (0 when no listing was consulted or nothing dropped).
    - `failed_package` / `failure_reason` -- set when the external task
      system failed mid-batch (an entry-point failure, which includes an OS
      error raised while launching the entry point or writing its temporary
      references file); both None on a batch that completed without such a
      failure. `failure_reason` is a fixed token, never OS-error or
      advisory-sourced text; that text goes to stderr only.
    - `unattempted_packages` -- on a mid-batch failure, the failed package
      followed by every later package in the group order (after title
      recovery, de-duplication and truncation), in that order; malformed
      findings never appear in it. An empty list when the batch completed,
      on the report branch and on the degraded report branch.

    No exception escapes this function for a poison finding or a mid-batch
    external failure -- both degrade to data in the returned summary
    instead."""
    groups, malformed_findings = group_findings_by_package(findings)

    if entry_point is None:
        dest = report_destination(project_root, feature)
        write_report(dest, groups, degraded=False, degraded_reason=None, malformed_findings=malformed_findings)
        return {
            "branch": "report",
            "filed_packages": [],
            "appended_packages": [],
            "suppressed": [],
            "report_path": str(dest),
            "degraded": False,
            "degraded_reason": None,
            "malformed_findings": malformed_findings,
            "listing_dropped_count": 0,
            "failed_package": None,
            "failure_reason": None,
            "unattempted_packages": [],
        }

    listing_outcome = list_security_tasks(entry_point)
    if not listing_outcome.available:
        dest = report_destination(project_root, feature)
        write_report(
            dest, groups,
            degraded=True, degraded_reason=listing_outcome.reason,
            malformed_findings=malformed_findings,
        )
        return {
            "branch": "report",
            "filed_packages": [],
            "appended_packages": [],
            "suppressed": [],
            "report_path": str(dest),
            "degraded": True,
            "degraded_reason": listing_outcome.reason,
            "malformed_findings": malformed_findings,
            "listing_dropped_count": 0,
            "failed_package": None,
            "failure_reason": None,
            "unattempted_packages": [],
        }

    listing = listing_outcome.tasks
    tasks_by_package_key = {}
    for task in listing:
        key = build_dedup_key(task.get("package"))
        tasks_by_package_key.setdefault(key, []).append(task)

    filed_packages = []
    appended_packages = []
    suppressed = []
    failed_package = None
    failure_reason = None

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
                try:
                    append_security_task_references(entry_point, task.get("id"), new_lines)
                except EntryPointError as exc:
                    failed_package = package
                    failure_reason = "task_update_failed"
                    print(f"file-tasks: {failure_reason} for package {package!r}: {exc}", file=sys.stderr)
                    break
                appended_packages.append(package)
        else:
            lines = [format_reference_line(advisory_id, severity) for advisory_id, severity in entries]
            try:
                create_security_task(entry_point, package, lines)
            except EntryPointError as exc:
                failed_package = package
                failure_reason = "task_create_failed"
                print(f"file-tasks: {failure_reason} for package {package!r}: {exc}", file=sys.stderr)
                break
            filed_packages.append(package)

    # The failed package and every package after it in the group order were
    # never completed (empty when the walk ran to the end). Group keys are
    # unique, so the failed package's position is unambiguous.
    package_order = list(groups)
    unattempted_packages = (
        package_order[package_order.index(failed_package):] if failed_package is not None else []
    )

    return {
        "branch": "ntd",
        "filed_packages": filed_packages,
        "appended_packages": appended_packages,
        "suppressed": suppressed,
        "report_path": None,
        "degraded": False,
        "degraded_reason": None,
        "malformed_findings": malformed_findings,
        "listing_dropped_count": listing_outcome.dropped_count,
        "failed_package": failed_package,
        "failure_reason": failure_reason,
        "unattempted_packages": unattempted_packages,
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
# `scan` subcommand (task0001's half in full): axis 2's ecosystem
# detection, tool execution and normalization pass. Re-applied on top of
# task0005's real `file-tasks` half after parent-side adoption (neither
# subcommand is a placeholder in this merged file -- see the module
# docstring's "Module co-ownership skeleton" description).
# ---------------------------------------------------------------------------

DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parent.parent / "references" / "vuln-scanners.yaml"
)


def load_registry(path):
    if yaml is None:
        raise ExecutionError("PyYAML is required (import yaml failed)")
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ExecutionError(f"cannot read registry file {path}: {exc}")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ExecutionError(f"cannot parse registry file {path}: {exc}")
    if not isinstance(data, dict) or not isinstance(data.get("ecosystems"), list):
        raise ExecutionError(
            f"registry file {path} is missing a top-level ecosystems list"
        )
    return data


# Lockfile basenames per registered ecosystem -- review-phase.md dispatches
# the `vulnerability` perspective on these manifests "and their lockfiles",
# a wider trigger than the registry's own `manifests` lists. Kept here
# (not in the registry file) since a lockfile still resolves to the SAME
# ecosystem entry/normalizer as its manifest -- it is not a new ecosystem.
ECOSYSTEM_LOCKFILES = {
    "npm": {"package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml"},
    "cargo": {"Cargo.lock"},
    "pip": {"poetry.lock", "Pipfile.lock"},
    "go": {"go.sum"},
}

# Manifests review-phase.md's trigger also covers but this registry has no
# scanner/normalizer for. Matched separately from `select_ecosystems` so a
# change confined to one of these yields an explicit skip rather than a
# silent, unqualified "no findings".
UNSUPPORTED_MANIFESTS = {
    "composer.json": "composer_unsupported",
    "composer.lock": "composer_unsupported",
    "Gemfile": "bundler_unsupported",
    "Gemfile.lock": "bundler_unsupported",
    "build.gradle": "gradle_unsupported",
    "build.gradle.kts": "gradle_unsupported",
    "pom.xml": "maven_unsupported",
}


def select_ecosystems(registry, changed_files):
    """Reduces `changed_files` to the set of manifests OR lockfiles the
    registry recognises (matched by basename -- a manifest/lockfile can
    live at any project-relative path), then to the ecosystems those files
    select. Returns registry ecosystem entries in registry order; empty
    when no changed file matches any registered manifest or lockfile."""
    changed_basenames = {os.path.basename(f) for f in changed_files}
    selected = []
    for ecosystem in registry["ecosystems"]:
        name = ecosystem.get("ecosystem", "unknown")
        manifests = set(ecosystem.get("manifests") or [])
        lockfiles = ECOSYSTEM_LOCKFILES.get(name, set())
        if changed_basenames & (manifests | lockfiles):
            selected.append(ecosystem)
    return selected


def unsupported_manifest_reasons(changed_files):
    """Skip reasons for changed files matching review-phase.md's wider
    `vulnerability` trigger (composer.json, Gemfile, build.gradle/pom.xml)
    that this registry has no scanner for. Deduplicated, sorted for a
    stable combined reason string."""
    changed_basenames = {os.path.basename(f) for f in changed_files}
    return sorted({UNSUPPORTED_MANIFESTS[b] for b in changed_basenames if b in UNSUPPORTED_MANIFESTS})


# Executable allowlist per known ecosystem (IMPLEMENTATION.md's registered
# ecosystems only -- an entry naming anything else is rejected rather than
# executed, regardless of what a registry file/override says).
ALLOWED_EXECUTABLES = {
    "npm": {"npm"},
    "cargo": {"cargo-audit"},
    "pip": {"pip-audit"},
    "go": {"govulncheck"},
}


def validate_ecosystem_entry(ecosystem):
    """Validates a registry ecosystem entry before it is ever turned into a
    subprocess command: known ecosystem name, executable basename present
    in ALLOWED_EXECUTABLES for that ecosystem, and args that are a plain
    list of strings (no shell metacharacters, no path separators -- the
    registry's args are flags/literal values, not paths to arbitrary
    binaries). Returns an error string describing the failure, or None
    when the entry is safe to execute."""
    name = ecosystem.get("ecosystem")
    if name not in ALLOWED_EXECUTABLES:
        return f"{name or 'unknown'}_ecosystem_not_allowlisted"

    executable = ecosystem.get("executable")
    if not isinstance(executable, str) or not executable:
        return f"{name}_executable_invalid"
    if os.path.basename(executable) != executable:
        return f"{name}_executable_invalid"
    if executable not in ALLOWED_EXECUTABLES[name]:
        return f"{name}_executable_not_allowlisted"

    args = ecosystem.get("args") or []
    if not isinstance(args, list):
        return f"{name}_args_invalid"
    for arg in args:
        if not isinstance(arg, str):
            return f"{name}_args_invalid"
        if arg.startswith(os.sep) or (os.altsep and arg.startswith(os.altsep)):
            return f"{name}_args_invalid"
        if re.search(r"[;&|`$<>\n\r]", arg):
            return f"{name}_args_invalid"

    return None


def build_command(ecosystem):
    return [ecosystem["executable"]] + list(ecosystem.get("args") or [])


def resolve_executable(name):
    """The absolute path of the scanner executable `name` (an allowlisted
    bare name -- planning validates the registry entry first), or None.

    Only ABSOLUTE entries of the search list are searched. The list is the
    process PATH when that variable is present (an empty value counts as
    present and yields no entries); when PATH is unset it is the platform
    default search path (`os.defpath`), read at call time. An empty entry and a
    relative entry (`tools`, `./node_modules/.bin`, `.`, `~/bin`) are skipped
    silently: nothing is expanded, and no implicit current-directory entry is
    searched on any platform. Such an entry names a different directory
    depending on the current directory (the process cwd at planning, the
    job's cwd at launch), so it could let a file inside the reviewed tree
    stand in for the scanner.

    The first absolute entry, in its original order, that holds an existing
    non-directory file named `name` that the current user may execute wins;
    the result is that entry joined with `name`, unnormalized, and therefore
    absolute. None means no absolute entry qualifies -- including a scanner
    reachable only through relative or empty entries -- and planning reports
    the existing `<ecosystem>_tool_not_found` reason for it."""
    search_path = os.environ.get("PATH")
    if search_path is None:
        search_path = os.defpath
    for entry in search_path.split(os.pathsep):
        if not entry or not os.path.isabs(entry):
            continue
        candidate = os.path.join(entry, name)
        if (
            os.path.exists(candidate)
            and os.access(candidate, os.X_OK)
            and not os.path.isdir(candidate)
        ):
            return candidate
    return None


def manifest_file_for(ecosystem, changed_files):
    """The first changed file whose basename is one of this ecosystem's
    manifests -- a project-relative path, so R3b step 1's existence check
    passes. Falls back to the registry's own first manifest name (never
    reached in practice, since an ecosystem is only selected when a
    matching changed file exists -- see select_ecosystems).

    pip is the one ecosystem that prefers a lockfile (sca-python-lockfile-
    audit C2): when the change holds a pip lockfile (poetry.lock /
    Pipfile.lock) the target is the FIRST such lockfile in `changed_files`
    order, even when a pyproject.toml / requirements.txt appears earlier.
    Without a pip lockfile the target is what it always was. npm, cargo and
    go keep their manifest-first order.

    The selection rule is unchanged by per-project binding: `build_scan_jobs`
    calls this once per (ecosystem, project directory) group, with ONLY that
    group's changed files, in their original input order (FR2). `run_scan`
    never selects a target again; it launches the target the plan carries."""
    manifests = set(ecosystem.get("manifests") or [])
    lockfiles = ECOSYSTEM_LOCKFILES.get(ecosystem.get("ecosystem", "unknown"), set())
    if ecosystem.get("ecosystem") == "pip":
        for f in changed_files:
            if os.path.basename(f) in lockfiles:
                return f
    for f in changed_files:
        if os.path.basename(f) in manifests:
            return f
    for f in changed_files:
        if os.path.basename(f) in lockfiles:
            return f
    manifest_list = ecosystem.get("manifests") or ["unknown"]
    return manifest_list[0]


# ---------------------------------------------------------------------------
# Scan job construction (IMPLEMENTATION.md Shared Components, "Scan job";
# task0008 Design, "The scan job" / "Trusted binary, never a multiplexer
# subcommand" / "Configuration isolation"). PURE: no subprocess is launched
# by anything in this section. `build_scan_jobs`, the caller of everything
# here, plans the scan: it validates each selected registry entry
# (validate_ecosystem_entry), resolves its executable (resolve_executable)
# and returns one `ScanPlan` per project-directory group -- an
# unresolvable/invalid entry yields no plan and the ecosystem's existing
# tool-absent skip reason instead, never a fallback command form. Resolution
# searches only the ABSOLUTE entries of PATH (the default search path when
# PATH is unset) and never an empty or relative entry, so every plan carries
# an absolute executable, and a scanner reachable only through relative or
# empty entries gets the existing `<ecosystem>_tool_not_found` reason.
# `build_scan_job` then builds ONE job from a plan's ALREADY-RESOLVED
# executable and target once the run side has bound and prepared the group.
# ---------------------------------------------------------------------------

# Process plumbing carried through when present -- locating the shell, temp
# space and the scanner's own helper programs -- never a source of a TOOL'S
# OWN configuration (a registry endpoint, a subcommand alias). Every key but
# PATH is carried through unchanged. PATH keeps only its absolute entries,
# unmodified and in their original order, and is left out when no absolute
# entry remains, so a scanner cannot resolve a helper program from a relative
# or empty entry (see build_child_env). Everything else the reviewed
# project's environment might carry is left out: the child environment is
# built explicitly, never inherited wholesale (task0008 Design,
# "Configuration isolation").
CHILD_ENV_BASE_KEYS = ("PATH", "HOME", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT", "USERPROFILE")

# Per-ecosystem pins, each through the tool's OWN documented environment
# variable, keeping the reviewed project's configuration out of the set the
# child process reads from. npm and cargo are protected a second way, by WHERE
# they run (sca-scanner-project-config-isolation): each of their scan groups
# runs from a per-group isolation directory outside the reviewed tree that
# holds only copies of the validated scan inputs, so the reviewed project's
# own `.npmrc` / `.cargo/audit.toml` are not on the scanners' discovery path
# at all. No pin below was added or changed for that; a project-level file is
# excluded by the isolation directory, not by a pin.
#   npm   -- npm_config_registry pins the package-registry endpoint (an
#            environment variable outranks a `registry=` line in any .npmrc in
#            npm's own documented config precedence); npm_config_userconfig
#            points the user-level config file outside the reviewed tree.
#            npm itself runs from the isolation directory, where no project
#            `.npmrc` exists on the cwd or any ancestor path.
#   cargo -- cargo-audit is resolved and executed directly (never through
#            the `cargo` front end -- see ALLOWED_EXECUTABLES), which
#            already removes the [alias] dispatch the registry's OLD
#            `cargo audit` form was vulnerable to. No pin is needed: it runs
#            from the isolation directory with `--file` pointing at the copied
#            Cargo.lock, so no project `.cargo/audit.toml` is read, and
#            `--url` / `--db` are never passed.
#   pip   -- PIP_CONFIG_FILE keeps a reviewed project's own pip.conf from
#            being read; PIP_INDEX_URL pins the package index.
#   go    -- GOENV=off disables reading any go env config file at all;
#            GOPROXY is pinned to the public module proxy so it cannot be
#            redirected by one. GOWORK=off stops go from discovering a
#            go.work file above the project directory, so the scan stays
#            inside the bound project instead of an ancestor workspace.
#            GOFLAGS=-mod=readonly stops go from rewriting go.mod / go.sum
#            (and replaces whatever flags the caller's GOFLAGS carried).
# Trusted configuration scope (FR11): HOME, the npm globalconfig, the
# Cargo-home `audit.toml` and the advisory DB are managed by the reviewer and
# cannot be changed by the PR author. This module disables or overrides none
# of them: HOME is passed to the child as is, and no pin for any of them is
# added.
ECOSYSTEM_ENV_PINS = {
    "npm": {
        "npm_config_registry": "https://registry.npmjs.org/",
        "npm_config_userconfig": os.devnull,
    },
    "cargo": {},
    "pip": {
        "PIP_CONFIG_FILE": os.devnull,
        "PIP_INDEX_URL": "https://pypi.org/simple/",
    },
    "go": {
        "GOENV": "off",
        "GOWORK": "off",
        "GOFLAGS": "-mod=readonly",
        "GOPROXY": "https://proxy.golang.org,direct",
    },
}


def build_child_env(ecosystem, environ=None):
    """The explicit child environment for one scan job: a minimal base
    (process plumbing only, see CHILD_ENV_BASE_KEYS) plus this ecosystem's
    pins (ECOSYSTEM_ENV_PINS) layered on top. Every base key but PATH is
    copied unchanged when `environ` has it. PATH keeps only the entries of
    `environ`'s PATH that are non-empty and absolute, each as written and in
    its original order, joined with the platform's path-list separator, and
    it is left out when no such entry remains or `environ` has no PATH, so a
    scanner cannot resolve its own helper programs from a relative or empty
    entry. The decision is lexical: no file is opened, no filesystem state is
    inspected and no process is started, and the result is identical
    regardless of what configuration files the reviewed project's tree
    happens to contain."""
    environ = os.environ if environ is None else environ
    name = ecosystem.get("ecosystem", "unknown")
    env = {}
    for key in CHILD_ENV_BASE_KEYS:
        if key not in environ:
            continue
        if key == "PATH":
            entries = [
                entry for entry in environ[key].split(os.pathsep)
                if entry and os.path.isabs(entry)
            ]
            if entries:
                env[key] = os.pathsep.join(entries)
        else:
            env[key] = environ[key]
    env.update(ECOSYSTEM_ENV_PINS.get(name, {}))
    return env


def _pip_target(manifest_file):
    """task0008 Design, "The pip job audits the reviewed project, not the
    ambient environment": a changed requirements file IS the audited
    input, paired with the registry's `target_flag`. A changed
    pyproject.toml audits that project's OWN DIRECTORY instead, as a bare
    positional argument with no flag -- a manifest that only declares
    version ranges is never passed to `-r`. Returns (flagged, target):
    `flagged` is True when the registry's `target_flag` belongs immediately
    before `target` in the argument vector.

    A pip lockfile (poetry.lock / Pipfile.lock) has NO target of this kind:
    it is neither a pip-format requirements file (`-r` would misparse it)
    nor audited through its directory (that would audit the ambient
    environment's view of the project, not the lockfile's pins). Its job is
    built from a prepared requirements file in `build_scan_job`; asking
    for its target here is rejected, so the directory form can never be
    produced for a lockfile."""
    if os.path.basename(manifest_file) in ECOSYSTEM_LOCKFILES["pip"]:
        raise JobConstructionError(
            f"pip lockfile {manifest_file!r} has no direct audit target; "
            "it is audited through a prepared requirements file"
        )
    if os.path.basename(manifest_file) == "requirements.txt":
        return True, manifest_file
    dirname = os.path.dirname(manifest_file)
    return False, (dirname if dirname else ".")


# The job targets of npm, cargo and go name a project directory
# (sca-per-project-scan-binding FR3). go's scanner starts inside that
# directory; npm and cargo start from a per-group isolation directory outside
# the reviewed tree instead (sca-scanner-project-config-isolation), which
# holds copies of that project's validated scan inputs; pip keeps the project
# root (FR10).
PROJECT_BOUND_ECOSYSTEMS = frozenset({"npm", "cargo", "go"})

# The ecosystems whose scanner runs from an isolation directory.
ISOLATION_ECOSYSTEMS = frozenset({"npm", "cargo"})

# The roles of a scan group's copied inputs, as keys of PreparedInputs.files.
ROLE_MANIFEST = "manifest"
ROLE_ANCHOR = "anchor"
ROLE_LOCKFILE = "lockfile"

# Per isolating ecosystem, the roles `build_scan_job` needs a copy of.
_ISOLATION_ROLES = {
    "npm": (ROLE_MANIFEST, ROLE_ANCHOR),
    "cargo": (ROLE_LOCKFILE,),
}


@dataclasses.dataclass(frozen=True)
class PreparedInputs:
    """The prepared isolation paths of ONE npm / cargo scan group: the
    isolation directory (`directory`, the scanner's cwd) and the path of each
    copied input (`files`, keyed by role: npm `manifest` and `anchor`, cargo
    `lockfile`). A plain value -- `build_scan_job` only composes argv / cwd
    from it, so the paths need not exist there. Created and removed by
    `isolation_workspace`."""

    directory: str
    files: dict


def _bound_job_directory_parts(name, manifest_file):
    """The directory segments of an npm / cargo / go job target, in order,
    with empty and `.` segments dropped (an empty list for a root target).
    Purely lexical: no file is opened and no path is resolved on disk.

    Raises JobConstructionError for a target that is not a string, is
    absolute, has a `..` segment or contains NUL -- such a target can never
    be bound to a directory inside the project root (TM-1), so no job is
    produced for it. The message never carries the target text."""
    if not isinstance(manifest_file, str) or "\x00" in manifest_file:
        raise JobConstructionError(
            f"{name} job target is not a plain project-relative path"
        )
    normalized = manifest_file.replace(os.sep, "/")
    if os.altsep:
        normalized = normalized.replace(os.altsep, "/")
    if os.path.isabs(manifest_file) or normalized.startswith("/"):
        raise JobConstructionError(f"{name} job target must not be absolute")
    segments = normalized.split("/")
    if ".." in segments:
        raise JobConstructionError(f"{name} job target must not contain a '..' segment")
    return [segment for segment in segments[:-1] if segment not in ("", ".")]


def build_scan_job(ecosystem, manifest_file, project_root, executable_path, environ=None,
                   prepared_file=None, prepared_inputs=None):
    """Builds ONE scan job from `ecosystem`'s ALREADY-RESOLVED absolute
    `executable_path` (never re-resolved here -- see build_scan_jobs).
    Carries: the ecosystem name; the project-relative `manifest_file`; the
    full argument vector (`argv[0]` is the absolute, allowlisted executable
    path -- never a package-manager front end resolving a subcommand
    through the reviewed project's own configuration); the working
    directory; and the explicit child environment (build_child_env).
    Launches nothing -- every claim about the resulting command is
    assertable without running a scanner.

    Working directory: npm and cargo run in the isolation directory the
    run side prepared for the group (`prepared_inputs`, see below), outside
    the reviewed tree, so the reviewed project's own `.npmrc` /
    `.cargo/audit.toml` are not on the scanner's discovery path. go runs in
    the project root joined LEXICALLY with the target's directory part --
    exactly the string form of `project_root` when that part is empty (a
    root target). pip keeps the project root for every target form (FR10).
    An npm / cargo / go target that is absolute, has a `..` segment or
    contains NUL is rejected with JobConstructionError (TM-1): the caller
    passes a verified project-relative target. The job's manifest (the
    label findings carry) stays that project-relative target for every
    ecosystem.

    `prepared_inputs` (npm / cargo only; pip and go ignore it and keep their
    previous output) is a `PreparedInputs`: the isolation directory path and
    the path of each copy keyed by input role. npm's argument vector is the
    registry's `args` unchanged. cargo's is [executable, the registry's
    first arg (the `audit` subcommand), the registry's `target_flag`, the
    copied lockfile path, then the rest of the registry's `args`] -- the
    flag is read from the registry's declaration, never hard-coded here, and
    there is no `--url` / `--db`. An npm / cargo job WITHOUT `prepared_inputs`
    (or without a copy for a role it needs, or, for cargo, without a
    registry `target_flag`) is rejected with JobConstructionError: this
    function never produces an npm / cargo job whose cwd is the project root.

    Pure (NFR1): it reads and writes no file and starts no process, so the
    prepared paths and `prepared_file` need not exist. For a pip lockfile
    `manifest_file` (poetry.lock / Pipfile.lock) `prepared_file` is the path
    of the requirements file the preparation stage wrote for ONE run
    (IMPLEMENTATION.md C5/C6); the argument vector is then [executable, the
    registry's `target_flag`, prepared_file, `--no-deps`, `--disable-pip`,
    then the registry `args`] and the job's manifest stays the lockfile. A
    pip lockfile WITHOUT a prepared file is rejected with
    JobConstructionError (also a ValueError): the directory form is never
    produced for a lockfile. Every other manifest ignores `prepared_file`
    and keeps its previous argument vector, with neither `--no-deps` nor
    `--disable-pip`."""
    name = ecosystem.get("ecosystem", "unknown")
    cwd = str(project_root)
    if name in PROJECT_BOUND_ECOSYSTEMS:
        directory_parts = _bound_job_directory_parts(name, manifest_file)
        if directory_parts:
            cwd = os.path.join(cwd, *directory_parts)
    args = list(ecosystem.get("args") or [])
    argv = [executable_path]
    if name in ISOLATION_ECOSYSTEMS:
        copies = _prepared_copies(name, prepared_inputs)
        cwd = str(prepared_inputs.directory)
        if name == "cargo":
            target_flag = ecosystem.get("target_flag")
            if not isinstance(target_flag, str) or not target_flag:
                raise JobConstructionError(
                    "cargo job needs the registry's target_flag to point at the copied lockfile"
                )
            argv.extend(args[:1])
            argv.extend([target_flag, copies[ROLE_LOCKFILE]])
            args = args[1:]
    elif name == "pip":
        if os.path.basename(manifest_file) in ECOSYSTEM_LOCKFILES["pip"]:
            target_flag = ecosystem.get("target_flag")
            if not prepared_file or not target_flag:
                raise JobConstructionError(
                    f"pip lockfile job for {manifest_file!r} needs a prepared "
                    "requirements file and the registry's target_flag"
                )
            argv.extend([target_flag, str(prepared_file), "--no-deps", "--disable-pip"])
        else:
            flagged, target = _pip_target(manifest_file)
            target_flag = ecosystem.get("target_flag")
            if flagged and target_flag:
                argv.append(target_flag)
            argv.append(target)
    argv.extend(args)
    return {
        "ecosystem": name,
        "manifest": manifest_file,
        "argv": argv,
        "cwd": cwd,
        "env": build_child_env(ecosystem, environ),
    }


def _prepared_copies(name, prepared_inputs):
    """The copy path of every role `name`'s job needs, as a dict, taken from
    `prepared_inputs`. Raises JobConstructionError (no path in the message)
    when `prepared_inputs` is not a `PreparedInputs`, has no directory, or
    lacks a copy for a needed role."""
    if not isinstance(prepared_inputs, PreparedInputs) or not prepared_inputs.directory:
        raise JobConstructionError(f"{name} job needs the prepared isolation inputs")
    files = prepared_inputs.files if isinstance(prepared_inputs.files, dict) else {}
    copies = {}
    for role in _ISOLATION_ROLES[name]:
        path = files.get(role)
        if not isinstance(path, str) or not path:
            raise JobConstructionError(f"{name} job needs a prepared copy for its {role}")
        copies[role] = path
    return copies


@dataclasses.dataclass(frozen=True)
class ScanPlan:
    """One scan unit that has not been launched: the group of one ecosystem's
    changed files that share a project directory. A read-only record with
    exactly these fields:

    - `ecosystem`: the validated registry entry (its name is read from it).
    - `directory`: the group key D -- the real directory relative to the real
      project root, `/`-separated, `""` for the root; for a pip path that
      could not be verified, its raw directory part.
    - `real_root`: the real path of the project root (None when it could not
      be resolved).
    - `files`: the group's changed files, in input order.
    - `target`: the selected target. npm, cargo and go: D, a `/`, and the
      basename of the file `manifest_file_for` selected over `files` (the bare
      basename at the root); pip: the raw selected file.
    - `executable`: the absolute executable path, resolved once for the
      ecosystem.

    `run_scan` launches exactly these units and never selects a target again.
    A plan is not a verdict: the binding check still runs on the run side."""

    ecosystem: dict
    directory: str
    real_root: object
    files: tuple
    target: str
    executable: str


def build_scan_jobs(registry, changed_files, project_root):
    """The only planning stage of the `scan` subcommand: reduces `changed_files`
    to the ecosystems the registry selects (select_ecosystems, unchanged),
    validates each entry (validate_ecosystem_entry), resolves its executable
    (resolve_executable), groups that ecosystem's changed files by real
    path (`_verified_groups`) and emits ONE `ScanPlan` per (ecosystem, project
    directory) group, with the group's target already selected by
    manifest_file_for. Returns (plans, skip_reasons): ecosystems in registry
    order, each ecosystem's groups in ascending plain-string order of the
    directory (the root first), each reason at most once per ecosystem. An
    invalid entry or an unresolvable binary contributes its existing
    machine-stable skip reason once and NO plan -- no path is resolved for it
    and no fallback command form is ever attempted.

    Resolution searches only the ABSOLUTE entries of PATH (the default search
    path when PATH is unset); an empty or relative entry is never searched, so
    every plan's executable is an absolute path whatever the job's working
    directory. A scanner found only under relative or empty entries is an
    unresolvable binary: the ecosystem gets the existing
    `<ecosystem>_tool_not_found` reason once and no plan.

    Grouping is by REAL path: a changed file belongs to the group of its
    containing directory's real path relative to the real project root, so a
    symlinked alias of a directory and a `..` spelling that stays inside the
    root share one plan with the plain spelling. For npm, cargo and go a path
    that is absolute, contains NUL or escapes the root (lexically or through a
    symlink) can belong to no project directory: it joins no plan, and the
    ecosystem gains `<ecosystem>_project_unbindable` once. pip paths are only
    partitioned, never rejected; an unverifiable one keeps its raw directory
    part as its key, apart from the verified keys. An npm / cargo / go plan's
    target is the group directory, `/`, and the basename of the selected file
    (the bare basename at the root); a pip plan's target is the raw selected
    file.

    Launches no process, builds no job, opens no file and creates no
    directory: it only resolves paths and looks up the executable. A plan is
    not a verdict -- the binding check, the per-group isolation directory, the
    pip lockfile preparation and `build_scan_job` belong to `run_scan`, which
    executes these plans in order (`_scan_bound_group`, `_scan_pip_group`)."""
    plans = []
    skip_reasons = []
    for ecosystem in select_ecosystems(registry, changed_files):
        name = ecosystem.get("ecosystem", "unknown")
        validation_error = validate_ecosystem_entry(ecosystem)
        if validation_error is not None:
            skip_reasons.append(validation_error)
            continue
        executable_path = resolve_executable(ecosystem.get("executable"))
        if executable_path is None:
            skip_reasons.append(f"{name}_tool_not_found")
            continue
        real_root = _verified_real_root(project_root)
        groups, rejected = _verified_groups(name, ecosystem, changed_files, real_root)
        if rejected:
            skip_reasons.append(f"{name}_project_unbindable")
        for directory, files in groups:
            selected_file = manifest_file_for(ecosystem, files)
            if name == "pip":
                target = selected_file
            else:
                basename = os.path.basename(selected_file)
                target = f"{directory}/{basename}" if directory else basename
            plans.append(
                ScanPlan(
                    ecosystem=ecosystem,
                    directory=directory,
                    real_root=real_root,
                    files=tuple(files),
                    target=target,
                    executable=executable_path,
                )
            )
    return plans, skip_reasons


# ---------------------------------------------------------------------------
# Scan outcome (IMPLEMENTATION.md Shared Components, "Scan outcome"; task
# plan Design "Exit status and payload shape are judged together"):
# executing one scan job yields exactly ONE outcome -- `completed` with a
# payload the ecosystem's normalizer can read, or `not_completed` with a
# machine-stable reason distinguishable from every other reason (including
# the tool-absent skip FR3 already defines). There is no "completed with an
# empty payload" outcome. Neither exit status nor payload shape alone
# decides this: an audit tool legitimately exits non-zero precisely when it
# found something (so exit status alone would discard real findings), and a
# tool can exit non-zero while printing a well-formed JSON error envelope
# (so a parseable payload alone would accept a failure as data).
# ---------------------------------------------------------------------------

OUTCOME_COMPLETED = "completed"
OUTCOME_NOT_COMPLETED = "not_completed"

# The exit statuses each tool's OWN documentation defines: 0 (clean) and the
# tool's documented "found something" status. An exit status outside this
# set is `not_completed` regardless of payload shape.
DOCUMENTED_EXIT_STATUSES = {
    "npm": {0, 1},
    "cargo": {0, 1},
    "pip": {0, 1},
    "go": {0, 3},
}


def _has_success_structure(name, data):
    """True when `data`'s top level is ecosystem `name`'s OWN successful-
    report shape -- never the shape of an error envelope, and never an
    unrelated JSON object."""
    if not isinstance(data, dict):
        return False
    if name == "npm":
        return isinstance(data.get("vulnerabilities"), dict)
    if name == "cargo":
        return isinstance(data.get("vulnerabilities"), dict) and "list" in data["vulnerabilities"]
    if name == "pip":
        return isinstance(data.get("dependencies"), list)
    return False


def _error_envelope_reason(name, data):
    """A machine-stable reason when `data`'s top level is that tool's own
    documented error-envelope shape -- a well-formed JSON object reporting a
    TOOL-side failure, never a scan result. npm's missing-lockfile error
    object (`{"error": {...}}`) is the concrete case (task plan Design).
    Returns None when `data` does not match any known error-envelope
    shape."""
    if not isinstance(data, dict):
        return None
    if name == "npm" and isinstance(data.get("error"), dict):
        return f"{name}_error_envelope"
    return None


def judge_scan_outcome(name, exit_code, stdout):
    """Judges exit status and payload shape TOGETHER, per tool (task plan
    Design). Returns `(OUTCOME_COMPLETED, data)` or
    `(OUTCOME_NOT_COMPLETED, reason)`.

    `stdout` empty (after stripping) is ALWAYS not_completed -- there is no
    "completed with an empty payload" outcome: a front end that resolves
    but has no audit capability, and a scanner that dies before writing
    anything, both produce it, and both are not_completed. An error
    envelope is checked before the exit-status/success-structure rule
    because it applies "regardless of exit status" (Design). Go has its own
    validity rule over a stream of JSON objects (`_judge_go_outcome`)."""
    stripped = (stdout or "").strip()
    if not stripped:
        return OUTCOME_NOT_COMPLETED, f"{name}_empty_output"

    if name == "go":
        return _judge_go_outcome(exit_code, stripped)

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        try:
            objs = _parse_json_stream(stripped)
        except json.JSONDecodeError:
            return OUTCOME_NOT_COMPLETED, f"{name}_unparseable_output"
        if not objs:
            return OUTCOME_NOT_COMPLETED, f"{name}_unparseable_output"
        if len(objs) == 1:
            data = objs[-1]
        else:
            return OUTCOME_NOT_COMPLETED, f"{name}_unparseable_output"

    error_reason = _error_envelope_reason(name, data)
    if error_reason is not None:
        return OUTCOME_NOT_COMPLETED, error_reason

    if exit_code not in DOCUMENTED_EXIT_STATUSES.get(name, set()):
        return OUTCOME_NOT_COMPLETED, f"{name}_undocumented_exit_status"

    if not _has_success_structure(name, data):
        return OUTCOME_NOT_COMPLETED, f"{name}_unparseable_output"

    return OUTCOME_COMPLETED, data


GO_UNPARSEABLE_OUTPUT = "go_unparseable_output"
GO_UNDOCUMENTED_EXIT_STATUS = "go_undocumented_exit_status"
GO_DIRECT_MANIFEST_UNREADABLE = "go_direct_manifest_unreadable"


def _judge_go_outcome(exit_code, stripped):
    """The Go branch of `judge_scan_outcome` (stdout already known to be
    non-empty, so `go_empty_output` keeps its precedence). `govulncheck
    -json` prints a stream of JSON objects, so stdout counts as a completed
    scan only when ALL of these hold, checked in this order:

    1. it decodes as a sequence of one or more JSON values (one document is
       a sequence of one) and every top-level value is an object, else
       `go_unparseable_output`;
    2. the exit status is one of the documented ones, else
       `go_undocumented_exit_status`;
    3. at least one top-level object has a `config` key whose value is an
       object (the scanner's own header), else `go_unparseable_output`.

    The completed payload is the list of decoded top-level objects."""
    try:
        objs = _parse_json_stream(stripped)
    except (ValueError, RecursionError):
        return OUTCOME_NOT_COMPLETED, GO_UNPARSEABLE_OUTPUT
    if not objs or not all(isinstance(obj, dict) for obj in objs):
        return OUTCOME_NOT_COMPLETED, GO_UNPARSEABLE_OUTPUT
    if exit_code not in DOCUMENTED_EXIT_STATUSES["go"]:
        return OUTCOME_NOT_COMPLETED, GO_UNDOCUMENTED_EXIT_STATUS
    if not any(isinstance(obj.get("config"), dict) for obj in objs):
        return OUTCOME_NOT_COMPLETED, GO_UNPARSEABLE_OUTPUT
    return OUTCOME_COMPLETED, objs


# The time one scanner run may take before it is abandoned (seconds).
SCAN_TIMEOUT_SECONDS = 300


def run_ecosystem_command(job):
    """Runs `job`'s constructed argument vector (task0008's "Scan job"
    contract: `argv[0]` the absolute allowlisted executable, `cwd` the
    directory the job runs in, `env` the explicit child environment --
    never the calling process's environment inherited wholesale) from
    `job["cwd"]` exactly as given. For npm and cargo that is the group's
    isolation directory, outside the reviewed tree (prepared before and
    removed after this call by `_scan_bound_group`, which owns that
    lifecycle -- this function neither creates nor removes it); for go it is
    the project directory the job is bound to, for pip the project root.
    Nothing here writes inside the project root (NFR2). Returns
    `(outcome, payload)`: `payload` is the parsed data dict when `outcome`
    is `OUTCOME_COMPLETED`, or the machine-stable reason string when
    `OUTCOME_NOT_COMPLETED` (see `judge_scan_outcome`, unchanged -- this
    function only supplies WHAT gets run, never how the result is judged).
    An OS-level failure to even launch the process is its own
    `not_completed` reason, distinct from every reason `judge_scan_outcome`
    can produce from an actual process result."""
    name = job["ecosystem"]
    try:
        proc = subprocess.run(
            job["argv"],
            cwd=job["cwd"],
            env=job["env"],
            capture_output=True,
            text=True,
            timeout=SCAN_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return OUTCOME_NOT_COMPLETED, f"{name}_execution_failed"
    return judge_scan_outcome(name, proc.returncode, proc.stdout)


def _parse_json_stream(stdout):
    """Decodes a whitespace/newline-delimited sequence of JSON values (e.g.
    `govulncheck -json`'s NDJSON output) using json.JSONDecoder.raw_decode
    repeatedly, rather than a single json.loads() over the whole stdout --
    real tool output is not always one JSON object. Raises
    json.JSONDecodeError when the stream cannot be decoded at all."""
    decoder = json.JSONDecoder()
    objs = []
    idx = 0
    n = len(stdout)
    while idx < n:
        while idx < n and stdout[idx] in " \t\r\n":
            idx += 1
        if idx >= n:
            break
        obj, end = decoder.raw_decode(stdout, idx)
        objs.append(obj)
        idx = end
    return objs


def _merge_govulncheck_stream(objs):
    """Reduces the objects of one `govulncheck -json` stream to advisory
    records, one per (OSV id, module) of the scan unit.

    The stream holds separate top-level objects: `{"osv": ...}` (one per
    advisory, indexed here by its `id`) and `{"finding": ...}` (one per
    module-, package- or symbol-level hit, each with any number of traces).
    A finding object yields an OSV id (its `osv` value) and a module (the
    `module` of its first trace frame); one without a string of each
    contributes nothing. Every finding object with the same (OSV id, module),
    at any level and with any number of traces, collapses into ONE record
    `{"id", "module", "osv"}`, in first-seen order; `osv` is the stream's OSV
    object for that id, or `{"id": <id>}` when the stream holds none.

    Reduction computes neither severity nor directness and never reads
    `database_specific`."""
    osv_by_id = {}
    for obj in objs:
        if not isinstance(obj, dict):
            continue
        osv = obj.get("osv")
        if isinstance(osv, dict) and isinstance(osv.get("id"), str):
            osv_by_id[osv["id"]] = osv

    records = {}
    for obj in objs:
        if not isinstance(obj, dict):
            continue
        finding = obj.get("finding")
        if not isinstance(finding, dict):
            continue
        osv_id = finding.get("osv")
        trace = finding.get("trace")
        first_frame = trace[0] if isinstance(trace, list) and trace else None
        module = first_frame.get("module") if isinstance(first_frame, dict) else None
        if not isinstance(osv_id, str) or not isinstance(module, str):
            continue
        records.setdefault(
            (osv_id, module),
            {"id": osv_id, "module": module, "osv": osv_by_id.get(osv_id) or {"id": osv_id}},
        )
    return list(records.values())


def _map_severity(ecosystem, raw_severity):
    severity_map = ecosystem.get("severity_map") or {}
    return severity_map.get(raw_severity)


def _passes_threshold(ecosystem, is_direct, mapped_severity):
    """D5: applied FIRST, before a finding object exists. Direct
    dependencies only; severity high and above (critical/high -- anything
    else, including a severity absent from the registry's severity_map, is
    below threshold)."""
    threshold = ecosystem.get("threshold") or {}
    if threshold.get("direct_only", True) and not is_direct:
        return False
    return mapped_severity in ("critical", "high")


def _collapse_short_title(title):
    """The advisory short title with every maximal run of whitespace
    (whatever `str.isspace()` accepts -- LF, CR, TAB, VT, FF, NEL, no-break
    space, U+2028, U+2029, U+3000 and the rest) replaced by ONE ASCII space,
    and leading / trailing whitespace removed. A short title that is only
    whitespace collapses to the empty string (no fallback is added here)."""
    return " ".join(str(title).split())


def _build_finding(*, manifest_file, package, advisory_id, title, affected_range,
                    fixed_version, summary, severity):
    """IMPLEMENTATION.md "Finding text-encoding contract": `title` is
    `{package}: {advisory_id} — {advisory short title}`; `description`
    carries the affected range, the fixed version and the advisory summary;
    `suggestion` is prose only (D4 -- never diff-shaped, so a vulnerability
    finding can never be classified auto-applicable). Every advisory-sourced
    string passes through `truncate_untrusted()` -- the SAME helper
    `file_tasks` uses, per IMPLEMENTATION.md's single-helper contract.

    The short title is whitespace-collapsed (`_collapse_short_title`) BEFORE
    the title is composed and truncated, so the title is one line that
    `recover_package_advisory` can always parse back. `package` and
    `advisory_id` are passed through untouched, as are the description and
    suggestion.

    `reproduction` is always None: the vulnerability axis is not the
    security perspective, and the reviewer output schema requires the key on
    every finding."""
    title_text = truncate_untrusted(
        f"{package}: {advisory_id} — {_collapse_short_title(title)}"
    )
    description_parts = []
    if affected_range:
        description_parts.append(f"affected: {affected_range}")
    if fixed_version:
        description_parts.append(f"fixed: {fixed_version}")
    if summary:
        description_parts.append(str(summary))
    description_text = truncate_untrusted(
        " | ".join(description_parts) or "no further detail available"
    )
    suggestion_text = truncate_untrusted(
        f"Update {package} to {fixed_version or 'a patched version'} to resolve {advisory_id}."
    )
    return {
        "file": manifest_file,
        "line": None,
        "line_end": None,
        "severity": severity,
        "category": "vulnerability",
        "title": title_text,
        "description": description_text,
        "suggestion": suggestion_text,
        "reproduction": None,
    }


def _advisory_id_from_url(url):
    if not url:
        return "UNKNOWN"
    return url.rstrip("/").rsplit("/", 1)[-1]


def normalize_npm(ecosystem, data, manifest_file):
    findings = []
    vulnerabilities = data.get("vulnerabilities") or {}
    for pkg_name in sorted(vulnerabilities):
        entry = vulnerabilities[pkg_name]
        if not isinstance(entry, dict):
            continue
        is_direct = bool(entry.get("isDirect"))
        mapped = _map_severity(ecosystem, entry.get("severity"))
        if not _passes_threshold(ecosystem, is_direct, mapped):
            continue
        fix_available = entry.get("fixAvailable")
        fixed_version = fix_available.get("version") if isinstance(fix_available, dict) else None
        for via in entry.get("via") or []:
            if not isinstance(via, dict):
                continue
            findings.append(
                _build_finding(
                    manifest_file=manifest_file,
                    package=pkg_name,
                    advisory_id=_advisory_id_from_url(via.get("url")),
                    title=via.get("title") or pkg_name,
                    affected_range=via.get("range") or entry.get("range"),
                    fixed_version=fixed_version,
                    summary=via.get("title"),
                    severity=mapped,
                )
            )
    return findings


_CVSS_METRIC_WEIGHTS = {
    "AV": {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2},
    "AC": {"L": 0.77, "H": 0.44},
    "UI": {"N": 0.85, "R": 0.62},
    "C": {"H": 0.56, "L": 0.22, "N": 0.0},
    "I": {"H": 0.56, "L": 0.22, "N": 0.0},
    "A": {"H": 0.56, "L": 0.22, "N": 0.0},
}
_CVSS_PR_WEIGHTS = {
    "U": {"N": 0.85, "L": 0.62, "H": 0.27},
    "C": {"N": 0.85, "L": 0.68, "H": 0.5},
}


def _cvss_roundup(value):
    """CVSS v3.1 spec's Roundup(): round to the nearest 0.1 that is not
    below the input (banker's rounding on the raw float would round some
    scores down)."""
    int_value = round(value * 100000)
    if int_value % 10000 == 0:
        return int_value / 100000.0
    return (int_value - (int_value % 10000) + 10000) / 100000.0


def _cvss_base_score(vector):
    """Computes the CVSS v3.1 base score from an advisory's vector string
    (e.g. "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"). cargo audit's
    JSON carries no plain severity string -- only this vector -- so the
    band used for threshold/severity_map lookup has to be derived here.
    Returns None when the vector is missing or unparseable."""
    if not vector or not isinstance(vector, str):
        return None
    metrics = {}
    for part in vector.split("/"):
        if ":" not in part:
            continue
        key, _, val = part.partition(":")
        metrics[key] = val
    try:
        scope = metrics["S"]
        av = _CVSS_METRIC_WEIGHTS["AV"][metrics["AV"]]
        ac = _CVSS_METRIC_WEIGHTS["AC"][metrics["AC"]]
        ui = _CVSS_METRIC_WEIGHTS["UI"][metrics["UI"]]
        pr = _CVSS_PR_WEIGHTS[scope][metrics["PR"]]
        c = _CVSS_METRIC_WEIGHTS["C"][metrics["C"]]
        i = _CVSS_METRIC_WEIGHTS["I"][metrics["I"]]
        a = _CVSS_METRIC_WEIGHTS["A"][metrics["A"]]
    except KeyError:
        return None
    iss = 1 - ((1 - c) * (1 - i) * (1 - a))
    if scope == "U":
        impact = 6.42 * iss
    else:
        impact = 7.52 * (iss - 0.029) - 3.25 * pow(iss - 0.02, 15)
    exploitability = 8.22 * av * ac * pr * ui
    if impact <= 0:
        return 0.0
    if scope == "U":
        return _cvss_roundup(min(impact + exploitability, 10))
    return _cvss_roundup(min(1.08 * (impact + exploitability), 10))


def _cvss_severity_band(vector):
    """Qualitative severity rating per the CVSS v3.1 spec's score ranges,
    matched against this registry's severity_map (critical/high/medium/
    low/none)."""
    score = _cvss_base_score(vector)
    if score is None:
        return None
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    if score > 0.0:
        return "low"
    return "none"


class DirectNames(frozenset):
    """The direct-dependency set of ONE scan unit: the declared names, as
    written in the manifest after `package =` / workspace rename resolution
    and never canonicalized, plus whether the manifest was resolved in full.

    Immutable, and for every read an existing caller performs on a plain name
    collection (membership, iteration, size, equality with a plain set of the
    same names) it behaves exactly like an immutable set of those names.
    `complete` is true when every declaration of the manifest was resolved; a
    consumer that is handed a name collection WITHOUT a `complete` attribute
    treats it as complete (`_names_complete`)."""

    __slots__ = ("_complete",)

    def __new__(cls, names=(), complete=True):
        instance = super().__new__(cls, names)
        instance._complete = bool(complete)
        return instance

    @property
    def complete(self):
        return self._complete

    def __reduce__(self):
        return (type(self), (tuple(self), self._complete))


def _names_complete(direct_names):
    """The legacy-value rule: a name collection that has no `complete`
    attribute is treated as complete."""
    return bool(getattr(direct_names, "complete", True))


_CARGO_DEP_TABLES = {"dependencies", "dev-dependencies", "build-dependencies"}

CARGO_TOML_PARSER_UNAVAILABLE = "cargo_toml_parser_unavailable"


def _cargo_entry_name(key, value, workspace_dependencies):
    """The direct-dependency name of one dependency entry (key `key`, parsed
    value `value`) and whether the entry was understood: the string
    `package` of a table entry; for a table entry with `workspace = true` the
    string `package` of the same manifest's `[workspace.dependencies]` entry
    `key` when it has one; otherwise the key. A `package` that is not a string
    is an unexpected shape: no name is taken from it and the entry is not
    understood."""
    if isinstance(value, dict):
        if "package" in value:
            package = value["package"]
            if isinstance(package, str):
                return package, True
            return None, False
        if value.get("workspace") is True:
            inherited = workspace_dependencies.get(key)
            if isinstance(inherited, dict) and "package" in inherited:
                package = inherited["package"]
                if isinstance(package, str):
                    return package, True
                return key, False
            return key, True
    return key, True


def _cargo_dependency_tables(data):
    """Every dependency table of a parsed Cargo.toml -- the three tables at the
    top level and under each `target.<cfg>` table -- as `(tables, understood)`:
    `understood` is false when a table, `target` or a `target.<cfg>` entry
    that has to be a table is not one."""
    tables = []
    understood = True
    sources = [data]
    if "target" in data:
        target = data["target"]
        if isinstance(target, dict):
            for config in target.values():
                if isinstance(config, dict):
                    sources.append(config)
                else:
                    understood = False
        else:
            understood = False
    for source in sources:
        for table_name in sorted(_CARGO_DEP_TABLES):
            if table_name not in source:
                continue
            table = source[table_name]
            if isinstance(table, dict):
                tables.append(table)
            else:
                understood = False
    return tables, understood


def _cargo_entry_has_path(key, value, workspace_dependencies):
    """True when one root dependency entry (key `key`, parsed value `value`)
    is path-bearing: a table that has a `path` key, or a table with
    `workspace = true` whose same-key entry in `workspace_dependencies` is a
    table that has a `path` key. Only the presence of the key counts; its
    value is never interpreted, resolved or opened, and a non-table entry is
    not path-bearing."""
    if not isinstance(value, dict):
        return False
    if "path" in value:
        return True
    if value.get("workspace") is True:
        inherited = workspace_dependencies.get(key)
        return isinstance(inherited, dict) and "path" in inherited
    return False


def _cargo_workspace_view(data, tables):
    """`(workspace_dependencies, complete)` of a parsed Cargo.toml's
    `[workspace]` table: its `[workspace.dependencies]` table (empty when
    absent or not a table), and whether the root's direct set is complete.
    `tables` are the root dependency tables (`_cargo_dependency_tables`).

    `complete` is false when the table lists members (their manifests are not
    read), when it has an unexpected shape, and when a `[workspace]` table is
    present and any entry of `tables` is path-bearing -- it carries a `path`
    key directly or through `workspace = true` and the same key's
    `[workspace.dependencies]` entry; the path target may be an implicit
    workspace member whose manifest is not read. This also holds when
    `members` is absent or an empty list. The set stays complete when there is
    no `[workspace]` table (path dependencies included), when the only path
    entries sit in `[workspace.dependencies]` and no root entry inherits them,
    and for `[patch]` / `[replace]` paths, which are not root dependency
    tables."""
    if "workspace" not in data:
        return {}, True
    workspace = data["workspace"]
    if not isinstance(workspace, dict):
        return {}, False
    complete = True
    if "members" in workspace:
        members = workspace["members"]
        if not isinstance(members, list) or members:
            complete = False
    workspace_dependencies = workspace.get("dependencies", {})
    if not isinstance(workspace_dependencies, dict):
        return {}, False
    if any(
        _cargo_entry_has_path(key, value, workspace_dependencies)
        for table in tables
        for key, value in table.items()
    ):
        complete = False
    return workspace_dependencies, complete


def _cargo_direct_dependency_names(manifest_path):
    """The direct-dependency names declared by the Cargo.toml at
    `manifest_path`, parsed with tomllib, as a `DirectNames`; never raises.

    Read: `dependencies`, `dev-dependencies` and `build-dependencies` at the
    top level and under every `target.<cfg>` table (the sub-table form
    `[dependencies.serde]` is an ordinary entry of the parsed table). An
    entry's name is its `package` (also through a `workspace = true` entry
    renamed in the same manifest's `[workspace.dependencies]`), else its key;
    `[workspace.dependencies]` entries are not direct names by themselves.

    The result is incomplete when the manifest cannot be resolved, read or
    parsed (no tomllib included), when its `[workspace]` lists members -- the
    member manifests are not read -- and for any unexpected shape; the names
    resolved up to that point stay in the set. It is also incomplete when the
    manifest has a `[workspace]` table (with `members` absent or empty) and a
    root dependency table holds a path-bearing entry -- a `path` key, directly
    or inherited through `workspace = true` from the same manifest's
    `[workspace.dependencies]` -- because the path target may be an implicit
    workspace member whose manifest is not read; the path value is never
    interpreted or opened, and a path-bearing entry still contributes its name
    as above. It stays complete without a `[workspace]` table (path
    dependencies included), when the only path entries are unreferenced
    `[workspace.dependencies]` entries, and for `[patch]` / `[replace]`
    paths."""
    incomplete = DirectNames((), complete=False)
    try:
        text = _read_resolved_text(manifest_path) if manifest_path else None
        data = _parse_toml(text) if text is not None else None
        if data is None:
            return incomplete
        tables, understood = _cargo_dependency_tables(data)
        workspace_dependencies, complete = _cargo_workspace_view(data, tables)
        names = set()
        for table in tables:
            for key, value in table.items():
                name, entry_understood = _cargo_entry_name(key, value, workspace_dependencies)
                if name is not None:
                    names.add(name)
                understood = understood and entry_understood
        return DirectNames(names, complete=complete and understood)
    except Exception:
        return incomplete


def _resolve_project_relative(project_root, rel_path):
    """Joins project_root with rel_path, confining the result inside
    project_root. Returns None (never a path) when rel_path is absolute,
    escapes project_root via '..', or project_root is not supplied --
    callers must treat None as "cannot resolve", never fall back to
    joining unsafely."""
    if project_root is None or not rel_path:
        return None
    if os.path.isabs(rel_path):
        return None
    root = os.path.realpath(str(project_root))
    candidate = os.path.realpath(os.path.join(root, rel_path))
    if candidate != root and not candidate.startswith(root + os.sep):
        return None
    return candidate


def _cargo_manifest_candidate(project_root, manifest_file):
    """Resolves the Cargo.toml to scan for direct-dependency names. When
    manifest_file is itself a lockfile (Cargo.lock -- selected by
    manifest_file_for when only the lockfile changed), looks for
    Cargo.toml alongside it instead: Cargo.lock has no [dependencies]
    tables, so scanning it directly would always yield an empty direct
    set and silently reclassify every advisory as transitive. Never
    returns a lockfile path. Returns None when unresolvable/unsafe (see
    _resolve_project_relative) -- callers must not fall back to opening
    manifest_file directly in that case."""
    if os.path.basename(manifest_file) == "Cargo.lock":
        candidate_rel = os.path.join(os.path.dirname(manifest_file), "Cargo.toml")
    else:
        candidate_rel = manifest_file
    return _resolve_project_relative(project_root, candidate_rel)


# The qualitative bands a cargo advisory's severity can be determined as: the
# CVSS v3 bands `_cvss_severity_band` derives from the advisory's vector, or
# the same words in the entry's own `severity` field. Anything else is a
# severity that cannot be determined.
_CARGO_KNOWN_SEVERITIES = frozenset({"critical", "high", "medium", "low", "none"})


def normalize_cargo(ecosystem, data, manifest_file, project_root=None):
    """Turns one completed cargo-audit payload into
    `(findings, directness_undetermined)`.

    Directness of each advisory, in this order: a payload entry carrying
    `is_direct` decides itself and is never undetermined; a reported name
    whose canonical form (`canonical_pip_name`) equals the canonical form of a
    name declared in the unit's Cargo.toml is direct; otherwise it is
    transitive when the declared set is complete. Under an incomplete set an
    advisory whose severity is determined and below the threshold is dropped
    without being counted; any other is undetermined -- no finding, not
    transitive, counted exactly once in `directness_undetermined` (counts
    only: nothing taken from the manifest or the advisory is reported)."""
    findings = []
    undetermined = 0
    entries = ((data.get("vulnerabilities") or {}).get("list")) or []
    manifest_path = _cargo_manifest_candidate(project_root, manifest_file)
    direct_names = (
        _cargo_direct_dependency_names(manifest_path)
        if manifest_path
        else DirectNames((), complete=False)
    )
    declared = {canonical_pip_name(name) for name in direct_names}
    names_complete = _names_complete(direct_names)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        advisory = entry.get("advisory") or {}
        package = (entry.get("package") or {}).get("name", "unknown")
        raw_severity = _cvss_severity_band(advisory.get("cvss"))
        if raw_severity is None:
            raw_severity = entry.get("severity")
        mapped = _map_severity(ecosystem, raw_severity)
        if "is_direct" in entry:
            is_direct = bool(entry.get("is_direct"))
        elif canonical_pip_name(package) in declared:
            is_direct = True
        elif names_complete:
            is_direct = False
        else:
            severity_known = isinstance(raw_severity, str) and raw_severity in _CARGO_KNOWN_SEVERITIES
            if not severity_known or _passes_threshold(ecosystem, True, mapped):
                undetermined += 1
            continue
        if not _passes_threshold(ecosystem, is_direct, mapped):
            continue
        patched_versions = (entry.get("versions") or {}).get("patched") or []
        fixed_version = patched_versions[0] if patched_versions else None
        findings.append(
            _build_finding(
                manifest_file=manifest_file,
                package=package,
                advisory_id=advisory.get("id", "UNKNOWN"),
                title=advisory.get("title") or advisory.get("id") or "vulnerability",
                affected_range=None,
                fixed_version=fixed_version,
                summary=advisory.get("description"),
                severity=mapped,
            )
        )
    return findings, undetermined


# The leading PEP 508 name of a requirement string, accepted only when it is
# followed by the end of the string, whitespace, an extras bracket, a version
# operator, a parenthesis, a marker separator, a direct-reference marker or a
# comma.
_REQUIREMENT_NAME_RE = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?(?=$|[\s\[<>=!~(;@,])"
)
_ARCHIVE_SUFFIXES = (
    ".whl", ".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz", ".tar.xz", ".txz",
)


def _requirement_name(requirement):
    """The package name of one PEP 508 requirement string (comments and pip
    options already removed), as written; None ("no name") when the leading
    token is a URL (a scheme separator), a local path (a leading dot, slash
    or tilde, a path separator, or a wheel / source-archive suffix) or
    anything else that does not begin with a PEP 508 name. Never raises."""
    if not isinstance(requirement, str):
        return None
    match = _REQUIREMENT_NAME_RE.match(requirement.strip())
    if match is None:
        return None
    name = match.group(0)
    if name.lower().endswith(_ARCHIVE_SUFFIXES):
        return None
    return name


# ---------------------------------------------------------------------------
# pip direct-dependency resolution (task0008 Design, "The pip normalizer's
# real input contract"): pip-audit's `--format json` output carries no
# per-dependency directness flag, so directness is resolved from the
# reviewed manifest's own declared dependency set -- the same SHAPE of
# resolution the cargo path already performs against Cargo.toml
# (_cargo_direct_dependency_names), reusing _resolve_project_relative so a
# changed-file entry can never open a file outside the project root.
# pyproject.toml is read with tomllib (`_pip_pyproject_direct_names`); a
# resolver reports through `DirectNames` whether it resolved every
# declaration. A requirements file's `-r` includes are followed under the
# same confinement (`_pip_requirements_direct_names`).
# ---------------------------------------------------------------------------

# pip's own comment rule: a `#` that starts the line or follows whitespace.
_REQUIREMENTS_COMMENT_RE = re.compile(r"(^|\s+)#.*$")
# A string that starts with a URL scheme (`https:`, `file:`, `git+ssh:`, ...).
_URL_SCHEME_PREFIX_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
# The option forms a requirements file may use to include, constrain or
# declare an editable requirement: (kind, short form, long form).
_REQUIREMENTS_OPTION_FORMS = (
    ("include", "-r", "--requirement"),
    ("constraint", "-c", "--constraint"),
    ("editable", "-e", "--editable"),
)


def _requirements_logical_lines(content):
    """The logical lines of a requirements file's text: a physical line
    ending in a backslash joins the following line (a whole-line comment
    ends a joined run, as in pip), comments are dropped, and blank lines
    are skipped."""
    joined = []
    pending = []
    for line in content.splitlines():
        comment_only = _REQUIREMENTS_COMMENT_RE.match(line) is not None
        if line.endswith("\\") and not comment_only:
            pending.append(line[:-1])
            continue
        if pending:
            pending.append(" " + line if comment_only else line)
            line = "".join(pending)
            pending = []
        joined.append(line)
    if pending:
        joined.append("".join(pending))
    logical = []
    for line in joined:
        text = _REQUIREMENTS_COMMENT_RE.sub("", line).strip()
        if text:
            logical.append(text)
    return logical


def _requirements_option(text):
    """(kind, value) when the option line `text` is an include, constraint
    or editable line in any of its forms (`-r X`, `-rX`, `--requirement X`,
    `--requirement=X`, and the same for the other two); None for every
    other line. `value` may be empty. An include or constraint value is the
    first token, or the quoted text; an editable value is the rest of the
    line."""
    for kind, short, long in _REQUIREMENTS_OPTION_FORMS:
        if text.startswith(long):
            rest = text[len(long):]
            if rest.startswith("="):
                value = rest[1:].strip()
            elif rest[:1].isspace():
                value = rest.strip()
            else:
                continue
        elif text.startswith(short):
            value = text[len(short):].strip()
        else:
            continue
        if kind != "editable":
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            else:
                value = value.split(None, 1)[0] if value else ""
        return kind, value
    return None


def _requirements_include_target(project_root, including_rel, target):
    """(project-relative location, resolved path) of the include `target`
    named in the file at project-relative `including_rel`, or None when it
    may not be opened: `target` is a URL, or does not resolve to a location
    confined to the project root (`..` escapes, absolute paths outside the
    root and symlinks leading outside it)."""
    if not target or _URL_SCHEME_PREFIX_RE.match(target):
        return None
    try:
        if os.path.isabs(target):
            rel = os.path.relpath(target, project_root)
        else:
            rel = os.path.join(os.path.dirname(including_rel), target)
        resolved = _resolve_project_relative(project_root, rel)
    except (OSError, ValueError):
        return None
    if resolved is None:
        return None
    return rel, resolved


def _pip_requirements_direct_names(path, project_root):
    """The direct names of the requirements file at `path` (inside
    `project_root`), following `-r` includes -- `-r X`, `-rX`,
    `--requirement X`, `--requirement=X` -- recursively. Returns a
    `DirectNames`; never raises, never opens a file outside the project
    root and never fetches a URL.

    Each include is taken relative to the including file's directory and
    opened only when `_resolve_project_relative` confines it to the root;
    every file is opened at most once per walk (keyed by its resolved
    location), so cycles end without error. Names declared by an included
    file are direct. The set is incomplete when a file is missing or
    unreadable, an include is a URL or leaves the root, a requirement line
    has no resolvable name (a URL or a local path), or an editable line has
    none. Constraint files (`-c` / `--constraint`) are neither opened nor
    cause incompleteness; every other option line is ignored."""
    names = set()
    complete = True
    try:
        if project_root is None or not path:
            return DirectNames((), complete=False)
        root = os.path.realpath(str(project_root))
        candidate = str(path)
        if not os.path.isabs(candidate):
            candidate = os.path.join(root, candidate)
        start_rel = os.path.relpath(candidate, root)
        start = _resolve_project_relative(root, start_rel)
        if start is None:
            return DirectNames((), complete=False)
        visited = {start}
        pending = [(start_rel, start)]
        while pending:
            file_rel, file_path = pending.pop()
            text = _read_resolved_text(file_path)
            if text is None:
                complete = False
                continue
            for line in _requirements_logical_lines(text.lstrip("\ufeff")):
                if not line.startswith("-"):
                    name = _requirement_name(line)
                    if name is None:
                        complete = False
                    else:
                        names.add(name)
                    continue
                option = _requirements_option(line)
                if option is None:
                    continue
                kind, value = option
                if kind == "constraint":
                    continue
                if kind == "editable":
                    name = _requirement_name(value)
                    if name is None:
                        complete = False
                    else:
                        names.add(name)
                    continue
                target = _requirements_include_target(root, file_rel, value)
                if target is None:
                    complete = False
                    continue
                if target[1] in visited:
                    continue
                visited.add(target[1])
                pending.append(target)
    except Exception:
        complete = False
    return DirectNames(names, complete=complete)


# The Poetry tables of `[tool.poetry]` whose keys are direct names. Poetry's
# group tables (`tool.poetry.group.<g>.dependencies`) are deliberately absent.
_POETRY_DEP_TABLES = ("dependencies", "dev-dependencies")


def _pip_pyproject_direct_names(manifest_path):
    """The direct names of a pyproject.toml, read with tomllib: the `[project]`
    `dependencies` list (each item through `_requirement_name`, so quoting,
    extras, markers and direct references make no difference) plus the keys of
    `[tool.poetry.dependencies]` and `[tool.poetry.dev-dependencies]` except
    `python`. `project.optional-dependencies`, `dependency-groups`,
    `tool.poetry.group.<g>.dependencies` and every other table are never read.

    `manifest_path` is the already-confined location of the manifest (None
    when it could not be resolved). Returns a `DirectNames`; never raises.
    The set is incomplete when the manifest cannot be resolved, read or parsed
    (no tomllib, invalid TOML), when `[project].dynamic` lists `dependencies`
    without a static list, when neither a static `[project].dependencies` list
    nor a Poetry dependency table exists (a static empty list is a complete
    declaration of zero names), and for any unexpected shape (a scalar where a
    table or list is expected, a list item without a package name). Every name
    that did resolve is still returned."""
    unresolved = DirectNames((), complete=False)
    if not manifest_path:
        return unresolved
    text = _read_resolved_text(str(manifest_path))
    if text is None:
        return unresolved
    data = _parse_toml(text)
    if data is None:
        return unresolved
    return _pyproject_declared_names(data)


def _pyproject_declared_names(data):
    """The `DirectNames` declared by an already-parsed pyproject.toml table
    (see `_pip_pyproject_direct_names`)."""
    names = []
    complete = True
    declared = False  # a static project list or a Poetry dependency table exists

    if "project" in data:
        project = data["project"]
        if not isinstance(project, dict):
            complete = False
        else:
            if "dependencies" in project:
                dependencies = project["dependencies"]
                if isinstance(dependencies, list):
                    declared = True
                    for item in dependencies:
                        name = _requirement_name(item)
                        if name is None:
                            complete = False
                        else:
                            names.append(name)
                else:
                    complete = False
            if "dynamic" in project:
                dynamic = project["dynamic"]
                if not isinstance(dynamic, list):
                    complete = False
                elif "dependencies" in dynamic and "dependencies" not in project:
                    complete = False

    if "tool" in data:
        tool = data["tool"]
        if not isinstance(tool, dict):
            complete = False
        elif "poetry" in tool:
            poetry = tool["poetry"]
            if not isinstance(poetry, dict):
                complete = False
            else:
                for table_name in _POETRY_DEP_TABLES:
                    if table_name not in poetry:
                        continue
                    table = poetry[table_name]
                    if not isinstance(table, dict):
                        complete = False
                        continue
                    declared = True
                    names.extend(key for key in table if canonical_pip_name(key) != "python")

    if not declared:
        complete = False
    return DirectNames(names, complete=complete)


# The file declaring a pip lockfile's DIRECT dependencies (a lockfile carries
# no direct/transitive distinction of its own), as a sibling of the lockfile.
_PIP_LOCKFILE_DECLARATIONS = {"poetry.lock": "pyproject.toml", "Pipfile.lock": "Pipfile"}


def _pip_manifest_candidate(project_root, manifest_file):
    """Resolves the manifest to scan for direct-dependency names. When
    manifest_file is itself a lockfile (poetry.lock / Pipfile.lock --
    selected by manifest_file_for when a lockfile changed), looks alongside
    it instead, mirroring _cargo_manifest_candidate's resolution -- a
    lockfile carries no dependency TABLE to scan: pyproject.toml for
    poetry.lock, Pipfile for Pipfile.lock. Every other manifest maps to
    itself. Never returns a lockfile path. Returns None when
    unresolvable/unsafe (see _resolve_project_relative: a path outside the
    project root, including through a symlink)."""
    basename = os.path.basename(manifest_file)
    if basename in _PIP_LOCKFILE_DECLARATIONS:
        candidate_rel = os.path.join(
            os.path.dirname(manifest_file), _PIP_LOCKFILE_DECLARATIONS[basename]
        )
    elif basename in ECOSYSTEM_LOCKFILES["pip"]:
        return None
    else:
        candidate_rel = manifest_file
    return _resolve_project_relative(project_root, candidate_rel)


def _pip_pipfile_direct_names(content):
    """The direct names a Pipfile declares: the keys of its `[packages]` and
    `[dev-packages]` tables (each only when it is a table). Content that is
    not valid TOML declares nothing."""
    data = _parse_toml(content)
    if data is None:
        return set()
    names = set()
    for table_name in ("packages", "dev-packages"):
        table = data.get(table_name)
        if isinstance(table, dict):
            names.update(table)
    return names


def _pip_direct_names_from_pyproject(manifest_file):
    """True when the direct names of a pip scan unit with this target come
    from pyproject.toml: the target is a pyproject.toml itself, or a lockfile
    whose declaration file is a pyproject.toml (poetry.lock). A requirements
    file or a Pipfile never does."""
    basename = os.path.basename(manifest_file)
    return _PIP_LOCKFILE_DECLARATIONS.get(basename, basename) == "pyproject.toml"


def _pip_direct_dependency_names(project_root, manifest_file):
    try:
        manifest_path = _pip_manifest_candidate(project_root, manifest_file)
    except (OSError, ValueError):
        manifest_path = None
    if _pip_direct_names_from_pyproject(manifest_file):
        return _pip_pyproject_direct_names(manifest_path)
    if not manifest_path:
        # The unit's manifest cannot be resolved inside the project root: its
        # declarations are unknown, so nothing may be assumed transitive.
        return DirectNames((), complete=False)
    if os.path.basename(manifest_path) != "Pipfile":
        # A requirements file is read by its own resolver, which follows
        # `-r` includes confined to the project root.
        return _pip_requirements_direct_names(manifest_path, project_root)
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, ValueError):
        return set()
    return _pip_pipfile_direct_names(content)


# ---------------------------------------------------------------------------
# pip lockfile audit (sca-python-lockfile-audit; IMPLEMENTATION.md C1, C3,
# C4, C5): a changed poetry.lock / Pipfile.lock is audited by turning its
# pins into exact `name==version` requirement lines handed to pip-audit, in
# a prepared file OUTSIDE the project root. The lockfile and its declaration
# file are authored by the change under review, so every read, parse or
# shape failure maps to a fixed skip reason or an entry exclusion -- nothing
# in this section raises for any file content (TM-4), and no text taken from
# either file enters the scan result.
# ---------------------------------------------------------------------------

PIP_LOCKFILE_UNCONVERTIBLE = "pip_lockfile_unconvertible"
PIP_DIRECT_MANIFEST_NOT_FOUND = "pip_direct_manifest_not_found"
# FR6: the unit's direct names come from pyproject.toml and tomllib is
# unavailable at call time.
PIP_TOML_PARSER_UNAVAILABLE = "pip_toml_parser_unavailable"

_PEP503_SEPARATORS_RE = re.compile(r"[-_.]+")


def canonical_pip_name(name):
    """C1: the PEP 503 form of a package name, for comparison,
    de-duplication and grouping -- lower-cased, every run of `-`, `_` and
    `.` replaced by a single `-`. Pure; tolerates any value (a non-string is
    compared through its text form, never raised on)."""
    return _PEP503_SEPARATORS_RE.sub("-", str(name)).lower()


def _parse_toml(text):
    """The parsed TOML table for `text`, or None when it cannot be parsed
    for ANY reason (no TOML parser on this interpreter, a syntax error,
    nesting beyond the parser's limit, ...)."""
    if tomllib is None:
        return None
    try:
        data = tomllib.loads(text)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _read_resolved_text(path):
    """The UTF-8 text of the regular file at `path` (an already-confined,
    fully resolved path), or None when it is not a regular file, cannot be
    read, or is not valid UTF-8."""
    try:
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as f:
            raw = f.read()
        return raw.decode("utf-8")
    except (OSError, ValueError):
        return None


def _read_project_text(project_root, rel_path):
    """The UTF-8 text of the project-relative file `rel_path`, read only
    when its resolved real path lies inside the project root (TM-3);
    otherwise, or on any read failure, None."""
    try:
        path = _resolve_project_relative(project_root, rel_path)
    except (OSError, ValueError):
        return None
    if path is None:
        return None
    return _read_resolved_text(path)


_PIP_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_PIP_NON_REGISTRY_SOURCE_TYPES = frozenset({"git", "directory", "file", "url"})
_PIPFILE_NON_REGISTRY_KEYS = ("git", "path", "file", "editable")


def _pip_pin_is_valid(name, version):
    """FR11: the only (name, version) pairs allowed into a prepared
    requirements file, each written as exactly ONE `name==version` line. The
    name must fully match the name pattern (`fullmatch`: a trailing line
    break does not slip through a `$`). The version must be non-empty,
    contain no whitespace of any kind (a line break would start a new line),
    no `;` (environment marker) and no `#` (comment), and not begin with `-`
    (an option). Beyond those rules, a version holding a backslash (a line
    continuation that would join the next line) or any non-printable
    character is not a version and is rejected the same way."""
    if not isinstance(name, str) or not isinstance(version, str):
        return False
    if _PIP_NAME_RE.fullmatch(name) is None:
        return False
    if not version or version.startswith("-"):
        return False
    return not any(
        ch.isspace() or not ch.isprintable() or ch in ";#\\" for ch in version
    )


def _pip_poetry_lock_pins(data):
    """(pins, excluded_count) for a parsed poetry.lock, or None when it has
    no top-level `package` array. Every array element is considered whatever
    its group or category (A3); an element that is not a table, whose
    `source` table names git / directory / file / url, or whose name or
    version fails FR11, is excluded and counted."""
    packages = data.get("package")
    if not isinstance(packages, list):
        return None
    pins = set()
    excluded = 0
    for entry in packages:
        if not isinstance(entry, dict):
            excluded += 1
            continue
        source = entry.get("source")
        source_type = source.get("type") if isinstance(source, dict) else None
        if isinstance(source_type, str) and source_type in _PIP_NON_REGISTRY_SOURCE_TYPES:
            excluded += 1
            continue
        name, version = entry.get("name"), entry.get("version")
        if not _pip_pin_is_valid(name, version):
            excluded += 1
            continue
        pins.add((canonical_pip_name(name), version))
    return pins, excluded


def _pip_pipfile_lock_pins(data):
    """(pins, excluded_count) for a parsed Pipfile.lock, or None when
    neither `default` nor `develop` is an object. Every entry of both is
    considered (A3), keyed by name; an entry that is not an object, carries
    git / path / file / editable, has a version that is not `==` followed by
    a non-empty remainder, or whose name or remainder fails FR11, is
    excluded and counted. The pin's version is the remainder after `==`.
    Other top-level keys (such as `_meta`) are ignored."""
    sections = [data[key] for key in ("default", "develop") if isinstance(data.get(key), dict)]
    if not sections:
        return None
    pins = set()
    excluded = 0
    for section in sections:
        for name, entry in section.items():
            if not isinstance(entry, dict) or any(k in entry for k in _PIPFILE_NON_REGISTRY_KEYS):
                excluded += 1
                continue
            spec = entry.get("version")
            version = spec[2:] if isinstance(spec, str) and spec.startswith("==") else None
            if not _pip_pin_is_valid(name, version):
                excluded += 1
                continue
            pins.add((canonical_pip_name(name), version))
    return pins, excluded


def _group_pip_pins(pins):
    """A5/D4: for each canonical name, its distinct versions in plain string
    order; the k-th version goes to group k, so no group holds a name twice.
    Groups are ordered 1..K and the lines inside a group are sorted."""
    versions_by_name = {}
    for name, version in pins:
        versions_by_name.setdefault(name, set()).add(version)
    groups = []
    for name in sorted(versions_by_name):
        for index, version in enumerate(sorted(versions_by_name[name])):
            if index == len(groups):
                groups.append([])
            groups[index].append(f"{name}=={version}")
    return [sorted(group) for group in groups]


def convert_pip_lockfile(project_root, lockfile):
    """C3: the lockfile's pins as auditable requirement groups. `lockfile` is
    a project-relative path whose basename is poetry.lock or Pipfile.lock.
    Returns exactly one of: None (unconvertible), or `(groups, excluded)` --
    an ordered list of one or more groups, each a sorted list of
    `canonical-name==version` lines in which each canonical name appears at
    most once, plus the number of excluded entries.

    Unconvertible: the file is absent, not a regular file, unreadable, not
    valid UTF-8, not valid TOML / JSON, parses in any other failing way
    (TM-4), resolves outside the project root (TM-3), lacks the expected
    structure, or leaves zero lines. Reads only that file; writes nothing;
    never raises for any file content; the same input gives the same
    output."""
    text = _read_project_text(project_root, lockfile)
    if text is None:
        return None
    basename = os.path.basename(lockfile)
    try:
        if basename == "poetry.lock":
            data = _parse_toml(text)
            collected = _pip_poetry_lock_pins(data) if data is not None else None
        elif basename == "Pipfile.lock":
            data = json.loads(text)
            collected = _pip_pipfile_lock_pins(data) if isinstance(data, dict) else None
        else:
            collected = None
    except Exception:
        # Untrusted content never raises out of `scan` (a JSON document
        # nested beyond the parser's limit raises RecursionError, an oversize
        # integer literal ValueError, ...): it is simply unconvertible.
        return None
    if collected is None:
        return None
    pins, excluded = collected
    if not pins:
        return None
    return _group_pip_pins(pins), excluded


def pip_declaration_found(project_root, lockfile):
    """C4: True when the lockfile's direct-dependency declaration file (the
    sibling pyproject.toml for poetry.lock, the sibling Pipfile for
    Pipfile.lock -- `_pip_manifest_candidate`) is present, a readable
    regular file inside the project root, valid UTF-8 and valid TOML.
    False ("not found") otherwise. Reads only; never raises. The
    pyproject.toml NAME extraction itself stays the existing parser."""
    try:
        candidate = _pip_manifest_candidate(project_root, lockfile)
    except (OSError, ValueError):
        return False
    if candidate is None:
        return False
    text = _read_resolved_text(candidate)
    return text is not None and _parse_toml(text) is not None


@contextlib.contextmanager
def prepared_requirements_files(groups):
    """C5: inside the scope there is one requirements file per group, in
    group order, holding exactly that group's lines, one per line. Each file
    is created exclusively by `tempfile.mkstemp` -- a unique, unpredictable
    name with owner-only access -- in the system temporary directory, which
    lies outside the project root (TM-6, A1). Yields the list of file paths.
    On scope exit, normal or exceptional, EVERY file created so far is
    removed (NFR1), including when creating a later file fails. The paths
    exist only for the pip-audit launch; none of them enters the scan
    result (NFR3)."""
    paths = []
    try:
        for group in groups:
            fd, path = tempfile.mkstemp(prefix="pip-lockfile-", suffix=".txt")
            paths.append(path)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write("".join(f"{line}\n" for line in group))
        yield list(paths)
    finally:
        for path in paths:
            try:
                os.unlink(path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# pip severity resolution (task0008 Design, "The pip normalizer's real
# input contract"): pip-audit's `--format json` output carries no
# per-advisory severity string either -- each vuln entry has only an
# identifier, fix versions, aliases and a description. The one piece of
# STRUCTURED severity metadata that description can actually carry is an
# embedded CVSS v3 vector string; when present, its band is computed with
# the SAME helper the cargo path already uses for cargo-audit's own CVSS
# vector (_cvss_severity_band). When no vector is present, severity is
# genuinely undeterminable from this output -- callers must not treat that
# as below threshold.
# ---------------------------------------------------------------------------

_CVSS_VECTOR_RE = re.compile(r"CVSS:3\.[01](?:/[A-Z]{1,3}:[A-Za-z])+")


def _pip_cvss_band(description):
    """The CVSS severity band (critical / high / medium / low / none) of
    the v3 vector embedded in `description`, or None when there is no
    vector or it cannot be scored."""
    if not isinstance(description, str):
        return None
    match = _CVSS_VECTOR_RE.search(description)
    if not match:
        return None
    return _cvss_severity_band(match.group(0))


def _pip_severity_from_description(ecosystem, description):
    """Returns the mapped severity (per this ecosystem's severity_map) when
    `description` embeds a CVSS v3 vector, else None -- "cannot be
    determined from that output" (task0008 Design), never a guess."""
    band = _pip_cvss_band(description)
    if band is None:
        return None
    return _map_severity(ecosystem, band)


def _pip_advisory_headline(description):
    """The natural-language sentence(s) preceding an embedded CVSS vector
    (or the whole description when none is present) -- used as the
    finding's advisory-short-title source so a raw CVSS vector string
    never appears in `title`."""
    if not isinstance(description, str):
        return None
    match = _CVSS_VECTOR_RE.search(description)
    headline = description[: match.start()] if match else description
    headline = headline.strip()
    return headline or None


def normalize_pip(ecosystem, data, manifest_file, project_root=None):
    """AC-5/6/7 (task0008): pip-audit's real `--format json` shape carries
    NEITHER a per-dependency directness flag NOR a per-advisory severity
    string. Directness is resolved from the reviewed manifest's own
    declared dependency set (_pip_direct_dependency_names) -- never read
    from a tool-supplied field, because none exists. Severity is taken
    from advisory metadata actually present in the output
    (_pip_severity_from_description); an advisory whose severity cannot be
    determined that way is NEVER silently treated as below threshold -- it
    is excluded from `findings` but counted (direct dependencies only,
    since a transitive one is dropped regardless of severity) and returned
    as `skip_info` for the caller to fold into the summary's affected count
    (NFR4: counts only, no advisory-sourced text).

    The declared set may be incomplete (a declaration that could not be
    resolved: an include leaving the project root, a URL or path
    requirement, an unreadable file, ...). IMPLEMENTATION.md D2 then
    decides an advisory for a package the set does not name: a severity
    that is known and below the threshold drops it uncounted; otherwise it
    is neither a finding nor transitive but counted once as undetermined
    directness, and in no other counter. With a complete set such an
    advisory is transitive and dropped. A resolver result without a
    `complete` attribute is treated as complete.

    Returns (findings, skip_info); skip_info is None when nothing was
    undetermined, otherwise a dict: `reason` (always
    `pip_severity_undetermined`) and `count` (the severity-undetermined
    count, possibly 0), plus `directness_undetermined` (the count above)
    only when it is not 0.

    For a pip lockfile `manifest_file` (sca-python-lockfile-audit FR10) the
    findings' `file` is the lockfile's project-relative path, directness is
    resolved from its sibling declaration file (`_pip_manifest_candidate`),
    and `affected_range` is the pinned version pip-audit reported."""
    findings = []
    declared = _pip_direct_dependency_names(project_root, manifest_file)
    complete = _names_complete(declared)
    # FR9: directness is decided on PEP 503 canonical names on BOTH sides, so
    # a declared `Django` / `Foo_Bar.baz` matches a reported `django` /
    # `foo-bar-baz` (every pip job, whatever its manifest).
    direct_names = {canonical_pip_name(name) for name in declared}
    directness_matters = (ecosystem.get("threshold") or {}).get("direct_only", True)
    undetermined_count = 0
    directness_undetermined_count = 0
    for dep in data.get("dependencies") or []:
        if not isinstance(dep, dict):
            continue
        package = dep.get("name", "unknown")
        is_direct = canonical_pip_name(package) in direct_names
        for vuln in dep.get("vulns") or []:
            if not isinstance(vuln, dict):
                continue
            description = vuln.get("description")
            mapped = _pip_severity_from_description(ecosystem, description)
            if directness_matters and not is_direct and not complete:
                # D2 step 4: a severity that is known (a CVSS band could be
                # scored) and below the threshold drops the advisory
                # uncounted; anything else is undetermined directness.
                band = _pip_cvss_band(description)
                if band is None or _passes_threshold(
                    ecosystem, True, _map_severity(ecosystem, band)
                ):
                    directness_undetermined_count += 1
                continue
            if mapped is None:
                if is_direct:
                    undetermined_count += 1
                continue
            if not _passes_threshold(ecosystem, is_direct, mapped):
                continue
            fix_versions = vuln.get("fix_versions") or []
            findings.append(
                _build_finding(
                    manifest_file=manifest_file,
                    package=package,
                    advisory_id=vuln.get("id", "UNKNOWN"),
                    title=_pip_advisory_headline(description) or vuln.get("id") or "vulnerability",
                    affected_range=dep.get("version"),
                    fixed_version=fix_versions[0] if fix_versions else None,
                    summary=description,
                    severity=mapped,
                )
            )
    skip_info = None
    if undetermined_count or directness_undetermined_count:
        skip_info = {"reason": "pip_severity_undetermined", "count": undetermined_count}
        if directness_undetermined_count:
            skip_info["directness_undetermined"] = directness_undetermined_count
    return findings, skip_info


# ---------------------------------------------------------------------------
# Go normalization (sca-go-govulncheck-real-output). `govulncheck -json`
# carries no per-finding directness and no severity string the registry can
# map, so both are resolved here: directness from the unit's own go.mod
# require entries (or the synthetic `stdlib` / `toolchain` modules), severity
# only from the OSV object's top-level CVSS v3 vectors. An advisory whose
# severity cannot be determined is counted, never treated as below threshold.
# ---------------------------------------------------------------------------

_GO_SYNTHETIC_DIRECT_MODULES = frozenset({"stdlib", "toolchain"})
_GO_SEVERITY_BANDS_DESCENDING = ("critical", "high", "medium", "low", "none")
_GO_CVSS_V3_PREFIXES = ("CVSS:3.0/", "CVSS:3.1/")
_GO_MOD_TOKEN_RE = re.compile(r'"[^"\n]*"|`[^`\n]*`|[()]|[^\s()"`]+|["`]')


def _go_mod_split_comment(line):
    """Splits one go.mod line into `(code, comment)` at the first `//` that
    is outside a double- or back-quoted string. `comment` is the text after
    the `//` (None when the line holds no comment)."""
    quote = None
    index = 0
    while index < len(line):
        char = line[index]
        if quote is not None:
            if char == quote:
                quote = None
        elif char in ('"', "`"):
            quote = char
        elif line.startswith("//", index):
            return line[:index], line[index + 2:]
        index += 1
    return line, None


def _go_mod_unquote(token):
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ('"', "`"):
        return token[1:-1]
    return token


def _go_mod_comment_marks_indirect(comment):
    """True only for the canonical indirect marker: the comment's words are
    exactly `indirect`, or `indirect;` followed by more words. A comment
    that merely contains the word leaves the entry direct."""
    if comment is None:
        return False
    words = comment.split()
    return words == ["indirect"] or (len(words) > 1 and words[0] == "indirect;")


def _go_mod_direct_modules(content):
    """The module paths of every `require` entry of go.mod `content` that is
    not marked indirect. Only the single-line `require m v` and the
    `require ( ... )` block forms contribute. Every other directive (single
    line or block, known or unknown), every full-line comment and every
    line that is not shaped like an entry contributes nothing -- malformed
    content just yields fewer entries."""
    direct = set()
    block = None  # None outside a block; "require" or "other" inside one
    for raw_line in content.split("\n"):
        code, comment = _go_mod_split_comment(raw_line.rstrip("\r"))
        tokens = _GO_MOD_TOKEN_RE.findall(code)
        if block is not None:
            if tokens == [")"]:
                block = None
            elif block == "require" and len(tokens) == 2:
                if not _go_mod_comment_marks_indirect(comment):
                    direct.add(_go_mod_unquote(tokens[0]))
            continue
        if not tokens:
            continue
        if len(tokens) == 2 and tokens[1] == "(":
            block = "require" if tokens[0] == "require" else "other"
        elif tokens[0] == "require" and len(tokens) == 3:
            if not _go_mod_comment_marks_indirect(comment):
                direct.add(_go_mod_unquote(tokens[1]))
    return direct


def _go_mod_relative_path(manifest_file):
    """The project-relative go.mod that decides directness for a unit whose
    target is `manifest_file`: the target itself when it is a go.mod, the
    go.mod beside it when it is a go.sum, otherwise None."""
    basename = os.path.basename(manifest_file)
    if basename == "go.mod":
        return manifest_file
    if basename == "go.sum":
        return os.path.join(os.path.dirname(manifest_file), "go.mod")
    return None


def _go_osv_severity_band(osv):
    """The highest qualitative band over the OSV object's top-level
    `severity` entries of type `CVSS_V3` whose score is a CVSS 3.0 / 3.1
    vector `_cvss_severity_band` can rate; None when there is none. Other
    types (CVSS_V4, ...), non-string scores and unparseable vectors are
    ignored, and `database_specific` is never read."""
    entries = osv.get("severity")
    if not isinstance(entries, list):
        return None
    best = None
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("type") != "CVSS_V3":
            continue
        score = entry.get("score")
        if not isinstance(score, str) or not score.startswith(_GO_CVSS_V3_PREFIXES):
            continue
        band = _cvss_severity_band(score)
        if band is None:
            continue
        if best is None or (
            _GO_SEVERITY_BANDS_DESCENDING.index(band)
            < _GO_SEVERITY_BANDS_DESCENDING.index(best)
        ):
            best = band
    return best


def _go_fixed_version(osv, module):
    """The fixed version from the OSV `affected` entries whose
    `package.name` equals `module` (the last fixed event wins); None when no
    such entry carries one. Other modules' entries are never consulted."""
    fixed_version = None
    affected_entries = osv.get("affected")
    for affected in affected_entries if isinstance(affected_entries, list) else []:
        package = affected.get("package") if isinstance(affected, dict) else None
        if not isinstance(package, dict) or package.get("name") != module:
            continue
        ranges = affected.get("ranges")
        for rng in ranges if isinstance(ranges, list) else []:
            events = rng.get("events") if isinstance(rng, dict) else None
            for event in events if isinstance(events, list) else []:
                if isinstance(event, dict) and isinstance(event.get("fixed"), str):
                    fixed_version = event["fixed"]
    return fixed_version


def normalize_go(ecosystem, data, manifest_file, project_root=None):
    """Turns one completed Go unit payload (the object list
    `judge_scan_outcome` hands on) into `(findings, undetermined, reason)`.

    The unit's go.mod (the target itself, or the go.mod beside a go.sum
    target) is read through the project-relative confinement as a regular
    UTF-8 file; any failure returns `([], 0, "go_direct_manifest_unreadable")`
    -- never a fallback to an empty direct set. Nothing is written.

    The stream is reduced to one advisory per (OSV id, module). An advisory
    is direct when its module is a non-indirect require entry of that go.mod
    or the synthetic `stdlib` / `toolchain` module; a non-direct advisory is
    neither a finding nor counted. A direct advisory with no CVSS v3 band is
    undetermined: counted in `undetermined`, never a finding. A direct
    advisory with a band is mapped through the registry and the threshold
    rule, which drops it silently when below high."""
    gomod_path = _go_mod_relative_path(manifest_file)
    content = _read_project_text(project_root, gomod_path) if gomod_path else None
    if content is None:
        return [], 0, GO_DIRECT_MANIFEST_UNREADABLE
    direct_modules = _go_mod_direct_modules(content)
    findings = []
    undetermined = 0
    for advisory in _merge_govulncheck_stream(data):
        module = advisory["module"]
        if module not in direct_modules and module not in _GO_SYNTHETIC_DIRECT_MODULES:
            continue
        osv = advisory["osv"]
        band = _go_osv_severity_band(osv)
        if band is None:
            undetermined += 1
            continue
        mapped = _map_severity(ecosystem, band)
        if not _passes_threshold(ecosystem, True, mapped):
            continue
        findings.append(
            _build_finding(
                manifest_file=manifest_file,
                package=module,
                advisory_id=advisory["id"],
                title=osv.get("summary") or advisory["id"],
                affected_range=None,
                fixed_version=_go_fixed_version(osv, module),
                summary=osv.get("details"),
                severity=mapped,
            )
        )
    return findings, undetermined, None


NORMALIZERS = {
    "npm": normalize_npm,
    "cargo": normalize_cargo,
    "pip": normalize_pip,
    "go": normalize_go,
}


def _empty_result():
    return {
        "findings": [],
        "summary": "No dependency manifests recognised by the registry in this change.",
        "skipped": False,
        "skip_reason": None,
        "source": "tool",
    }


def _skip_result(skip_reason, summary, findings=None):
    """`findings` defaults to empty (the no-ecosystem-ran / unsupported-
    manifest skips), but the partial-coverage case (task plan Design)
    passes the completed ecosystems' findings through explicitly -- a skip
    about one ecosystem never suppresses another's advisories."""
    return {
        "findings": findings if findings is not None else [],
        "summary": summary,
        "skipped": True,
        "skip_reason": skip_reason,
        "source": "tool",
    }


def _findings_result(findings, summary):
    return {
        "findings": findings,
        "summary": summary,
        "skipped": False,
        "skip_reason": None,
        "source": "tool",
    }


def _scan_pip_lockfile(ecosystem, lockfile, project_root, executable_path):
    """The pip axis for a changed poetry.lock / Pipfile.lock
    (sca-python-lockfile-audit "Scan flow for pip", steps 3-7). The tool is
    already validated and resolved. Returns a dict:

    - `reasons`: the not-completed reasons, de-duplicated, in first-seen
      order (an unconvertible lockfile, a declaration file that cannot be
      resolved, or the reasons of runs that did not complete -- D5).
    - `findings`: the completed runs' findings, in run order.
    - `undetermined`: the undetermined-severity count summed over runs.
    - `directness_undetermined`: the undetermined-directness count summed
      over runs.
    - `excluded`: the number of lockfile entries left out of conversion --
      0 unless at least one run was launched (D3).
    - `completed`: True when at least one run completed.

    Conversion comes first, then the declaration check, and pip-audit is
    launched only after both pass (A4): a lockfile that cannot be converted
    or whose declaration file cannot be resolved launches nothing and never
    falls back to a manifest or directory audit (FR5, FR8, TM-2). One run
    per group of the prepared-file scope (FR4); the scope removes every
    prepared file on exit, normal or exceptional (NFR1). An exception from
    the execution step propagates -- only untrusted FILE CONTENT is
    contained."""
    audit = {
        "reasons": [],
        "findings": [],
        "undetermined": 0,
        "directness_undetermined": 0,
        "excluded": 0,
        "completed": False,
    }
    converted = convert_pip_lockfile(project_root, lockfile)
    if converted is None:
        audit["reasons"].append(PIP_LOCKFILE_UNCONVERTIBLE)
        return audit
    groups, excluded = converted
    if not pip_declaration_found(project_root, lockfile):
        audit["reasons"].append(PIP_DIRECT_MANIFEST_NOT_FOUND)
        return audit
    # FR6 / D4: after every check above, before anything is launched.
    if _pip_direct_names_from_pyproject(lockfile) and tomllib is None:
        audit["reasons"].append(PIP_TOML_PARSER_UNAVAILABLE)
        return audit

    audit["excluded"] = excluded
    normalizer = NORMALIZERS.get("pip")
    with prepared_requirements_files(groups) as prepared_files:
        for prepared_file in prepared_files:
            job = build_scan_job(
                ecosystem, lockfile, project_root, executable_path, prepared_file=prepared_file
            )
            outcome, payload = run_ecosystem_command(job)
            reason = payload if outcome == OUTCOME_NOT_COMPLETED else None
            if reason is None and normalizer is None:
                reason = "pip_no_normalizer"
            if reason is not None:
                if reason not in audit["reasons"]:
                    audit["reasons"].append(reason)
                continue
            findings, skip_info = normalizer(ecosystem, payload, lockfile, project_root)
            audit["findings"].extend(findings)
            if skip_info:
                audit["undetermined"] += skip_info["count"]
                audit["directness_undetermined"] += skip_info.get("directness_undetermined", 0)
            audit["completed"] = True
    return audit


# ---------------------------------------------------------------------------
# Per-project grouping and binding (sca-per-project-scan-binding). One scan
# unit per (ecosystem, project directory): the changed files of an ecosystem
# are grouped by the REAL directory that holds them, and an npm / cargo / go
# group is scanned only for a directory that passes the binding check.
# The grouping and binding helpers read path metadata only -- they never
# write, never launch, and never fall back to the project root or an ancestor
# directory. An exception raised while resolving or inspecting a reviewed
# path is contained and turned into that ecosystem's path-free reason
# (`<ecosystem>_project_unbindable`); it never escapes `scan`. A group that
# passed the binding check is then scanned by `_scan_bound_group`: go from its
# project directory, npm and cargo from a per-group isolation directory
# (`isolation_workspace`, below) outside the reviewed tree. The workspace is
# the one writer in this section, and it writes only under the system
# temporary area.
# ---------------------------------------------------------------------------

# Per ecosystem: the anchor lockfile names in preference order (npm: an
# npm-shrinkwrap.json entry, when present, wins and never falls back to
# package-lock.json) and the manifest the project must hold beside it.
# yarn.lock and pnpm-lock.yaml still SELECT npm but never serve as an anchor.
_BINDING_ANCHORS = {
    "npm": ("npm-shrinkwrap.json", "package-lock.json"),
    "cargo": ("Cargo.lock",),
    "go": ("go.mod",),
}
_BINDING_MANIFESTS = {"npm": "package.json", "cargo": "Cargo.toml", "go": "go.mod"}


def _verified_real_root(project_root):
    """The real path of the project root, or None when it cannot be
    resolved (every verification then fails)."""
    try:
        return os.path.realpath(str(project_root))
    except Exception:
        return None


def _verified_inside(real_root, real_path):
    """True when `real_path` equals `real_root` or lies under it (both
    already real paths)."""
    prefix = real_root.rstrip(os.sep) + os.sep
    return real_path == real_root or real_path.startswith(prefix)


def _verified_directory(real_root, changed_file, confine_file):
    """The group key D of one changed file: its containing directory's real
    path relative to the real project root, `/`-separated, `""` for the
    root -- so every spelling of one directory (duplicate segments, `.`, an
    inside `..`, a symlinked alias) yields the same D. None when the file
    cannot be verified: it is not a non-empty string, is absolute, contains
    NUL, resolving it raises, or a real path leaves the project root.

    `confine_file` (npm / cargo / go, FR5) also requires the file's OWN real
    path to lie inside the root; pip (D3) resolves only the containing
    directory, because pip keeps its own existing validation and no pip path
    is ever rejected -- an unverifiable pip path just keeps its raw
    directory part as its key."""
    try:
        if real_root is None or not isinstance(changed_file, str) or not changed_file:
            return None
        if "\x00" in changed_file or os.path.isabs(changed_file):
            return None
        directory_real = os.path.realpath(
            os.path.join(real_root, os.path.dirname(changed_file) or ".")
        )
        if not _verified_inside(real_root, directory_real):
            return None
        if confine_file:
            file_real = os.path.realpath(os.path.join(real_root, changed_file))
            if not _verified_inside(real_root, file_real):
                return None
        relative = os.path.relpath(directory_real, real_root)
        if relative == os.curdir:
            return ""
        return relative.replace(os.sep, "/")
    except Exception:
        return None


def _verified_groups(name, ecosystem, changed_files, real_root):
    """Groups one ecosystem's changed files (basename among its manifests or
    its lockfiles, input order kept inside each group) by project directory
    (FR1, FR10). Returns `(groups, rejected)`: `groups` is a list of
    `(directory, files)` in Group order -- ascending plain-string order of
    the directory, the root `""` first -- and `rejected` is True when an
    npm / cargo / go changed file failed verification (it joins no group,
    A-10). pip never rejects: a file whose directory cannot be verified is
    grouped under its raw directory part, kept apart from every verified
    key."""
    manifests = set(ecosystem.get("manifests") or [])
    relevant = manifests | ECOSYSTEM_LOCKFILES.get(name, set())
    pip = name == "pip"
    grouped = {}
    rejected = False
    for changed in changed_files:
        if os.path.basename(changed) not in relevant:
            continue
        directory = _verified_directory(real_root, changed, confine_file=not pip)
        if directory is not None:
            key = (directory, 1)
        elif pip:
            key = (os.path.dirname(changed), 0)
        else:
            rejected = True
            continue
        grouped.setdefault(key, []).append(changed)
    return [(key[0], grouped[key]) for key in sorted(grouped)], rejected


def _binding_source(project_dir, file_name):
    """The real path of `file_name` inside `project_dir` (a real path) when it
    resolves to a regular file whose real containing directory is
    `project_dir` itself, otherwise None: a symlink to another file of the
    same directory is fine, one resolving into any other directory is not,
    and neither is a directory, a dangling link or a special file."""
    real = os.path.realpath(os.path.join(project_dir, file_name))
    if os.path.dirname(real) == project_dir and os.path.isfile(real):
        return real
    return None


def _binding_file_in_directory(project_dir, file_name):
    """True when `_binding_source` accepts `file_name` inside `project_dir`."""
    return _binding_source(project_dir, file_name) is not None


def _binding_project_dir(real_root, directory):
    """The real project directory of group key `directory` (D): the real
    project root for the root group `""`, otherwise the real path of D below
    it."""
    return os.path.realpath(os.path.join(real_root, directory)) if directory else real_root


def _binding_anchor_name(name, project_dir):
    """The anchor lockfile name of an npm / cargo / go project in
    `project_dir` (a real path): for npm an `npm-shrinkwrap.json` entry, when
    present, wins and never falls back to `package-lock.json`."""
    anchors = _BINDING_ANCHORS[name]
    if name == "npm" and os.path.lexists(os.path.join(project_dir, anchors[0])):
        return anchors[0]  # an invalid shrinkwrap never falls back to package-lock.json
    return anchors[-1]


def _binding_check(name, real_root, directory, target_basename):
    """True when the npm / cargo / go group in `directory` (D) can be bound
    (FR4, FR5): the real project directory exists, is a directory and lies
    inside the real project root; its anchor and its required manifest are
    each a regular file of that very directory; and the selected target
    (`target_basename`) is one too -- a deleted target is unbindable. Any
    exception means unbindable. There is no fallback to the root or an
    ancestor directory."""
    try:
        if real_root is None:
            return False
        project_dir = _binding_project_dir(real_root, directory)
        if not _verified_inside(real_root, project_dir) or not os.path.isdir(project_dir):
            return False
        anchor = _binding_anchor_name(name, project_dir)
        for file_name in (anchor, _BINDING_MANIFESTS[name], target_basename):
            if not _binding_file_in_directory(project_dir, file_name):
                return False
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Isolation workspace (sca-scanner-project-config-isolation). npm and cargo
# find project-level configuration (`.npmrc`, `.cargo/audit.toml`) by walking
# from their working directory, so a scan group that passed the binding check
# is run from a newly created directory OUTSIDE the reviewed tree that holds
# only copies of its validated inputs. The directory exists for exactly one
# group and is removed on every exit path. Nothing is created or written
# under the real project root (NFR2), and a failure of any step is an
# isolation failure -- the scanner is never launched and never falls back to
# running inside the tree. A failure carries no path (NFR3).
# ---------------------------------------------------------------------------

ISOLATION_DIRECTORY_PREFIX = "sca-isolation-"


class IsolationError(Exception):
    """Creating, validating or filling an isolation directory failed. A fixed
    signal: it is raised with no argument and chains no cause, so neither a
    path nor filesystem exception text can travel with it (NFR3)."""


def _isolation_temp_parent(real_root):
    """The real path of the temporary directory the standard selection
    (`tempfile.gettempdir`: the process-wide `tempfile.tempdir`, else
    `TMPDIR` / `TEMP` / `TMP`) uses in this process. Raises IsolationError
    when it equals the real project root or lies under it (FR6).

    The environment candidates are checked BEFORE the standard selection
    runs: it probes a candidate by creating and removing a file there, which
    must never happen inside the reviewed tree (NFR2). Candidates are
    compared in the standard order and the first usable one ends the check,
    as the selection itself would use it. Containment is decided on real
    paths by path components."""
    if tempfile.tempdir is None:
        for key in ("TMPDIR", "TEMP", "TMP"):
            candidate = os.environ.get(key)
            if not candidate:
                continue
            real = os.path.realpath(candidate)
            if _verified_inside(real_root, real):
                raise IsolationError()
            if os.path.isdir(real) and os.access(real, os.W_OK | os.X_OK):
                break
    parent = os.path.realpath(tempfile.gettempdir())
    if _verified_inside(real_root, parent):
        raise IsolationError()
    return parent


def _isolation_sources(name, project_dir):
    """The inputs to copy for an npm / cargo group in `project_dir`, as
    `(role, file name)` pairs in copy order: npm's manifest then its selected
    anchor (`npm-shrinkwrap.json` preferred over `package-lock.json`), cargo's
    `Cargo.lock`. The names are the binding check's own."""
    anchor = _binding_anchor_name(name, project_dir)
    if name == "npm":
        return [(ROLE_MANIFEST, _BINDING_MANIFESTS["npm"]), (ROLE_ANCHOR, anchor)]
    if name == "cargo":
        return [(ROLE_LOCKFILE, anchor)]
    raise IsolationError()


def _copy_input(source, destination):
    """Writes the content of the regular file `source` (a real path) as a NEW
    regular file `destination`, owner-only (mode 0o600), failing when
    `destination` already exists. Only content is copied: no mode, owner or
    link. Raises OSError on any failure."""
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(source, os.O_RDONLY | nofollow | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as reader:
        if not stat.S_ISREG(os.fstat(reader.fileno()).st_mode):
            raise OSError("not a regular file")
        content = reader.read()
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow, 0o600)
    with os.fdopen(fd, "wb") as writer:
        writer.write(content)


def _remove_tree(path):
    """Removes the directory tree at `path` recursively, including files a
    scanner left in it. A tree a scanner made unwritable is made removable
    and removed again. Never raises and never reports a path: a removal that
    still fails leaves the scan's recorded outcome as it was."""
    for attempt in range(2):
        try:
            shutil.rmtree(path)
        except Exception:
            pass
        if not os.path.lexists(path):
            return
        if attempt == 0:
            _make_tree_removable(path)


def _make_tree_removable(path):
    """Restores owner access on every directory below `path` (links are never
    followed), so a second removal can delete what a scanner locked."""
    try:
        if not stat.S_ISDIR(os.lstat(path).st_mode):
            return
        os.chmod(path, 0o700)
        names = os.listdir(path)
    except OSError:
        return
    for entry in names:
        _make_tree_removable(os.path.join(path, entry))


@contextlib.contextmanager
def isolation_workspace(name, real_root, project_dir):
    """A scoped isolation directory for ONE npm / cargo scan group of the
    project directory `project_dir` (a real path inside `real_root`, the real
    project root). Yields a `PreparedInputs`. On entry:

    1. the temp parent is resolved and must lie outside the real project root
       (`_isolation_temp_parent`);
    2. one new, uniquely named directory is created under that same parent,
       owner-only from the moment of creation (`tempfile.mkdtemp` makes it
       mode 0o700 -- no window for group or other);
    3. its own real path must lie outside the real project root;
    4. each input is re-validated with the binding check's own rule
       (`_binding_source`) and copied by content as a new regular file under
       its own file name (an allowed same-directory symlink contributes its
       target's content); nothing else is copied.

    Any failure removes what was created and raises IsolationError, with no
    path. On exit -- normal, a failed or timed-out scan, an error in the body
    or a KeyboardInterrupt -- the directory is removed recursively, scanner
    leftovers included (`_remove_tree`)."""
    created = None
    try:
        try:
            parent = _isolation_temp_parent(real_root)
            created = tempfile.mkdtemp(prefix=ISOLATION_DIRECTORY_PREFIX, dir=parent)
            directory = os.path.realpath(created)
            if _verified_inside(real_root, directory):
                raise IsolationError()
            if not _verified_inside(real_root, project_dir) or not os.path.isdir(project_dir):
                raise IsolationError()
            files = {}
            for role, file_name in _isolation_sources(name, project_dir):
                source = _binding_source(project_dir, file_name)
                if source is None:
                    raise IsolationError()
                destination = os.path.join(directory, file_name)
                _copy_input(source, destination)
                files[role] = destination
            prepared = PreparedInputs(directory=directory, files=files)
        except IsolationError:
            raise
        except Exception:
            raise IsolationError() from None
        yield prepared
    finally:
        if created is not None:
            _remove_tree(created)


def _group_audit(reasons=(), findings=(), completed=False, undetermined=0):
    return {
        "reasons": list(reasons),
        "findings": list(findings),
        "completed": completed,
        "undetermined": undetermined,
    }


def _scan_bound_group(plan, project_root):
    """One npm / cargo / go scan unit: the `ScanPlan` of one group of changed
    files in project directory `plan.directory` (D). The target and the
    findings' `file` label are the plan's `target` -- it follows the Target
    convention (the basename of the file manifest_file_for selected from the
    group, prefixed by D unless D is the root) and is never selected again
    here. The plan is not a verdict: the binding check runs here, against the
    plan's directory and the basename of the plan's target, immediately before
    isolation and launch. A group that fails the binding check launches
    nothing and reports `<ecosystem>_project_unbindable` (and no isolation
    directory is created for it); otherwise its outcome is judged and
    normalized as before. A Go unit's normalizer gets the project root, like
    the cargo one, and may return a not-completed reason
    (`go_direct_manifest_unreadable`): that becomes the unit's only reason,
    with no findings and no undetermined count. Returns `_group_audit` (its
    `undetermined` is the unit's Go undetermined-severity count, 0 for every
    other ecosystem).

    go runs in D. npm and cargo run from a per-group isolation directory
    outside the reviewed tree (`isolation_workspace`), which this function
    owns end to end: it prepares the directory for the group's validated
    inputs after the binding check, builds the job from the prepared paths,
    runs it through run_ecosystem_command with the job's cwd, and removes the
    directory on every path (success, tool failure, timeout, an error while
    copying). When the isolation fails -- creating, validating or filling the
    directory -- the scanner is NOT launched, nothing is retried inside the
    tree, and the unit reports `npm_isolation_failed` /
    `cargo_isolation_failed` (fixed tokens, no path, no exception text);
    the caller goes on with the remaining groups. The cargo
    direct-dependency judgment still reads the ORIGINAL Cargo.toml in the
    reviewed tree."""
    ecosystem = plan.ecosystem
    name = ecosystem.get("ecosystem", "unknown")
    directory = plan.directory
    real_root = plan.real_root
    target = plan.target
    executable_path = plan.executable
    unbindable = _group_audit(reasons=[f"{name}_project_unbindable"])
    if not _binding_check(name, real_root, directory, os.path.basename(target)):
        return unbindable
    if name in ISOLATION_ECOSYSTEMS:
        project_dir = _binding_project_dir(real_root, directory)
        try:
            with isolation_workspace(name, real_root, project_dir) as prepared:
                try:
                    job = build_scan_job(
                        ecosystem, target, project_root, executable_path,
                        prepared_inputs=prepared,
                    )
                except JobConstructionError:
                    return unbindable
                if name == "cargo" and tomllib is None:
                    # FR6: the unit's directness comes from Cargo.toml, which
                    # cannot be parsed here -- the scanner is not launched.
                    return _group_audit(reasons=[CARGO_TOML_PARSER_UNAVAILABLE])
                outcome, payload = run_ecosystem_command(job)
        except IsolationError:
            return _group_audit(reasons=[f"{name}_isolation_failed"])
    else:
        try:
            job = build_scan_job(ecosystem, target, project_root, executable_path)
        except JobConstructionError:
            return unbindable
        outcome, payload = run_ecosystem_command(job)
    if outcome == OUTCOME_NOT_COMPLETED:
        return _group_audit(reasons=[payload])
    normalizer = NORMALIZERS.get(name)
    if normalizer is None:
        return _group_audit(reasons=[f"{name}_no_normalizer"])
    if name == "go":
        findings, undetermined, reason = normalizer(ecosystem, payload, target, project_root)
        if reason is not None:
            return _group_audit(reasons=[reason])
        return _group_audit(findings=findings, completed=True, undetermined=undetermined)
    if name == "cargo":
        findings, directness_undetermined = normalizer(ecosystem, payload, target, project_root)
        audit = _group_audit(findings=findings, completed=True)
        audit["directness_undetermined"] = directness_undetermined
        return audit
    findings = normalizer(ecosystem, payload, target)
    return _group_audit(findings=findings, completed=True)


def _scan_pip_group(plan, project_root):
    """One pip scan unit (FR10): the `ScanPlan`'s target is the raw file
    manifest_file_for selected over the group's raw files, lockfile first --
    it is never selected again here. A lockfile target goes through the
    existing lockfile audit; any other target through the existing job
    (cwd = the project root) and normalizer. Returns `_group_audit` plus
    `undetermined`, `directness_undetermined` and `excluded` counts."""
    ecosystem = plan.ecosystem
    executable_path = plan.executable
    name = ecosystem.get("ecosystem", "unknown")
    manifest_file = plan.target
    if os.path.basename(manifest_file) in ECOSYSTEM_LOCKFILES["pip"]:
        audit = _scan_pip_lockfile(ecosystem, manifest_file, project_root, executable_path)
        result = _group_audit(audit["reasons"], audit["findings"], audit["completed"])
        result["undetermined"] = audit["undetermined"]
        result["directness_undetermined"] = audit["directness_undetermined"]
        result["excluded"] = audit["excluded"]
        return result
    result = _group_audit()
    result["undetermined"] = 0
    result["directness_undetermined"] = 0
    result["excluded"] = 0
    # FR6 / D4: a unit whose direct names come from pyproject.toml cannot be
    # judged without the TOML parser -- it does not complete and pip-audit is
    # not started. A requirements-file unit never takes this skip.
    if _pip_direct_names_from_pyproject(manifest_file) and tomllib is None:
        result["reasons"].append(PIP_TOML_PARSER_UNAVAILABLE)
        return result
    job = build_scan_job(ecosystem, manifest_file, project_root, executable_path)
    outcome, payload = run_ecosystem_command(job)
    if outcome == OUTCOME_NOT_COMPLETED:
        result["reasons"].append(payload)
        return result
    normalizer = NORMALIZERS.get(name)
    if normalizer is None:
        result["reasons"].append(f"{name}_no_normalizer")
        return result
    # task0008 AC-7: an advisory whose severity cannot be determined from
    # pip-audit's own output is never silently treated as below threshold.
    # It is deliberately NOT folded into the reasons -- they drive the whole
    # object's `skipped` boolean, which run_scan's contract defines as
    # meaning ONLY "did every selected ecosystem complete"; pip DID complete
    # here, so this normalization-time ambiguity is surfaced as a counts-only
    # summary note instead (no advisory-sourced text -- NFR4).
    pip_findings, pip_skip = normalizer(ecosystem, payload, manifest_file, project_root)
    result["findings"].extend(pip_findings)
    if pip_skip:
        result["undetermined"] += pip_skip["count"]
        result["directness_undetermined"] += pip_skip.get("directness_undetermined", 0)
    result["completed"] = True
    return result


def _undetermined_directness_notes(pip_count, cargo_count):
    """The FR5 summary notes for the advisories whose directness could not be
    decided: the pip note (when `pip_count` is above 0) followed by the cargo
    note (when `cargo_count` is above 0), each with its leading space and
    `advisory` / `advisories` by count; empty when both are 0. Counts only --
    never a name, a path or advisory text (NFR4)."""
    notes = ""
    for ecosystem, count in (("pip", pip_count), ("cargo", cargo_count)):
        if count > 0:
            noun = "advisory" if count == 1 else "advisories"
            notes += (
                f" {count} {ecosystem} {noun} with undetermined directness "
                f"({ecosystem}_directness_undetermined)."
            )
    return notes


def run_scan(project_root, changed_files, registry_path):
    """AC-1..AC-7 (task0001) plus this task's partial-coverage contract,
    sca-per-project-scan-binding and sca-scanner-project-config-isolation:
    select ecosystems, plan the scan once (`build_scan_jobs`: validate and
    resolve each ecosystem, group its changed files by project directory,
    select each group's target), execute one scan job per plan, in plan order,
    and judge the ONE outcome that execution yields
    (`judge_scan_outcome`), normalize completed payloads with a threshold
    applied at normalization time, and emit exactly one
    review-output-schema.json-conformant object. A plan never selects a target
    twice and never replaces the run-side checks: planning every ecosystem
    before the first launch widens the time between grouping and launch, so
    each group's binding check still runs immediately before its isolation
    directory and launch.

    - No manifest in the change: an empty, non-skipped result.
    - A selected ecosystem's validation fails or its executable is not
      resolvable on PATH: `build_scan_jobs` gives that ecosystem's reason
      ONCE and no plan, so nothing below runs for it -- no path verification,
      no binding check, no launch, no fallback of any kind (FR9).
    - npm / cargo / go: one scan unit per verified project directory (FR1),
      labelled with its own manifest path (FR2, FR3). go is launched inside
      that directory. npm and cargo are launched from a per-group isolation
      directory outside the reviewed tree that holds only copies of the
      group's validated inputs, so the reviewed project's own `.npmrc` /
      `.cargo/audit.toml` are not on the scanner's discovery path
      (`_scan_bound_group` prepares and removes it). A project that cannot
      be bound -- no anchor lockfile, no required manifest, a path or
      symlink escaping the project root, a deleted target, an absent
      directory -- launches nothing and reports
      `<ecosystem>_project_unbindable`; a changed file that fails path
      verification joins no group and reports the same reason (FR4, FR5,
      FR6). Nothing falls back to the root or an ancestor.
    - An npm / cargo group whose isolation directory cannot be created,
      validated or filled -- including a temp parent that is, or resolves
      into, the reviewed tree -- launches nothing, never falls back to
      running inside the tree, and reports `npm_isolation_failed` /
      `cargo_isolation_failed`: fixed tokens, never a path. The remaining
      groups are still scanned and the completed groups' findings stay in
      the result; the reason enters `skip_reason` like any other.
    - pip: grouped per project directory too, each group audited by the
      existing rules from the project root (FR10).
    - `skipped` is `true` exactly when ANY unit did not complete (tool
      absent, validation failure, unbindable project, or an execution
      outcome of `not_completed`), with `skip_reason` carrying every such
      reason de-duplicated, sorted and joined with "+" (FR7, FR8) -- fixed
      tokens only, never path text (NFR3). `findings` still carries
      everything the COMPLETED groups produced, in processing order -- a
      skip about one group never suppresses another's advisories (task plan
      Design, "Partial coverage is machine-readable, not prose").
      `skipped: false` with `skip_reason: null` therefore means, and only
      means, that every selected unit completed. The summary names each
      scanned ecosystem once.
    - pip, when a group holds a poetry.lock / Pipfile.lock, audits that
      lockfile's own pins (`_scan_pip_lockfile`): its reasons travel the
      same path, and the findings carry the lockfile as `file`.
    - pip, when tomllib is unavailable at call time: a unit whose direct
      names come from pyproject.toml (the pyproject.toml unit itself, or a
      poetry.lock unit that passed the lockfile checks) is not scanned and
      reports `pip_toml_parser_unavailable`; a requirements-file unit never
      does (FR6).
    - go: the Go normalizer returns, per unit, its findings, an
      undetermined-severity count and an optional not-completed reason
      (`go_direct_manifest_unreadable`). The counts are summed over every
      Go unit; a non-zero sum appends the counts-only note
      `N go advisory|advisories with undetermined severity
      (go_severity_undetermined).` after the pip notes. It is a note, never
      a skip reason.
    - directness: each pip / cargo unit reports `directness_undetermined`,
      the number of advisories it could not classify as direct or transitive
      (absent means 0). The counts are summed per ecosystem and
      `_undetermined_directness_notes` appends the counts-only notes after
      every pre-existing note, pip before cargo. They are notes, never skip
      reasons. A cargo unit whose Cargo.toml cannot be parsed because tomllib
      is unavailable reports `cargo_toml_parser_unavailable` instead.
    """
    registry = load_registry(registry_path)
    selected = select_ecosystems(registry, changed_files)
    if not selected:
        unsupported = unsupported_manifest_reasons(changed_files)
        if unsupported:
            combined_reason = "+".join(unsupported)
            summary = "Scan skipped: " + "; ".join(unsupported)
            return _skip_result(combined_reason, summary)
        return _empty_result()

    plans, plan_reasons = build_scan_jobs(registry, changed_files, project_root)
    all_findings = []
    skip_reasons = set(plan_reasons)
    ran_ecosystems = set()
    pip_severity_undetermined_total = 0
    pip_unpinnable_total = 0
    go_severity_undetermined_total = 0
    pip_directness_undetermined_total = 0
    cargo_directness_undetermined_total = 0
    for plan in plans:
        name = plan.ecosystem.get("ecosystem", "unknown")
        if name == "pip":
            audit = _scan_pip_group(plan, project_root)
            pip_severity_undetermined_total += audit["undetermined"]
            pip_unpinnable_total += audit["excluded"]
            pip_directness_undetermined_total += audit.get("directness_undetermined", 0)
        else:
            audit = _scan_bound_group(plan, project_root)
            if name == "go":
                go_severity_undetermined_total += audit["undetermined"]
            if name == "cargo":
                cargo_directness_undetermined_total += audit.get("directness_undetermined", 0)
        all_findings.extend(audit["findings"])
        skip_reasons.update(audit["reasons"])
        if audit["completed"]:
            ran_ecosystems.add(name)

    undetermined_note = ""
    if pip_severity_undetermined_total:
        noun = "advisory" if pip_severity_undetermined_total == 1 else "advisories"
        undetermined_note = (
            f" {pip_severity_undetermined_total} pip {noun} with undetermined "
            f"severity (pip_severity_undetermined)."
        )

    # D3: counts only, never lockfile text; after the undetermined-severity
    # note. Present only when a pip run was launched for the lockfile and
    # at least one entry was excluded from conversion.
    unpinnable_note = ""
    if pip_unpinnable_total == 1:
        unpinnable_note = " 1 pip lockfile entry not auditable (pip_lockfile_entries_unpinnable)."
    elif pip_unpinnable_total > 1:
        unpinnable_note = (
            f" {pip_unpinnable_total} pip lockfile entries not auditable "
            f"(pip_lockfile_entries_unpinnable)."
        )
    # Counts only, never advisory text; after the pip notes. A note, never a
    # skip reason: `skipped` keeps meaning only "every selected unit
    # completed".
    go_undetermined_note = ""
    if go_severity_undetermined_total:
        noun = "advisory" if go_severity_undetermined_total == 1 else "advisories"
        go_undetermined_note = (
            f" {go_severity_undetermined_total} go {noun} with undetermined "
            f"severity (go_severity_undetermined)."
        )
    # D3: the directness notes come after every pre-existing note, pip before
    # cargo; counts only, and never a skip reason.
    summary_notes = (
        undetermined_note
        + unpinnable_note
        + go_undetermined_note
        + _undetermined_directness_notes(
            pip_directness_undetermined_total, cargo_directness_undetermined_total
        )
    )

    if skip_reasons:
        ordered_reasons = sorted(skip_reasons)
        combined_reason = "+".join(ordered_reasons)
        if ran_ecosystems:
            summary = (
                f"Scanned {', '.join(sorted(ran_ecosystems))}; "
                f"{len(all_findings)} finding(s) at or above threshold. "
                f"Not completed: {', '.join(ordered_reasons)}."
            )
        else:
            summary = "Scan skipped: " + "; ".join(ordered_reasons)
        summary += summary_notes
        return _skip_result(combined_reason, summary, findings=all_findings)

    summary = f"Scanned {', '.join(sorted(ran_ecosystems))}; {len(all_findings)} finding(s) at or above threshold."
    summary += summary_notes
    return _findings_result(all_findings, summary)


def scan_command(args):
    changed_files_path = Path(args.changed_files)
    try:
        changed_text = changed_files_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ExecutionError(f"cannot read --changed-files: {exc}")
    try:
        changed_files = json.loads(changed_text)
    except json.JSONDecodeError as exc:
        raise ExecutionError(f"--changed-files is not valid JSON: {exc}")
    if not isinstance(changed_files, list):
        raise ExecutionError("--changed-files must be a JSON array of strings")

    registry_path = Path(args.registry) if args.registry else DEFAULT_REGISTRY_PATH
    return run_scan(Path(args.project_root), changed_files, registry_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(prog="scan-dependencies.py")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    scan_parser = sub.add_parser(
        "scan",
        help="run axis 2's ecosystem detection, tool execution and normalize pass",
    )
    scan_parser.add_argument("--project-root", required=True)
    scan_parser.add_argument(
        "--changed-files",
        required=True,
        help="path to a JSON file holding an array of changed file paths (project-relative)",
    )
    scan_parser.add_argument(
        "--registry",
        default=None,
        help="registry path override (default: the plugin's own references/vuln-scanners.yaml)",
    )
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
