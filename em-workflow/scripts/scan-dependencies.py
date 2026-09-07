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


def _entry_point_is_valid(entry_point):
    """Returns True when entry_point is an existing regular file that is
    executable. Callers must not exec entry_point unless this passes."""
    try:
        path = Path(entry_point)
        return path.is_file() and os.access(path, os.X_OK)
    except OSError:
        return False


def list_security_tasks(entry_point):
    """Returns a list of {"id", "package", "status", "references"} dicts
    describing every task of the security type, or None when the listing
    could not be obtained (non-zero exit, stdout that is not a JSON array,
    or entry_point failing validation) -- the caller degrades to the report
    branch (IMPLEMENTATION.md D6). `status` is one of "incomplete" /
    "complete" / "discarded"; `references` is the raw current 参照 field
    text (possibly empty, possibly multi-line)."""
    if not _entry_point_is_valid(entry_point):
        return None
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
    validated = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        if not isinstance(entry.get("id"), str):
            continue
        if not isinstance(entry.get("package"), str):
            continue
        if not isinstance(entry.get("status"), str):
            continue
        references = entry.get("references")
        if references is not None and not isinstance(references, str):
            continue
        validated.append(entry)
    if not validated:
        return None
    return validated


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
# Scan job construction (IMPLEMENTATION.md Shared Components, "Scan job";
# task0008 Design, "The scan job" / "Trusted binary, never a multiplexer
# subcommand" / "Configuration isolation"). PURE: no subprocess is launched
# by anything in this section. Pre: the registry entry has already passed
# validate_ecosystem_entry and its executable has already resolved on PATH
# (resolve_executable) -- an unresolvable/invalid entry yields no job and
# the ecosystem's existing tool-absent skip reason instead (build_scan_jobs
# below), never a fallback command form.
# ---------------------------------------------------------------------------

# Process plumbing carried through unchanged when present -- locating the
# shell, temp space, the already-resolved binary on PATH -- never a source
# of a TOOL'S OWN configuration (a registry endpoint, a subcommand alias).
# Everything else the reviewed project's environment might carry is left
# out: the child environment is built explicitly, never inherited
# wholesale (task0008 Design, "Configuration isolation").
CHILD_ENV_BASE_KEYS = ("PATH", "HOME", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT", "USERPROFILE")

# Per-ecosystem pins, each through the tool's OWN documented environment
# variable, keeping the reviewed project's configuration out of the set the
# child process reads from:
#   npm   -- npm_config_registry pins the package-registry endpoint ahead of
#            a hostile `registry=` line in the reviewed project's own
#            .npmrc (environment variables outrank a project .npmrc in
#            npm's own documented config precedence); npm_config_userconfig
#            points the user-level config file outside the reviewed tree.
#   cargo -- cargo-audit is resolved and executed directly (never through
#            the `cargo` front end -- see ALLOWED_EXECUTABLES), which
#            already removes the [alias] dispatch the registry's OLD
#            `cargo audit` form was vulnerable to; no further pin closes a
#            vector for this ecosystem today.
#   pip   -- PIP_CONFIG_FILE keeps a reviewed project's own pip.conf from
#            being read; PIP_INDEX_URL pins the package index.
#   go    -- GOENV=off disables reading any go env config file at all;
#            GOFLAGS is pinned empty and GOPROXY pinned to the public
#            module proxy so neither can be redirected by one.
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
        "GOFLAGS": "",
        "GOPROXY": "https://proxy.golang.org,direct",
    },
}


def build_child_env(ecosystem, environ=None):
    """The explicit child environment for one scan job: a minimal base
    (process plumbing only, see CHILD_ENV_BASE_KEYS) plus this ecosystem's
    pins (ECOSYSTEM_ENV_PINS) layered on top. Never reads any file inside
    the reviewed project -- the result is identical regardless of what
    configuration files that project's tree happens to contain."""
    environ = os.environ if environ is None else environ
    name = ecosystem.get("ecosystem", "unknown")
    env = {key: environ[key] for key in CHILD_ENV_BASE_KEYS if key in environ}
    env.update(ECOSYSTEM_ENV_PINS.get(name, {}))
    return env


def _pip_target(manifest_file):
    """task0008 Design, "The pip job audits the reviewed project, not the
    ambient environment": a changed requirements file IS the audited
    input, paired with the registry's `target_flag`. Anything else
    selected for pip (a changed pyproject.toml, or a changed poetry.lock /
    Pipfile.lock) audits that project's OWN DIRECTORY instead, as a bare
    positional argument with no flag -- pip-audit's `-r` flag parses pip's
    own requirements format, not a TOML/JSON lock format, so a lockfile or
    a manifest that only declares version ranges is never passed to it
    directly. Returns (flagged, target): `flagged` is True when the
    registry's `target_flag` belongs immediately before `target` in the
    argument vector."""
    if os.path.basename(manifest_file) == "requirements.txt":
        return True, manifest_file
    dirname = os.path.dirname(manifest_file)
    return False, (dirname if dirname else ".")


def build_scan_job(ecosystem, manifest_file, project_root, executable_path, environ=None):
    """Builds ONE scan job from `ecosystem`'s ALREADY-RESOLVED absolute
    `executable_path` (never re-resolved here -- see build_scan_jobs).
    Carries: the ecosystem name; the project-relative `manifest_file`; the
    full argument vector (`argv[0]` is the absolute, allowlisted executable
    path -- never a package-manager front end resolving a subcommand
    through the reviewed project's own configuration); the working
    directory (the reviewed project's own root -- still the thing being
    audited, NFR2's read-only discipline unchanged); and the explicit
    child environment (build_child_env). Launches nothing -- every claim
    about the resulting command is assertable without running a scanner."""
    name = ecosystem.get("ecosystem", "unknown")
    argv = [executable_path]
    if name == "pip":
        flagged, target = _pip_target(manifest_file)
        target_flag = ecosystem.get("target_flag")
        if flagged and target_flag:
            argv.append(target_flag)
        argv.append(target)
    argv.extend(ecosystem.get("args") or [])
    return {
        "ecosystem": name,
        "manifest": manifest_file,
        "argv": argv,
        "cwd": str(project_root),
        "env": build_child_env(ecosystem, environ),
    }


def build_scan_jobs(registry, changed_files, project_root, environ=None):
    """Orchestrates job construction for every SELECTED ecosystem
    (select_ecosystems, unchanged): validates each entry
    (validate_ecosystem_entry), resolves its executable on PATH
    (resolve_executable), and builds a job for it (build_scan_job). An
    invalid entry or an unresolvable binary contributes its existing
    machine-stable skip reason and NO job -- no fallback command form is
    ever attempted for it. Returns (jobs, skip_reasons); executing a job
    (judging its exit status and payload together) is the sibling rework
    task's contract, not this function's."""
    selected = select_ecosystems(registry, changed_files)
    jobs = []
    skip_reasons = []
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
        manifest_file = manifest_file_for(ecosystem, changed_files)
        jobs.append(build_scan_job(ecosystem, manifest_file, project_root, executable_path, environ))
    return jobs, skip_reasons


def run_ecosystem_command(ecosystem, project_root):
    """Runs the registry's command form against the existing lockfile, cwd
    at the project root, reading only -- nothing here writes inside the
    project root (NFR2). Returns (parsed_json_or_None, error_or_None).

    A non-zero exit is NOT itself an error -- audit tools commonly exit
    non-zero precisely when they found something to report. Only
    unparseable stdout (empty results count as `{}`, not a parse failure)
    or an OS-level failure to even launch the process is an error, and it
    is surfaced as a machine-stable skip reason -- never as an empty
    successful scan, which would silently claim the ecosystem is clean."""
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
        return None, f"{name}_execution_failed"
    stdout = proc.stdout.strip()
    if not stdout:
        return {}, None
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        try:
            objs = _parse_json_stream(stdout)
        except json.JSONDecodeError:
            return None, f"{name}_unparseable_output"
        if not objs:
            return None, f"{name}_unparseable_output"
        if name == "go":
            data = {"vulns": _merge_govulncheck_stream(objs)}
        elif len(objs) == 1:
            data = objs[-1]
        else:
            return None, f"{name}_unparseable_output"
    return data, None


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


# ---------------------------------------------------------------------------
# pip direct-dependency resolution (task0008 Design, "The pip normalizer's
# real input contract"): pip-audit's `--format json` output carries no
# per-dependency directness flag, so directness is resolved from the
# reviewed manifest's own declared dependency set -- the same SHAPE of
# resolution the cargo path already performs against Cargo.toml
# (_cargo_direct_dependency_names), reusing _resolve_project_relative so a
# changed-file entry can never open a file outside the project root.
# ---------------------------------------------------------------------------

_REQUIREMENTS_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]*")


def _pip_requirements_direct_names(content):
    """Package names declared in a requirements.txt-style file: option
    lines (-e, -r, --hash, ...), blank lines and comments are skipped; an
    extras suffix (`pkg[extra]`) and an environment marker (`; ...`) are
    stripped before the bare package name is matched."""
    names = set()
    for raw_line in content.splitlines():
        stripped = raw_line.split("#", 1)[0].strip()
        if not stripped or stripped.startswith("-"):
            continue
        stripped = stripped.split(";", 1)[0].strip()
        stripped = re.sub(r"\[[^\]]*\]", "", stripped)
        match = _REQUIREMENTS_NAME_RE.match(stripped)
        if match:
            names.add(match.group(0))
    return names


_POETRY_DEP_TABLES = {"tool.poetry.dependencies", "tool.poetry.dev-dependencies"}
_POETRY_TABLE_KEY_RE = re.compile(r'^"?([A-Za-z0-9][A-Za-z0-9_.\-]*)"?\s*=')
_PEP508_NAME_HEAD_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]*")


def _extract_pep508_name(entry):
    """The bare package name from one PEP 508 dependency string (e.g.
    `"requests[socks]>=2.25; python_version >= '3.7'"` -> `requests`)."""
    entry = entry.split(";", 1)[0]            # drop an environment marker
    entry = re.sub(r"\[[^\]]*\]", "", entry)   # drop an extras suffix
    match = _PEP508_NAME_HEAD_RE.match(entry.strip())
    return match.group(0) if match else None


def _pip_pyproject_direct_names(content):
    """Package names declared in pyproject.toml's PEP 621 `[project]`
    `dependencies` list, or Poetry's `[tool.poetry.dependencies]` /
    `[tool.poetry.dev-dependencies]` tables -- a lightweight TOML-lite
    scan, the same shape as the cargo path's own Cargo.toml scan (neither
    pip-audit's nor cargo-audit's JSON carries a per-entry directness field
    to read this from directly)."""
    names = set()
    current_table = None
    in_dependencies_list = False
    for raw_line in content.splitlines():
        line = raw_line.split("#", 1)[0]
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            current_table = stripped.strip("[]").strip()
            in_dependencies_list = False
            continue
        if current_table == "project":
            if re.match(r"^dependencies\s*=\s*\[", stripped):
                in_dependencies_list = True
                stripped = re.sub(r"^dependencies\s*=\s*\[", "", stripped)
            if in_dependencies_list:
                for entry in re.findall(r'"([^"]+)"', stripped):
                    name = _extract_pep508_name(entry)
                    if name:
                        names.add(name)
                if "]" in stripped:
                    in_dependencies_list = False
                continue
        if current_table in _POETRY_DEP_TABLES:
            match = _POETRY_TABLE_KEY_RE.match(stripped)
            if match and match.group(1).lower() != "python":
                names.add(match.group(1))
    return names


def _pip_manifest_candidate(project_root, manifest_file):
    """Resolves the manifest to scan for direct-dependency names. When
    manifest_file is itself a lockfile (poetry.lock / Pipfile.lock --
    selected by manifest_file_for when only the lockfile changed), looks
    for pyproject.toml alongside it instead, mirroring
    _cargo_manifest_candidate's resolution -- a lockfile carries no
    dependency TABLE to scan. Never returns a lockfile path. Returns None
    when unresolvable/unsafe (see _resolve_project_relative)."""
    if os.path.basename(manifest_file) in {"poetry.lock", "Pipfile.lock"}:
        candidate_rel = os.path.join(os.path.dirname(manifest_file), "pyproject.toml")
    else:
        candidate_rel = manifest_file
    return _resolve_project_relative(project_root, candidate_rel)


def _pip_direct_dependency_names(project_root, manifest_file):
    manifest_path = _pip_manifest_candidate(project_root, manifest_file)
    if not manifest_path:
        return set()
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return set()
    if os.path.basename(manifest_path) == "pyproject.toml":
        return _pip_pyproject_direct_names(content)
    return _pip_requirements_direct_names(content)


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


def _pip_severity_from_description(ecosystem, description):
    """Returns the mapped severity (per this ecosystem's severity_map) when
    `description` embeds a CVSS v3 vector, else None -- "cannot be
    determined from that output" (task0008 Design), never a guess."""
    if not isinstance(description, str):
        return None
    match = _CVSS_VECTOR_RE.search(description)
    if not match:
        return None
    band = _cvss_severity_band(match.group(0))
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
    as `skip_info` for the caller to fold into the machine-readable skip
    surface and the summary's affected count (NFR4: counts only, no
    advisory-sourced text). Returns (findings, skip_info); skip_info is
    None when nothing was undetermined."""
    findings = []
    direct_names = _pip_direct_dependency_names(project_root, manifest_file) if project_root else set()
    undetermined_count = 0
    for dep in data.get("dependencies") or []:
        if not isinstance(dep, dict):
            continue
        package = dep.get("name", "unknown")
        is_direct = package in direct_names
        for vuln in dep.get("vulns") or []:
            if not isinstance(vuln, dict):
                continue
            description = vuln.get("description")
            mapped = _pip_severity_from_description(ecosystem, description)
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
    skip_info = {"reason": "pip_severity_undetermined", "count": undetermined_count} if undetermined_count else None
    return findings, skip_info


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


def _skip_result(skip_reason, summary):
    return {
        "findings": [],
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
    """AC-1..AC-7 flow: select ecosystems, resolve each on PATH, run its
    registry command, normalize with a threshold applied at normalization
    time, and emit exactly one review-output-schema.json-conformant object.

    - No manifest in the change: an empty, non-skipped result.
    - A selected ecosystem's executable is not resolvable on PATH: that
      ecosystem contributes a skip reason (no fallback of any kind).
    - Tool-execution failure that is not "tool absent" (unparseable
      output, a process that cannot be launched) contributes its own
      machine-stable skip reason.
    - When every selected ecosystem skipped/failed and nothing was found,
      the whole result is `skipped: true` with the combined reasons. When
      at least one ecosystem produced findings (even zero), the result is
      NOT skipped -- any other ecosystem's skip is folded into `summary`
      prose instead (the schema has one `skipped`/`skip_reason` pair for
      the whole object, never per-ecosystem).
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
    pip_severity_undetermined_total = 0
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
        data, error = run_ecosystem_command(ecosystem, project_root)
        if error is not None:
            skip_reasons.append(error)
            continue
        normalizer = NORMALIZERS.get(name)
        if normalizer is None:
            skip_reasons.append(f"{name}_no_normalizer")
            continue
        manifest_file = manifest_file_for(ecosystem, changed_files)
        if name == "cargo":
            all_findings.extend(normalizer(ecosystem, data, manifest_file, project_root))
        elif name == "pip":
            # task0008 AC-7: an advisory whose severity cannot be
            # determined from pip-audit's own output is never silently
            # treated as below threshold -- normalize_pip excludes it from
            # findings but reports it via skip_info instead, folded here
            # into the SAME machine-readable skip surface every other
            # ecosystem's reasons use, plus a counts-only summary note
            # (no advisory-sourced text in either -- NFR4).
            pip_findings, pip_skip = normalizer(ecosystem, data, manifest_file, project_root)
            all_findings.extend(pip_findings)
            if pip_skip:
                skip_reasons.append(pip_skip["reason"])
                pip_severity_undetermined_total += pip_skip["count"]
        else:
            all_findings.extend(normalizer(ecosystem, data, manifest_file))
        ran_ecosystems.append(name)

    if not ran_ecosystems:
        combined_reason = "+".join(sorted(skip_reasons)) if skip_reasons else "no_ecosystem_ran"
        summary = "Scan skipped: " + "; ".join(sorted(skip_reasons)) if skip_reasons else "Scan skipped."
        return _skip_result(combined_reason, summary)

    summary = f"Scanned {', '.join(sorted(ran_ecosystems))}; {len(all_findings)} finding(s) at or above threshold."
    if skip_reasons:
        summary += " Skipped: " + "; ".join(sorted(skip_reasons)) + "."
    if pip_severity_undetermined_total:
        noun = "advisory" if pip_severity_undetermined_total == 1 else "advisories"
        summary += f" {pip_severity_undetermined_total} pip {noun} with undetermined severity."
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
