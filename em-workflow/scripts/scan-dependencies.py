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
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

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
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write("\n".join(reference_lines) + "\n")
        return fh.name


def create_security_task(entry_point, package, reference_lines):
    if not _entry_point_is_valid(entry_point):
        raise EntryPointError(f"entry point {entry_point!r} is not an executable file")
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
    if not _entry_point_is_valid(entry_point):
        raise EntryPointError(f"entry point {entry_point!r} is not an executable file")
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
    nothing new.

    Every pre-existing key (`branch`, `filed_packages`, `appended_packages`,
    `suppressed`, `report_path`, `degraded`, `degraded_reason`) keeps its
    name and meaning (task plan "the summary dict grows, never changes
    shape"). Four keys are ADDED:

    - `malformed_findings` -- findings skipped by the poison-finding policy
      (position + machine-stable reason, never advisory-sourced text).
    - `listing_dropped_count` -- entries the task listing dropped item-wise
      by validation (0 when no listing was consulted or nothing dropped).
    - `failed_package` / `failure_reason` -- set when the external task
      system failed mid-batch; both None on a batch that completed without
      such a failure. No exception escapes this function for a poison
      finding or a mid-batch external failure -- both degrade to data in
      the returned summary instead."""
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
    "cargo": {"cargo"},
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
    return shutil.which(name)


def manifest_file_for(ecosystem, changed_files):
    """The first changed file whose basename is one of this ecosystem's
    manifests -- a project-relative path, so R3b step 1's existence check
    passes. Falls back to the registry's own first manifest name (never
    reached in practice, since an ecosystem is only selected when a
    matching changed file exists -- see select_ecosystems)."""
    manifests = set(ecosystem.get("manifests") or [])
    lockfiles = ECOSYSTEM_LOCKFILES.get(ecosystem.get("ecosystem", "unknown"), set())
    for f in changed_files:
        if os.path.basename(f) in manifests:
            return f
    for f in changed_files:
        if os.path.basename(f) in lockfiles:
            return f
    manifest_list = ecosystem.get("manifests") or ["unknown"]
    return manifest_list[0]


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
    if name == "go":
        return isinstance(data.get("vulns"), list)
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
    because it applies "regardless of exit status" (Design)."""
    stripped = (stdout or "").strip()
    if not stripped:
        return OUTCOME_NOT_COMPLETED, f"{name}_empty_output"

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        try:
            objs = _parse_json_stream(stripped)
        except json.JSONDecodeError:
            return OUTCOME_NOT_COMPLETED, f"{name}_unparseable_output"
        if not objs:
            return OUTCOME_NOT_COMPLETED, f"{name}_unparseable_output"
        if name == "go":
            data = {"vulns": _merge_govulncheck_stream(objs)}
        elif len(objs) == 1:
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


def run_ecosystem_command(ecosystem, project_root):
    """Runs the registry's command form against the existing lockfile, cwd
    at the project root, reading only -- nothing here writes inside the
    project root (NFR2). Returns `(outcome, payload)`: `payload` is the
    parsed data dict when `outcome` is `OUTCOME_COMPLETED`, or the
    machine-stable reason string when `OUTCOME_NOT_COMPLETED` (see
    `judge_scan_outcome`). An OS-level failure to even launch the process
    is its own `not_completed` reason, distinct from every reason
    `judge_scan_outcome` can produce from an actual process result."""
    name = ecosystem.get("ecosystem", "unknown")
    command = build_command(ecosystem)
    try:
        proc = subprocess.run(
            command,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=300,
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
    """Reduces govulncheck -json's NDJSON stream (separate {"osv": ...} and
    {"finding": ...} objects) to the same vulns-list shape normalize_go
    already reads (one dict per vuln carrying "osv", "is_direct",
    "severity", "package") -- keeps normalize_go itself unchanged so the
    existing single-object GO_FIXTURE shape still works too."""
    osv_by_id = {}
    for obj in objs:
        if isinstance(obj, dict) and isinstance(obj.get("osv"), dict) and "id" in obj["osv"]:
            osv_by_id[obj["osv"]["id"]] = obj["osv"]

    vulns = []
    for obj in objs:
        if not isinstance(obj, dict):
            continue
        finding = obj.get("finding")
        if not isinstance(finding, dict):
            continue
        osv_id = finding.get("osv")
        osv = osv_by_id.get(osv_id) or {"id": osv_id}
        trace = finding.get("trace") or []
        package = trace[0].get("module") if trace and isinstance(trace[0], dict) else None
        severity = osv.get("database_specific", {}).get("severity") if isinstance(osv.get("database_specific"), dict) else None
        vulns.append(
            {
                "osv": osv,
                "is_direct": len(trace) == 1,
                "severity": severity,
                "package": package or "unknown",
            }
        )
    return vulns


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


def _build_finding(*, manifest_file, package, advisory_id, title, affected_range,
                    fixed_version, summary, severity):
    """IMPLEMENTATION.md "Finding text-encoding contract": `title` is
    `{package}: {advisory_id} — {advisory short title}`; `description`
    carries the affected range, the fixed version and the advisory summary;
    `suggestion` is prose only (D4 -- never diff-shaped, so a vulnerability
    finding can never be classified auto-applicable). Every advisory-sourced
    string passes through `truncate_untrusted()` -- the SAME helper
    `file_tasks` uses, per IMPLEMENTATION.md's single-helper contract."""
    title_text = truncate_untrusted(f"{package}: {advisory_id} — {title}")
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


_CARGO_DEP_TABLES = {"dependencies", "dev-dependencies", "build-dependencies"}


def _cargo_direct_dependency_names(manifest_path):
    """Package names declared in Cargo.toml's [dependencies],
    [dev-dependencies] and [build-dependencies] tables (including their
    target-specific forms, e.g. target.'cfg(unix)'.dependencies) -- a
    lightweight TOML-lite scan rather than a full parser, since cargo
    audit's JSON output carries no per-entry "is_direct" field to read
    directness from directly."""
    names = set()
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return names
    current_table = None
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped.strip("[]").strip()
            current_table = section.rsplit(".", 1)[-1]
            continue
        if current_table in _CARGO_DEP_TABLES:
            match = re.match(r'^"?([A-Za-z0-9_.\-]+)"?\s*=', stripped)
            if match:
                names.add(match.group(1))
    return names


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


def normalize_cargo(ecosystem, data, manifest_file, project_root=None):
    findings = []
    entries = ((data.get("vulnerabilities") or {}).get("list")) or []
    manifest_path = _cargo_manifest_candidate(project_root, manifest_file)
    direct_names = _cargo_direct_dependency_names(manifest_path) if manifest_path else set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        advisory = entry.get("advisory") or {}
        package = (entry.get("package") or {}).get("name", "unknown")
        if "is_direct" in entry:
            is_direct = bool(entry.get("is_direct"))
        else:
            is_direct = package in direct_names
        raw_severity = _cvss_severity_band(advisory.get("cvss"))
        if raw_severity is None:
            raw_severity = entry.get("severity")
        mapped = _map_severity(ecosystem, raw_severity)
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
    return findings


def normalize_pip(ecosystem, data, manifest_file):
    findings = []
    for dep in data.get("dependencies") or []:
        if not isinstance(dep, dict):
            continue
        is_direct = bool(dep.get("direct"))
        package = dep.get("name", "unknown")
        for vuln in dep.get("vulns") or []:
            if not isinstance(vuln, dict):
                continue
            mapped = _map_severity(ecosystem, vuln.get("severity"))
            if not _passes_threshold(ecosystem, is_direct, mapped):
                continue
            fix_versions = vuln.get("fix_versions") or []
            findings.append(
                _build_finding(
                    manifest_file=manifest_file,
                    package=package,
                    advisory_id=vuln.get("id", "UNKNOWN"),
                    title=vuln.get("description") or vuln.get("id") or "vulnerability",
                    affected_range=dep.get("version"),
                    fixed_version=fix_versions[0] if fix_versions else None,
                    summary=vuln.get("description"),
                    severity=mapped,
                )
            )
    return findings


def normalize_go(ecosystem, data, manifest_file):
    findings = []
    for entry in data.get("vulns") or []:
        if not isinstance(entry, dict):
            continue
        osv = entry.get("osv") or {}
        is_direct = bool(entry.get("is_direct"))
        mapped = _map_severity(ecosystem, entry.get("severity"))
        if not _passes_threshold(ecosystem, is_direct, mapped):
            continue
        fixed_version = None
        for affected in osv.get("affected") or []:
            for rng in affected.get("ranges") or []:
                for event in rng.get("events") or []:
                    if isinstance(event, dict) and "fixed" in event:
                        fixed_version = event["fixed"]
        findings.append(
            _build_finding(
                manifest_file=manifest_file,
                package=entry.get("package") or "unknown",
                advisory_id=osv.get("id", "UNKNOWN"),
                title=osv.get("summary") or osv.get("id") or "vulnerability",
                affected_range=None,
                fixed_version=fixed_version,
                summary=osv.get("details"),
                severity=mapped,
            )
        )
    return findings


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


def run_scan(project_root, changed_files, registry_path):
    """AC-1..AC-7 (task0001) plus this task's partial-coverage contract:
    select ecosystems, resolve each on PATH, execute its scan job and judge
    the ONE outcome that execution yields (`judge_scan_outcome`), normalize
    completed payloads with a threshold applied at normalization time, and
    emit exactly one review-output-schema.json-conformant object.

    - No manifest in the change: an empty, non-skipped result.
    - A selected ecosystem's executable is not resolvable on PATH: that
      ecosystem contributes a `not_completed` reason (no fallback of any
      kind) -- the same accounting as an execution `not_completed` outcome.
    - `skipped` is `true` whenever ANY selected ecosystem did not complete
      (tool absent, validation failure, or an execution outcome of
      `not_completed`), with `skip_reason` carrying every such reason
      combined in a deterministic (sorted) order. `findings` still carries
      everything the COMPLETED ecosystems produced -- a skip about one
      ecosystem never suppresses another's advisories (task plan Design,
      "Partial coverage is machine-readable, not prose"). `skipped: false`
      with `skip_reason: null` therefore means, and only means, that every
      selected ecosystem completed.
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

    all_findings = []
    skip_reasons = []
    ran_ecosystems = []
    for ecosystem in selected:
        name = ecosystem.get("ecosystem", "unknown")
        validation_error = validate_ecosystem_entry(ecosystem)
        if validation_error is not None:
            skip_reasons.append(validation_error)
            continue
        executable_path = resolve_executable(ecosystem.get("executable"))
        if executable_path is None:
            skip_reasons.append(f"{name}_tool_not_found")
            continue
        outcome, payload = run_ecosystem_command(ecosystem, project_root)
        if outcome == OUTCOME_NOT_COMPLETED:
            skip_reasons.append(payload)
            continue
        data = payload
        normalizer = NORMALIZERS.get(name)
        if normalizer is None:
            skip_reasons.append(f"{name}_no_normalizer")
            continue
        manifest_file = manifest_file_for(ecosystem, changed_files)
        if name == "cargo":
            all_findings.extend(normalizer(ecosystem, data, manifest_file, project_root))
        else:
            all_findings.extend(normalizer(ecosystem, data, manifest_file))
        ran_ecosystems.append(name)

    if skip_reasons:
        combined_reason = "+".join(sorted(skip_reasons))
        if ran_ecosystems:
            summary = (
                f"Scanned {', '.join(sorted(ran_ecosystems))}; "
                f"{len(all_findings)} finding(s) at or above threshold. "
                f"Not completed: {', '.join(sorted(skip_reasons))}."
            )
        else:
            summary = "Scan skipped: " + "; ".join(sorted(skip_reasons))
        return _skip_result(combined_reason, summary, findings=all_findings)

    summary = f"Scanned {', '.join(sorted(ran_ecosystems))}; {len(all_findings)} finding(s) at or above threshold."
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
